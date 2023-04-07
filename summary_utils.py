import csv
import sys
import html
import heapq
import random
import logging
import argparse
from collections import defaultdict

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
cre_label_to_weight = {
    "Cause-associated": 3,
    "In-patient": 2,
    "Appositive": 1,
}
template_type_to_list = {
    "X": [
        [
            [],
            [
                "",
            ],
        ],
    ],
    "query_ABP": [
        [
            ["entity1", "entity2", "pmid"],
            [
                "Based on our search results, relation exists between ",
                " and ",
                " in PMID: ",
                ".",
            ],
        ],
        [
            ["entity1", "entity2", "pmid"],
            [
                "Relations occur between ",
                " and ",
                " as shown from our search for PMID: ",
                ".",
            ],
        ],
        [
            ["entity1", "entity2", "pmid"],
            [
                "",
                " and ",
                " relate to each other in PMID: ",
                ".",
            ],
        ],
    ],
    "query_AP": [
        [
            ["pmid", "entity"],
            [
                "Based on our search results, in PMID: ",
                ", relation exists for ",
                ".",
            ],
        ],
        [
            ["pmid", "entity"],
            [
                "From PMID: ",
                ", relation exists for ",
                ".",
            ],
        ],
        [
            ["entity", "pmid"],
            [
                "We found relations for ",
                " in PMID: ",
                ".",
            ],
        ],
    ],
    "query_P": [
        [
            ["pmid"],
            [
                "PMID: ",
                " shows the following relations.",
            ],
        ],
        [
            ["pmid"],
            [
                "In PMID: ",
                ", our search results find these relations.",
            ],
        ],
        [
            ["pmid"],
            [
                "For PMID: ",
                ", some relations are extracted.",
            ],
        ],
    ],
    "query_AB": [
        [
            ["entity1", "entity2"],
            [
                "Based on our search results, relation exists between ",
                " and ",
                ".",
            ],
        ],
        [
            ["entity1", "entity2"],
            [
                "Relations occur between ",
                " and ",
                " as shown from our search. The exact sources are demonstrated by PMID.",
            ],
        ],
        [
            ["entity1", "entity2"],
            [
                "",
                " and ",
                " relate to each other in the following ways.",
            ],
        ],
    ],
    "query_A": [
        [
            ["entity"],
            [
                "Based on our search results, relation exists for ",
                ".",
            ],
        ],
        [
            ["entity"],
            [
                "",
                " has the following relations.",
            ],
        ],
        [
            ["entity"],
            [
                "These relations are present in our search results for ",
                ".",
            ],
        ],
    ],
    "odds_ratio_P": [
        [
            ["variant", "disease", "pmid", "OR", "CI", "p-value"],
            [
                "The odds ratio found between ",
                " and ",
                " in PMID: ",
                " is ",
                " (CI: ",
                ", p-value: ",
                ").",
            ],
        ],
        [
            ["variant", "disease", "OR", "CI", "p-value", "pmid"],
            [
                "",
                " and ",
                " have an ",
                " odds ratio (CI: ",
                ", p-value: ",
                ") in PMID: ",
                ".",
            ],
        ],
    ],
    "odds_ratio_X": [
        [
            ["variant", "disease", "OR", "CI", "p-value"],
            [
                "The odds ratio found between ",
                " and ",
                " is ",
                " (CI: ",
                ", p-value: ",
                ").",
            ],
        ],
        [
            ["variant", "disease", "OR", "CI", "p-value"],
            [
                "",
                " and ",
                " have an ",
                " odds ratio (CI: ",
                ", p-value: ",
                ").",
            ],
        ],
    ],
    "cre_cause_P": [
        [
            ["variant", "disease", "score", "pmid", "sentence"],
            [
                "We believe that there is a causal relationship between ",
                " and ",
                " with a confidence of ",
                ". Here is an excerpt of the literature (PMID: ",
                ") that captures the relation: \"",
                "\".",
            ],
        ],
        [
            ["score", "variant", "disease", "pmid", "sentence"],
            [
                "With a confidence of ",
                ", we found that ",
                " is a causal variant of ",
                ". This piece of relation is evidenced by the sentence in PMID: ",
                ": \"",
                "\".",
            ],
        ],
        [
            ["pmid", "sentence", "variant", "disease", "score"],
            [
                "Based on the sentence (PMID: ",
                "): \"",
                "\". Our finding indicates that ",
                " is associated with ",
                " by a confidence of ",
                ".",
            ],
        ],
    ],
    "cre_cause_X": [
        [
            ["variant", "disease", "score", "sentence"],
            [
                "We believe that there is a causal relationship between ",
                " and ",
                " with a confidence of ",
                ". Here is an excerpt in the paper that captures the relation: \"",
                "\".",
            ],
        ],
        [
            ["score", "variant", "disease", "sentence"],
            [
                "With a confidence of ",
                ", we found that ",
                " is a causal variant of ",
                ". This piece of relation is evidenced by the sentence: \"",
                "\".",
            ],
        ],
        [
            ["sentence", "variant", "disease", "score"],
            [
                "Based on the sentence: \"",
                "\". Our finding indicates that ",
                " is associated with ",
                " by a confidence of ",
                ".",
            ],
        ],
    ],
    "cre_patient_P": [
        [
            ["varaint", "disease", "score", "pmid", "sentence"],
            [
                "",
                " occurs in some ",
                " patients. Our finding shows that the confidence of this association is approximately ",
                ". Here is an excerpt of the literature (PMID: ",
                ") that captures the relation: \"",
                "\".",
            ],
        ],
        [
            ["score", "disease", "variant", "pmid", "sentence"],
            [
                "With a confidence of ",
                ", we found that ",
                " patients carry ",
                ". This is evidenced by the following sentence in PMID ",
                ". \"",
                "\"",
            ],
        ],
        [
            ["pmid", "sentence", "score", "disease", "variant"],
            [
                "As claimed by (PMID: ",
                ") \"",
                "\", we are ",
                " sure that ",
                " patients show to have ",
                ".",
            ],
        ],
    ],
    "cre_patient_X": [
        [
            ["varaint", "disease", "score", "sentence"],
            [
                "",
                " occurs in some ",
                " patients. Our finding shows that the confidence of this association is approximately ",
                ". Here is an excerpt in the paper that captures the relation: \"",
                "\".",
            ],
        ],
        [
            ["score", "disease", "variant", "pmid", "sentence"],
            [
                "With a confidence of ",
                ", we found that ",
                " patients carry ",
                ". This is evidenced by the following sentence. \"",
                "\"",
            ],
        ],
        [
            ["sentence", "score", "disease", "variant"],
            [
                "As claimed by \"",
                "\", we are ",
                " sure that ",
                " patients show to have ",
                ".",
            ],
        ],
    ],
    "cre_appositive_P": [
        [
            ["variant", "disease", "score", "pmid", "sentence"],
            [
                "",
                "'s relation with ",
                " is presupposed. We are ",
                " confident about this association. Here is an excerpt of the literature (PMID: ",
                ") that captures this: \"",
                "\".",
            ],
        ],
        [
            ["score", "variant", "disease", "sentence", "pmid"],
            [
                "It is ",
                " presupposed that ",
                " is related to ",
                " as evidenced by \"",
                "\" (PMID: ",
                ").",
            ],
        ],
        [
            ["sentence", "pmid", "score", "variant", "disease"],
            [
                "According to the sentence: \"",
                "\" (PMID: ",
                "), We are ",
                " confident that the relation between ",
                " and ",
                " contains a presupposition.",
            ],
        ],
    ],
    "cre_appositive_X": [
        [
            ["variant", "disease", "score", "sentence"],
            [
                "",
                "'s relation with ",
                " is presupposed. We are ",
                " confident about this association. Here is an excerpt in the paper that captures this: \"",
                "\".",
            ],
        ],
        [
            ["score", "variant", "disease", "sentence"],
            [
                "It is ",
                " presupposed that ",
                " is related to ",
                " as evidenced by \"",
                "\".",
            ],
        ],
        [
            ["sentence", "score", "variant", "disease"],
            [
                "According to the sentence: \"",
                "\", We are ",
                " confident that the relation between ",
                " and ",
                " contains a presupposition.",
            ],
        ],
    ],
    "ore_2_P": [
        [
            ["triplet1", "pmid1", "triplet2", "pmid2"],
            [
                "Moreover, there are also open relations found between entities, which includes the following. \"",
                "\" (PMID: ",
                "). \"",
                "\" (PMID: ",
                ").",
            ],
        ],
        [
            ["triplet1", "pmid1", "triplet2", "pmid2"],
            [
                "Further relations are present, notably: \"",
                "\" (PMID ",
                ") and \"",
                "\" (PMID ",
                ").",
            ],
        ],
        [
            ["triplet1", "pmid1", "triplet2", "pmid2"],
            [
                "Between entities, prior literature also entails that \"",
                "\" (PMID: ",
                ") and \"",
                "\" (PMID: ",
                ").",
            ],
        ],
    ],
    "ore_2_X": [
        [
            ["triplet1", "triplet2"],
            [
                "Moreover, there are also open relations found between entities, which includes the following. \"",
                "\". \"",
                "\".",
            ],
        ],
        [
            ["triplet1", "triplet2"],
            [
                "Further relations are present, notably: \"",
                "\" and \"",
                "\".",
            ],
        ],
        [
            ["triplet1", "triplet2"],
            [
                "Between entities, prior literature also entails that \"",
                "\" and \"",
                "\".",
            ],
        ],
    ],
    "ore_1_P": [
        [
            ["triplet", "pmid"],
            [
                "We also found \"",
                "\" (PMID: ",
                ").",
            ],
        ],
        [
            ["triplet", "pmid"],
            [
                "\"",
                "\" (PMID: ",
                ").",
            ],
        ],
        [
            ["triplet", "pmid"],
            [
                "In addition, \"",
                "\" (PMID: ",
                ").",
            ],
        ],
    ],
    "ore_1_X": [
        [
            ["triplet"],
            [
                "We also found \"",
                "\".",
            ],
        ],
        [
            ["triplet"],
            [
                "\"",
                "\".",
            ],
        ],
        [
            ["triplet"],
            [
                "In addition, \"",
                "\".",
            ],
        ],
    ],
}
span_class_to_style = {
    "query_entity": "font-weight: bold;",
    "odds_ratio_entity": "font-weight: bold; color: #21d59b;",
    "cre_entity": "font-weight: bold; color: #0058ff;",
    "ore_entity": "font-weight: bold; color: #ff8389;",
    "query": "",
    "odds_ratio": "background-color: #62e0b84d;",
    "cre": "background-color: #5f96ff4d;",
    "ore": "background-color: #ff83894d;",
}


def get_passage_from_template(template, term_type_to_term):
    term_type_sequence, text_list = template
    assert len(term_type_sequence) == len(text_list) - 1

    term_type_to_span_list = defaultdict(lambda: [])
    passage = text_list[0]

    for text_index, text in enumerate(text_list[1:]):
        term_type = term_type_sequence[text_index]
        term = term_type_to_term[term_type]

        span = (len(passage), len(passage) + len(term))
        term_type_to_span_list[term_type].append(span)

        passage = passage + term + text

    return passage, term_type_to_span_list


def get_id_name_from_entity_spec(entity_spec):
    if not entity_spec:
        return "", ""
    op, arg = entity_spec

    if op in ["AND", "OR"]:
        first_id, first_name = "", ""

        for sub_entity_spec in arg:
            _id, name = get_id_name_from_entity_spec(sub_entity_spec)
            if not first_id:
                first_id = _id
            if not first_name:
                first_name = name
            if first_id and first_name:
                break

        return first_id, first_name

    elif op == "type_id":
        return arg[1], ""

    elif op == "type_name":
        return "", arg[1]

    else:
        assert False


def get_term_for_entity_spec(entity_spec):
    _id, name = get_id_name_from_entity_spec(entity_spec)
    if name:
        return name
    return _id


class Summary:
    def __init__(self, paper_list, e1_spec, e2_spec, pmid_spec):
        self.paper_list = paper_list
        self.e1_spec = get_term_for_entity_spec(e1_spec)
        self.e2_spec = get_term_for_entity_spec(e2_spec)
        self.pmid_spec = pmid_spec if pmid_spec else ""

        # relation
        self.selected_pmid_set = set()
        self.annotator_to_selected_paper_relation = {
            annotator: []
            for annotator in ["odds_ratio", "cre", "ore"]
        }

        # passage
        self.passage_type_list = ["query", "odds_ratio", "cre", "ore"]
        self.type_to_passage_and_term_span = {}

        # summary
        self.text_summary = {}
        self.html_summary = ""
        return

    def run_pipeline(self):
        self.select_odds_ratio_relation()
        self.select_cre_relation()
        self.select_ore_relation()
        self.create_passage()
        self.create_text_summary()
        self.create_html_summary()
        return

    def select_odds_ratio_relation(self):
        paper_relation_list = [
            (paper, relation)
            for paper in self.paper_list
            for relation in paper.annotator_to_relation.get("odds_ratio", [])
        ]
        if not paper_relation_list:
            return

        key_list = []
        for paper, relation in paper_relation_list:
            odds_ratio = relation["annotation"]["OR"]
            try:
                odds_ratio = float(odds_ratio)
            except ValueError:
                key_list.append(0)
                continue

            if odds_ratio < 1:
                odds_ratio = 1 / odds_ratio
            key_list.append(odds_ratio)

        top_index = max(range(len(paper_relation_list)), key=lambda i: key_list[i])
        paper_relation = paper_relation_list[top_index]
        self.selected_pmid_set.add(paper_relation[0].pmid)
        self.annotator_to_selected_paper_relation["odds_ratio"].append(paper_relation)
        return

    def select_cre_relation(self):
        paper_relation_list = [
            (paper, relation)
            for paper in self.paper_list
            for relation in paper.annotator_to_relation.get("rbert_cre", [])
        ]
        if not paper_relation_list:
            return

        key_list = []
        for paper, relation in paper_relation_list:
            label = relation["annotation"]["relation"]
            score = relation["annotation"]["score"]
            score = float(score[:-1]) * cre_label_to_weight[label]
            key_list.append((paper.pmid not in self.selected_pmid_set, score))

        # use negative score instead of reverse=True, to preserve paper order
        top_index = max(range(len(paper_relation_list)), key=lambda i: key_list[i])

        paper_relation = paper_relation_list[top_index]
        self.selected_pmid_set.add(paper_relation[0].pmid)
        self.annotator_to_selected_paper_relation["cre"].append(paper_relation)
        return

    def get_ore_top_predicate_to_paper_relation(self, annotator, top_k, exclude_predicate_set=None):
        """

        :param annotator: "spacy_ore" / "openie_ire"
        :param top_k: int
        :param exclude_predicate_set: set
        :return: {
            predicate: (pmid, relation),
            ...
        }
        """
        if top_k <= 0:
            return {}
        if exclude_predicate_set is None:
            exclude_predicate_set = set()

        predicate_to_paper_relation_list = defaultdict(lambda: [])

        # collect predicate to relations (annotations) mapping
        for paper in self.paper_list:
            for relation in paper.annotator_to_relation.get(annotator, []):
                predicate = relation["annotation"]["predicate"]
                if predicate not in exclude_predicate_set:
                    predicate_to_paper_relation_list[predicate].append((paper, relation))

        # sort and get predicates with most relations
        if len(predicate_to_paper_relation_list) > top_k:
            predicate_list = [predicate for predicate in predicate_to_paper_relation_list]

            if top_k == 1:
                # max
                key_list = [
                    len(predicate_to_paper_relation_list[predicate])
                    for predicate in predicate_list
                ]
                top_index = max(range(len(predicate_list)), key=lambda i: key_list[i])
                top_index_list = [top_index]

            else:
                # heap sort
                key_list = [
                    (len(predicate_to_paper_relation_list[predicate]), -pi)  # add original index to ensure stable sorting
                    for pi, predicate in enumerate(predicate_list)
                ]
                top_index_list = heapq.nlargest(top_k, range(len(predicate_list)), key=lambda i: key_list[i])

            predicate_to_paper_relation_list = {
                predicate_list[i]: predicate_to_paper_relation_list[predicate_list[i]]
                for i in top_index_list
            }

        # use the first relation with not-yet-selected pmid for each predicate
        predicate_to_paper_relation = {}
        for predicate, paper_relation_list in predicate_to_paper_relation_list.items():
            for paper_relation in paper_relation_list:
                pmid = paper_relation[0].pmid
                if pmid not in self.selected_pmid_set:
                    self.selected_pmid_set.add(pmid)
                    predicate_to_paper_relation[predicate] = paper_relation
                    break
            else:
                predicate_to_paper_relation[predicate] = paper_relation_list[0]

        return predicate_to_paper_relation

    def select_ore_relation(self):
        # spacy
        top_k = 2
        spacy_predicate_to_paper_relation = self.get_ore_top_predicate_to_paper_relation(
            "spacy_ore", top_k, exclude_predicate_set=None,
        )
        predicate_set = set(spacy_predicate_to_paper_relation.keys())

        # openie
        top_k -= len(spacy_predicate_to_paper_relation)
        openie_predicate_to_paper_relation = self.get_ore_top_predicate_to_paper_relation(
            "openie_ore", top_k, exclude_predicate_set=predicate_set,
        )

        for predicate_to_paper_relation in (spacy_predicate_to_paper_relation, openie_predicate_to_paper_relation):
            for _predicate, paper_relation in predicate_to_paper_relation.items():
                self.annotator_to_selected_paper_relation["ore"].append(paper_relation)
        return

    def get_template_type_and_term(self, passage_type):
        if passage_type == "query":
            e1_spec, e2_spec, pmid_spec = self.e1_spec, self.e2_spec, self.pmid_spec
            term_type_to_term = {}

            if pmid_spec:
                term_type_to_term["pmid"] = pmid_spec
                if e1_spec and e2_spec:
                    template_type = "query_ABP"
                    term_type_to_term["entity1"] = e1_spec
                    term_type_to_term["entity2"] = e2_spec
                elif e1_spec:
                    template_type = "query_AP"
                    term_type_to_term["entity"] = e1_spec
                elif e2_spec:
                    template_type = "query_AP"
                    term_type_to_term["entity"] = e2_spec
                else:
                    template_type = "query_P"
            else:
                if e1_spec and e2_spec:
                    template_type = "query_AB"
                    term_type_to_term["entity1"] = e1_spec
                    term_type_to_term["entity2"] = e2_spec
                elif e1_spec:
                    template_type = "query_A"
                    term_type_to_term["entity"] = e1_spec
                elif e2_spec:
                    template_type = "query_A"
                    term_type_to_term["entity"] = e2_spec
                else:
                    template_type = "X"

        elif passage_type == "odds_ratio":
            paper_relation_list = self.annotator_to_selected_paper_relation["odds_ratio"]

            if not paper_relation_list:
                template_type = "X"
                term_type_to_term = {}

            else:
                paper, relation = paper_relation_list[0]

                # pmid
                if self.pmid_spec:
                    template_type = "odds_ratio_X"
                    term_type_to_term = {}
                else:
                    template_type = "odds_ratio_P"
                    term_type_to_term = {"pmid": paper.pmid}

                # variant and disease
                si = relation["sentence_index"]
                sentence_datum = paper.sentence_index_to_sentence_mention[si]
                mention_list = sentence_datum["mention"]

                hi = relation["head_mention"][0]
                ti = relation["tail_mention"][0]
                term_type_to_term["variant"] = mention_list[hi]["name"]
                term_type_to_term["disease"] = mention_list[ti]["name"]

                # OR, CI, p-value
                annotation = relation["annotation"]
                term_type_to_term["OR"] = annotation["OR"]
                term_type_to_term["CI"] = annotation["CI"]
                term_type_to_term["p-value"] = annotation["p-value"]

        elif passage_type == "cre":
            paper_relation_list = self.annotator_to_selected_paper_relation["cre"]

            if not paper_relation_list:
                template_type = "X"
                term_type_to_term = {}

            else:
                paper, relation = paper_relation_list[0]

                # pmid
                if self.pmid_spec:
                    template_type = "X"
                    term_type_to_term = {}
                else:
                    template_type = "P"
                    term_type_to_term = {"pmid": paper.pmid}

                # sentence
                si = relation["sentence_index"]
                sentence_datum = paper.sentence_index_to_sentence_mention[si]
                term_type_to_term["sentence"] = sentence_datum["sentence"]
                mention_list = sentence_datum["mention"]

                # variant and disease
                hi = relation["head_mention"][0]
                ti = relation["tail_mention"][0]
                term_type_to_term["variant"] = mention_list[hi]["name"]
                term_type_to_term["disease"] = mention_list[ti]["name"]

                # relation score and label
                annotation = relation["annotation"]
                term_type_to_term["score"] = annotation["score"]
                label = annotation["relation"]

                if label == "Cause-associated":
                    template_type = f"cre_cause_{template_type}"
                elif label == "In-patient":
                    template_type = f"cre_patient_{template_type}"
                elif label == "Appositive":
                    template_type = f"cre_appositive_{template_type}"
                else:
                    assert False

        elif passage_type == "ore":
            paper_relation_list = self.annotator_to_selected_paper_relation["ore"]

            if not paper_relation_list:
                template_type = "X"
                term_type_to_term = {}

            else:
                paper_relation_list = paper_relation_list[:2]

                if len(paper_relation_list) == 2:
                    # pmid
                    if self.pmid_spec:
                        template_type = "ore_2_X"
                        term_type_to_term = {}
                    else:
                        template_type = "ore_2_P"
                        term_type_to_term = {
                            "pmid1": paper_relation_list[0][0].pmid,
                            "pmid2": paper_relation_list[1][0].pmid,
                        }

                    # triplet
                    for ri, (_paper, relation) in enumerate(paper_relation_list):
                        annotation = relation["annotation"]
                        triplet = f"{annotation['subject']} {annotation['predicate']} {annotation['object']}"
                        term_type_to_term[f"triplet{ri + 1}"] = triplet

                else:
                    # pmid
                    if self.pmid_spec:
                        template_type = "ore_1_X"
                        term_type_to_term = {}
                    else:
                        template_type = "ore_1_P"
                        term_type_to_term = {
                            "pmid": paper_relation_list[0][0].pmid,
                        }

                    # triplet
                    _paper, relation = paper_relation_list[0]
                    annotation = relation["annotation"]
                    triplet = f"{annotation['subject']} {annotation['predicate']} {annotation['object']}"
                    term_type_to_term[f"triplet"] = triplet

        else:
            assert False

        return template_type, term_type_to_term

    def create_passage(self):
        for passage_type in self.passage_type_list:
            template_type, term_type_to_term = self.get_template_type_and_term(passage_type)
            template = random.choice(template_type_to_list[template_type])
            passage, term_type_to_span_list = get_passage_from_template(template, term_type_to_term)
            self.type_to_passage_and_term_span[passage_type] = (passage, term_type_to_span_list)
        return

    def create_text_summary(self):
        text = ""
        term_type_to_span_list = defaultdict(lambda: [])

        for passage_type in self.passage_type_list:
            passage, passage_term_type_to_span_list = self.type_to_passage_and_term_span[passage_type]
            if not passage:
                continue

            if text:
                text += " "

            for term_type, span_list in passage_term_type_to_span_list.items():
                for pos_i, pos_j in span_list:
                    term_type_to_span_list[f"{passage_type}_{term_type}"].append((
                        len(text) + pos_i, len(text) + pos_j,
                    ))

            text += passage

        self.text_summary = {
            "text": text,
            "term_to_span": term_type_to_span_list,
        }
        return

    def create_html_summary(self):
        # legend
        legend_html_list = []
        for passage_type in self.passage_type_list:
            span_class = f"{passage_type}_entity"
            span_style = span_class_to_style[span_class]
            legend_html = f"<span style='{span_style}'> &mdash; {html.escape(passage_type)} </span>"
            legend_html_list.append(legend_html)
        legend_html = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;".join(legend_html_list)
        del legend_html_list

        # passage
        passage_html_list = []

        passage_type_to_highlight_term_type_set = {
            "query": {"entity", "entity1", "entity2"},
            "odds_ratio": {"variant", "disease", "OR", "CI", "p-value"},
            "cre": {"variant", "disease", "sentence"},
            "ore": {"triplet", "triplet1", "triplet2"},
        }
        entity_term_type_set = {"entity", "entity1", "entity2", "variant", "disease"}

        for passage_type in self.passage_type_list:
            passage, term_type_to_span_list = self.type_to_passage_and_term_span[passage_type]
            if not passage:
                continue

            entity_term_span_prefix = f"<span style='{span_class_to_style[passage_type + '_entity']}'>"
            other_term_span_prefix = f"<span style='{span_class_to_style[passage_type]}'>"
            term_span_suffix = "</span>"

            # get sorted list of spans that should be highlighted
            highlight_term_type_set = passage_type_to_highlight_term_type_set[passage_type]
            span_type_list = [
                (span, term_type)
                for term_type, span_list in term_type_to_span_list.items()
                if term_type in highlight_term_type_set
                for span in span_list
            ]
            span_type_list = sorted(span_type_list)

            # replace term spans in passage with html span tags
            passage_html = ""
            last_j = 0
            for (pos_i, pos_j), term_type in span_type_list:
                # text before the term span
                passage_html += html.escape(passage[last_j:pos_i])
                last_j = pos_j

                # term span
                if term_type in entity_term_type_set:
                    term_span_prefix = entity_term_span_prefix
                else:
                    term_span_prefix = other_term_span_prefix
                passage_html += term_span_prefix + html.escape(passage[pos_i:pos_j]) + term_span_suffix

            passage_html += html.escape(passage[last_j:])

            passage_html_list.append(passage_html)

        passage_html = " ".join(passage_html_list)
        del passage_html_list

        # full summary
        self.html_summary = legend_html + "<br />" + passage_html
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmp", type=str)
    arg = parser.parse_args()
    for key, value in vars(arg).items():
        if value is not None:
            logger.info(f"[{key}] {value}")
    return


if __name__ == "__main__":
    main()
    sys.exit()
