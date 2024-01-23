import csv
import sys
import copy
import html
import json
import logging
import traceback
from collections import defaultdict

from flask import Flask, render_template, request

from kb_utils import query_variant, NEN, V2G, NCBIGene, VariantNEN, KB, PaperKB, GeVarToGLOF, Meta
from kb_utils import GVDScore, GDScore, DiseaseToGene
from kb_utils import MESHNameKB, MESHGraph, MESHChemical, ChemicalDiseaseKB
from kb_utils import ner_gvdc_mapping, entity_type_to_real_type_mapping
from summary_utils import Summary
from VarSum_germline import GermlineVarSum
try:
    import gpt_utils
    from gpt_utils import PaperGPT, ReviewGPT
except ModuleNotFoundError:
    pass
from kb_utils import QA

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
nen = NEN(None)
v2g = V2G(None, None)
ncbi_gene = NCBIGene(None)
variant_nen = VariantNEN(None)
kb = KB(None)
kb_meta = Meta(None)
paper_nen = PaperKB(None)
paper_glof = PaperKB(None)
entity_glof = GeVarToGLOF(None)
gvd_score = GVDScore(None)
gd_score = GDScore(None)
gd_db = GVDScore(None)
disease_to_gene = DiseaseToGene()
mesh_name_kb = MESHNameKB(None)
mesh_graph = MESHGraph(None)
mesh_chemical = MESHChemical(None)
chemical_disease_kb = ChemicalDiseaseKB(None)
qa = QA(None)
kb_type = None
show_aid = False


@app.route("/")
def serve_base():
    return render_template("base.html")


@app.route("/home")
def serve_home():
    return render_template("home.html")


@app.route("/name_to_id_alias")
def serve_name_to_id_alias():
    return render_template("name_to_id_alias.html")


@app.route("/var")
def serve_var():
    return render_template("var.html")


@app.route("/rel")
def serve_rel():
    return render_template("rel.html")


@app.route("/paper")
def serve_paper():
    return render_template("paper.html")


@app.route("/rs_hgvs_gene")
def serve_rs_hgvs_gene():
    return render_template("rs_hgvs_gene.html")


@app.route("/pmid_glof")
def serve_pmid_glof():
    return render_template("pmid_glof.html")


@app.route("/ent_glof")
def serve_ent_glof():
    return render_template("ent_glof.html")


@app.route("/id_to_name")
def serve_id_to_name():
    return render_template("id_to_name.html")


@app.route("/varsum")
def serve_varsum():
    return render_template("varsum.html")


@app.route("/litsum")
def serve_litsum():
    return render_template("litsum.html")


@app.route("/gvd_stats")
def serve_gvd_stats():
    return render_template("gvd_stats.html")


@app.route("/gd_db")
def serve_gd_db():
    return render_template("gd_db.html")


@app.route("/disease_to_gene")
def serve_disease_to_gene():
    return render_template("disease_to_gene.html")


@app.route("/mesh_disease")
def serve_mesh_disease():
    return render_template("mesh_disease.html")


@app.route("/mesh_chemical")
def serve_mesh_chemical():
    return render_template("mesh_chemical.html")


@app.route("/chemical_to_disease")
def serve_chemical_to_disease():
    return render_template("chemical_to_disease.html")


@app.route("/qa")
def serve_qa():
    return render_template("qa.html")


@app.route("/run_name_to_id_alias", methods=["POST"])
def run_name_to_id_alias():
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

    name_similarity_list = nen.get_names_by_query(
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
        type_id_frequency_list = nen.get_ids_by_name(name)
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
            alias_frequency_list = nen.get_aliases_by_id(_type, _id, max_aliases=max_aliases)
            # logger.info(f"({_type}, {_id}, {name}, {id_frequency}): alias_list={alias_frequency_list}")

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


@app.route("/query_name_to_id_alias")
def query_name_to_id_alias():
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
    name_similarity_list = nen.get_names_by_query(
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
        type_id_frequency_list = nen.get_ids_by_name(name)
        ids = len(type_id_frequency_list)
        logger.info(f"ids: {ids}")

        for _type, _id, id_frequency in type_id_frequency_list:
            type_id_alias = {
                "type": _type,
                "id": _id,
                "type_id_name_frequency": id_frequency,
            }

            # alias
            alias_frequency_list = nen.get_aliases_by_id(_type, _id, max_aliases=max_aliases)
            type_id_alias["alias_list"] = [
                {
                    "alias": alias,
                    "type_id_alias_frequency": alias_frequency,
                }
                for alias, alias_frequency in alias_frequency_list
            ]

            match["type_id_alias_list"].append(type_id_alias)
            # logger.info(f"({_type}, {_id}, {name}, {id_frequency}): alias_list={alias_frequency_list}")

        response["match_list"].append(match)

    return json.dumps(response)


@app.route("/run_id_to_name", methods=["POST"])
def run_id_to_name():
    arg = json.loads(request.data)
    _type = arg.get("type", "").strip()
    _id = arg.get("id", "").strip()
    top_k = 20

    logger.info(f"[query] type={_type} id={_id}")

    # expand the umbrella type to real types and query KB
    name_frequency_list = []
    for _type in entity_type_to_real_type_mapping.get(_type, [_type]):
        name_frequency_list += nen.get_aliases_by_id(_type, _id, max_aliases=top_k)
    name_frequency_list = sorted(name_frequency_list, key=lambda nf: -nf[1])[:top_k]

    # table html
    table_html = f"<table><tr><th>Name</th><th>Frequency</th></tr>"

    for name, frequency in name_frequency_list:
        name_html = html.escape(name)
        frequency_html = html.escape(f"{frequency:,}")
        table_html += f"<tr><td>{name_html}</td><td>{frequency_html}</td></tr>"

    table_html += "</table>"

    result = table_html + "<br /><br /><br /><br /><br />"

    response = {"result": result}
    return json.dumps(response)


@app.route("/query_id_to_name")
def query_id_to_name():
    arg = request.args
    _type = arg.get("type", "")
    _id = arg.get("id", "")
    top_k = 20

    response = {}

    # url argument
    _type = arg.get("type", "").strip()
    _id = arg.get("id", "").strip()

    response["url_argument"] = {
        "type": _type,
        "id": _id,
    }

    logger.info(f"[query] type={_type} id={_id}")

    # expand the umbrella type to real types and query KB
    name_frequency_list = []
    for _type in entity_type_to_real_type_mapping.get(_type, [_type]):
        name_frequency_list += nen.get_aliases_by_id(_type, _id, max_aliases=top_k)
    name_frequency_list = sorted(name_frequency_list, key=lambda nf: -nf[1])[:top_k]
    response["name_frequency_list"] = name_frequency_list

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
        type_id_name_frequency_list = nen.get_variant_in_kb(id_list, name_list)
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
        type_id_name_frequency_list = nen.get_variant_in_kb(id_list, name_list)
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


@app.route("/run_rs_hgvs_gene", methods=["POST"])
def run_rs_hgvs_gene():
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


@app.route("/query_rs_hgvs_gene")
def query_rs_hgvs_gene():
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

        self.sentence_index_to_sentence_mention = {}
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
        sid_to_sentence_index = dict()
        sentence_index_to_sentence_mention = dict()

        for aid, _ann_score in self.aid_score_list:
            sid, h_list, t_list, annotator, annotation = kb.get_annotation(aid)

            # sentence and mention
            if sid not in sid_to_sentence_index:
                sentence_index, sentence, mention_list = kb.get_sentence(sid)
                mention_list = [
                    {
                        "name": name,
                        "type": _type,
                        "id": id_list,
                        "offset": pos,
                    }
                    for name, _type, id_list, pos in mention_list
                ]

                sid_to_sentence_index[sid] = sentence_index
                sentence_index_to_sentence_mention[sentence_index] = {
                    "sentence": sentence,
                    "mention": mention_list,
                }

            sentence_index = sid_to_sentence_index[sid]

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

        self.sentence_index_to_sentence_mention = sentence_index_to_sentence_mention
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
            sentences += len(paper.sentence_index_to_sentence_mention)
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
        sentence_index_to_sentence_mention = paper.sentence_index_to_sentence_mention
        annotator_to_relation = paper.annotator_to_relation

        for annotator, relation_list in annotator_to_relation.items():
            annotator_html = html.escape(annotator)

            for relation in relation_list:
                h_list = relation["head_mention"]
                t_list = relation["tail_mention"]
                annotation = relation["annotation"]
                sentence_index = relation["sentence_index"]
                aid = relation["annotation_id"]

                sentence_data = sentence_index_to_sentence_mention[sentence_index]
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


@app.route("/query_rel", methods=["GET", "POST"])
def query_rel():
    if request.method == "GET":
        raw_arg = request.args
    else:
        raw_arg = json.loads(request.data)

    rel = Rel(raw_arg)
    rel.run_pipeline()

    response = {
        "url_argument": rel.str_arg,
        "result_statistics": rel.statistics,
        "paper_list": [
            {
                "pmid": paper.pmid,
                "meta": paper.meta,
                "sentence_data": paper.sentence_index_to_sentence_mention,
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


@app.route("/query_rel_statistics", methods=["GET", "POST"])
def query_rel_statistics():
    if request.method == "GET":
        raw_arg = request.args
    else:
        raw_arg = json.loads(request.data)

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


def get_sorted_nonoverlap_mention_list(mention_list, glof_mention_list):
    # sort mention list and remove overlap
    if len(mention_list) > 1:
        mention_list = sorted(mention_list, key=lambda m: m["offset"])
        clean_mention_list = [mention_list[0]]
        for mention in mention_list[1:]:
            last_mention = clean_mention_list[-1]
            last_offset = last_mention["offset"] + len(last_mention["name"])
            if mention["offset"] >= last_offset:
                clean_mention_list.append(mention)
        mention_list = clean_mention_list

    # sort glof mention list and remove overlap
    if len(glof_mention_list) > 1:
        glof_mention_list = sorted(glof_mention_list, key=lambda m: m["offset"])
        clean_mention_list = [glof_mention_list[0]]
        for mention in glof_mention_list[1:]:
            last_mention = clean_mention_list[-1]
            last_offset = last_mention["offset"] + len(last_mention["name"])
            if mention["offset"] >= last_offset:
                clean_mention_list.append(mention)
        glof_mention_list = clean_mention_list

    # remove glof mentions that overlap with normal mentions
    if mention_list and glof_mention_list:
        mention_index_set = {
            i
            for mention in mention_list
            for i in range(mention["offset"], mention["offset"] + len(mention["name"]))
        }
        clean_mention_list = []
        for mention in glof_mention_list:
            if all(
                i not in mention_index_set
                for i in range(mention["offset"], mention["offset"] + len(mention["name"]))
            ):
                clean_mention_list.append(mention)
        glof_mention_list = clean_mention_list

    # sort the two nonoverlap mention lists
    mention_list = mention_list + glof_mention_list
    mention_list = sorted(mention_list, key=lambda m: m["offset"])
    return mention_list


@app.route("/run_pmid_glof", methods=["POST"])
def run_pmid_glof():
    arg = json.loads(request.data)
    query = arg.get("query", "")

    meta = kb_meta.get_meta_by_pmid(query)
    paper = paper_glof.query_data(query)

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
        "glof": "background-color:#5f96ff4d;",
    }

    for sentence_datum in paper["sentence_list"]:
        sentence = sentence_datum["sentence"]
        mention_list = sentence_datum["mention"]
        glof_mention_list = sentence_datum["glof_mention_list"]
        mention_list = get_sorted_nonoverlap_mention_list(mention_list, glof_mention_list)

        sentence_html = ""
        last_j = 0

        for mention in mention_list:
            name = mention["name"]
            _type = mention["type"]
            i = mention["offset"]
            j = i + len(name)

            span_style = span_class_to_style[ner_gvdc_mapping.get(_type, "glof")]
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
        glof_mention_list = sentence_datum["glof_mention_list"]
        if not mention_list and not glof_mention_list:
            continue

        sentence_html = f'<div style="font-size: 18px; line-height: 200%;">{sentence_html_list[si]}</div>'
        sentence_html += \
            "<table><tr>" \
            + "<th>Name</th>" \
            + "<th>Type</th>" \
            + "<th>ID</th>" \
            + "<th>Offset</th>" \
            + "</tr>"

        for mention in mention_list + glof_mention_list:
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


@app.route("/query_pmid_glof")
def query_pmid_glof():
    arg = request.args
    query = arg.get("query", "")

    paper = paper_glof.query_data(query)
    meta = kb_meta.get_meta_by_pmid(query)

    response = {
        "url_argument": arg,
        "meta": meta,
        "paper": paper,
    }
    return json.dumps(response)


@app.route("/run_ent_glof", methods=["POST"])
def run_ent_glof():
    arg = json.loads(request.data)
    _type = arg.get("type", "")
    _id = arg.get("id", "")

    glof_pmid_sid = entity_glof.query_data(_type, _id)

    glof_to_html = {}

    for glof in ["gof", "lof"]:
        # title
        title_html = f'<div style="font-size: 20px; line-height: 200%;">{html.escape(glof.upper())}</div>'

        # pmid to sentence_index table
        table_html = "<table><tr><th>PMID</th><th>sentence index</th></tr>"
        pmid_sid = sorted(glof_pmid_sid.get(glof, {}).items(), key=lambda kv: -len(kv[1]))

        for pmid, sid_list in pmid_sid:
            table_html += f'<tr><td><a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">{pmid}</a></td>'
            sid_list = ", ".join([str(sid) for sid in sid_list])
            sid_list = html.escape(sid_list)
            table_html += f'<td>{sid_list}</td></tr>'

        table_html += "</table>"

        glof_to_html[glof] = title_html + "<br />" + table_html

    result = glof_to_html["gof"] \
             + "<br /><br /><br />" \
             + glof_to_html["lof"] \
             + "<br /><br /><br /><br /><br />"

    response = {
        "result": result,
    }
    return json.dumps(response)


@app.route("/query_ent_glof")
def query_ent_glof():
    arg = request.args
    _type = arg.get("type", "")
    _id = arg.get("id", "")

    glof_pmid_sid = entity_glof.query_data(_type, _id)

    response = {
        "url_argument": arg,
        "GOF_pmid_to_sentence": glof_pmid_sid["gof"],
        "LOF_pmid_to_sentence": glof_pmid_sid["lof"],
    }
    return json.dumps(response)


@app.route("/run_varsum", methods=["POST"])
def run_varsum():
    data = json.loads(request.data)
    query = json.loads(data["query"])
    logger.info(f"query={query}")

    report = GermlineVarSum(query, lang = 'En')
    report = report.generate_report()
    report = html.escape(report)

    result = f'<div style="font-size: 16px; line-height: 200%;">{report}</div><br />'

    response = {"result": result}
    return json.dumps(response)


@app.route("/query_varsum", methods=["GET", "POST"])
def query_varsum():
    response = {}

    if request.method == "GET":
        arg = request.args
    else:
        arg = json.loads(request.data)

    # url argument
    query = arg.get("query")
    response["url_argument"] = {
        "query": query,
    }
    query = json.loads(query)
    logger.info(f"query={query}")

    # variant matches
    report = GermlineVarSum(query, lang = 'En')
    report = report.generate_report()
    response["report"] = report
    return json.dumps(response)


@app.route("/run_litsum", methods=["POST"])
def run_litsum():
    # argument
    data = json.loads(request.data)
    gpt_utils.openai.api_key = data["openai_api_key"]
    query = json.loads(data["query"])
    logger.info(f"query={query}")

    entity_1 = query["entity_1"]
    entity_2 = query["entity_2"]
    pmid_list = query["pmid_list"]

    # paper summary
    paper_html_list = []
    papergpt_list = []

    for pmid in pmid_list:
        paper = paper_nen.query_data(pmid)
        title = paper["title"]
        abstract = paper["abstract"]

        if title or abstract:
            papergpt = PaperGPT(pmid, title, abstract, entity_1, entity_2)
            papergpt.get_paper_summary()
            papergpt_list.append(papergpt)

            title_html = html.escape(title)
            summary_html = html.escape(papergpt.paper_summary)
            summary_html = summary_html.replace("\n", "<br />")
        else:
            title_html = "Paper not found"
            summary_html = "No summary."

        paper_html = \
            '<div style="font-size: 16px; font-weight: bold; line-height: 200%;">' \
            f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">[PMID-{pmid}]</a> ' \
            f'{title_html}' \
            '</div><br />' \
            '<div style="font-size: 16px; line-height: 200%;">' \
            f'{summary_html}' \
            '</div>'
        paper_html_list.append(paper_html)

    all_paper_html = "<br /><hr /><br />".join(paper_html_list)

    # review summary
    reviewgpt = ReviewGPT(papergpt_list, entity_1, entity_2)
    reviewgpt.get_summary()
    review_html = html.escape(reviewgpt.summary)

    result = \
        f'<div style="font-size: 16px; font-weight: bold; line-height: 200%;">[REVIEW] {entity_1} and {entity_2}</div><br />' \
        f'<div style="font-size: 16px; line-height: 200%;">{review_html}</div><br /><hr /><br />' \
        f"{all_paper_html}"

    response = {"result": result}
    return json.dumps(response)


@app.route("/query_litsum")
def query_litsum():
    response = {}

    # url argument
    openai_api_key = request.args.get("openai_api_key")
    gpt_utils.openai.api_key = openai_api_key

    query = request.args.get("query")
    response["url_argument"] = {
        "query": query,
        "openai_api_key": "yolo",
    }
    query = json.loads(query)
    logger.info(f"query={query}")

    entity_1 = query["entity_1"]
    entity_2 = query["entity_2"]
    pmid_list = query["pmid_list"]

    # paper summary
    paper_summary_list = []
    papergpt_list = []

    for pmid in pmid_list:
        paper = paper_nen.query_data(pmid)
        title = paper["title"]
        abstract = paper["abstract"]

        if title or abstract:
            papergpt = PaperGPT(pmid, title, abstract, entity_1, entity_2)
            papergpt.get_paper_summary()
            papergpt_list.append(papergpt)

            paper_summary_list.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "summary": papergpt.paper_summary,
            })
        else:
            paper_summary_list.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "summary": "No summary.",
            })

    response["paper_summary_list"] = paper_summary_list

    # review summary
    reviewgpt = ReviewGPT(papergpt_list, entity_1, entity_2)
    reviewgpt.get_summary()
    response["review_summary"] = reviewgpt.summary

    return json.dumps(response)


@app.route("/run_gvd_stats", methods=["POST"])
def run_gvd_stats():
    arg = json.loads(request.data)
    _type = arg.get("type", "")
    arg_gene_id = arg.get("gene_id", "")
    arg_variant_id = arg.get("variant_id", "")
    arg_disease_id = arg.get("disease_id", "")
    top_k = arg.get("top_k", None)
    if top_k:
        top_k = int(top_k)

    gvd_score_data = gvd_score.query_data(_type, arg_gene_id, arg_variant_id, arg_disease_id)

    ann_list = [
        "paper", "sentence",
        "odds_ratio",
        "cre_Cause-associated", "cre_Appositive", "cre_In-patient",
        "spacy_ore", "openie_ore",
        "sort_score", "new_score",
    ]

    # table header
    if "g" in _type:
        header_list = ["gene", "disease"] + ann_list
    else:
        header_list = ["gene", "variant", "disease"] + ann_list

    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in header_list)
    table_html = f"<table><tr>{header_html}</tr>"

    # table data

    def get_table_cell_for_gene_id(_gene_id):
        gene_name = ncbi_gene.id_to_name.get(_gene_id, "-")
        cell = f"({_gene_id}) {gene_name}"
        cell = f"<td>{html.escape(cell)}</td>"
        return cell

    def get_table_cell_for_variant_id(_variant_id):
        _i = _variant_id.find("_")
        _gene_id, _variant_id = _variant_id[:_i], _variant_id[_i + 1:]

        if _variant_id.startswith("HGVS:"):
            _variant_id = _variant_id[len("HGVS:"):]
        else:
            _variant_id = "rs" + _variant_id[len("RS#:"):]

        _gene_cell = get_table_cell_for_gene_id(_gene_id)
        _variant_cell = f"<td>{html.escape(_variant_id)}</td>"
        return _gene_cell, _variant_cell

    def get_table_cell_disease_id(_disease_id):
        disease_name_list = mesh_name_kb.get_mesh_name_by_mesh_id(_disease_id)

        if disease_name_list:
            _disease_name = disease_name_list[0]
        else:
            _disease_name = "-"

        _disease_id = _disease_id[len("MESH:"):]

        cell = f"({_disease_id}) {_disease_name}"
        cell = f"<td>{html.escape(cell)}</td>"
        return cell

    def get_table_cell_for_annotation(_ann_to_score):
        cell_list = []

        for _ann in ann_list:
            _score = _ann_to_score.get(_ann, 0)
            if isinstance(_score, str):
                pass
            elif _score:
                _score = f"{_score:,}"
            else:
                _score = "-"

            cell = f"<td>{html.escape(_score)}</td>"
            cell_list.append(cell)

        cell = "".join(cell_list)
        return cell

    def get_string_score(_score):
        return f"{_score / 100:.1f}"

    if _type == "gd":
        score = gd_score.query_data("gd", arg_gene_id, arg_disease_id)
        gvd_score_data["new_score"] = get_string_score(score)

        gene_cell = get_table_cell_for_gene_id(arg_gene_id)
        disease_cell = get_table_cell_disease_id(arg_disease_id)
        ann_cell = get_table_cell_for_annotation(gvd_score_data)
        table_html += f"<tr>{gene_cell}{disease_cell}{ann_cell}</tr>"

    elif _type == "vd":
        gene_cell, variant_cell = get_table_cell_for_variant_id(arg_variant_id)
        disease_cell = get_table_cell_disease_id(arg_disease_id)
        ann_cell = get_table_cell_for_annotation(gvd_score_data)
        table_html += f"<tr>{gene_cell}{variant_cell}{disease_cell}{ann_cell}</tr>"

    elif _type == "g":
        gene_cell = get_table_cell_for_gene_id(arg_gene_id)
        disease_to_score = gd_score.query_data("g", arg_gene_id, arg_disease_id)

        for i, (result_disease_id, score) in enumerate(disease_to_score.items()):
            if top_k and i >= top_k:
                break
            ann_to_score = gvd_score_data.get(result_disease_id, {})
            ann_to_score["new_score"] = get_string_score(score)

            disease_cell = get_table_cell_disease_id(result_disease_id)
            ann_cell = get_table_cell_for_annotation(ann_to_score)
            table_html += f"<tr>{gene_cell}{disease_cell}{ann_cell}</tr>"

    elif _type == "v":
        gene_cell, variant_cell = get_table_cell_for_variant_id(arg_variant_id)
        for i, (result_disease_id, ann_to_score) in enumerate(gvd_score_data.items()):
            if top_k and i >= top_k:
                break
            disease_cell = get_table_cell_disease_id(result_disease_id)
            ann_cell = get_table_cell_for_annotation(ann_to_score)
            table_html += f"<tr>{gene_cell}{variant_cell}{disease_cell}{ann_cell}</tr>"

    elif _type == "d2g":
        disease_cell = get_table_cell_disease_id(arg_disease_id)
        gene_to_score = gd_score.query_data("d", arg_gene_id, arg_disease_id)

        for i, (result_gene_id, score) in enumerate(gene_to_score.items()):
            if top_k and i >= top_k:
                break
            ann_to_score = gvd_score_data.get(result_gene_id, {})
            ann_to_score["new_score"] = get_string_score(score)

            gene_cell = get_table_cell_for_gene_id(result_gene_id)
            ann_cell = get_table_cell_for_annotation(ann_to_score)
            table_html += f"<tr>{gene_cell}{disease_cell}{ann_cell}</tr>"

    elif _type == "d2v":
        disease_cell = get_table_cell_disease_id(arg_disease_id)
        for i, (result_variant_id, ann_to_score) in enumerate(gvd_score_data.items()):
            if top_k and i >= top_k:
                break
            gene_cell, variant_cell = get_table_cell_for_variant_id(result_variant_id)
            ann_cell = get_table_cell_for_annotation(ann_to_score)
            table_html += f"<tr>{gene_cell}{variant_cell}{disease_cell}{ann_cell}</tr>"

    else:
        assert False

    table_html += "</table>"
    result = f'<div style="width: 100%;">{table_html}</div>'

    response = {
        "result": result,
    }
    return json.dumps(response)


@app.route("/query_gvd_stats")
def query_gvd_stats():
    arg = request.args
    _type = arg.get("type", "")
    gene_id = arg.get("gene_id", "")
    variant_id = arg.get("variant_id", "")
    disease_id = arg.get("disease_id", "")
    top_k = arg.get("top_k", None)

    gvd_score_data = gvd_score.query_data(_type, gene_id, variant_id, disease_id)

    if top_k:
        top_k = int(top_k)

    if _type == "gd":
        gvd_score_data["new_score"] = gd_score.query_data("gd", gene_id, disease_id)

    elif _type == "g":
        raw_gvd_score_data = gvd_score_data
        gvd_score_data = {}
        disease_to_score = gd_score.query_data("g", gene_id, disease_id)

        for i, (result_disease_id, score) in enumerate(disease_to_score.items()):
            if top_k and i >= top_k:
                break
            ann_to_score = raw_gvd_score_data.get(result_disease_id, {})
            ann_to_score["new_score"] = score
            gvd_score_data[result_disease_id] = ann_to_score

    elif _type == "d2g":
        raw_gvd_score_data = gvd_score_data
        gvd_score_data = {}
        gene_to_score = gd_score.query_data("d", gene_id, disease_id)

        for i, (result_gene_id, score) in enumerate(gene_to_score.items()):
            if top_k and i >= top_k:
                break
            ann_to_score = raw_gvd_score_data.get(result_gene_id, {})
            ann_to_score["new_score"] = score
            gvd_score_data[result_gene_id] = ann_to_score

    elif top_k and _type in ["v", "d2v"]:
        full_gvd_score_data = gvd_score_data
        gvd_score_data = {}
        for i, (k, ann_to_score) in enumerate(full_gvd_score_data.items()):
            if i >= top_k:
                break
            gvd_score_data[k] = ann_to_score

    response = {
        "url_argument": arg,
        "result": gvd_score_data,
    }
    return json.dumps(response)


@app.route("/run_gd_db", methods=["POST"])
def run_gd_db():
    arg = json.loads(request.data)
    _type = arg.get("type", "")
    arg_gene_id = arg.get("gene_id", "")
    arg_disease_id = arg.get("disease_id", "")
    top_k = arg.get("top_k", None)
    if top_k:
        top_k = int(top_k)

    gvd_score_data = gd_db.query_data(_type, arg_gene_id, "", arg_disease_id)

    ann_list = ["clinvar2023", "clinvar", "panelapp"]

    # table header
    if "g" in _type:
        header_list = ["gene", "disease"] + ann_list
    else:
        header_list = ["gene", "variant", "disease"] + ann_list

    header_html = "".join(f"<th>{html.escape(header)}</th>" for header in header_list)
    table_html = f"<table><tr>{header_html}</tr>"

    # table data

    def get_table_cell_for_gene_id(_gene_id):
        gene_name = ncbi_gene.id_to_name.get(_gene_id, "-")
        cell = f"({_gene_id}) {gene_name}"
        cell = f"<td>{html.escape(cell)}</td>"
        return cell

    def get_table_cell_disease_id(_disease_id):
        disease_name_list = mesh_name_kb.get_mesh_name_by_mesh_id(_disease_id)

        if disease_name_list:
            _disease_name = disease_name_list[0]
        else:
            _disease_name = "-"

        _disease_id = _disease_id[len("MESH:"):]

        cell = f"({_disease_id}) {_disease_name}"
        cell = f"<td>{html.escape(cell)}</td>"
        return cell

    def get_table_cell_for_annotation(_ann_to_score):
        cell_list = []

        for _ann in ann_list:
            _score = _ann_to_score.get(_ann, 0)
            if _score:
                _score = f"{_score:,}"
            else:
                _score = "-"

            cell = f"<td>{html.escape(_score)}</td>"
            cell_list.append(cell)

        cell = "".join(cell_list)
        return cell

    if _type == "gd":
        gene_cell = get_table_cell_for_gene_id(arg_gene_id)
        disease_cell = get_table_cell_disease_id(arg_disease_id)
        ann_cell = get_table_cell_for_annotation(gvd_score_data)
        table_html += f"<tr>{gene_cell}{disease_cell}{ann_cell}</tr>"

    elif _type == "g":
        gene_cell = get_table_cell_for_gene_id(arg_gene_id)
        for i, (result_disease_id, ann_to_score) in enumerate(gvd_score_data.items()):
            if top_k and i >= top_k:
                break
            disease_cell = get_table_cell_disease_id(result_disease_id)
            ann_cell = get_table_cell_for_annotation(ann_to_score)
            table_html += f"<tr>{gene_cell}{disease_cell}{ann_cell}</tr>"

    elif _type == "d2g":
        disease_cell = get_table_cell_disease_id(arg_disease_id)
        for i, (result_gene_id, ann_to_score) in enumerate(gvd_score_data.items()):
            if top_k and i >= top_k:
                break
            gene_cell = get_table_cell_for_gene_id(result_gene_id)
            ann_cell = get_table_cell_for_annotation(ann_to_score)
            table_html += f"<tr>{gene_cell}{disease_cell}{ann_cell}</tr>"

    else:
        assert False

    table_html += "</table>"

    if "v" in _type:
        width = 1800
    else:
        width = 1500
    result = f'<div style="width: {width}px;">{table_html}</div>'

    response = {
        "result": result,
    }
    return json.dumps(response)


@app.route("/query_gd_db")
def query_gd_db():
    arg = request.args
    _type = arg.get("type", "")
    gene_id = arg.get("gene_id", "")
    disease_id = arg.get("disease_id", "")
    top_k = arg.get("top_k", None)

    gvd_score_data = gd_db.query_data(_type, gene_id, "", disease_id)

    if top_k and _type in ["g", "v", "d2g", "d2v"]:
        full_gvd_score_data = gvd_score_data
        gvd_score_data = {}
        top_k = int(top_k)
        for i, (k, ann_to_score) in enumerate(full_gvd_score_data.items()):
            if i >= top_k:
                break
            gvd_score_data[k] = ann_to_score

    response = {
        "url_argument": arg,
        "result": gvd_score_data,
    }
    return json.dumps(response)


def get_term_mesh_mapping_for_disease_to_gene(query_mesh_list, query_term_list):
    query_mesh_list = set(query_mesh_list)
    query_term_list = set(query_term_list)

    mesh_to_term = defaultdict(lambda: set())
    term_to_mesh = defaultdict(lambda: set())
    prefix = "MESH:"

    if query_mesh_list:
        # use unique mesh name as mesh term

        for query_mesh in query_mesh_list:
            if not query_mesh.startswith(prefix):
                query_mesh = prefix + query_mesh
            name_list = mesh_name_kb.get_mesh_name_by_mesh_id(query_mesh)
            name = name_list[0] if name_list else "-"
            mesh_to_term[query_mesh].add(name)
            term_to_mesh[name].add(query_mesh)

        for query_term in query_term_list:
            mesh_set = mesh_name_kb.get_mesh_id_by_all_source_name(query_term)
            for mesh in mesh_set:
                if not mesh.startswith(prefix):
                    mesh = prefix + mesh
                if mesh in mesh_to_term:
                    continue
                name_list = mesh_name_kb.get_mesh_name_by_mesh_id(mesh)
                name = name_list[0] if name_list else "-"
                mesh_to_term[mesh].add(name)
                term_to_mesh[name].add(mesh)

    else:
        # mesh and term are n-to-n
        for query_term in query_term_list:
            mesh_set = mesh_name_kb.get_mesh_id_by_all_source_name(query_term)
            for mesh in mesh_set:
                if not mesh.startswith(prefix):
                    mesh = prefix + mesh
                mesh_to_term[mesh].add(query_term)
                term_to_mesh[query_term].add(mesh)

    return mesh_to_term, term_to_mesh


@app.route("/run_disease_to_gene", methods=["POST"])
def run_disease_to_gene():
    # url argument
    data = json.loads(request.data)
    query = json.loads(data["query"])
    logger.info(f"query={query}")

    # mesh
    query_mesh_list = query.get("mesh_list", [])
    query_disease_list = query.get("disease_list", [])
    mesh_to_disease, disease_to_mesh = get_term_mesh_mapping_for_disease_to_gene(query_mesh_list, query_disease_list)
    for disease, mesh_set in disease_to_mesh.items():
        logger.info(f"[query] disease={disease} mesh_set={mesh_set}")

    # show gene->score and gene->mesh
    gene_score_list, disease_to_gene_list = disease_to_gene.get_score(mesh_to_disease, disease_to_mesh)

    gene_to_disease = defaultdict(lambda: [])
    for disease, gene_list in disease_to_gene_list.items():
        for gene in gene_list:
            gene_to_disease[gene].append(disease)

    width = 800
    table_html = f'<table style="width: {width}px;"><tr><th>Gene</th><th>Score</th><th>Disease</th></tr>'
    prefix = "MESH:"

    for gene, score in gene_score_list:
        gene_name = ncbi_gene.id_to_name.get(gene, "-")
        gene_html = f'<a href="https://www.ncbi.nlm.nih.gov/gene/{gene}">[{html.escape(gene)}]</a> {html.escape(gene_name)}'

        score_html = html.escape(f"{score:.1f}")

        disease_html_list = []
        for disease in gene_to_disease[gene]:
            mesh_html_list = []
            for mesh in disease_to_mesh[disease]:
                mesh = mesh[len(prefix):]
                mesh_html = f'<a href="https://meshb.nlm.nih.gov/record/ui?ui={mesh}">{html.escape(mesh)}</a>'
                mesh_html_list.append(mesh_html)
            disease_html = html.escape(", ").join(mesh_html_list)
            disease_html = f"[{disease_html}] {html.escape(disease)}"
            disease_html_list.append(disease_html)
        disease_html = "<br />".join(disease_html_list)

        table_html += f"<tr><td>{gene_html}</td><td>{score_html}</td><td>{disease_html}</td></tr>"
    table_html += "</table>"

    response = {"result": table_html}
    return json.dumps(response)


@app.route("/query_disease_to_gene", methods=["GET", "POST"])
def query_disease_to_gene():
    response = {}

    # url argument
    if request.method == "GET":
        query = request.args.get("query")
        query = json.loads(query)
    else:
        data = json.loads(request.data)
        query = json.loads(data["query"])

    response["url_argument"] = {
        "query": query,
    }
    logger.info(f"query={query}")

    # mesh
    query_mesh_list = query.get("mesh_list", [])
    query_disease_list = query.get("disease_list", [])
    mesh_to_disease, disease_to_mesh = get_term_mesh_mapping_for_disease_to_gene(query_mesh_list, query_disease_list)
    for disease, mesh_set in disease_to_mesh.items():
        logger.info(f"[query] disease={disease} mesh_set={mesh_set}")

    # get (gene, name) -> score and (disease, mesh_list) -> [(gene, name), ...]
    gene_score_list, disease_to_gene_list = disease_to_gene.get_score(mesh_to_disease, disease_to_mesh)

    gene_to_name = {}
    gene_name_score_list = []
    for gene, score in gene_score_list:
        name = ncbi_gene.id_to_name.get(gene, "-")
        gene_to_name[gene] = name
        gene_name_score_list.append(((gene, name), f"{score:.1f}"))
    gene_score_list = gene_name_score_list

    disease_gene_list = []
    for disease, gene_list in disease_to_gene_list.items():
        mesh_set = disease_to_mesh[disease]
        if mesh_set:
            mesh_list = list(mesh_set)
        else:
            mesh_list = ["-"]

        gene_list = [
            (gene, gene_to_name[gene])
            for gene in gene_list
        ]

        disease_gene_list.append(((disease, mesh_list), gene_list))

    response["gene_score_list"] = gene_score_list
    response["disease_gene_list"] = disease_gene_list
    return json.dumps(response)


@app.route("/run_mesh_disease", methods=["POST"])
def run_mesh_disease():
    data = json.loads(request.data)

    query_type = data["query_type"]
    query = data["query"]
    super_level = data["super_level"]
    sub_level = data["sub_level"]
    sibling_level = data["sibling_level"]
    supplemental_level = data["supplemental_level"]

    query = query.strip()

    try:
        super_level = int(super_level)
    except ValueError:
        super_level = 3

    try:
        sub_level = int(sub_level)
    except ValueError:
        sub_level = 1

    try:
        sibling_level = int(sibling_level)
    except ValueError:
        sibling_level = 1

    try:
        supplemental_level = int(supplemental_level)
    except ValueError:
        supplemental_level = 1

    logger.info(
        f"query_type={query_type}"
        f" query={query}"
        f" super_level={super_level}"
        f" sub_level={sub_level}"
        f" sibling_level={sibling_level}"
        f" supplemental_level={supplemental_level}"
    )

    # mesh
    prefix = "MESH:"

    if query_type == "mesh":
        if query.startswith(prefix):
            query = query[len(prefix):]
        if query in mesh_name_kb.mesh_to_mesh_name:
            mesh_list = [query]
        else:
            mesh_list = []

    elif query_type == "mesh_name":
        mesh_list = mesh_name_kb.mesh_name_to_mesh.get(query.lower(), [])
        mesh_list = list(mesh_list)

    elif query_type == "hpo":
        mesh_list = mesh_name_kb.hpo_to_mesh.get(query, [])
        mesh_list = list(mesh_list)

    elif query_type == "hpo_name":
        mesh_list = mesh_name_kb.hpo_name_to_mesh.get(query.lower(), [])
        mesh_list = list(mesh_list)

    elif query_type == "literature_name":
        mesh_list = mesh_name_kb.literature_name_to_mesh.get(query.lower(), [])
        mesh_list = list(mesh_list)

    elif query_type == "all_name":
        mesh_list = mesh_name_kb.get_mesh_id_by_all_source_name(query)
        mesh_list = list(mesh_list)

    else:
        assert False

    for i, mesh in enumerate(mesh_list):
        if not mesh.startswith(prefix):
            mesh_list[i] = prefix + mesh

    # name
    mesh_to_namelist = {
        mesh: mesh_name_kb.get_mesh_name_by_mesh_id(mesh)
        for mesh in mesh_list
    }

    name_table_html = \
        f"<table><tr>" \
        f"<th>MeSH ID</th>" \
        f"<th>MeSH Name</th>" \
        f"<th>MeSH Aliases</th>" \
        f"</tr>"

    for mesh, name_list in mesh_to_namelist.items():
        mesh_html = f'<a href="https://meshb.nlm.nih.gov/record/ui?ui={mesh[len(prefix):]}">{html.escape(mesh)}</a>'

        name_html = name_list[0] if name_list else "-"
        name_html = html.escape(name_html)

        alias_html = [html.escape(alias) for alias in name_list[1:]]
        alias_html = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;".join(alias_html)

        name_table_html += \
            f"<tr>" \
            f"<td>{mesh_html}</td>" \
            f"<td>{name_html}</td>" \
            f"<td>{alias_html}</td>" \
            f"</tr>"

    name_table_html += "</table>"
    name_result = name_table_html + '<br /><br /><span style="font-size: 20px;">Ontology Subgraph:</span><br />'

    # subgraph
    subgraph = mesh_graph.get_subgraph(
        mesh_list,
        super_level=super_level,
        sub_level=sub_level,
        sibling_level=sibling_level,
        supplemental_level=supplemental_level,
    )
    nodes = len(subgraph["index_to_node"])
    edges = len(subgraph["edge_list"])
    logger.info(f"{nodes:,} nodes; {edges:,} edges")

    # vis node
    node_list = []
    label_to_node_color = {
        "query": "#d5abff",  # 270°, 33%, 100% violet
        "sub-category": "#abffff",  # 180°, 33%, 100% cyan
        "super-category": "#d5ffab",  # 90°, 33%, 100% yellow-green
        "sibling": "#ffffab",  # 60°, 33%, 100% yellow
        "supplemental": "#ffd5ab",  # 30°, 33%, 100% orange
        "descriptor": "#ffabab",  # 0°, 33%, 100% red
    }

    for index, raw_node in subgraph["index_to_node"].items():
        mesh = raw_node["mesh"]
        display_name = raw_node["display_name"]
        label = raw_node["label"]

        node = {
            "id": index,
            "label": f"{mesh}\n{display_name}",
            "color": label_to_node_color[label],
        }
        node_list.append(node)

    # vis edge
    edge_list = []
    label_to_length = {
        "query": 300,
        "sub-category": 120,
        "super-category": 300,
        "sibling": 120,
        "supplemental": 120,
        "descriptor": 120,
    }
    label_to_edge_color = {
        "query": "#8945cc",  # 270°, 66%, 80% violet
        "sub-category": "#45cccc",  # 180°, 66%, 80% cyan
        "super-category": "#89cc45",  # 90°, 66%, 80% yellow-green
        "sibling": "#cccc45",  # 60°, 66%, 80% yellow
        "supplemental": "#cc8945",  # 30°, 66%, 80% orange
        "descriptor": "#cc4545",  # 0°, 66%, 80% red
    }

    for from_index, to_index in subgraph["edge_list"]:
        to_label = subgraph["index_to_node"][to_index]["label"]

        edge = {
            "from": from_index,
            "to": to_index,
            "length": label_to_length[to_label],
            "color": label_to_edge_color[to_label],
            "arrows": {"to": {"enabled": True, "type": "arrow"}},
        }
        edge_list.append(edge)

    response = {
        "result": name_result,
        "node_list": node_list,
        "edge_list": edge_list,
    }
    return json.dumps(response)


@app.route("/query_mesh_disease")
def query_mesh_disease():
    # url argument
    query_type = request.args.get("query_type")
    query = request.args.get("query")
    super_level = request.args.get("super_level")
    sub_level = request.args.get("sub_level")
    sibling_level = request.args.get("sibling_level")
    supplemental_level = request.args.get("supplemental_level")

    query = query.strip()

    try:
        super_level = int(super_level)
    except ValueError:
        super_level = 3

    try:
        sub_level = int(sub_level)
    except ValueError:
        sub_level = 1

    try:
        sibling_level = int(sibling_level)
    except ValueError:
        sibling_level = 1

    try:
        supplemental_level = int(supplemental_level)
    except ValueError:
        supplemental_level = 1

    logger.info(
        f"query_type={query_type}"
        f" query={query}"
        f" super_level={super_level}"
        f" sub_level={sub_level}"
        f" sibling_level={sibling_level}"
        f" supplemental_level={supplemental_level}"
    )

    # mesh
    prefix = "MESH:"

    if query_type == "mesh":
        if query.startswith(prefix):
            query = query[len(prefix):]
        if query in mesh_name_kb.mesh_to_mesh_name:
            mesh_list = [query]
        else:
            mesh_list = []

    elif query_type == "mesh_name":
        mesh_list = mesh_name_kb.mesh_name_to_mesh.get(query.lower(), [])
        mesh_list = list(mesh_list)

    elif query_type == "hpo":
        mesh_list = mesh_name_kb.hpo_to_mesh.get(query, [])
        mesh_list = list(mesh_list)

    elif query_type == "hpo_name":
        mesh_list = mesh_name_kb.hpo_name_to_mesh.get(query.lower(), [])
        mesh_list = list(mesh_list)

    elif query_type == "literature_name":
        mesh_list = mesh_name_kb.literature_name_to_mesh.get(query.lower(), [])
        mesh_list = list(mesh_list)

    elif query_type == "all_name":
        mesh_list = mesh_name_kb.get_mesh_id_by_all_source_name(query)
        mesh_list = list(mesh_list)

    else:
        assert False

    for i, mesh in enumerate(mesh_list):
        if not mesh.startswith(prefix):
            mesh_list[i] = prefix + mesh

    # name
    mesh_to_namelist = {
        mesh: mesh_name_kb.get_mesh_name_by_mesh_id(mesh)
        for mesh in mesh_list
    }

    # subgraph
    subgraph = mesh_graph.get_subgraph(
        mesh_list,
        super_level=super_level,
        sub_level=sub_level,
        sibling_level=sibling_level,
        supplemental_level=supplemental_level,
    )
    nodes = len(subgraph["index_to_node"])
    edges = len(subgraph["edge_list"])
    logger.info(f"{nodes:,} nodes; {edges:,} edges")

    response = {
        "url_argument": request.args,
        "mesh_to_namelist": mesh_to_namelist,
        "subgraph": subgraph,
    }
    return json.dumps(response)


@app.route("/run_qa", methods=["POST"])
def run_qa():
    # url argument
    data = json.loads(request.data)
    query = json.loads(data["query"])
    logger.info(f"query={query}")

    # disease
    d_set = set(query.get("disease_id_list", []))
    d_name_set = set(query.get("disease_name_list", []))
    mesh_prefix = "MESH:"
    for d_name in d_name_set:
        mesh_set = mesh_name_kb.get_mesh_id_by_all_source_name(d_name)
        for mesh in mesh_set:
            if not mesh.startswith(mesh_prefix):
                mesh = mesh_prefix + mesh
            d_set.add(mesh)
    logger.info(f"d_set={d_set}")

    # gene
    g_set = set(query.get("gene_id_list", []))
    g_name_set = set(query.get("gene_name_list", []))
    for g_name in g_name_set:
        if g_name in ncbi_gene.name_to_id:
            g_set.add(ncbi_gene.name_to_id[g_name])
        elif g_name in ncbi_gene.alias_to_id:
            g_set.add(ncbi_gene.alias_to_id[g_name])
    logger.info(f"g_set={g_set}")

    # variant
    v_set = set(query.get("variant_id_list", []))
    v_name_set = set(query.get("variant_name_list", []))
    for v_name in v_name_set:
        i = v_name.find("_")
        if i == -1:
            continue

        v_g_name, v_v_name = v_name[:i], v_name[i + 1:]
        if v_g_name in ncbi_gene.name_to_id:
            v_g = ncbi_gene.name_to_id[v_g_name]
        elif v_g_name in ncbi_gene.alias_to_id:
            v_g = ncbi_gene.alias_to_id[v_g_name]
        else:
            continue

        for v_v in variant_nen.name_to_id.get(v_v_name.lower(), []):
            v = v_g + "_" + v_v
            v_set.add(v)
    logger.info(f"v_set={v_set}")

    # qa
    question = query["question"]
    answer, p_set = qa.query(question, d_set, g_set, v_set)

    # reference
    pmid_to_meta = {
        p: kb_meta.get_meta_by_pmid(p)
        for p in p_set
    }
    pmid_meta_list = sorted(pmid_to_meta.items(), key=lambda pm: -pm[1]["citation"])

    # html
    answer = "<br />".join([
        html.escape(line)
        for line in answer.split("\n")
    ])
    answer_html = f'<div style="font-size: 16px;">{answer}</div>'
    reference_html = f'<div style="font-size: 22px;">Reference</div>'
    reference_html += \
        "<table><tr>" \
        + "<th>PMID</th>" \
        + "<th>Title</th>" \
        + "<th>Year</th>" \
        + "<th>Journal</th>" \
        + "<th>Citation</th>" \
        + "</tr>"
    for pmid, meta in pmid_meta_list:
        reference_html += \
            f'<tr><td><a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">{pmid}</a></td>' \
            + f"<td>{meta['title']}</td>" \
            + f"<td>{meta['year']}</td>" \
            + f"<td>{meta['journal']}</td>" \
            + f"<td>{meta['citation']}</td></tr>"
    reference_html += "</table>"
    result = answer_html \
        + "<br /><br />" \
        + reference_html \
        + "<br /><br /><br /><br /><br />"

    response = {"result": result}
    return json.dumps(response)


@app.route("/query_qa", methods=["GET", "POST"])
def query_qa():
    response = {}

    # url argument
    if request.method == "GET":
        query = request.args.get("query")
        query = json.loads(query)
    else:
        data = json.loads(request.data)
        query = json.loads(data["query"])

    response["url_argument"] = {
        "query": query,
    }
    logger.info(f"query={query}")

    # disease
    d_set = set(query.get("disease_id_list", []))
    d_name_set = set(query.get("disease_name_list", []))
    mesh_prefix = "MESH:"
    for d_name in d_name_set:
        mesh_set = mesh_name_kb.get_mesh_id_by_all_source_name(d_name)
        for mesh in mesh_set:
            if not mesh.startswith(mesh_prefix):
                mesh = mesh_prefix + mesh
            d_set.add(mesh)
    logger.info(f"d_set={d_set}")

    # gene
    g_set = set(query.get("gene_id_list", []))
    g_name_set = set(query.get("gene_name_list", []))
    for g_name in g_name_set:
        if g_name in ncbi_gene.name_to_id:
            g_set.add(ncbi_gene.name_to_id[g_name])
        elif g_name in ncbi_gene.alias_to_id:
            g_set.add(ncbi_gene.alias_to_id[g_name])
    logger.info(f"g_set={g_set}")

    # variant
    v_set = set(query.get("variant_id_list", []))
    v_name_set = set(query.get("variant_name_list", []))
    for v_name in v_name_set:
        i = v_name.find("_")
        if i == -1:
            continue

        v_g_name, v_v_name = v_name[:i], v_name[i + 1:]
        if v_g_name in ncbi_gene.name_to_id:
            v_g = ncbi_gene.name_to_id[v_g_name]
        elif v_g_name in ncbi_gene.alias_to_id:
            v_g = ncbi_gene.alias_to_id[v_g_name]
        else:
            continue

        for v_v in variant_nen.name_to_id.get(v_v_name, []):
            v = v_g + "_" + v_v
            v_set.add(v)
    logger.info(f"v_set={v_set}")

    # qa
    question = query["question"]
    answer, p_set = qa.query(question, d_set, g_set, v_set)
    pmid_list = list(p_set)
    response["answer"] = answer
    response["pmid_list"] = pmid_list

    return json.dumps(response)


@app.route("/run_mesh_chemical", methods=["POST"])
def run_mesh_chemical():
    # url argument
    data = json.loads(request.data)
    query = json.loads(data["query"])
    logger.info(f"query={query}")

    # mesh
    mesh_list = []
    query_mesh = query.get("mesh_id", "")
    query_name = query.get("mesh_name", "")
    mesh_prefix = "MESH:"
    mesh_prefix_len = len(mesh_prefix)

    if not query_mesh.startswith(mesh_prefix):
        query_mesh = mesh_prefix + query_mesh
    if query_mesh in mesh_chemical.mesh_to_mesh_name:
        mesh_list.append(query_mesh)

    for mesh in mesh_chemical.get_id_set_by_name(query_name):
        mesh_list.append(mesh)

    # name
    mesh_to_namelist = {
        mesh: mesh_chemical.get_name_list_by_id(mesh)
        for mesh in mesh_list
    }

    # html
    name_table_html = \
        f"<table><tr>" \
        f"<th>MeSH ID</th>" \
        f"<th>MeSH Name</th>" \
        f"<th>MeSH Aliases</th>" \
        f"</tr>"

    for mesh, name_list in mesh_to_namelist.items():
        mesh_html = f'<a href="https://meshb.nlm.nih.gov/record/ui?ui={mesh[mesh_prefix_len:]}">{html.escape(mesh)}</a>'

        name_html = name_list[0] if name_list else "-"
        name_html = html.escape(name_html)

        alias_html = [html.escape(alias) for alias in name_list[1:]]
        alias_html = "<br />".join(alias_html)

        name_table_html += \
            f"<tr>" \
            f"<td>{mesh_html}</td>" \
            f"<td>{name_html}</td>" \
            f"<td>{alias_html}</td>" \
            f"</tr>"

    name_table_html += "</table>"
    response = {"result": name_table_html}
    return json.dumps(response)


@app.route("/query_mesh_chemical", methods=["GET", "POST"])
def query_mesh_chemical():
    # url argument
    if request.method == "GET":
        query = request.args.get("query")
        query = json.loads(query)
    else:
        data = json.loads(request.data)
        query = json.loads(data["query"])
    logger.info(f"query={query}")

    # mesh
    mesh_list = []
    query_mesh = query.get("mesh_id", "")
    query_name = query.get("mesh_name", "")
    mesh_prefix = "MESH:"

    if not query_mesh.startswith(mesh_prefix):
        query_mesh = mesh_prefix + query_mesh
    if query_mesh in mesh_chemical.mesh_to_mesh_name:
        mesh_list.append(query_mesh)

    for mesh in mesh_chemical.get_id_set_by_name(query_name):
        mesh_list.append(mesh)

    # name
    mesh_to_namelist = {
        mesh: mesh_chemical.get_name_list_by_id(mesh)
        for mesh in mesh_list
    }

    response = {
        "url_argument": {"query": query},
        "mesh_to_namelist": mesh_to_namelist,
    }
    return json.dumps(response)


@app.route("/query_chemical_to_disease", methods=["GET", "POST"])
def query_chemical_to_disease():
    response = {}

    # url argument
    if request.method == "GET":
        query = request.args.get("query")
        query = json.loads(query)
    else:
        data = json.loads(request.data)
        query = json.loads(data["query"])

    response["url_argument"] = {
        "query": query,
    }
    logger.info(f"query={query}")

    # chemical
    mesh_prefix = "MESH:"
    chemical_mesh = query.get("chemical_mesh", "")
    if not chemical_mesh.startswith(mesh_prefix):
        chemical_mesh = mesh_prefix + chemical_mesh
    chemical_name = mesh_chemical.get_name_list_by_id(chemical_mesh)
    chemical_name = chemical_name[0] if chemical_name else "-"
    response["chemical_mesh"] = chemical_mesh
    response["chemical_name"] = chemical_name

    # disease
    top_k = query.get("top_k", 5)
    disease_ann_pmidlist = chemical_disease_kb.get(chemical_mesh, {})
    disease_mesh_to_data = {}
    response["disease_mesh_to_data"] = disease_mesh_to_data
    pmid_to_data = {}
    response["pmid_to_data"] = pmid_to_data

    for disease_mesh, ann_to_pmidlist in disease_ann_pmidlist.items():
        # mesh
        disease_datum = {}
        disease_mesh_to_data[disease_mesh] = disease_datum

        # name
        disease_name = mesh_name_kb.get_mesh_name_by_mesh_id(disease_mesh)
        disease_name = disease_name[0] if disease_name else "-"
        disease_datum["disease_name"] = disease_name

        # annotation
        for ann, pmid_list in zip(["paper", "sentence"], ann_to_pmidlist):
            pmids = len(pmid_list)
            disease_datum[f"co-{ann}_total_pmids"] = pmids

            pmid_list = pmid_list[:top_k]
            disease_datum[f"co-{ann}_top-k_pmid_list"] = pmid_list

            for pmid in pmid_list:
                if pmid not in pmid_to_data:
                    meta = kb_meta.get_meta_by_pmid(pmid)
                    pmid_to_data[pmid] = {
                        "title": meta.get("title", ""),
                        "year": meta.get("year", ""),
                        "journal": meta.get("journal", ""),
                        "citation": meta.get("citation", 0),
                    }

    return json.dumps(response)


@app.route("/run_chemical_to_disease", methods=["POST"])
def run_chemical_to_disease():
    # url argument
    data = json.loads(request.data)
    query = json.loads(data["query"])
    logger.info(f"query={query}")

    # chemical
    mesh_prefix = "MESH:"
    mesh_prefix_len = len(mesh_prefix)
    chemical_mesh = query.get("chemical_mesh", "")
    if chemical_mesh.startswith(mesh_prefix):
        chemical_non_prefix_mesh = chemical_mesh[mesh_prefix_len:]
    else:
        chemical_non_prefix_mesh = chemical_mesh
        chemical_mesh = mesh_prefix + chemical_non_prefix_mesh
    chemical_name = mesh_chemical.get_name_list_by_id(chemical_mesh)
    chemical_name = chemical_name[0] if chemical_name else "-"

    # disease
    disease_ann_pmidlist = chemical_disease_kb.get(chemical_mesh, {})

    # chemical html
    chemical_mesh_html = html.escape(chemical_mesh)
    chemical_html = (f'<a href="https://meshb.nlm.nih.gov/record/ui?ui={chemical_non_prefix_mesh}">'
                     f'[{chemical_mesh_html}]</a>')
    chemical_html = f'<div style="font-size: 18px;">{chemical_html} {chemical_name}</div>'

    # disease table html
    top_k = query.get("top_k", 5)
    disease_table_html = (f'<table><tr>'
                          f'<th>Disease</th>'
                          f'<th>Co-paper PMID (showing top {top_k})</th>'
                          f'<th>Co-sentence PMID (showing top {top_k})</th>'
                          f'</tr>')
    large_break = '<br style="display: block; content: \' \'; margin-top: 10px;" />'

    for disease_mesh, ann_to_pmidlist in disease_ann_pmidlist.items():
        disease_non_prefix_mesh = disease_mesh[mesh_prefix_len:]

        # disease html
        disease_name = mesh_name_kb.mesh_to_mesh_name.get(disease_non_prefix_mesh, [])
        if disease_name:
            disease_name = disease_name[0]
        else:
            disease_name = "-"
        disease_mesh_html = html.escape(disease_mesh)
        disease_name_html = html.escape(disease_name)
        disease_html = (f'<a href="https://meshb.nlm.nih.gov/record/ui?ui={disease_non_prefix_mesh}">'
                        f'[{disease_mesh_html}]</a><br />{disease_name_html}')

        # pmid html
        ann_html_list = []

        for pmid_list in ann_to_pmidlist:
            pmids = len(pmid_list)
            pmid_list = pmid_list[:top_k]
            pmid_html_list = []

            for pmid in pmid_list:
                meta = kb_meta.get_meta_by_pmid(pmid)

                title = meta.get("title", "")
                if title and title[-1] not in [".", "?", "!"]:
                    title = title + "."
                title_html = html.escape(title)
                title_html = f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">[{html.escape(pmid)}]</a> {title_html}'

                year = meta.get("year", "")
                if year:
                    year = year + "."
                year = html.escape(year)

                journal = meta.get("journal", "")
                if journal and journal[-1] not in [".", "?", "!"]:
                    journal = journal + "."
                journal_html = html.escape(journal)
                journal_html = f"<em>{journal_html}</em>"

                citation = meta.get("citation", 0)
                citation_html = html.escape(f"Cited by {citation}")

                pmid_html = f"{title_html} {year} {journal_html} {citation_html}."
                pmid_html_list.append(pmid_html)

            ann_html = f"({pmids:,} PMIDs in total){large_break}" + large_break.join(pmid_html_list)
            ann_html_list.append(ann_html)

        disease_table_html += (f"<tr>"
                               f"<td>{disease_html}</td>"
                               f"<td>{ann_html_list[0]}</td>"
                               f"<td>{ann_html_list[1]}</td>"
                               f"</tr>")
    disease_table_html += "</table>"

    result_html = chemical_html + "<br />" + disease_table_html
    response = {"result": result_html}
    return json.dumps(response)


class Arg:
    def __init__(self):
        with open("server_config.json", "r", encoding="utf8") as f:
            raw_arg = json.load(f)

        self.nen_dir = raw_arg.get("nen_dir")
        self.meta_dir = raw_arg.get("meta_dir")
        self.paper_dir = raw_arg.get("paper_dir")
        self.gene_dir = raw_arg.get("gene_dir")
        self.variant_dir = raw_arg.get("variant_dir")
        self.variant_nen_dir = raw_arg.get("variant_nen_dir")
        self.glof_dir = raw_arg.get("glof_dir")
        self.gvd_score_dir = raw_arg.get("gvd_score_dir")
        self.gd_score_file = raw_arg.get("gd_score_file")
        self.gd_db_dir = raw_arg.get("gd_db_dir")
        self.mesh_disease_dir = raw_arg.get("mesh_disease_dir")
        self.chemical_nen_dir = raw_arg.get("chemical_nen_dir")
        self.chemical_disease_dir = raw_arg.get("chemical_disease_dir")
        self.retriv_dir = raw_arg.get("retriv_dir")
        self.kb_type = raw_arg.get("kb_type")
        self.kb_dir = raw_arg.get("kb_dir")
        self.show_aid = raw_arg.get("show_aid", "false")
        return


def main():
    arg = Arg()
    for key, value in vars(arg).items():
        if value is not None:
            logger.info(f"[{key}] {value}")

    if arg.nen_dir:
        global nen
        nen = NEN(arg.nen_dir)

    if arg.meta_dir:
        global kb_meta
        kb_meta = Meta(arg.meta_dir)

    if arg.paper_dir:
        global paper_nen
        paper_nen = PaperKB(arg.paper_dir)

    if arg.gene_dir and arg.variant_dir:
        global v2g
        v2g = V2G(arg.variant_dir, arg.gene_dir)

    if arg.gene_dir:
        global ncbi_gene
        ncbi_gene = NCBIGene(arg.gene_dir)

    if arg.variant_nen_dir:
        global variant_nen
        variant_nen = VariantNEN(arg.variant_nen_dir)

    if arg.glof_dir:
        global paper_glof, entity_glof
        paper_glof = PaperKB(arg.glof_dir)
        entity_glof = GeVarToGLOF(arg.glof_dir)

    if arg.kb_dir and arg.kb_type:
        global kb, kb_type
        kb = KB(arg.kb_dir)
        kb.load_data()
        kb.load_index()
        kb_type = arg.kb_type

    if arg.gvd_score_dir:
        global gvd_score
        gvd_score = GVDScore(arg.gvd_score_dir)

    if arg.gd_score_file:
        global gd_score
        gd_score = GDScore(arg.gd_score_file)

    if arg.gd_db_dir:
        global gd_db
        gd_db = GVDScore(arg.gd_db_dir, type_list=("gdas", "dgas"))

    if arg.gvd_score_dir and arg.gd_db_dir and arg.gene_dir:
        global disease_to_gene
        disease_to_gene = DiseaseToGene(gd_score, gd_db)

    if arg.mesh_disease_dir:
        global mesh_name_kb, mesh_graph
        mesh_name_kb = MESHNameKB(arg.mesh_disease_dir)
        mesh_graph = MESHGraph(arg.mesh_disease_dir)

    if arg.chemical_nen_dir:
        global mesh_chemical
        mesh_chemical = MESHChemical(arg.chemical_nen_dir)

    if arg.chemical_disease_dir:
        global chemical_disease_kb
        chemical_disease_kb = ChemicalDiseaseKB(arg.chemical_disease_dir)

    if arg.retriv_dir:
        global qa
        qa = QA(arg.retriv_dir)

    global show_aid
    show_aid = arg.show_aid == "true"

    return


if __name__ == "server":
    main()

elif __name__ == "__main__":
    main()
    app.run(host="0.0.0.0", port=12345)
    sys.exit()
