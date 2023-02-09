import os
import sys
import logging
from kb_utils import KB
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
    level=logging.INFO,
)


def main():
    # Load KB
    kb_path = "pubmedkb"
    kb = KB(kb_path)
    kb.load_nen()
    kb.load_data()
    kb.load_index()

    # NEN: get entity names similar to user query
    query = "V600E"
    logger.info(f"[NEN] querying names for {query}")
    name_similarity_list = kb.nen.get_names_by_query(
        query,
        case_sensitive=False,
        max_length_diff=1,
        min_similarity=0.85,
        max_names=20,
    )
    for name, similarity in name_similarity_list:
        logger.info(f"{name}: {similarity:.1%}")

    # NEN: get entity types, IDs, frequencies for a name
    name = "V600E"
    logger.info(f"[NEN] searching IDs for {name}")
    type_id_frequency_list = kb.nen.get_ids_by_name(name)
    for _type, _id, frequency in type_id_frequency_list:
        logger.info(f"{name} is tagged by (type: {_type}, ID: {_id}) {frequency:,} times in literature")

    # NEN: get entity aliases, frequencies for a (type, ID) tuple
    _type, _id = "ProteinMutation", "HGVS:p.V600E"
    logger.info(f"[NEN] searching aliases for (type: {_type}, ID: {_id})")
    alias_frequency_list = kb.nen.get_aliases_by_id(_type, _id, max_aliases=10)
    for alias, frequency in alias_frequency_list:
        logger.info(f"(type: {_type}, ID: {_id}) is tagged to {alias} {frequency:,} times in literature")

    # REL: get evidence IDs for a query of entity, entity pair, or PMID
    # entity keys can be type_id_name, type_id, or type_name
    pmid = "29323258"
    e1_key, e1 = "type_name", ("SNP", "rs4925")
    e2_key, e2 = "type_id", ("Disease", "MESH:D012871")
    logger.info(f"[REL] get evidence IDs for ({e1}, {e2})")
    # evidence_id_list = kb.get_evidence_ids_by_pmid(pmid)
    # evidence_id_list = kb.get_evidence_ids_by_entity(e1, key=e1_key)
    evidence_id_list = kb.get_evidence_ids_by_pair((e1, e2), key=(e1_key, e2_key))
    logger.info(f"evidence IDs for ({e1}, {e2}): {evidence_id_list}")

    # REL: get evidence content, i.e., (head, tail, annotation, PMID, sentence), from evidence ID
    # can return annotation_id/sentence_id instead of annotation/sentence
    evidence_id = evidence_id_list[0]
    logger.info(f"[REL] get evidence for evidence ID {evidence_id}")
    head, tail, annotation, pmid, sentence = kb.get_evidence_by_id(
        evidence_id, return_annotation=True, return_sentence=True,
    )
    annotator, annotation = annotation
    logger.info(f"evidence {evidence_id}: head={head} tail={tail}")
    logger.info(f"evidence {evidence_id}: annotator={annotator} annotation={annotation}")
    logger.info(f"evidence {evidence_id}: pmid={pmid} sentence={sentence}")
    return


if __name__ == "__main__":
    main()
    sys.exit()
