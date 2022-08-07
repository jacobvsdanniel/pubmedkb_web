import random
import sys
import logging
import argparse
import html
from collections import defaultdict
# from kb_utils import KB

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
    cre_ungrouped =  [d for d in detailed_evidence if d["annotator"]=="rbert_cre"]
    odds_ungrouped = [d for d in detailed_evidence if d["annotator"]=="odds_ratio"]
    spacy_ungrouped = [d for d in detailed_evidence if d["annotator"]=="spacy_ore"]
    openie_ungrouped = [d for d in detailed_evidence if d["annotator"]=="openie_ore"]
    if odds_ungrouped:
        if len(odds_ungrouped)==1:
            odds_sorted=odds_ungrouped[0]
        else:
            for l in odds_ungrouped:
                l["odds_ratio"]=l["annotation"][0]
                if l["odds_ratio"] == "x":
                    l["odds_ratio"] = "0"
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
            ore_sorted.append(spacy_ungrouped[0])
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
            logger.info(d_list_sorted)
            for i in range (0, len(d_list_sorted)):
                if len(ore_sorted)<2:
                    e=d_list_sorted[i][1][0]
                    s = ' '.join(e["annotation"])
                    if len(ore_sorted)==0:
                        ore_sorted.append(e)
                        string_list.append(s)
                    else:
                        if s!=string_list[i-1]:
                            ore_sorted.append(e)
                else:
                    break
    return odds_sorted, cre_sorted, ore_sorted

## AP
def gen_summary_by_entity_pmid(kb,evidence_id_list,target):
    combined_mentions = set()
    detailed_evidence = []
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    odds_list2 = [""]
    triplet_list2 = [""]
    rbert_list2 = [""]
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
        elif target[0] == "type_id":
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
            sent1 = "The odds ratio found between " + mention1 + " and " + mention2+ " is " + str(odds_sorted["annotation"][0]) + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2])+ "). "
            sent2 = mention1+ " and " + mention2 + " have an " + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio. "
            ## html version
            sent10 = "The odds ratio found between " + "<span style='color:#21d59b;font-weight:bold'>"+ html.escape(mention1) + " and " + html.escape(mention2)+ "</span>"+ " is " + "<mark style='background-color:62e0b84d'>" + html.escape(str(odds_sorted["annotation"][0])) + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2]))+ ")." +"</mark>" +" "
            sent20 = "<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention1) + " and " + html.escape(mention2) + "</span>"+ " have an " + "<mark style='background-color:62e0b84d'>" + html.escape(str(odds_sorted["annotation"][0]))  + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2])) + ")"+" odds ratio." +"</mark>" +" "
            odds_list = [sent1,sent2]
            combined_mentions.add(mention2)
            odds_list = random.choice(odds_list)
            odds_list2 = [sent10,sent20]
            odds_list2 = random.choice(odds_list2)
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
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "
                ## html
                sent10="We believe that there is a " +  "<mark style='background-color:#5f96ff4d'>" + "causal relationship" +"</mark>"+" between " +  "<span style='color:#0058ff;font-weight:bold'>" + str(mention1) +" and " + str(mention2) + "</span>" + " "+ "<mark style='background-color:#5f96ff4d'>"+ "with a confidence of " + '{}'.format(cre_sorted["annotation"][1])+"</mark>" + ". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent20= "With a " + "<mark style='background-color:#5f96ff4d'>"+ "confidence of " + '{}'.format(cre_sorted["annotation"][1])+ "</mark>" +", we found that " +  "<span style='color:#0058ff;font-weight:bold'>" + str(mention1)  + "</span>"+ " is " +  "<mark style='background-color:#5f96ff4d'>" + "a causal variant of" +"</mark>"+ " " +  "<span style='color:#0058ff;font-weight:bold'>" + str(mention2)  + "</span>" + ". " + "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent30= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' +  "<span style='color:#0058ff;font-weight:bold'>" + str(mention1) + "</span>" + " is associated with " +  "<span style='color:#0058ff;font-weight:bold'>" + str(mention2) +  "</span>" + " "+ "<mark style='background-color:#5f96ff4d'>" + "by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+"</mark>" + ". "
            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= 'As claimed by "'+ cre_sorted["sentence"] +'" ' + '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
                ## html
                sent10 = "<span style='color:#0058ff;font-weight:bold'>"+html.escape(mention1)+ "</span>" + " " +"<span style='color:#0058ff;font-weight:bold'>"+"occurs" +"</span>" + " in some " + "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention2) + " patients." "</span>" +" Our finidng shows that " + "<mark style='background-color:#5f96ff4d'>"  +"the confidence of this association is approximately " + html.escape('{}'.format(cre_sorted["annotation"][1]))+"." + "</mark>" + "Here is an excerpt of the literature (PMID: " +html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' + html.escape(cre_sorted["sentence"]) +'" '
                sent20 = "With a " +"<mark style='background-color:#5f96ff4d'>"+ "confidence of " + html.escape('{}'.format(cre_sorted["annotation"][1]))+ "</mark>" + ", we found that " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1)+" patients"+ "</span>" + " " +"carry" + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2) +"."+ "</span>" + "This piece of relation is evidenced by the sentence in PMID: " + html.escape(str(cre_sorted["pmid"])) + ': "'+html.escape(cre_sorted["sentence"]) + '" '
                sent30 = 'As claimed by "'+ html.escape(cre_sorted["sentence"]) +'" ' + "we are " + "<mark style='background-color:#5f96ff4d'>"+ html.escape('{}'.format(cre_sorted["annotation"][1]))+ ""+ " sure" + "</mark>" + " that " +  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2)+" patients" + "</mark>" +" show to have " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1) + "." + "</mark>" + " "
            if cre_sorted["annotation"][0]=="Appositive":
                sent1 = mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + ' as evidenced by "' + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+'." '
                sent3= 'According to the sentence: "' + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
                ## html
                sent10 = "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1)+ "'s relation with " + "<span style='color:#0058ff;font-weight:bold'>"+html.escape(mention2) + " is " + "<mark style='background-color:#5f96ff4d'>"+ "presupposed." + "</mark>"+ " We are " +  "<mark style='background-color:#5f96ff4d'>" + html.escape('{}'.format(cre_sorted["annotation"][1]))+ " " + "confidence" + "</mark>" +" about this association. " + "Here is an excerpt of the literature (PMID:" +html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' + html.escape(cre_sorted["sentence"]) +'" '
                sent20 = "It is " + html.escape('{}'.format(cre_sorted["annotation"][1])) +" "+   "<mark style='background-color:#5f96ff4d'>" + "presupposed" + "</mark>" +" that " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1) +"</mark>" + " is related to "+"<mark style='background-color:#5f96ff4d'>"+ html.escape(mention2) + "</mark>" + ' as evidenced by "' + html.escape(cre_sorted["sentence"]) + "' (PMID: "+ html.escape(str(cre_sorted["pmid"]))+'." '
                sent30 = 'According to the sentence: "' + html.escape(cre_sorted["sentence"])+ "' (PMID: " + html.escape(str(cre_sorted["pmid"]))+ ") " + "The relation between " + "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention1) +"</mark>" +" and " + html.escape(mention2) + " contains a " +   "<mark style='background-color:#5f96ff4d'>" + "presupposition." + "</mark>" +" "
            rbert_list = [sent1,sent2,sent3]
            rbert_list = random.choice(rbert_list)
            rbert_list2 = [sent10,sent20,sent30]
            rbert_list2 = random.choice(rbert_list2)
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
                sent1="Moreover, there are also other relations found, which includes the following: " + str(mention1) + " & " + str(mention2)  + " and " + str(mention3) +" & " + str(mention4) + '." "'+ str(relation1) + '." and "' + str(relation2) + '." '
                sent2='Notably, further relations between the aforementioned entities are discovered. "' + str(relation1) + '." "' + str(relation2) +'." '
                sent3= str(mention1) + " & " + str(mention2)  + " and " + str(mention3) + " & " + str(mention4)+ ' also contain further relations. "'+ str(relation1) + '." and "' + str(relation2) +'." '
                ## html
                sent10="Moreover, there are also other relations found, which includes the following: " + "<span style='color:#ff8389;font-weight:bold'>"+ str(mention1) + "</span>" + " " +  html.escape("&") + " " + "<span style='color:#ff8389;font-weight:bold'>"+str(mention2)  +  "</span>" + " and " + "<span style='color:#0058ff;font-weight:bold'>" + str(mention3) + "</span>" + " " +html.escape("&") + " " +  "<span style='color:#0058ff;font-weight:bold'>"+str(mention4) +"</span>" + ". " + "<mark style='background-color:#ff83894d'>" + ' "'+ str(relation1) + '."' + "</mark>" + " and " + "<mark style='background-color:#ff83894d'>"+'"' + str(relation2) + '."' +  "</mark>"  + " "
                sent20="Notably, further relations between the aforementioned entities are discovered. " + "<mark style='background-color:#ff83894d'>" + '"' + str(relation1) + '."' + "</mark>" + " " + "<mark style='background-color:#ff83894d'>" + '"' + html.escape(str(relation1)) + '."' + "</mark>" + " "
                sent30= "<span style='color:#ff8389;font-weight:bold'>" + html.escape(str(mention1)) + "</span>" + " " +html.escape("&")+" " + "<span style='color:#ff8389;font-weight:bold'>"+ html.escape(str(mention2)) + "</span>" + " and " + "<span style='color:#ff8389;font-weight:bold'>"+ html.escape(str(mention3)) +  "</span>"  + " " + html.escape("&") + " " + "<span style='color:#ff8389;font-weight:bold'>" + html.escape(str(mention4)) + "</span>" + ' also contain further relations. ' + "<mark style='background-color:#ff83894d'>"+ '"'+ html.escape(str(relation1)) + '."' + "</mark>" + " and " + "<mark style='background-color:#ff83894d'>" + html.escape(str(relation2)) +'."' + "</mark>" + " "
            else:
                sent1='We also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                ## html
                sent10 ='We also found "'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '"' + ". "
                sent20 ="<mark style='background-color:#ff83894d'>" + '"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '"' + "." + "</mark>" + " "
                sent30 ="In addition, " +"<mark style='background-color:#ff83894d'>"+'"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '"' + "."+ "</mark>" + " "
            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
            triplet_list2=[sent10,sent20, sent30]
            triplet_list2=random.choice(triplet_list2)
        final_combine=list(combined_mentions)
        if len(final_combine)>1:
            final_combine= ", ".join(final_combine[:-1]) + " and " + final_combine[-1]
        else:
            final_combine="".join(final_combine)
        sent1= "Based on our search results, in PMID: " + target[2]+ ", relation exists between " +  mention1 + " and these prominent mentions: " + final_combine + ". "
        sent2= "From PMID: " + target[2] + ", " + mention1 + " relates to "  + final_combine + ". "
        sent3= "We found that these mentions-" + final_combine+ "-" + "relate(s) to " + mention1 +" in PMID: " +target[2]
        ## html intro
        sent10=  "Based on our search results, in PMID: " + "<b>" +html.escape(target[2]) +"</b>"+ ", relation exists between " +  "<b>" + html.escape(mention1) +  "</b>" +" and these prominent mentions: " + "<span style='color:#f99600;font-weight:bold'>" + html.escape(final_combine) + "</span>"  +". "
        sent20= "From PMID: " +"<b>"+ html.escape(target[2])+"</b>" + ", " + "<b>"+html.escape(mention1) +"</b>"+ " relates to "  + "<span style='color:#f99600;font-weight:bold'>" + html.escape(final_combine) + "</span>" + ". "
        sent30= "We found that these mentions-" + "<span style='color:#f99600;font-weight:bold'>" + html.escape(final_combine)+ "</span>"  + "-" + "relate(s) to " +"<b>"+ html.escape(mention1) + "</b>" +" in PMID: " +"<b>"+html.escape(target[2]) + "</b>" + "." + ' '
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        intro_list2=[sent10,sent20, sent30]
        intro_list2=random.choice(intro_list2)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        final_summary_ht = list(intro_list2)+list(odds_list2)+list(rbert_list2)+list(triplet_list2)
        final_summary_ht  = ''.join(str(v) for v in final_summary_ht)
        return tuple([final_summary,final_summary_ht])
    else:
        final_summary = "There are not enough information for generating a substantial summary for this entity and PMID. Please view the following table or re-enter the entity."
        final_summary_ht = html.escape("There are not enough information for generating a substantial summary for this entity. Please view the following table or re-enter the entity.")
        return tuple([final_summary,final_summary_ht])

## A
def gen_summary_by_entity(kb,evidence_id_list,target):
    combined_mentions = set()
    detailed_evidence = []
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    odds_list2 = [""]
    triplet_list2 = [""]
    rbert_list2 = [""]
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
            ## html
            sent10="The odds ratio found between " + "<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention1) + "</span>" + " and " +"<span style='color:#21d59b;font-weight:bold'>"+ html.escape(mention2) +"</span>"+ " in PMID: " + html.escape(str(odds_sorted["pmid"])) + " is " + "<mark style='background-color:#62e0b84d'>" + html.escape(str(odds_sorted["annotation"][0])) + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2]))+ ")." + "</mark>" + " "
            sent20= "<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention1)+ " and " + mention2 + "</span>" + " have an " + "<mark style='background-color:#62e0b84d'>" + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio" + "</mark>"+  " (PMID: " + str(odds_sorted["pmid"]) + ")."  +" "
            odds_list=[sent1,sent2]
            combined_mentions.add(mention2)
            odds_list=random.choice(odds_list)
            odds_list2=[sent10,sent20]
            odds_list2=random.choice(odds_list2)
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
                elif target[1][2] in cre_sorted["tail"]:
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
                        tmp = mention1
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
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ' "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "
                ##html
                sent10 ="We believe that there is a " + "<mark style='background-color:#5f96ff4d'>" + "causal relationship" + "</mark>" +  " between " +  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + "</span>" +" and " + "<span style='color:#0058ff;font-weight:bold'>"+html.escape(str(mention2))+ "</span>"+ " with a " + "<mark style='background-color:#5f96ff4d'>"+ "confidence of " + html.escape('{}'.format(cre_sorted["annotation"][1]))+ "." + "</mark>" + " Here is an excerpt of the literature (PMID: " +html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' + html.escape(cre_sorted["sentence"]) +'" '
                sent20 = "With a " +"<mark style='background-color:#5f96ff4d'>"+"confidence of " + html.escape('{}'.format(cre_sorted["annotation"][1]))+"</mark>" + ", we found that " + "<span style='color:#0058ff;font-weight:bold'>" + str(mention1) + "</span>" + " is a " + "<mark style='background-color:#5f96ff4d'>" + "causal variant" + "</mark>" + " of " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2)) +"</span>" + ". " + "This piece of relation is evidenced by the sentence in PMID: " + html.escape(str(cre_sorted["pmid"])) + ' "'+html.escape(cre_sorted["sentence"]) + '" '
                sent30 = "Based on the sentence (PMID: " +html.escape(str(cre_sorted["pmid"]))+") "+ ': "'+ html.escape(cre_sorted["sentence"]) + '" Our finding indicates that ' + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + "</span>" + " is " + "<mark style='background-color:#5f96ff4d'>" + "associated with" + "</mark>" " " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2)) +"</span>" + " by a " + "<mark style='background-color:#5f96ff4d'>"+" confidence of "+html.escape('{}'.format(cre_sorted["annotation"][1]))+ "." + "</mark>" + " "
            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= 'As claimed by "'+ cre_sorted["sentence"] +'" ' + '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + "(PMID: " +str(cre_sorted["pmid"]) + "). "
                ## html
                sent10 = "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + " " +"</span>" +"<mark style='background-color:#5f96ff4d'>" + "occurs" + "</mark>" + " in some " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2)) + " patients." +"</span>"+ " Our finidng shows that the " + "<mark style='background-color:#5f96ff4d'>"+ " confidence of this association is approximately " + html.escape('{}'.format(cre_sorted["annotation"][1]))+"." + "</mark>"+ " Here is an excerpt of the literature (PMID:" +html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' + html.escape(cre_sorted["sentence"]) +'" '
                sent20 = "With a " + "<mark style='background-color:#5f96ff4d'>" + "confidence of " + html.escape('{}'.format(cre_sorted["annotation"][1]))+ "</mark>"+ ", we found that " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1))+"</span>" +" " + "<mark style='background-color:#5f96ff4d'>" +"patients" + " carry" + "</mark>" + " "+ "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2)) +"." +"</span>" + "This piece of relation is evidenced by the sentence in PMID: " + html.escape(str(cre_sorted["pmid"])) + ': "'+ html.escape(cre_sorted["sentence"]) + '" '
                sent30 = 'As claimed by "'+ html.escape(cre_sorted["sentence"]) +'" ' + "we are " + "<mark style='background-color:#5f96ff4d'>"+ html.escape('{}'.format(cre_sorted["annotation"][1]))+ ""+ " sure" +"</mark>" +" that " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1))+" patients " + "</span>" +  " show to have " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1)  + "</span>" + "(PMID: " +str(cre_sorted["pmid"]) + "). "
            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confident about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + ' as evidenced by "' + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+')." '
                sent3= 'According to the sentence: "' + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."
                ## html
                sent10= "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1))+ "'s"+ "</span>"+" relation with " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2)) + "</span>" + "is " + "<mark style='background-color:#5f96ff4d'>" + "presupposed." + "</mark>" + " We are " + "<mark style='background-color:#5f96ff4d'>" + html.escape('{}'.format(cre_sorted["annotation"][1]))+ " " + "confident" + "</mark>" + " about this association. " + "Here is an excerpt of the literature (PMID:" + html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' + html.escape(cre_sorted["sentence"]) +'" '
                sent20= "It is " + "<mark style='background-color:#5f96ff4d'>" + html.escape('{}'.format(cre_sorted["annotation"][1])) +  " presupposed" + "</mark>" + " that "+  "<span style='color:#0058ff;font-weight:bold'>"  + html.escape(str(mention1)) + "</span>" + " is related to "+ "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(str(mention2)) + "</span>"+' as evidenced by "' + cre_sorted["sentence"] + "' (PMID: "+ html.escape(str(cre_sorted["pmid"]))+')." '
                sent30= 'According to the sentence: "' + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(str(mention1)) +  "</span>" + " and " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2)) + "</span>"+ " contains a " + "<mark style='background-color:#5f96ff4d'>" +"presupposition." + "</mark>" + " "
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
            rbert_list2=[sent10,sent20,sent30]
            rbert_list2=random.choice(rbert_list2)
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
                sent1="Moreover, there are also other relations found, which includes the following: " + str(mention1) +" & "+ str(mention2)  + " and " + str(mention3) + " & " +str(mention4) + '. "'+ str(relation1) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ') and "' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+'). '
                sent2='Notably, further relations between the aforementioned entities are discovered. ' + str(mention1) +" & " + str(mention2)  + " and " + str(mention3) + " & "+  str(mention4) + '. "'+ str(relation1) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ') and "' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+'). '
                sent3= str(mention1) + " & " + str(mention2)  + " and " + str(mention3) +" & " + str(mention4)+ ' also contain further relations. "'+ str(mention2)  + " & "  + str(mention3) + '. "' +  str(mention4) + '." "'+ str(relation1) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ') and "' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+'). '
                ## html
                sent10 ="Moreover, there are also other relations found, which includes the following: " + "<span style='color:#ff8389;font-weight:bold'>" + html.escape(str(mention1))  + " " +html.escape("&")  + " " + html.escape(str(mention2))  +"</span>" +" and " + "<span style='color:#ff8389;font-weight:bold'>" + html.escape(str(mention3)) +" "  +html.escape("&") + " " + html.escape(str(mention4)) + '. ' + "</span>" + " " + "<mark style='background-color:#ff83894d'>"+ '"'+ str(relation1) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ')' + "</mark>" + ' and ' + "<mark style='background-color:#ff83894d'>"+'"' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+').' +"</mark>" + " "
                sent20 ='Notably, further relations between the aforementioned entities are discovered. ' + "<span style='color:#ff8389;font-weight:bold'>" + html.escape(str(mention1))  + " "   +html.escape("&") +" "  +html.escape(str(mention2))  +"</span>"+ " and " + "<span style='color:#ff8389;font-weight:bold'>" + html.escape(str(mention3)) + " " +html.escape("&") + " "  + html.escape(str(mention4)) + '. ' +"</span>"+ ""  +"<mark style='background-color:#ff83894d'>"+ '"'+ str(relation1) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ')' + "</mark>" + ' and ' + "<mark style='background-color:#ff83894d'>"+'"' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+').' +"</mark>" + " "
                sent30 = "<span style='color:#ff8389;font-weight:bold'>"+html.escape(str(mention1)) +" "  +html.escape("&")+ " " + html.escape(str(mention2))  + "</span>" + " and " + "<span style='color:#ff8389;font-weight:bold'>" + html.escape(str(mention3)) +" " + html.escape("&") + " " + html.escape(str(mention4))+ "</span>" + ' also contain further relations. '+ "<mark style='background-color:#ff83894d'>"+ '"'+ html.escape(str(relation1)) + '" (PMID: ' +  ore_sorted[0]["pmid"]+ ')' + "</mark>" + ' and ' + "<mark style='background-color:#ff83894d'>"+'"' + str(relation2) + '" (PMID: ' +  ore_sorted[1]["pmid"]+').' +"</mark>" + " "
            else:
                sent1='We also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + "). "
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ". "
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + "). "
                ## html
                sent10 ='We also found' + "<mark style='background-color:#ff83894d'>" + '"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ")." + "</mark>" + " "
                sent20 ="<mark style='background-color:#ff83894d'>" + '"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ")." + "</mark>" + " "
                sent30 ="In addition, " + "<mark style='background-color:#ff83894d'>" +'"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ")." + "</mark>" + " "
            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
            triplet_list2=[sent10,sent20,sent30]
            triplet_list2=random.choice(triplet_list2)
        final_combine=list(combined_mentions)
        final_combine= ", ".join(final_combine[:-1]) + " and " + final_combine[-1]
        sent1="Based on our search results, relation exists between " + mention1 + " and these prominent mentions: " + (final_combine) + ". "
        sent2= mention1 + " relates to "  + final_combine + ". "
        sent3= "We found that these mentions-" + final_combine+ "-" + "relate(s) to " + mention1 +". "
        ## html
        sent10="Based on our search results, relation exists between " + "<b>" + html.escape(mention1) +"</b>" + " and these prominent mentions: " +  "<span style='color:#f99600;font-weight:bold'>" +html.escape(final_combine) + "</span>" + ". "
        sent20= "<b>" + html.escape(mention1) + "</b>"+" relates to "  + "<span style='color:#f99600;font-weight:bold'>"+ html.escape(final_combine) + "</span>"+ ". "
        sent30= "We found that these mentions-" + "<span style='color:#f99600;font-weight:bold'>" + html.escape(final_combine) + "</span>"+"-" + "relate(s) to " +"<b>"+ html.escape(mention1) + "</b>"  + ". "
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        intro_list2=[sent10,sent20, sent30]
        intro_list2=random.choice(intro_list2)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        final_summary_ht = list(intro_list2)+list(odds_list2)+list(rbert_list2)+list(triplet_list2)
        final_summary_ht  = ''.join(str(v) for v in final_summary_ht)
        return tuple([final_summary,final_summary_ht])
    else:
        final_summary = "There are not enough information for generating a substantial summary for this entity. Please view the following table or re-enter the entity."
        final_summary_ht = html.escape("There are not enough information for generating a substantial summary for this entity. Please view the following table or re-enter the entity.")
        return tuple([final_summary,final_summary_ht])

## AB
def gen_summary_by_pair(kb,evidence_id_list,target):
    detailed_evidence = []
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    odds_list2 = [""]
    triplet_list2 = [""]
    rbert_list2 = [""]
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
            logger.info("target100")
            print(target)
            print(odds_sorted["head"])
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in odds_sorted["head"]:
                    mention1 = odds_sorted["head"][2]
                elif target[1][2] in odds_sorted["tail"]:
                    mention1 = odds_sorted["tail"][2]
                logger.info("mention1_name00")
                print(mention1)
            if target[0] == "type_id" :
                if target[1][1] in odds_sorted["head"]:
                    mention1 = odds_sorted["head"][1]
                elif target[1][1] in odds_sorted["tail"]:
                    mention1= odds_sorted["tail"][1]
            if target[2] == "type_id_name" or target[2] == "type_name":
                if target[3][2] in odds_sorted["head"]:
                    mention2 = odds_sorted["head"][2]
                elif target[3][2] in odds_sorted["tail"]:
                    mention2= odds_sorted["tail"][2]
                logger.info("mention2_name")
                print(mention2)
            if target[2] == "type_id" :
                if target[3][1] in odds_sorted["head"]:
                    mention2 = odds_sorted["head"][1]
                elif target[3][1] in odds_sorted["tail"]:
                    mention2 = odds_sorted["tail"][1]
                logger.info("mention2_name")
                print(mention2)
            logger.info("beforesent")
            print(mention1)
            print(mention2)
            sent1 = "The odds ratio found between " + mention1 + " and " + mention2+ " in PMID: " + str(odds_sorted["pmid"]) + " is " + str(odds_sorted["annotation"][0]) + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2])+ "). "
            sent2 = mention1+ " and " + mention2 + " have an " + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio (PMID: " + str(odds_sorted["pmid"]) + "). "
            sent10 = "The odds ratio found between " + "<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention1) + "</span>" + " and " + "<span style='color:#21d59b;font-weight:bold'>"+ html.escape(mention2)+ "</span>"+ " in PMID: " + html.escape(str(odds_sorted["pmid"])) + " is " + "<mark style='background-color:#62e0b84d'>" + html.escape(str(odds_sorted["annotation"][0])) + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2]))+ ")." + "</mark>" + " "
            sent20 = "<span style='color:#21d59b;font-weight:bold'>"+ html.escape(mention1)+ "</span>" +" and " + "<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention2) +"</span>" + " have an " + "<mark style='background-color:#62e0b84d'>" + html.escape(str(odds_sorted["annotation"][0]))  + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2])) + ")"+" odds ratio"  + "</mark>" + " (PMID: " + html.escape(str(odds_sorted["pmid"])) + "). "
            odds_list = [sent1,sent2]
            odds_list = random.choice(odds_list)
            odds_list2 = [sent10,sent20]
            odds_list2 = random.choice(odds_list2)
        if cre_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in cre_sorted["head"]:
                    mention1 = cre_sorted["head"][2]
                elif target[1][2] in cre_sorted["tail"]:
                    mention1= cre_sorted["tail"][2]
            if target[0] == "type_id" :
                if target[1][1] in cre_sorted["head"]:
                    mention1 = cre_sorted["head"][1]
                elif target[1][1] in cre_sorted["tail"]:
                    mention1= cre_sorted["tail"][1]
            if target[2] == "type_id_name" or target[2] == "type_name":
                if target[3][2] in cre_sorted["head"]:
                    mention2 = cre_sorted["head"][2]
                elif target[3][2] in cre_sorted["tail"]:
                    mention2 = cre_sorted["tail"][2]
            if target[2] == "type_id" :
                if target[3][1] in cre_sorted["head"]:
                    mention2 = cre_sorted["head"][1]
                elif target[3][1] in cre_sorted["tail"]:
                    mention2 = cre_sorted["tail"][1]
            if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                # switch head and tail
                tmp=mention1
                mention1=mention2
                mention2=tmp
            if cre_sorted["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " + str(mention1) + " and " + str(mention2)+ " with a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+")" + ' that captures the relations: ' + '"' + cre_sorted["sentence"] + '"' + "."
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is " + "<mark style='background-color:#5f96ff4d'>" + "associated with" + "</mark>" + " " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "
                ## html ##
                sent10="We believe that there is a " +"<mark style='background-color:#5f96ff4d'>"+  "causal relationship" + "</mark>" + " between " + "<span style='color:#0058ff;font-weight:bold'>"  + html.escape(str(mention1)) +"</span>" +" and " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2))+"</span>" + " with a " + "<mark style='background-color:#5f96ff4d'>" + "confidence of " + '{}'.format(cre_sorted["annotation"][1])+ "."+ "</mark>" + " Here is an excerpt of the literature (PMID: " + html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' +  html.escape(cre_sorted["sentence"]) +'" '
                sent20= "With a " + "<mark style='background-color:#5f96ff4d'>" + "confidence of " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+"</mark>" +", we found that " +  "<span style='color:#0058ff;font-weight:bold'>" + str(mention1) +"</span>"  + " is a " + "<mark style='background-color:#5f96ff4d'>"+ "causal variant"  + "</mark>" +" of " +  "<span style='color:#0058ff;font-weight:bold'>"  + html.escape(str(mention2)) + "</span>" + ". " + "This piece of relation is evidenced by the sentence in PMID: " +  html.escape(str(cre_sorted["pmid"])) + ': "'+ html.escape(cre_sorted["sentence"]) + '" '
                sent30= "Based on the sentence (PMID: " + html.escape(str(cre_sorted["pmid"]))+") "+ ': "'+  html.escape(cre_sorted["sentence"]) + '" Our finding indicates that ' +  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + "</span>" +  " is " + "<mark style='background-color:#5f96ff4d'>" + "associated with" + "</mark>"  + " "  +  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2)) + "</span>"  + " by a " + "<mark style='background-color:#5f96ff4d'>"+ "confidence of "+ html.escape('{}'.format(cre_sorted["annotation"][1]))+ "." + "</mark>" + " "

            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finding shows that the confidence of this association is approximately " +  '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +". " "This piece of relation is evidenced by the following sentence in (PMID: " + str(cre_sorted["pmid"]) + '). "' +cre_sorted["sentence"] + '" '
                sent3= 'As claimed by "'+  cre_sorted["sentence"] +'" PMID: (' + str(cre_sorted["pmid"])+"), we are " +  '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
                ## html ##
                sent10=  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1))+ "</span>" + " "+"<mark style='background-color:#5f96ff4d'>"+ "occurs in" + "</mark>" + " some " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2))+" " + "</span>"  + "<mark style='background-color:#5f96ff4d'>" + "patients." + "</mark>" + " Our finding shows that the confidence of this association is approximately " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+". "+ "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent20= "With a " + "<mark style='background-color:#5f96ff4d'>"+ "confidence of " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+ "</mark>" + ", we found that " +  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + " "+ "</span>"   +"<mark style='background-color:#5f96ff4d'>" + "patients" +" carry" + "</mark>"  +  "<span style='color:#0058ff;font-weight:bold'>" +" " +html.escape(str(mention2)) + "</span>" +". " "This piece of relation is evidenced by the following sentence in (PMID: " + str(cre_sorted["pmid"]) + '). "' +cre_sorted["sentence"] + '" '
                sent30= 'As claimed by "'+ html.escape(cre_sorted["sentence"]) +'" PMID: (' + html.escape(str(cre_sorted["pmid"]))+"), we are " + "<mark style='background-color:#5f96ff4d'>" + '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure" + "</mark>"+ " that " +  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2))+ "</span>"  + " " +"<mark style='background-color:#5f96ff4d'>"+ "patients "  + "show to have" +"</mark>"+ " "+  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) +"</span>"  +". "
            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "It is " +  '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + " as evidenced by '" + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+". "
                sent3= 'According to the sentence: "' + cre_sorted["sentence"]+ '" (PMID: ' + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition. "
                ## html ##
                sent10 =  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1))+ "</span>"  +"'s relation with " + "<span style='color:#0058ff;font-weight:bold'>"  +  html.escape(str(mention2)) +"</span>" + "is "+ "<mark style='background-color:#5f96ff4d'>" + "presupposed."  + "</marl>"+ " We are " +  "<mark style='background-color:#5f96ff4d'>" + html.escape('{}'.format(cre_sorted["annotation"][1]))+ " " + "confidence" +"</mark>" +" about this association. " + "Here is an excerpt of the literature (PMID:" + html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' +  html.escape(cre_sorted["sentence"]) +'" '
                sent20 = "It is " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+" "+  "<mark style='background-color:#5f96ff4d'>" + "presupposed"+ "</mark>"+" that "+  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + "</span>" + " is related to "+  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2)) + "</span>" +" as evidenced by '" +  html.escape(cre_sorted["sentence"]) + "' (PMID: "+  html.escape(str(cre_sorted["pmid"]))+". "
                sent30 = 'According to the sentence: "' +  html.escape(cre_sorted["sentence"])+ '" (PMID: ' +  html.escape(str(cre_sorted["pmid"]))+") " + "The relation between " +  "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + "</span>" +" and "+ "<span style='color:#0058ff;font-weight:bold'>"  + html.escape(str(mention2)) +"</span>" + " contains a" + "<mark style='background-color:#5f96ff4d'>"+"presupposition." + "</mark>" + " "
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
            rbert_list2=[sent10,sent20,sent30]
            rbert_list2=random.choice(rbert_list2)
        if ore_sorted:
            if len(ore_sorted)==2:
                if target[0] == "type_id_name" or target[0] == "type_name":
                    if target[1][2] in ore_sorted[0]["head"]:
                        mention1 = ore_sorted[0]["head"][2]
                    elif target[1][2] in ore_sorted[0]["tail"]:
                        mention1 = ore_sorted[0]["tail"][2]
                if target[0] == "type_id" :
                    if target[1][1] in ore_sorted[0]["head"]:
                        mention1 = ore_sorted[0]["head"][1]
                    elif target[1][1] in ore_sorted[0]["tail"]:
                        mention1= ore_sorted[0]["tail"][1]
                if target[2] == "type_id_name" or target[2] == "type_name":
                    if target[3][2] in ore_sorted[1]["head"]:
                        mention2 = ore_sorted[1]["head"][2]
                    elif target[3][2] in ore_sorted[1]["tail"]:
                        mention2 = ore_sorted[1]["tail"][2]
                if target[2] == "type_id" :
                    if target[3][1] in ore_sorted[1]["head"]:
                        mention2 = ore_sorted[1]["head"][1]
                    elif target[3][1] in ore_sorted[1]["tail"]:
                        mention2 = ore_sorted[1]["tail"][1]
                relation1 = ' '.join(ore_sorted[0]["annotation"])
                relation2= ' '.join(ore_sorted[1]["annotation"])
                sent1='Moreover, there are also relations found between these two entities, which includes the following. "' + relation1 + '" (PMID: ' + ore_sorted[0]["pmid"] +'). "' + relation2+ '" (PMID: ' + ore_sorted[1]["pmid"] +').'
                sent2='Notably, further relations between ' + mention1 + " and " + mention2 +  ' are present. "' + relation1 + '" (PMID: ' + ore_sorted[0]["pmid"] +'). "' + relation2+ '" (PMID: ' + ore_sorted[1]["pmid"] +').'
                sent3= 'Between these two entities, prior literature also entails that "' + relation1 + '" (PMID: ' + ore_sorted[0]["pmid"] +') and ' +'"' + relation2+ '" (PMID: ' + ore_sorted[1]["pmid"] +').'

                ## html
                sent10='Moreover, there are also relations found between these two entities, which includes the following. ' +"<mark style='background-color:#ff83894d'>"+ '"' + html.escape(relation1) + '" (PMID: ' + html.escape(ore_sorted[0]["pmid"]) +').' + "</mark>" + " " +"<mark style='background-color:#ff83894d'>"+'"'+ html.escape(relation2)+ '" (PMID: ' + html.escape(ore_sorted[1]["pmid"]) +').' + "</mark>" + " "
                sent20='Notably, further relations between ' + "<span style='color:#ff8389;font-weight:bold'>" + html.escape(mention1) +"</span>" + " and " + "<span style='color:#ff8389;font-weight:bold'>" + html.escape(mention2)  +"</span>"+  ' are present. '+  "<mark style='background-color:#ff83894d'>" +'"' + html.escape(relation1) + '" (PMID: ' + html.escape(ore_sorted[0]["pmid"]) +').'  +"</mark>" + " " +"<mark style='background-color:#ff83894d'>" + '"'+html.escape(relation2)+ '" (PMID: ' + html.escape(ore_sorted[1]["pmid"]) +').' + "</mark>"+" "
                sent30= 'Between these two entities, prior literature also entails that ' + "<mark style='background-color:#ff83894d'>" + '"'+html.escape(relation1) + '" (PMID: ' + html.escape(ore_sorted[0]["pmid"]) +')'+ "</mark>" + ' and ' +"<mark style='background-color:#ff83894d'>"+ '"'+html.escape(relation2)+ '" (PMID: ' + html.escape(ore_sorted[1]["pmid"]) +').' +"</mark>" + " "

            else:
                if target[0] == "type_id_name" or target[0] == "type_name":
                    if target[1][2] in ore_sorted[0]["head"]:
                        mention1 = ore_sorted[0]["head"][2]
                    elif target[1][2] in ore_sorted[0]["tail"]:
                        mention1 = ore_sorted[0]["tail"][2]
                if target[0] == "type_id" :
                    if target[1][1] in ore_sorted[0]["head"]:
                        mention1 = ore_sorted[0]["head"][1]
                    elif target[1][1] in ore_sorted[0]["tail"]:
                        mention1= ore_sorted[0]["tail"][1]
                if target[2] == "type_id_name" or target[2] == "type_name":
                    if target[3][2] in ore_sorted[1]["head"]:
                        mention2 = ore_sorted[1]["head"][2]
                    elif target[3][2] in ore_sorted[1]["tail"]:
                        mention2 = ore_sorted[1]["tail"][2]
                if target[2] == "type_id" :
                    if target[3][1] in ore_sorted[1]["head"]:
                        mention2 = ore_sorted[1]["head"][1]
                    elif target[3][1] in ore_sorted[1]["tail"]:
                        mention2 = ore_sorted[1]["tail"][1]
                sent1='We also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ". "
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ". "
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '" (PMID: ' +  ore_sorted[0]["pmid"] + ". "

                ## html
                sent10='We also found ' + "<mark style='background-color:#ff83894d'>"+'"' + html.escape(' '.join(ore_sorted[0]["annotation"])) + '" (PMID: ' +  html.escape(ore_sorted[0]["pmid"]) + "." + "</mark>" +" "
                sent20="<mark style='background-color:#ff83894d'>"+'"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '" (PMID: ' +  html.escape(ore_sorted[0]["pmid"])+ "</mark>" +" "
                sent30="In addition, " +"<mark style='background-color:#ff83894d'>"+'"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '" (PMID: ' +  html.escape(ore_sorted[0]["pmid"]) + "." + "</mark>" +" "

            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)

            triplet_list2=[sent10,sent20,sent30]
            triplet_list2=random.choice(triplet_list2)
        sent1="Based on our search results, relation exists between " +  mention1 + " and " + mention2 + ". "
        sent2="Relations occur between "+ mention1 + " and " + mention2 + " as shown from our search. The exact sources are demonstrated by PMID. "
        sent3=mention1 + " and " + mention2 + " relate to each other in the following ways."
        ## html
        sent10 = "Based on our search results, relation exists between " + "<b>" +  html.escape(mention1) + "</b>" +" and " + "<b>" + html.escape(mention2) + "</b>" + ". "
        sent20 = "Relations occur between "+  "<b>"+ html.escape(mention1) + "</b>"+ " and " +  "<b>" + html.escape(mention2) + "</b>" + " as shown from our search. The exact sources are demonstrated by PMID. "
        sent30 =  "<b>"+html.escape(mention1) + "</b>" + " and " + "<b>" +html.escape(mention2) +"</b>" + " relate to each other in the following ways. "
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        intro_list2=[sent10,sent20, sent30]
        intro_list2=random.choice(intro_list2)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        final_summary_ht=list(intro_list2)+list(odds_list2)+list(rbert_list2)+list(triplet_list2)
        final_summary_ht = ''.join(str(v) for v in final_summary_ht)
        logger.info("summary for single pair")
        print(final_summary)
        print(final_summary_ht)
        return tuple([final_summary,final_summary_ht])
    else:
        final_summary = "There are not enough information for generating a substantial summary for this pair. Please view the following table or re-enter the entity."
        final_summary_ht = html.escape("There are not enough information for generating a substantial summary for this pair. Please view the following table or re-enter the entity.")
        return tuple([final_summary,final_summary_ht])

## P
def gen_summary_by_pmid(kb,evidence_id_list,target):
    combined_mentions = set()
    detailed_evidence = []
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    odds_list2 = [""]
    triplet_list2 = [""]
    rbert_list2 = [""]
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
            ## html
            sent10="The odds ratio found between " +"<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention1) + "</span>" +" and " + "<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention2) +"</span>" + " in PMID: " + html.escape(str(odds_sorted["pmid"])) + " is " + "<mark style='background-color:#62e0b84d'>" + html.escape(str(odds_sorted["annotation"][0])) + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2]))+ ")." + "</mark>" + " "
            sent20="<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention1) + "</span>" +" and " + "<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention2)  + "</span>" +" have an " + "<mark style='background-color:#62e0b84d'>" + str(odds_sorted["annotation"][0])  + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2])) + ")"+" odds ratio" + "</mark>" + ". "
            odds_list2=[sent10,sent20]
            odds_list2=random.choice(odds_list2)
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
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+")"+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "

            ## html
                sent10="We believe that there is a " + "<mark style='background-color:#5f96ff4d'>"+ "causal relationship" + "</mark>"  + " between " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + "</span>" +" and " + "<span style='color:#0058ff;font-weight:bold'>"  +html.escape(str(mention2)) +"</span>" + " with a " + "<mark style='background-color:#5f96ff4d'>" + "confidence of " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+ "." + "</mark>"+ " " + "Here is an excerpt of the literature (PMID: " + html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' +  html.escape(cre_sorted["sentence"]) +'" '
                sent20= "With a " + "<mark style='background-color:#5f96ff4d'>" + "confidence of " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+ "</mark>"  +", we found that " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1))  + "</span>"  + " is a " + "<mark style='background-color:#5f96ff4d'>" "causal variant" + "</mark>" + " of " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention2))  + "</span>"  + ". " + "This piece of relation is evidenced by the sentence in PMID: " +  html.escape(str(cre_sorted["pmid"])) + ': "'+ html.escape(cre_sorted["sentence"]) + '" '
                sent30= "Based on the sentence (PMID: " + html.escape(str(cre_sorted["pmid"]))+")"+ ': "'+  html.escape(cre_sorted["sentence"]) + '" Our finding indicates that ' + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + "</span>" + " is " + "<mark style='background-color:#5f96ff4d'>" + "associated with" + "</mark>"+ " " +"<span style='color:#0058ff;font-weight:bold'>" +  html.escape(str(mention2))   + "</span>" + " by a " + "<mark style='background-color:#5f96ff4d'>" + "confidence of "+ html.escape('{}'.format(cre_sorted["annotation"][1]))+ "." + "</mark>" + " "


            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "As claimed by '"+ cre_sorted["sentence"] +"' PMID: (" +str(cre_sorted["pmid"])+"), we are " + '{}'.format(cre_sorted["annotation"][1])+ " sure that " + mention2+" patients show to have " + mention1 + ". "

                ## html
                sent10= "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1)+ "</span>" + " " +"<mark style='background-color:#5f96ff4d'>"+ " "  + "occurs in" + "</mark>" +" some " + "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention2) +"</span>" +  " " +"<mark style='background-color:#5f96ff4d'>"  +"patients." +  "<mark>"  +" Our finidng shows that the " + "<mark style='background-color:#5f96ff4d'>"+ "confidence of this association is approximately " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+"." + "</mark>" + " " + "Here is an excerpt of the literature (PMID: " + html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent20= "With a " +"<mark style='background-color:#5f96ff4d'>"+"confidence of " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+ "</mark>"+", we found that " + "<span style='color:#0058ff;font-weight:bold'>" +  html.escape(mention1)+ "</span>" +" " +"<mark style='background-color:#5f96ff4d'>" +"patients "+ "carry" + "</mark>"  +" " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2) + "</span>" +"." "This piece of relation is evidenced by the sentence in PMID: " +  html.escape(str(cre_sorted["pmid"])) + ': "'+ html.escape(cre_sorted["sentence"]) + '" '
                sent30= "As claimed by '"+  html.escape(cre_sorted["sentence"]) +"' PMID: (" + html.escape(str(cre_sorted["pmid"]))+"), we are " +  html.escape('{}'.format(cre_sorted["annotation"][1]))+ " sure that " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2)+ "</span>" + " " +  "<mark style='background-color:#5f96ff4d'>" + "patients show to have" + "</mark>" + " "  +"<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2) + "." + "</span>" + " "


            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + "that captures the relations: '" + cre_sorted["sentence"] +"' "
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + " as evidenced by '" + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+". "
                sent3= "According to the sentence: '" + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."

                ## html
                sent10= "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1)+ "'s"+ "</span>" + " relation with " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2) + "</span>"  + "is " + "<mark style='background-color:#5f96ff4d'>" + "presupposed."+ "</mark>" + " We are " + "<mark style='background-color:#5f96ff4d'>"+html.escape('{}'.format(cre_sorted["annotation"][1]))+ " " + "confidence" + "</mark>" + " about this association. " + "Here is an excerpt of the literature (PMID:" +html.escape(str(cre_sorted["pmid"]))+") " + "that captures the relations: '" + html.escape(cre_sorted["sentence"]) +"' "
                sent20= "It is " +"<mark style='background-color:#5f96ff4d'>"+ html.escape('{}'.format(cre_sorted["annotation"][1]))+ " "+  "presupposed"  +"</mark>" + "that "+ "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1) + "</span>" + " is related to "+ html.escape(mention2) + " as evidenced by '" + html.escape(cre_sorted["sentence"]) + "' (PMID: "+html.escape(str(cre_sorted["pmid"]))+". "
                sent30= "According to the sentence: '" + html.escape(cre_sorted["sentence"])+ "' (PMID: " + html.escape(str(cre_sorted["pmid"]))+") " + "The relation between " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1) + "</span>"   +" and " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2) +  "</span>"  + " contains a " +"<mark style='background-color:#5f96ff4d'>"+ "presupposition." + "</mark>"  +" "

            combined_mentions.add(mention1)
            combined_mentions.add(mention2)
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
            rbert_list2=[sent10,sent20,sent30]
            rbert_list2=random.choice(rbert_list2)
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


                ## html
                sent10 ='Moreover, there are also other relations found in this PMID: ' + html.escape(target)+ ', which includes the following. "' + "<mark style='background-color:#ff83894d'>" + html.escape(relation1) + "."  + "</mark>" + " " + "<mark style='background-color:#ff83894d'>"  + '"'+ html.escape(relation2)+ '."'+ "</mark>" + " "
                sent20 ='Notably, in this PMID, further relations between these two entities are discovered.'+ " " +  "<mark style='background-color:#ff83894d'>" +'"' + html.escape(relation1) + '."' +"</mark>" + " " + "<mark style='background-color:#ff83894d'>" + '"' + html.escape(relation2)+ '."' +"</mark>" + " "
                sent30 = 'PMID: ' + html.escape(target) + ' also entails relations:' + " " +"<mark style='background-color:#ff83894d'>"+ '"' + html.escape(relation1) + '"' +"</mark>" + " and " + "<mark style='background-color:#ff83894d'>"+ " " +'"'+ html.escape(relation2) +'."' + "</mark>"
            else:
                mention1=ore_sorted[0]["head"][2]
                mention2=ore_sorted[0]["tail"][2]
                combined_mentions.add(mention1)
                combined_mentions.add(mention2)
                sent1='In this PMID, we also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '." '
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '." '
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '." '

                ## html
                sent10 ='In this PMID, we also found' + " "+"<mark style='background-color:#ff83894d'>" +'"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '."' + "</mark>" + " "
                sent20 ="<mark style='background-color:#ff83894d'>"+ '"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '."' +"</mark>"+ " "
                sent30 ="In addition, " + "<mark style='background-color:#ff83894d'>" +'"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '."'+ "</mark>" + " "
            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
            triplet_list2=[sent10,sent20,sent30]
            triplet_list2=random.choice(triplet_list2)
        final_combine=list(combined_mentions)
        final_combine= ", ".join(final_combine[:-1]) + " and " + final_combine[-1]
        sent1= "PMID: " + target + " showcases that relations exist between these prominent mentions: " + final_combine + ". "
        sent2= "In PMID: " + target + ", our search results indicate that relations presented in " + final_combine + ". "
        sent3= "For " + final_combine, " in PMID: "+ target + ", some relations are extracted. "
        ## html
        sent10= "PMID: " +"<b>" + target + "</b>" +" showcases that relations exist between these prominent mentions: " +"<span style='color:#f99600;font-weight:bold'>" +final_combine + "." + "</span>" + " "
        sent20= "In PMID: " + "<b>" + target +"</b>"+ ", our search results indicate that relations presented in " + "<span style='color:#f99600;font-weight:bold'>" + final_combine + "</span>"  +"." + " "
        sent30= "For " + "<span style='color:#f99600;font-weight:bold'>" + final_combine + "</span>" +  " in PMID: "+"<b>" +target +"</b>" + ", some relations are extracted. "
        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        intro_list2=[sent10,sent20, sent30]
        intro_list2=random.choice(intro_list2)
        final_summary_ht=list(intro_list2)+list(odds_list2)+list(rbert_list2)+list(triplet_list2)
        final_summary_ht = ''.join(str(v) for v in final_summary_ht)
        logger.info("summary for single pmid: 22494505")
        return tuple([final_summary,final_summary_ht])
    else:
        final_summary = "There are not enough information for generating a substantial summary for this PMID. Please view the following table or re-enter the entity."
        final_summary_ht = html.escape("There are not enough information for generating a substantial summary for this PMID. Please view the following table or re-enter the PMID.")
        return tuple([final_summary,final_summary_ht])

## ABP
def gen_summary_by_pmid_pair(kb,evidence_id_list,target):
    detailed_evidence = []
    odds_list = [""]
    triplet_list = [""]
    rbert_list = [""]
    odds_list2 = [""]
    triplet_list2 = [""]
    rbert_list2 = [""]
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
                if target[1][2] in odds_sorted["head"]:
                    mention1 = odds_sorted["head"][2]
                elif target[1][2] in odds_sorted["tail"]:
                    mention1 = odds_sorted["tail"][2]
                logger.info("mention1_name00")
                print(mention1)
            if target[0] == "type_id" :
                if target[1][1] in odds_sorted["head"]:
                    mention1 = odds_sorted["head"][1]
                elif target[1][1] in odds_sorted["tail"]:
                    mention1= odds_sorted["tail"][1]
            if target[2] == "type_id_name" or target[2] == "type_name":
                if target[3][2] in odds_sorted["head"]:
                    mention2 = odds_sorted["head"][2]
                elif target[3][2] in odds_sorted["tail"]:
                    mention2= odds_sorted["tail"][2]
                logger.info("mention2_name")
                print(mention2)
            if target[2] == "type_id" :
                if target[3][1] in odds_sorted["head"]:
                    mention2 = odds_sorted["head"][1]
                elif target[3][1] in odds_sorted["tail"]:
                    mention2 = odds_sorted["tail"][1]
            sent1="The odds ratio found between " + mention1 + " and " + mention2+ " is " + str(odds_sorted["annotation"][0]) + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2])+ "). "
            sent2=mention1+ " and " + mention2 + " have an " + str(odds_sorted["annotation"][0])  + " (CI: " + str(odds_sorted["annotation"][1]) + ", p-value: "+  str(odds_sorted["annotation"][2]) + ")"+" odds ratio. "
            odds_list=[sent1,sent2]
            odds_list=random.choice(odds_list)
            ## html
            sent10 ="The odds ratio found between " + "<span style='color:#21d59b;font-weight:bold'>"  + html.escape(mention1) + "</span>" + " and " + "<span style='color:#21d59b;font-weight:bold'>" + html.escape(mention2)+  "</span>"  +" is " + "<mark style='background-color:#62e0b84d'>" + html.escape(str(odds_sorted["annotation"][0])) + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2]))+ ")." + "</mark>" + " "
            sent20 ="<span style='color:#21d59b;font-weight:bold'>"+ html.escape(mention1)+ "</span>"  +" and " +"<span style='color:#21d59b;font-weight:bold'>" +html.escape(mention2) + "</span>"  +" have an " + "<mark style='background-color:#62e0b84d'>"  + html.escape(str(odds_sorted["annotation"][0]))  + " (CI: " + html.escape(str(odds_sorted["annotation"][1])) + ", p-value: "+  html.escape(str(odds_sorted["annotation"][2])) + ")"+" odds ratio." + "</mark>" + " "
            odds_list2=[sent10,sent20]
            odds_list2=random.choice(odds_list2)
        if cre_sorted:
            if target[0] == "type_id_name" or target[0] == "type_name":
                if target[1][2] in cre_sorted["head"]:
                    mention1 = cre_sorted["head"][2]
                elif target[1][2] in cre_sorted["tail"]:
                    mention1= cre_sorted["tail"][2]
            if target[0] == "type_id" :
                if target[1][1] in cre_sorted["head"]:
                    mention1 = cre_sorted["head"][1]
                elif target[1][1] in cre_sorted["tail"]:
                    mention1= cre_sorted["tail"][1]
            if target[2] == "type_id_name" or target[2] == "type_name":
                if target[3][2] in cre_sorted["head"]:
                    mention2 = cre_sorted["head"][2]
                elif target[3][2] in cre_sorted["tail"]:
                    mention2 = cre_sorted["tail"][2]
            if target[2] == "type_id" :
                if target[3][1] in cre_sorted["head"]:
                    mention2 = cre_sorted["head"][1]
                elif target[3][1] in cre_sorted["tail"]:
                    mention2 = cre_sorted["tail"][1]
            if cre_sorted["head"][0] == "Disease" and (cre_sorted["tail"][0] == "SNP" or cre_sorted["tail"][0] == "ProteinMutation" or cre_sorted["tail"][0] =="CopyNumberVariant" or cre_sorted["tail"][0] == "DNAMutation"):
                # switch head and tail
                tmp=mention1
                mention1=mention2
                mention2=tmp
            if cre_sorted["annotation"][0]=="Cause-associated":
                sent1="We believe that there is a causal relationship between " +  str(mention1) +" and " + str(mention2)+ " with a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ". "+ "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + str(mention1)  + " is a causal variant of " + str(mention2)  + ". " + "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= "Based on the sentence (PMID: " +str(cre_sorted["pmid"])+") "+ ': "'+ cre_sorted["sentence"] + '" Our finding indicates that ' + str(mention1) + " is associated with " + str(mention2) + " by a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ ". "

                ## html
                sent10="We believe that there is a " +"<mark style='background-color:#5f96ff4d'>"+ "causal relationship" + "</mark>" + " between " + "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(str(mention1))+ "</span>" +" and " + "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(str(mention2))+ "</span>" + " with " + "<mark style='background-color:#5f96ff4d'>"+ "a confidence of " + html.escape('{}'.format(cre_sorted["annotation"][1]))+ "." + "</mark>" + " "+  "Here is an excerpt of the literature (PMID: " +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent20= "With a " + "<mark style='background-color:#5f96ff4d'>"+ "confidence of " + html.escape('{}'.format(cre_sorted["annotation"][1]))+ "</mark>" +", we found that " +"<span style='color:#0058ff;font-weight:bold'>"+ html.escape(str(mention1)) + "</span>" + " is a " + "<mark style='background-color:#5f96ff4d'>"+ "causal variant" + "</mark>" + " of " +"<span style='color:#0058ff;font-weight:bold'>"+ html.escape(str(mention2))+"</span>"  + ". " + "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent30= "Based on the sentence (PMID: " + html.escape(str(cre_sorted["pmid"]))+") "+ ': "'+ html.escape(cre_sorted["sentence"]) + '" Our finding indicates that ' + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(str(mention1)) + "</span>"+ " is " +"<mark style='background-color:#5f96ff4d'>"+ "associated with" + "</mark>"+ " " +"<span style='color:#0058ff;font-weight:bold'>"+ html.escape(str(mention2)) + "</span>" +" by " +"<mark style='background-color:#5f96ff4d'>"+ "a confidence of "+'{}'.format(cre_sorted["annotation"][1])+ "." + "</mark>" + " "

            if cre_sorted["annotation"][0]=="In-patient":
                sent1= mention1+ " occurs in some " + mention2 + " patients." " Our finidng shows that the confidence of this association is approximately " + '{}'.format(cre_sorted["annotation"][1])+". "+ "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "With a confidence of " + '{}'.format(cre_sorted["annotation"][1])+ ", we found that " + mention1+" patients "+ "carry " + mention2 +"." "This piece of relation is evidenced by the sentence in PMID: " + str(cre_sorted["pmid"]) + ': "'+cre_sorted["sentence"] + '" '
                sent3= 'As claimed by "'+ cre_sorted["sentence"] +'" ' + '{}'.format(cre_sorted["annotation"][1])+ ""+ " sure that " + mention2+" patients show to have " + mention1 + ". "
                ## html
                sent10= "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention1)+ "</span>"  +" occurs in some " + "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention2) +"</span>"  +" patients." " Our finidng shows that the confidence of this association is approximately " + html.escape('{}'.format(cre_sorted["annotation"][1]))+". "+ "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + html.escape(cre_sorted["sentence"]) +'" '
                sent20= "With a " +"<mark style='background-color:#5f96ff4d'>"+ "confidence of " + html.escape('{}'.format(cre_sorted["annotation"][1]))+"</mark>" + ", we found that " +"<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention1)+"</span>" +" " + "<mark style='background-color:#5f96ff4d'>"+ "patients "+ "carry" + "</mark>" + " " +"<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention2) +"."+"</mark>" +  "This piece of relation is evidenced by the sentence in PMID: " + html.escape(str(cre_sorted["pmid"])) + ': "'+html.escape(cre_sorted["sentence"]) + '" '
                sent30= 'As claimed by "'+ html.escape(cre_sorted["sentence"]) +'" ' +"<mark style='background-color:#5f96ff4d'>"+ html.escape('{}'.format(cre_sorted["annotation"][1]))+ " sure" +"</mark>" + " "  +"that" + " "+ "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention2)+"</span>" +" " + "<mark style='background-color:#5f96ff4d'>"+ "patients show to have" +"</mark>" +" " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1) + "." + "</span>" + " "

            if cre_sorted["annotation"][0]=="Appositive":
                sent1= mention1+ "'s relation with " + mention2 + "is presupposed." + " We are " + '{}'.format(cre_sorted["annotation"][1])+ " " + "confidence about this association. " + "Here is an excerpt of the literature (PMID:" +str(cre_sorted["pmid"])+") " + 'that captures the relations: "' + cre_sorted["sentence"] +'" '
                sent2= "It is " + '{}'.format(cre_sorted["annotation"][1])+" "+  "presupposed that "+ mention1 + " is related to "+ mention2 + ' as evidenced by "' + cre_sorted["sentence"] + "' (PMID: "+str(cre_sorted["pmid"])+'." '
                sent3= 'According to the sentence: "' + cre_sorted["sentence"]+ "' (PMID: " + str(cre_sorted["pmid"])+") " + "The relation between " + mention1 + " and " + mention2 + " contains a presupposition."

                ## html
                sent10= "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1)+ "'s" + "</span>" +" relation with " + "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2) + "</span>" + "is" + "<mark style='background-color:#ff83894d'>"+"presupposed." + "</mark>" +" We are " + "<mark style='background-color:#5f96ff4d'>"+html.escape('{}'.format(cre_sorted["annotation"][1]))+ " " + "confident" +"</mark>"+ " about this association. " + "Here is an excerpt of the literature (PMID:" +html.escape(str(cre_sorted["pmid"]))+") " + 'that captures the relations: "' + html.escape(cre_sorted["sentence"]) +'" '
                sent20= "It is " + "<mark style='background-color:#5f96ff4d'>"+ html.escape('{}'.format(cre_sorted["annotation"][1]))+" "+  "presupposed" + "</mark>" +" that "+ "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention1) +  "</span>"  +" is related to "+ "<span style='color:#0058ff;font-weight:bold'>" + html.escape(mention2) + "</span>" + ' as evidenced by "' + html.escape(cre_sorted["sentence"]) + "' (PMID: "+html.escape(str(cre_sorted["pmid"]))+'." '
                sent30= 'According to the sentence: "' + html.escape(cre_sorted["sentence"])+ "' (PMID: " + html.escape(str(cre_sorted["pmid"]))+") " + "The relation between " + "<span style='color:#0058ff;font-weight:bold'>"+ html.escape(mention1) + "</span>" +" and " +"<span style='color:#0058ff;font-weight:bold'>"+html.escape(mention2) +  "</span>" +" contains a " + "<mark style='background-color:#ff83894d'>"+"presupposition." + "</mark>" + " "
            rbert_list=[sent1,sent2,sent3]
            rbert_list=random.choice(rbert_list)
            rbert_list2=[sent10,sent20,sent30]
            rbert_list2=random.choice(rbert_list2)
        if ore_sorted:
            if len(ore_sorted)==2:
                if target[0] == "type_id_name" or target[0] == "type_name":
                    if target[1][2] in ore_sorted[0]["head"]:
                        mention1 = ore_sorted[0]["head"][2]
                    elif target[1][2] in ore_sorted[0]["tail"]:
                        mention1 = ore_sorted[0]["tail"][2]
                if target[0] == "type_id" :
                    if target[1][1] in ore_sorted[0]["head"]:
                        mention1 = ore_sorted[0]["head"][1]
                    elif target[1][1] in ore_sorted[0]["tail"]:
                        mention1= ore_sorted[0]["tail"][1]
                if target[2] == "type_id_name" or target[2] == "type_name":
                    if target[3][2] in ore_sorted[1]["head"]:
                        mention2 = ore_sorted[1]["head"][2]
                    elif target[3][2] in ore_sorted[1]["tail"]:
                        mention2 = ore_sorted[1]["tail"][2]
                if target[2] == "type_id" :
                    if target[3][1] in ore_sorted[1]["head"]:
                        mention2 = ore_sorted[1]["head"][1]
                    elif target[3][1] in ore_sorted[1]["tail"]:
                        mention2 = ore_sorted[1]["tail"][1]
                relation1 = ' '.join(ore_sorted[0]["annotation"])
                relation2= ' '.join(ore_sorted[1]["annotation"])
                sent1='Moreover, there are also other relations found in this PMID: ' + target[4]+ ', which includes the following. "' + relation1 + '." "' + relation2+ '." '
                sent2='Notably, in this PMID, further relations between these two entities are discovered. "' + relation1 + '." "' + relation2+ '." '
                sent3= 'PMID: ' + target[4] + ' also entails relations: "' + relation1 + '"' + " and " + '"' + relation2 +'."'
               ## html
                sent10='Moreover, there are also other relations found in this PMID: ' + html.escape(target[4])+ ', which includes the following. ' + "<mark style='background-color:#ff83894d'>" +'"' + html.escape(relation1) + '."' + "</mark>" + " " + "<mark style='background-color:#ff83894d'>" +  '"' + html.escape(relation2)+ '."' + "</mark>" + " "
                sent20='Notably, in this PMID, further relations between these two entities are discovered. ' + "<mark style='background-color:#ff83894d'>" + '"' + html.escape(relation1) + '."' + "</mark>"+ " " +"<mark style='background-color:#ff83894d'>"+  '"' + html.escape(relation2)+ '."' + "</mark>" + " "
                sent30= 'PMID: ' + html.escape(target[4]) + ' also entails relations: '  + "<mark style='background-color:#ff83894d'>"   + '"'+ html.escape(relation1) + '"' + "</mark>"  +" and " + "<mark style='background-color:#ff83894d'>" + '"' + html.escape(relation2) +'."'  + "</mark>" + " "
            else:
                if target[0] == "type_id_name" or target[0] == "type_name":
                    if target[1][2] in ore_sorted[0]["head"]:
                        mention1 = ore_sorted[0]["head"][2]
                    elif target[1][2] in ore_sorted[0]["tail"]:
                        mention1 = ore_sorted[0]["tail"][2]
                if target[0] == "type_id" :
                    if target[1][1] in ore_sorted[0]["head"]:
                        mention1 = ore_sorted[0]["head"][1]
                    elif target[1][1] in ore_sorted[0]["tail"]:
                        mention1= ore_sorted[0]["tail"][1]
                if target[2] == "type_id_name" or target[2] == "type_name":
                    if target[3][2] in ore_sorted[0]["head"]:
                        mention2 = ore_sorted[0]["head"][2]
                    elif target[3][2] in ore_sorted[1]["tail"]:
                        mention2 = ore_sorted[0]["tail"][2]
                if target[2] == "type_id" :
                    if target[3][1] in ore_sorted[1]["head"]:
                        mention2 = ore_sorted[0]["head"][1]
                    elif target[3][1] in ore_sorted[1]["tail"]:
                        mention2 = ore_sorted[0]["tail"][1]
                sent1='We also found "'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                sent2='"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "
                sent3="In addition, " +'"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + ". "

                ## html
                sent10='We also found'+"<mark style='background-color:#ff83894d'>"+' "' + html.escape(' '.join(ore_sorted[0]["annotation"])) + '"'+ "." + "</mark>" + " "
                sent20="<mark style='background-color:#ff83894d'>"+'"'+ ' '.join(ore_sorted[0]["annotation"]) + '"' + "." + "</mark>" + " "
                sent30="In addition, "+ "<mark style='background-color:#ff83894d'>" +'"'+ html.escape(' '.join(ore_sorted[0]["annotation"])) + '"' + "." + "</mark>" + " "

            triplet_list=[sent1,sent2,sent3]
            triplet_list=random.choice(triplet_list)
            triplet_list2=[sent10,sent20,sent30]
            triplet_list2=random.choice(triplet_list2)
        sent1="Based on our search results, relation exists between " +mention1 + " and " + mention2 + " in PMID: " + target[4] + ". "
        sent2="Relations occur between "+ mention1 + " and " + mention2 + " as shown from our search for PMID: " + target[4] + ". "
        sent3=mention1 + " and " + mention2 + " relate to each other in PMID: " + target[4] +". "

        ## html
        sent10 = "Based on our search results, relation exists between " + "<b>"+  html.escape(mention1)+ "</b>" + " and " + "<b>"+ html.escape(mention2) + "</b>" + " in PMID: " + "<b>"+ html.escape(target[4]) + "</b>"+ ". "
        sent20 ="Relations occur between "+ "<b>"+ html.escape(mention1) + "</b>" + " and " + "<b>"+ html.escape(mention2)+ "</b>"  + " as shown from our search for PMID: " + "<b>"+ html.escape(target[4]) + "</b>"+ ". "
        sent30 = "<b>"+html.escape(mention1) + "</b>" + " and "+ "<b>" + html.escape(mention2)+ "</b>"  + " relate to each other in PMID: " + "<b>"+ target[4]+ "</b>" +". "

        intro_list=[sent1,sent2, sent3]
        intro_list=random.choice(intro_list)
        summary=list(intro_list)+list(odds_list)+list(rbert_list)+list(triplet_list)
        final_summary = ''.join(str(v) for v in summary)
        logger.info("summary for pmid and single pair: rs4925 & MESH:D012871 & 29323258")
        intro_list2=[sent10,sent20, sent30]
        intro_list2=random.choice(intro_list2)
        final_summary_ht=list(intro_list2)+list(odds_list2)+list(rbert_list2)+list(triplet_list2)
        final_summary_ht = ''.join(str(v) for v in final_summary_ht)
        logger.info("summary for pmid and single pair: rs4925 & MESH:D012871 & 29323258")
        return tuple([final_summary,final_summary_ht])
    else:
        final_summary = "There are not enough information for generating a substantial summary for this PMID and pair. Please view the following table or re-enter the entity."
        final_summary_ht = html.escape("There are not enough information for generating a substantial summary for this PMID. Please view the following table or re-enter the PMID.")
        return tuple([final_summary,final_summary_ht])

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

    # test none
    evidence_id_list = [1869807,1869813,343203,343227,398056,444473,459084,554087,601608,601614,636431,1292876,1875988,801997,1292888,1842892,2632957,2632962,2632996,3094696]
    # print(gen_summary_by_entity(kb=kb,evidence_id_list=evidence_id_list, target=("type_id",("Disease", "MESH:D012871", "skin lesions"))))
    text=get_summary(kb,evidence_id_list, target=None, query_filter="X")
    print(text)

    # test A
    evidence_id_list = [928292,1395158,2449403,2449407,2449411,2584152,227365,570299,570313,570323,900159,900183,928286,4836,21298,21692,25199,34845,35464,35468,35493,35494,36495,2467,3086,4837,10339,10839,14928,15549,16764,19499,20412]
    # print(gen_summary_by_entity(kb=kb,evidence_id_list=evidence_id_list, target=("type_id",("Disease", "MESH:D012871", "skin lesions"))))
    text=get_summary(kb,evidence_id_list, target=("type_id",("Disease", "MESH:D012871", "skin lesions")), query_filter="A")
    print(text)

    # test AB
    evidence_id_list = [444474,636438,697193,726676,802003,881275,962387,989533,1016015,1016021,801999,2632963,2632997,2640407]
    # evidence_id_list = [2449403,2449404,2449405,2449406,2449353,2449364,2449365,2449366,2449367,2449382]
    # print(gen_summary_by_pair(kb=kb,evidence_id_list=evidence_id_list, target=("type_name",("SNP", "RS#:4925", "rs4925"),"type_id",("Disease", "MESH:D012871", "skin lesions"))))
    text=get_summary(kb,evidence_id_list, target=("type_name",("Disease", "???", "tumors"),"type_id",("Disease", "HGVS:p.V600E", "???")), query_filter="AB")
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
    # from kb_utils import KB
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb_dir", type=str, default="/volume/summary/data")
    arg = parser.parse_args()
    test_summary(arg.kb_dir)
    return

if __name__ == "__main__":
    main()
    sys.exit()