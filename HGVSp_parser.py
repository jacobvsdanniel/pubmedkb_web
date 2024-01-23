# version 2024.01.23
import re
class HGVSpParser:
    def __init__(self, HGVSp):
        self.HGVSp, variant = self.HGVSp_preprocess(HGVSp)
        self.aa_pos_dict = self.HGVSp_aa_pos_parse(variant)
        self.text, self.text_zhtw = self.HGVSp_text(self.HGVSp, self.aa_pos_dict)
    
    def HGVSp_preprocess(self, HGVSp):
        variant = '.'
        HGVSp = HGVSp.strip().replace('%3D', '=') # e.g. p.Cys188%3D -> p.Cys188=
        if HGVSp != '.':
            variant = HGVSp.split('.')[-1] # e.g. p.(Val7del) -> (Val7del)
            if variant[0] == "(": 
                variant = variant[1:-1]  # e.g. (Val7del) -> Val7del
        variant = variant.replace('*', 'Ter') # e.g. His321Leufs*3 -> His321LeufsTer3
        return HGVSp, variant # ['p.Cys188=', 'Cys188='] 
    
    def HGVSp_aa_pos_parse(self, variant):
        '''
        parsing HGVSp into the amino acids affected by the variant and its position 
        '''
        v1_POS1, v1_AA1, v1_POS2, v1_AA2, v2_POS1, v2_AA1 = ['.']*6
        if variant == '.':
            pass
        
        elif '_?' in variant: # e.g. p.MetGly1_?2
            self.type = 'frameshift_or_start-lost'
            split_var = variant.split('_?') # ['MetGly1', '2']


        # deletion-insertion
        elif 'delins' in variant: # e.g. p.Cys28delinsTrpVal
            self.type = 'deletion-insertion'
            split_var = variant.split('delins') # ['Cys28', 'TrpVal']
            v1_AA1, v1_POS1, v1_AA2, v1_POS2  = self.variant_parser(split_var[0]) # 'Cys' -> ['Cysteine', '28', '.', '.']
            v2_AA1 = self.aa_decode(split_var[-1]) # 'TrpVal' -> 'Tryptophan and Valine'

        # insertion 
        elif 'ins' in variant:
            if "insTer" in variant: # e.g. p.Lys2_Leu3insTer12
                self.type = 'insertion_Ter'
                split_var = variant.split('insTer') # ['Lys2_Leu3', '12']
                v1_AA1, v1_POS1, v1_AA2, v1_POS2  = self.variant_parser(split_var[0]) # 'Lys2_Leu3' -> ['Lysine', '2', 'Leucine', '3']
                v2_POS1 = split_var[-1] # '12'
            else: # p.His4_Gln5insAla
                self.type = 'insertion'
                split_var = variant.split('ins') # ['His4_Gln5', 'Ala']
                v1_AA1, v1_POS1, v1_AA2, v1_POS2  = self.variant_parser(split_var[0]) # 'His4_Gln5' -> ['Histidine', '4', 'Glutamine', '5']
                v2_AA1 = self.aa_decode(split_var[-1]) # 'Ala' -> 'Alanine'

        # deletion
        elif 'del' in variant: # e.g. p.Val7del
            self.type = 'deletion'
            split_var = variant.split('del') # ['Val7']
            v1_AA1, v1_POS1, v1_AA2, v1_POS2  = self.variant_parser(split_var[0]) # 'Val7' -> ['Valine', '7', '.', '.']
        
        # duplication 
        elif 'dup' in variant: # e.g. p.Lys23_Val25dup
            self.type = 'duplication'
            split_var = variant.split('dup') # ['Lys23_Val25']
            v1_AA1, v1_POS1, v1_AA2, v1_POS2  = self.variant_parser(split_var[0]) # 'Lys23_Val25' -> ['Lysine', '23', 'Valine', '25']

        # frame-shift
        elif 'fs' in variant:
            self.type = 'frame-shift'
            split_var = variant.split('fs')
            if "fsTer" in variant: # e.g. p.Arg97ProfsTer23
                self.type = 'frame-shift_Ter'
                split_var = variant.split('fsTer') # ['Arg97Pro', '23']
                v1_AA1, v1_POS1, v2_AA1, _  = self.variant_parser(split_var[0]) # 'Arg97Pro' -> ['Arginine', '97', 'Proline', '.']
                v2_POS1 = split_var[-1] # '23'
            else: # e.g. p.Arg97fs (short for p.Arg97ProfsTer23)
                split_var = variant.split('fs') # ['Arg97Pro']
                v1_AA1, v1_POS1, v2_AA1, _  = self.variant_parser(split_var[0])  # 'Arg97Pro' -> ['Arginine', '97', 'Proline', '.']
                #v2_POS1 = split_var[-1]

        # extension
        elif 'ext' in variant:
            split_var = variant.split('ext')
            ### N-terminal (p.Met1extNEWPOS)
            if split_var[0] == 'Met1':
                self.type = 'extension_N-terminal'
                v1_POS1, v1_AA1 = ['1', self.aa_decode('Met')]
                v2_POS1 = split_var[-1]
            ### C-terminal (p.TerPOSaa_1extTerNEWPOS, p.*POSaa_1ext*NEWPOS)
            else: # e.g. p.Ter110GlnextTer17 -> ['Ter110Gln', 'Ter17']
                self.type = 'extension_C-terminal'
                v1_AA1, v1_POS1, v1_AA2, v1_POS2 = self.variant_parser(split_var[0]) #['a stop codon', '110', 'Glutamine', '.']
                v2_POS1 = split_var[-1].split("Ter")[-1] # 'Ter17' -> ['', '17']

        # translation initiation codon
        elif variant == '0': # e.g. p.0
            self.type = 'translation_initiation_codon'
            v1_POS1 = '0'
        elif variant == 'Met1?': # e.g. p.Met1?
            self.type = 'translation_initiation_codon'
            v1_POS1 = '1'
            v1_AA1 = self.aa_decode('Met')
            v2_POS1 = '?'

        #TODO: Allele

        #TODO: Repeated sequences (p.aa_1POS[copy_number])

        # substitution
        else: # e.g. p.Trp24Cys (missense), p.Trp24Ter (nonsense), p.Cys188= (silent), p.Gly56Ala^Ser^Cys (uncertain), p.Trp24=/Cys (mosaic)
            self.type = 'substitution'
            v1_AA1, v1_POS1, v2_AA1, _  = self.variant_parser(variant)
        return {'v1_POS1': v1_POS1, 'v1_AA1': v1_AA1, 'v1_POS2': v1_POS2, 'v1_AA2': v1_AA2, 'v2_POS1': v2_POS1, 'v2_AA1': v2_AA1}


    def variant_parser(self, split_var):
        '''
        parsing the variant expression to get the amino acid affected by the variant and its position
        '''
        # A region of protein sequence is affected (several amino acid)
        if '_' in split_var: # e.g. His4_Gln5
            AAs = split_var.split('_') # ['His4', 'Gln5']
            POS1 = self.find_aa_pos(AAs[0]) # '4'
            POS2 = self.find_aa_pos(AAs[-1]) # '5'
            AA1 = AAs[0].rstrip(POS1) # 'His'
            AA2 = AAs[-1].rstrip(POS2) # 'Gln'
        # single amino acid is affected
        else: # e.g. Cys28
            POS1 = self.find_aa_pos(split_var) # '28'
            AA1, AA2 = [aa if aa != '' else '.' for aa in split_var.split(POS1)] # ['Cys', '.']
            POS2 = '.'
        return self.aa_decode(AA1), POS1, self.aa_decode(AA2), POS2
    
    def aa_decode(self, AA):
        '''
            possible AA:
                - .
                - AA
                - AA1AA2AA3... (sequence)
                - AA1^AA2^AA3... (uncertain)
                - =/AA (mosaic)
                - = (silent)
                - AA1AA2Ter
                - Ter
        '''
        aa_dict = {"Ala": "Alanine", "Phe": "Phenylalanine", "Cys": "Cysteine", "Sec": "Selenocysteine",
                   "Asp": "Aspartate", "Asn": "Asparagine", "Glu": "Glutamate", "Gln": "Glutamine", 
                   "Gly": "Glycine", "His": "Histidine", "Leu": "Leucine", "Ile": "Isoleucine",
                   "Lys": "Lysine", "Pyl": "Pyrrolysine", "Met": "Methionine", "Pro": "Proline",
                   "Arg": "Arginine", "Ser": "Serine", "Thr": "Threonine", "Val": "Valine", 
                   "Trp": "Tryptophan", "Tyr": "Tyrosine", ".":''}
        aa_dict_zhtw = {"Ala": "丙胺酸", "Phe": "苯丙胺酸", "Cys": "半胱胺酸", "Sec": "硒半胱胺酸",
                    "Asp": "天門冬胺酸", "Asn": "天門冬醯胺", "Glu": "麩胺酸", "Gln": "麩醯胺酸", 
                    "Gly": "甘胺酸", "His": "組胺酸", "Leu": "白胺酸", "Ile": "異白胺酸",
                    "Lys": "離胺酸", "Pyl": "吡咯離胺酸", "Met": "甲硫胺酸", "Pro": "脯胺酸",
                    "Arg": "精胺酸", "Ser": "絲胺酸", "Thr": "蘇胺酸", "Val": "纈胺酸", 
                    "Trp": "色胺酸", "Tyr": "酪胺酸", ".":''}
        if AA == '.':
            return '.', '.'
        elif re.search(r"^=/", AA):
            AA = AA.lstrip('=/') if AA.lstrip('=/') != '' else '.' # e.g. "=/Gly" -> "Gly"; "=/" -> "."
            return f"=/{aa_dict[AA]}", f"=/{aa_dict_zhtw[AA]}"
        elif AA == "Ter":
            return 'a stop codon', '終止密碼子'
        elif AA == "=":
            return 'silence change', '沉默突變'
        elif AA == '?':
             return 'unknown consequence', '未知的後果'
        elif '^' in AA: # uncertain substitution case
            AA_ls = [aa_dict[aa] for aa in AA.split('^')]
            AA_ls_zhtw = [aa_dict_zhtw[aa] for aa in AA.split('^')]
            if len(AA_ls) > 2:
                return  ', '.join(AA_ls[:-1]) + f', or {AA_ls[-1]}', '、'.join(AA_ls_zhtw[:-1]) + f'或{AA_ls_zhtw[-1]}'
            return ' or '.join(AA_ls), '或'.join(AA_ls_zhtw)
        else: # one or more common amino acid
            prefix = ''
            if AA[-3:] == 'Ter': # premature termination case
                AA = AA[:-3]
                prefix = 'Ter/'
            AAs = [aa_dict[AA[i:i+3]] for i in range(0,len(AA),3)]
            AAs_zhtw = [aa_dict_zhtw[AA[i:i+3]] for i in range(0,len(AA),3)]
            return prefix + "-".join(AAs), prefix + "-".join(AAs_zhtw)

    def find_aa_pos(self, split_var):
        '''
        find the position of the amino acid that affected by the variant
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
            else:
                break
        return ''.join(pos)

    def ordinal_suffix(self, num):
        '''
        add ordinal suffix to the position of amino acid
        '''
        j = int(num) % 10
        k = int(num) % 100
        if j == 1 and k != 11:
            return num + "st"
        elif j == 2 and k != 12:
            return num + "nd"
        elif j == 3 and k != 13:
            return num + "rd"
        else:
            return num + "th"


    def HGVSp_text(self, HGVSp, aa_pos_dict):
        '''
        parsing HGVSp into text
        '''
        if HGVSp == ".":
            text =  "There is no substitution of amino acid."
            text_zhtw =  "此變異沒有造成胺基酸的置換。"
            self.type = "NA"
            return text, text_zhtw
        else:
            v1_POS1, v1_AA1, v1_POS2, v1_AA2, v2_POS1, v2_AA1 = aa_pos_dict.values()
            # AA: [0] -> En; [1] -> Zh

            # frameshift_or_start-lost (_?)
            if self.type == 'frameshift_or_start-lost':
                text = "This leads to the movement of the stop codon to the 3'UTR region"
                text_zhtw = f"此變異導致終止密碼子移動至三端非轉譯區（3'UTR）中"
            # deletion-insertion
            elif self.type == 'deletion-insertion':
                if v1_POS2 == '.': # one amino acid deletion-insertion
                    #if 'Ter' in v2_AA1:
                    if re.search(r'^Ter/', v2_AA1[0]): # premature termination
                        v2_AA1 = [aa.replace('Ter/', '') for aa in v2_AA1]
                        text = f"This leads to the deletion of the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, which is replaced with {v2_AA1[0]}, resulting in premature termination"
                        text_zhtw = f"這導致第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）被刪除，並被{v2_AA1[1]}（{v2_AA1[0]}）取代，形成過早的終止密碼子"

                    else:
                        text = f"This results in the deletion of the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, which is replaced with {v2_AA1[0]}"
                        text_zhtw = f"這導致第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）被刪除，並被{v2_AA1[1]}（{v2_AA1[0]}）取代"
                else: # a region of amino acids deletion-insertion
                    if re.search(r'^Ter/', v2_AA1[0]): # premature termination
                        v2_AA1 = [aa.replace('Ter/', '') for aa in v2_AA1]
                        text = f"This leads to the deletion of amino acids from the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, to the {self.ordinal_suffix(v1_POS2)} amino acid, {v1_AA2[0]}, which are replaced with {v2_AA1[0]}, resulting in premature termination"
                        text_zhtw = f"這導致從第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）至第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}）被刪除，並被{v2_AA1[1]}（{v2_AA1[0]}）取代，形成過早的終止密碼子"

                    else:
                        text = f"This results in the deletion of amino acids from the {self.ordinal_suffix(v1_POS1)}, {v1_AA1[0]}, to the {self.ordinal_suffix(v1_POS2)}, {v1_AA2[0]}, which are then replaced with {v2_AA1[0]}"
                        # text_zhtw = f"這導致從第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）至第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}），共{int(v1_POS2)-int(v1_POS1)+1}個胺基酸被刪除，並被{v2_AA1[1]}（{v2_AA1[0]}）取代"
                        text_zhtw = f"這導致從第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）至第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}）被刪除，並被{v2_AA1[1]}（{v2_AA1[0]}）取代"

            # insertion   
            elif self.type == 'insertion':
                if '-' in v2_AA1[0]: # insert more than one amino acids (AA1-AA2-AA3)
                    if re.search(r'^Ter/', v2_AA1[0]):
                        v2_AA1 = [aa.replace('Ter/', '') for aa in v2_AA1]
                        text = f"This leads to the insertion of amino acids, {v2_AA1[0]}, between the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, and the {self.ordinal_suffix(v1_POS2)} amino acid, {v1_AA2[0]}, resulting in premature termination"
                        text_zhtw = f"這導致多個胺基酸{v2_AA1[1]}（{v2_AA1[0]}）插入於第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）和第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}）之間，形成過早的終止密碼子"

                    else:
                        text = f"This results in the insertion of amino acids, {v2_AA1[0]}, between the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, and the {self.ordinal_suffix(v1_POS2)} amino acid, {v1_AA2[0]}"
                        text_zhtw = f"這導致多個胺基酸{v2_AA1[1]}（{v2_AA1[0]}）插入於第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）和第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}）之間"
                else:
                    text = f"This results in the insertion of the amino acid {v2_AA1[0]} between the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, and the {self.ordinal_suffix(v1_POS2)} amino acid, {v1_AA2[0]}"
                    text_zhtw = f"這導致胺基酸{v2_AA1[1]}（{v2_AA1[0]}）插入於第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）和第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}）之間"
            
            elif self.type == 'insertion_Ter':
                if v2_POS1 == '':
                    text = f"This results in the insertion of a stop codon between the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, and the {self.ordinal_suffix(v1_POS2)} amino acid, {v1_AA2[0]}"
                    text_zhtw = f"這導致一個終止密碼子（a stop codon）插入於第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）和第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}）之間"
                else:
                    text = f"This results in the insertion of a {int(v2_POS1)-1}-amino-acid sequence ending up at a stop codon between the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, and the {self.ordinal_suffix(v1_POS2)} amino acid, {v1_AA2[0]}"
                    text_zhtw = f"這導致{int(v2_POS1)-1}個胺基酸及一個終止密碼子（a stop codon）插入於第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）和第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}）之間"

            # deletion
            elif self.type == 'deletion':
                if v1_POS2 == '.':
                    ### one amino acid (p.aa_1POSdel, p.(aa_1POSdel))
                    text = f"This results in a deletion at the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}"
                    text_zhtw = f"這導致第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）被刪除"
                    if v1_AA2 == "=/":
                        ### mosaic(p.aa_1POS=/del)
                        text = f"The variant leads to a mosaic case that besides the normal amino acid {v1_AA1[0]} also protein is found containing a deletion at position {v1_POS1}"
                        text_zhtw = f"此變異導致了鑲嵌現象（mosaic case），蛋白質中的第{v1_POS1}個胺基酸，除了正常的{v1_AA1[1]}（{v1_AA1[0]}）外，也發現了一些蛋白質在這個位置上的胺基酸被刪除"
                else:
                    ### several amino acid (p.aa_1POS1_aa_2POS2del, p.(aa_1POS1_aa_2POS2del))
                    text = f"This results in the deletion of amino acids from the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, to the {self.ordinal_suffix(v1_POS2)} amino acid, {v1_AA2[0]}"
                    text_zhtw = f"這導致從第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）至第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}），共{int(v1_POS2)-int(v1_POS1)+1}個胺基酸被刪除"

            # duplication
            elif self.type == 'duplication':
                if v1_POS2 == '.':
                    ### one amino acid
                    if re.search(r'^=/', v1_AA2[0]): ### mosaic case
                        text = f"The variant leads to a mosaic case that besides the normal amino acid {v1_AA1[0]} also protein is found containing a duplication at position {v1_POS1}"
                        text_zhtw = f"此變異導致了鑲嵌現象（mosaic case），蛋白質中的第{v1_POS1}個胺基酸，除了正常的{v1_AA1[1]}（{v1_AA1[0]}）外，也發現了有一些蛋白質在這個位置上的胺基酸產生重複"
                    else:
                        text = f"This results in the duplication of the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}"
                        text_zhtw = f"這導致第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）產生重複"
                else:
                    ### several amino acids
                    text = f"This results in the duplication of amino acids from the {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, to the {self.ordinal_suffix(v1_POS2)} amino acid, {v1_AA2[0]}"
                    text_zhtw = f"這導致從第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）至第{v1_POS2}個胺基酸{v1_AA2[1]}（{v1_AA2[0]}）產生重複"


            # frame-shift
            elif self.type == 'frame-shift':
                if v2_POS1 == '':
                    text = f'The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {v1_AA1[0]} to {v2_AA1[0]}. This results in the translation error of the following amino acids'
                    text_zhtw = f"這導致第{v1_POS1}個胺基酸由{v1_AA1[1]}（{v1_AA1[0]}）置換為{v2_AA1[1]}（{v2_AA1[0]}），並產生移碼變異，造成轉譯錯誤"
                else:
                    text = f'The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {v1_AA1[0]} to {v2_AA1[0]}. This results in the translation error of the following {v2_POS1} amino acids'
                    text_zhtw = f"這導致第{v1_POS1}個胺基酸由{v1_AA1[1]}（{v1_AA1[0]}）置換為{v2_AA1[1]}（{v2_AA1[0]}），並使得接續的{v2_POS1}個胺基酸產生移碼變異，造成轉譯錯誤"

            elif self.type == "frame-shift_Ter":
                if v2_POS1 == '?':
                    text = f'The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {v1_AA1[0]} to {v2_AA1[0]}. But the new reading frame does not encounter a new translation termination (stop) codon'
                    text_zhtw = f"這導致第{v1_POS1}個胺基酸由{v1_AA1[1]}（{v1_AA1[0]}）置換為{v2_AA1[1]}（{v2_AA1[0]}），但移碼變異後的結果並未包含新的終止密碼子"
                else:
                    text = f"The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {v1_AA1[0]} to {v2_AA1[0]}. This results in the translation error of the following {v2_POS1} amino acids and leads to premature termination"
                    text_zhtw = f"這導致第{v1_POS1}個胺基酸由{v1_AA1[1]}（{v1_AA1[0]}）置換為{v2_AA1[1]}（{v2_AA1[0]}），並使得接續的{v2_POS1}個胺基酸產生移碼變異，除了造成轉譯錯誤外也造成提前終止"

            # extension
            elif self.type == 'extension_N-terminal':
                ### N-terminal (p.Met1extNEWPOS)
                text = f"The variant, which is in the 5'UTR, activates a new upstream translation initiation site at {v2_POS1}"
                text_zhtw = f"這導致了一個位於五端非轉譯區（5' UTR）中的變異，此變異於第{v2_POS1}個胺基酸的位置啟動了一個新的上游轉譯起始位點"
            elif self.type == 'extension_C-terminal':
                ### C-terminal (p.TerPOSaa_1extTerNEWPOS, p.*POSaa_1ext*NEWPOS)
                if v2_POS1 == "?":
                    text = f"This results in the replacement of a stop codon at position {v1_POS1} with a {v1_AA2[0]}, generating a no-stop variant and appending a sequence of new amino acids of an unknown length"
                    text_zhtw = f"這導致了位於第{v1_POS1}位置的終止密碼子置換為{v1_AA2[1]}（{v1_AA2[0]}），並增加了一段未知長度的新胺基酸序列於原序列尾端"
                else:
                    text = f"This results in the replacement of a stop codon at position {v1_POS1} with a {v1_AA2[0]}, generating a no-stop variant and appending a sequence of new amino acids to the protein's C-terminus, ending at a new stop codon at position {v2_POS1}"
                    text_zhtw = f"這導致了位於第{v1_POS1}位置的終止密碼子置換為{v1_AA2[1]}（{v1_AA2[0]}），並於蛋白質的羧基端（C-terminus）增加了一段新的胺基酸序列，並結束於位在第{v2_POS1}個位置的新終止密碼子"
            
            # translation initiation codon
            elif self.type == 'translation_initiation_codon':
                if v1_POS1 == '0':
                    text = "As a consequence of a variant in the translation initiation codon no protein is produced"
                    text_zhtw = "因變異位於轉譯起始密碼子，無任何蛋白質產生"
                else:
                    text = "The impact of a variant affecting the translation initiation codon can not be reliably predicted at protein level"
                    text_zhtw = "此變異因對轉譯起始密碼子造成影響，無法在蛋白質層級被預測"


            #TODO: Allele

            #TODO: Repeated sequences (p.aa_1POS[copy_number])

            # substitution
            else:
                if v2_AA1[0] == 'silence change':
                    text = f"The {self.ordinal_suffix(v1_POS1)} amino acid, {v1_AA1[0]}, was affected, but it is a {v2_AA1[0]}"
                    text_zhtw = f"第{v1_POS1}個胺基酸{v1_AA1[1]}（{v1_AA1[0]}）被此變異影響，但為一個{v2_AA1[1]}"
                elif re.search(r'^=/', v2_AA1[0]): # mosaic case
                    v2_AA1 = [aa.replace('=/', '') for aa in v2_AA1]
                    text = f"The variant leads to a mosaic case that besides the normal amino acid {v1_AA1[0]} also protein is found containing {v2_AA1[0]} at position {v1_POS1}"
                    text_zhtw = f"此變異造成鑲嵌現象（mosaic case），蛋白質中的第{v1_POS1}個胺基酸，除了正常的{v1_AA1[1]}（{v1_AA1[0]}）外，也發現了一些蛋白質在這個位置上的胺基酸置換為{v2_AA1[1]}（{v2_AA1[0]}）"
                else:
                    text = f"This leads to the substitution of the {self.ordinal_suffix(v1_POS1)} amino acid from {v1_AA1[0]} to {v2_AA1[0]}"
                    text_zhtw = f"這導致第{v1_POS1}個胺基酸由{v1_AA1[1]}（{v1_AA1[0]}）置換為{v2_AA1[1]}（{v2_AA1[0]}）"
        return text + f" ({HGVSp}). ", text_zhtw + f"（{HGVSp}）。"

