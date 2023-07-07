import os
import sys
import json
import logging
import argparse
import requests

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
    level=logging.INFO,
)


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


def write_json(file, data, is_jsonl=False, indent=None, write_log=True):
    if write_log:
        objects = len(data)
        logger.info(f"Writing {objects:,} objects")

    with open(file, "w", encoding="utf8") as f:
        if is_jsonl:
            for datum in data:
                json.dump(datum, f)
                f.write("\n")
        else:
            json.dump(data, f, indent=indent)

    if write_log:
        logger.info(f"Written to {file}")
    return


def get_result_from_server(server_path, query):
    logger.info("[Query]")

    for key, value in query.items():
        logger.info(f"[argument] {key}={value}")

    response = requests.get(
        server_path,
        params=query,
    )
    result = response.json()
    return result


def run_rel_test(server_path, client_path):
    query_list = [
        {
            "e1_spec": json.dumps(
                ("type_id", ("VARIANT", "RS#:113488022"))
            ),
            "paper_start": "0",
            "paper_end": "10",
        },
        {
            "e1_spec": json.dumps(
                ("type_id", ("VARIANT", "RS#:113488022"))
            ),
            "e2_spec": json.dumps(
                ("type_id", ("Disease", "MESH:D009369"))
            ),
            "pmid": "35246262",
            "paper_start": "0",
            "paper_end": "10",
        },
        {
            "e1_spec": json.dumps(
                (
                    "OR",
                    (
                        (
                            "AND",
                            (
                                ("type_id", ("ProteinMutation", "HGVS:p.V600E")),
                                ("type_id", ("ProteinMutation", "CorrespondingGene:673")),
                            )
                        ),
                        ("type_id", ("VARIANT", "RS#:113488022")),
                    )
                )
            ),
            "e2_spec": json.dumps(
                ("type_id", ("Disease", "MESH:D009369"))
            ),
            "pmid": "35246262",
            "paper_start": "0",
            "paper_end": "10",
        },
    ]

    os.makedirs(client_path, exist_ok=True)

    for qi, query in enumerate(query_list):
        result = get_result_from_server(server_path, query)
        result_file = os.path.join(client_path, f"result_{qi}.json")
        write_json(result_file, result)
    return


def run_litsum_test(server_path, client_path):
    openai_api_key = input("OpenAI API Key: ")

    query_list = [
        {
            "entity_1": "V600E", "entity_2": "lung cancer",
            "pmid_list": [
                "36112789", "24589553", "22511580", "34433708", "33276639",
                "33037234", "31452510", "36697098", "34484797", "24019382",
            ],
        },
        {
            "entity_1": "PRKD1", "entity_2": "diseases",
            "pmid_list": None,
        },
        {
            "entity_1": "GABRA5", "entity_2": "diseases",
            "pmid_list": None,
        },
        {
            "entity_1": "SYNE1", "entity_2": "diseases",
            "pmid_list": None,
        },
        {
            "entity_1": "EPO", "entity_2": "diseases",
            "pmid_list": None,
        },
        {
            "entity_1": "V600E", "entity_2": "diseases",
            "pmid_list": None,
        },
        {
            "entity_1": "variants", "entity_2": "lung cancer",
            "pmid_list": None,
        },
        {
            "entity_1": "genes", "entity_2": "lung cancer",
            "pmid_list": None,
        },
    ]

    os.makedirs(client_path, exist_ok=True)

    for qi, query in enumerate(query_list):
        pmid_list = query["pmid_list"]
        if not pmid_list:
            e1 = query["entity_1"].replace(" ", "_")
            e2 = query["entity_2"].replace(" ", "_")
            rel_file = os.path.join(client_path, f"{e1}_{e2}_relevance.json")
            rel_data = read_json(rel_file)
            pmid_list = [paper["pmid"] for paper in rel_data["paper_list"]]
            query["pmid_list"] = pmid_list
        assert len(pmid_list) == 10

    for qi, query in enumerate(query_list):
        logger.info(f"[query #{qi}] {query}")
        e1 = query["entity_1"].replace(" ", "_")
        e2 = query["entity_2"].replace(" ", "_")
        query = {
            "query_dict": query,
            "query": json.dumps(query),
            "openai_api_key": openai_api_key,
        }
        result = get_result_from_server(server_path, query)
        result_file = os.path.join(client_path, f"summary_{e1}_and_{e2}.json")
        write_json(result_file, result)
    return


def main():
    parser = argparse.ArgumentParser()
    # parser.add_argument("--server", default="https://lab5-k8s.corp.ailabs.tw/pubmedkb-api/rel")
    parser.add_argument("--server", default="http://127.0.0.1:12345/query_litsum")
    parser.add_argument("--client", default="test_litsum")
    arg = parser.parse_args()
    for key, value in vars(arg).items():
        if value is not None:
            logger.info(f"[{key}] {value}")

    # run_rel_test(arg.server, arg.client)
    run_litsum_test(arg.server, arg.client)
    return


if __name__ == "__main__":
    main()
    sys.exit()
