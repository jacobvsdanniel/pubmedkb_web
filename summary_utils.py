import random
import os
import csv
import sys
import json
import difflib
import logging
import argparse
from collections import defaultdict
from kb_utils import KB


logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
    level=logging.INFO,
)

## organizing which ore/cre/odds to choose 
def gen_summary_input (detailed_evidence):
    string_list = []
    cre_sorted = []
    odds_sorted = []
    ore_sorted = []
    # logger.info("original list of dictionaries with evidence")
    # print(detailed_evidence)
    cre_ungrouped =  [d for d in detailed_evidence if d["annotator"]=="rbert_cre"]
    # logger.info("cre_ungrouped")
    # print(cre_ungrouped)
    odds_ungrouped = [d for d in detailed_evidence if d["annotator"]=="odds_ratio"]
    # logger.info("odds_ungrouped")
    # print(odds_ungrouped)
    spacy_ungrouped = [d for d in detailed_evidence if d["annotator"]=="spacy_ore"]
    # logger.info("spacy_ungrouped")
    # print(spacy_ungrouped)
    openie_ungrouped = [d for d in detailed_evidence if d["annotator"]=="openie_ore"]
    # logger.info("openie_ungrouped")
    # print(openie_ungrouped)
    if odds_ungrouped:
        if len(odds_ungrouped)==1:
            odds_sorted=odds_ungrouped[0]
        else:
            for l in odds_ungrouped:
                l["odds_ratio"]=l["annotation"][0]
                if l["odds_ratio"] == "x":
                    l["odds_ratio"]=="0"
                l["odds_ratio"]=float(l["odds_ratio"])
                l["odds_ratio_reciprocal"]=1/l["odds_ratio"]
            odds_sorted = max(odds_ungrouped, key=lambda l: l['odds_ratio_reciprocal'])
    if cre_ungrouped:
        if len(cre_ungrouped)==1:
            cre_sorted=cre_ungrouped[0]
        else:
            for l in cre_ungrouped:
                l["rbert_type"]=l["annotation"][0]
                l["rbert_value"]=l["annotation"][1]
                l["rbert_value"]=float(l["rbert_value"].rstrip("%"))
            sortorder={'Cause-associated':2, 'In-patient':1, 'Appositive':0}
            cre_sorted=max(cre_ungrouped, key=lambda x: (sortorder[x["rbert_type"]], x['rbert_value']))
    if len(spacy_ungrouped)>0:
        if len(spacy_ungrouped) ==1: 
            s1=' '.join(spacy_ungrouped[0]["annotation"])
            string_list.append(s1)
            ore_sorted = spacy_ungrouped[0]
        else:
            d = {}
            for l in spacy_ungrouped:
                d.setdefault(l['sentence_id'], []).append(l)
            d_list_sorted = sorted(d.items(), key=lambda l: len(l[1]),reverse=True)
            e1=d_list_sorted[0][1][0]
            s1=' '.join(e1["annotation"])
            string_list.append(s1)
            ore_sorted.append(e1)
            for i in range (1, len(d_list_sorted)):
                if len(ore_sorted)<2:
                    e=d_list_sorted[i][1][0]
                    s = ' '.join(e["annotation"])
                    if s!=string_list[i-1]:
                        ore_sorted.append(e)
                        string_list.append(s)
                else:
                    break
    if openie_ungrouped and len(ore_sorted)<2:
        if len(openie_ungrouped)==1:
            s1=' '.join(openie_ungrouped[0]["annotation"])
            # already has one spacy
            if len(string_list)!=0 and s1!=string_list[0]:
                string_list.append(s1)
                ore_sorted.append(openie_ungrouped[0])
        else:
            d = {}
            for l in openie_ungrouped:
                d.setdefault(l['sentence_id'], []).append(l)
            d_list_sorted = sorted(d.items(), key=lambda l: len(l[1]),reverse=True)
            e1=d_list_sorted[0][1][0]
            s1=' '.join(e1["annotation"])
            string_list.append(s1)
            ore_sorted.append(e1)
            for i in range (1, len(d_list_sorted)):
                if len(ore_sorted)<2:
                    e=d_list_sorted[i][1][0]
                    s = ' '.join(e["annotation"])
                    if s!=string_list[i-1]:
                        ore_sorted.append(e)
                        string_list.append(s)
                else:
                    break
    return odds_sorted, cre_sorted, ore_sorted

## STILL WORKING ON ORGANIZING THIS FUNCTION
## gen_summary_by_none will need evidence_id_list specification
def gen_summary_by_none(evidence_id_list):
    ungrouped_evidence = []
    pair_evidence = defaultdict(lambda: defaultdict(lambda:[]))
    name_evidence = defaultdict(lambda: defaultdict(lambda:[]))

    for evidence_id in evidence_id_list:
        _head, _tail, _annotation_id, _pmid, sentence_id = kb.get_evidence_by_id(
            evidence_id, return_annotation=False, return_sentence=False,
        )
        head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
            evidence_id, return_annotation=True, return_sentence=True,
        )
        head_name = head[2]
        tail_name = tail[2]
        head_tail = sorted([head_name,tail_name])
        head_tail = tuple(head_tail)
        # pair
        pair_evidence[head_tail][annotator].append({  
        "head": head, "tail": tail,
        "annotator": annotator, "annotation": annotation,
        "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        # name
        name_evidence[head_name][annotator].append({  
        "head": head, "tail": tail,
        "annotator": annotator, "annotation": annotation,
        "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        name_evidence[tail_name][annotator].append({  
        "head": head_name, "tail": tail_name,
        "annotator": annotator, "annotation": annotation,
        "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        # evidence that doesnt group (list of dictionary)
        ungrouped_evidence.append({  
        "head": head, "tail": tail,
        "annotator": annotator, "annotation": annotation,
        "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})

    
    ############ sorting pair_evidence ############
    ## input: pair_evidence
    ## output: organized_dict (sorted pair)
    organized_dict = defaultdict(lambda:[])
    non_empty_annotator = []
    for ae in pair_evidence.items():
        order_score = (min(1, len(ae[1]["rbert_cre"])) + min(1, len(ae[1]["odds_ratio"])) + min(2, len(ae[1]["spacy_ore"]))+ min(2 - min(2, len(ae[1]["spacy_ore"])), len(ae[1]["openie_ore"])))
        organized_dict[ae[0]].append(order_score)
        non_empty_annotator = [key for (key, value) in ae[1].items() if len(value) != 0]
        if "spacy_ore" and "openie_ore" in non_empty_annotator:
            annotator_number = len(non_empty_annotator) - 1 
        else:
            annotator_number = len(non_empty_annotator) 
        logger.info("annotator_kind")
        print(annotator_number)
        organized_dict[ae[0]].append(annotator_number)
        setence_id = set()
        for key,value in ae[1].items():
            ## get each list of dictionaries
            for list in value:
                setence_id.add(list["sentence_id"])
        logger.info("setence_id")
        len_sentid = len(setence_id)
        organized_dict[ae[0]].append(len_sentid)

    organized_dict_max = max(organized_dict.items(), key=lambda x: x[1])
    mentions=""
    final_pair_dict=None
    final_name_dict=None
    ## if the selected pair has more than 3 annotators (ore+cre+odds)
    if organized_dict_max[1][1]>=3:
        ## get the evidence ( then proceed to generating summary )
        mentions = organized_dict_max[0]
        final_pair_dict = pair_evidence[mentions]
        logger.info("final_pair_dict")
        print(final_pair_dict)
    ## else: sort the name name_evidence
    else:
        organized_dict = defaultdict(lambda:[])
        non_empty_annotator = []
        for ae in name_evidence.items():
            order_score = (min(1, len(ae[1]["rbert_cre"])) + min(1, len(ae[1]["odds_ratio"])) + min(2, len(ae[1]["spacy_ore"]))+ min(2 - min(2, len(ae[1]["spacy_ore"])), len(ae[1]["openie_ore"])))
            organized_dict[ae[0]].append(order_score)
            non_empty_annotator = [key for (key, value) in ae[1].items() if len(value) != 0]
            logger.info("nameannotator_kind")
            if "spacy_ore" and "openie_ore" in non_empty_annotator:
                annotator_number = len(non_empty_annotator) - 1 
            else:
                annotator_number = len(non_empty_annotator) 
            print(annotator_number)
            organized_dict[ae[0]].append(annotator_number)
            setence_id = set()
            for key,value in ae[1].items():
                for list in value:
                    setence_id.add(list["sentence_id"])
            len_sentid = len(setence_id)
            organized_dict[ae[0]].append(len_sentid)
            logger.info("namefinal_dict")
            print(organized_dict)
            organized_dict_name_max = max(organized_dict.items(), key=lambda x: x[1])
            if organized_dict_name_max[1][1]>=3:
                ## get the top name ( then proceed to generating summary )
                mentions = organized_dict_name_max[0]
                final_name_dict = name_evidence[mentions]
                logger.info("namefinal_pair_dict")
                print(final_name_dict)
                        
    string_list=[]
    rbert=[]
    odds=[]
    ore=[]
    if final_name_dict!=None:
        ## choose which cre, spacy, ore
        for key, value in final_name_dict.items():
            if key == "rbert_cre" and len(final_name_dict["rbert_cre"])>0:
                for l in value:
                    l["rbert_type"]=l["annotation"][0]
                    l["rbert_value"]=l["annotation"][1]
                    l["rbert_value"]=float(l["rbert_value"].rstrip("%"))
                sortorder={'Cause-associated':0, 'In-patient':1, 'Appositive':2}
                sorted_list=sorted(value, key=lambda x: (sortorder[x["rbert_type"]], -x['rbert_value']))
                rbert = sorted_list[0]
                logger.info("rbert")
                print(rbert)
            if key == "odds_ratio" and len(final_name_dict["odds_ratio"])>0:
                for l in value:
                    l["odds_ratio"]=l["annotation"][0]
                    if l["odds_ratio"] == "x":
                        l["odds_ratio"]=="0"
                    l["odds_ratio"]=float(l["odds_ratio"])
                    l["odds_ratio_reciprocal"]=1/l["odds_ratio"]
                sorted_list = sorted(value, key=lambda k: k.get('odds_ratio_reciprocal'),reverse=True)
                odds=sorted_list[0]
                logger.info("all_odds")
                print(sorted_list)
                logger.info("odds")
                print(odds)
            if key== "spacy_ore": 
                logger.info("spacy")
                print(value)
                print(len(value))
                ## if there are more than 2 spacy
                if len(value)>=2:
                    d = {}
                    for l in value:
                        d.setdefault(l['sentence_id'], []).append(l)
                    logger.info("loop")
                    print(d)
                    d_list_sorted = sorted(d.items(), key=lambda l: len(l[1]), reverse=True)
                    logger.info("d_list_sorted0000")
                    print(d_list_sorted)
                    e1=d_list_sorted[0][1][0]
                    logger.info("d_list_sorted1111")
                    print(e1)
                    s1=' '.join(e1["annotation"])
                    string_list.append(s1)
                    ore.append(e1)
                    for i in range (1, len(d_list_sorted)):
                        if len(ore)<2:
                            e=d_list_sorted[i][1][0]
                            s = ' '.join(e["annotation"])
                            if s!=string_list[i-1]:
                                ore.append(e)
                                string_list.append(s)
                        else:
                            break
                else:
                    s1=' '.join(value[0]["annotation"])
                    string_list.append(s1)
                    ore.append(value[0])
                    
        logger.info("string_list")
        print(string_list) 
        logger.info("ore_list")
        print(ore)
        if len(ore)<2:
            openieData = {key: final_name_dict[key] for key in final_name_dict.keys() if key == "openie_ore"}
            logger.info("inside for openie loop")
            print(len(ore))
            print(openieData)
            for key,value in openieData.items():
                ## only one openie
                if len(value)==1:
                    s1=' '.join(value[0]["annotation"])
                    # already has one spacy
                    if len(string_list)!=0 and s1!=string_list[0]:
                        string_list.append(s1)
                        ore.append(value[0])
            ## more than one openie
                else:
                    d = {}
                    for l in value:
                        d.setdefault(l['sentence_id'], []).append(l)
                    logger.info("loop")
                    print(d)
                    d_list_sorted = sorted(d.items(), key=lambda l: len(l[1]), reverse=True)
                    e1=d_list_sorted[0][1][0]
                    s1=' '.join(e1["annotation"])
                    string_list.append(s1)
                    ore.append(e1)
                    for i in range (1, len(d_list_sorted)):
                        if len(ore)<2:
                            e=d_list_sorted[i][1][0]
                            s = ' '.join(e["annotation"])
                            if s!=string_list[i-1]:
                                ore.append(e)
                                string_list.append(s)
                        else:
                            break

    if final_pair_dict!=None:
        ## choose which cre, spacy, ore
        for key, value in final_pair_dict.items():
            if key == "rbert_cre" and len(final_pair_dict["rbert_cre"])>0:
                for l in value:
                    l["rbert_type"]=l["annotation"][0]
                    l["rbert_value"]=l["annotation"][1]
                    l["rbert_value"]=float(l["rbert_value"].rstrip("%"))
                sortorder={'Cause-associated':0, 'In-patient':1, 'Appositive':2}
                sorted_list=sorted(value, key=lambda x: (sortorder[x["rbert_type"]], -x['rbert_value']))
                rbert = sorted_list[0]
                logger.info("rbert")
                print(rbert)
            if key == "odds_ratio" and len(final_pair_dict["odds_ratio"])>0:
                for l in value:
                    l["odds_ratio"]=l["annotation"][0]
                    if l["odds_ratio"] == "x":
                        l["odds_ratio"]=="0"
                    l["odds_ratio"]=float(l["odds_ratio"])
                    l["odds_ratio_reciprocal"]=1/l["odds_ratio"]
                sorted_list = sorted(value, key=lambda k: k.get('odds_ratio_reciprocal'),reverse=True)
                odds=sorted_list[0]
                logger.info("all_odds")
                print(sorted_list)
                logger.info("odds")
                print(odds)
            if key== "spacy_ore": 
                logger.info("spacy")
                print(value)
                print(len(value))
                ## if there are more than 2 spacy
                if len(value)>=2:
                    d = {}
                    for l in value:
                        d.setdefault(l['sentence_id'], []).append(l)
                    logger.info("loop")
                    print(d)
                    d_list_sorted = sorted(d.items(), key=lambda l: len(l[1]), reverse=True)
                    logger.info("d_list_sorted0000")
                    print(d_list_sorted)
                    e1=d_list_sorted[0][1][0]
                    logger.info("d_list_sorted1111")
                    print(e1)
                    s1=' '.join(e1["annotation"])
                    string_list.append(s1)
                    ore.append(e1)
                    for i in range (1, len(d_list_sorted)):
                        if len(ore)<2:
                            e=d_list_sorted[i][1][0]
                            s = ' '.join(e["annotation"])
                            if s!=string_list[i-1]:
                                ore.append(e)
                                string_list.append(s)
                        else:
                            break
                else:
                    s1=' '.join(value[0]["annotation"])
                    string_list.append(s1)
                    ore.append(value[0])
                    
        logger.info("string_list")
        print(string_list) 
        logger.info("ore_list")
        print(ore)
        if len(ore)<2:
            openieData = {key: final_pair_dict[key] for key in final_pair_dict.keys() if key == "openie_ore"}
            logger.info("inside for openie loop")
            print(len(ore))
            print(openieData)
            for key,value in openieData.items():
                ## only one openie
                if len(value)==1:
                    s1=' '.join(value[0]["annotation"])
                    # already has one spacy
                    if len(string_list)!=0 and s1!=string_list[0]:
                        string_list.append(s1)
                        ore.append(value[0])
            ## more than one openie
                else:
                    d = {}
                    for l in value:
                        d.setdefault(l['sentence_id'], []).append(l)
                    logger.info("loop")
                    print(d)
                    d_list_sorted = sorted(d.items(), key=lambda l: len(l[1]), reverse=True)
                    e1=d_list_sorted[0][1][0]
                    s1=' '.join(e1["annotation"])
                    string_list.append(s1)
                    ore.append(e1)
                    for i in range (1, len(d_list_sorted)):
                        if len(ore)<2:
                            e=d_list_sorted[i][1][0]
                            s = ' '.join(e["annotation"])
                            if s!=string_list[i-1]:
                                ore.append(e)
                                string_list.append(s)
                        else:
                            break
    
    logger.info("final_pair_dict")
    print(final_pair_dict)
    logger.info("rbert")
    print(rbert)
    logger.info("odds")
    print(odds)
    logger.info("ore")
    print(ore)

    string_list = []
    cre_sorted = []
    odds_sorted = []
    ore_sorted = []
    cre_ungrouped= []
    spacy_ungrouped = []
    openie_ungrouped =[]
    odds_ungrouped = []
    logger.info("ungrouped_evidence")
    print(ungrouped_evidence)

    if final_pair_dict==None and final_name_dict==None:
        odds_sorted, cre_sorted, ore_sorted = gen_summary_input(ungrouped_evidence)


        
    #     logger.info("inside final")
    #     cre_ungrouped =  [d for d in ungrouped_evidence if d["annotator"]=="rbert_cre"]
    #     odds_ungrouped = [d for d in ungrouped_evidence if d["annotator"]=="odds_ratio"]
    #     spacy_ungrouped = [d for d in ungrouped_evidence if d["annotator"]=="spacy_ore"]
    #     openie_ungrouped = [d for d in ungrouped_evidence if d["annotator"]=="openie_ore"]
    #     logger.info("odds_ungrouped")
    #     print(odds_ungrouped)
    #     logger.info("spacy_ungrouped")
    #     print(spacy_ungrouped)
    #     logger.info("cre_ungrouped")
    #     print(cre_ungrouped)
    #     logger.info("openie_ungrouped")
    #     print(openie_ungrouped)
    #     if odds_ungrouped:
    #         for l in odds_ungrouped:
    #             l["odds_ratio"]=l["annotation"][0]
    #             if l["odds_ratio"] == "x":
    #                 l["odds_ratio"]=="0"
    #             l["odds_ratio"]=float(l["odds_ratio"])
    #             l["odds_ratio_reciprocal"]=1/l["odds_ratio"]
    #         odds_sorted = max(odds_ungrouped, key=lambda l: l['odds_ratio_reciprocal'])
    #         logger.info("odds_sorted")
    #         print(odds_sorted)
    #     if cre_ungrouped:
    #         for l in cre_ungrouped:
    #             l["rbert_type"]=l["annotation"][0]
    #             l["rbert_value"]=l["annotation"][1]
    #             l["rbert_value"]=float(l["rbert_value"].rstrip("%"))
    #         sortorder={'Cause-associated':2, 'In-patient':1, 'Appositive':0}
    #         cre_sorted=max(value, key=lambda x: (sortorder[x["rbert_type"]], x['rbert_value']))
    #         logger.info("rbert_sorted")
    #         print(cre_sorted)
    #     logger.info("len spacy_ungrouped")
    #     print(len(spacy_ungrouped))
    #     if len(spacy_ungrouped)>0:
    #         if  len(spacy_ungrouped) ==1: 
    #             s1=' '.join(spacy_ungrouped[0]["annotation"])
    #             string_list.append(s1)
    #             ore_sorted = spacy_ungrouped[0]
    #             # ore_sorted.append(spacy_ungrouped[0])
    #         else:
    #             d = {}
    #             for l in spacy_ungrouped:
    #                 d.setdefault(l['sentence_id'], []).append(l)
    #             logger.info("loop")
    #             print(d)
    #             for l in d.items():
    #                 logger.info("k")
    #                 print(l)
    #                 logger.info("k[1]")
    #                 print(l[1])
    #                 logger.info("lenk1")
    #                 print(len(l[1]))
    #             d_list_sorted = sorted(d.items(), key=lambda l: len(l[1]),reverse=True)
    #             logger.info("l")
    #             print(d_list_sorted)
    #             e1=d_list_sorted[0][1][0]
    #             logger.info("d_list_sorted1111")
    #             print(e1)
    #             s1=' '.join(e1["annotation"])
    #             string_list.append(s1)
    #             ore_sorted.append(e1)
    #             # ore_sorted.append(e1)
    #             logger.info("len d")
    #             print(len(d_list_sorted))
    #             logger.info ("len ore sorted")
    #             print(len(ore_sorted))
    #             for i in range (1, len(d_list_sorted)):
    #                 if len(ore_sorted)<2:
    #                     e=d_list_sorted[i][1][0]
    #                     s = ' '.join(e["annotation"])
    #                     if s!=string_list[i-1]:
    #                         ore_sorted.append(e)
    #                         string_list.append(s)
    #                 else:
    #                     break
    #     if openie_ungrouped and len(ore_sorted)<2:
    #         if len(openie_ungrouped)==1:
    #             s1=' '.join(openie_ungrouped[0]["annotation"])
    #             # already has one spacy
    #             if len(string_list)!=0 and s1!=string_list[0]:
    #                 string_list.append(s1)
    #                 ore_sorted.append(openie_ungrouped[0]["annotation"])
    #             # dont have any spacy
    #             # else:
    #             #     string_list.append(s1)
    #             #     ore.append(value[0])
    #         ## more than one openie
    #         else:
    #             d = {}
    #             for l in openie_ungrouped:
    #                 d.setdefault(l['sentence_id'], []).append(l)
    #             logger.info("loop")
    #             print(d)
    #             d_list_sorted = sorted(d.items(), key=lambda l: len(l[1]),reverse=True)
    #             e1=d_list_sorted[0][1][0]
    #             s1=' '.join(e1[0]["annotation"])
    #             string_list.append(s1)
    #             ore_sorted.append(e1)
    #             for i in range (1, len(d_list_sorted)):
    #                 if len(ore_sorted)<2:
    #                     e=d_list_sorted[i][1][0]
    #                     s = ' '.join(e["annotation"])
    #                     if s!=string_list[i-1]:
    #                         ore_sorted.append(e)
    #                         string_list.append(s)
    #                 else:
    #                     break
    #         logger.info("string list")
    #         print(string_list)
    # logger.info("odds_sorted")
    # print(odds_sorted)
    # logger.info("cre_sorted")
    # print(cre_sorted)
    # logger.info("ore_sorted")
    # print(ore_sorted)

    triplet_list=[""]
    # intro_list=[""]
    # odds_list=[""]
    # rbert_list=[""]
# pair version summary
    if (odds or rbert or ore) and final_pair_dict!=None and final_name_dict==None:
        sent1="Based on our search results, relation exists between " +  str(mentions[0]) + " and " + str(mentions[1]) + ". "
        sent2="Relations occur between "+ str(mentions[0]) + " and " + str(mentions[1]) + " as shown from our search. The exact sources are demonstrated using PMID. "
        sent3=str(mentions[0]) + " and " + str(mentions[1]) + " relate to each other in the following ways."
        intro_list=[sent1,sent2,sent3]
        intro_list=random.choice(intro_list)
        if odds:
            sent1="The odds ratio found between these two entities in PMID: " + str(odds["pmid"]) + " is " + str(odds["odds_ratio"]) + " (CI: " + str(odds["annotation"][1]) + ", p-value: "+  str(odds["annotation"][2])+ "). "
            sent2="They have an " + str(odds["odds_ratio"])  + " (CI: " + str(odds["annotation"][1]) + ", p-value: "+  str(odds["annotation"][2]) + ")"+" odds ratio (PMID: " + str(odds["pmid"]) + "). "
            odds_list=[sent1,sent2]
            odds_list=random.choice(odds_list)
        if rbert:
            mention1=""
            mention2=""
            if rbert["head"][2] == "Disease" and (rbert["tail"][2] == "SNP" or rbert["tail"][2] == "ProteinMutation" or rbert["tail"][2] =="CopyNumberVariant" or rbert["tail"][2] == "DNAMutation"):
                # switch head and tail 
                mention1=rbert["tail"][2]
                mention2=rbert["head"][2]
            else:
                mention1=rbert["head"][2]
                mention2=rbert["tail"][2]
            if rbert["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " +  str(mention1) +" and " + str(mention2)+ " with a confidence of " + '{}'.format(["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(rbert["pmid"])+") " + 'that captures the relations: "' + rbert["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID " + str(rbert["pmid"]) + ': "'+rbert["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(rbert["pmid"])+")"+ ': "'+ rbert["sentence"] + '" our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(["annotation"][1])+ ". "
                rbert_list=[sent1,sent2,sent3]
                rbert_list=random.choice(rbert_list)
            if rbert["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(rbert["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID:" +str(rbert["pmid"])+") " + 'that captures the relations: "' + rbert["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(rbert["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID" + str(rbert["pmid"]) + ": '"+rbert["sentence"] + "'"
                sent3= 'As claimed by "'+ rbert["sentence"] +'" (' +str(rbert["pmid"])+") we are " + '{}'.format(rbert["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
                rbert_list=[sent1,sent2,sent3]
                rbert_list=random.choice(rbert_list)
            if rbert["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(rbert["annotation"][0])+ " confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(rbert["pmid"])+") " + 'that captures the relations: "' + rbert["sentence"] +'" '
                sent2= "It is " + '{}'.format(rbert["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + " as evidenced by '" + rbert["sentence"] + "' (PMID: "+str(rbert["pmid"])+". "
                sent3= "According to the sentence: '" + rbert["sentence"]+ "' (PMID: " + str(rbert["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
                rbert_list=[sent1,sent2,sent3]
                rbert_list=random.choice(rbert_list)
        if ore:
            logger.info("len ore")
            print(len(ore))
            print(ore)
            if len(ore)==2:
                relation1 = ' '.join(ore[0]["annotation"])
                relation2= ' '.join(ore[1]["annotation"])
                sent1='Moreover, there are also other relations found, which includes the following. "' + relation1 + '." "' + relation2+ '." '
                sent2='Notably, further relations between these two entities are discovered. "' + relation1 + '." "' + relation2+ '." '
                sent3= mentions[0] + " and " + mentions[1] + ' also contain further relations. "' + relation1 + '." "' + relation2+ '." '
                triplet_list=[sent1,sent2,sent3]
                triplet_list=random.choice(triplet_list)
            else:
                sent1='We also found "'+ ' '.join(ore[0]["annotation"]) + '." ' 
                sent2='"'+ ' '.join(ore[0]["annotation"]) + '." '
                sent3="In addition, " +'"'+ ' '.join(ore[0]["annotation"]) + '." ' 
                triplet_list=[sent1,sent2,sent3]
                triplet_list=random.choice(triplet_list)

# A version summary
    if (odds or rbert or ore) and final_name_dict!=None :
        combined_mentions=set()
        if odds:
            sent1="The odds ratio found between " + odds["head"][2] + " and " + odds["tail"][2] + " in PMID: " + str(odds["pmid"]) + " is " + str(odds["annotation"][0]) + " (CI: " + str(odds["annotation"][1]) + ", p-value: "+  str(odds["annotation"][2])+ "). "
            sent2=odds["head"][2] + " and " + odds["tail"][2]  + " have an " + str(odds["annotation"][0])  + " (CI: " + str(odds["annotation"][1]) + ", p-value: "+  str(odds["annotation"][2]) + ")"+" odds ratio (PMID: " + str(odds["pmid"]) + "). "
            odds_list=[sent1,sent2]
            if odds["head"][2]==mentions[0]:
                combined_mentions.add(odds["tail"][2])
            else:
                combined_mentions.add(odds["head"][2])
            odds_list=random.choice(odds_list)
        if rbert:
            mention1=rbert["head"][2]
            mention2=rbert["head"][2]
            if rbert["head"][0] == "Disease" and (rbert["tail"][0] == "SNP" or rbert["tail"][0] == "ProteinMutation" or rbert["tail"][0] =="CopyNumberVariant" or rbert["tail"][0] == "DNAMutation"):
                # switch head and tail           
                tmp=mention1
                mention1=mention2
                mention2=tmp
            if rbert["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " +  str(mention1) +" and " + str(mention2)+ " with a confidence of " + '{}'.format(rbert["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(rbert["pmid"])+") " + 'that captures the relations: "' + rbert["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(rbert["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID " + str(rbert["pmid"]) + ': "'+rbert["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(rbert["pmid"])+")"+ ': "'+ rbert["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(rbert["annotation"][1])+ ". "
            if rbert["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(rbert["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID:" +str(rbert["pmid"])+") " + 'that captures the relations: "' + rbert["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(rbert["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID" + str(rbert["pmid"]) + ': "'+rbert["sentence"] + '" '
                sent3= 'As claimed by "'+ rbert["sentence"] +'" ' + '{}'.format(rbert["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
            if rbert["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(rbert["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + rbert["sentence"] +'" '
                sent2= "It is " + '{}'.format(rbert["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + ' as evidenced by "' + rbert["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+'." '
                sent3= 'According to the sentence: "' + rbert["sentence"]+ "' (PMID: " + str(rbert["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
            if rbert["head"][2]==mentions[0]:
                combined_mentions.add(rbert["tail"][2])
            else:
                combined_mentions.add(rbert["head"][2])
        if ore:
            if len(ore)==2:
                relation1 = ' '.join(ore[0]["annotation"])
                relation2= ' '.join(ore[1]["annotation"])
                sent1='Moreover, there are also other relations found, which includes the following. "' + str(relation1) + '" (PMID: ' +  ore[0]["pmid"]+ '." and "' + str(relation2) + '" (PMID: ' +  ore[1]["pmid"]+'.)" '
                sent2='Notably, further relations between these two entities are discovered. "' + str(relation1) + '" (PMID: ' +  ore[0]["pmid"]+ '." and "' + str(relation2) + '" (PMID: ' +  ore[1]["pmid"]+'.)" '
                sent3= "We also found other relations with " + mentions[0] + ' "' + relation1 + '." "' + relation2+ '." '
                triplet_list=[sent1,sent2,sent3]
                triplet_list=random.choice(triplet_list)
                if ore[0]["head"][2]==mentions[0]:
                    combined_mentions.add(ore[0]["tail"][2])
                else:
                    combined_mentions.add(ore[0]["head"][2])
                if ore[1]["head"][2]==mentions[0]:
                    combined_mentions.add(ore[1]["tail"][2])
                else:
                    combined_mentions.add(ore[1]["head"][2])
            else:
                sent1='We also found "'+ ' '.join(ore[0]["annotation"]) + '." ' 
                sent2='"'+ ' '.join(ore[0]["annotation"]) + '." '
                sent3="In addition, " +'"'+ ' '.join(ore[0]["annotation"]) + '." ' 
                triplet_list=[sent1,sent2,sent3]
                triplet_list=random.choice(triplet_list)
                if ore[0]["head"][2]==mentions[0]:
                    combined_mentions.add(ore[0]["tail"][2])
                else:
                    combined_mentions.add(ore[0]["head"][2])
        final_combine=list(combined_mentions)
        final_combine= ", ".join(final_combine[:-1]) + " and " + final_combine[-1]
        sent1="Based on our search results, relation exists between " +  mention1 + " and these prominent mentions: " + final_combine + ". "
        sent2= mention1 + " relates to "  + final_combine + ". "
        sent3= "We found that these mentions-" + final_combine+ "-" + "relate(s) to " + mention1 +". " 
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        return final_summary

    logger.info("intro_list")
    print(intro_list)
    logger.info("rbert_list")
    print(rbert_list)
    logger.info("triplet_list")
    print(triplet_list)
    logger.info("odds_list")
    print(odds_list)

    summary=(intro_list)+(odds_list)+(rbert_list)+(triplet_list)
    final_summary = ''.join(str(v) for v in summary)
    logger.info("final_summary")
    print(final_summary)

## AP
def gen_summary_by_entity_pmid(kb,evidence_id_list,target):
    combined_mentions = set()
    detailed_evidence = [] 
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    for evidence_id in evidence_id_list:
        _head, _tail, _annotation_id, _pmid, sentence_id = kb.get_evidence_by_id(
        evidence_id, return_annotation=False, return_sentence=False)
        head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
            evidence_id, return_annotation=True, return_sentence=True)
        if (target[0] == "type_id_name" or target[0] == "type_name"):
            if (target[1][2]==head[2] or target[1][2]==tail[2]) and pmid==target[2]:
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        ## id id combo
        elif (target[0] == "type_id"):
            if (target[1][1]==head[1] or target[1][1]==tail[1]) and pmid==target[2]:
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
    odds_sorted, cre_sorted, ore_sorted = gen_summary_input(detailed_evidence)
    if (odds_sorted or cre_sorted or ore_sorted):
        mention1=""
        mention2=""
        if odds_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in odds_sorted["head"]:
                    mention1 = odds_sorted["head"][2]
                    mention2 = odds_sorted["tail"][2]
                elif target[1][2] in odds_sorted["tail"]:
                    mention1 = odds_sorted["tail"][2]
                    mention2 = odds_sorted["head"][2]
            elif target[0] == "type_id":
                if target[1][1] in odds_sorted["head"]:
                    logger.info("inside second loop h")
                    mention1 = odds_sorted["head"][1]
                    mention2 = odds_sorted["tail"][2]
                elif target[1][1] in odds_sorted["tail"]:
                    logger.info("inside second loop t")
                    mention1= odds_sorted["tail"][1]
                    mention2=odds_sorted["head"][2]
            sent1="The odds ratio found between " + mention1 + " and " + mention2+ " is " + str(odds_sorted["annotation"][0]) + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2])+ "). "
            sent2=mention1+ " and " + mention2 + " have an " + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio. "
            odds_list=[sent1,sent2]
            combined_mentions.add(mention2)
            odds_list=random.choice(odds_list)
        if cre_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in cre_sorted["head"]:
                    mention1 = cre_sorted["head"][2]
                    mention2 = cre_sorted["tail"][2]
                    if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                        tmp=mention1
                        mention1=mention2
                        mention2=tmp
                        combined_mentions.add(mention1)
                    else:
                        combined_mentions.add(mention2)
                elif target[2] in cre_sorted["tail"]:
                    mention1= cre_sorted["tail"][2]
                    mention2=cre_sorted["head"][2]
                    if cre_sorted["tail"][0] == "Disease" and (cre_sorted["head"][0] == "SNP" or cre_sorted["head"][0] == "ProteinMutation" or cre_sorted["head"][0] =="CopyNumberVariant" or cre_sorted["head"][0] == "DNAMutation"):
                        tmp=mention1
                        mention1=mention2
                        mention2=tmp
                        combined_mentions.add(mention1)
                    else:
                        combined_mentions.add(mention2)
            elif target[0] == "type_id":
                if target[1][1] in cre_sorted["head"]:
                    mention1 = cre_sorted["head"][1]
                    mention2 = cre_sorted["tail"][1]
                    if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                        tmp=mention1
                        mention1=mention2
                        mention2=tmp
                        combined_mentions.add(mention1)
                    else:
                        combined_mentions.add(mention2)
                elif target[1][1] in cre_sorted["tail"]:
                    mention1= cre_sorted["tail"][1]
                    mention2=cre_sorted["head"][1]
                    if cre_sorted["tail"][0] == "Disease" and (cre_sorted["head"][0] == "SNP" or cre_sorted["head"][0] == "ProteinMutation" or cre_sorted["head"][0] =="CopyNumberVariant" or cre_sorted["head"][0] == "DNAMutation"):
                        tmp=mention1
                        mention1=mention2
                        mention2=tmp
                        combined_mentions.add(mention1)
                    else:
                        combined_mentions.add(mention2)
            if cre_sorted["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " +  str(mention1) +" and " + str(mention2)+ " with a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "
            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID" + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= 'As claimed by "'+ cre_sorted["sentence"] +'" ' + '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + ' as evidenced by "' + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+'." '
                sent3= 'According to the sentence: "' + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
        if ore_sorted:
            mention3=""
            mention4=""
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in ore_sorted[0]["head"]:
                    mention1 = ore_sorted[0]["head"][2]
                    mention2 = ore_sorted[0]["tail"][2]
                elif target[1][2] in ore_sorted["tail"]:
                    mention1= ore_sorted[0]["tail"][2]
                    mention2=ore_sorted[0]["head"][2]
            elif target[0] == "type_id":
                if target[1][1] in ore_sorted[0]["head"]:
                    mention1 = ore_sorted[0]["head"][1]
                    mention2 = ore_sorted[0]["tail"][2]
                elif target[1][1] in ore_sorted[0]["tail"]:
                    mention1= ore_sorted[0]["tail"][1]
                    mention2=ore_sorted[0]["head"][2]
            combined_mentions.add(mention2)
            if len(ore_sorted)==2:
                if target[0] == "type_id_name" or target[0] == "type_name":
                    if target[1][2] in ore_sorted[1]["head"]:
                        mention3 = ore_sorted[1]["head"][2]
                        mention4 = ore_sorted[1]["tail"][2]
                    elif target[1][2] in ore_sorted[1]["tail"]:
                        mention3= ore_sorted[1]["tail"][2]
                        mention4=ore_sorted[1]["head"][2]
                elif target[0] == "type_id":
                    if target[1][1] in ore_sorted[1]["head"]:
                        mention3 = ore_sorted[1]["head"][1]
                        mention4 = ore_sorted[1]["tail"][2]
                    elif target[1][1] in ore_sorted[1]["tail"]:
                        mention3 = ore_sorted[1]["tail"][1]
                        mention4 = ore_sorted[1]["head"][2]
                relation1 = ' '.join(ore_sorted[0]["annotation"])
                relation2= ' '.join(ore_sorted[1]["annotation"])
                combined_mentions.add(mention4)
                sent1="Moreover, there are also other relations found, which includes the following: " + str(mention1) + " & " + str(mention2)  + " and " + str(mention3) + " & " +  str(mention4) + '." "'+ str(relation1) + '." and "' + str(relation2) + '." '
                sent2='Notably, further relations between the aforementioned entities are discovered. "' + str(relation1) + '." "' + str(relation2) +'." '
                sent3= str(mention1) + " & " + str(mention2)  + " and " + str(mention3) + " & " + str(mention4)+ ' also contain further relations. "'+ str(relation1) + '." and "' + str(relation2) +'." '
                # sent1='Moreover, there are also other relations found in this PMID: ' + target+ ', which includes the following. "' + relation1 + '." "' + relation2+ '." '
                # sent2='Notably, in this PMID, further relations between these two entities are discovered. "' + relation1 + '." "' + relation2+ '." '
                # sent3= 'PMID: ' + target + ' also entails relations: "' + relation1 + '" and "'+ relation2 +'."'
            else:
                sent1='We also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
        final_combine=list(combined_mentions)
        if len(final_combine)>1:
            final_combine= ", ".join(final_combine[:-1]) + " and " + final_combine[-1]
        else:
            final_combine="".join(final_combine)
        sent1="Based on our search results, in PMID: " + target[2]+ ", relation exists between " +  mention1 + " and these prominent mentions: " + final_combine + ". "
        sent2= "From PMID: " + target[2] + ", " + mention1 + " relates to "  + final_combine + ". "
        sent3= "We found that these mentions-" + final_combine+ "-" + "relate(s) to " + mention1 +" in PMID: " +target[2] 
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        logger.info("summary for pmid and single entity: 23644288 & skin lesions")
        return final_summary
    return 

## A
def gen_summary_by_entity(kb,evidence_id_list,target):
    combined_mentions = set()
    detailed_evidence = [] 
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    for evidence_id in evidence_id_list:
        _head, _tail, _annotation_id, _pmid, sentence_id = kb.get_evidence_by_id(
        evidence_id, return_annotation=False, return_sentence=False)
        head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
            evidence_id, return_annotation=True, return_sentence=True)
        if (target[0] == "type_id_name" or target[0] == "type_name"):
            if (target[1][2]==head[2] or target[1][2]==tail[2]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        ## id id combo
        elif (target[0] == "type_id"):
            if (target[1][1]==head[1] or target[1][1]==tail[1]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
    odds_sorted, cre_sorted, ore_sorted = gen_summary_input(detailed_evidence)
    if (odds_sorted or cre_sorted or ore_sorted):
        mention1=""
        mention2=""
        if odds_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in odds_sorted["head"]:
                    mention1 = odds_sorted["head"][2]
                    mention2 = odds_sorted["tail"][2]
                elif target[1][2] in odds_sorted["tail"]:
                    mention1 = odds_sorted["tail"][2]
                    mention2 = odds_sorted["head"][2]
            elif target[0] == "type_id":
                if target[1][1] in odds_sorted["head"]:
                    mention1 = odds_sorted["head"][1]
                    mention2 = odds_sorted["tail"][2]
                elif target[1][1] in odds_sorted["tail"]:
                    mention1= odds_sorted["tail"][1]
                    mention2=odds_sorted["head"][2]
            sent1="The odds ratio found between " + mention1 + " and " + mention2+ " in PMID: " + str(odds_sorted["pmid"]) + " is " + str(odds_sorted["annotation"][0]) + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2])+ "). "
            sent2=mention1+ " and " + mention2 + " have an " + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio (PMID: " + str(odds_sorted["pmid"]) + "). "
            odds_list=[sent1,sent2]
            combined_mentions.add(mention2)
            odds_list=random.choice(odds_list)
        if cre_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in cre_sorted["head"]:
                    mention1 = cre_sorted["head"][2]
                    mention2 = cre_sorted["tail"][2]
                    if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                        tmp=mention1
                        mention1=mention2
                        mention2=tmp
                        combined_mentions.add(mention1)
                    else:
                        combined_mentions.add(mention2)
                elif target[2] in cre_sorted["tail"]:
                    mention1= cre_sorted["tail"][2]
                    mention2=cre_sorted["head"][2]
                    if cre_sorted["tail"][0] == "Disease" and (cre_sorted["head"][0] == "SNP" or cre_sorted["head"][0] == "ProteinMutation" or cre_sorted["head"][0] =="CopyNumberVariant" or cre_sorted["head"][0] == "DNAMutation"):
                        tmp=mention1
                        mention1=mention2
                        mention2=tmp
                        combined_mentions.add(mention1)
                    else:
                        combined_mentions.add(mention2)
            elif target[0] == "type_id":
                if target[1][1] in cre_sorted["head"]:
                    mention1 = cre_sorted["head"][1]
                    mention2 = cre_sorted["tail"][2]
                    if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                        tmp=mention1
                        mention1=mention2
                        mention2=tmp
                        combined_mentions.add(mention1)
                    else:
                        combined_mentions.add(mention2)
                elif target[1][1] in cre_sorted["tail"]:
                    mention1= cre_sorted["tail"][1]
                    mention2=cre_sorted["head"][2]
                    if cre_sorted["tail"][0] == "Disease" and (cre_sorted["head"][0] == "SNP" or cre_sorted["head"][0] == "ProteinMutation" or cre_sorted["head"][0] =="CopyNumberVariant" or cre_sorted["head"][0] == "DNAMutation"):
                        tmp=mention1
                        mention1=mention2
                        mention2=tmp
                        combined_mentions.add(mention1)
                    else:
                        combined_mentions.add(mention2)
            if cre_sorted["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " +  str(mention1) +" and " + str(mention2)+ " with a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + "that captures the relations: '" + cre_sorted["sentence"] +"' "
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "
            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID" + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= 'As claimed by "'+ cre_sorted["sentence"] +'" ' + '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + ' as evidenced by "' + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+'." '
                sent3= 'According to the sentence: "' + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
        if ore_sorted:
            mention3=""
            mention4=""
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in ore_sorted[0]["head"]:
                    mention1 = ore_sorted[0]["head"][2]
                    mention2 = ore_sorted[0]["tail"][2]
                elif target[1][2] in ore_sorted[0]["tail"]:
                    mention1= ore_sorted[0]["tail"][2]
                    mention2=ore_sorted[0]["head"][2]
            elif target[0] == "type_id":
                if target[1][1] in ore_sorted[0]["head"]:
                    mention1 = ore_sorted[0]["head"][1]
                    mention2 = ore_sorted[0]["tail"][2]
                elif target[1][1] in ore_sorted[0]["tail"]:
                    mention1= ore_sorted[0]["tail"][1]
                    mention2=ore_sorted[0]["head"][2]
            combined_mentions.add(mention2)
            if len(ore_sorted)==2:
                if target[0] == "type_id_name" or target[0] == "type_name":
                    if target[1][2] in ore_sorted[1]["head"]:
                        mention3 = ore_sorted[1]["head"][2]
                        mention4 = ore_sorted[1]["tail"][2]
                    elif target[1][2] in ore_sorted[1]["tail"]:
                        mention3= ore_sorted[1]["tail"][2]
                        mention4=ore_sorted[1]["head"][2]
                elif target[0] == "type_id":
                    if target[1][1] in ore_sorted[1]["head"]:
                        mention3 = ore_sorted[1]["head"][1]
                        mention4 = ore_sorted[1]["tail"][2]
                    elif target[1][1] in ore_sorted[1]["tail"]:
                        mention3 = ore_sorted[1]["tail"][1]
                        mention4 = ore_sorted[1]["head"][2]
                relation1 = ' '.join(ore_sorted[0]["annotation"])
                relation2= ' '.join(ore_sorted[1]["annotation"])
                combined_mentions.add(mention4)
                sent1="Moreover, there are also other relations found, which includes the following: " + str(mention1) + " & " + str(mention2)  + " and " + str(mention3) + ' & ' +  str(mention4) + '. "'+ str(relation1) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ') and "' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+'). '
                sent2='Notably, further relations between the aforementioned entities are discovered. ' + str(mention1) + " & " + str(mention2)  + " and " + str(mention3) + ' & '  +  str(mention4) + '. "'+ str(relation1) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ') and "' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+'). '
                sent3= str(mention1) + " & " + str(mention2)  + " and " + str(mention3) + " & " + str(mention4)+ ' also contain further relations. "'+ str(mention2)  + ' & '  + str(mention3) + '. "' +  str(mention4) + '." "'+ str(relation1) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ') and "' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+'). '
                # sent1='Moreover, there are also other relations found in this PMID: ' + target+ ', which includes the following. "' + relation1 + '." "' + relation2+ '." '
                # sent2='Notably, in this PMID, further relations between these two entities are discovered. "' + relation1 + '." "' + relation2+ '." '
                # sent3= 'PMID: ' + target + ' also entails relations: "' + relation1 + '" and "'+ relation2 +'."'
            else:
                sent1='We also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + "). "
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ". "
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + "). "
            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
        final_combine=list(combined_mentions)
        final_combine= ", ".join(final_combine[:-1]) + " and " + final_combine[-1]
        sent1="Based on our search results, relation exists between " +  mention1 + " and these prominent mentions: " + final_combine + ". "
        sent2= mention1 + " relates to "  + final_combine + ". "
        sent3= "We found that these mentions-" + final_combine+ "-" + "relate(s) to " + mention1 +". " 
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        logger.info("summary for single entity: MESH:D012871")
        return final_summary
    return 

## AB
def gen_summary_by_pair(kb,evidence_id_list,target):
    detailed_evidence = [] 
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    for evidence_id in evidence_id_list:
        _head, _tail, _annotation_id, _pmid, sentence_id = kb.get_evidence_by_id(
        evidence_id, return_annotation=False, return_sentence=False)
        head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
            evidence_id, return_annotation=True, return_sentence=True)
        ## name name combo
        if (target[0] == "type_id_name" or target[0] == "type_name") and (target[2] == "type_id_name" or target[2] == "type_name"):
            if (target[1][2]==head[2] or target[1][2]==tail[2]) and (target[3][2]==head[2] or target[3][2]==tail[2]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        ## id id combo
        elif (target[0] == "type_id") and (target[2] == "type_id"):
            if (target[1][1]==head[1] or target[1][1]==tail[1]) and (target[3][1]==head[1] or target[3][1]==tail[1]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        ## id name combo
        elif (target[0] == "type_id") and (target[2] == "type_id_name" or target[2] == "type_name"):
            if (target[1][1]==head[1] or target[1][1]==tail[1]) and (target[3][2]==head[2] or target[3][2]==tail[2]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        ## name id combo
        elif (target[0] == "type_id_name" or target[0] == "type_name") and (target[2] == "type_id"):
            if (target[1][2]==head[2] or target[1][2]==tail[2]) and (target[3][1]==head[1] or target[3][1]==tail[1]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
    odds_sorted, cre_sorted, ore_sorted = gen_summary_input(detailed_evidence)
    if (odds_sorted or cre_sorted or ore_sorted):
        mention1=""
        mention2=""
        if odds_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                mention1 = odds_sorted["head"][2]
            if target[0] == "type_id" :
                mention1 = odds_sorted["head"][1]
            if target[2] == "type_id_name" or target[2] == "type_name":
                mention2 = odds_sorted["tail"][2]
            if target[2] == "type_id" :
                mention2 = odds_sorted["tail"][1]
            sent1="The odds ratio found between " + mention1 + " and " + mention2+ " in PMID: " + str(odds_sorted["pmid"]) + " is " + str(odds_sorted["annotation"][0]) + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2])+ "). "
            sent2=mention1+ " and " + mention2 + " have an " + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio (PMID: " + str(odds_sorted["pmid"]) + "). "
            odds_list=[sent1,sent2]
            odds_list=random.choice(odds_list)
        if cre_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                mention1 = odds_sorted["head"][2]
            if target[0] == "type_id" :
                mention1 = odds_sorted["head"][1]
            if target[2] == "type_id_name" or target[2] == "type_name":
                mention2 = odds_sorted["tail"][2]
            if target[2] == "type_id" :
                mention2 = odds_sorted["tail"][1]
            if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                # switch head and tail           
                tmp=mention1
                mention1=mention2
                mention2=tmp
            if cre_sorted["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " +  str(mention1) +" and " + str(mention2)+ " with a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + "that captures the relations: '" + cre_sorted["sentence"] +"' "
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "
            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finding shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID" + str(cre_sorted["pmid"]) + ": '"+cre_sorted["sentence"] + "'"
                sent3= "As claimed by '"+ cre_sorted["sentence"] +"' PMID: (" +str(cre_sorted["pmid"])+"), we are " + '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + " as evidenced by '" + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+". "
                sent3= "According to the sentence: '" + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
        if ore_sorted:
            if len(ore_sorted)==2:
                mention1=ore_sorted[0]["head"][2]
                mention2=ore_sorted[0]["tail"][2]
                relation1 = ' '.join(ore_sorted[0]["annotation"])
                relation2= ' '.join(ore_sorted[1]["annotation"])
                sent1='Moreover, there are also relations found between these two entities, which includes the following. "' + relation1 + '" (PMID: ' + ore_sorted[0]["pmid"] +'). "' + relation2+ '" (PMID: ' + ore_sorted[1]["pmid"] +').'
                sent2='Notably,further relations between' + mention1 + " and " + mention2 +  'are present. "' + relation1 + '" (PMID: ' + ore_sorted[0]["pmid"] +'). "' + relation2+ '" (PMID: ' + ore_sorted[1]["pmid"] +').'
                sent3= 'Btween these two entities, prior literature also entails that "' + + relation1 + '" (PMID: ' + ore_sorted[0]["pmid"] +') and "' + relation2+ '" (PMID: ' + ore_sorted[1]["pmid"] +').'
            else:
                mention1=ore_sorted[0]["head"][2]
                mention2=ore_sorted[0]["tail"][2]
                sent1='We also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ". "
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ". "
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ". "
            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
        sent1="Based on our search results, relation exists between " +  mention1 + " and " + mention2 + ". "
        sent2="Relations occur between "+ mention1 + " and " + mention2 + " as shown from our search. The exact sources are demonstrated by PMID. "
        sent3=mention1 + " and " + mention2 + " relate to each other in the following ways."
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        logger.info("summary for pmid and single entity: 23644288 & skin lesions")
        return final_summary
    return 
    
## P
def gen_summary_by_pmid(kb,evidence_id_list,target):
    combined_mentions = set()
    detailed_evidence = [] 
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    for evidence_id in evidence_id_list:
        _head, _tail, _annotation_id, _pmid, sentence_id = kb.get_evidence_by_id(
        evidence_id, return_annotation=False, return_sentence=False)
        head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
            evidence_id, return_annotation=True, return_sentence=True)
        if pmid == target:
            detailed_evidence.append({  
            "head": head, "tail": tail,
            "annotator": annotator, "annotation": annotation,
            "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
    odds_sorted, cre_sorted, ore_sorted = gen_summary_input(detailed_evidence)
    if (odds_sorted or cre_sorted or ore_sorted):
        if odds_sorted:
            mention1=odds_sorted["head"][2]
            mention2=odds_sorted["tail"][2]
            combined_mentions.add(mention1)
            combined_mentions.add(mention2)
            sent1="The odds ratio found between " + mention1 + " and " + mention2+ " in PMID: " + str(odds_sorted["pmid"]) + " is " + str(odds_sorted["annotation"][0]) + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2])+ "). "
            sent2=mention1+ " and " + mention2 + " have an " + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio (PMID: " + str(odds_sorted["pmid"]) + "). "
            odds_list=[sent1,sent2]
            odds_list=random.choice(odds_list)
        if cre_sorted:
            mention1=cre_sorted["head"][2]
            mention2=cre_sorted["tail"][2]
            combined_mentions.add(mention1)
            combined_mentions.add(mention2)
            if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                # switch head and tail           
                tmp=mention1
                mention1=mention2
                mention2=tmp
            if cre_sorted["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " +  str(mention1) +" and " + str(mention2)+ " with a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+")"+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "
            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID" + str(cre_sorted["pmid"]) + ": '"+cre_sorted["sentence"] + "'"
                sent3= "As claimed by '"+ cre_sorted["sentence"] +"' PMID: (" +str(cre_sorted["pmid"])+"), we are " + '{}'.format(cre_sorted["annotation"][1])+ " sure that " + mention2+" patients show to have " + mention1 + ". "
            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + "that captures the relations: '" + cre_sorted["sentence"] +"' "
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + " as evidenced by '" + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+". "
                sent3= "According to the sentence: '" + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
            combined_mentions.add(mention1)
            combined_mentions.add(mention2)
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
        if ore_sorted:
            mention1=""
            mention2=""
            mention3=""
            mention4=""
            if len(ore_sorted)==2:
                mention1=ore_sorted[0]["head"][2]
                mention2=ore_sorted[0]["tail"][2]
                mention3=ore_sorted[1]["head"][2]
                mention4=ore_sorted[1]["tail"][2]
                combined_mentions.add(mention1)
                combined_mentions.add(mention2)
                combined_mentions.add(mention3)
                combined_mentions.add(mention4)
                relation1 = ' '.join(ore_sorted[0]["annotation"])
                relation2= ' '.join(ore_sorted[1]["annotation"])
                sent1='Moreover, there are also other relations found in this PMID: ' + target+ ', which includes the following. "' + relation1 + '." "' + relation2+ '." '
                sent2='Notably, in this PMID, further relations between these two entities are discovered. "' + relation1 + '." "' + relation2+ '." '
                sent3= 'PMID: ' + target + ' also entails relations: "' + relation1 + '" and "'+ relation2 +'."'
            else:
                mention1=ore_sorted[0]["head"][2]
                mention2=ore_sorted[0]["tail"][2]
                combined_mentions.add(mention1)
                combined_mentions.add(mention2)
                sent1='In this PMID, we also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '." ' 
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '." '
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '." ' 
            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
        final_combine=list(combined_mentions)
        final_combine= ", ".join(final_combine[:-1]) + " and " + final_combine[-1]
        sent1= "PMID: " + target + " showcases that relations exist between these prominent mentions: " + final_combine + ". " 
        sent2= "In PMID: " + target + ", our search results indicate that relations presented in " + final_combine + ". " 
        sent3= "For " + final_combine, " in PMID: "+ target + ", some relations are extracted. "
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        logger.info("summary for single pmid: 22494505")
        return final_summary
    return 

## ABP
def gen_summary_by_pmid_pair(kb,evidence_id_list,target):
    detailed_evidence = [] 
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    for evidence_id in evidence_id_list:
        _head, _tail, _annotation_id, _pmid, sentence_id = kb.get_evidence_by_id(
        evidence_id, return_annotation=False, return_sentence=False)
        head, tail, (annotator, annotation), pmid, sentence = kb.get_evidence_by_id(
            evidence_id, return_annotation=True, return_sentence=True)
        ## name name combo
        if (target[0] == "type_id_name" or target[0] == "type_name") and (target[2] == "type_id_name" or target[2] == "type_name") and pmid==target[4]:
            if (target[1][2]==head[2] or target[1][2]==tail[2]) and (target[3][2]==head[2] or target[3][2]==tail[2]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        ## id id combo
        elif (target[0] == "type_id") and (target[2] == "type_id") and pmid==target[4]:
            if (target[1][1]==head[1] or target[1][1]==tail[1]) and (target[3][1]==head[1] or target[3][1]==tail[1]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        ## id name combo
        elif (target[0] == "type_id") and (target[2] == "type_id_name" or target[2] == "type_name") and pmid==target[4]:
            if (target[1][1]==head[1] or target[1][1]==tail[1]) and (target[3][2]==head[2] or target[3][2]==tail[2]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
        ## name id combo
        elif (target[0] == "type_id_name" or target[0] == "type_name") and (target[2] == "type_id") and pmid==target[4]:
            if (target[1][2]==head[2] or target[1][2]==tail[2]) and (target[3][1]==head[1] or target[3][1]==tail[1]):
                detailed_evidence.append({  
                "head": head, "tail": tail,
                "annotator": annotator, "annotation": annotation,
                "pmid": pmid, "sentence": sentence, "sentence_id": sentence_id})
    odds_sorted, cre_sorted, ore_sorted = gen_summary_input(detailed_evidence)
    if (odds_sorted or cre_sorted or ore_sorted):
        mention1=""
        mention2=""
        if odds_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                mention1 = odds_sorted["head"][2]
            if target[0] == "type_id" :
                mention1 = odds_sorted["head"][1]
            if target[2] == "type_id_name" or target[2] == "type_name":
                mention2 = odds_sorted["tail"][2]
            if target[2] == "type_id" :
                mention2 = odds_sorted["tail"][1]
            sent1="The odds ratio found between " + mention1 + " and " + mention2+ " is " + str(odds_sorted["annotation"][0]) + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2])+ "). "
            sent2=mention1+ " and " + mention2 + " have an " + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio. "
            odds_list=[sent1,sent2]
            odds_list=random.choice(odds_list)
        if cre_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                mention1 = cre_sorted["head"][2]
            if target[0] == "type_id" :
                mention1 = cre_sorted["head"][1]
            if target[2] == "type_id_name" or target[2] == "type_name":
                mention2 = cre_sorted["tail"][2]
            if target[2] == "type_id" :
                mention2 = cre_sorted["tail"][1]
            if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                # switch head and tail           
                tmp=mention1
                mention1=mention2
                mention2=tmp
            if cre_sorted["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " +  str(mention1) +" and " + str(mention2)+ " with a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "
            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID" + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= 'As claimed by "'+ cre_sorted["sentence"] +'" ' + '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + ' as evidenced by "' + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+'." '
                sent3= 'According to the sentence: "' + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
        if ore_sorted:
            if len(ore_sorted)==2:
                mention1=ore_sorted[0]["head"][2]
                mention2=ore_sorted[0]["tail"][2]
                relation1 = ' '.join(ore_sorted[0]["annotation"])
                relation2= ' '.join(ore_sorted[1]["annotation"])
                sent1='Moreover, there are also other relations found in this PMID: ' + target+ ', which includes the following. "' + relation1 + '." "' + relation2+ '." '
                sent2='Notably, in this PMID, further relations between these two entities are discovered. "' + relation1 + '." "' + relation2+ '." '
                sent3= 'PMID: ' + target + ' also entails relations: "' + relation1 + '" and "'+ relation2 +'."'
            else:
                mention1=ore_sorted[0]["head"][2]
                mention2=ore_sorted[0]["tail"][2]
                sent1='We also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
        sent1="Based on our search results, relation exists between " +  mention1 + " and " + mention2 + " in PMID: " + target[4] + ". "
        sent2="Relations occur between "+ mention1 + " and " + mention2 + " as shown from our search for PMID: " + target[4] + ". "
        sent3=mention1 + " and " + mention2 + " relate to each other in PMID: " + target[4] +". "
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        logger.info("summary for pmid and single pair: rs4925 & MESH:D012871 & 29323258")
        return final_summary
    return 

def get_summary (kb,evidence_id_list, target, query_filter):
    if query_filter == "A":
        return(gen_summary_by_entity(kb,evidence_id_list,target))

    elif query_filter == "AB":
        return(gen_summary_by_pair(kb,evidence_id_list,target))

    elif query_filter == "P":
        return(gen_summary_by_pmid(kb,evidence_id_list,target))

    elif query_filter == "AP":
        return(gen_summary_by_entity_pmid(kb,evidence_id_list,target))

    elif query_filter == "ABP":
        return(gen_summary_by_pmid_pair(kb,evidence_id_list,target))

def test_summary(kb_dir):
    kb = KB(kb_dir)
    kb.load_data()
    kb.load_index()

    # test A
    evidence_id_list = [928292,1395158,2449403,2449407,2449411,2584152,227365,570299,570313,570323,900159,900183,928286,4836,21298,21692,25199,34845,35464,35468,35493,35494,36495,2467,3086,4837,10339,10839,14928,15549,16764,19499,20412]
    # print(gen_summary_by_entity(kb=kb,evidence_id_list=evidence_id_list, target=("type_id",("Disease", "MESH:D012871", "skin lesions"))))
    text=get_summary(kb,evidence_id_list, target=("type_id",("Disease", "MESH:D012871", "skin lesions")), query_filter="A")
    print(text)
    
    # test AB
    evidence_id_list = [2449403,2449404,2449405,2449406,2449353,2449364,2449365,2449366,2449367,2449382]
    # print(gen_summary_by_pair(kb=kb,evidence_id_list=evidence_id_list, target=("type_name",("SNP", "RS#:4925", "rs4925"),"type_id",("Disease", "MESH:D012871", "skin lesions"))))
    text=get_summary(kb,evidence_id_list, target=("type_name",("SNP", "RS#:4925", "rs4925"),"type_id",("Disease", "MESH:D012871", "skin lesions")), query_filter="AB")
    print(text)

    # test pmid
    evidence_id_list = [3561262,3561263,3561264,3561265,3561242,3561246,3561250,3561254,3561258,3561241,3561266]
    # print(gen_summary_by_pmid(kb=kb,evidence_id_list=evidence_id_list, target="22494505"))
    text =get_summary(kb,evidence_id_list, target="22494505", query_filter="P")
    print(text)

    # test AP
    evidence_id_list = [928292,1395158,2449403,2449407,2449411,2584152,227365,570299,570313,570323,900159,900183,928286,4836,21298,21692,25199,34845,35464,35468,35493,35494,36495,2467,3086,4837,10339,10839,14928,15549,16764,19499,20412]
    # print(gen_summary_by_entity_pmid(kb=kb,evidence_id_list=evidence_id_list, target=("type_name",("Disease", "MESH:D012871", "skin lesions"),"23644288")))
    text = get_summary(kb,evidence_id_list,target=("type_name",("Disease", "MESH:D012871", "skin lesions"),"23644288"), query_filter="AP")
    print(text)

    # test ABP
    evidence_id_list = [2449403,2449404,2449405,2449406,2449353,2449364,2449365,2449366,2449367,2449382]
    # print(gen_summary_by_pmid_pair(kb=kb,evidence_id_list=evidence_id_list, target=("type_name",("SNP", "RS#:4925", "rs4925"),"type_id",("Disease", "MESH:D012871", "skin lesions"),"29323258")))
    text=get_summary(kb,evidence_id_list,("type_name",("SNP", "RS#:4925", "rs4925"),"type_id",("Disease", "MESH:D012871", "skin lesions"),"29323258"), query_filter="ABP")
    print(text)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb_dir", type=str, default="/volume/summary/data")
    arg = parser.parse_args()
    test_summary(arg.kb_dir)
    return

if __name__ == "__main__":
    main()
    sys.exit()











