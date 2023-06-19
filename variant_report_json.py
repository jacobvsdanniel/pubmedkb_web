# json version (vtable)
import random
from HGVSp_parser import HGVSp_parser
class clinical_report:
    def __init__(self, sample):
        self.table = {}
        self.basic_info(sample)
        self.Pathogenicity_prediction(sample)
        self.allele_frequency(sample)

        self.hotspot_region(sample)
        self.template_1(self.table)
        self.template_2(self.table)
        self.template_na()
    
    def find_CDS_pos(self, split_var):
        '''
        find the position of the nucleotide(s) that affected by the variant
        '''
        pos=[]
        start = 0
        for j in split_var:
            if j.isdigit():
                break
            else:
                start += 1
        
        for i in split_var[start:]:
            if i.isdigit():
                pos.append(i)
            elif i in ['+', '-']:
                pos.append(i)
            else:
                break
        return ''.join(pos)

    def ordinal_suffix(self,num):
        tmp_num = num
        if "+" in num:
            tmp_num = num.split('+')[-1]
        if "-" in num:
            tmp_num = num.split('-')[-1]
        j = int(tmp_num) % 10
        k = int(tmp_num) % 100
        if j == 1 and k != 11:
            return num + "st"
        elif j == 2 and k != 12:
            return num + "nd"
        elif j == 3 and k != 13:
            return num + "rd"
        else:
            return num + "th"
    
    def basic_info(self, sample):
        # gene name
        if 'VEP_VEP-refseq-Gene-Name' in sample.keys():
            self.table['gene_name'] = sample['VEP_VEP-refseq-Gene-Name']
        else:
            self.table['gene_name'] = '.'
        
        # HGVSc, GT
        if 'VEP_VEP-refseq-HGVSc' in sample.keys():
            self.table['gene_ID'], self.table['HGVSc'] = sample['VEP_VEP-refseq-HGVSc'].split(':')
            self.table['CDS_position'] = self.find_CDS_pos(self.table['HGVSc'].split('.')[-1]).strip()
        else:
            self.table['gene_ID'], self.table['HGVSc'] = ['.', '.']
            self.table['CDS_position'] = '.'
        if 'Otherinfo_FORMAT-GT' in sample.keys():
            if sample['Otherinfo_FORMAT-GT'].split("/")[0] == sample['Otherinfo_FORMAT-GT'].split("/")[1]:
                self.table['GT'] = 'homozygous'
            else:
                self.table['GT']  = 'heterozygous'
        else:
            self.table['GT']  = ''
        
        # Consequence
        if 'VEP_VEP-refseq-Consequence' in sample.keys():
            tmp_consequence = [' '.join(cons.split('_')[:-1]) if cons.split('_')[-1] == 'variant' else ' '.join(cons.split('_')) for cons in sample['VEP_VEP-refseq-Consequence'][0].split(',')]
            self.table['consequence'] = ', '.join(tmp_consequence)
        else:
            self.table['consequence'] = ''

        if 'VEP_VEP-refseq-HGVSp'in sample.keys():
            self.table['exon_intron'] = 'exon'
            self.table['HGVSp'] = sample['VEP_VEP-refseq-HGVSp'].split(':')[1]
        else:
            self.table['exon_intron'] = 'intron'
            self.table['HGVSp'] = '.'
    
        # HGVSp parsing
        [self.table['v1_POS1'], self.table['v1_AA1'], self.table['v1_POS2'], self.table['v1_AA2'], 
        self.table['v2_POS1'], self.table['v2_AA1'], self.table['v2_POS2'], self.table['v2_AA2']] = HGVSp_parser(self.table['HGVSp']).aa_pos_dict.values()
        
        # exon/intron position
        if 'VEP_VEP-refseq-Exon-or-Intron-Rank' in sample.keys():
            self.table['exon_intron_position'] = ' '.join([self.table['exon_intron'], sample['VEP_VEP-refseq-Exon-or-Intron-Rank'].split('/')[0]])
        else:
            self.table['exon_intron_position'] = '.'
    

    def Pathogenicity_prediction(self, sample):
        # pathogenicity record from ClinVar
        if 'ClinVar_CLNSIG' in sample.keys():
            self.table['ClinVar_record'] = " ".join(sample['ClinVar_CLNSIG'][0].split('_'))
        else:
            self.table['ClinVar_record'] = '.'

        # Transcript ID
        if 'Pathogenicity Scores_Ensembl-transcriptid' in sample.keys():
            self.table['Ensembl_transcriptid'] = sample['Pathogenicity Scores_Ensembl-transcriptid'].split(';')
        else:
            self.table['Ensembl_transcriptid'] = '.'

        # Pathogenicity prediction: SIFT score
        if 'Pathogenicity Scores_SIFT-score' in sample.keys():
            self.table['SIFT'] = str(sample['Pathogenicity Scores_SIFT-score']).split(';')
        else:
            self.table['SIFT'] = "."

        # Pathogenicity prediction: Polyphen2 score
        if 'Pathogenicity Scores_Polyphen2-HVAR-score' in sample.keys():
            self.table['PolyPhen2'] = str(sample['Pathogenicity Scores_Polyphen2-HVAR-score']).split(';')
        else:
            self.table['PolyPhen2'] = "."
        
        if self.table['Ensembl_transcriptid'] != '.':
            if self.table['SIFT'] == "." and self.table['PolyPhen2'] == ".":
                self.table['pathogenicity'] = '.'
                self.table['SIFT_record'] = '.'
                self.table['PolyPhen2_record'] = '.'
            elif all(score == '.' for score in self.table['SIFT']) and all(score == '.' for score in self.table['PolyPhen2']):
                self.table['pathogenicity'] = '.'
                self.table['SIFT_record'] = '.'
                self.table['PolyPhen2_record'] = '.'
            elif all(score == '.' for score in self.table['SIFT']):
                self.table['pathogenicity'] = 'recorded'
                self.table['SIFT_record'] = '; '.join([' for transcript' .join(list(record)) for record in zip(self.table['SIFT'], self.table['Ensembl_transcriptid']) if record[0] != "."])
                self.table['PolyPhen2_record'] = '.'
            elif all(score == '.' for score in self.table['PolyPhen2']):
                self.table['pathogenicity'] = 'recorded'
                self.table['SIFT_record'] = '.'
                self.table['PolyPhen2_record'] = '; '.join([' for transcript '.join(list(record)) for record in zip(self.table['PolyPhen2'], self.table['Ensembl_transcriptid']) if record[0] != "."])
            else:
                self.table['SIFT_record'] = '; '.join([' for transcript '.join(list(record)) for record in zip(self.table['SIFT'], self.table['Ensembl_transcriptid']) if record[0] != "."])
                self.table['PolyPhen2_record'] = '; '.join([' for transcript '.join(list(record)) for record in zip(self.table['PolyPhen2'], self.table['Ensembl_transcriptid']) if record[0] != "."])
                self.table['pathogenicity'] = 'recorded'
        else:
            if self.table['SIFT'] == "." and self.table['PolyPhen2'] == ".":
                self.table['pathogenicity'] = '.'
                self.table['SIFT_record'] = '.'
                self.table['PolyPhen2_record'] = '.'
            elif all(score == '.' for score in self.table['SIFT']) and all(score == '.' for score in self.table['PolyPhen2']):
                self.table['pathogenicity'] = '.'
                self.table['SIFT_record'] = '.'
                self.table['PolyPhen2_record'] = '.'
            elif all(score == '.' for score in self.table['SIFT']):
                self.table['pathogenicity'] = 'recorded'
                self.table['SIFT_record'] = self.table['SIFT']
                self.table['PolyPhen2_record'] = '.'
            elif all(score == '.' for score in self.table['PolyPhen2']):
                self.table['pathogenicity'] = 'recorded'
                self.table['SIFT_record'] = '.'
                self.table['PolyPhen2_record'] = self.table['PolyPhen2']
            else:
                self.table['SIFT_record'] = self.table['SIFT']
                self.table['PolyPhen2_record'] = self.table['PolyPhen2']
                self.table['pathogenicity'] = 'recorded'

        # Pathogenicity prediction: SpliceAI
        if 'SpliceAI-SNV_DS-AG' in sample.keys():
            self.table['spliceAI_AG'] = sample['SpliceAI-SNV_DS-AG']
            self.table['spliceAI_AL'] = sample['SpliceAI-SNV_DS-AL']
            self.table['spliceAI_DG'] = sample['SpliceAI-SNV_DS-DG']
            self.table['spliceAI_DL'] = sample['SpliceAI-SNV_DS-DL']
        else:
            self.table['spliceAI_AG'] = '.'
            self.table['spliceAI_AL'] = '.'
            self.table['spliceAI_DG'] = '.'
            self.table['spliceAI_DL'] = '.'
        
        # Pathogenicity prediction: DANN
        if 'DANN_DANN-score' in sample.keys():
            try:
                self.table['DANN']= round(float(sample['DANN_DANN-score']),3)
            except ValueError:
                self.table['DANN']= "."
        else:
            self.table['DANN']= '.'

        # Conservation Scores: phyloP100way
        if 'Conservation Scores_phyloP100way-vertebrate-rankscore' in sample.keys():
            try:
                self.table['phyloP100way']= round(float(sample['Conservation Scores_phyloP100way-vertebrate-rankscore']),3)
            except ValueError:
                self.table['phyloP100way']= "."
        else:
            self.table['phyloP100way']= '.'


    def allele_frequency(self, sample):
        # gnomAD
        if 'gnomAD-Genomes_AF-popmax' in sample.keys():
            try:
                self.table['gnomAD_freq'] = round(float(sample['gnomAD-Genomes_AF-popmax']),3)
            except ValueError:
                self.table['gnomAD_freq'] = "."
        else:
            self.table['gnomAD_freq'] = '.'
        # TaiwanBiobank
        if 'TaiwanBiobank-official_Illumina1000-AF' in sample.keys():
            try:
                self.table['TaiwanBiobank_freq'] = round(float(sample['TaiwanBiobank-official_Illumina1000-AF']),3)
            except ValueError:
                self.table['TaiwanBiobank_freq'] = '.'
        else:
            self.table['TaiwanBiobank_freq'] = '.'
   
    
    def hotspot_region(self, sample):
        if 'pathogenicHotspot-ailabs_pathogenicHotspot' in sample.keys():
            self.table['hotspot'] = ' and '.join(sample['pathogenicHotspot-ailabs_pathogenicHotspot'][0].split(','))
        else:
            self.table['hotspot'] = '.'

    
    def template_1(self, table):
        self.text_1 = {}
        if table['gene_name'] != ".":
            if table['HGVSc'] == ".":
                self.text_1['gene_name'] = f"A {table['GT']} {table['consequence']} variant is detected in the {table['gene_name']} gene, "
                self.text_1['HGVSc'] =  ""
            else:
                if len(self.table['CDS_position'].split('_')) > 1:
                    tmp_position = 'from the ' + ' to the '.join([self.ordinal_suffix(pos) for pos in self.table['CDS_position'].split('_')])
                else:
                    tmp_position = 'at the ' + self.ordinal_suffix(self.table['CDS_position'])
                self.text_1['gene_name'] = f"A {table['GT']} {table['consequence']} variant ({table['HGVSc']}) is detected {tmp_position} nucleotide \
in {table['exon_intron_position']} of the {table['gene_name']} gene ({table['gene_ID']}).\n"
                self.text_1['HGVSc'] =  ""
        else:
            self.text_1['gene_name'] = ''
        self.text_1['HGVSp'] = HGVSp_parser(self.table['HGVSp']).text
        self.text_1['ClinVar_record'] = f"This variant is recorded as '{table['ClinVar_record']}' in the ClinVar database.\n"
        self.text_1['hotspot'] = f"This variant is located in a hotspot region associated with high pathogenicity. (Pathogenic variants from {table['hotspot']})\n"
        self.text_1['gnomAD_freq'] = f"The allele frequency of this variant in the East Asian population of the Genome Aggregation Database (gnomAD) is {table['gnomAD_freq']}. "
        self.text_1['TaiwanBiobank_freq'] = f"In the Taiwan BioBank, the allele frequency in the Taiwanese population is {table['TaiwanBiobank_freq']}.\n"
        self.text_1['pathogenicity'] = f"The pathogenicity of the variant is predicted by multiple pathogenicity prediction software with SIFT*={table['SIFT_record']} and PolyPhen2#={table['PolyPhen2_record']} \
(*A lower SIFT score indicates higher pathogenicity, #a higher PolyPhen2 score indicates higher pathogenicity). "
        self.text_1['spliceAI_AG'] = f"The 4 predicted categories from spliceAI are acceptor gain (AG) = {table['spliceAI_AG']}, acceptor loss (AL) = {table['spliceAI_AL']}, \
donor gain (DG) = {table['spliceAI_DG']}, and donor loss (DL) = {table['spliceAI_DL']} \
(Any of AG, AL, DG, DL higher then 0.5 indicates higher pathogenicity). "
        self.text_1['DANN'] = f"The predicted score from DANN = {table['DANN']}, "
        self.text_1['phyloP100way'] = f"and the conservation score phyloP100way = {table['phyloP100way']}. "

    
    def template_2(self, table):
        self.text_2 = {}
        if table['gene_name'] != ".":
            if table['HGVSc'] == ".":
                self.text_2['gene_name'] = f"A {table['GT']} {table['consequence']} variant is detected in the {table['gene_name']} gene, "
            else:
                if len(self.table['CDS_position'].split('_')) > 1:
                    tmp_position = 'from the ' + ' to the '.join([self.ordinal_suffix(pos) for pos in self.table['CDS_position'].split('_')])
                else:
                    tmp_position = 'at the ' + self.ordinal_suffix(self.table['CDS_position'])
                self.text_2['gene_name'] = f"We detected a {table['GT']} {table['consequence']} variant ({table['HGVSc']}) {tmp_position} nucleotide \
in {table['exon_intron_position']} of the {table['gene_name']} gene ({table['gene_ID']}).\n"
                self.text_2['HGVSc'] =  ""
        self.text_2['HGVSp'] = HGVSp_parser(self.table['HGVSp']).text
        self.text_2['ClinVar_record'] = f"The ClinVar database depicted this variant as '{table['ClinVar_record']}'.\n"
        self.text_2['hotspot'] = f"Based on the record from {table['hotspot']}, this variant is located in a hotspot region associated with high pathogenicity.\n"
        self.text_2['gnomAD_freq'] = f"The East Asian population of the Genome Aggregation Database (gnomAD) showed that the allele frequency of this variant is {table['gnomAD_freq']}. "
        self.text_2['TaiwanBiobank_freq'] = f"The allele frequency of this variant in the Taiwanese population is {table['TaiwanBiobank_freq']} in the Taiwan BioBank.\n"
        self.text_2['pathogenicity'] = f"Multiple pathogenicity prediction software had applied to check the pathogenicity of the variant, and showed that SIFT*={table['SIFT_record']} and PolyPhen2#={table['PolyPhen2_record']} \
(*A lower SIFT score indicates higher pathogenicity, #a higher PolyPhen2 score indicates higher pathogenicity). "
        self.text_2['spliceAI_AG'] = f"SpliceAI reported the score of 4 predicted categories with acceptor gain (AG) = {table['spliceAI_AG']}, acceptor loss (AL) = {table['spliceAI_AL']}, donor gain (DG) = {table['spliceAI_DG']}, and donor loss (DL) = {table['spliceAI_DL']} \
(Any of AG, AL, DG, DL higher then 0.5 indicates higher pathogenicity). "
        self.text_2['DANN'] = f"The result from DANN = {table['DANN']}, "
        self.text_2['phyloP100way'] = f"and the conservation score predicted by phyloP100way is {table['phyloP100way']}."
    
    def template_na(self):
        self.text_na = {}
        self.text_na['gene_name'] = "The variant might be detected in an upstream or downstream region of the sequence, and the software could not identify which gene it is located in. "
        self.text_na['HGVSc'] = "but there is no sequence change compare to a reference sequence. "
        self.text_na['HGVSp'] = "There is no substitution of amino acid.\n"
        self.text_na['hotspot'] = "This variant is not recorded in any database to be located in a hotspot region.\n"
        self.text_na['gnomAD_freq'] = "The allele frequency of this variant didn't report in the East Asian population of the Genome Aggregation Database (gnomAD), "
        self.text_na['TaiwanBiobank_freq'] = "and the allele frequency of this variant in the Taiwanese population wasn't reported in the Taiwan BioBank.\n"
        self.text_na['ClinVar_record'] = "The pathogenicity of the variant had not been described in the ClinVar database.\n"
        self.text_na['pathogenicity'] = "Multiple pathogenicity prediction software could be applied to check the pathogenicity of the variant, but there are no records of the results of SIFT and PolyPhen2. "
        self.text_na['spliceAI_AG'] = "There is no prediction of spliceAI, "
        self.text_na['DANN'] = "and no result from DANN.\n"
        self.text_na['phyloP100way'] = "There is no conservation score predicted by phyloP100way."


    
    def generate_report(self):
        report = ''
        for key in self.text_1.keys():
            if self.table[key] =='.':
                report += self.text_na[key]
                if key == 'gene_name':
                    return report
            else:
                n = random.random()
                if n > 0.5:
                    report += self.text_1[key]
                else:
                    report += self.text_2[key]
        return report

    def generate_linear(self):
        linear_table = "<table> "
        keys = ['gene_name', 'gene_ID', 'HGVSc', 'CDS_position', 'GT', 'consequence', 'exon_intron', 'HGVSp', 'v1_POS1', 'v1_AA1', 'v1_POS2', 'v1_AA2', 'v2_POS1', 'v2_AA1', 'v2_POS2', 'v2_AA2', 'exon_intron_position', 'ClinVar_record', 'hotspot', 'SIFT_record', 'PolyPhen2_record', 'spliceAI_AG', 'spliceAI_AL', 'spliceAI_DG', 'spliceAI_DL', 'DANN', 'phyloP100way', 'gnomAD_freq', 'TaiwanBiobank_freq']
        for key in keys:
            linear_table += f"<cell> {self.table[key]} <col_header> {key} </col_header> </cell> "
        linear_table += "</table>"
        return linear_table
    
    def generate_raw_linear(self):
        linear_raw_table = "<table> "
        keys = ['Otherinfo_FORMAT-GT', 'VEP_VEP-refseq-Consequence', 'VEP_VEP-refseq-HGVSc', 'VEP_VEP-refseq-Exon-or-Intron-Rank', 'VEP_VEP-refseq-Gene-Name',
                 'VEP_VEP-refseq-HGVSp','ClinVar_CLNSIG', 'pathogenicHotspot-ailabs_pathogenicHotspot', 'TaiwanBiobank-official_Illumina1000-AF',
                 'Pathogenicity Scores_Ensembl-transcriptid', 'Pathogenicity Scores_SIFT-score','Pathogenicity Scores_Polyphen2-HVAR-score', 
                 'SpliceAI-SNV_DS-AG', 'SpliceAI-SNV_DS-AL', 'SpliceAI-SNV_DS-DG', 'SpliceAI-SNV_DS-DL',
                 'DANN_DANN-score', 'gnomAD-Genomes_AF-popmax', 'Conservation Scores_phyloP100way-vertebrate-rankscore']
        for key in keys:
            linear_raw_table += f"<cell> {self.sample[key]} <col_header> {key} </col_header> </cell> "
        linear_raw_table += "</table>"
        return linear_raw_table
    