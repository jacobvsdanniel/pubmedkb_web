import csv
import sys
import html
import json
import logging
import argparse
import traceback

from flask import Flask, render_template, request

from kb_utils import query_variant, V2G, KB, Meta
from summary_utils import get_summary

app = Flask(__name__)
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(message)s",
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
v2g = V2G(None, None)
kb = KB(None)
kb_meta = Meta(None, None)
kb_type = None
show_eid, eid_list = False, []


@app.route("/")
def serve_home():
    return render_template("home.html")


@app.route("/nen")
def serve_nen():
    return render_template("nen.html")


@app.route("/var")
def serve_var():
    return render_template("var.html")


@app.route("/rel")
def serve_rel():
    return render_template("rel.html")


@app.route("/v2g")
def serve_v2g():
    return render_template("v2g.html")


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


@app.route("/query_nen")
def query_nen():
    response = {}

    # url argument
    query = request.args.get("query")
    case_sensitive = request.args.get("case_sensitive")
    max_length_diff = request.args.get("max_length_diff")
    min_similarity = request.args.get("min_similarity")
    max_names = request.args.get("max_names")
    max_aliases = request.args.get("max_aliases")

    response["url_argument"] = {
        "query": query,
        "case_sensitive": case_sensitive,
        "max_length_diff": max_length_diff,
        "min_similarity": min_similarity,
        "max_names": max_names,
        "max_aliases": max_aliases,
    }

    query = query.strip()
    case_sensitive = case_sensitive == "Y"
    max_length_diff = int(max_length_diff)
    min_similarity = float(min_similarity)
    max_names = int(max_names)
    max_aliases = int(max_aliases)

    logger.info(
        f"query={query}"
        f" case_sensitive={case_sensitive}"
        f" max_length_diff={max_length_diff}"
        f" min_similarity_ratio={min_similarity}"
        f" max_aliases={max_aliases}"
    )

    # name matches
    name_similarity_list = kb.nen.get_names_by_query(
        query,
        case_sensitive=case_sensitive,
        max_length_diff=max_length_diff,
        min_similarity=min_similarity,
        max_names=max_names,
    )
    names = len(name_similarity_list)
    logger.info(f"{names:,} names")
    response["match_list"] = []

    for name, similarity in name_similarity_list:
        match = {
            "name": name,
            "similarity": similarity,
            "type_id_alias_list": [],
        }
        logger.info(f"name: {name}, similarity: {similarity}")

        # id
        type_id_frequency_list = kb.nen.get_ids_by_name(name)
        ids = len(type_id_frequency_list)
        logger.info(f"ids: {ids}")

        for _type, _id, id_frequency in type_id_frequency_list:
            type_id_alias = {
                "type": _type,
                "id": _id,
                "type_id_name_frequency": id_frequency,
            }

            # alias
            alias_frequency_list = kb.nen.get_aliases_by_id(_type, _id, max_aliases=max_aliases)
            type_id_alias["alias_list"] = [
                {
                    "alias": alias,
                    "type_id_alias_frequency": alias_frequency,
                }
                for alias, alias_frequency in alias_frequency_list
            ]

            match["type_id_alias_list"].append(type_id_alias)
            logger.info(f"({_type}, {_id}, {name}, {id_frequency}): alias_list={alias_frequency_list}")

        response["match_list"].append(match)

    return json.dumps(response)


@app.route("/run_var", methods=["POST"])
def run_var():
    data = json.loads(request.data)
    query = data["query"].strip()
    logger.info(f"query={query}")

    extraction_list = query_variant(query)
    result = ""

    for extraction_id, (id_list, name_list, gene_list) in enumerate(extraction_list):
        logger.info(f"{id_list} {name_list} {gene_list}")

        caption_html = html.escape(f"Match #{extraction_id + 1}")
        result += f"<label style='font-size: 22px;'>{caption_html}</label><br /><br />"

        # attribute table
        result += html.escape("Normalization:")
        attribute_table_html = \
            f"<table><tr>" \
            f"<th>Attribute</th>" \
            f"<th>Values</th>" \
            f"</tr>"
        for key, value in [("ID", id_list), ("Name", name_list), ("Gene", gene_list)]:
            key_html = html.escape(f"{key}")
            value_html = [html.escape(v) for v in value]
            value_html = "&nbsp;&nbsp;&nbsp;&nbsp;".join(value_html)

            attribute_table_html += \
                f"<tr>" \
                f"<td>{key_html}</td>" \
                f"<td>{value_html}</td>" \
                f"</tr>"

        attribute_table_html += "</table>"
        result += attribute_table_html + "<br />"

        # tuple table
        result += html.escape("(Type, ID, Name) tuples with relations in current KB:")
        type_id_name_frequency_list = kb.nen.get_variant_in_kb(id_list, name_list)
        tuples = len(type_id_name_frequency_list)
        logger.info(f"tuples: {tuples}")
        tuple_table_html = \
            f"<table><tr>" \
            f"<th>Type</th>" \
            f"<th>ID</th>" \
            f"<th>Name</th>" \
            f"<th>Frequency in all texts</th>" \
            f"</tr>"

        for _type, _id, name, frequency in type_id_name_frequency_list:
            logger.info(f"-> ({_type} {_id} {name}): {frequency}")

            type_html = html.escape(_type)
            id_html = html.escape(_id)
            name_html = html.escape(name)
            frequency_html = html.escape(f"{frequency:,}")

            tuple_table_html += \
                f"<tr>" \
                f"<td>{type_html}</td>" \
                f"<td>{id_html}</td>" \
                f"<td>{name_html}</td>" \
                f"<td>{frequency_html}</td>" \
                f"</tr>"

        tuple_table_html += "</table>"
        result += tuple_table_html + "<br /><br /><br />"

    response = {"result": result}
    return json.dumps(response)


@app.route("/query_var")
def query_var():
    response = {}

    # url argument
    query = request.args.get("query")
    response["url_argument"] = {
        "query": query,
    }
    query = query.strip()
    logger.info(f"query={query}")

    # variant matches
    extraction_list = query_variant(query)
    response["match_list"] = []

    for extraction_id, (id_list, name_list, gene_list) in enumerate(extraction_list):
        logger.info(f"{id_list} {name_list} {gene_list}")
        match = {
            "attribute": {},
            "kb_entity_list": [],
        }

        # attribute
        for key, value in [("id_list", id_list), ("name_list", name_list), ("gene_list", gene_list)]:
            match["attribute"][key] = value

        # tuple_in_kb
        type_id_name_frequency_list = kb.nen.get_variant_in_kb(id_list, name_list)
        tuples = len(type_id_name_frequency_list)
        logger.info(f"tuples: {tuples}")
        for _type, _id, name, frequency in type_id_name_frequency_list:
            match["kb_entity_list"].append({
                "type": _type,
                "id": _id,
                "name": name,
                "frequency_in_text": frequency,
            })

        response["match_list"].append(match)

    return json.dumps(response)


@app.route("/run_v2g", methods=["POST"])
def run_v2g():
    data = json.loads(request.data)
    query = data["query"].strip()
    logger.info(f"query={query}")

    hgvs_to_frequency, rs_to_frequency, gene_to_frequency = v2g.query(query)
    result = ""

    table_html = \
        f"<table><tr>" \
        f"<th>Type</th>" \
        f"<th>Name (Frequency)</th>" \
        f"</tr>"
    for key, value in [("HGVS", hgvs_to_frequency), ("RS#", rs_to_frequency), ("Gene", gene_to_frequency)]:
        logger.info(f"[{key}] {value}")

        key_html = html.escape(f"{key}")
        value_html = [
            html.escape(f"{name}") + "&nbsp;" + html.escape(f"({frequency:,})")
            for name, frequency in value.items()
        ]
        value_html = " &nbsp;&nbsp;&nbsp;".join(value_html)

        table_html += \
            f"<tr>" \
            f"<td>{key_html}</td>" \
            f"<td>{value_html}</td>" \
            f"</tr>"

    table_html += "</table>"
    result += table_html + "<br />"
    response = {"result": result}
    return json.dumps(response)


@app.route("/query_v2g")
def query_v2g():
    response = {}

    # url argument
    query = request.args.get("query")
    response["url_argument"] = {
        "query": query,
    }
    query = query.strip()
    logger.info(f"query={query}")

    hgvs_to_frequency, rs_to_frequency, gene_to_frequency = v2g.query(query)

    for key, value in [("HGVS", hgvs_to_frequency), ("RS#", rs_to_frequency), ("Gene", gene_to_frequency)]:
        logger.info(f"[{key}] {value}")
        response[key] = [
            {"name": name, "frequency": frequency}
            for name, frequency in value.items()
        ]

    return json.dumps(response)


@app.route("/run_rel", methods=["POST"])
def run_rel():
    data = json.loads(request.data)

    # input: e1
    e1_filter = data["e1_filter"]
    e1_type, e1_id, e1_name = data["e1_type"], data["e1_id"].strip(), data["e1_name"].strip()
    if e1_filter == "type_id_name":
        e1 = (e1_type, e1_id, e1_name)
    elif e1_filter == "type_id":
        e1 = (e1_type, e1_id)
    elif e1_filter == "type_name":
        e1 = (e1_type, e1_name)
    else:
        assert False
    logger.info(f"[Entity A] key={e1_filter} value={e1}")

    # input: e2
    e2_filter = data["e2_filter"]
    e2_type, e2_id, e2_name = data["e2_type"], data["e2_id"].strip(), data["e2_name"].strip()
    if e2_filter == "type_id_name":
        e2 = (e2_type, e2_id, e2_name)
    elif e2_filter == "type_id":
        e2 = (e2_type, e2_id)
    elif e2_filter == "type_name":
        e2 = (e2_type, e2_name)
    else:
        assert False
    logger.info(f"[Entity B] key={e2_filter} value={e2}")

    # input: pmid
    query_pmid = data["query_pmid"].strip()
    logger.info(f"[PMID] value={query_pmid}")

    # input: query
    query_filter = data["query_filter"]
    query_start = int(data["query_start"])
    query_end = int(data["query_end"])
    query_max_rels = query_end - query_start
    logger.info(
        f"[Query] filter={query_filter}; rel_range=[{query_start:,} - {query_end:,}); max_rels={query_max_rels:,}"
    )

    # query rel ids
    if eid_list:
        rel_id_list = eid_list
    elif query_filter == "P":
        rel_id_list = kb.get_evidence_ids_by_pmid(query_pmid)
    elif query_filter == "A":
        rel_id_list = kb.get_evidence_ids_by_entity(e1, key=e1_filter)
    elif query_filter == "B":
        rel_id_list = kb.get_evidence_ids_by_entity(e2, key=e2_filter)
    elif query_filter == "AB":
        rel_id_list = kb.get_evidence_ids_by_pair((e1, e2), key=(e1_filter, e2_filter))
    elif query_filter == "ABP":
        ab_list = kb.get_evidence_ids_by_pair((e1, e2), key=(e1_filter, e2_filter))
        p_list = kb.get_evidence_ids_by_pmid(query_pmid)
        rel_id_list = sorted(set(ab_list) & set(p_list))
        del ab_list, p_list
    else:
        assert False
    rel_ids = len(rel_id_list)
    logger.info(f"Total matching #rel in KB = {rel_ids:,}")
    rel_id_list = rel_id_list[query_start:query_end]

    # collect rel by annotator and group evidence by annotation
    if kb_type == "relation":
        annotator_list = ["odds_ratio", "rbert_cre", "spacy_ore", "openie_ore"]
    else:
        annotator_list = ["co_occurrence"]

    annotation_id_to_rel = {}
    annotator_to_rel = {annotator: [] for annotator in annotator_list}

    for rel_id in rel_id_list:
        head, tail, annotation_id, _pmid, _sentence_id = kb.get_evidence_by_id(
            rel_id, return_annotation=False, return_sentence=False,
        )
        if annotation_id not in annotation_id_to_rel:
            head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
                rel_id, return_annotation=True, return_sentence=True,
            )

            if annotator == "odds_ratio":
                annotation = f"OR: {annotation[0]}, CI: {annotation[1]}, p-value: {annotation[2]}"
            elif annotator == "rbert_cre":
                annotation = f"{annotation[0]}: {annotation[1]}"
            elif annotator in ["spacy_ore", "openie_ore"]:
                annotation = ", ".join(annotation)

            rel = {
                "head_set": {tuple(head)}, "tail_set": {tuple(tail)},
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence,
                "evidence_id": [rel_id],
            }
            annotation_id_to_rel[annotation_id] = rel
            annotator_to_rel[annotator].append(rel)
        else:
            annotation_id_to_rel[annotation_id]["head_set"].add(tuple(head))
            annotation_id_to_rel[annotation_id]["tail_set"].add(tuple(tail))
            annotation_id_to_rel[annotation_id]["evidence_id"].append(rel_id)

    del rel_id_list
    del annotation_id_to_rel

    result = ""

    # create summary html
    if kb_type == "relation":
        summary_evidence_id_list = [
            _id
            for _annotator, rel_list in annotator_to_rel.items()
            for rel in rel_list
            for _id in rel["evidence_id"]
        ]

        if eid_list:
            summary_query = "X"
            summary_target = None
        elif query_filter == "P":
            summary_query = "P"
            summary_target = query_pmid
        elif query_filter == "A":
            summary_query = "A"
            summary_target = (e1_filter, (e1_type, e1_id, e1_name))
        elif query_filter == "B":
            summary_query = "A"
            summary_target = (e2_filter, (e2_type, e2_id, e2_name))
        elif query_filter == "AB":
            summary_query = "AB"
            summary_target = (e1_filter, (e1_type, e1_id, e1_name), e2_filter, (e2_type, e2_id, e2_name))
        elif query_filter == "ABP":
            summary_query = "ABP"
            summary_target = (e1_filter, (e1_type, e1_id, e1_name), e2_filter, (e2_type, e2_id, e2_name), query_pmid)
        else:
            assert False

        try:
            summary_text, summary_html = get_summary(kb, summary_evidence_id_list, summary_target, summary_query)
            assert isinstance(summary_text, str)
            assert summary_text
            assert isinstance(summary_html, str)
            assert summary_html
        except Exception:
            traceback.print_exc()
            summary_text = "No summary (exception caught)."
            summary_html = html.escape(summary_text)

        result += \
            "<div style='font-size: 15px; color: #131523; line-height: 200%'>" \
            "<span style='font-size: 17px'> " \
            "Summary" \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold'> " \
            "&mdash; target query" \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold; color: #f99600'>" \
            "&mdash; selected related mentions" \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold; color: #21d59b; background-color: #62e0b84d'>" \
            " &mdash; odds_ratio " \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold; color: #0058ff; background-color: #5f96ff4d'>" \
            " &mdash; rbert_cre " \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold; color: #ff8389; background-color: #ff83894d'>" \
            " &mdash; spacy_ore / openie_ore " \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br />" \
            + summary_html \
            + "</div><br /><br />"

    # create table html
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
        f'<th style="width:20%">Annotation</th>' \
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

            head_html = "<b>" + html.escape(head_name) + "</b>" + html.escape(head_type) + "<i>" + html.escape(
                head_id) + "</i>"
            tail_html = "<b>" + html.escape(tail_name) + "</b>" + html.escape(tail_type) + "<i>" + html.escape(
                tail_id) + "</i>"
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


@app.route("/query_rel")
def query_rel():
    response = {}

    # url argument
    e1_filter = request.args.get("e1_filter")
    e1_type = request.args.get("e1_type")
    e1_id = request.args.get("e1_id")
    e1_name = request.args.get("e1_name")
    e2_filter = request.args.get("e2_filter")
    e2_type = request.args.get("e2_type")
    e2_id = request.args.get("e2_id")
    e2_name = request.args.get("e2_name")
    query_pmid = request.args.get("query_pmid")
    query_filter = request.args.get("query_filter")
    query_start = request.args.get("query_start")
    query_end = request.args.get("query_end")

    arg_list = [
        ("e1_filter", e1_filter),
        ("e1_type", e1_type),
        ("e1_id", e1_id),
        ("e1_name", e1_name),
        ("e2_filter", e2_filter),
        ("e2_type", e2_type),
        ("e2_id", e2_id),
        ("e2_name", e2_name),
        ("query_pmid", query_pmid),
        ("query_filter", query_filter),
        ("query_start", query_start),
        ("query_end", query_end),
    ]
    response["url_argument"] = {
        arg_name: arg_value
        for arg_name, arg_value in arg_list
        if arg_value is not None
    }

    # input: e1
    if e1_id:
        e1_id = e1_id.strip()
    if e1_name:
        e1_name = e1_name.strip()

    if e1_filter == "type_id_name":
        e1 = (e1_type, e1_id, e1_name)
    elif e1_filter == "type_id":
        e1 = (e1_type, e1_id)
    elif e1_filter == "type_name":
        e1 = (e1_type, e1_name)
    else:
        e1 = None
    logger.info(f"[Entity A] key={e1_filter} value={e1}")

    # input: e2
    if e2_id:
        e2_id = e2_id.strip()
    if e2_name:
        e2_name = e2_name.strip()

    if e2_filter == "type_id_name":
        e2 = (e2_type, e2_id, e2_name)
    elif e2_filter == "type_id":
        e2 = (e2_type, e2_id)
    elif e2_filter == "type_name":
        e2 = (e2_type, e2_name)
    else:
        e2 = None
    logger.info(f"[Entity B] key={e2_filter} value={e2}")

    # input: pmid
    if query_pmid:
        query_pmid = query_pmid.strip()
    logger.info(f"[PMID] value={query_pmid}")

    # input: query
    query_start = int(query_start)
    query_end = int(query_end)
    query_max_rels = query_end - query_start
    logger.info(
        f"[Query] filter={query_filter}; rel_range=[{query_start:,} - {query_end:,}); max_rels={query_max_rels:,}"
    )

    # query rel ids
    if eid_list:
        rel_id_list = eid_list
    elif query_filter == "P":
        rel_id_list = kb.get_evidence_ids_by_pmid(query_pmid)
    elif query_filter == "A":
        rel_id_list = kb.get_evidence_ids_by_entity(e1, key=e1_filter)
    elif query_filter == "B":
        rel_id_list = kb.get_evidence_ids_by_entity(e2, key=e2_filter)
    elif query_filter == "AB":
        rel_id_list = kb.get_evidence_ids_by_pair((e1, e2), key=(e1_filter, e2_filter))
    elif query_filter == "ABP":
        ab_list = kb.get_evidence_ids_by_pair((e1, e2), key=(e1_filter, e2_filter))
        p_list = kb.get_evidence_ids_by_pmid(query_pmid)
        rel_id_list = sorted(set(ab_list) & set(p_list))
        del ab_list, p_list
    else:
        assert False
    rel_ids = len(rel_id_list)
    logger.info(f"Total matching #rel in KB = {rel_ids:,}")
    rel_id_list = rel_id_list[query_start:query_end]

    # collect rel by annotator and group evidence by annotation
    if kb_type == "relation":
        annotator_list = ["odds_ratio", "rbert_cre", "spacy_ore", "openie_ore"]
    else:
        annotator_list = ["co_occurrence"]

    annotation_id_to_rel = {}
    annotator_to_rel = {annotator: [] for annotator in annotator_list}

    for rel_id in rel_id_list:
        head, tail, annotation_id, _pmid, _sentence_id = kb.get_evidence_by_id(
            rel_id, return_annotation=False, return_sentence=False,
        )
        if annotation_id not in annotation_id_to_rel:
            head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
                rel_id, return_annotation=True, return_sentence=True,
            )

            if annotator == "odds_ratio":
                annotation = f"OR: {annotation[0]}, CI: {annotation[1]}, p-value: {annotation[2]}"
            elif annotator == "rbert_cre":
                annotation = f"{annotation[0]}: {annotation[1]}"
            elif annotator in ["spacy_ore", "openie_ore"]:
                annotation = ", ".join(annotation)

            rel = {
                "head_set": {tuple(head)}, "tail_set": {tuple(tail)},
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence,
                "evidence_id": [rel_id],
            }
            annotation_id_to_rel[annotation_id] = rel
            annotator_to_rel[annotator].append(rel)
        else:
            annotation_id_to_rel[annotation_id]["head_set"].add(tuple(head))
            annotation_id_to_rel[annotation_id]["tail_set"].add(tuple(tail))
            annotation_id_to_rel[annotation_id]["evidence_id"].append(rel_id)

    del rel_id_list
    del annotation_id_to_rel

    # create summary
    if kb_type == "relation":
        summary_evidence_id_list = [
            _id
            for _annotator, rel_list in annotator_to_rel.items()
            for rel in rel_list
            for _id in rel["evidence_id"]
        ]

        if eid_list:
            summary_query = "X"
            summary_target = None
        elif query_filter == "P":
            summary_query = "P"
            summary_target = query_pmid
        elif query_filter == "A":
            summary_query = "A"
            summary_target = (e1_filter, (e1_type, e1_id, e1_name))
        elif query_filter == "B":
            summary_query = "A"
            summary_target = (e2_filter, (e2_type, e2_id, e2_name))
        elif query_filter == "AB":
            summary_query = "AB"
            summary_target = (e1_filter, (e1_type, e1_id, e1_name), e2_filter, (e2_type, e2_id, e2_name))
        elif query_filter == "ABP":
            summary_query = "ABP"
            summary_target = (e1_filter, (e1_type, e1_id, e1_name), e2_filter, (e2_type, e2_id, e2_name), query_pmid)
        else:
            assert False

        try:
            summary_text, summary_html = get_summary(kb, summary_evidence_id_list, summary_target, summary_query)
            assert isinstance(summary_text, str)
            assert summary_text
            assert isinstance(summary_html, str)
            assert summary_html
        except Exception:
            traceback.print_exc()
            summary_text = "No summary (exception caught)."
            summary_html = html.escape(summary_text)

        summary_html = \
            "<div style='font-size: 15px; color: #131523; line-height: 200%'>" \
            "<span style='font-size: 17px'> " \
            "Summary" \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold'> " \
            "&mdash; target query" \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold; color: #f99600'>" \
            "&mdash; selected related mentions" \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold; color: #21d59b; background-color: #62e0b84d'>" \
            " &mdash; odds_ratio " \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold; color: #0058ff; background-color: #5f96ff4d'>" \
            " &mdash; rbert_cre " \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            "<span style='font-size: 13px; font-weight:bold; color: #ff8389; background-color: #ff83894d'>" \
            " &mdash; spacy_ore / openie_ore " \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br />" \
            + summary_html \
            + "</div><br /><br />"

    else:
        summary_text = f"No summary for kb_type={kb_type}"
        summary_html = html.escape(summary_text)

    response["summary"] = {
        "text": summary_text,
        "html": summary_html,
    }

    # create relation table
    response["relation"] = {}
    pmid_set = set()

    for annotator in annotator_list:
        response["relation"][annotator] = []
        rel_list = annotator_to_rel[annotator]

        for rel in rel_list:
            head_type_set, head_id_set, head_name_set = set(), set(), set()
            tail_type_set, tail_id_set, tail_name_set = set(), set(), set()
            annotation = rel["annotation"]
            pmid = rel["pmid"]
            sentence = rel["sentence"]
            pmid_set.add(int(pmid))

            for _type, _id, name in rel["head_set"]:
                head_type_set.add(_type)
                head_id_set.add(_id)
                head_name_set.add(name)
            for _type, _id, name in rel["tail_set"]:
                tail_type_set.add(_type)
                tail_id_set.add(_id)
                tail_name_set.add(name)

            head_type_list = sorted(head_type_set)
            head_id_list = sorted(head_id_set)
            head_name_list = sorted(head_name_set)

            tail_type_list = sorted(tail_type_set)
            tail_id_list = sorted(tail_id_set)
            tail_name_list = sorted(tail_name_set)

            if isinstance(sentence, str):
                section_type = "ABSTRACT"
                text_type = "paragraph"
            else:
                sentence, section_type, text_type = sentence

            response["relation"][annotator].append({
                "head": {
                    "type_list": head_type_list,
                    "id_list": head_id_list,
                    "name_list": head_name_list,
                },
                "tail": {
                    "type_list": tail_type_list,
                    "id_list": tail_id_list,
                    "name_list": tail_name_list,
                },
                "annotation": annotation,
                "source": {
                    "pmid": pmid,
                    "section": section_type,
                    "text": sentence,
                    "text_parent": text_type,
                }
            })

    # create paper meta
    pmid_set = [str(pmid) for pmid in sorted(pmid_set)]
    response["paper_meta"] = {
        pmid: kb_meta.get_meta_by_pmid(pmid)
        for pmid in pmid_set
    }

    return json.dumps(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="12345")

    parser.add_argument("--variant_dir", default="data/variant")
    parser.add_argument("--gene_dir", default="data/gene")

    # parser.add_argument("--kb_dir", default="pubmedKB-BERN/189_236_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-BERN/1_236_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC/256_319_disk")
    parser.add_argument("--kb_dir", default="pubmedKB-PTC/1_319_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC-FT/15823_19778_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC-FT/1_19778_disk")

    parser.add_argument("--paper_meta_file", default="meta.json")
    parser.add_argument("--journal_impact_file", default="journal_impact.csv")

    parser.add_argument("--kb_type", default="relation", choices=["relation", "cooccur"])

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
    for key, value in vars(arg).items():
        if value is not None:
            logger.info(f"[{key}] {value}")

    global v2g
    v2g = V2G(arg.variant_dir, arg.gene_dir)

    global kb
    kb = KB(arg.kb_dir)
    kb.load_nen()
    kb.load_data()
    kb.load_index()

    global kb_type
    kb_type = arg.kb_type

    global kb_meta
    kb_meta = Meta(arg.paper_meta_file, arg.journal_impact_file)

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
