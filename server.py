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
show_eid, eid_list = False, []


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
    logger.info(f"[Entity B] key={e2_filter} value={e2}")
    logger.info(f"[Query] filter={query_filter} #rel={query_rels:,} pmid={query_pmid}")

    # query rel ids
    if eid_list:
        rel_id_list = eid_list
    elif query_filter == "PMID":
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

    # group evidence by annotation
    annotation_id_to_rel = {}
    for rel_id in rel_id_list:
        head, tail, annotation_id, _pmid, _sentence_id = kb.get_evidence_by_id(
            rel_id, return_annotation=False, return_sentence=False,
        )
        if annotation_id not in annotation_id_to_rel:
            head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
                rel_id, return_annotation=True, return_sentence=True,
            )
            annotation_id_to_rel[annotation_id] = {
                "head_set": {tuple(head)}, "tail_set": {tuple(tail)},
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence,
                "evidence_id": [rel_id],
            }
        else:
            annotation_id_to_rel[annotation_id]["head_set"].add(tuple(head))
            annotation_id_to_rel[annotation_id]["tail_set"].add(tuple(tail))
            annotation_id_to_rel[annotation_id]["evidence_id"].append(rel_id)
    del rel_id_list

    # collect rel by annotator
    annotator_list = ["odds_ratio", "rbert_cre", "spacy_ore", "openie_ore"]
    annotator_to_rel = {annotator: [] for annotator in annotator_list}
    full_annotator_set = set()
    rels = 0
    for annotation_id, rel in annotation_id_to_rel.items():
        annotator = rel["annotator"]
        if len(annotator_to_rel[annotator]) >= query_rels:
            full_annotator_set.add(annotator)
            if len(full_annotator_set) == len(annotator_list):
                break
            continue
        annotation = rel["annotation"]
        if annotator == "odds_ratio":
            annotation = f"OR: {annotation[0]}, CI: {annotation[1]}, p-value: {annotation[2]}"
        elif annotator == "rbert_cre":
            annotation = f"{annotation[0]}: {annotation[1]}"
        else:
            annotation = ", ".join(annotation)
        rel["annotation"] = annotation
        annotator_to_rel[annotator].append(rel)
        rels += 1
    del annotation_id_to_rel

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

        for rel in rel_list:
            head_type_set, head_id_set, head_name_set = set(), set(), set()
            tail_type_set, tail_id_set, tail_name_set = set(), set(), set()
            annotation = rel["annotation"]
            pmid = rel["pmid"]
            sentence = rel["sentence"]
            evidence_id = rel["evidence_id"]

            for _type, _id, name in rel["head_set"]:
                head_type_set.add(f"[{_type}]")
                head_id_set.add(_id)
                head_name_set.add(name)
            for _type, _id, name in rel["tail_set"]:
                tail_type_set.add(f"[{_type}]")
                tail_id_set.add(_id)
                tail_name_set.add(name)

            head_name = "\n".join(sorted(head_name_set)) + "\n"
            head_type = "\n".join(sorted(head_type_set)) + "\n"
            head_id = "\n".join(sorted(head_id_set))

            tail_name = "\n".join(sorted(tail_name_set)) + "\n"
            tail_type = "\n".join(sorted(tail_type_set)) + "\n"
            tail_id = "\n".join(sorted(tail_id_set))

            head_html = "<b>" + html.escape(head_name) + "</b>" + html.escape(head_type) + "<i>" + html.escape(head_id) + "</i>"
            tail_html = "<b>" + html.escape(tail_name) + "</b>" + html.escape(tail_type) + "<i>" + html.escape(tail_id) + "</i>"
            annotation_html = html.escape(annotation)
            pmid_html = f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">{pmid}</a>'

            if isinstance(sentence, str):
                section_type = "ABSTRACT"
                text_type = "paragraph"
            else:
                sentence, section_type, text_type = sentence
            sentence_html = html.escape(sentence)
            section_type_html = html.escape(f"{section_type} {text_type}")
            sentence_html = f"{section_type_html}<br /><i>{sentence_html}</i>"

            if show_eid:
                evidence_id_html = "<br />" + html.escape(" ".join([str(_id) for _id in evidence_id]))
            else:
                evidence_id_html = ""

            rel_table_html += \
                f"<tr>" \
                f"<td><pre>{head_html}</pre></td>" \
                f"<td><pre>{tail_html}</pre></td>" \
                f"<td>{annotator_html}{evidence_id_html}</td>" \
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

    # parser.add_argument("--kb_dir", default="pubmedKB-BERN/189_236_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-BERN/1_236_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC/256_319_disk")
    parser.add_argument("--kb_dir", default="pubmedKB-PTC/1_319_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC-FT/15823_19778_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC-FT/1_19778_disk")

    # parser.add_argument("--kb_type", default="memory", choices=["memory", "disk"])
    parser.add_argument("--kb_type", default="disk", choices=["memory", "disk"])

    parser.add_argument("--eid_list", default="")
    # parser.add_argument(  # pubmedKB-PTC, V600E, MESH:D009369, #rel=20
    #     "--eid_list",
    #     default="3424943591,3424943714,3424943843,3424943967,3424944089,3424944209,"
    #             "53579971,53580227,"
    #             "2473843891,2473844014,2473844143,2473844267,2473844389,2473844509,"
    #             "466766074,466766195,466766322,466766444,466766564,466766682"
    # )
    # parser.add_argument(  # pubmedKB-PTC-FT, V600E, MESH:D009369, #rel=20
    #     "--eid_list",
    #     default="72387678,72387804,72387924,72388052,72388171,72388288,"
    #             "6559686,6559808,6559924,6560048,6560163,6560276,"
    #             "78864632,78864756,78864874,78865000,78865117,78865232,"
    #             "363611221,363611348,363611469,363611598,363611718,363611836"
    # )

    parser.add_argument("--show_eid", default="false")
    # parser.add_argument("--show_eid", default="true")

    arg = parser.parse_args()

    global kb
    kb = KB(arg.kb_dir) if arg.kb_type == "memory" else DiskKB(arg.kb_dir)
    kb.load_nen()
    kb.load_data()
    kb.load_index()

    global eid_list
    if arg.eid_list:
        for eid in arg.eid_list.split(","):
            eid_list.append(int(eid))

    global show_eid
    show_eid = arg.show_eid == "true"

    app.run(host=arg.host, port=arg.port)
    return


if __name__ == "__main__":
    main()
    sys.exit()
