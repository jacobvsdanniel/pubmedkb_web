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


def run_test(server_path, client_path):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="https://lab5-k8s.corp.ailabs.tw/pubmedkb-api/rel")
    # parser.add_argument("--server", default="http://127.0.0.1:12345/query_rel")
    parser.add_argument("--client", default="tmp")
    arg = parser.parse_args()
    for key, value in vars(arg).items():
        if value is not None:
            logger.info(f"[{key}] {value}")

    run_test(arg.server, arg.client)
    return


if __name__ == "__main__":
    main()
    sys.exit()
