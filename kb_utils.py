import os
import csv
import sys
import json
import difflib
import logging
import argparse
import urllib.parse
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


class VariantQuery:
    def __init__(self, data_file):
        self.type_id_name_frequency = defaultdict(lambda: defaultdict(lambda: {}))

        type_id_name_frequency_list = read_csv(data_file, "csv")
        type_set = {"ProteinMutation", "DNAMutation", "SNP", "CopyNumberVariant"}
        id_system_set = {"HGVS", "RS#"}

        for _type, _id, name, frequency in type_id_name_frequency_list[1:]:
            if _type not in type_set:
                continue

            i = _id.find(":")
            id_system = _id[:i]
            if id_system not in id_system_set:
                continue

            self.type_id_name_frequency[_type][_id][name] = int(frequency)
        return

    def get_nen(self, query):
        query_quote = urllib.parse.quote(query)
        response = requests.get(
            "https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/autocomplete/",
            params={"query": query_quote},
        )
        result_list = response.json()
        extraction_list = []

        for result in result_list:
            # logger.info(f"raw result: {result}")

            _id = []
            if "rsid" in result:
                _id.append("RS#:" + result["rsid"][2:])
            if "hgvs" in result:
                _id.append("HGVS:" + result["hgvs"])

            name = [result["name"]]
            if "match" in result:
                match = result["match"]
                prefix = "<m>"
                suffix = "</m>"
                i = match.find(prefix) + len(prefix)
                j = match.find(suffix, i)
                match = match[i:j]
                if match != name[0]:
                    name.append(match)

            gene = result.get("gene", [])

            extraction = (_id, name, gene)
            extraction_list.append(extraction)
            # logger.info(f"extracted result: {extraction}")

        return extraction_list

    def get_nen_in_kb(self, id_list, name_list):
        type_id_name_frequency = []

        for _type, id_name_frequency in self.type_id_name_frequency.items():
            for _id in id_list:
                if _id not in id_name_frequency:
                    continue
                for name in name_list:
                    if name not in id_name_frequency[_id]:
                        continue
                    frequency = id_name_frequency[_id][name]
                    type_id_name_frequency.append((_type, _id, name, frequency))

        type_id_name_frequency = sorted(type_id_name_frequency, key=lambda tidf: tidf[3], reverse=True)

        return type_id_name_frequency


class NEN:
    def __init__(self, data_file):
        self.type_id_name_frequency = defaultdict(lambda: defaultdict(lambda: {}))
        self.name_type_id = defaultdict(lambda: defaultdict(lambda: []))
        self.length_name = defaultdict(lambda: set())

        type_id_name_frequency_list = read_csv(data_file, "csv")
        for _type, _id, name, frequency in type_id_name_frequency_list[1:]:
            self.type_id_name_frequency[_type][_id][name] = int(frequency)
            self.name_type_id[name][_type].append(_id)
            self.length_name[len(name)].add(name)
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


class KB:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.nen = None
        self.data = {
            "sentence": None,
            "annotation": None,
            "evidence": None,
        }
        self.index = {
            "pmid": None,
            "type_id": None,
            "type_name": None,
        }
        return

    def load_nen(self):
        nen_file = os.path.join(self.data_dir, "type_id_name_frequency.csv")
        self.nen = NEN(nen_file)
        return

    def load_data(self, data_type=("evidence", "annotation", "sentence")):
        for name in data_type:
            file = os.path.join(self.data_dir, f"{name}.jsonl")
            self.data[name] = read_lines(file, line_by_line=True)
        return

    def load_index(self, index_type=("pmid", "type_id", "type_name")):
        for name in index_type:
            file = os.path.join(self.data_dir, f"{name}.jsonl")
            key_value_list = read_json(file, is_jsonl=True)
            if name == "pmid":
                self.index[name] = {key: value for key, value in key_value_list}
            else:
                self.index[name] = {tuple(key): value for key, value in key_value_list}
        return

    def get_evidence_ids_by_pmid(self, pmid):
        assert isinstance(pmid, str)
        id_list = self.index["pmid"].get(pmid, [])
        return id_list

    def get_evidence_ids_by_entity(self, entity, key="type_id_name"):
        assert isinstance(entity, tuple)
        assert len(entity) == len(key.split("_"))
        if key in ["type_id", "type_name"]:
            id_list = self.index[key].get(entity, [])
        elif key == "type_id_name":
            _type, _id, name = entity
            id_list_1 = self.index["type_id"].get((_type, _id), [])
            id_list_2 = self.index["type_name"].get((_type, name), [])
            id_list = sorted(set(id_list_1) & set(id_list_2))
        else:
            assert False
        return id_list

    def get_evidence_ids_by_pair(self, pair, key=("type_id_name", "type_id_name")):
        head_id_list = self.get_evidence_ids_by_entity(pair[0], key[0])
        tail_id_list = self.get_evidence_ids_by_entity(pair[1], key[1])
        id_list = sorted(set(head_id_list) & set(tail_id_list))
        return id_list

    def get_evidence_by_id(self, _id, return_annotation=True, return_sentence=True):
        evidence = self.data["evidence"][_id]
        head, tail, annotation, pmid, sentence = json.loads(evidence)

        if return_annotation:
            annotation = self.data["annotation"][annotation]
            annotation = json.loads(annotation)

        if return_sentence:
            sentence = self.data["sentence"][sentence]
            sentence = json.loads(sentence)

        return head, tail, annotation, pmid, sentence


class DiskKB:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.nen = None
        self.data = {
            "sentence": None,
            "annotation": None,
            "evidence": None,
        }
        self.index = {
            "pmid": None,
            "type_id": None,
            "type_name": None,
        }
        return

    def load_nen(self):
        nen_file = os.path.join(self.data_dir, "type_id_name_frequency.csv")
        self.nen = NEN(nen_file)
        return

    def load_data(self, data_type=("evidence", "annotation", "sentence")):
        for name in data_type:
            file = os.path.join(self.data_dir, f"{name}.jsonl")
            self.data[name] = open(file, "r", encoding="utf8")
        return

    def load_index(self, index_type=("pmid", "type_id", "type_name")):
        for name in index_type:
            file = os.path.join(self.data_dir, f"{name}.jsonl")
            key_value_list = read_json(file, is_jsonl=True)
            if name == "pmid":
                self.index[name] = {key: value for key, value in key_value_list}
            else:
                self.index[name] = {tuple(key): value for key, value in key_value_list}
        return

    def get_evidence_ids_by_pmid(self, pmid):
        assert isinstance(pmid, str)
        id_list = self.index["pmid"].get(pmid, [])
        return id_list

    def get_evidence_ids_by_entity(self, entity, key="type_id_name"):
        assert isinstance(entity, tuple)
        assert len(entity) == len(key.split("_"))
        if key in ["type_id", "type_name"]:
            id_list = self.index[key].get(entity, [])
        elif key == "type_id_name":
            _type, _id, name = entity
            id_list_1 = self.index["type_id"].get((_type, _id), [])
            id_list_2 = self.index["type_name"].get((_type, name), [])
            id_list = sorted(set(id_list_1) & set(id_list_2))
        else:
            assert False
        return id_list

    def get_evidence_ids_by_pair(self, pair, key=("type_id_name", "type_id_name")):
        head_id_list = self.get_evidence_ids_by_entity(pair[0], key[0])
        tail_id_list = self.get_evidence_ids_by_entity(pair[1], key[1])
        id_list = sorted(set(head_id_list) & set(tail_id_list))
        return id_list

    def get_evidence_by_id(self, _id, return_annotation=True, return_sentence=True):
        self.data["evidence"].seek(_id)
        evidence = self.data["evidence"].readline()[:-1]
        head, tail, annotation, pmid, sentence = json.loads(evidence)

        if return_annotation:
            self.data["annotation"].seek(annotation)
            annotation = self.data["annotation"].readline()[:-1]
            annotation = json.loads(annotation)

        if return_sentence:
            self.data["sentence"].seek(sentence)
            sentence = self.data["sentence"].readline()[:-1]
            sentence = json.loads(sentence)

        return head, tail, annotation, pmid, sentence


def test_vq(kb_dir):
    nen_file = os.path.join(kb_dir, "type_id_name_frequency.csv")
    vq = VariantQuery(nen_file)

    extraction_list = vq.get_nen("val600g")

    for id_list, name_list, gene_list in extraction_list:
        logger.info(f"{id_list} {name_list}")

        type_id_name_frequency_list = vq.get_nen_in_kb(id_list, name_list)
        for _type, _id, name, frequency in type_id_name_frequency_list:
            logger.info(f"-> in KB: {_type} {_id} {name} {frequency}")
    return


def test_nen(kb_dir):
    kb = KB(kb_dir)
    kb.load_nen()

    query = "Metformin"
    logger.info(f"query: {query}")

    name_similarity_list = kb.nen.get_names_by_query(
        query, case_sensitive=False, max_length_diff=1, min_similarity=0.85, max_names=10,
    )
    names = len(name_similarity_list)
    logger.info(f"{names:,} names")
    input("YOLO")

    for name, similarity in name_similarity_list:
        logger.info(f"name: {name}, similarity: {similarity}")
        type_id_frequency_list = kb.nen.get_ids_by_name(name)
        ids = len(type_id_frequency_list)
        logger.info(f"ids: {ids}")

        for _type, _id, id_frequency in type_id_frequency_list:
            alias_frequency_list = kb.nen.get_aliases_by_id(_type, _id, max_aliases=5)
            logger.info(f"({_type}, {_id}, {name}, {id_frequency}): alias_list={alias_frequency_list}")

        input("YOLO")
    return


def test_kb(kb_dir):
    kb = KB(kb_dir)
    kb.load_data()
    kb.load_index()
    input("YOLO")

    head = ("Chemical", "MESH:D001639", "bicarbonate")
    tail = ("Disease", "MESH:D000138", "metabolic acidosis")
    evidence_list = kb.get_evidence_ids_by_pair((head, tail))
    evidence_list = [kb.get_evidence_by_id(_id) for _id in evidence_list]
    evidences = len(evidence_list)
    logger.info(f"{evidences:,} evidences")
    input("YOLO")
    for evidence in evidence_list:
        logger.info(evidence)
    input("YOLO")

    head = ("Chemical", "MESH:D001639")
    tail = ("Disease", "MESH:D000138")
    evidence_list = kb.get_evidence_ids_by_pair((head, tail), key=("type_id", "type_id"))
    evidence_list = [kb.get_evidence_by_id(_id) for _id in evidence_list]
    evidences = len(evidence_list)
    logger.info(f"{evidences:,} evidences")
    input("YOLO")
    for evidence in evidence_list:
        logger.info(evidence)
    input("YOLO")

    head = ("Chemical", "bicarbonate")
    tail = ("Disease", "metabolic acidosis")
    evidence_list = kb.get_evidence_ids_by_pair((head, tail), key=("type_name", "type_name"))
    evidence_list = [kb.get_evidence_by_id(_id) for _id in evidence_list]
    evidences = len(evidence_list)
    logger.info(f"{evidences:,} evidences")
    input("YOLO")
    for evidence in evidence_list:
        logger.info(evidence)
    input("YOLO")
    return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb_dir", type=str, default="pubmedKB-PTC/1_319_disk")
    arg = parser.parse_args()

    test_vq(arg.kb_dir)
    # test_nen(arg.kb_dir)
    # test_kb(arg.kb_dir)
    return


if __name__ == "__main__":
    main()
    sys.exit()
