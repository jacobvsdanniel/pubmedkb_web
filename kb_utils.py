import os
import csv
import sys
import html
import json
import heapq
import asyncio
import difflib
import logging
import argparse
import unicodedata
from collections import defaultdict

import requests
import retriv
from retriv import DenseRetriever

try:
    from gpt_utils import async_run_qa, run_qa, run_qa_stream, run_qka_stream, run_pqa_stream
except ModuleNotFoundError:
    pass

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(process)d - %(name)s - %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
    level=logging.INFO,
    force=True,
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


class DiskDict:
    def __init__(self, key_file, value_file, key_process=None):
        self.key_file = key_file
        self.value_file = value_file
        self.key_process = key_process
        self.key_to_offset = {}
        self.value_fp = None

        if key_file and value_file:
            self.load_data()
        return

    def load_data(self):
        self.value_fp = open(self.value_file, "r", encoding="utf8")

        logger.info(f"Reading {self.key_file}")
        self.key_to_offset = {}

        with open(self.key_file, "r", encoding="utf8") as f:
            for line in f:
                key, value_offset = json.loads(line)
                if self.key_process:
                    key = self.key_process(key)
                self.key_to_offset[key] = value_offset

        keys = len(self.key_to_offset)
        logger.info(f"Read {keys:,} keys")
        return

    def get(self, key, default_value=None):
        try:
            offset = self.key_to_offset[key]
        except KeyError:
            return default_value

        self.value_fp.seek(offset)
        value = self.value_fp.readline()
        value = json.loads(value)
        return value


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
    def __init__(self, data_dir):
        self.typeid_name_frequency = None
        self.typeid_to_most_frequent_name = None
        self.name_type_id_frequency = None
        self.length_name = None

        if data_dir:
            k_file = os.path.join(data_dir, "typeid_name_frequency_key.jsonl")
            v_file = os.path.join(data_dir, "typeid_name_frequency_value.jsonl")
            self.typeid_name_frequency = DiskDict(k_file, v_file)

            kv_file = os.path.join(data_dir, "typeid_to_most_frequent_name.json")
            self.typeid_to_most_frequent_name = read_json(kv_file)

            k_file = os.path.join(data_dir, "name_type_id_frequency_key.jsonl")
            v_file = os.path.join(data_dir, "name_type_id_frequency_value.jsonl")
            self.name_type_id_frequency = DiskDict(k_file, v_file)

            k_file = os.path.join(data_dir, "length_name_key.jsonl")
            v_file = os.path.join(data_dir, "length_name_value.jsonl")
            self.length_name = DiskDict(k_file, v_file)
        return

    def get_names_by_query(self, query, case_sensitive=False, max_length_diff=1, min_similarity=0.85, max_names=20):
        # exact match
        exact_match_list = [(query, 1.0)] if self.name_type_id_frequency.get(query) else []
        if len(exact_match_list) >= max_names:
            return exact_match_list
        max_non_exact_matches = max_names - len(exact_match_list)

        # set up matcher
        if min_similarity == 1:
            if case_sensitive:
                return exact_match_list
            else:
                matcher = query.lower()
        else:
            if case_sensitive:
                matcher = difflib.SequenceMatcher(a=query, autojunk=False)
            else:
                matcher = difflib.SequenceMatcher(a=query.lower(), autojunk=False)

        query_length = len(query)
        name_to_similarity = {}
        perfect_matches = 0

        for length_diff in range(max_length_diff + 1):
            sign_list = [0] if length_diff == 0 else [1, -1]

            for sign in sign_list:
                name_length = query_length + sign * length_diff
                if name_length < 1:
                    continue
                if sign == 0:
                    sign_string = ""
                elif sign == 1:
                    sign_string = f" ({query_length}+{length_diff})"
                else:
                    sign_string = f" ({query_length}-{length_diff})"
                logger.info(f"[{query}]: searching names with length {name_length}{sign_string} ...")

                for name in self.length_name.get(name_length, []):
                    # skip exact match
                    if name == query:
                        continue

                    # compute similarity
                    if min_similarity == 1:
                        # must be case-insensitive
                        similarity = 1 if name.lower() == matcher else 0
                    else:
                        if case_sensitive:
                            matcher.set_seq2(name)
                        else:
                            matcher.set_seq2(name.lower())
                        similarity = matcher.ratio()

                    if similarity >= min_similarity:
                        name_to_similarity[name] = similarity
                        if similarity == 1:
                            perfect_matches += 1
                            if perfect_matches >= max_non_exact_matches:
                                break
                if perfect_matches >= max_non_exact_matches:
                    break
            if perfect_matches >= max_non_exact_matches:
                break

        name_similarity_list = heapq.nlargest(max_non_exact_matches, name_to_similarity.items(), key=lambda x: x[1])
        name_similarity_list = exact_match_list + name_similarity_list
        return name_similarity_list

    def get_ids_by_name(self, name):
        type_id_frequency_list = [
            [_type, _id, frequency]
            for _type, id_to_frequency in self.name_type_id_frequency.get(name, {}).items()
            for _id, frequency in id_to_frequency.items()
        ]
        type_id_frequency_list = sorted(type_id_frequency_list, key=lambda x: x[2], reverse=True)
        return type_id_frequency_list

    def get_aliases_by_id(self, _type, _id, max_aliases=20):
        alias_frequency_list = [
            [alias, frequency]
            for alias, frequency in self.typeid_name_frequency.get(f"{_type}_{_id}", {}).items()
        ]
        alias_frequency_list = alias_frequency_list[:max_aliases]
        return alias_frequency_list

    def get_most_frequent_name_by_id(self, _type, _id):
        return self.typeid_to_most_frequent_name.get(f"{_type}_{_id}")

    def get_variant_in_kb(self, id_list, name_list):
        type_id_name_frequency = []

        for _type in entity_type_to_real_type_mapping["VARIANT"]:
            for _id in id_list:
                for name in name_list:
                    frequency = self.typeid_name_frequency.get(f"{_type}_{_id}", {}).get(name, None)
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


class NCBIGene:
    def __init__(self, gene_dir):
        self.id_to_name = {}
        self.name_to_id = {}
        self.alias_to_id = {}

        if gene_dir:
            ncbi_file = os.path.join(gene_dir, "ncbi_protein_gene.csv")
            ncbi_data = read_csv(ncbi_file, "csv")
            ncbi_header, ncbi_data = ncbi_data[0], ncbi_data[1:]
            assert ncbi_header == ["tax_id", "gene_id", "gene_name", "gene_alias"]
            alias_to_id = defaultdict(lambda: [])

            for _tax_id, gene_id, gene_name, gene_alias_list in ncbi_data:
                self.id_to_name[gene_id] = gene_name
                self.name_to_id[gene_name] = gene_id

                if gene_alias_list == "-":
                    continue
                for gene_alias in gene_alias_list.split("|"):
                    alias_to_id[gene_alias].append(gene_id)

            for alias, id_list in alias_to_id.items():
                if len(id_list) == 1:
                    self.alias_to_id[alias] = id_list[0]
        return


class Gene:
    def __init__(self, gene_id="", symbol="", tax_id="", taxon=""):
        self.gene_id = gene_id
        self.symbol = symbol
        self.tax_id = tax_id
        self.taxon = taxon
        return

    def get_json(self):
        return {
            "gene_id": self.gene_id,
            "symbol": self.symbol,
            "tax_id": self.tax_id,
            "taxon": self.taxon,
        }

    def get_html_anchor(self):
        if self.symbol:
            html_symbol = html.escape(self.symbol)
            if self.taxon:
                html_l = html.escape("[")
                html_r = html.escape("]")
                html_taxon = html.escape(self.taxon)
                html_result = (
                    f'<a href="https://www.ncbi.nlm.nih.gov/gene/{self.gene_id}">'
                    f'{html_symbol} {html_l} <i>{html_taxon}</i> {html_r}'
                    f'</a>'
                )
            else:
                html_result = (
                    f'<a href="https://www.ncbi.nlm.nih.gov/gene/{self.gene_id}">'
                    f'{html_symbol}'
                    f'</a>'
                )
        else:
            html_result = (
                f'<a href="https://www.ncbi.nlm.nih.gov/gene/{self.gene_id}">'
                f'GENE:{self.gene_id}'
                f'</a>'
            )
        return html_result


class NCBIGene2025:
    def __init__(self, gene_dir):
        self.geneid_to_taxid_symbol = {}
        self.taxid_to_name = {}

        if gene_dir:
            # gene data
            gene_file = os.path.join(gene_dir, "taxid_geneid_symbol.csv")
            logger.info(f"reading {gene_file}")
            with open(gene_file, "r", encoding="utf8", newline="") as f:
                reader = csv.reader(f, dialect="csv")
                header = next(reader)
                assert header == ["taxonomy_id", "gene_id", "gene_symbol"]
                for tax_id, gene_id, symbol in reader:
                    self.geneid_to_taxid_symbol[gene_id] = (tax_id, symbol)
            gene_ids = len(self.geneid_to_taxid_symbol)
            logger.info(f"read {gene_ids:,} gene_ids")

            # taxonomy data
            taxonomy_file = os.path.join(gene_dir, "taxid_taxon.csv")
            logger.info(f"reading {taxonomy_file}")
            with open(taxonomy_file, "r", encoding="utf8", newline="") as f:
                reader = csv.reader(f, dialect="csv")
                header = next(reader)
                assert header == ["taxonomy_id", "scientific_name"]
                for tax_id, name in reader:
                    self.taxid_to_name[tax_id] = name
            tax_ids = len(self.taxid_to_name)
            logger.info(f"read {tax_ids:,} tax_ids")
        return

    def query(self, gene_id):
        tax_id, symbol = self.geneid_to_taxid_symbol.get(gene_id, ("", ""))
        taxon = self.taxid_to_name.get(tax_id, "")
        return Gene(gene_id=gene_id, symbol=symbol, tax_id=tax_id, taxon=taxon)


class VariantNEN:
    def __init__(self, variant_dir):
        self.id_to_name = defaultdict(lambda: [])
        self.name_to_id = defaultdict(lambda: [])

        if variant_dir:
            # RS
            rs_file = os.path.join(variant_dir, f"rs.jsonl")
            rs_prefix = "RS#:"
            rs_prefix_len = len(rs_prefix)

            with open(rs_file, "r", encoding="utf8") as f:
                for line in f:
                    _id = json.loads(line)
                    name = "rs" + _id[rs_prefix_len:]
                    self.id_to_name[_id].append(name)
                    self.name_to_id[name].append(_id)

            # HGVS
            hgvs_file = os.path.join(variant_dir, f"hgvs.jsonl")
            with open(hgvs_file, "r", encoding="utf8") as f:
                for line in f:
                    _id, name_to_count = json.loads(line)
                    name_set = set()
                    for name in name_to_count:
                        name = name.lower()
                        if name in name_set:
                            continue
                        name_set.add(name)
                        self.id_to_name[_id].append(name)
                        self.name_to_id[name].append(_id)
        return


class KB:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.data = {}
        self.key = {}
        self.value = {}
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
        self.meta_dir = meta_dir
        self.pmid_to_meta = None
        self.journal_to_impact = None

        if meta_dir:
            self.load_data()
        return

    def load_data(self):
        # pmid_to_meta
        meta_key_file = os.path.join(self.meta_dir, "meta_key.jsonl")
        meta_value_file = os.path.join(self.meta_dir, "meta_value.jsonl")
        self.pmid_to_meta = DiskDict(meta_key_file, meta_value_file)

        # journal_to_impact
        self.journal_to_impact = {}
        journal_impact_file = os.path.join(self.meta_dir, "journal_impact.csv")
        with open(journal_impact_file, "r", encoding="utf8", newline="") as f:
            reader = csv.reader(f, dialect="csv")
            header = next(reader)
            assert header == [
                "journal", "articles", "match_ratio", "match_substring", "match_journal", "match_impact",
            ]
            for journal, _articles, match_ratio, match_substring, _match_journal, match_impact in reader:
                match_ratio = int(match_ratio[:-1])
                if match_ratio >= 70 or match_substring == "True":
                    self.journal_to_impact[journal] = match_impact
        return

    def get_meta_by_pmid(self, pmid):
        pmid = str(pmid)

        meta = self.pmid_to_meta.get(
            pmid,
            {
                "title": "", "author": "", "year": "", "journal": "",
                "doi": "", "publication_type_list": [], "citation": 0,
            },
        )

        journal = get_normalized_journal_name(meta["journal"])
        meta["journal_impact"] = self.journal_to_impact.get(journal, "")
        return meta


def get_paper_meta_html(pmid, meta):
    title = meta["title"]
    if title and title[-1] not in [".", "?", "!"]:
        title = title + "."
    title_html = html.escape(title)
    title_html = f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}">[{html.escape(pmid)}]</a> {title_html}'

    year = meta["year"]
    if year:
        year = year + "."
    year = html.escape(year)

    journal = meta["journal"]
    if journal and journal[-1] not in [".", "?", "!"]:
        journal = journal + "."
    journal_html = html.escape(journal)
    journal_html = f"<em>{journal_html}</em>"

    doi = meta["doi"]
    if doi:
        doi_html = html.escape(f"doi.org/{doi}")
        doi_html = f'<a href="https://doi.org/{doi}">{doi_html}</a>'
    else:
        doi_html = ""

    publication_type = meta["publication_type_list"]
    publication_type = ", ".join(html.escape(_type) for _type in publication_type)
    if publication_type:
        publication_type += "."

    citation = meta["citation"]
    citation_html = html.escape(f"Cited by {citation}.")

    paper_meta_html = f"{title_html} {year} {journal_html} {doi_html} {publication_type} {citation_html}"
    return paper_meta_html


class GVDScore:
    def __init__(self, data_dir, type_list=("gdas", "dgas", "vdas", "dvas")):
        self.data_dir = data_dir
        self.type_to_dict = {}
        self.type_list = type_list

        if data_dir:
            self.load_data()
        return

    def load_data(self):
        for _type in self.type_list:
            key_file = os.path.join(self.data_dir, f"{_type}_key.jsonl")
            value_file = os.path.join(self.data_dir, f"{_type}_value.jsonl")
            self.type_to_dict[_type] = DiskDict(key_file, value_file)
        return

    def query_data(self, _type, g, v, d):
        if _type == "gd":
            value = self.type_to_dict["gdas"].get(g, {}).get(d, {})
        elif _type == "vd":
            value = self.type_to_dict["vdas"].get(v, {}).get(d, {})
        elif _type == "g":
            value = self.type_to_dict["gdas"].get(g, {})
        elif _type == "v":
            value = self.type_to_dict["vdas"].get(v, {})
        elif _type == "d2g":
            value = self.type_to_dict["dgas"].get(d, {})
        elif _type == "d2v":
            value = self.type_to_dict["dvas"].get(d, {})
        else:
            assert False
        return value


class GDScore:
    def __init__(self, mesh_gene_score_file):
        self.mesh_gene_score_file = mesh_gene_score_file
        self.dgs = {}
        self.gds = {}

        if mesh_gene_score_file:
            self.load_data()
        return

    def load_data(self):
        self.dgs = defaultdict(lambda: {})
        self.gds = defaultdict(lambda: {})

        with open(self.mesh_gene_score_file, "r", encoding="utf8", newline="") as f:
            reader = csv.reader(f, dialect="csv")
            for mesh, gene, score in reader:
                score = int(score)
                self.dgs[mesh][gene] = score
                self.gds[gene][mesh] = score
        return

    def query_data(self, _type, g, d):
        if _type == "gd":
            value = self.dgs.get(d, {}).get(g, 0)
        elif _type == "g":
            value = self.gds.get(g, {})
        elif _type == "d":
            value = self.dgs.get(d, {})
        else:
            assert False
        return value


class DiseaseToGene:
    def __init__(self, pubmedkb_gd_score=None, db_gvd_score=None):
        self._group_to_score_range = [(1, 100), (101, 125)]
        self.max_raw_pubmedkbscore = 10000

        self.pubmedkb_gd_score = pubmedkb_gd_score
        self.db_gvd_score = db_gvd_score
        return

    def get_pubmedkb_score(self, mesh):
        gene_to_score = self.pubmedkb_gd_score.query_data("d", "", mesh)
        return gene_to_score

    def get_db_score(self, mesh):
        gene_ann_score = self.db_gvd_score.query_data("d2g", "", "", mesh)
        gene_to_score = {
            gene: sum(ann_to_score.values())
            for gene, ann_to_score in gene_ann_score.items()
        }
        return gene_to_score

    def get_score(self, mesh_to_disease_set, _disease_to_mesh_set):
        # normalize mesh ID format
        clean_mesh_to_disease_set = defaultdict(lambda: set())
        prefix = "MESH:"
        for mesh, disease_set in mesh_to_disease_set.items():
            if not mesh.startswith(prefix):
                mesh = prefix + mesh
            for disease in disease_set:
                clean_mesh_to_disease_set[mesh].add(disease)
        mesh_to_disease_set = clean_mesh_to_disease_set

        # calculate score for each <disease, gene> pair
        disease_gene_score = defaultdict(lambda: defaultdict(lambda: 0))
        gene_disease_score = defaultdict(lambda: defaultdict(lambda: 0))

        for mesh, disease_set in mesh_to_disease_set.items():
            gene_to_dbscore = self.get_db_score(mesh)
            gene_to_pubmedkbscore = self.get_pubmedkb_score(mesh)

            for gene in gene_to_dbscore.keys() | gene_to_pubmedkbscore.keys():
                # calculate <mesh, gene> score
                dbscore = gene_to_dbscore.get(gene, 0)
                if dbscore > 0:
                    dbscore = 100

                pubmedkbscore = gene_to_pubmedkbscore.get(gene, 0)
                pubmedkbscore = 100 * pubmedkbscore / self.max_raw_pubmedkbscore

                score = dbscore + pubmedkbscore

                # update <disease, gene> score by <mesh, gene> score
                for disease in disease_set:
                    disease_gene_score[disease][gene] = max(score, disease_gene_score[disease][gene])

        for disease, gene_to_score in disease_gene_score.items():
            for gene, score in gene_to_score.items():
                gene_disease_score[gene][disease] = score

        # sorted gene_score_list
        gene_to_score = {
            gene: max(disease_to_score.values())
            for gene, disease_to_score in gene_disease_score.items()
        }
        gene_score_list = sorted(gene_to_score.items(), key=lambda gs: -gs[1])
        del gene_to_score

        # sorted disease_to_gene_list
        disease_to_gene_list = {
            disease: sorted(gene_to_score, key=lambda g: -gene_to_score[g])
            for disease, gene_to_score in disease_gene_score.items()
        }

        return gene_score_list, disease_to_gene_list, gene_disease_score

    def _get_score(self, mesh_to_disease_set, disease_to_mesh_set):
        # normalize mesh ID format
        clean_mesh_to_disease_set = defaultdict(lambda: set())
        prefix = "MESH:"
        for mesh, disease_set in mesh_to_disease_set.items():
            if not mesh.startswith(prefix):
                mesh = prefix + mesh
            for disease in disease_set:
                clean_mesh_to_disease_set[mesh].add(disease)
        mesh_to_disease_set = clean_mesh_to_disease_set

        # collect pubmedkb score and db score for all diseases
        disease_gene_dbscore = defaultdict(lambda: defaultdict(lambda: 0))
        disease_gene_pubmedkbscore = defaultdict(lambda: defaultdict(lambda: 0))

        gene_to_dbscore = defaultdict(lambda: 0)
        gene_to_pubmedkbscore = defaultdict(lambda: 0)

        for mesh, disease_set in mesh_to_disease_set.items():
            sub_gene_to_dbscore = self.get_db_score(mesh)
            sub_gene_to_pubmedkbscore = self.get_pubmedkb_score(mesh)

            for gene, dbscore in sub_gene_to_dbscore.items():
                for disease in disease_set:
                    disease_gene_dbscore[disease][gene] += dbscore
                    disease_gene_pubmedkbscore[disease][gene] += 0
                gene_to_dbscore[gene] += dbscore
                gene_to_pubmedkbscore[gene] += 0

            for gene, pubmedkbscore in sub_gene_to_pubmedkbscore.items():
                for disease in disease_set:
                    disease_gene_pubmedkbscore[disease][gene] += pubmedkbscore
                gene_to_pubmedkbscore[gene] += pubmedkbscore

        # get per-disease score
        disease_gene_score = defaultdict(lambda: defaultdict(lambda: 0))
        for disease in disease_to_mesh_set:
            if not disease_gene_pubmedkbscore[disease]:
                continue

            max_pubmedkbscore = max(disease_gene_pubmedkbscore[disease].values())
            if max_pubmedkbscore == 0:
                max_pubmedkbscore = 1
            for gene, pubmedkbscore in disease_gene_pubmedkbscore[disease].items():
                disease_gene_score[disease][gene] += pubmedkbscore / max_pubmedkbscore

            for gene, dbscore in disease_gene_dbscore[disease].items():
                if dbscore > 0:
                    disease_gene_score[disease][gene] += 2

        disease_to_gene_list = {
            disease: sorted(gene_to_score, key=lambda g: -gene_to_score[g])
            for disease, gene_to_score in disease_gene_score.items()
        }
        del disease_gene_score

        # get all-disease-combined score
        gene_to_score = {}

        if gene_to_pubmedkbscore:
            max_pubmedkbscore = max(gene_to_pubmedkbscore.values())
            # max_pubmedkbscore = math.log(1 + max_pubmedkbscore)
            if max_pubmedkbscore == 0:
                max_pubmedkbscore = 1

            for gene, pubmedkbscore in gene_to_pubmedkbscore.items():
                # pubmedkbscore = math.log(1 + pubmedkbscore)
                dbscore = gene_to_dbscore[gene]
                group = 1 if dbscore > 0 else 0

                score_min, score_max = self._group_to_score_range[group]
                score_range = score_max - score_min
                score = score_min + score_range * pubmedkbscore / max_pubmedkbscore
                gene_to_score[gene] = score

        gene_score_list = sorted(gene_to_score.items(), key=lambda gs: -gs[1])
        del gene_to_score

        return gene_score_list, disease_to_gene_list


class MESHNameKB:
    def __init__(self, data_dir):
        self.data_dir = data_dir

        self.prefix = "MESH:"
        self.mesh_to_mesh_name = {}

        self.mesh_name_to_mesh = {}
        self.hpo_to_mesh = {}
        self.hpo_name_to_mesh = {}
        self.literature_name_to_mesh = {}

        if data_dir:
            self.load_data()
        return

    def load_mesh_data(self):
        descriptor_file = os.path.join(self.data_dir, "raw_json", "desc2023.jsonl")
        supplemental_file = os.path.join(self.data_dir, "raw_json", "supp2023_clean.jsonl")

        self.mesh_to_mesh_name = {}
        self.mesh_name_to_mesh = defaultdict(lambda: set())

        for name_file in [descriptor_file, supplemental_file]:
            with open(name_file, "r", encoding="utf8") as f:
                for line in f:
                    mesh, name, alias_list, _ = json.loads(line)
                    if not mesh.startswith(self.prefix):
                        mesh = self.prefix + mesh

                    self.mesh_to_mesh_name[mesh] = [name] + alias_list

                    self.mesh_name_to_mesh[name.lower()].add(mesh)
                    for alias in alias_list:
                        self.mesh_name_to_mesh[alias.lower()].add(mesh)
        return

    def load_hpo_data(self):
        hpo_file = os.path.join(self.data_dir, "hpo", "hpo_name_term_mesh.jsonl")

        self.hpo_to_mesh = defaultdict(lambda: set())
        self.hpo_name_to_mesh = defaultdict(lambda: set())

        with open(hpo_file, "r", encoding="utf8") as f:
            for line in f:
                hpo, name, alias_list, mesh_list = json.loads(line)

                for mesh in mesh_list:
                    if not mesh.startswith(self.prefix):
                        mesh = self.prefix + mesh
                    self.hpo_to_mesh[hpo].add(mesh)
                    self.hpo_name_to_mesh[name.lower()].add(mesh)
                    for alias in alias_list:
                        self.hpo_name_to_mesh[alias.lower()].add(mesh)
        return

    def load_literature_data(self):
        literature_file = os.path.join(self.data_dir, "literature", "mesh_name.jsonl")

        self.literature_name_to_mesh = defaultdict(lambda: set())

        with open(literature_file, "r", encoding="utf8") as f:
            for line in f:
                mesh, name_list = json.loads(line)
                if not mesh.startswith(self.prefix):
                    mesh = self.prefix + mesh
                for name in name_list:
                    self.literature_name_to_mesh[name.lower()].add(mesh)
        return

    def load_data(self):
        self.load_mesh_data()
        self.load_hpo_data()
        self.load_literature_data()
        return

    def get_mesh_name_by_mesh_id(self, mesh):
        if not mesh.startswith(self.prefix):
            mesh = self.prefix + mesh
        name_list = self.mesh_to_mesh_name.get(mesh, [])
        return name_list

    def get_mesh_id_by_all_source_name(self, name):
        name = name.lower()
        result_mesh_set = set()

        dictionary_list = [
            self.mesh_name_to_mesh,
            self.hpo_name_to_mesh,
            self.literature_name_to_mesh,
        ]

        for name_to_mesh_set in dictionary_list:
            mesh_set = name_to_mesh_set.get(name, set())
            for mesh in mesh_set:
                result_mesh_set.add(mesh)

        return result_mesh_set


class MESHNode:
    def __init__(self, graph_data, index):
        self.index = index
        datum = graph_data[index]

        if datum[0][0] == "D":
            self.is_supplemental = False
            self.mesh, self.display_name, self.parent_list, self.child_list, self.supplemental_list = datum
            self.descriptor_list = []

        else:
            self.is_supplemental = True
            self.mesh, self.display_name, self.descriptor_list = datum
            self.parent_list = []
            self.child_list = []
            self.supplemental_list = []

        self.label = ""
        return

    def get_dictionary(self):
        data = {
            "index": self.index,
            "is_supplemental": self.is_supplemental,
            "mesh": self.mesh,
            "display_name": self.display_name,
            "parent_list": self.parent_list,
            "child_list": self.child_list,
            "supplemental_list": self.supplemental_list,
            "descriptor_list": self.descriptor_list,
            "label": self.label,
        }
        return data


class MESHGraph:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.graph_data = []
        self.mesh_to_index = {}

        if data_dir:
            self.load_data()
        return

    def load_data(self):
        graph_file = os.path.join(self.data_dir, "graph", "graph.jsonl")

        self.graph_data = []
        self.mesh_to_index = {}

        with open(graph_file, "r", encoding="utf8") as f:
            for line in f:
                datum = json.loads(line)
                self.mesh_to_index[datum[0]] = len(self.graph_data)
                self.graph_data.append(datum)
        return

    def add_and_get_node(self, index, label, subgraph_index_to_node):
        if index in subgraph_index_to_node:
            node = subgraph_index_to_node[index]
        else:
            node = MESHNode(self.graph_data, index)
            node.label = label
            subgraph_index_to_node[index] = node
        return node

    def get_subgraph(
            self, query_mesh_list,
            super_level=3, sub_level=1, sibling_level=1, supplemental_level=1,
    ):
        index_to_node = {}
        edge_set = set()

        # query
        clean_query_mesh_set = set()
        for mesh in query_mesh_list:
            if mesh.startswith("MESH:"):
                mesh = mesh[len("MESH:"):]
            if mesh in self.mesh_to_index:
                clean_query_mesh_set.add(mesh)

        if not clean_query_mesh_set:
            return {
                "index_to_node": {},
                "edge_list": [],
            }

        query_index_to_node = {}
        for mesh in clean_query_mesh_set:
            index = self.mesh_to_index[mesh]
            node = self.add_and_get_node(index, "query", index_to_node)
            query_index_to_node[index] = node

        # ancestor
        this_level = query_index_to_node
        for _ in range(super_level):
            next_level = {}
            for node_index, node in this_level.items():
                for parent_index in node.parent_list:
                    edge_set.add((parent_index, node_index))
                    if parent_index in next_level:
                        continue
                    parent_node = self.add_and_get_node(parent_index, "super-category", index_to_node)
                    next_level[parent_index] = parent_node
            this_level = next_level
        del this_level

        # descendant
        this_level = query_index_to_node
        for _ in range(sub_level):
            next_level = {}
            for node_index, node in this_level.items():
                for child_index in node.child_list:
                    edge_set.add((node_index, child_index))
                    if child_index in next_level:
                        continue
                    child_node = self.add_and_get_node(child_index, "sub-category", index_to_node)
                    next_level[child_index] = child_node
            this_level = next_level
        del this_level

        # sibling
        if sibling_level == 1:
            parent_level = {}
            sibling_level = {}
            for query_index, query_node in query_index_to_node.items():
                for parent_index in query_node.parent_list:
                    edge_set.add((parent_index, query_index))
                    if parent_index in parent_level:
                        continue
                    parent_node = self.add_and_get_node(parent_index, "super-category", index_to_node)
                    parent_level[parent_index] = parent_node
                    for sibling_index in parent_node.child_list:
                        edge_set.add((parent_index, sibling_index))
                        if sibling_index in sibling_level:
                            continue
                        sibling_node = self.add_and_get_node(sibling_index, "sibling", index_to_node)
                        sibling_level[sibling_index] = sibling_node

        # descriptor to supplemental (for all nodes)
        label_to_level = {"query": 1, "sub-category": 2, "super-category": 3, "sibling": 4}

        for node_index in list(index_to_node.keys()):
            node = index_to_node[node_index]
            if supplemental_level < label_to_level[node.label]:
                continue
            for supplemental_index in node.supplemental_list:
                _supplemental_node = self.add_and_get_node(supplemental_index, "supplemental", index_to_node)
                edge_set.add((node_index, supplemental_index))

        # supplemental to descriptor (for query only)
        for query_index, query_node in query_index_to_node.items():
            for descriptor_index in query_node.descriptor_list:
                _descriptor_node = self.add_and_get_node(descriptor_index, "descriptor", index_to_node)
                edge_set.add((descriptor_index, query_index))

        # transform to JSON compatible dictionary
        data = {
            "index_to_node": {
                index: node.get_dictionary()
                for index, node in index_to_node.items()
            },
            "edge_list": sorted(edge_set),
        }
        return data


class MESHChemical:
    def __init__(self, data_dir):
        self.mesh_prefix = "MESH:"
        self.data_dir = data_dir
        self.mesh_to_mesh_name = {}
        self.mesh_name_to_mesh = {}

        if data_dir:
            self.load_data()
        return

    def load_data(self):
        descriptor_file = os.path.join(self.data_dir, "raw_json", "desc2023.jsonl")
        supplemental_file = os.path.join(self.data_dir, "raw_json", "supp2023_clean.jsonl")

        self.mesh_to_mesh_name = {}
        self.mesh_name_to_mesh = defaultdict(lambda: set())

        for name_file in [descriptor_file, supplemental_file]:
            with open(name_file, "r", encoding="utf8") as f:
                for line in f:
                    mesh, name, alias_list, _ = json.loads(line)
                    mesh = self.mesh_prefix + mesh

                    self.mesh_to_mesh_name[mesh] = [name] + alias_list

                    self.mesh_name_to_mesh[name.lower()].add(mesh)
                    for alias in alias_list:
                        self.mesh_name_to_mesh[alias.lower()].add(mesh)
        return

    def get_name_list_by_id(self, mesh):
        if not mesh.startswith(self.mesh_prefix):
            mesh = self.mesh_prefix + mesh
        name_list = self.mesh_to_mesh_name.get(mesh, [])
        return name_list

    def get_id_set_by_name(self, name):
        name = name.lower()
        mesh_set = self.mesh_name_to_mesh.get(name, set())
        return mesh_set


class ChemicalDiseaseKB:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.t_x_y_ann_pmidlist = {}

        if data_dir:
            for t in ["cd", "dc"]:
                key_file = os.path.join(data_dir, f"{t}_key.jsonl")
                value_file = os.path.join(data_dir, f"{t}_value.jsonl")
                self.t_x_y_ann_pmidlist[t] = DiskDict(key_file, value_file)
        return


class QA:
    def __init__(self, retriv_dir):
        self.retriv_dir = retriv_dir
        self.retriever = None
        self.top_dgp = 10000
        self.top_p = 10
        self.top_t = 30

        if self.retriv_dir:
            self.load_data()
        return

    def load_data(self):
        retriv.set_base_path(self.retriv_dir)
        logger.info(f"[qa] loading retriv index ...")
        self.retriever = DenseRetriever.load("dense_dgp_2025")
        logger.info("[qa] done loading retriv index")
        return

    def query_paper(self, question, d_set=None, g_set=None, v_set=None):
        logger.info(f"[qa] [question] {question}")
        logger.info(f"[qa] retrieving knowledge...")
        search_result_list = self.retriever.search(
            query=question,
            return_docs=True,
            cutoff=self.top_dgp,
        )
        logger.info(f"{len(search_result_list):,} search_results")

        logger.info("[qa] filtering by targets...")
        result_list = []
        p_set = set()
        t_set = set()

        for search_result in search_result_list:
            datum = search_result["datum"]
            p, d_name_matches, g_name_matches, v_name_matches, triplet_list = datum
            if not triplet_list:
                continue
            if d_set:
                for d in d_set:
                    if d in d_name_matches:
                        break
                else:
                    continue
            if g_set or v_set:
                for g in g_set:
                    if g in g_name_matches:
                        break
                else:
                    for v2 in v_name_matches:
                        i = v2.find("_")
                        g2 = v2[:i]
                        if g2 in g_set:
                            break
                    else:
                        for v in v_set:
                            if v in v_name_matches:
                                break
                        else:
                            continue
            result_list.append((p, triplet_list))

            p_set.add(p)
            for head, predicate, tail in triplet_list:
                t = f"{head} {predicate} {tail}".lower()
                t_set.add(t)
            if len(p_set) >= self.top_p and len(t_set) >= self.top_t:
                break
        pmids = len(p_set)
        triplets = len(t_set)
        logger.info(f"{len(result_list):,} filtered_results: {pmids:,} pmids; {triplets:,} triplets;")
        return p_set

    def query(self, question, d_set, g_set, v_set):
        logger.info(f"[qa] [question] {question}")
        logger.info(f"[qa] retrieving knowledge...")
        search_result_list = self.retriever.search(
            query=question,
            return_docs=True,
            cutoff=self.top_dgp,
        )
        logger.info(f"{len(search_result_list):,} search_results")

        logger.info("[qa] filtering by targets...")
        result_list = []
        p_set = set()
        t_set = set()

        for search_result in search_result_list:
            datum = search_result["datum"]
            p, d_name_matches, g_name_matches, v_name_matches, triplet_list = datum
            if not triplet_list:
                continue
            if d_set:
                for d in d_set:
                    if d in d_name_matches:
                        break
                else:
                    continue
            if g_set or v_set:
                for g in g_set:
                    if g in g_name_matches:
                        break
                else:
                    for v2 in v_name_matches:
                        i = v2.find("_")
                        g2 = v2[:i]
                        if g2 in g_set:
                            break
                    else:
                        for v in v_set:
                            if v in v_name_matches:
                                break
                        else:
                            continue
            result_list.append((p, triplet_list))

            p_set.add(p)
            for head, predicate, tail in triplet_list:
                t = f"{head} {predicate} {tail}".lower()
                t_set.add(t)
            if len(p_set) >= self.top_p and len(t_set) >= self.top_t:
                break
        pmids = len(p_set)
        triplets = len(t_set)
        logger.info(f"{len(result_list):,} filtered_results: {pmids:,} pmids; {triplets:,} triplets;")

        if result_list:
            answer_text = run_qa(question, "gpt-4o", "", 1000)
            answer_completion = run_qka_stream(question, answer_text, result_list, "gpt-4o", "", 7000)
        else:
            answer_completion = run_qa_stream(question, "gpt-4o", "", 1000)
        return answer_completion, p_set

    async def async_query(self, question, d_set, g_set, v_set):
        logger.info(f"[qa] [question] {question}")

        # parametric answering
        async_qa_task = asyncio.create_task(
            async_run_qa(question, "gpt-4o", "", 1000)
        )
        await asyncio.sleep(0)

        # retrieval
        logger.info(f"[qa] retrieving knowledge...")
        search_result_list = self.retriever.search(
            query=question,
            return_docs=True,
            cutoff=self.top_dgp,
        )
        logger.info(f"{len(search_result_list):,} search_results")

        logger.info("[qa] filtering by targets...")
        result_list = []
        p_set = set()
        t_set = set()

        for search_result in search_result_list:
            datum = search_result["datum"]
            p, d_name_matches, g_name_matches, v_name_matches, triplet_list = datum
            if not triplet_list:
                continue
            if d_set:
                for d in d_set:
                    if d in d_name_matches:
                        break
                else:
                    continue
            if g_set or v_set:
                for g in g_set:
                    if g in g_name_matches:
                        break
                else:
                    for v2 in v_name_matches:
                        i = v2.find("_")
                        g2 = v2[:i]
                        if g2 in g_set:
                            break
                    else:
                        for v in v_set:
                            if v in v_name_matches:
                                break
                        else:
                            continue
            result_list.append((p, triplet_list))

            p_set.add(p)
            for head, predicate, tail in triplet_list:
                t = f"{head} {predicate} {tail}".lower()
                t_set.add(t)
            if len(p_set) >= self.top_p and len(t_set) >= self.top_t:
                break
        pmids = len(p_set)
        triplets = len(t_set)
        logger.info(f"{len(result_list):,} filtered_results: {pmids:,} pmids; {triplets:,} triplets;")

        # combine retrieval and parametric answer
        if result_list:
            async_gpt_task = await async_qa_task
            task_datum = await async_gpt_task
            answer_text = task_datum.text_out_list[0]
            answer_completion = run_qka_stream(question, answer_text, result_list, "gpt-4o", "", 7000)

        else:
            async_qa_task.cancel()
            answer_completion = run_qa_stream(question, "gpt-4o", "", 1000)

        return answer_completion, p_set


class CGDInferenceKB:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.c_d_score_pathlist_list = []
        self.c_d_index = defaultdict(lambda: {})
        self.d_c_index = defaultdict(lambda: {})
        self.c_g_relationpmidlist = {}
        self.g_d_relationpmidlist = {}

        if data_dir:
            self.load_data()
        return

    def load_data(self):
        prefix = "[CGD Inference KB]"

        # C -> G -> (relation, pmid_list)
        # G -> D -> (relation, pmid_list)
        logger.info(f"{prefix} reading CG and GD papers...")
        for type_pair in ["CG", "GD"]:
            type_1, type_2 = type_pair[0], type_pair[1]
            e1_e2_relation_pmidlist_file = os.path.join(self.data_dir, f"{type_pair}_pmid_list.csv")
            e1_e2_relationpmidlist = defaultdict(lambda: {})

            with open(e1_e2_relation_pmidlist_file, "r", encoding="utf8", newline="") as f:
                reader = csv.reader(f, dialect="csv")
                header = next(reader)
                assert header == [type_1, type_2, "correlation", "PMID"]
                for e1, e2, relation, pmid_list_string in reader:
                    pmid_list = pmid_list_string.split("|")
                    e1_e2_relationpmidlist[e1][e2] = (relation, pmid_list)

            pairs = sum(
                len(e2_to_relationpmidlist) for _e1, e2_to_relationpmidlist in e1_e2_relationpmidlist.items()
            )
            logger.info(f"{prefix} read PMIDs for {pairs:,} {type_pair}")
            if type_pair == "CG":
                self.c_g_relationpmidlist = e1_e2_relationpmidlist
            else:
                self.g_d_relationpmidlist = e1_e2_relationpmidlist

        # [(C, D, cd_score, path_list), ...]
        # C -> D -> index
        # D -> C -> index
        c_d_score_pathlist_list_file = os.path.join(self.data_dir, f"CD.csv")
        logger.info(f"{prefix} reading CD scores and CGD paths...")
        with open(c_d_score_pathlist_list_file, "r", encoding="utf8", newline="") as f:
            reader = csv.reader(f, dialect="csv")
            header = next(reader)
            assert header == ["C", "D", "score", "inference_path_list"]
            for c, d, cd_score, path_list in reader:
                path_list = [
                    g_cgdscore.split(":")
                    for g_cgdscore in path_list.split("|")
                ]
                self.c_d_score_pathlist_list.append((c, d, cd_score, path_list))
        cds = len(self.c_d_score_pathlist_list)
        logger.info(f"{prefix} read {cds:,} CDs")
        for i, (c, d, _cd_score, _path_list) in enumerate(self.c_d_score_pathlist_list):
            self.c_d_index[c][d] = i
            self.d_c_index[d][c] = i
        return

    def query(self, c_list=None, d_list=None, max_cds=None, max_cgds_per_cd=None, max_pmids_per_cg_gd=None):
        # default arguments
        if c_list is None:
            c_list = []
        if d_list is None:
            d_list = []
        if max_cds is None:
            max_cds = 10
        if max_cgds_per_cd is None:
            max_cgds_per_cd = 10
        if max_pmids_per_cg_gd is None:
            max_pmids_per_cg_gd = 3

        # retrieve CD data indices
        index_list = []
        if c_list:
            if d_list:
                for c in c_list:
                    for d in d_list:
                        index = self.c_d_index.get(c, {}).get(d, None)
                        if index is not None:
                            index_list.append(index)
            else:
                for c in c_list:
                    for _d, index in self.c_d_index.get(c, {}).items():
                        index_list.append(index)
        else:
            if d_list:
                for d in d_list:
                    for _c, index in self.d_c_index.get(d, {}).items():
                        index_list.append(index)

        # sort index list
        #   CD data should have been sorted by score
        all_cds = len(index_list)
        if max_cds < all_cds / 4:
            index_list = heapq.nsmallest(max_cds, index_list)
        else:
            index_list = sorted(index_list)[:max_cds]

        # collect data
        #   path data should have been sorted by score
        cd_data = []
        for index in index_list:
            c, d, cd_score, pathlist = self.c_d_score_pathlist_list[index]
            all_cgds = len(pathlist)
            cgd_data = []
            for g, cgd_score in pathlist[:max_cgds_per_cd]:
                cg_relation, cg_pmid_list = self.c_g_relationpmidlist[c][g]
                gd_relation, gd_pmid_list = self.g_d_relationpmidlist[g][d]
                all_cg_pmids = len(cg_pmid_list)
                all_gd_pmids = len(gd_pmid_list)
                cgd_data.append((
                    g, cgd_score,
                    cg_relation, gd_relation,
                    all_cg_pmids, all_gd_pmids,
                    cg_pmid_list[:max_pmids_per_cg_gd], gd_pmid_list[:max_pmids_per_cg_gd]
                ))
            cd_data.append((c, d, cd_score, all_cgds, cgd_data))

        return all_cds, cd_data


def run_paper_qa(question, paper_list):
    completion = run_pqa_stream(question, paper_list, "gpt-4o", "", 7000)
    return completion


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

    # test_v2g(arg.variant_dir, arg.gene_dir)
    # test_kb(arg.kb_dir)
    # test_meta(arg.meta_dir)
    return


if __name__ == "__main__":
    main()
    sys.exit()
