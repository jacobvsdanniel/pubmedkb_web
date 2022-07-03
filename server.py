import csv
import sys
import html
import json
import logging
import argparse

from flask import Flask, render_template, request

from kb_utils import KB, DiskKB

app = Flask(__name__)
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
    level=logging.INFO,
)
csv.register_dialect(
    "csv", delimiter=",", quoting=csv.QUOTE_MINIMAL, quotechar='"', doublequote=True,
    escapechar=None, lineterminator="\n", skipinitialspace=False,
)
csv.register_dialect(
    "tsv", delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None, doublequote=False,
    escapechar=None, lineterminator="\n", skipinitialspace=False,
)
kb = None


@app.route("/")
def serve_home():
    return render_template("home.html")


@app.route("/nen")
def serve_nen():
    return render_template("nen.html")


@app.route("/rel")
def serve_rel():
    return render_template("rel.html")


@app.route("/run_nen", methods=["POST"])
def run_nen():
    data = json.loads(request.data)

    query = data["query"].strip()
    case_sensitive = data["case_sensitive"] == "Y"
    max_length_diff = int(data["max_length_diff"])
    min_similarity = float(data["min_similarity"])
    max_names = int(data["max_names"])
    max_aliases = int(data["max_aliases"])

    logger.info(
        f"query={query}"
        f" case_sensitive={case_sensitive}"
        f" max_length_diff={max_length_diff}"
        f" min_similarity_ratio={min_similarity}"
        f" max_aliases={max_aliases}"
    )

    name_similarity_list = kb.nen.get_names_by_query(
        query,
        case_sensitive=case_sensitive,
        max_length_diff=max_length_diff,
        min_similarity=min_similarity,
        max_names=max_names,
    )
    names = len(name_similarity_list)
    logger.info(f"{names:,} names")

    result = ""

    for name, similarity in name_similarity_list:
        # name
        logger.info(f"name: {name}, similarity: {similarity}")
        caption_html = html.escape(f"Name: {name}") + "&nbsp;" * 4 + html.escape(f"Similarity: {similarity:.0%}")
        result += f"<label style='font-size: 22px;'>{caption_html}</label><br /><br />"

        # id
        type_id_frequency_list = kb.nen.get_ids_by_name(name)
        ids = len(type_id_frequency_list)
        logger.info(f"ids: {ids}")
        table_html = \
            f"<table><tr>" \
            f"<th>Type</th>" \
            f"<th>ID</th>" \
            f"<th>Frequency of (Type, ID, Name) in all texts</th>" \
            f"<th>Top {max_aliases:,} aliases by frequency of (Type, ID, Alias) in all texts</th>" \
            f"</tr>"

        # alias
        for _type, _id, id_frequency in type_id_frequency_list:
            alias_frequency_list = kb.nen.get_aliases_by_id(_type, _id, max_aliases=max_aliases)
            logger.info(f"({_type}, {_id}, {name}, {id_frequency}): alias_list={alias_frequency_list}")

            type_html = html.escape(_type)
            id_html = html.escape(_id)
            id_frequency_html = html.escape(f"{id_frequency:,}")

            table_html += \
                f"<tr>" \
                f"<td>{type_html}</td>" \
                f"<td>{id_html}</td>" \
                f"<td>{id_frequency_html}</td>" \
                f"<td>"
            for alias, alias_frequency in alias_frequency_list:
                alias_html = html.escape(f"{alias} ({alias_frequency:,})")
                table_html += "&nbsp;&nbsp;&nbsp;&nbsp;" + alias_html
            table_html += "</td></tr>"

        table_html += "</table>"
        result += table_html + "<br /><br /><br />"

    response = {"result": result}
    return json.dumps(response)


@app.route("/run_rel", methods=["POST"])
def run_rel():
    data = json.loads(request.data)

    # input: e1
    e1_filter = data["e1_filter"]
    e1_type = data["e1_type"]
    e1_id = data["e1_id"].strip()
    e1_name = data["e1_name"].strip()
    if e1_filter == "type_id_name":
        e1 = (e1_type, e1_id, e1_name)
    elif e1_filter == "type_id":
        e1 = (e1_type, e1_id)
    elif e1_filter == "type_name":
        e1 = (e1_type, e1_name)
    else:
        assert False

    # input: e2
    e2_filter = data["e2_filter"]
    e2_type = data["e2_type"]
    e2_id = data["e2_id"].strip()
    e2_name = data["e2_name"].strip()
    if e2_filter == "type_id_name":
        e2 = (e2_type, e2_id, e2_name)
    elif e2_filter == "type_id":
        e2 = (e2_type, e2_id)
    elif e2_filter == "type_name":
        e2 = (e2_type, e2_name)
    else:
        assert False

    # input: query
    query_filter = data["query_filter"]
    query_rels = int(data["query_rels"])
    query_pmid = data["query_pmid"].strip()

    logger.info(f"[Entity A] key={e1_filter} value={e1}")
    logger.info(f"[Entity A] key={e2_filter} value={e2}")
    logger.info(f"[Query] filter={query_filter} #rel={query_rels:,} pmid={query_pmid}")

    # query rel ids
    if query_filter == "PMID":
        rel_id_list = kb.get_evidence_ids_by_pmid(query_pmid)
    elif query_filter == "AB":
        rel_id_list = kb.get_evidence_ids_by_pair((e1, e2), key=(e1_filter, e2_filter))
    elif query_filter == "A":
        rel_id_list = kb.get_evidence_ids_by_entity(e1, key=e1_filter)
    elif query_filter == "B":
        rel_id_list = kb.get_evidence_ids_by_entity(e2, key=e2_filter)
    else:
        assert False
    rel_ids = len(rel_id_list)
    logger.info(f"Total #rel = {rel_ids:,}")

    # collect rel by annotator
    annotator_list = ["odds_ratio", "rbert_cre", "spacy_ore", "openie_ore"]
    annotator_to_rel = {annotator: [] for annotator in annotator_list}
    full_annotator_set = set()
    rels = 0
    for rel_id in rel_id_list:
        head, tail, annotation, pmid, sentence = kb.get_evidence_by_id(
            rel_id, return_annotation=True, return_sentence=True,
        )
        annotator, annotation = annotation
        if len(annotator_to_rel[annotator]) >= query_rels:
            full_annotator_set.add(annotator)
            if len(full_annotator_set) == len(annotator_list):
                break
            continue
        head = ", ".join(head)
        tail = ", ".join(tail)
        if annotator == "odds_ratio":
            annotation = f"OR: {annotation[0]}, CI: {annotation[1]}, p-value: {annotation[2]}"
        elif annotator == "rbert_cre":
            annotation = f"{annotation[0]}: {annotation[1]}"
        else:
            annotation = ", ".join(annotation)
        annotator_to_rel[annotator].append((head, tail, annotation, pmid, sentence))
        rels += 1

    # create html result
    result = ""

    annotator_table_html = f"<table><tr>"
    for annotator in annotator_list:
        annotator_table_html += f"<th>{annotator}</th>"
    annotator_table_html += "</tr><tr>"
    for annotator in annotator_list:
        rels = len(annotator_to_rel[annotator])
        logger.info(f"{annotator}: {rels:,} rels")
        annotator_table_html += f"<td>{rels:,}</td>"
    annotator_table_html += "</tr><table>"

    result += f"{annotator_table_html}<br /><br />"

    rel_table_html = \
        f"<table><tr>" \
        f'<th style="width:20%">Head</th>' \
        f'<th style="width:20%">Tail</th>' \
        f'<th style="width:5%">Annotator</th>' \
        f'<th style="width:20%">Annotation</th>'\
        f'<th style="width:5%">PMID</th>' \
        f'<th style="width:30%">Sentence</th>' \
        f"</tr>"

    for annotator in annotator_list:
        rel_list = annotator_to_rel[annotator]
        annotator_html = html.escape(annotator)

        for head, tail, annotation, pmid, sentence in rel_list:
                head_html = html.escape(str(head))
                tail_html = html.escape(str(tail))
                annotation_html = html.escape(str(annotation))
                pmid_html = html.escape(pmid)
                sentence_html = html.escape(sentence)

                rel_table_html += \
                    f"<tr>" \
                    f"<td>{head_html}</td>" \
                    f"<td>{tail_html}</td>" \
                    f"<td>{annotator_html}</td>" \
                    f"<td>{annotation_html}</td>" \
                    f"<td>{pmid_html}</td>" \
                    f"<td>{sentence_html}</td>" \
                    f"</tr>"

    rel_table_html += "</table><br /><br /><br /><br /><br /><br /><br /><br /><br /><br />"
    result += rel_table_html

    response = {"result": result}
    return json.dumps(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-host", default="0.0.0.0")
    parser.add_argument("-port", default="12345")
    parser.add_argument("--kb_dir", default="diskkb")
    parser.add_argument("--kb_type", default="disk", choices=["memory", "disk"])
    arg = parser.parse_args()

    global kb
    kb = KB(arg.kb_dir) if arg.kb_type == "memory" else DiskKB(arg.kb_dir)
    kb.load_nen()
    kb.load_data()
    kb.load_index()

    app.run(host=arg.host, port=arg.port)
    return


if __name__ == "__main__":
    main()
    sys.exit()
