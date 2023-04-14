import os
import csv
import sys
import json
import difflib
import logging
import argparse
import unicodedata
from collections import defaultdict

import requests

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
ner_gvdc_mapping = {
    "Gene": "gene",
    "Disease": "disease",
    "Chemical": "drug",
    "ProteinMutation": "mutation",
    "DNAMutation": "mutation",
    "SNP": "mutation",
    "DNAAcidChange": "mutation",
    "CopyNumberVariant": "mutation",
    "Mutation": "mutation",
}
entity_type_to_real_type_mapping = {
    "VARIANT": [
        "ProteinMutation",
        "DNAMutation",
        "SNP",
        "DNAAcidChange",
        "CopyNumberVariant",
        "Mutation",
    ],
}


def read_lines(file, line_by_line=False, write_log=True):
    if write_log:
        logger.info(f"Reading {file}")

    with open(file, "r", encoding="utf8") as f:
        if line_by_line:
            line_list = [line[:-1] for line in f]
        else:
            line_list = f.read().splitlines()

    if write_log:
        lines = len(line_list)
        logger.info(f"Read {lines:,} lines")
    return line_list


def read_json(file, is_jsonl=False, write_log=True):
    if write_log:
        logger.info(f"Reading {file}")

    with open(file, "r", encoding="utf8") as f:
        if is_jsonl:
            data = []
            for line in f:
                datum = json.loads(line[:-1])
                data.append(datum)
        else:
            data = json.load(f)

    if write_log:
        objects = len(data)
        logger.info(f"Read {objects:,} objects")
    return data


def read_csv(file, dialect, write_log=True):
    if write_log:
        logger.info(f"Reading {file}")

    with open(file, "r", encoding="utf8", newline="") as f:
        reader = csv.reader(f, dialect=dialect)
        row_list = [row for row in reader]

    if write_log:
        rows = len(row_list)
        logger.info(f"Read {rows:,} rows")
    return row_list


def intersection_of_key_to_set(dict_list):
    if len(dict_list) <= 1:
        return dict_list[0]

    dict_list = sorted(dict_list, key=lambda d: len(d))
    smallest_dict, other_dict_list = dict_list[0], dict_list[1:]
    del dict_list

    key_to_value_set = {}
    for key, value_set in smallest_dict.items():
        if any(
            key not in other_dict
            for other_dict in other_dict_list
        ):
            continue

        value_set = set(
            value
            for value in value_set
            if all(
                value in other_dict[key]
                for other_dict in other_dict_list
            )
        )

        if value_set:
            key_to_value_set[key] = value_set

    return key_to_value_set


def union_of_key_to_set(dict_list):
    if len(dict_list) <= 1:
        return dict_list[0]

    key_set = set(
        key
        for key_to_value_set in dict_list
        for key in key_to_value_set
    )

    key_to_value_set = {
        key: set(
            value
            for key_to_value_set in dict_list
            for value in key_to_value_set.get(key, set())
        )
        for key in key_set
    }
    return key_to_value_set


def query_variant(query):
    response = requests.get(
        "https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/autocomplete/",
        params={"query": query},
    )
    result_list = response.json()
    variant_list = []

    for result in result_list:
        id_list = []
        if "rsid" in result:
            id_list.append("RS#:" + result["rsid"][2:])
        if "hgvs" in result:
            id_list.append("HGVS:" + result["hgvs"])

        name_list = [result["name"]]
        if "match" in result:
            match = result["match"]
            prefix = "<m>"
            suffix = "</m>"
            i = match.find(prefix) + len(prefix)
            j = match.find(suffix, i)
            match = match[i:j]
            if match != name_list[0]:
                name_list.append(match)

        gene_list = result.get("gene", [])

        variant = (id_list, name_list, gene_list)
        variant_list.append(variant)

    return variant_list


def filter_frequency(name_to_frequency, ratio=0):
    if not name_to_frequency:
        return name_to_frequency

    result = {}
    threshold = 0

    for name, frequency in name_to_frequency.items():
        if not result:
            result[name] = frequency
            threshold = frequency * ratio
            continue
        if frequency < threshold:
            break
        result[name] = frequency

    return result


class NEN:
    def __init__(self, data_file):
        self.type_id_name_frequency = defaultdict(lambda: defaultdict(lambda: {}))
        self.name_type_id = defaultdict(lambda: defaultdict(lambda: []))
        self.length_name = defaultdict(lambda: set())

        if data_file:
            logger.info(f"Reading {data_file}")
            with open(data_file, "r", encoding="utf8", newline="") as f:
                reader = csv.reader(f, dialect="csv")
                _header = next(reader)
                tuples = 0
                for _type, _id, name, frequency in reader:
                    self.type_id_name_frequency[_type][_id][name] = int(frequency)
                    self.name_type_id[name][_type].append(_id)
                    self.length_name[len(name)].add(name)
                    tuples += 1
                logger.info(f"Read {tuples:,} tuples")
        return

    def get_names_by_query(self, query, case_sensitive=False, max_length_diff=1, min_similarity=0.85, max_names=20):
        length = len(query)
        length_min = max(1, length - max_length_diff)
        length_max = length + max_length_diff
        name_to_similarity = {}

        if case_sensitive:
            matcher = difflib.SequenceMatcher(a=query, autojunk=False)
        else:
            matcher = difflib.SequenceMatcher(a=query.lower(), autojunk=False)

        for name_length in range(length_min, length_max + 1):
            logger.info(f"[{query}]: searching names with length {name_length}/[{length_min}-{length_max}] ...")
            for name in self.length_name.get(name_length, []):
                if case_sensitive:
                    matcher.set_seq2(name)
                else:
                    matcher.set_seq2(name.lower())
                similarity = matcher.ratio()
                if similarity >= min_similarity:
                    name_to_similarity[name] = similarity

        name_similarity_list = sorted(name_to_similarity.items(), key=lambda x: (x[0] == query, x[1]), reverse=True)
        name_similarity_list = name_similarity_list[:max_names]
        return name_similarity_list

    def get_ids_by_name(self, name):
        type_id_frequency_list = [
            [_type, _id, self.type_id_name_frequency[_type][_id][name]]
            for _type, id_list in self.name_type_id.get(name, {}).items()
            for _id in id_list
        ]
        type_id_frequency_list = sorted(type_id_frequency_list, key=lambda x: x[2], reverse=True)
        return type_id_frequency_list

    def get_aliases_by_id(self, _type, _id, max_aliases=20):
        alias_frequency_list = [
            [alias, frequency]
            for alias, frequency in self.type_id_name_frequency.get(_type, {}).get(_id, {}).items()
        ]
        alias_frequency_list = sorted(alias_frequency_list, key=lambda x: x[1], reverse=True)
        alias_frequency_list = alias_frequency_list[:max_aliases]
        return alias_frequency_list

    def get_variant_in_kb(self, id_list, name_list):
        type_id_name_frequency = []

        for _type in entity_type_to_real_type_mapping["VARIANT"]:
            for _id in id_list:
                for name in name_list:
                    frequency = self.type_id_name_frequency.get(_type, {}).get(_id, {}).get(name, None)
                    if frequency is not None:
                        type_id_name_frequency.append((_type, _id, name, frequency))

        type_id_name_frequency = sorted(type_id_name_frequency, key=lambda tidf: tidf[3], reverse=True)
        return type_id_name_frequency


class V2G:
    def __init__(self, variant_dir, gene_dir):
        if variant_dir:
            self.hgvs_frequency = read_json(os.path.join(variant_dir, "hgvs_frequency.json"))
            self.rs_frequency = read_json(os.path.join(variant_dir, "rs_frequency.json"))
            # self.geneid_frequency = read_json(os.path.join(variant_dir, "gene_frequency.json"))

            self.hgvs_rs_frequency = read_json(os.path.join(variant_dir, "hgvs_rs_frequency.json"))
            self.rs_hgvs_frequency = read_json(os.path.join(variant_dir, "rs_hgvs_frequency.json"))

            self.hgvs_geneid_frequency = read_json(os.path.join(variant_dir, "hgvs_gene_frequency.json"))
            self.geneid_hgvs_frequency = read_json(os.path.join(variant_dir, "gene_hgvs_frequency.json"))

            self.rs_geneid_frequency = read_json(os.path.join(variant_dir, "rs_gene_frequency.json"))
            self.geneid_rs_frequency = read_json(os.path.join(variant_dir, "gene_rs_frequency.json"))

        if gene_dir:
            self.gene_geneid_frequency = read_json(os.path.join(gene_dir, "gene_id_frequency.json"))
            self.geneid_gene_frequency = read_json(os.path.join(gene_dir, "id_gene_frequency.json"))
        return

    def query(self, query):
        if query.startswith("HGVS:"):
            hgvs_frequency, rs_frequency, gene_frequency = self.query_hgvs(query)
        elif query.startswith("RS#:"):
            hgvs_frequency, rs_frequency, gene_frequency = self.query_rs(query)
        else:
            hgvs_frequency, rs_frequency, gene_frequency = self.query_gene(query)
        return hgvs_frequency, rs_frequency, gene_frequency

    def query_hgvs(self, hgvs):
        hgvs_frequency = {hgvs: self.hgvs_frequency.get(hgvs, 0)}
        rs_frequency = self.hgvs_rs_frequency.get(hgvs, {})
        gene_frequency = {}
        for geneid, frequency in self.hgvs_geneid_frequency.get(hgvs, {}).items():
            for gene, _ in self.geneid_gene_frequency.get(geneid, {}).items():
                if gene not in gene_frequency:
                    gene_frequency[gene] = frequency
                break

        hgvs_frequency = filter_frequency(hgvs_frequency)
        rs_frequency = filter_frequency(rs_frequency)
        gene_frequency = filter_frequency(gene_frequency)
        return hgvs_frequency, rs_frequency, gene_frequency

    def query_rs(self, rs):
        hgvs_frequency = self.rs_hgvs_frequency.get(rs, {})
        rs_frequency = {rs: self.rs_frequency.get(rs, 0)}
        gene_frequency = {}
        for geneid, frequency in self.rs_geneid_frequency.get(rs, {}).items():
            for gene, _ in self.geneid_gene_frequency.get(geneid, {}).items():
                if gene not in gene_frequency:
                    gene_frequency[gene] = frequency
                break

        hgvs_frequency = filter_frequency(hgvs_frequency)
        rs_frequency = filter_frequency(rs_frequency)
        gene_frequency = filter_frequency(gene_frequency)
        return hgvs_frequency, rs_frequency, gene_frequency

    def query_gene(self, gene):
        geneid = ""
        frequency = 0
        for geneid, frequency in self.gene_geneid_frequency.get(gene, {}).items():
            break

        if not geneid:
            hgvs_frequency = {}
            rs_frequency = {}
        else:
            hgvs_frequency = self.geneid_hgvs_frequency.get(geneid, {})
            rs_frequency = self.geneid_rs_frequency.get(geneid, {})

        gene_frequency = {gene: frequency}

        hgvs_frequency = filter_frequency(hgvs_frequency)
        rs_frequency = filter_frequency(rs_frequency)
        gene_frequency = filter_frequency(gene_frequency)
        return hgvs_frequency, rs_frequency, gene_frequency


class KB:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.nen = NEN(None)
        self.data = {}
        self.key = {}
        self.value = {}
        return

    def load_nen(self):
        nen_file = os.path.join(self.data_dir, "nen.csv")
        self.nen = NEN(nen_file)
        return

    def load_data(self, data_type=("sentence", "annotation")):
        for name in data_type:
            file = os.path.join(self.data_dir, f"{name}.jsonl")
            self.data[name] = open(file, "r", encoding="utf8")
        return

    def load_index(self, index_type=("pmid", "type_id", "type_name")):
        for name in index_type:
            value_file = os.path.join(self.data_dir, f"{name}_value.jsonl")
            self.value[name] = open(value_file, "r", encoding="utf8")

            key_file = os.path.join(self.data_dir, f"{name}_key.jsonl")
            logger.info(f"Reading {key_file}")
            self.key[name] = {}

            with open(key_file, "r", encoding="utf8") as f:
                if name == "pmid":
                    for line in f:
                        key, value_offset = json.loads(line[:-1])
                        self.key[name][key] = value_offset
                else:
                    for line in f:
                        key, value_offset = json.loads(line[:-1])
                        self.key[name][tuple(key)] = value_offset

            keys = len(self.key[name])
            logger.info(f"Read {keys:,} keys")
        return

    def get_sentence(self, sentence_file_offset):
        """

        :param sentence_file_offset: int
        :return: [sentence_index: int, sentence: str, mention_list: list]
            mention: [name: str, type: str, id_list: list, start_position_in_sentence: int]
        """
        self.data["sentence"].seek(sentence_file_offset)
        sentence = self.data["sentence"].readline()[:-1]
        sentence = json.loads(sentence)
        return sentence

    def get_annotation(self, annotation_file_offset):
        """

        :param annotation_file_offset: int
        :return: [
            sentence_file_offset: int,
            h_list: list[int],
            t_list: list[int],
            annotator: str,
            annotation: dict,
        ]
        """
        self.data["annotation"].seek(annotation_file_offset)
        annotation = self.data["annotation"].readline()[:-1]
        annotation = json.loads(annotation)
        return annotation

    def query_annotation_list_by_pmid(self, pmid):
        """

        :param pmid: str
        :return: [(annotation_file_offset, annotation_score), ...]
        """
        value_offset = self.key["pmid"].get(pmid, None)
        if value_offset is None:
            return []

        self.value["pmid"].seek(value_offset)
        ann_list = self.value["pmid"].readline()[:-1]
        ann_list = json.loads(ann_list)
        return ann_list

    def query_ht_pmid_annlist_by_type_idname(self, idname, key):
        """

        :param idname: "type_id" / "type_name"
        :param key: (_type, id/name)
        :return: {
            "head": ...
            "tail": {
                pmid: [(annotation_file_offset, annotation_score), ...],
                ...
            }
        }
        """
        value_offset = self.key[idname].get(key, None)
        if value_offset is None:
            return {"head": {}, "tail": {}}

        self.value[idname].seek(value_offset)
        ht_pmid_ann = self.value[idname].readline()[:-1]
        ht_pmid_ann = json.loads(ht_pmid_ann)
        return ht_pmid_ann

    def query_ht_pmid_annset_by_entity(self, entity_spec, pmid, idname_key_ht_pmid_ann=None):
        """

        :param entity_spec: (
            "OR",
            ("type_id", ("VARIANT", "RS#:113488022")),
            (
                "AND",
                ("type_id", ("ProteinMutation", "HGVS:p.V600E")),
                ("type_id", ("CorrespondingGene", "673")),
            ),
        )
        :param pmid: None / "35246262"
        :param idname_key_ht_pmid_ann: "type_id"/"type_name" -> (type, id/name) -> "head"/"tail" -> pmid -> ann_list
            ann_list: [(annotation_file_offset, annotation_score), ...]
        :return: "head"/"tail" -> pmid -> ann_set
        """
        # shared storage to avoid repeated self.query_annotation_by_type_idname()
        if idname_key_ht_pmid_ann is None:
            idname_key_ht_pmid_ann = {
                idname: {}
                for idname in ["type_id", "type_name"]
            }

        op, arg = entity_spec

        if op in ["AND", "OR"]:
            ht_to_list_of_pmid_ann = {"head": [], "tail": []}
            for sub_entity_spec in arg:
                ht_pmid_ann = self.query_ht_pmid_annset_by_entity(sub_entity_spec, pmid, idname_key_ht_pmid_ann)
                for ht, pmid_to_ann in ht_pmid_ann.items():
                    ht_to_list_of_pmid_ann[ht].append(pmid_to_ann)
                if op == "AND" and not ht_pmid_ann["head"] and not ht_pmid_ann["tail"]:
                    break  # early stop when the intersection is already sure be empty

            if op == "AND":
                merge_function = intersection_of_key_to_set
            else:
                merge_function = union_of_key_to_set

            ht_pmid_ann = {
                ht: merge_function(list_of_pmid_ann)
                for ht, list_of_pmid_ann in ht_to_list_of_pmid_ann.items()
            }
            return ht_pmid_ann

        elif op in ["type_id", "type_name"]:
            idname = op
            _type, idname_key = arg
            real_type_list = entity_type_to_real_type_mapping.get(_type, [_type])

            if len(real_type_list) > 1:
                expanded_entity_spec = ("OR", (
                    (idname, (real_type, idname_key))
                    for real_type in real_type_list
                ))
                return self.query_ht_pmid_annset_by_entity(expanded_entity_spec, pmid, idname_key_ht_pmid_ann)

            else:
                _type = real_type_list[0]
                key = (_type, idname_key)

                if key in idname_key_ht_pmid_ann[idname]:
                    # use result cached in shared storage
                    ht_pmid_ann = idname_key_ht_pmid_ann[idname][key]
                else:
                    # query type_id/name, filter by pmid, and then save to shared storage
                    ht_pmid_ann = self.query_ht_pmid_annlist_by_type_idname(idname, key)
                    if pmid:
                        ht_single_pmid_ann = {}
                        for ht, pmid_to_ann in ht_pmid_ann.items():
                            if pmid in pmid_to_ann:
                                ht_single_pmid_ann[ht] = {pmid: pmid_to_ann[pmid]}
                            else:
                                ht_single_pmid_ann[ht] = {}
                        ht_pmid_ann = ht_single_pmid_ann
                    idname_key_ht_pmid_ann[idname][key] = ht_pmid_ann

                # make ann_set from ann_list
                ht_pmid_ann = {
                    ht: {
                        pmid: set(tuple(ann) for ann in ann_list)
                        for pmid, ann_list in pmid_to_ann.items()
                    }
                    for ht, pmid_to_ann in ht_pmid_ann.items()
                }
                return ht_pmid_ann

        else:
            assert False

    def query_pmid_to_annotation_list(self, e1_spec, e2_spec, pmid):
        """

        :param e1_spec: ...
        :param e2_spec: None / (
            "OR",
            ("type_id", ("VARIANT", "RS#:113488022")),
            (
                "AND",
                ("type_id", ("ProteinMutation", "HGVS:p.V600E")),
                ("type_id", ("CorrespondingGene", "673")),
            ),
        )
        :param pmid: None / str
        :return: [
            pmid: [(annotation_file_offset, annotation_score), ...],
            ...
        ]
        """

        if e1_spec and e2_spec:
            e1_ht_pmid_annset = self.query_ht_pmid_annset_by_entity(e1_spec, pmid)
            e2_ht_pmid_annset = self.query_ht_pmid_annset_by_entity(e2_spec, pmid)

            h1t2_pmid_annset = intersection_of_key_to_set([
                e1_ht_pmid_annset["head"], e2_ht_pmid_annset["tail"],
            ])
            h2t1_pmid_annset = intersection_of_key_to_set([
                e1_ht_pmid_annset["tail"], e2_ht_pmid_annset["head"],
            ])
            del e1_ht_pmid_annset, e2_ht_pmid_annset

            pmid_to_ann = union_of_key_to_set([h1t2_pmid_annset, h2t1_pmid_annset])
            del h1t2_pmid_annset, h2t1_pmid_annset
            pmid_to_ann = {
                pmid: sorted(ann_set)
                for pmid, ann_set in pmid_to_ann.items()
            }

        elif e1_spec or e2_spec:
            entity_spec = e1_spec if e1_spec else e2_spec
            ht_pmid_annset = self.query_ht_pmid_annset_by_entity(entity_spec, pmid)
            pmid_to_ann = union_of_key_to_set([ht_pmid_annset["head"], ht_pmid_annset["tail"]])
            pmid_to_ann = {
                pmid: sorted(ann_set)
                for pmid, ann_set in pmid_to_ann.items()
            }

        else:
            pmid_to_ann = {pmid: self.query_annotation_list_by_pmid(pmid)}

        return pmid_to_ann


class PaperKB:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.pmid_to_offset = {}
        self.data_file = None

        if data_dir:
            self.load_data()
        return

    def load_data(self):
        data_file = os.path.join(self.data_dir, f"pmid_value.jsonl")
        self.data_file = open(data_file, "r", encoding="utf8")

        key_file = os.path.join(self.data_dir, f"pmid_key.jsonl")
        logger.info(f"Reading {key_file}")
        self.pmid_to_offset = {}

        with open(key_file, "r", encoding="utf8") as f:
            for line in f:
                key, value_offset = json.loads(line[:-1])
                self.pmid_to_offset[key] = value_offset

        papers = len(self.pmid_to_offset)
        logger.info(f"Read {papers:,} papers")
        return

    def query_data(self, pmid):
        try:
            offset = self.pmid_to_offset[pmid]
        except KeyError:
            return {
                "pmid": pmid,
                "title": "",
                "abstract": "",
                "sentence_list": [],
            }

        self.data_file.seek(offset)
        paper_datum = self.data_file.readline()[:-1]
        paper_datum = json.loads(paper_datum)
        return paper_datum


class GeVarToGLOF:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.type_key_offset = {}
        self.type_to_value_file = {}
        self.type_list = ["Gene", "VARIANT"]

        if data_dir:
            self.load_data()
        return

    def load_data(self):
        for _type in self.type_list:
            value_file = os.path.join(self.data_dir, f"{_type}_value.jsonl")
            self.type_to_value_file[_type] = open(value_file, "r", encoding="utf8")

            key_file = os.path.join(self.data_dir, f"{_type}_key.jsonl")
            logger.info(f"Reading {key_file}")
            self.type_key_offset[_type] = {}

            with open(key_file, "r", encoding="utf8") as f:
                for line in f:
                    key, value_offset = json.loads(line[:-1])
                    self.type_key_offset[_type][key] = value_offset

            keys = len(self.type_key_offset[_type])
            logger.info(f"Read {keys:,} {_type} keys")
        return

    def query_data(self, _type, key):
        try:
            offset = self.type_key_offset[_type][key]
        except KeyError:
            return {"gof": [], "lof": []}

        value_file = self.type_to_value_file[_type]
        value_file.seek(offset)
        value = value_file.readline()[:-1]
        value = json.loads(value)
        return value


def get_normalized_journal_name(name):
    name = unicodedata.normalize("NFKC", name)
    name = name.lower()
    term_list = []
    for c in name:
        if c.isalnum() or c == " ":
            term_list.append(c)
        elif c == "&":
            term_list.append(" and ")
        else:
            term_list.append(" ")
    name = "".join(term_list)
    name = " ".join(name.split())
    return name


class Meta:
    def __init__(self, meta_dir):
        self.meta_file = None
        self.pmid_to_meta_offset = {}
        self.pmid_to_cites = {}
        self.journal_to_impact = {}

        if not meta_dir:
            return

        meta_file = os.path.join(meta_dir, "meta.jsonl")
        self.meta_file = open(meta_file, "r", encoding="utf8")

        pmid_to_meta_offset_file = os.path.join(meta_dir, "pmid_to_meta_offset.json")
        self.pmid_to_meta_offset = read_json(pmid_to_meta_offset_file)

        pmid_to_citation_file = os.path.join(meta_dir, "pmid_to_citation.json")
        self.pmid_to_citation = read_json(pmid_to_citation_file)

        journal_impact_file = os.path.join(meta_dir, "journal_impact.csv")
        journal_impact_data = read_csv(journal_impact_file, "csv")
        assert journal_impact_data[0] == [
            "journal", "articles", "match_ratio", "match_substring", "match_journal", "match_impact",
        ]
        journal_impact_data = journal_impact_data[1:]
        self.journal_to_impact = {}
        for journal, _articles, match_ratio, match_substring, _match_journal, match_impact in journal_impact_data:
            match_ratio = int(match_ratio[:-1])
            if match_ratio >= 70 or match_substring == "True":
                self.journal_to_impact[journal] = match_impact
        return

    def get_meta_by_pmid(self, pmid):
        pmid = str(pmid)

        offset = self.pmid_to_meta_offset.get(pmid)
        if offset is None:
            meta = {
                "title": "",
                "author": "",
                "year": "",
                "journal": "",
            }
        else:
            self.meta_file.seek(offset)
            meta = self.meta_file.readline()[:-1]
            meta = json.loads(meta)

        meta["citation"] = self.pmid_to_citation.get(pmid, 0)

        journal = get_normalized_journal_name(meta["journal"])
        meta["journal_impact"] = self.journal_to_impact.get(journal, "")
        return meta


def test_nen(kb_dir):
    kb = KB(kb_dir)
    kb.load_nen()

    # variant query
    variant_list = query_variant("val600g")

    for id_list, name_list, gene_list in variant_list:
        logger.info(f"{id_list} {name_list}")

        type_id_name_frequency_list = kb.nen.get_variant_in_kb(id_list, name_list)
        for _type, _id, name, frequency in type_id_name_frequency_list:
            logger.info(f"-> in KB: {_type} {_id} {name} {frequency}")

    # other query
    query = "Metformin"
    logger.info(f"query: {query}")

    name_similarity_list = kb.nen.get_names_by_query(
        query, case_sensitive=False, max_length_diff=1, min_similarity=0.85, max_names=10,
    )
    names = len(name_similarity_list)
    logger.info(f"{names:,} names")

    for name, similarity in name_similarity_list:
        logger.info(f"name: {name}, similarity: {similarity}")
        type_id_frequency_list = kb.nen.get_ids_by_name(name)
        ids = len(type_id_frequency_list)
        logger.info(f"ids: {ids}")

        for _type, _id, id_frequency in type_id_frequency_list:
            alias_frequency_list = kb.nen.get_aliases_by_id(_type, _id, max_aliases=5)
            logger.info(f"({_type}, {_id}, {name}, {id_frequency}): alias_list={alias_frequency_list}")

    return


def test_v2g(variant_dir, gene_dir):
    v2g = V2G(variant_dir, gene_dir)

    def show_dict(name_to_frequency):
        for name, frequency in name_to_frequency.items():
            logger.info(f"{frequency:>6,} {name}")
        return

    query_list = [
        "HGVS:p.V600E",
        "RS#:113488022",
        "BRAF",
    ]

    for query in query_list:
        logger.info("----------")
        logger.info(f"[{query}]")
        hgvs_to_frequency, rs_to_frequency, gene_to_frequency = v2g.query(query)
        show_dict(hgvs_to_frequency)
        show_dict(rs_to_frequency)
        show_dict(gene_to_frequency)
    return


def test_kb(kb_dir):
    kb = KB(kb_dir)
    kb.load_data()
    kb.load_index()

    """
    query_list = [
        [
            ["type_id", ["VARIANT", "HGVS:p.V600E"]],
            None,
            "35246262",
        ],
        [
            None,
            ["type_name", ["Disease", "tumor"]],
            "35246262",
        ],
        (
            ["AND", [
                ["type_id", ["Chemical", "MESH:D001639"]],
                ["type_name", ["Chemical", "bicarbonate"]],
            ]],
            ("AND", (
                ("type_id", ("Disease", "MESH:D000138")),
                ("type_name", ("Disease", "metabolic acidosis")),
            )),
            "35387196",
        ),
        (
            ("AND", (
                ("type_id", ("ProteinMutation", "HGVS:p.V600E")),
                ("type_id", ("ProteinMutation", "CorrespondingGene:673")),
            )),
            ("type_id", ("Disease", "MESH:D009369")),
            "35373151",
        ),
        (
            ("type_id", ("VARIANT", "RS#:113488022")),
            ("type_id", ("Disease", "MESH:D009369")),
            "35373151",
        ),
        (
            ("OR", (
                ("AND", (
                    ("type_id", ("ProteinMutation", "HGVS:p.V600E")),
                    ("type_id", ("ProteinMutation", "CorrespondingGene:673")),
                )),
                ("type_id", ("VARIANT", "RS#:113488022"))
            )),
            ("type_id", ("Disease", "MESH:D009369")),
            "35373151",
        ),
    ]
    """
    query_list = [
        (
            ("type_id", ("VARIANT", "HGVS:p.V600E")),
            ("type_id", ("Disease", "MESH:D009369")),
            "35373151",
        ),
        (
            ("type_id", ("VARIANT", "HGVS:c.1799T>A")),
            ("type_id", ("Disease", "MESH:D009369")),
            "35373151",
        ),
        (
            ("AND", (
                ("OR", (
                    ("type_id", ("VARIANT", "HGVS:p.V600E")),
                    ("type_id", ("VARIANT", "HGVS:c.1799T>A")),
                )),
                ("type_id", ("VARIANT", "CorrespondingGene:673"))
            )),
            ("type_id", ("Disease", "MESH:D009369")),
            "35373151",
        ),
    ]

    for e1_spec, e2_spec, pmid_spec in query_list:
        logger.info("=" * 100)
        logger.info(f"e1_spec={e1_spec}")
        logger.info(f"e2_spec={e2_spec}")
        logger.info(f"pmid_spec={pmid_spec}")

        pmid_to_ann = kb.query_pmid_to_annotation_list(e1_spec, e2_spec, pmid_spec)
        pmids = len(pmid_to_ann)
        annotations = sum(len(ann_list) for ann_list in pmid_to_ann.values())
        logger.info(f"{pmids:,} pmids; {annotations:,} annotations")

        pmid_to_relevance = {
            pmid: sum(ann_score for _ann_offset, ann_score in ann_list)
            for pmid, ann_list in pmid_to_ann.items()
        }
        pmid_list = sorted(pmid_to_ann, key=lambda pmid: pmid_to_relevance[pmid], reverse=True)

        for pmid in pmid_list:
            relevance = pmid_to_relevance[pmid]
            logger.info("-" * 100)
            logger.info(f"pmid={pmid} relevance={relevance:,}")
            for ann_offset, _ann_score in pmid_to_ann[pmid]:
                annotation = kb.get_annotation(ann_offset)
                sentence, mention_list = kb.get_sentence(annotation[0])
                logger.info(f"sentence   -> {sentence}")
                logger.info(f"mentions   -> {mention_list}")
                logger.info(f"annotation -> {annotation}")
                logger.info("")
        input("YOLO")
    return


def test_meta(meta_dir):
    kb_meta = Meta(meta_dir)

    pmid = "35267245"
    paper_meta = kb_meta.get_meta_by_pmid(pmid)

    for key, value in paper_meta.items():
        logger.info(f"[{key}] {value}")
    return


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--kb_dir", type=str, default="/volume/penghsuanli-genome2-nas2/pubtator_2023/kb/1_10")

    parser.add_argument("--variant_dir", type=str, default="/volume/penghsuanli-genome2-nas2/pubtator_2023/data/variant")
    parser.add_argument("--gene_dir", type=str, default="/volume/penghsuanli-genome2-nas2/pubtator_2023/data/gene")

    parser.add_argument("--meta_dir", type=str, default="/volume/penghsuanli-genome2-nas2/pubtator/data/meta")

    arg = parser.parse_args()
    for key, value in vars(arg).items():
        if value is not None:
            logger.info(f"[{key}] {value}")

    # test_nen(arg.kb_dir)
    # test_v2g(arg.variant_dir, arg.gene_dir)
    # test_kb(arg.kb_dir)
    # test_meta(arg.meta_dir)
    return


if __name__ == "__main__":
    main()
    sys.exit()
