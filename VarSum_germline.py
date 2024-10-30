import random
import numpy as np
import pandas as pd
import re
import logging
from HGVSp_parser import HGVSpParser
from VarSum_utils import find_CDS_pos, ordinal_suffix, clinvar_translate, vep_consequence_translate

class GermlineVarSum:
    def __init__(self, sample, lang='Zh', sample_keys = None, create_data = False, delexicalized = False):
        self.sample = sample.copy()
        # setting
        self.lang = lang
        self.delexicalized = delexicalized
        self.sample_keys = sample_keys if sample_keys else ['VEP_VEP-refseq-Gene-Name', 'VEP_VEP-refseq-HGVSc', 'Otherinfo_FORMAT-GT', 'VEP_VEP-refseq-Consequence', 'VEP_VEP-refseq-HGVSp',
                            'VEP_VEP-refseq-Exon-or-Intron-Rank', 'ClinVar_CLNSIG', 'VEP_VEP-ensembl-Transcript-ID',
                            'gnomAD-Genomes_AF-popmax', 'TaiwanBiobank-official_Illumina1000-AF', 'pathogenicHotspot-ailabs_pathogenicHotspot',
                            'Pathogenicity Scores_Ensembl-transcriptid', 'Pathogenicity Scores_SIFT-score', 'Pathogenicity Scores_Polyphen2-HVAR-score',
                            'Pathogenicity Scores_VEST4-score', 'Pathogenicity Scores_PROVEAN-pred', 'CADD_PHRED', 'DANN_DANN-score', 
                            'SpliceAI-SNV_DS-AG', 'SpliceAI-SNV_DS-AL', 'SpliceAI-SNV_DS-DG', 'SpliceAI-SNV_DS-DL', 
                            'Conservation Scores_phyloP100way-vertebrate-rankscore',
                            'ANNOVAR_ANNOVAR-ensembl-Transcript-ID'] #TODO: 資料改版後不使用此欄位

        self.pathogenicity_SW = ['SIFT', 'PolyPhen2', 'CADD-phred', 'VEST4', 'PROVEAN', 'DANN', 'spliceAI']
        self.conservation_SW = ['phyloP100way']

        ## for linearization planning
        self.shared_attributes = ['genotype', 'consequence', 'HGVSc', 'gene_name', 'reference', 'CDS_position', 'exon_or_intron_rank',
                                  'HGVSp', #'original_position_init', 'original_amino_acid_init', 'original_position_end', 'original_amino_acid_end', 'changed_position', 'changed_amino_acid', 
                                  'ClinVar_record', 'hotspot', 'gnomAD_freq', 'TaiwanBiobank_freq', 
                                  'pathogenicity_prediction', 'conservation_prediction']
        # process
        self.preprocessing(self.sample, self.sample_keys)
        self.table = self.table_cleaning(self.sample, create_data)
        if delexicalized:
            self.delexicalized_table, self.reversed_map = self.delexicalize_table(self.table)
            self.text_enus_delexicalized = self.template_enus(self.delexicalized_table, delexicalized = True)
        self.text_enus = self.template_enus(self.table)
        self.text_zhtw = self.template_zhtw(self.table)
        self.template_na()


    def preprocessing(self, sample, keys):
        for key in keys:
            if key not in sample.keys() or pd.isna(sample[key]):
                logging.warning(f"[VarSum: preprocessing] Incomplete data! '{key}' is missing...")
                sample[key] = "."
            else:
                if type(sample[key]) == list:
                    sample[key] = sample[key][0]

    def table_cleaning(self, sample, create_data = False):
        table = {}
        # gene name
        if sample['VEP_VEP-refseq-Gene-Name'] != ".":
            table['gene_name'] = sample['VEP_VEP-refseq-Gene-Name']
        else: table['gene_name'] = '.'
        
        # Genotype
        if create_data and table['gene_name'] != '.':
            # create data (for training)
            n = random.random()
            if n > 0.5:
                table['genotype'] = 'homozygous'
                table['genotype_zhtw'] = '同型合子（homozygous）'
                self.sample['Otherinfo_FORMAT-GT'] = '1/1'
            else:
                table['genotype']  = 'heterozygous'
                table['genotype_zhtw'] = '異型合子（heterozygous）'
                tmp_n = random.random()
                if tmp_n > 0.5:
                    self.sample['Otherinfo_FORMAT-GT'] = '1/0'
                else:
                    self.sample['Otherinfo_FORMAT-GT'] = '0/1'
        else:
            # preprocessing data
                ## 1/1     : homozygous
                ## 1/0, 0/1: heterozygous
            if sample['Otherinfo_FORMAT-GT'] != ".":
                if sample['Otherinfo_FORMAT-GT'].split("/")[0] == sample['Otherinfo_FORMAT-GT'].split("/")[1]:
                    table['genotype'] = 'homozygous'
                    table['genotype_zhtw'] = '同型合子（homozygous）'
                else:
                    table['genotype']  = 'heterozygous'
                    table['genotype_zhtw'] = '異型合子（heterozygous）'
            else:
                table['genotype']  = ''
                table['genotype_zhtw'] = ''
        
        # HGVSc, exon/intron position
        if sample['VEP_VEP-refseq-HGVSc'] != ".":
            table['reference'], table['HGVSc'] = sample['VEP_VEP-refseq-HGVSc'].split(':') # e.g. NM_001005484.2:c.107A>G
            table['CDS_position'] = find_CDS_pos(table['HGVSc'].split('.')[-1]).strip() # c.107A>G -> 107
            match = re.search(r'^[*-]', table['CDS_position']) # check if the position is in 3'- or 5'- UTR (starting with * or -)
            if match:
                if match.group(0) == '*':
                    table['exon_intron'] = "3'-UTR"
                    table['exon_intron_zhtw'] = '三端非轉譯區'
                else:
                    table['exon_intron'] = "5'-UTR"
                    table['exon_intron_zhtw'] = '五端非轉譯區'
            elif re.search(r'[+-]', table['CDS_position']): # check if the position is in intron (includes + or -)
                table['exon_intron'] = 'intron'
                table['exon_intron_zhtw'] = '內含子'
            else: # else the position is in exon
                table['exon_intron'] = 'exon'
                table['exon_intron_zhtw'] = '外顯子'
            table['CDS_position'] = ', '.join(table['CDS_position'].split('_'))
        else: # if there is no VEP_VEP-refseq-HGVSc information -> usually in intron
            table['reference'], table['HGVSc'] = ['.', '.']
            table['CDS_position'] = '.'
            table['exon_intron'] = 'intron'
            table['exon_intron_zhtw'] = '內含子'
        
        # exon/intron rank
        if sample['VEP_VEP-refseq-Exon-or-Intron-Rank'] != '.':
            exon_intron_rank = sample['VEP_VEP-refseq-Exon-or-Intron-Rank'].split('/')[0] # e.g. 3/3 (indicate there are 3 exon or intron region, the variant is in the 3rd exon or intron)
            if table['exon_intron'] in ['exon', 'intron']:
                table['exon_or_intron_rank'] = ' '.join([table['exon_intron'], exon_intron_rank])
                table['exon_or_intron_rank_zhtw'] = '第{:s}{:s}'.format(exon_intron_rank, table['exon_intron_zhtw'])
            else: # the variant is in 3'- or 5'- UTR -> no need intron/exon rank
                table['exon_or_intron_rank'] = table['exon_intron']
                table['exon_or_intron_rank_zhtw'] = table['exon_intron_zhtw']
        else:
            table['exon_or_intron_rank'] = table['exon_intron']
            table['exon_or_intron_rank_zhtw'] = table['exon_intron']
        
        # HGVSp
        if sample['VEP_VEP-refseq-HGVSp'] != '.':
            table['HGVSp'] = sample['VEP_VEP-refseq-HGVSp'].split(':')[1] # e.g. NP_001005484.2:p.Glu36Gly
        else:
            table['HGVSp'] = '.'
        # HGVSp parsing
        self.hgvsp_parse = HGVSpParser(table['HGVSp'])
        [table['original_position_init'], table['original_amino_acid_init'], 
         table['original_position_end'], table['original_amino_acid_end'], 
         table['changed_position'], table['changed_amino_acid']] = self.hgvsp_parse.aa_pos_dict.values() # e.g. p.Glu36Gly
        table['change_type'] = self.hgvsp_parse.type
        table['HGVSp'] = self.hgvsp_parse.HGVSp
        
        # Consequence
        if sample['VEP_VEP-refseq-Consequence'] != '.':
            tmp_cons_zhtw, tmp_cons_enus = vep_consequence_translate(sample['VEP_VEP-refseq-Consequence']) # e.g. missense_variant,intron_variant

            table['consequence_zhtw'] = '、'.join(tmp_cons_zhtw) # chinese: concatenate the consequences with "、" (if more than one)
            table['consequence'] = ', '.join(tmp_cons_enus) # english: concatenate the consequences with "," (if more than one)
        else:
            table['consequence_zhtw'] = ''
            table['consequence'] = ''
        
        # pathogenicity record from ClinVar
        if sample['ClinVar_CLNSIG'] != ".":
            table['ClinVar_record'] = " ".join(sample['ClinVar_CLNSIG'].split('_')) # e.g. Likely_benign -> Likely benign
            try:
                table['ClinVar_record_zhtw'] = clinvar_translate(table['ClinVar_record'].strip()) # translate to chinese
            except KeyError:
                table['ClinVar_record_zhtw'] = table['ClinVar_record'] # the term is not in dictionary -> report in origin term (in English)
        else:
            table['ClinVar_record'] = '.'
            table['ClinVar_record_zhtw'] = '.'

        # Transcript ID
        if sample['VEP_VEP-ensembl-Transcript-ID'] != '.':
            table['transcriptid_MANE'] = sample['VEP_VEP-ensembl-Transcript-ID'].split('.')[0] # e.g. ENST00000641515.5 -> remove version code: ENST00000641515
        elif sample['ANNOVAR_ANNOVAR-ensembl-Transcript-ID'] != '.':
            table['transcriptid_MANE'] = sample['ANNOVAR_ANNOVAR-ensembl-Transcript-ID'].split('.')[0] #TODO: 資料庫改版後會使用別的欄位
        else: table['transcriptid_MANE'] = '.'
        # list of Transcripts from the result of Pathogenicity prediction -> for reporting the pathogenicity prediction of MANE transcript ID
        if sample['Pathogenicity Scores_Ensembl-transcriptid'] != ".":
            table['Ensembl_transcriptid'] = [transcript.strip() for transcript in sample['Pathogenicity Scores_Ensembl-transcriptid'].split(';')]
                # e.g. ENST00000641515;ENST00000335137
            if table['transcriptid_MANE'] in table['Ensembl_transcriptid']: # check if MANE transcript ID is in the list 
                table['transcriptid_index'] = table['Ensembl_transcriptid'].index(table['transcriptid_MANE']) # keep the index of MANE in the list
            else: table['transcriptid_index'] = -1
        else:
            table['Ensembl_transcriptid'] = '.'
            table['transcriptid_index'] = -1

        # Pathogenicity prediction: 
        default_value = '.'
        table['pathogenicity_prediction'] = dict.fromkeys(self.pathogenicity_SW, default_value)
        if table['transcriptid_index'] != -1: # MANE transcript ID is in the list of Transcripts from the result of pathogenicity prediction -> report pathogenicity prediction
            ## SIFT score
            if sample['Pathogenicity Scores_SIFT-score'] != ".":
                table['SIFT_all'] = str(sample['Pathogenicity Scores_SIFT-score']).split(';') # e.g. ".;0.129"
                table['pathogenicity_prediction']['SIFT'] = table['SIFT_all'][table['transcriptid_index']] # get prediction of MANE
            ## Polyphen2 score
            if sample['Pathogenicity Scores_Polyphen2-HVAR-score'] != ".":
                table['PolyPhen2_all'] = str(sample['Pathogenicity Scores_Polyphen2-HVAR-score']).split(';') # e.g. ".;0.001"
                table['pathogenicity_prediction']['PolyPhen2'] = table['PolyPhen2_all'][table['transcriptid_index']] # get prediction of MANE
            ## VEST4 rankscore
            if sample['Pathogenicity Scores_VEST4-score'] != ".":
                table['VEST4_all'] = str(sample['Pathogenicity Scores_VEST4-score']).split(';') # e.g. ".;0.107"
                table['pathogenicity_prediction']['VEST4'] = table['VEST4_all'][table['transcriptid_index']] # get prediction of MANE
            ## PROVEAN score
            if sample['Pathogenicity Scores_PROVEAN-pred'] != ".":
                table['PROVEAN_all'] = str(sample['Pathogenicity Scores_PROVEAN-pred']).split(';') # e.g. ".;D"
                table['pathogenicity_prediction']['PROVEAN'] = table['PROVEAN_all'][table['transcriptid_index']] # get prediction of MANE
        ## CADD-phred score
        if sample['CADD_PHRED'] != ".":
            table['pathogenicity_prediction']['CADD-phred'] = str(sample['CADD_PHRED']) # e.g. 16.91
        ## DANN
        if sample['DANN_DANN-score'] != ".":
            try:
                table['pathogenicity_prediction']['DANN']= "{:.3f}".format(round(float(sample['DANN_DANN-score']),3)) # e.g. 0.9577714132251449
            except ValueError:
                table['pathogenicity_prediction']['DANN']= "."
        ## SpliceAI
        if sample['SpliceAI-SNV_DS-AG'] != ".":
            table['pathogenicity_prediction']['spliceAI'] = {}
            table['pathogenicity_prediction']['spliceAI']['AG'] = "{:.3f}".format(round(float(sample['SpliceAI-SNV_DS-AG']), 3)) # e.g. 0.0
            table['pathogenicity_prediction']['spliceAI']['AL'] = "{:.3f}".format(round(float(sample['SpliceAI-SNV_DS-AL']), 3))
            table['pathogenicity_prediction']['spliceAI']['DG'] = "{:.3f}".format(round(float(sample['SpliceAI-SNV_DS-DG']), 3))
            table['pathogenicity_prediction']['spliceAI']['DL'] = "{:.3f}".format(round(float(sample['SpliceAI-SNV_DS-DL']), 3))
            if create_data:
                tmp_n = random.random()
                if tmp_n > 0.6:
                    del_type = random.sample(['AG', 'AL', 'DG', 'DL'],1)
                elif tmp_n < 0.3:
                    del_type = random.sample(['AG', 'AL', 'DG', 'DL'],2)
                else:
                    del_type = []
                for type_i in del_type:
                    del table['pathogenicity_prediction']['spliceAI'][type_i]


        if any([table['pathogenicity_prediction'][key] != '.' for key in self.pathogenicity_SW]): # if these is any prediction of MANE -> pathogenicity = "recorded"
            table['pathogenicity'] = 'recorded'
        else: 
            table['pathogenicity'] = '.'
            table['pathogenicity_prediction'] = '.'
        
        # Conservation Scores: phyloP100way
        default_value = '.'
        table['conservation_prediction'] = dict.fromkeys(self.conservation_SW, default_value)
        if sample['Conservation Scores_phyloP100way-vertebrate-rankscore'] != ".":
            try:
                table['conservation_prediction']['phyloP100way']= "{:.3f}".format(round(float(sample['Conservation Scores_phyloP100way-vertebrate-rankscore']),3)) # e.g. 0.20738
            except ValueError:
                table['conservation_prediction']= "."

        if any([table['conservation_prediction'][key] != '.' for key in self.conservation_SW]): # if these is any prediction of MANE -> pathogenicity = "recorded"
            table['conservation'] = 'recorded'
        else: table['conservation'] = '.'
        
        # Allele Frequency: gnomAD
        if sample['gnomAD-Genomes_AF-popmax'] != ".":
            try:
                table['gnomAD_freq'] = "{:.6f}".format(round(float(sample['gnomAD-Genomes_AF-popmax']),6)) # e.g. 0.00301205
            except ValueError:
                table['gnomAD_freq'] = "."
        else:
            table['gnomAD_freq'] = "."

        # Allele Frequency: TaiwanBiobank
        if sample['TaiwanBiobank-official_Illumina1000-AF'] != ".":
            try:
                table['TaiwanBiobank_freq'] = "{:.6f}".format(round(float(sample['TaiwanBiobank-official_Illumina1000-AF']),6))
            except ValueError:
                table['TaiwanBiobank_freq'] = '.'
        else:
            table['TaiwanBiobank_freq'] = '.'
        
        # hotspot region
        if sample['pathogenicHotspot-ailabs_pathogenicHotspot'] != ".":
            DB_ls = list(set([DB.strip() for DB in sample['pathogenicHotspot-ailabs_pathogenicHotspot'].split(',')])) # e.g. DeafnessVD,ClinVar
            if len(DB_ls) > 2: # hotspot record from more than 2 database
                table['hotspot'] = ', '.join(DB_ls[:-1]) + ', and ' + DB_ls[-1]
                table['hotspot_zhtw'] = '、'.join(DB_ls[:-1]) + '和' + DB_ls[-1]
            else:
                table['hotspot'] = ' and '.join(DB_ls)
                table['hotspot_zhtw'] = '和'.join(DB_ls)
        else:
            table['hotspot'] = '.'
            table['hotspot_zhtw'] ='.'
        
        return table
    
    def delexicalize_table(self, table):
        delexicalized_table = table.copy()
        reversed_map = {}
        delexicalization = {
            'gene_name': 'GENE',
            #'genotype': 'GENOTYPE',
            'consequence': 'CONSEQUENCE',
            #'CDS_position': 'CDS_POS',
            'HGVSc':'HGVSC',
            'reference': 'REFERENCE',
            #'HGVSp': 'HGVSP',
            'ClinVar_record': 'CLINVARRECORD',
            #'gnomAD_freq': 'FREQUENCY_1',
            #'TaiwanBiobank_freq': 'FREQUENCY_2',
            'pathogenicity_prediction': 'PATHOGENICITY_TOOL',
            'conservation_prediction': 'CONSERVATION_TOOL'
        }
        for key, delexica_value in delexicalization.items():
            if all(delexicalized_table[key] != con for con in ['.', '']):
                if key in ['pathogenicity_prediction', 'conservation_prediction']:
                    tmp_dict = {}
                    i = 1
                    for subtype in delexicalized_table[key].keys():
                        if all(delexicalized_table[key][subtype] != con for con in ['.', '']):
                            reversed_map[delexica_value+f"_{i}"] = subtype
                            if type(delexicalized_table[key][subtype]) == dict:
                                prefix = "SUBTYPE_"
                                j = 1
                                sub_dict = {}
                                for k in delexicalized_table[key][subtype].keys():
                                    reversed_map[prefix+f"{j}"] = k
                                    sub_dict[prefix+f"{j}"] = delexicalized_table[key][subtype][k]
                                    j += 1
                                tmp_dict[delexica_value+f"_{i}"] = sub_dict
                            else:
                                tmp_dict[delexica_value+f"_{i}"] = delexicalized_table[key][subtype]
                            i += 1

                    delexicalized_table[key] = tmp_dict
                else:
                    reversed_map[delexica_value] = delexicalized_table[key]
                    delexicalized_table[key] = delexica_value
        for attr, delexicalized_value in zip([ 'changed_amino_acid', 'original_amino_acid_end', 'original_amino_acid_init'], ['CHANGED_AA', 'ORIGINAL_AA_END', 'ORIGINAL_AA_INIT']):
            if table[attr][0] != '.':
                replace_value = delexicalized_table[attr][0].replace('Ter/', '').replace('=/', '')
                reversed_map[delexicalized_value] = replace_value
                #delexicalized_table[attr] = delexicalized_value
        for attr, delexicalized_value in zip(['original_position_init', 'original_position_end', 'changed_position'], ['ORIGINAL_POS_INIT', 'ORIGINAL_POS_END', 'CHANGED_POS']):
            if all(table[attr] != con for con in ['.', '', '?']):
                replace_value = ordinal_suffix(delexicalized_table[attr])
                reversed_map[delexicalized_value] = replace_value
        reversed_map['HGVSP'] = delexicalized_table['HGVSp']
        return delexicalized_table, reversed_map

    def template_zhtw(self, table):
        """
            template-based report in Chinese
        """
        text_zhtw = {}

        if table['gene_name'] != ".":
            if table['HGVSc'] == "." : # without HGVSc annotation
                if table['genotype'] == "": # without genotype information
                    text_zhtw['gene_name'] = [f"個案之{table['gene_name']}基因偵測到{table['consequence_zhtw']}變異。", # NTUH
                                            f"此個案之{table['gene_name']}基因序列含有{table['consequence_zhtw']}變異，",
                                            f"檢測結果顯示，{table['gene_name']}基因序列含有{table['consequence_zhtw']}變異，",
                                            f"在此個案中，有一個{table['consequence_zhtw']}變異在{table['gene_name']}基因中被檢測出來，"]
                else:
                    text_zhtw['gene_name'] = [f"個案之{table['gene_name']}基因偵測到{table['consequence_zhtw']}變異。", # NTUH"
                                            f"此個案之{table['gene_name']}基因序列含有{table['consequence_zhtw']}變異，被偵測到發生{table['genotype_zhtw']}核苷酸序列變化，",
                                            f"檢測結果顯示，{table['gene_name']}基因序列含有一個{table['genotype_zhtw']}{table['consequence_zhtw']}變異，",
                                            f"在此個案中，有一個{table['consequence_zhtw']}變異在{table['gene_name']}基因中被檢測出來，使核苷酸序列發生{table['genotype_zhtw']}改變，"]
            else: # with HGVSc annotation -> get CDS position
                if len(table['CDS_position'].split(', ')) > 1:
                    if any(ann in table['HGVSc'] for ann in ['del', 'dup']):
                        tmp_position = f"從{'至'.join(['第'+ pos for pos in table['CDS_position'].split(', ')])}個核苷酸"
                    else:
                        tmp_position = f"在{'和'.join(['第'+ pos for pos in table['CDS_position'].split(', ')])}個核苷酸之間"
                else:
                    tmp_position = f"第{table['CDS_position']}個核苷酸"

                    
                if table['genotype'] == "": # without genotype information
                    text_zhtw['gene_name'] = [f"個案之{table['gene_name']}（{table['reference']}）基因{table['exon_or_intron_rank_zhtw']}偵測到{table['HGVSc']}核苷酸{table['consequence_zhtw']}變異。", # NTUH
                                            f"此個案之{table['gene_name']}基因序列（{table['reference']}）{tmp_position}發生{table['consequence_zhtw']}變異（{table['HGVSc']}）。",
                                            f"檢測結果顯示，此個案之{table['gene_name']}基因序列（{table['reference']}）{tmp_position}（位於{table['exon_or_intron_rank_zhtw']}中）發生一個{table['consequence_zhtw']}變異（{table['HGVSc']}）。",
                                            f"在此個案中，有一個{table['consequence_zhtw']}變異在{table['gene_name']}基因（{table['reference']}）{tmp_position}的位置（位於{table['exon_or_intron_rank_zhtw']}中）被檢測出來（{table['HGVSc']}）。"]
                else:
                    text_zhtw['gene_name'] = [f"個案之{table['gene_name']}（{table['reference']}）基因{table['exon_or_intron_rank_zhtw']}偵測到{table['HGVSc']}核苷酸{table['consequence_zhtw']}變異。", # NTUH
                                            f"此個案之{table['gene_name']}基因序列（{table['reference']}）{tmp_position}（位於{table['exon_or_intron_rank_zhtw']}中）發生{table['consequence_zhtw']}變異，發生{table['genotype_zhtw']}核苷酸序列變化（{table['HGVSc']}）。",
                                            f"檢測結果顯示，此個案之{table['gene_name']}基因序列（{table['reference']}）{tmp_position}（位於{table['exon_or_intron_rank_zhtw']}中）發生一個{table['genotype_zhtw']}{table['consequence_zhtw']}變異（{table['HGVSc']}）。",
                                            f"在此個案中，有一個{table['consequence_zhtw']}變異在{table['gene_name']}基因（{table['reference']}）{tmp_position}的位置（位於{table['exon_or_intron_rank_zhtw']}中）被檢測出來，使核苷酸序列發生{table['genotype_zhtw']}改變（{table['HGVSc']}）。"]
            
            text_zhtw['HGVSc'] =  [''] # keep the key for checking whether the HGVSc exist or not in comprehensive report generating step
        else:
            text_zhtw['gene_name'] = [''] 
            # no information of gene name, keep the key for checking whether the gene name exist or not in comprehensive report generating step
            # if there is no information of gene name, do not need to check whether the HGVSc exist or not
        
        text_zhtw['HGVSp'] = [self.hgvsp_parse.text_zhtw] # text from HGVSpParser
        text_zhtw['ClinVar_record'] = [f"此變異位點於ClinVar資料庫有報導過，且ClinVar資料庫報導為一{table['ClinVar_record_zhtw']}變異位點。", # NTUH
                                        f"此變異於ClinVar資料庫中之致病性紀錄{table['ClinVar_record_zhtw']}。",
                                        f"此變異的致病性在ClinVar資料庫中的紀錄{table['ClinVar_record_zhtw']}。",
                                        f"在ClinVar資料庫中，對此變異之致病性的紀錄{table['ClinVar_record_zhtw']}。"]
        text_zhtw['hotspot'] = [f"根據{table['hotspot_zhtw']}資料庫中記錄之致病性變異，此變異位於基因高度致病性之熱點區（hotspot region）中。",
                                f"此變異根據{table['hotspot_zhtw']}資料庫中的紀錄，有高機率位於基因高度致病性之熱點區（hotspot region）中。",
                                f"根據{table['hotspot_zhtw']}資料庫中的紀錄顯示，此變異位於基因高度致病性之熱點區（hotspot region）中。",
                                f"根據{table['hotspot_zhtw']}資料庫的記錄，這個變異存在於被視為基因高度致病性的熱點區（hotspot region）內。"]

        text_zhtw['gnomAD_freq'] = [f"在世界基因體計畫gnomAD資料庫對偶基因頻率為{table['gnomAD_freq']}，", # NTUH
                                    f"根據Genome Agrregation Database（gnomAD）之紀錄，此變異的「對偶基因頻率」（allele frequency）於東亞地區族群中為{table['gnomAD_freq']}；",
                                    f"此變異於東亞地區族群中的「對偶基因頻率」（allele frequency）根據Genome Agrregation Database（gnomAD）之紀錄為{table['gnomAD_freq']}；",
                                    f"在東亞地區族群中，此變異的「對偶基因頻率」（allele frequency）根據Genome Agrregation Database（gnomAD）中的紀錄為{table['gnomAD_freq']}；",
                                    f"根據Genome Aggregation Database（gnomAD）的紀錄，這個變異在東亞地區的族群中，其「對偶基因頻率」（allele frequency）為{table['gnomAD_freq']}"]

        text_zhtw['TaiwanBiobank_freq'] = [f"在臺灣人體生物資料庫對偶基因頻率為{table['TaiwanBiobank_freq']}。", # NTUH
                                        f"在臺灣人體生物資料庫（Taiwan BioBank）中，此變異的「對偶基因頻率」（allele frequency）於臺灣族群中為{table['TaiwanBiobank_freq']}。\n",
                                        f"而其在臺灣族群中的「對偶基因頻率」（allele frequency），根據臺灣人體生物資料庫（Taiwan BioBank）的紀錄為{table['TaiwanBiobank_freq']}。\n",
                                        f"而在臺灣族群中，其「對偶基因頻率」（allele frequency根據臺灣人體生物資料庫（Taiwan BioBank）之紀錄為{table['TaiwanBiobank_freq']}。\n",
                                        f"就台灣族群而言，根據台灣人體生物資料庫（Taiwan BioBank）的資料，「對偶基因頻率」（allele frequency）被記錄為{table['TaiwanBiobank_freq']}。\n"]

        if table['pathogenicity'] == 'recorded': # check if these is record from any of the pathogenicity prediction software       
            text_zhtw['pathogenicity'] = ["此外，此變異點之", # NTUH
                                          "透過預測軟體對此變異之致病性進行評估，結果顯示：",
                                          "透過預測軟體評估這個變異的致病性，所顯示的結果為：",
                                          "利用預測軟體對這個變異的致病性進行分析，結果顯示："]
            pred_ls = []
            interpretation_ls = []
            interpretation = {'SIFT': 'SIFT值越接近0',
                              'PolyPhen2': 'PolyPhen2值越接近1',
                              'CADD-phred': 'CADD-phred值越接近99',
                              'VEST4': 'VEST4值越接近1',
                              'PROVEAN': 'PROVEAN = D',
                              'DANN': 'DANN越接近1',
                              'spliceAI': 'spliceAI任一預測數值大於0.5'}
            for key in self.pathogenicity_SW:
                tmp = table['pathogenicity_prediction'][key]
                if tmp != '.':
                    interpretation_ls.append(interpretation[key])
                    if type(tmp) == dict:
                        pred_ls.append(f"{key}的" + '、'.join([f"{subtype} = {value}" for subtype, value in tmp.items()]))
                    else:
                        pred_ls.append(f"{key} = {tmp}")

            tmp_prediction = '，'.join(pred_ls)
            tmp_prediction += f"（{'；'.join(interpretation_ls)}，表示較高的致病性）。"

            text_zhtw['pathogenicity'] = [text+tmp_prediction for text in text_zhtw['pathogenicity']]
        else:
            text_zhtw['pathogenicity'] = [''] # no available prediction, keep the key for checking if any these is record from any of the pathogenicity prediction software in comprehensive report generating step

        if table['conservation'] == 'recorded': 
            sw_ls = []
            pred_ls = []
            for key in self.conservation_SW:
                if table['conservation_prediction'][key] != '.':
                    sw_ls.append(key)
                    pred_ls.append(table['conservation_prediction'][key])
            text_zhtw['conservation'] = [f"而{'、'.join(sw_ls)}預測之保守性分數（conservation score）為{'、'.join(pred_ls)}。",
                                            f"而此變異的保守性分數（conservation score）根據{'、'.join(sw_ls)}預測為{'、'.join(pred_ls)}。",
                                            f"最後，使用{'、'.join(sw_ls)}對此變異之保守性分數（conservation score）進行預測，結果為{'、'.join(pred_ls)}。"]
        else: 
            text_zhtw['conservation'] = ['']
        return text_zhtw

    def template_enus(self, table, delexicalized = False):
        text_enus = {}
        if table['gene_name'] != ".":
            if table['HGVSc'] == ".":
                text_enus['gene_name'] = [f"A {table['genotype']} {table['consequence']} variant is detected in the {table['gene_name']} gene, "]
            else:
                if len(table['CDS_position'].split(', ')) > 1:
                    if any(ann in table['HGVSc'] for ann in ['del', 'dup']):
                        tmp_position = 'from the ' + ' to the '.join([ordinal_suffix(pos) for pos in table['CDS_position'].split(', ')])
                    else:
                        tmp_position = 'between the ' + ' and the '.join([ordinal_suffix(pos) for pos in table['CDS_position'].split(', ')])
                else:
                    tmp_position = 'at the ' + ordinal_suffix(table['CDS_position'])

                if delexicalized:
                    self.reversed_map['CDS_POS'] = tmp_position
                    tmp_position = 'CDS_POS'
                    self.delexicalized_table['CDS_position'] = 'CDS_POS'
            
                text_enus['gene_name'] = [f"A {table['genotype']} {table['consequence']} variant ({table['HGVSc']}) is detected {tmp_position} nucleotide in {table['exon_or_intron_rank']} of the {table['gene_name']} gene ({table['reference']}). ",
                                            f"A {table['genotype']} {table['consequence']} variant ({table['HGVSc']}) has been identified {tmp_position} nucleotide in {table['exon_or_intron_rank']} of the {table['gene_name']} gene ({table['reference']}). ",
                                            f"In the {table['gene_name']} gene, a {table['genotype']} {table['consequence']} variant ({table['HGVSc']}) has been detected {tmp_position} nucleotide position in {table['exon_or_intron_rank']} ({table['reference']}). ",
                                            f"An alteration in the {table['gene_name']} gene involves a {table['genotype']} {table['consequence']} variant ({table['HGVSc']}) found {tmp_position} nucleotide in {table['exon_or_intron_rank']} ({table['reference']}). ",
                                            f"A genetic variation, {table['HGVSc']}, has been identified as a {table['genotype']} {table['consequence']} variant in the {table['gene_name']} gene {tmp_position} nucleotide position in {table['exon_or_intron_rank']} ({table['reference']}). ",
                                            f"The {table['gene_name']} gene exhibits a {table['genotype']} {table['consequence']} variant ({table['HGVSc']}) {tmp_position} nucleotide in {table['exon_or_intron_rank']} ({table['reference']}). "]
            text_enus['HGVSc'] =  ['']
        else:
            text_enus['gene_name'] = ['']
        

        hgvsp_text =  self.hgvsp_parse.text
        if delexicalized:
            if self.table['HGVSp'] != '.':
                hgvsp_text = hgvsp_text.split('(')[0] + '(HGVSP). '
            for attr, delexical_value in zip([ 'changed_amino_acid', 'original_amino_acid_init', 'original_amino_acid_end'], ['CHANGED_AA', 'ORIGINAL_AA_INIT', 'ORIGINAL_AA_END']):
                if self.table[attr][0] != '.':
                    replace_value = self.table[attr][0].replace('Ter/', '').replace('=/', '')
                    hgvsp_text = hgvsp_text.replace(replace_value, delexical_value, 1)
            # for attr, delexical_value in zip(['original_position_init', 'original_position_end', 'changed_position'], ['ORIGINAL_POS_INIT', 'ORIGINAL_POS_END', 'CHANGED_POS']):
            #     if all(self.table[attr] != con for con in ['.', '', '?']):
            #         replace_value = ordinal_suffix(self.table[attr])
            #         hgvsp_text = hgvsp_text.replace(replace_value, delexical_value, 1)
        if delexicalized:
            text_enus['HGVSp'] = ['HGVSP. ']
        else:
            text_enus['HGVSp'] = [hgvsp_text] # text from HGVSpParser

        text_enus['ClinVar_record'] = [f"This variant is recorded as '{table['ClinVar_record']}' in the ClinVar database. ",
                                         f"The ClinVar database records this variant as having '{table['ClinVar_record']}' status. ",
                                         f"In the ClinVar database, this variant is categorized as '{table['ClinVar_record']}.' ",
                                         f"According to the ClinVar database, this variant is labeled as '{table['ClinVar_record']}.' ",
                                         f"'{table['ClinVar_record']}' is the classification assigned to this variant in the ClinVar database. ",
                                         f"The ClinVar database classifies this variant as '{table['ClinVar_record']}.' ",
                                         f"This variant is annotated as '{table['ClinVar_record']}' in the ClinVar database. ",
                                         f"The ClinVar database designates this variant with the term '{table['ClinVar_record']}.' ",
                                         f"In ClinVar, this variant is documented with the status '{table['ClinVar_record']}.' ",
                                         f"The '{table['ClinVar_record']}' classification is attributed to this variant in the ClinVar database. ",
                                         f"According to the ClinVar database, this variant falls under the category of '{table['ClinVar_record']}.' "]
        text_enus['hotspot'] = [f"This specific variant is situated within a hotspot region known for its strong association with high pathogenicity, as documented in {table['hotspot']}. ",
                                  f"In {table['hotspot']}, this variant is found in a hotspot region recognized for its elevated pathogenicity. ",
                                  f"The {table['hotspot']} database identifies this variant as being positioned in a hotspot region known for its significant pathogenicity. ",
                                  f"Within {table['hotspot']}, this variant is situated in a hotspot region that is strongly linked to high pathogenicity. ",
                                  f"According to {table['hotspot']}, this variant is located in a hotspot region renowned for its pronounced pathogenicity. ",
                                  f"This variant is annotated in {table['hotspot']} as falling within a hotspot region with a high likelihood of pathogenicity. ",
                                  f"In {table['hotspot']}, this variant is documented as being part of a hotspot region linked to high pathogenicity. ",
                                  f"According to the data in {table['hotspot']}, this variant is positioned in a hotspot region known for its marked pathogenicity. ",
                                  f"The {table['hotspot']} database indicates that this variant is found in a hotspot region with a strong association with high pathogenicity. "]
        text_enus['gnomAD_freq'] = [f"The maximum allele frequency of this variant in all population is {table['gnomAD_freq']} based on the Genome Aggregation Database (gnomAD).",
                                      f"According to data from the Genome Aggregation Database (gnomAD), The maximum allele frequency of this variant in all population is {table['gnomAD_freq']}. ",
                                      f"The Genome Aggregation Database (gnomAD) reports a maximum allele frequency of {table['gnomAD_freq']} for this variant in all population. ",
                                      f"Based on gnomAD data, this maximum variant's allele frequency in all population is {table['gnomAD_freq']}, ",
                                      f"The Genome Aggregation Database (gnomAD) indicates a maximum allele frequency of {table['gnomAD_freq']} for this variant in all population. ",
                                      f"As per the Genome Aggregation Database (gnomAD), The maximum allele frequency of this variant in all population is {table['gnomAD_freq']}, ",
                                      f"The maximum allele frequency of this variant in all population is {table['gnomAD_freq']}, based on data from the Genome Aggregation Database (gnomAD). ",
                                      f"In all population, the maximum variant's allele frequency is {table['gnomAD_freq']}, as evidenced by data from the Genome Aggregation Database (gnomAD). ",
                                      f"The Genome Aggregation Database (gnomAD) shows a maximum allele frequency of {table['gnomAD_freq']} for this variant in all population. ",
                                      f"According to data from the Genome Aggregation Database (gnomAD), the maximum allele frequency of this variant is {table['gnomAD_freq']} in all population. ",
                                      f"This variant's maximum allele frequency in all population is {table['gnomAD_freq']}, as documented in the Genome Aggregation Database (gnomAD). "]
        text_enus['TaiwanBiobank_freq'] = [f"In the Taiwan BioBank, the allele frequency in the Taiwanese population is {table['TaiwanBiobank_freq']}.\n",
                                             f"Meanwhile, in the Taiwanese population recorded in the Taiwan BioBank, the allele frequency is {table['TaiwanBiobank_freq']}.\n",
                                             f"The Taiwanese population's allele frequency, as observed in the Taiwan BioBank, is {table['TaiwanBiobank_freq']}.\n",
                                             f"In the Taiwanese population, the allele frequency is {table['TaiwanBiobank_freq']}, as noted in the Taiwan BioBank.\n",
                                             f"On the other hand, the Taiwanese population's allele frequency, according to the Taiwan BioBank, is recorded at {table['TaiwanBiobank_freq']}.\n",
                                             f"In the Taiwanese population, the allele frequency is {table['TaiwanBiobank_freq']}, as documented by the Taiwan BioBank.\n",
                                             f"The Taiwanese population's allele frequency stands at {table['TaiwanBiobank_freq']}, as reported by the Taiwan BioBank.\n",
                                             f"The allele frequency in the Taiwanese population is {table['TaiwanBiobank_freq']}, according to the Taiwan BioBank.\n",
                                             f"In the Taiwanese population, recorded in the Taiwan BioBank, the allele frequency is {table['TaiwanBiobank_freq']}.\n",
                                             f"The allele frequency in the Taiwanese population, based on the Taiwan BioBank data, is {table['TaiwanBiobank_freq']}.\n",
                                             f"In the Taiwanese population recorded in the Taiwan BioBank, the allele frequency is {table['TaiwanBiobank_freq']}.\n"]
        
        if table['pathogenicity'] == 'recorded':
            text_enus['pathogenicity'] = [f"The pathogenicity of the variant is predicted by multiple pathogenicity prediction software: ",
                                        f"Several pathogenicity prediction tools were utilized to assess the variant's pathogenicit: ",
                                        f"The variant's pathogenicity was assessed using multiple prediction software: ",
                                        f"To evaluate the variant's pathogenicity, various prediction software were employed: ",
                                        f"The pathogenicity of the variant was examined using multiple prediction software: ",
                                        f"Various pathogenicity prediction tools were employed to assess the variant's pathogenicity: ",
                                        f"The variant's pathogenicity was evaluated using multiple prediction software: ",
                                        f"To determine the variant's pathogenicity, various prediction software were utilized: ",
                                        f"The pathogenicity of the variant was examined using multiple prediction software: ",
                                        f"Various pathogenicity prediction tools were employed to assess the variant's pathogenicity: ",
                                        f"The variant's pathogenicity was evaluated using multiple prediction software: "]
            pred_ls = []
            interpretation = {'SIFT': 'The closer the SIFT value is to 0',
                              'PolyPhen2': 'the closer the PolyPhen2 value is to 1',
                              'CADD-phred': 'the closer the CADD-phred value is to 99',
                              'VEST4': 'the closer the VEST4 value is to 1',
                              'PROVEAN': 'PROVEAN = D',
                              'DANN': 'the closer the DANN value is to 1',
                              'spliceAI': 'any of prediction from spliceAI higher than 0.5'}
            pathogenicity_SW = table['pathogenicity_prediction'].keys() if delexicalized else self.pathogenicity_SW
            for key in pathogenicity_SW:
                tmp = table['pathogenicity_prediction'][key]
                if tmp != '.':
                    if type(tmp) == dict:
                        #pred_ls.append(f"The {len(tmp)} predictions of {key} are " + ', '.join([f"{subtype} = {value}" for subtype, value in tmp.items()]))
                        pred_ls.append(f"The predictions of {key} are " + ', '.join([f"{subtype} = {value}" for subtype, value in tmp.items()]))
                    else:
                        pred_ls.append(f"{key} = {tmp}")

            tmp_prediction = ', '.join(pred_ls)
            if delexicalized:
                tmp_prediction += ". "
            else:
                tmp_prediction += f" ({'; '.join([interpretation[key] for key in pathogenicity_SW if table['pathogenicity_prediction'][key] != '.'])}, the higher the pathogenicity is implied). "
            text_enus['pathogenicity'] = [text+tmp_prediction for text in text_enus['pathogenicity']]
        else:
            text_enus['pathogenicity'] = ['']

        if table['conservation'] == 'recorded': 
            pred_ls = []
            conservation_SW = table['conservation_prediction'].keys() if delexicalized else self.conservation_SW
            for key in conservation_SW:
                if table['conservation_prediction'][key] != '.':
                    pred_ls.append(f"{key} = {table['conservation_prediction'][key]}")
            text_enus['conservation'] = [f"And the conservation score {', '.join(pred_ls)}.",
                                        f"while the conservation score by {', '.join(pred_ls)}.",
                                        f"And the conservation score by {', '.join(pred_ls)}.",
                                        f"And the conservation score predicted by {', '.join(pred_ls)}."]
        else:
            text_enus['conservation'] = ['']
        return text_enus
    
    def template_na(self):
        self.text_na = {}
        self.text_na_zhtw = {}
        self.text_na['gene_name'] = ["The variant might be detected in an upstream or downstream region of the sequence, and the software could not identify which gene it is located in. ",
                                    "The genetic variant may be detected either in an upstream or downstream region of the DNA sequence, and the software was unable to determine the specific gene in which it is located. ",
                                    "The identified variant might be present in either the upstream or downstream region of the DNA sequence, and the software could not ascertain its exact gene location. ",
                                    "The variant is potentially found in either the upstream or downstream region of the DNA sequence, and its specific gene location could not be determined by the software. ",
                                    "In the DNA sequence, the variant may be present in either the upstream or downstream region, and the software could not pinpoint the exact gene in which it is situated. ",
                                    "The detected variant might be located in either the upstream or downstream region of the DNA sequence, and the software was unable to specify the particular gene it affects. ",
                                    "The variant is possibly found in either the upstream or downstream region of the DNA sequence, and the software could not conclusively determine the gene it is associated with. ",
                                    "In the DNA sequence, the variant could be present in either the upstream or downstream region, and the software could not identify the precise gene location. ",
                                    "The identified variant may be located either upstream or downstream of the DNA sequence, and the software was unable to determine the specific gene affected. ",
                                    "The genetic variant is potentially present in either the upstream or downstream region of the DNA sequence, and the software could not definitively assign it to a particular gene. "]
        self.text_na_zhtw['gene_name'] = ["在此個案中，檢測到的變異可能位於序列的上游或下游區域，因此軟體無法辨識其所在之基因。",
                                          "在本次檢測中，所偵測到的變異可能位於序列的上游或下游區域，因此軟體無法確定其所屬基因。",
                                          "在這個個案中，因所檢測到的變異可能位於序列上游或下游區域，軟體無法分辨其所在基因。"]
        
        self.text_na['HGVSc'] = ["There is no sequence change compare to a reference sequence. ",
                                 "The sequence remains unchanged when compared to a reference sequence. ",
                                 "No alterations are observed in the sequence compared to a reference sequence. ", 
                                 "There are no sequence modifications relative to a reference sequence. ", 
                                 "The sequence is identical to the reference sequence without any changes. ", 
                                 "The sequence shows no differences when compared to a reference sequence. ",
                                 "A reference sequence and the given sequence are found to be identical. ",
                                 "There is an exact match between the sequence and the reference sequence. ",
                                 "The sequence exhibits complete similarity to the reference sequence. ",
                                 "No variations are identified in the sequence when compared to a reference sequence. ",
                                 "The sequence aligns perfectly with the reference sequence, showing no deviations. "]
        self.text_na_zhtw['HGVSc'] = ["相較於參考序列，此序列並無改變。",
                                      "與參考序列相比，此序列沒有發生變化。",
                                      "此序列與參考序列相較之下並無改變。"]
        
        self.text_na['HGVSp'] = ["There is no substitution of amino acid. ",
                                 "There is no substitution of amino acid in the sequence.",
                                 "The sequence does not involve any amino acid replacement.",
                                 "Amino acid remains unchanged in the sequence. ",
                                 "There are no modifications in the amino acid composition of the sequence. ",
                                 "The sequence shows no alterations in the amino acid content. ",
                                 "There is a lack of amino acid substitutions in the sequence. ",
                                 "No amino acid exchanges are observed in the sequence. ",
                                 "The sequence exhibits a constant amino acid configuration. ",
                                 "The amino acid composition remains constant in the sequence. ",
                                 "Amino acid substitution is not present in the sequence. "]
        self.text_na_zhtw['HGVSp'] = ["而在蛋白質層級，此序列未發生任何胺基酸的變化。",
                                      "此序列在蛋白質層級並未發生任何胺基酸更動。",
                                      "就蛋白質層級而言，此序列的胺基酸組成維持不變。"]
        
        self.text_na['DNA_codon'] = [""]
        self.text_na_zhtw['DNA_codon'] = [""]
        
        self.text_na['ClinVar_record'] = ["The pathogenicity of the variant had not been described in the ClinVar database. ",
                                          "The ClinVar database lacks information about the pathogenicity of the variant. ",
                                          "The pathogenicity of the variant has not been documented in the ClinVar database. ",
                                          "No description of the variant's pathogenicity can be found in the ClinVar database. ",
                                          "The ClinVar database does not contain any information regarding the pathogenicity of the variant. ",
                                          "The pathogenicity status of the variant is not available in the ClinVar database. ",
                                          "There is no record of the variant's pathogenicity in the ClinVar database. ",
                                          "The ClinVar database has no data on the pathogenicity of the variant. ",
                                          "The pathogenicity of the variant has not been specified in the ClinVar database. ",
                                          "The ClinVar database does not provide any information about the pathogenicity of the variant. ",
                                          "The pathogenicity status of the variant is missing from the ClinVar database. "]
        self.text_na_zhtw['ClinVar_record'] = ["此變異位點於 ClinVar資料庫未被報導過。", # NTUH
                                               "此變異之致病性在ClinVar資料庫尚未被描述。",
                                               "此變異之致病性在ClinVar資料庫尚未被描述。",
                                               "在ClinVar資料庫中尚未有關於此變異之致病性的描述。",
                                               "目前在ClinVar資料庫中，還沒有對此變異之致病性進行描述的紀錄。"]
        
        self.text_na['hotspot'] = ["This variant is not recorded in any database to be located in a hotspot region.",
                                   "This specific variant cannot be found in any database as it is not located within a hotspot region. ",
                                   "There is no record of this variant being present in any database within a hotspot region. ",
                                   "This variant is not documented in any database with regards to its location in a hotspot region. ",
                                   "No database entries indicate the presence of this variant within a hotspot region. ",
                                   "There are no records of this variant being situated in a hotspot region in any database. ",
                                   "The variant's location in a hotspot region is not recorded in any database. ",
                                   "This variant has not been reported to exist in any database within a hotspot region. ",
                                   "There is no data in any database suggesting the occurrence of this variant in a hotspot region. ",
                                   "No information in any database confirms the presence of this variant in a hotspot region. "]
        self.text_na_zhtw['hotspot'] = ["任何資料庫中皆未有此變異位於熱點區（hotspot region）的紀錄。",
                                        "此變異目前未在任何資料庫中被紀錄位於熱點區（hotspot region）之中。",
                                        "根據目前的資料庫資訊而言，無法斷定此變異位於熱點區（hotspot region）內。"]
        
        self.text_na['gnomAD_freq'] = ["The maximum allele frequency of this variant in the all populations wasn't reported in the Genome Aggregation Database (gnomAD). ",
                                       "The Genome Aggregation Database (gnomAD) did not report the allele frequency of this variant in all population. ",
                                       "In the Genome Aggregation Database (gnomAD), there is no recorded allele frequency for this variant in all population. ",
                                       "There is no information on the allele frequency of this variant in all population within the Genome Aggregation Database (gnomAD). ",
                                       "The Genome Aggregation Database (gnomAD) does not provide data on the allele frequency of this variant in all population. ",
                                       "The allele frequency in all populations for this variant is missing from the Genome Aggregation Database (gnomAD). ",
                                       "The Genome Aggregation Database (gnomAD) lacks information on the allele frequency of this variant in all population. ",
                                       "In the Genome Aggregation Database (gnomAD), no data regarding the allele frequency of this variant in all population is available. ",
                                       "This variant's allele frequency in all population is not reported within the Genome Aggregation Database (gnomAD). ",
                                       "The allele frequency in all populations for this variant is not documented in the Genome Aggregation Database (gnomAD). "]
        self.text_na_zhtw['gnomAD_freq'] = ["在世界基因體計畫gnomAD資料庫未報導過此變異位點，", # NTUH
                                            "Genome Aggregation Database（gnomAD）中無此變異在東亞地區族群中的「對偶基因頻率」（allele frequency）紀錄；",
                                            "此變異在東亞地區族群中的「對偶基因頻率」（allele frequency）尚未紀錄於Genome Aggregation Database（gnomAD）中；",
                                            "在Genome Aggregation Database（gnomAD）中，目前沒有關於此變異於東亞地區族群中的「對偶基因頻率」（allele frequency）的紀錄；"]
        
        self.text_na['TaiwanBiobank_freq'] = ["And the allele frequency of this variant in the Taiwanese population wasn't reported in the Taiwan BioBank, indicating that this variant is relatively rare in the population. ",
                                              "The Taiwan BioBank did not report the allele frequency of this variant in the Taiwanese population. This shows that this variant is relatively scarce within the population. ",
                                              "There is no information on the allele frequency of this variant in the Taiwanese population within the Taiwan BioBank. This indicates that this variant is not frequently observed among the population. ",
                                              "The Taiwan BioBank does not provide data on the allele frequency of this variant in the Taiwanese population, indicating that this variant is relatively rare in the population. ",
                                              "The allele frequency of this variant in the Taiwanese population was not recorded in the Taiwan BioBank, indicating that this variant is relatively rare in the population. ",
                                              "The Taiwan BioBank lacks information on the allele frequency of this variant in the Taiwanese population. This indicates that this variant is not frequently observed among the population. ",
                                              "In the Taiwan BioBank, there is no data regarding the allele frequency of this variant in the Taiwanese population. This shows that this variant is relatively scarce within the population. ",
                                              "The allele frequency of this variant in the Taiwanese population is not documented in the Taiwan BioBank, indicating that this variant is relatively rare in the population. ",
                                              "This variant's allele frequency in the Taiwanese population is not reported within the Taiwan BioBank. This indicates that this variant is not frequently observed among the population. ",
                                              "The Taiwan BioBank does not contain information about the allele frequency of this variant in the Taiwanese population. This shows that this variant is relatively scarce within the population. "]
        self.text_na_zhtw['TaiwanBiobank_freq'] = ["在臺灣人體生物資料庫未報導過此變異位點; 因此，此變異位點在人群中為相當罕見。", # NTUH
                                                   "在臺灣人體生物資料庫（Taiwan BioBank）中，此變異於臺灣族群中的「對偶基因頻率」（allele frequency）未被紀錄，顯示此變異位點在人群中相當罕見。\n",
                                                   "而此變異於臺灣族群中的「對偶基因頻率」（allele frequency），目前在臺灣人體生物資料庫（Taiwan BioBank）中未被紀錄，表示此變異位點在人群中相當罕見。\n",
                                                   "在臺灣人體生物資料庫（Taiwan BioBank）中尚未有關於此變異於臺灣族群中的「對偶基因頻率」（allele frequency）的紀錄，因此，此變異位點在人群中相當罕見。\n"]
        
        self.text_na['uniprot_gene'] = [""]
        self.text_na_zhtw['uniprot_gene'] = [""]

        self.text_na['pathogenicity'] = ["Multiple pathogenicity prediction software could be applied to check the pathogenicity of the variant, but there is no available data from these software for this transcript.",
                                        "Various pathogenicity prediction software can be utilized to assess the pathogenicity of the variant, but there are no recorded results from these software for this transcript. ",
                                        "The pathogenicity of the variant could be determined using multiple prediction algorithms, but there are no available records from these software for this transcript. ",
                                        "There are several pathogenicity prediction tools that could be employed to evaluate the variant's pathogenicity, yet there are no documented results from these software for this transcript. ",
                                        "The pathogenicity of the variant can be assessed through the application of different prediction software, but there is no data on the results from these software for this transcript. ",
                                        "Multiple algorithms for pathogenicity prediction can be used to examine the variant, but no records exist from these software for this transcript. ",
                                        "The variant's pathogenicity can be checked using various prediction tools, but there is no available information for the predictions from these software for this transcript. ",
                                        "There are several software options to predict the pathogenicity of the variant, but there are no recorded results from these software for this transcript. ",
                                        "The pathogenicity of the variant may be analyzed using different prediction algorithms, but there are no records of the outcomes from these software for this transcript. ",
                                        "Multiple pathogenicity prediction software could be applied to assess the variant, but there is no data available for the results from these software for this transcript. ",
                                        "There are various tools for pathogenicity prediction that can be utilized to evaluate the variant, but there are no recorded predictions from these software for this transcript. "]
        self.text_na_zhtw['pathogenicity'] = ["雖然有許多軟體可用於預測此變異之致病性，但在此分析中未得到各個預測軟體對此轉錄本的預測結果。",
                                              "此變異之致病性可透過各種軟體進行預測，不過在這次的分析中針對此轉錄本並未得到任何軟體的預測結果。",
                                              "此變異之致病性可使用許多軟體進行預測，但在這次的分析結果中並未涵蓋此轉錄本的預測結果。"]
        
        self.text_na['conservation'] = ['']
        self.text_na_zhtw['conservation'] = ['']

        self.text_na['OMIM_disease'] = ["The variant wasn't reported in the Online Mendelian Inheritance in Man (OMIM). "]
        self.text_na_zhtw['OMIM_disease'] = [f"此變異位點於Online Mendelian Inheritance in Man（OMIM）資料庫未報導過。"]

        self.text_na['CGD_condition'] = ["The variant wasn't reported in the Candida Genome Database (CGD). "]
        self.text_na_zhtw['CGD_condition'] = [f"此變異位點於Candida Genome Database（CGD）資料庫未報導過。"]

    def generate_report(self, template_idx = None, attribute_out = None):
        self.report = {}
        self.report['En'] = ''
        self.report['Zh'] = ''
        if self.delexicalized:
            self.report['delexicalized_En'] = ''
        
        attribute_out = attribute_out if attribute_out else self.text_zhtw.keys()

        for key in attribute_out:
            if key not in self.table.keys():
                 self.table[key] = '.'
        
        for key in attribute_out:
            if self.table[key] == '.':
                n = template_idx if template_idx != None else random.sample(list(range(len(self.text_na_zhtw[key]))),1)[0]
                self.report['Zh'] += self.text_na_zhtw[key][n]
                n = template_idx if template_idx != None else random.sample(list(range(len(self.text_na[key]))),1)[0]
                self.report['En'] += self.text_na[key][n]
                if self.delexicalized:
                    self.report['delexicalized_En'] += self.text_na[key][n]
            else:
                n = template_idx if template_idx != None else random.sample(list(range(len(self.text_zhtw[key]))),1)[0]
                self.report['Zh'] += self.text_zhtw[key][n]
                n = template_idx if template_idx != None else random.sample(list(range(len(self.text_enus[key]))),1)[0]
                self.report['En'] += self.text_enus[key][n]
                if self.delexicalized:
                    self.report['delexicalized_En'] += self.text_enus_delexicalized[key][n]

        if self.lang in self.report.keys():
            return self.report[self.lang].replace("  ", " ").strip()
        else:
            return "The variant report is currently only available in Chinese ('Zh') and English ('En')."
    
    def extract_required_info(self, attribute_out = None):
        table = self.table
        attributes = self.shared_attributes
        attribute_out = attribute_out if attribute_out else attributes
        required_info = []
        for attr in attribute_out:
            if all(table[attr] != con for con in ['NA', '.', '']):
                if attr in ['original_amino_acid_init', 'original_amino_acid_end', 'changed_amino_acid'] and type(table[attr]) == tuple:
                    tmp_record = [word[0] for word in table[attr]]
                    required_info += tmp_record
                elif type(table[attr]) == dict:
                    for key, value in table[attr].items():
                        if type(value) == dict:
                            tmp_record = np.array([[k,v] for k, v in value.items() if all(v != con for con in ['NA', '.', ''])])
                            tmp_record = tmp_record.flatten().tolist()
                            required_info.append(key)
                            required_info += tmp_record
                        else:
                            if all(value != con for con in ['NA', '.', '']):
                                required_info.append(key)
                                required_info.append(value)
                elif type(table[attr]) == list:
                    tmp_record = np.array([[w.rstrip(';,') for w in word.split()] for word in table[attr]])
                    tmp_record = tmp_record.flatten().tolist()
                    required_info += tmp_record
                else:
                    tmp_record = [word.rstrip(';,') for word in table[attr].split()]
                    required_info += tmp_record
        return required_info

    def generate_linear_raw(self, attribute_out = None):
        attributes = ['Otherinfo_FORMAT-GT', 'VEP_VEP-refseq-Consequence', 'VEP_VEP-refseq-HGVSc', 'VEP_VEP-refseq-Gene-Name', 
                      'VEP_VEP-ensembl-Transcript-ID', 'ANNOVAR_ANNOVAR-ensembl-Transcript-ID',
                      'VEP_VEP-refseq-Exon-or-Intron-Rank', 'VEP_VEP-refseq-HGVSp', 'ClinVar_CLNSIG', 'pathogenicHotspot-ailabs_pathogenicHotspot',
                      'gnomAD-Genomes_AF-popmax', 'TaiwanBiobank-official_Illumina1000-AF', 
                      'Pathogenicity Scores_Ensembl-transcriptid', 'Pathogenicity Scores_SIFT-score', 'Pathogenicity Scores_Polyphen2-HVAR-score',
                      'Pathogenicity Scores_VEST4-score', 'Pathogenicity Scores_PROVEAN-pred', 'CADD_PHRED', 'DANN_DANN-score', 
                      'SpliceAI-SNV_DS-AG', 'SpliceAI-SNV_DS-AL', 'SpliceAI-SNV_DS-DG', 'SpliceAI-SNV_DS-DL', 
                      'Conservation Scores_phyloP100way-vertebrate-rankscore']
        attribute_out = attribute_out if attribute_out else attributes
        linear_table = "<table> "
        for attr in attribute_out:
            if self.sample[attr] != ".":
                linear_table += f"<cell> {self.sample[attr]} <header> {attr} </header> </cell> "
            else:
                linear_table += f"<cell> NA <header> {attr} </header> </cell> "
        linear_table += "</table>"
        return linear_table
        
    def generate_linear(self, version = 'v2', attribute_out = None, delexicalized = False):
        # linear_table = "<table> "
        attributes = self.shared_attributes
        attribute_out = attribute_out if attribute_out else attributes
        table = self.delexicalized_table if delexicalized else self.table
        if version == 'v1':
            linear_table = "<table> "
            for attr in attribute_out:
                if all(table[attr] != con for con in [".", '']):
                    if attr in ['original_amino_acid_init', 'original_amino_acid_end', 'changed_amino_acid'] and len(table[attr]) == 2:
                        linear_table += f"<cell> {table[attr][0]} <header> {attr} </header> </cell> " if table[attr][0] != '.' else f"<cell> NA <header> {attr} </header> </cell> "
                    elif attr in ['pathogenicity_prediction', 'conservation_prediction']:
                        for key in table[attr].keys():
                            if type(table[attr][key]) == dict:
                                tmp = ", ".join([f"{k}={v}" for k, v in table[attr][key].items()])
                                linear_table += f"<cell> {key} = ({tmp}) <header> {attr} </header> </cell> "
                            else:
                                linear_table += f"<cell> {key} = NA <header> {attr} </header> </cell> " if table[attr][key] == '.' else f"<cell> {key} = {table[attr][key]} <header> {attr} </header> </cell> "
                    else:
                        linear_table += f"<cell> {table[attr]} <header> {attr} </header> </cell> "
                else:
                    linear_table += f"<cell> NA <header> {attr} </header> </cell> "
            linear_table += "</table>"
            return linear_table
        
        elif version == 'v2':
            linear_table = []
            for attr in attribute_out:
                if all(table[attr] != con for con in [".", '']):
                    if attr in ['original_amino_acid_init', 'original_amino_acid_end', 'changed_amino_acid'] and len(table[attr]) == 2:
                        linear_table.append(f"{attr}[{table[attr][0]}]" if table[attr][0] != '.' else f"{attr}[NA]")
                    elif attr in ['pathogenicity_prediction', 'conservation_prediction']:
                        for key in table[attr].keys():
                            if type(table[attr][key]) == dict:
                                tmp = ", ".join([f"{k}={v}" for k, v in table[attr][key].items()])
                                linear_table.append(f"{attr}[{key} = ({tmp})]")
                            else:
                                linear_table.append(f"{attr}[{key} = NA]" if table[attr][key] == '.' else f"{attr}[{key} = {table[attr][key]}]")
                    else:
                        linear_table.append(f"{attr}[{table[attr]}]")
                else:
                    linear_table.append(f"{attr}[NA]")

            return ', '.join(linear_table)
    
    def generate_linear_sentence(self, attribute_out = None, delexicalized = False, generate_word_class = False):
        table = self.delexicalized_table.copy() if delexicalized else self.table.copy()

        attributes = self.shared_attributes
        attribute_out = attribute_out if attribute_out else attributes

        short_sentence = ''
        for attr in attribute_out:
            if table[attr] != "." and table[attr] != "":
                if attr in ['original_amino_acid_init', 'original_amino_acid_end', 'changed_amino_acid'] and len(table[attr]) == 2:
                    short_sentence += f"The {attr} is {table[attr][0]}. " if table[attr][0] != '.' else f"The {attr} is NA. "
                elif type(table[attr]) == list:
                    short_sentence += f"The {attr} is {', '.join(table[attr])}. "
                elif type(table[attr]) == dict:
                    tmp_ls = []
                    for key in table[attr].keys():
                        if type(table[attr][key]) == dict:
                            tmp_ls += [f"The {attr} from {key}'s {subtype} is {value}. "  for subtype, value in table[attr][key].items() if value != '.']
                        else:
                            tmp_ls += [f"The {attr} from {key} is {table[attr][key]}. " if table[attr][key] != '.'  else f"The {attr} from {key} is NA. " ]
                    short_sentence += ''.join(tmp_ls)
                else:
                    short_sentence += f"The {attr} is {table[attr]}. "

            else:
                short_sentence += f"The {attr} is NA. "

        if generate_word_class:
            required_info = self.extract_required_info()
            short_sentence_split = short_sentence.split()
            word_class = ['0']*len(short_sentence_split)
            for i in range(len(short_sentence_split)):
                if short_sentence_split[i].rstrip(';,].') in required_info:
                    word_class[i] = '1'
            return short_sentence.strip(), ",".join(word_class)

        return short_sentence.strip()

    def generate_table_input(self, attribute_out = None, linearized = False, delexicalized = False, generate_word_class = False):
        table = self.delexicalized_table.copy() if delexicalized else self.table.copy()
        # NA data preprocessing
        for key, value in table.items():
            if value == '.' or value == '':
                table[key] = 'NA'
        # check: premature termination
        n_ter = False
        for key in ['original_amino_acid_init', 'original_amino_acid_end', 'changed_amino_acid']:
            if type(table[key]) == tuple:
                table[key] = table[key][0] if table[key][0] != '.' else 'NA'
                if re.search(r'^Ter/', table[key]):
                    n_ter = True
                    table[key] = table[key].split('Ter/')[-1]
        table['ter'] = 'YES' if n_ter else 'NO'
        
        # output table
        table_out = {}
        table_out['GeneName'] = table['gene_name']
        table_out['genotype'] = table['genotype']
        table_out['Consequence'] = table['consequence']
        table_out['HGVSc'] = f"annotation = {table['HGVSc']}, reference = {table['reference']}, position = {table['CDS_position']}, type_and_rank = {table['exon_or_intron_rank']}"
        table_out['HGVSp'] = f"annotation = {table['HGVSp']}, functional_impact = {table['change_type']}, original_position_init = {table['original_position_init']}, original_amino_acid_init = {table['original_amino_acid_init']}, original_position_end = {table['original_position_end']}, original_amino_acid_end = {table['original_amino_acid_end']}, changed_position = {table['changed_position']}, changed_amino_acid = {table['changed_amino_acid']}, termination = {table['ter']}"
        table_out['ClinVar'] = f"record = {table['ClinVar_record']}"
        table_out['Hotspot'] = f"database = {table['hotspot']}"
        table_out['AlleleFrequency'] = [f"from = {key.split('_')[0]}, score = {table[key]}" for key in ['gnomAD_freq', 'TaiwanBiobank_freq']]
        table_out['PathogenicityPrediction'] = []
        if table['pathogenicity'] != 'NA':
            for key in table['pathogenicity_prediction'].keys():
                tmp = table['pathogenicity_prediction'][key]
                if type(tmp) == dict:
                    for subtype, value in tmp.items():
                        if value != '.':
                            table_out['PathogenicityPrediction'] += [f"from = {key}, type = {subtype}, prediction = {value}"]
                else:
                    if tmp != '.':
                        table_out['PathogenicityPrediction'] += [f"from = {key}, type = None, prediction = {tmp}"]
                    #table_out['PathogenicityPrediction'] += [f"from = {key}, type = None, prediction = {tmp}" if tmp != '.' else f"from = {key}, type = None, prediction = NA"]
        else:
            table_out['PathogenicityPrediction'] = 'NA'
        table_out['ConservationPredcition'] = [f"from = {key}, prediction = {table['conservation_prediction'][key]}" if table['conservation_prediction'][key] != '.' else f"from = {key}, prediction = NA" for key in table['conservation_prediction'].keys()]

        # linearization
        if linearized:
            linear = ''
            table_attribute_out = attribute_out if attribute_out else table_out.keys()
            for key in table_attribute_out:
                if type(table_out[key]) == str:
                    linear += f"<{key}> {table_out[key]}; "  
                else:
                    tmp = ', '.join([f'[{text}]' for text in table_out[key]])
                    linear += f"<{key}> {tmp}; "
            # generate label for classifier
            if generate_word_class:
                required_info = self.extract_required_info()
                linear_split = linear.split()
                word_class = ['0']*len(linear_split)
                for i in range(len(linear_split)):
                    if linear_split[i].rstrip(';,]') in required_info:
                        word_class[i] = '1'
                return linear.strip(), ','.join(word_class)
            return linear.strip()
        return table_out



class GermlineVarSum_annotator_2_2(GermlineVarSum):
    def __init__(self, sample, lang = 'Zh'):
        self.sample_keys = ['VEP_Symbol', 'VEP_HGVSc', 'Otherinfo_GT', 'VEP_Consequence', 'VEP_HGVSp',
                            'VEP_Exon', 'VEP_Intron', 'ClinVar_CLNSIG', 'VEP_ManeSelect', # NM...
                            'gnomADGenomes_AFpopmax', 'TaiwanBiobank_Illumina1000AF',
                            'VEP_Feature', 'PathogenicityScores_EnsemblTranscriptid', 
                            'PathogenicityScores_SiftPred', 'CADD_PHRED', 'DANN_DannScore',
                            'SpliceAI_DSAG', 'SpliceAI_DSAL', 'SpliceAI_DSDG', 'SpliceAI_DSDL',
                            'VEP_Codons', # DNA codons
                            'PathogenicDB_Variant',  # Hotspot: DVD, or other database
                            'UniProt_genes', 'UniProt_diseaseNames', 'CGD_condition',  #OMIM, CGD
                            'ACMG_Classes' # variant classification
                            ]
        super().__init__(sample, lang= lang, sample_keys = self.sample_keys)
    
    def table_cleaning(self, sample, create = False):
        table = {}
        # gene name
        if sample['VEP_Symbol'] != ".":
            table['gene_name'] = sample['VEP_Symbol']
        else: table['gene_name'] = '.'
        
        # Genotype
        # preprocessing data
            ## 1/1     : homozygous
            ## 1/0, 0/1: heterozygous
        if sample['Otherinfo_GT'] != ".":
            if sample['Otherinfo_GT'].split("/")[0] == sample['Otherinfo_GT'].split("/")[1]:
                table['genotype'] = 'homozygous'
                table['genotype_zhtw'] = '同型合子（homozygous）'
            else:
                table['genotype']  = 'heterozygous'
                table['genotype_zhtw'] = '異型合子（heterozygous）'
        else:
            table['genotype']  = ''
            table['genotype_zhtw'] = ''
        
        # HGVSc, exon/intron position
        if sample['VEP_HGVSc'] != ".":
            table['reference'] = sample['VEP_ManeSelect']
            _, table['HGVSc'] = sample['VEP_HGVSc'].split(':') # e.g. ENST00000237596.7:c.681C>A
            table['CDS_position'] = find_CDS_pos(table['HGVSc'].split('.')[-1]).strip() # c.107A>G -> 107
            match = re.search(r'^[*-]', table['CDS_position']) # check if the position is in 3'- or 5'- UTR (starting with * or -)
            if match:
                if match.group(0) == '*':
                    table['exon_intron'] = "3'-UTR"
                    table['exon_intron_zhtw'] = '三端非轉譯區'
                else:
                    table['exon_intron'] = "5'-UTR"
                    table['exon_intron_zhtw'] = '五端非轉譯區'
            elif re.search(r'[+-]', table['CDS_position']): # check if the position is in intron (includes + or -)
                table['exon_intron'] = 'intron'
                table['exon_intron_zhtw'] = '內含子'
            else: # else the position is in exon
                table['exon_intron'] = 'exon'
                table['exon_intron_zhtw'] = '外顯子'
            
            table['HGVSc_full'] = f"c.[{table['HGVSc'].split('.')[-1]}];[{table['HGVSc'].split('.')[-1]}]" if table['genotype'] == 'homozygous' else f"c.[{table['HGVSc'].split('.')[-1]}];[{table['CDS_position']}=]"
            table['CDS_position'] = ', '.join(table['CDS_position'].split('_'))

        else: # if there is no VEP_HGVSc information -> usually in intron
            table['reference'], table['HGVSc'] = ['.', '.']
            table['CDS_position'] = '.'
            table['exon_intron'] = 'intron'
            table['exon_intron_zhtw'] = '內含子'
        
        # exon/intron rank
        rank_col = 'VEP_Exon' if table['exon_intron'] == 'exon' else 'VEP_Intron'
        if sample[rank_col] != '.':
            exon_intron_rank = sample[rank_col].split('/')[0] # e.g. 3/3 (indicate there are 3 exon or intron region, the variant is in the 3rd exon or intron)
            if table['exon_intron'] in ['exon', 'intron']:
                table['exon_or_intron_rank'] = ' '.join([table['exon_intron'], exon_intron_rank])
                table['exon_or_intron_rank_zhtw'] = '第{:s}{:s}'.format(exon_intron_rank, table['exon_intron_zhtw'])
            else: # the variant is in 3'- or 5'- UTR -> no need intron/exon rank
                table['exon_or_intron_rank'] = table['exon_intron']
                table['exon_or_intron_rank_zhtw'] = table['exon_intron_zhtw']
        else:
            table['exon_or_intron_rank'] = table['exon_intron']
            table['exon_or_intron_rank_zhtw'] = table['exon_intron']

        # HGVSp
        if sample['VEP_HGVSp'] != '.':
            table['HGVSp'] = sample['VEP_HGVSp'].split(':')[1] # e.g. ENSP00000237596.2:p.Tyr227Ter
        else:
            table['HGVSp'] = '.'
        # HGVSp parsing
        self.hgvsp_parse = HGVSpParser(table['HGVSp'])
        [table['original_position_init'], table['original_amino_acid_init'], 
            table['original_position_end'], table['original_amino_acid_end'], 
            table['changed_position'], table['changed_amino_acid']] = self.hgvsp_parse.aa_pos_dict.values() # e.g. p.Glu36Gly
        table['change_type'] = self.hgvsp_parse.type
        table['HGVSp'] = self.hgvsp_parse.HGVSp

        # DNA codon
        if sample['VEP_Codons'] != '.':
            table['DNA_codon'] = [codon.upper() for codon in sample['VEP_Codons'].split('/')]
        else:
            table['DNA_codon'] = '.'

        # Consequence
        if sample['VEP_Consequence'] != '.':
            tmp_cons_zhtw, tmp_cons_enus = vep_consequence_translate(sample['VEP_Consequence']) # e.g. missense_variant,intron_variant

            table['consequence_zhtw'] = '、'.join(tmp_cons_zhtw) # chinese: concatenate the consequences with "、" (if more than one)
            table['consequence'] = ', '.join(tmp_cons_enus) # english: concatenate the consequences with "," (if more than one)
        else:
            table['consequence_zhtw'] = ''
            table['consequence'] = ''
        
        # Hotspot pathogenicity record
        if sample['PathogenicDB_Variant'] != ".":
            DB_ls = list(set([DB.strip() for DB in sample['PathogenicDB_Variant'].split(',')])) # e.g. DeafnessVD,ClinVar
            if len(DB_ls) > 2: # hotspot record from more than 2 database
                table['hotspot'] = ', '.join(DB_ls[:-1]) + ', and ' + DB_ls[-1]
                table['hotspot_zhtw'] = '、'.join(DB_ls[:-1]) + '和' + DB_ls[-1]
            else:
                table['hotspot'] = ' and '.join(DB_ls)
                table['hotspot_zhtw'] = '和'.join(DB_ls)
        else:
            table['hotspot'] = '.'
            table['hotspot_zhtw'] ='.'
        
        # pathogenicity record from ClinVar
        if sample['ClinVar_CLNSIG'] != ".":
            table['ClinVar_record'] = " ".join(sample['ClinVar_CLNSIG'].split('_')) # e.g. Likely_benign -> Likely benign
            try:
                table['ClinVar_record_zhtw'] = clinvar_translate(table['ClinVar_record'].strip()) # translate to chinese
            except KeyError:
                table['ClinVar_record_zhtw'] = table['ClinVar_record'] # the term is not in dictionary -> report in origin term (in English)
        else:
            table['ClinVar_record'] = '.'
            table['ClinVar_record_zhtw'] = '.'
        
        # ACMG pathogenicity record
        if sample['ACMG_Classes'] != '.':
            table['ACMG_Classes'] = " ".join(sample['ACMG_Classes'].split('-'))
            try:
                table['ACMG_Classes_zhtw'] = clinvar_translate(table['ACMG_Classes'].strip()) # translate to chinese
            except KeyError:
                table['ACMG_Classes_zhtw'] = table['ACMG_Classes'] # the term is not in dictionary -> report in origin term (in English)

        # Transcript ID
        table['transcriptid_MANE'] = sample['VEP_Feature']
        # list of Transcripts from the result of Pathogenicity prediction -> for reporting the pathogenicity prediction of MANE transcript ID
        if sample['PathogenicityScores_EnsemblTranscriptid'] != ".":
            table['Ensembl_transcriptid'] = [transcript.strip() for transcript in sample['PathogenicityScores_EnsemblTranscriptid'].split('|')]
                # e.g. ENST00000237596|ENST00000508588|ENST00000502363
            if table['transcriptid_MANE'] in table['Ensembl_transcriptid']: # check if MANE transcript ID is in the list 
                table['transcriptid_index'] = table['Ensembl_transcriptid'].index(table['transcriptid_MANE']) # keep the index of MANE in the list
            else: table['transcriptid_index'] = -1
        else:
            table['Ensembl_transcriptid'] = '.'
            table['transcriptid_index'] = -1

        # Pathogenicity prediction: 
        default_value = '.'
        table['pathogenicity_prediction'] = dict.fromkeys(self.pathogenicity_SW, default_value)
        if table['transcriptid_index'] != -1: # MANE transcript ID is in the list of Transcripts from the result of pathogenicity prediction -> report pathogenicity prediction
            ## SIFT score
            if sample['PathogenicityScores_SiftPred'] != ".":
                table['SIFT_all'] = str(sample['PathogenicityScores_SiftPred']).split('|') # e.g. "D|D"
                table['pathogenicity_prediction']['SIFT'] = table['SIFT_all'][table['transcriptid_index']] # get prediction of MANE
        ## CADD-phred score
        if sample['CADD_PHRED'] != ".":
            table['pathogenicity_prediction']['CADD-phred'] = str(sample['CADD_PHRED']) # e.g. 16.91
        ## DANN
        if sample['DANN_DannScore'] != ".":
            try:
                table['pathogenicity_prediction']['DANN']= "{:.3f}".format(round(float(sample['DANN_DannScore']),3)) # e.g. 0.9577714132251449
            except ValueError:
                table['pathogenicity_prediction']['DANN']= "."
        ## SpliceAI
        if sample['SpliceAI_DSAG'] != ".":
            table['pathogenicity_prediction']['spliceAI'] = {}
            table['pathogenicity_prediction']['spliceAI']['AG'] = "{:.3f}".format(round(float(sample['SpliceAI_DSAG']), 3)) # e.g. 0.0
            table['pathogenicity_prediction']['spliceAI']['AL'] = "{:.3f}".format(round(float(sample['SpliceAI_DSAL']), 3))
            table['pathogenicity_prediction']['spliceAI']['DG'] = "{:.3f}".format(round(float(sample['SpliceAI_DSDG']), 3))
            table['pathogenicity_prediction']['spliceAI']['DL'] = "{:.3f}".format(round(float(sample['SpliceAI_DSDL']), 3))

        if any([table['pathogenicity_prediction'][key] != '.' for key in self.pathogenicity_SW]): # if these is any prediction of MANE -> pathogenicity = "recorded"
            table['pathogenicity'] = 'recorded'
        else: 
            table['pathogenicity'] = '.'
            table['pathogenicity_prediction'] = '.'

        # Allele Frequency: gnomAD
        if sample['gnomADGenomes_AFpopmax'] != ".":
            try:
                table['gnomAD_freq'] = "{:.6f}".format(round(float(sample['gnomADGenomes_AFpopmax']),6)) # e.g. 0.00301205
            except ValueError:
                table['gnomAD_freq'] = "."
        else:
            table['gnomAD_freq'] = "."

        # Allele Frequency: TaiwanBiobank
        if sample['TaiwanBiobank_Illumina1000AF'] != ".":
            try:
                table['TaiwanBiobank_freq'] = "{:.6f}".format(round(float(sample['TaiwanBiobank_Illumina1000AF']),6))
            except ValueError:
                table['TaiwanBiobank_freq'] = '.'
        else:
            table['TaiwanBiobank_freq'] = '.'
        
        table['conservation'] = '.'
        
        # uniprot protein
        if sample['UniProt_genes'] != ".":
            table['uniprot_gene'] = sample['UniProt_genes']
        else:
            table['uniprot_gene'] = "."
            
        # uniprot disease
        if sample['UniProt_diseaseNames'] != ".":
            table['OMIM_disease'] = sample['UniProt_diseaseNames']
        else:
            table['OMIM_disease'] = '.'
        
        # CGD condition
        if sample['CGD_condition'] != ".":
            table['CGD_condition'] = sample['CGD_condition']
        else:
            table['CGD_condition'] = '.'
        
        return table

    def template_zhtw(self, table):
        text_zhtw = super().template_zhtw(table) 
        text_zhtw['DNA_codon'] = [f"（DNA序列{table['DNA_codon'][0]}轉變為{table['DNA_codon'][-1]}）。"]
        text_zhtw['uniprot_gene'] = [f"UniProt蛋白質資料庫顯示，此基因轉譯之蛋白質為{table['uniprot_gene']}。"]
        text_zhtw['OMIM_disease'] = [f"此變異位點於Online Mendelian Inheritance in Man（OMIM）資料庫有報導過，與{table['OMIM_disease']}具有相關性。"]
        text_zhtw['CGD_condition'] = [f"此變異位點於Candida Genome Database（CGD）資料庫有報導過，與{table['CGD_condition']}具有相關性。"]
        return text_zhtw
    
    def template_enus(self, table, delexicalized=False):
        text_enus = super().template_enus(table, delexicalized)
        text_enus['DNA_codon'] = [f"(DNA sequence from {table['DNA_codon'][0]} turn into {table['DNA_codon'][-1]})."]
        text_enus['uniprot_gene'] = [f"The UniProt protein database indicates that the protein translated from this gene is {table['uniprot_gene']}. "]
        text_enus['OMIM_disease'] = [f"The variant was reported in Online Mendelian Inheritance in Man (OMIM) which is associated with {table['OMIM_disease']}. "]
        text_enus['CGD_condition'] = [f"The variant was reported in Candida Genome Database (CGD) that is related to {table['CGD_condition']}."]
        return text_enus
    
    def generate_report(self, template_idx=None, attribute_out=None):
        attribute_out = ['gene_name', 'HGVSp', 'DNA_codon', 
                         'gnomAD_freq', 'TaiwanBiobank_freq', 'uniprot_gene',
                         'pathogenicity', 'hotspot', 'ClinVar_record', 
                         'OMIM_disease', 'CGD_condition']
        return super().generate_report(template_idx, attribute_out = attribute_out)
