import csv
import sys
import copy
import html
import json
import logging
import argparse
import traceback
from collections import defaultdict

from flask import Flask, render_template, request

from kb_utils import query_variant, V2G, KB, Meta, PaperNEN, ner_gvdc_mapping
from summary_utils import Summary

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
kb_meta = Meta(None)
paper_nen = PaperNEN(None)
kb_type = None
show_aid = False


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


@app.route("/paper")
def serve_paper():
    return render_template("paper.html")


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


class Paper:
    def __init__(self, pmid, aid_score_list):
        self.pmid = pmid
        self.meta = {}

        self.aid_score_list = aid_score_list

        self.sentence_list = []
        self.annotator_to_relation = {}

        self.relevance = 0
        return

    def get_relevance(self):
        self.relevance = sum(score for _aid, score in self.aid_score_list)
        return

    def get_meta(self):
        self.meta = kb_meta.get_meta_by_pmid(self.pmid)
        return

    def get_sentence_and_relation(self):
        if kb_type == "relation":
            annotator_list = ["rbert_cre", "odds_ratio", "spacy_ore", "openie_ore"]
        else:
            annotator_list = ["co_occurrence"]

        annotator_to_relation = {annotator: [] for annotator in annotator_list}
        sid_to_index = dict()
        sentence_list = []

        for aid, _ann_score in self.aid_score_list:
            sid, h_list, t_list, annotator, annotation = kb.get_annotation(aid)

            # sentence and mention
            if sid not in sid_to_index:
                sid_to_index[sid] = len(sentence_list)

                sentence, mention_list = kb.get_sentence(sid)
                mention_list = [
                    {
                        "name": name,
                        "type": _type,
                        "id": id_list,
                        "offset": pos,
                    }
                    for name, _type, id_list, pos in mention_list
                ]

                sentence_list.append({
                    "sentence": sentence,
                    "mention": mention_list,
                })

            sentence_index = sid_to_index[sid]

            # relation
            if annotator == "rbert_cre":
                annotation = {
                    "relation": annotation[0],
                    "score": annotation[1],
                }
            elif annotator == "odds_ratio":
                annotation = {
                    "OR": annotation[0],
                    "CI": annotation[1],
                    "p-value": annotation[2],
                }
            elif annotator in ["spacy_ore", "openie_ore"]:
                annotation = {
                    "subject": annotation[0],
                    "predicate": annotation[1],
                    "object": annotation[2],
                }
            elif annotator == "co_occurrence":
                pass

            relation = {
                "head_mention": h_list,
                "tail_mention": t_list,
                "annotation": annotation,
                "sentence_index": sentence_index,
                "annotation_id": aid,
            }
            annotator_to_relation[annotator].append(relation)

        # sort cre relation by score
        if "rbert_cre" in annotator_to_relation:
            relation_list = annotator_to_relation["rbert_cre"]
            score_list = [
                float(relation_list[i]["annotation"]["score"][:-1])
                for i in range(len(relation_list))
            ]
            index_list = sorted(
                range(len(relation_list)),
                key=lambda i: score_list[i],
                reverse=True,
            )
            annotator_to_relation["rbert_cre"] = [relation_list[i] for i in index_list]

        self.sentence_list = sentence_list
        self.annotator_to_relation = annotator_to_relation
        return


class Rel:
    def __init__(self, raw_arg):
        str_arg = {}
        for arg_name, arg_value in raw_arg.items():
            if arg_value is None:
                continue
            arg_value = arg_value.strip()
            if arg_value == "":
                continue
            str_arg[arg_name] = arg_value

        self.raw_arg = raw_arg
        self.str_arg = str_arg
        self.arg = copy.deepcopy(str_arg)

        self.paper_list = []
        self.statistics = {}

        self.text_summary = {}
        self.html_summary = ""
        return

    def run_pipeline(self):
        self.get_argument()
        self.get_paper_annotation_id()
        self.sort_papers_and_paginate()
        self.get_paper_relation()
        self.get_paper_meta()
        self.get_statistics()
        self.get_summary()
        return

    def run_no_pagination_get_statistics_pipeline(self):
        self.get_argument()
        self.get_paper_annotation_id()
        return

    def get_argument(self):
        arg = self.arg

        logger.info("[Query]")

        # entity
        for spec in ["e1_spec", "e2_spec"]:
            if spec in arg:
                arg[spec] = json.loads(arg[spec])
            else:
                arg[spec] = None
            logger.info(f"{spec}: {arg[spec]}")

        # pmid
        if "pmid" not in arg:
            arg["pmid"] = None
        logger.info(f"pmid: {arg['pmid']}")

        # pagination
        try:
            arg["paper_start"] = int(arg["paper_start"])
        except (KeyError, ValueError):
            arg["paper_start"] = None  # slice from the first item
        try:
            arg["paper_end"] = int(arg["paper_end"])
        except (KeyError, ValueError):
            arg["paper_end"] = None  # slice to the last item
        logger.info(f"pagination: request papers in [{arg['paper_start']}, {arg['paper_end']})")
        return

    def get_paper_annotation_id(self):
        arg = self.arg

        # query paper and annotation id, score from kb
        pmid_to_ann = kb.query_pmid_to_annotation_list(arg["e1_spec"], arg["e2_spec"], arg["pmid"])
        papers = len(pmid_to_ann)
        relations = sum(len(ann_list) for _pmid, ann_list in pmid_to_ann.items())
        self.statistics["papers_before_pagination"] = papers
        self.statistics["relations_before_pagination"] = relations
        logger.info(f"Before pagination: {papers:,} papers; {relations:,} relations")

        self.paper_list = [
            Paper(pmid, aid_score_list)
            for pmid, aid_score_list in pmid_to_ann.items()
        ]
        return

    def sort_papers_and_paginate(self):
        arg = self.arg
        paper_list = self.paper_list

        if "paper_sort" in arg:
            key_list = [(0, 0) for _ in paper_list]

            if arg["paper_sort"] == "relevance":
                for pi, paper in enumerate(paper_list):
                    paper.get_relevance()
                    key_list[pi] = (paper.relevance, int(paper.pmid))

            elif arg["paper_sort"] == "citation":
                for pi, paper in enumerate(paper_list):
                    paper.get_meta()
                    try:
                        citation = int(paper.meta["citation"])
                    except ValueError:
                        citation = 0
                    key_list[pi] = (citation, int(paper.pmid))

            elif arg["paper_sort"] == "year":
                for pi, paper in enumerate(paper_list):
                    paper.get_meta()
                    try:
                        year = int(paper.meta["year"])
                    except ValueError:
                        year = 0
                    key_list[pi] = (year, int(paper.pmid))

            elif arg["paper_sort"] == "journal_impact":
                for pi, paper in enumerate(paper_list):
                    paper.get_meta()
                    try:
                        journal_impact = float(paper.meta["journal_impact"])
                    except ValueError:
                        journal_impact = 0
                    key_list[pi] = (journal_impact, int(paper.pmid))

            else:
                assert False

            pi_list = sorted(range(len(paper_list)), key=lambda _pi: key_list[_pi], reverse=True)
            pi_list = pi_list[arg["paper_start"]:arg["paper_end"]]
            paper_list = [paper_list[pi] for pi in pi_list]

        else:
            paper_list = paper_list[arg["paper_start"]:arg["paper_end"]]

        self.paper_list = paper_list
        return

    def get_paper_relation(self):
        for paper in self.paper_list:
            paper.get_sentence_and_relation()
        return

    def get_paper_meta(self):
        for paper in self.paper_list:
            if not paper.meta:
                paper.get_meta()
        return

    def get_statistics(self):
        papers = len(self.paper_list)
        sentences = 0
        relations = 0
        annotator_to_relations = defaultdict(lambda: 0)

        for paper in self.paper_list:
            sentences += len(paper.sentence_list)
            relations += len(paper.aid_score_list)
            for annotator, relation_list in paper.annotator_to_relation.items():
                annotator_to_relations[annotator] += len(relation_list)

        self.statistics["papers"] = papers
        self.statistics["sentences"] = sentences
        self.statistics["relations"] = relations

        log = "[statistics] "
        for item, number in self.statistics.items():
            log += f" {number:,} {item};"
        logger.info(log[:-1])

        self.statistics["annotator_to_relations"] = annotator_to_relations

        log = "[statistics] relations: "
        for annotator, relations in annotator_to_relations.items():
            log += f" {relations:,} {annotator};"
        logger.info(log[:-1])
        return

    def get_summary(self):
        arg = self.arg

        if kb_type == "relation" and self.paper_list:
            try:
                summary = Summary(self.paper_list, arg["e1_spec"], arg["e2_spec"], arg["pmid"])
                summary.run_pipeline()
                text_summary = summary.text_summary
                html_summary = summary.html_summary
                logger.info("[summary] created")
            except Exception:
                traceback.print_exc()
                text_summary = {
                    "text": "No summary.",
                    "term_to_span": {},
                }
                html_summary = html.escape(text_summary["text"])

        else:
            text_summary = {
                "text": "No summary.",
                "term_to_span": {},
            }
            html_summary = html.escape(text_summary["text"])

        html_summary = \
            "<div style='font-size: 15px; color: #131523; line-height: 200%'>" \
            "<span style='font-size: 17px'> " \
            "Summary" \
            "</span>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" \
            + html_summary \
            + "</div>"

        self.text_summary = text_summary
        self.html_summary = html_summary
        return


@app.route("/run_rel", methods=["POST"])
def run_rel():
    raw_arg = json.loads(request.data)

    rel = Rel(raw_arg)
    rel.run_pipeline()

    # statistics table
    statistics_table_html = "<table>"

    statistics_table_html += "<tr>"
    for key, value in rel.statistics.items():
        if key != "annotator_to_relations":
            statistics_table_html += f"<th>{key}</th>"
        else:
            for annotator, _relations in value.items():
                statistics_table_html += f"<th>{annotator}</th>"
    statistics_table_html += "</tr>"

    statistics_table_html += "<tr>"
    for key, value in rel.statistics.items():
        if key != "annotator_to_relations":
            statistics_table_html += f"<td>{value:,}</td>"
        else:
            for _annotator, relations in value.items():
                statistics_table_html += f"<td>{relations:,}</td>"
    statistics_table_html += "</tr><table>"

    # relation table
    relation_table_html = \
        f"<table><tr>" \
        f'<th style="width:20%">Head</th>' \
        f'<th style="width:20%">Tail</th>' \
        f'<th style="width:5%">Annotator</th>' \
        f'<th style="width:20%">Annotation</th>' \
        f'<th style="width:5%">PMID</th>' \
        f'<th style="width:30%">Sentence</th>' \
        f"</tr>"

    for paper in rel.paper_list:
        pmid = paper.pmid
        sentence_list = paper.sentence_list
        annotator_to_relation = paper.annotator_to_relation

        for annotator, relation_list in annotator_to_relation.items():
            annotator_html = html.escape(annotator)

            for relation in relation_list:
                h_list = relation["head_mention"]
                t_list = relation["tail_mention"]
                annotation = relation["annotation"]
                sentence_index = relation["sentence_index"]
                aid = relation["annotation_id"]

                sentence_data = sentence_list[sentence_index]
                sentence = sentence_data["sentence"]
                mention_list = sentence_data["mention"]

                head_type, head_id, head_name = set(), set(), set()
                tail_type, tail_id, tail_name = set(), set(), set()

                for mi in h_list:
                    mention = mention_list[mi]
                    head_type.add(mention["type"])
                    head_name.add(mention["name"])
                    for _id in mention["id"]:
                        head_id.add(_id)
                for mi in t_list:
                    mention = mention_list[mi]
                    tail_type.add(mention["type"])
                    tail_name.add(mention["name"])
                    for _id in mention["id"]:
                        tail_id.add(_id)

                head_type, head_id, head_name = sorted(head_type), sorted(head_id), sorted(head_name)
                tail_type, tail_id, tail_name = sorted(tail_type), sorted(tail_id), sorted(tail_name)

                head_type = "\n".join(head_type) + "\n"
                head_id = "\n".join(head_id)
                head_name = "\n".join(head_name) + "\n"
                tail_type = "\n".join(tail_type) + "\n"
                tail_id = "\n".join(tail_id)
                tail_name = "\n".join(tail_name) + "\n"

                head_type = html.escape(head_type)
                head_id = html.escape(head_id)
                head_name = html.escape(head_name)
                tail_type = html.escape(tail_type)
                tail_id = html.escape(tail_id)
                tail_name = html.escape(tail_name)

                head_html = f"<b>{head_name}</b>{head_type}<i>{head_id}</i>"
                tail_html = f"<b>{tail_name}</b>{tail_type}<i>{tail_id}</i>"
                pmid_html = f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">{pmid}</a>'

                if annotator == "rbert_cre":
                    annotation = f"{annotation['relation']}: {annotation['score']}"
                elif annotator == "odds_ratio":
                    annotation = f"OR: {annotation['OR']}, CI: {annotation['CI']}, p-value: {annotation['p-value']}"
                elif annotator in ["spacy_ore", "openie_ore"]:
                    annotation = f"{annotation['subject']}, {annotation['predicate']}, {annotation['object']}"
                elif annotator == "co_occurrence":
                    annotation = str(annotation)
                annotation_html = html.escape(annotation)

                if isinstance(sentence, str):
                    section_type = "ABSTRACT"
                    text_type = "paragraph"
                else:
                    sentence, section_type, text_type = sentence
                sentence_html = html.escape(sentence)
                section_type_html = html.escape(f"{section_type} {text_type}")
                sentence_html = f"{section_type_html}<br /><i>{sentence_html}</i>"

                if show_aid:
                    annotation_id_html = "<br />" + html.escape(str(aid))
                else:
                    annotation_id_html = ""

                relation_table_html += \
                    f"<tr>" \
                    f"<td><pre>{head_html}</pre></td>" \
                    f"<td><pre>{tail_html}</pre></td>" \
                    f"<td>{annotator_html}{annotation_id_html}</td>" \
                    f"<td>{annotation_html}</td>" \
                    f"<td>{pmid_html}</td>" \
                    f"<td>{sentence_html}</td>" \
                    f"</tr>"

    relation_table_html += "</table>"

    # combined html
    result = \
        rel.html_summary \
        + "<br /><br />" \
        + statistics_table_html \
        + "<br /><br />" \
        + relation_table_html \
        + "<br /><br /><br /><br /><br /><br /><br /><br /><br /><br />"

    response = {
        "result": result,
    }
    return json.dumps(response)


@app.route("/query_rel")
def query_rel():
    raw_arg = request.args

    rel = Rel(raw_arg)
    rel.run_pipeline()

    response = {
        "url_argument": rel.str_arg,
        "result_statistics": rel.statistics,
        "paper_list": [
            {
                "pmid": paper.pmid,
                "meta": paper.meta,
                "sentence_list": paper.sentence_list,
                "annotator_to_relation": paper.annotator_to_relation,
            }
            for paper in rel.paper_list
        ],
        "summary": {
            "text_summary": rel.text_summary,
            "html_summary": rel.html_summary,
        },
    }
    return json.dumps(response)


@app.route("/query_rel_statistics")
def query_rel_statistics():
    raw_arg = request.args

    rel = Rel(raw_arg)
    rel.run_no_pagination_get_statistics_pipeline()

    response = {
        "url_argument": rel.str_arg,
        "result_statistics": rel.statistics,
    }
    return json.dumps(response)


@app.route("/run_paper", methods=["POST"])
def run_paper():
    arg = json.loads(request.data)
    query = arg.get("query", "")

    meta = kb_meta.get_meta_by_pmid(query)
    paper = paper_nen.query_data(query)

    # pmid
    pmid = paper["pmid"]
    pmid_html = '<div style="font-size: 20px; line-height: 200%;">' \
                f'PMID: <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">{pmid}</a>' \
                '</div>'

    # meta
    meta_html = [
        f"Title: {meta['title']}",
        f"Author: {meta['author']}",
        f"Year: {meta['year']}",
        f"Journal: {meta['journal']}",
        f"PubMed Citation: {meta['citation']}",
    ]
    meta_html = "<br />".join(
        html.escape(term)
        for term in meta_html
    )
    meta_html = f'<div style="font-size: 20px; line-height: 200%;">{meta_html}</div>'

    # ner
    sentence_html_list = []
    span_class_to_style = {
        "gene": "font-weight: bold; color: #21d59b;",
        "mutation": "font-weight: bold; color: #0058ff;",
        "disease": "font-weight: bold; color: #ff8389;",
        "drug": "font-weight: bold;",
    }

    for sentence_datum in paper["sentence_list"]:
        sentence = sentence_datum["sentence"]
        mention_list = sentence_datum["mention"]
        sentence_html = ""
        last_j = 0

        for mention in mention_list:
            name = mention["name"]
            _type = mention["type"]
            i = mention["offset"]
            j = i + len(name)

            span_style = span_class_to_style[ner_gvdc_mapping[_type]]
            span_html = f"<span style='{span_style}'>{html.escape(name)}</span>"
            sentence_html += html.escape(sentence[last_j:i]) + span_html
            last_j = j

        sentence_html += html.escape(sentence[last_j:])
        sentence_html_list.append(sentence_html)

    ner_html = " ".join(sentence_html_list)
    ner_html = f'<div style="font-size: 18px; line-height: 200%;">{ner_html}</div>'

    # nen
    nen_html = []

    for si, sentence_datum in enumerate(paper["sentence_list"]):
        mention_list = sentence_datum["mention"]
        if not mention_list:
            continue

        sentence_html = f'<div style="font-size: 18px; line-height: 200%;">{sentence_html_list[si]}</div>'
        sentence_html += \
            "<table><tr>" \
            + "<th>Name</th>" \
            + "<th>Type</th>" \
            + "<th>ID</th>" \
            + "<th>Offset</th>" \
            + "</tr>"

        for mention in mention_list:
            name = mention["name"]
            _type = mention["type"]
            id_list = mention["id"]
            offset = mention["offset"]

            name = html.escape(name)
            _type = html.escape(_type)
            _id = html.escape(", ".join(id_list))

            sentence_html += \
                f"<tr><td>{name}</td>" \
                + f"<td>{_type}</td>" \
                + f"<td>{_id}</td>" \
                + f"<td>{offset}</td></tr>"

        sentence_html += "</table>"
        nen_html.append(sentence_html)

    nen_html = "<br /><br />".join(nen_html)

    # combined result
    result = pmid_html \
             + meta_html \
             + "<br /><br /><br />" \
             + ner_html \
             + "<br /><br /><br />" \
             + nen_html \
             + "<br /><br /><br /><br /><br />"

    response = {
        "result": result,
    }
    return json.dumps(response)


@app.route("/query_paper")
def query_paper():
    arg = request.args
    query = arg.get("query", "")

    paper = paper_nen.query_data(query)
    meta = kb_meta.get_meta_by_pmid(query)

    response = {
        "url_argument": arg,
        "meta": meta,
        "paper": paper,
    }
    return json.dumps(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="12345")

    parser.add_argument("--variant_dir", default="data/variant")
    parser.add_argument("--gene_dir", default="data/gene")
    parser.add_argument("--meta_dir", default="data/meta")
    parser.add_argument("--paper_dir", default="data/paper")

    parser.add_argument("--kb_type", default="relation", choices=["relation", "cooccur"])
    parser.add_argument("--kb_dir", default="pubmedKB-PTC/1_319_disk")
    parser.add_argument("--show_aid", default="false")

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
    kb_meta = Meta(arg.meta_dir)

    global paper_nen
    paper_nen = PaperNEN(arg.paper_dir)

    global show_aid
    show_aid = arg.show_aid == "true"

    app.run(host=arg.host, port=arg.port)
    return


if __name__ == "__main__":
    main()
    sys.exit()
