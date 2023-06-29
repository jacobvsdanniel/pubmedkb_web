import re
import csv
import sys
import json
import time
import logging
import argparse

import openai

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


class PaperGPT:
    def __init__(self, pmid, title, abstract, entity_1, entity_2):
        self.pmid = pmid
        self.title = title
        self.abstract = abstract
        self.entity_1 = entity_1
        self.entity_2 = entity_2

        self.article = \
            f"Article:\n" \
            f"[PMID] {self.pmid}\n" \
            f"[title] {self.title}\n" \
            f"[text] {self.abstract}\n"

        self.paper_summary = ""
        self.entity_summary = ""
        return

    def get_paper_summary(self):
        logger.info(f"[{self.pmid}] {self.title}")
        prompt = f"Please summarize the article in 1 sentence and 3 bullet points.."
        text_in = f"{self.article}\n{prompt}\n"

        for _ in range(10):
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    n=1,
                    messages=[
                        {"role": "user", "content": text_in},
                    ]
                )
                text_out = completion.choices[0].message.content
                break
            except:
                logger.info(f"PaperGPT.get_paper_summary(): openai.ChatCompletion.create(): Error")
                time.sleep(2)
        else:
            text_out = ""

        text_out = re.sub(r"\n\n+", "\n", text_out)
        text_out = text_out.replace(". -", ".\n -")
        self.paper_summary = text_out
        logger.info(f"[{self.pmid}] paper_summary: {self.paper_summary}")
        return

    def get_entity_summary(self):
        logger.info(f"[{self.pmid}] {self.title}")
        prompt = f"Based on the article, explain how {self.entity_1} relates to {self.entity_2}" \
                 f" using at most 3 sentences in layman's terms."
        text_in = f"{self.article}\n{prompt}\n"

        for _ in range(10):
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    n=1,
                    messages=[
                        {"role": "user", "content": text_in},
                    ]
                )
                text_out = completion.choices[0].message.content
                break
            except:
                logger.info(f"PaperGPT.get_entity_summary(): openai.ChatCompletion.create(): Error")
                time.sleep(2)
        else:
            text_out = ""

        self.entity_summary = text_out
        logger.info(f"[{self.pmid}] entity_summary: {self.entity_summary}")
        return


class ReviewGPT:
    def __init__(self, papergpt_list, entity_1, entity_2):
        self.papergpt_list = papergpt_list
        self.entity_1 = entity_1
        self.entity_2 = entity_2

        self.article = ""
        self.summary = ""
        return

    def get_summary(self):
        logger.info(f"[review] {self.entity_1} and {self.entity_2}")
        article = []

        for papergpt in self.papergpt_list:
            if not papergpt.entity_summary:
                papergpt.get_entity_summary()
            passage = f"[PMID-{papergpt.pmid}]\n{papergpt.entity_summary}\n"
            article.append(passage)

        self.article = "\n".join(article)

        prompt = f"Based on the articles, explain how {self.entity_1} relates to {self.entity_2}."
        text_in = f"{article}\n{prompt}\n"

        for _ in range(10):
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    n=1,
                    messages=[
                        {"role": "user", "content": text_in},
                    ]
                )
                text_out = completion.choices[0].message.content
                break
            except:
                logger.info(f"ReviewGPT.get_summary(): openai.ChatCompletion.create(): Error")
                time.sleep(2)
        else:
            text_out = ""

        self.summary = text_out
        logger.info(f"[review] summary: {self.summary}")
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tmp", type=str)
    arg = parser.parse_args()
    for key, value in vars(arg).items():
        if value is not None:
            logger.info(f"[{key}] {value}")
    return


if __name__ == "__main__":
    main()
    sys.exit()
