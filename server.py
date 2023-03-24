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
kb_meta = Meta(None)
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


class Paper:
    def __init__(self, pmid):
        self.pmid = pmid
        self.meta = {}

        self.evidence_list = []
        self.kb_items = 0

        self.annotator_to_relation = {}
        self.relations = 0

        self.sentence_list = []
        self.sentences = 0

        self.relevance = 0
        return

    def get_meta(self):
        self.meta = kb_meta.get_meta_by_pmid(self.pmid)
        return

    def get_sentence_and_relation(self, clean_up_evidence=True):
        """
        collect sentences; collect and group relation by annotator

        a relation is a merger of the kb evidence items of the same annotation (from the same sentence)
        """
        if kb_type == "relation":
            annotator_list = ["rbert_cre", "odds_ratio", "spacy_ore", "openie_ore"]
        else:
            annotator_list = ["co_occurrence"]

        annotation_id_to_relation = {}
        annotator_to_relation = {annotator: [] for annotator in annotator_list}

        sentence_id_to_index = {}
        sentence_list = []

        for evidence_id, (head, tail, annotation_id, pmid, sentence_id) in self.evidence_list:
            head_type, head_id, head_name = head
            tail_type, tail_id, tail_name = tail

            # sentence
            if sentence_id not in sentence_id_to_index:
                sentence_id_to_index[sentence_id] = len(sentence_list)
                sentence = kb.get_sentence(sentence_id)
                sentence_list.append(sentence)
            sentence_index = sentence_id_to_index[sentence_id]

            # relation
            if annotation_id not in annotation_id_to_relation:
                annotator, annotation = kb.get_annotation(annotation_id)

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
                    "head": {"type": {head_type}, "id": {head_id}, "name": {head_name}},
                    "tail": {"type": {tail_type}, "id": {tail_id}, "name": {tail_name}},
                    "annotation": annotation,
                    "sentence_index": sentence_index,
                    "evidence_id": [evidence_id],
                }
                annotation_id_to_relation[annotation_id] = relation
                annotator_to_relation[annotator].append(relation)

            else:
                annotation_id_to_relation[annotation_id]["head"]["type"].add(head_type)
                annotation_id_to_relation[annotation_id]["head"]["id"].add(head_id)
                annotation_id_to_relation[annotation_id]["head"]["name"].add(head_name)
                annotation_id_to_relation[annotation_id]["tail"]["type"].add(tail_type)
                annotation_id_to_relation[annotation_id]["tail"]["id"].add(tail_id)
                annotation_id_to_relation[annotation_id]["tail"]["name"].add(tail_name)
                annotation_id_to_relation[annotation_id]["evidence_id"].append(evidence_id)

        # sort set into list
        for _annotator, relation_list in annotator_to_relation.items():
            for relation in relation_list:
                for e in ["head", "tail"]:
                    for t in ["type", "id", "name"]:
                        relation[e][t] = sorted(relation[e][t])

        # sort cre relation by score
        if "rbert_cre" in annotator_to_relation:
            annotator_to_relation["rbert_cre"] = sorted(
                annotator_to_relation["rbert_cre"],
                key=lambda r: float(r["annotation"]["score"][:-1]),
                reverse=True,
            )

        self.sentence_list = sentence_list
        self.sentences = len(sentence_list)

        self.annotator_to_relation = annotator_to_relation
        self.relations = len(annotation_id_to_relation)

        if clean_up_evidence:
            self.evidence_list = []
        return

    def get_relevance(self):
        relevance = 0

        for annotator, relation_list in self.annotator_to_relation.items():
            if annotator == "rbert_cre":
                for relation in relation_list:
                    score = relation["annotation"]["score"]
                    score = float(score[:-1]) * 0.01
                    relevance += score

            elif annotator == "odds_ratio":
                relevance += 1 * len(relation_list)

            elif annotator == "spacy_ore":
                relevance += 0.5 * len(relation_list)

            elif annotator == "openie_ore":
                relevance += 0.5 * len(relation_list)

            elif annotator == "co_occurrence":
                relevance += 0.1 * len(relation_list)

        self.relevance = relevance
        return


def get_evidence_ids_by_entity(entity, key, return_list=True):
    if entity[0] == "VARIANT":
        type_list = ["ProteinMutation", "DNAMutation", "SNP", "CopyNumberVariant"]
    else:
        type_list = [entity[0]]

    if len(type_list) == 1:
        real_type_entity = (type_list[0], *entity[1:])
        evidence_id_list = kb.get_evidence_ids_by_entity(real_type_entity, key=key)
        return evidence_id_list

    evidence_id_set_list = []

    for _type in type_list:
        real_type_entity = (_type, *entity[1:])
        evidence_id_list = kb.get_evidence_ids_by_entity(real_type_entity, key=key)
        evidence_id_set_list.append(set(evidence_id_list))

    full_evidence_id_list = set.union(*evidence_id_set_list)
    del evidence_id_set_list

    if return_list:
        full_evidence_id_list = sorted(full_evidence_id_list)
    return full_evidence_id_list


def get_evidence_ids_by_pair(pair, key, return_list=True):
    head_id_set = get_evidence_ids_by_entity(pair[0], key[0], return_list=False)
    tail_id_set = get_evidence_ids_by_entity(pair[1], key[1], return_list=False)

    if isinstance(head_id_set, list):
        head_id_set = set(head_id_set)
    if isinstance(tail_id_set, list):
        tail_id_set = set(tail_id_set)

    id_list = head_id_set & tail_id_set
    if return_list:
        return sorted(id_list)
    return id_list


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

        self.evidence_id_list = []
        self.paper_list = []

        self.statistics = {}

        self.summary_text = ""
        self.summary_html = ""
        return

    def run_pipeline(self):
        self.get_argument()
        self.get_evidence_id()
        self.get_paper_evidence()
        self.get_paper_relation()

        if "paper_sort" in self.arg and self.arg["paper_sort"] in ["citation", "year", "journal_impact"]:
            self.get_paper_meta()
            self.sort_paper_and_paginate()
        else:
            self.sort_paper_and_paginate()
            self.get_paper_meta()

        self.get_statistics()
        self.get_summary()
        return

    def run_no_pagination_get_statistics_pipeline(self):
        self.get_argument()
        self.arg["paper_start"], self.arg["paper_end"] = 0, float("inf")
        self.get_evidence_id()
        self.get_paper_evidence()
        return

    def get_argument(self):
        arg = self.arg

        # query filter
        logger.info(f"[Query] filter={arg['query_filter']}")

        # e1
        if "A" in arg["query_filter"]:
            if arg["e1_filter"] == "type_id_name":
                e1 = (arg["e1_type"], arg["e1_id"], arg["e1_name"])
            elif arg["e1_filter"] == "type_id":
                e1 = (arg["e1_type"], arg["e1_id"])
            elif arg["e1_filter"] == "type_name":
                e1 = (arg["e1_type"], arg["e1_name"])
            else:
                assert False
            logger.info(f"[Entity A] key={arg['e1_filter']} value={e1}")
        else:
            e1 = None
        arg["e1"] = e1

        # e2
        if "B" in arg["query_filter"]:
            if arg["e2_filter"] == "type_id_name":
                e2 = (arg["e2_type"], arg["e2_id"], arg["e2_name"])
            elif arg["e2_filter"] == "type_id":
                e2 = (arg["e2_type"], arg["e2_id"])
            elif arg["e2_filter"] == "type_name":
                e2 = (arg["e2_type"], arg["e2_name"])
            else:
                assert False
            logger.info(f"[Entity B] key={arg['e2_filter']} value={e2}")
        else:
            e2 = None
        arg["e2"] = e2

        # pmid
        if "P" in arg["query_filter"]:
            logger.info(f"[PMID] value={arg['query_pmid']}")

        # pagination
        try:
            arg["kb_start"] = int(arg["kb_start"])
        except (KeyError, ValueError):
            arg["kb_start"] = None  # slice from the first item
        try:
            arg["kb_end"] = int(arg["kb_end"])
        except (KeyError, ValueError):
            arg["kb_end"] = None  # slice to the last item
        try:
            arg["paper_start"] = int(arg["paper_start"])
        except (KeyError, ValueError):
            arg["paper_start"] = 0
        try:
            arg["paper_end"] = int(arg["paper_end"])
        except (KeyError, ValueError):
            arg["paper_end"] = float("inf")
        logger.info(
            f"[Pagination]"
            f" request_kb_range=[{arg['kb_start']} - {arg['kb_end']});"
            f" request_paper_range=[{arg['paper_start']} - {arg['paper_end']});"
        )
        return

    def get_evidence_id(self):
        arg = self.arg

        if eid_list:
            evidence_id_list = eid_list

        elif arg["query_filter"] == "P":
            evidence_id_list = kb.get_evidence_ids_by_pmid(arg["query_pmid"])

        elif arg["query_filter"] == "A":
            evidence_id_list = get_evidence_ids_by_entity(arg["e1"], arg["e1_filter"], return_list=True)

        elif arg["query_filter"] == "B":
            evidence_id_list = get_evidence_ids_by_entity(arg["e2"], arg["e2_filter"], return_list=True)

        elif arg["query_filter"] == "AB":
            evidence_id_list = get_evidence_ids_by_pair(
                (arg["e1"], arg["e2"]),
                (arg["e1_filter"], arg["e2_filter"]),
                return_list=True,
            )

        elif arg["query_filter"] == "ABP":
            ab_list = get_evidence_ids_by_pair(
                (arg["e1"], arg["e2"]),
                (arg["e1_filter"], arg["e2_filter"]),
                return_list=False,
            )
            p_list = kb.get_evidence_ids_by_pmid(arg["query_pmid"])
            evidence_id_list = sorted(ab_list & set(p_list))
            del ab_list, p_list

        else:
            assert False

        evidence_ids = len(evidence_id_list)
        logger.info(f"Total # filter-matching items in KB = {evidence_ids:,}")
        self.evidence_id_list = evidence_id_list[arg["kb_start"]:arg["kb_end"]]
        return

    def get_paper_evidence(self, clean_up_evidence_id=True):
        arg = self.arg
        evidence_id_list = self.evidence_id_list

        paper_list = []
        paper = Paper(None)
        pmids = 0

        sentence_id_set = set()
        annotation_id_set = set()
        kb_items = 0

        for evidence_id in evidence_id_list:
            evidence = kb.get_evidence_by_id(evidence_id, return_annotation=False, return_sentence=False)
            _head, _tail, annotation_id, pmid, sentence_id = evidence

            # check if we have arrived at new paper
            if pmid != paper.pmid:
                if "paper_sort" not in arg and pmids == arg["paper_end"]:  # pagination early stop if no sorting
                    break
                else:
                    if paper.evidence_list:
                        paper.kb_items = len(paper.evidence_list)
                        paper_list.append(paper)
                    paper = Paper(pmid)
                    pmids += 1

            if "paper_sort" in arg or pmids > arg["paper_start"]:  # pagination initial skip if no sorting
                paper.evidence_list.append((evidence_id, evidence))
                kb_items += 1
                annotation_id_set.add(annotation_id)
                sentence_id_set.add(sentence_id)
        if paper.evidence_list:
            paper.kb_items = len(paper.evidence_list)
            paper_list.append(paper)

        self.paper_list = paper_list
        if clean_up_evidence_id:
            self.evidence_id_list = []

        self.statistics = {
            "papers": len(paper_list),
            "sentences": len(sentence_id_set),
            "relations": len(annotation_id_set),
            "kb_items": kb_items,
        }
        log = "[statistics before sorting and pagination] "
        for item, number in self.statistics.items():
            log += f" {number:,} {item};"
        logger.info(log[:-1])
        return

    def get_paper_relation(self, clean_up_evidence=True):
        for paper in self.paper_list:
            paper.get_sentence_and_relation(clean_up_evidence=clean_up_evidence)
        return

    def get_paper_meta(self):
        for paper in self.paper_list:
            paper.get_meta()
        return

    def sort_paper_and_paginate(self):
        arg = self.arg

        if "paper_sort" not in arg:
            return

        elif arg["paper_sort"] == "relevance":
            for paper in self.paper_list:
                paper.get_relevance()
                paper.sort_key = (paper.relevance, int(paper.pmid))

        elif arg["paper_sort"] == "citation":
            for paper in self.paper_list:
                try:
                    citation = int(paper.meta["citation"])
                except ValueError:
                    citation = 0
                paper.sort_key = (citation, int(paper.pmid))

        elif arg["paper_sort"] == "year":
            for paper in self.paper_list:
                try:
                    year = int(paper.meta["year"])
                except ValueError:
                    year = 0
                paper.sort_key = (year, int(paper.pmid))

        elif arg["paper_sort"] == "journal_impact":
            for paper in self.paper_list:
                try:
                    journal_impact = float(paper.meta["journal_impact"])
                except ValueError:
                    journal_impact = 0
                paper.sort_key = (journal_impact, int(paper.pmid))

        else:
            assert False

        self.paper_list = sorted(self.paper_list, key=lambda p: p.sort_key, reverse=True)
        i = arg["paper_start"]
        j = None if isinstance(arg["paper_end"], float) else arg["paper_end"]
        self.paper_list = self.paper_list[i:j]
        return

    def get_statistics(self):
        kb_items = 0
        relations = 0
        sentences = 0
        annotator_to_relations = defaultdict(lambda: 0)

        for paper in self.paper_list:
            kb_items += paper.kb_items
            relations += paper.relations
            sentences += paper.sentences
            for annotator, relation_list in paper.annotator_to_relation.items():
                annotator_to_relations[annotator] += len(relation_list)

        papers = len(self.paper_list)
        self.statistics = {
            "papers": papers,
            "sentences": sentences,
            "relations": relations,
            "kb_items": kb_items,
        }

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

        if kb_type == "relation":
            summary_evidence_id_list = [
                _id
                for paper in self.paper_list
                for _annotator, relation_list in paper.annotator_to_relation.items()
                for relation in relation_list
                for _id in relation["evidence_id"]
            ]

            if eid_list:
                summary_query = "X"
                summary_target = None
            elif arg["query_filter"] == "P":
                summary_query = "P"
                summary_target = arg["query_pmid"]
            elif arg["query_filter"] == "A":
                summary_query = "A"
                summary_target = (arg["e1_filter"], (arg["e1_type"], arg["e1_id"], arg["e1_name"]))
            elif arg["query_filter"] == "B":
                summary_query = "A"
                summary_target = (arg["e2_filter"], (arg["e2_type"], arg["e2_id"], arg["e2_name"]))
            elif arg["query_filter"] == "AB":
                summary_query = "AB"
                summary_target = (
                    arg["e1_filter"], (arg["e1_type"], arg["e1_id"], arg["e1_name"]),
                    arg["e2_filter"], (arg["e2_type"], arg["e2_id"], arg["e2_name"]),
                )
            elif arg["query_filter"] == "ABP":
                summary_query = "ABP"
                summary_target = (
                    arg["e1_filter"], (arg["e1_type"], arg["e1_id"], arg["e1_name"]),
                    arg["e2_filter"], (arg["e2_type"], arg["e2_id"], arg["e2_name"]),
                    arg["query_pmid"],
                )
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
                summary_text = "No summary."
                summary_html = html.escape(summary_text)

        else:
            summary_text = "No summary."
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
            + "</div>"

        self.summary_text = summary_text
        self.summary_html = summary_html
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
                head_type, head_id, head_name = (
                    relation["head"]["type"], relation["head"]["id"], relation["head"]["name"],
                )
                tail_type, tail_id, tail_name = (
                    relation["tail"]["type"], relation["tail"]["id"], relation["tail"]["name"],
                )
                annotation = relation["annotation"]
                sentence_index = relation["sentence_index"]
                sentence = sentence_list[sentence_index]
                evidence_id = relation["evidence_id"]

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

                if show_eid:
                    evidence_id_html = "<br />" + html.escape(" ".join([str(_id) for _id in evidence_id]))
                else:
                    evidence_id_html = ""

                relation_table_html += \
                    f"<tr>" \
                    f"<td><pre>{head_html}</pre></td>" \
                    f"<td><pre>{tail_html}</pre></td>" \
                    f"<td>{annotator_html}{evidence_id_html}</td>" \
                    f"<td>{annotation_html}</td>" \
                    f"<td>{pmid_html}</td>" \
                    f"<td>{sentence_html}</td>" \
                    f"</tr>"

    relation_table_html += "</table>"

    # combined html
    result = \
        rel.summary_html \
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
        "summary": {
            "text": rel.summary_text,
            "html": rel.summary_html,
        },
        "paper_list": [
            {
                "pmid": paper.pmid,
                "meta": paper.meta,
                "sentence_list": paper.sentence_list,
                "annotator_to_relation": paper.annotator_to_relation,
            }
            for paper in rel.paper_list
        ],
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default="12345")

    parser.add_argument("--variant_dir", default="data/variant")
    parser.add_argument("--gene_dir", default="data/gene")
    parser.add_argument("--meta_dir", default="data/meta")
    parser.add_argument("--kb_type", default="relation", choices=["relation", "cooccur"])

    # parser.add_argument("--kb_dir", default="pubmedKB-BERN/189_236_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-BERN/1_236_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC/256_319_disk")
    parser.add_argument("--kb_dir", default="pubmedKB-PTC/1_319_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC-FT/15823_19778_disk")
    # parser.add_argument("--kb_dir", default="pubmedKB-PTC-FT/1_19778_disk")

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
    kb_meta = Meta(arg.meta_dir)

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
