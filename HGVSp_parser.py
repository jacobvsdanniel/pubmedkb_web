class HGVSp_parser():
    def __init__(self, HGVSp):
        self.HGVSp, variant = self.HGVSp_preprocess(HGVSp)
        self.aa_pos_dict = self.HGVSp_aa_pos_parse(variant)
        self.text = self.HGVSp_text(self.HGVSp, self.aa_pos_dict)

    def aa_decode(self, AA):
        dict = {"Ala": "Alanine", "Phe": "Phenylalanine", "Cys": "Cysteine", "Sec": "Selenocysteine",
                "Asp": "Aspartate", "Asn": "Asparagine", "Glu": "Glutamate", "Gln": "Glutamine", 
            "Gly": "Glycine", "His": "Histidine", "Leu": "Leucine", "Ile": "Isoleucine",
            "Lys": "Lysine", "Pyl": "Pyrrolysine", "Met": "Methionine", "Pro": "Proline",
            "Arg": "Arginine", "Ser": "Serine", "Thr": "Threonine", "Val": "Valine", 
            "Trp": "Tryptophan", "Tyr": "Tyrosine"}
        if AA in ['a stop codon', 'silence change', 'unknown consequence']:
            return AA
        elif "or" in AA:
            return AA
        elif AA == '.':
            return AA
        else:
            if "Ter" in AA:
                AAs = [dict[AA[i:i+3]] for i in range(0,len(AA[:-3]),3)]
            else:
                AAs = [dict[AA[i:i+3]] for i in range(0,len(AA),3)]
            return ";".join(AAs)


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
                if i in ['+', '-']:
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

    def aa_parser(self, AA):
        '''
        annotate the expression into a description or an amino acid
        '''
        if '=/' in AA:
            AA_anno = AA.split('=/')[-1]  
        elif AA == "Ter" or AA == "*":
            AA_anno = 'a stop codon'
        elif AA == "=" or AA == "%3D":
            AA_anno = 'silence change'
        elif AA == "?":
            AA_anno = 'unknown consequence'
        elif "^" in AA:
            AA_anno = ' or '.join([self.aa_decode(aa) for aa in AA.split('^')])
        else:
            AA_anno = AA
        return AA_anno

    def variant_parser(self, split_var):
        '''
        parsing the variant expression to get the amino acid affected by the variant and its position
        '''
        # A region of protein sequence is affected (several amino acid)
        if '_' in split_var:
            AAs = split_var.split('_')
            POS1 = self.find_aa_pos(AAs[0])
            POS2 = self.find_aa_pos(AAs[-1])
            AA1 = AAs[0].split(POS1)[0]
            AA2 = AAs[-1].split(POS2)[0]
            AA2 = self.aa_parser(AA2)
        # single amino acid is affected
        else:
            POS1 = self.find_aa_pos(split_var)
            AA1 = split_var.split(POS1)[0]
            POS2 = '.'
            if '=/' in split_var.split(POS1)[-1]:
                AA2 = 'mosaic/' +  self.aa_parser(split_var.split(POS1)[-1])
            else:
                AA2 = split_var.split(POS1)[-1]
                AA2 = self.aa_parser(AA2)
        return POS1, self.aa_parser(AA1), POS2, AA2

    def HGVSp_preprocess(self, HGVSp):
        variant = '.'
        if "%3D" in HGVSp:
            HGVSp = HGVSp[:-3]+"="
        if HGVSp != '.':
            variant = HGVSp.split('.')[-1]
            if variant[0] == "(":
                variant = variant[1:-1]
        return HGVSp, variant
    
    def HGVSp_aa_pos_parse(self, variant):
        '''
        parsing HGVSp into the amino acids affected by the variant and its position 
        '''
        v1_POS1, v1_AA1, v1_POS2, v1_AA2 = ['.', '.', '.', '.']
        v2_POS1, v2_AA1, v2_POS2, v2_AA2 = ['.', '.', '.', '.']
        if variant == '.':
            pass
        # deletion-insertion
        elif 'delins' in variant:
            self.type = 'delins'
            split_var = variant.split('delins')
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(split_var[0])
            v2_AA1 = split_var[1]
        # insertion   
        elif 'ins' in variant:
            self.type = 'ins'
            split_var = variant.split('ins')
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(split_var[0])
            v2_AA1 = split_var[1]
        # deletion
        elif 'del' in variant:
            self.type = 'del'
            split_var = variant.split('del')
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(split_var[0])
        
        # duplication
        elif 'dup' in variant:
            self.type = 'dup'
            split_var = variant.split('dup')
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(split_var[0])
        # frame-shift
        elif 'fs' in variant:
            self.type = 'fs'
            split_var = variant.split('fs')
            if "fsTer" in variant:
                self.type = 'fsTer'
                split_var = variant.split('fsTer')
                v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(split_var[0])
                v2_POS1 = split_var[-1]
            elif "fs*" in variant:
                self.type = 'fs*'
                split_var = variant.split('fs*')
                v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(split_var[0])
                v2_POS1 = split_var[-1]
            else:
                split_var = variant.split('fs')
                v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(split_var[0])
                v2_POS1 = split_var[-1]
        # extension
        elif 'ext' in variant:
            split_var = variant.split('ext')
            ### N-terminal (p.Met1extNEWPOS)
            if split_var[0] == 'Met1':
                self.type = 'ext_N-ter'
                v1_POS1 = '1'
                v1_AA1 = 'Met'
                v2_POS1 = split_var[-1]
            ### C-terminal (p.TerPOSaa_1extTerNEWPOS, p.*POSaa_1ext*NEWPOS)
            else:
                self.type = 'ext_C-ter'
                v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(split_var[0])
                if "*" in split_var[-1]:
                    v2_POS1 = split_var[-1].split("*")[-1]
                else:
                    v2_POS1 = split_var[-1].split("Ter")[-1]
        # translation initiation codon
        elif variant == '0':
            self.type = 'translation_initiation_codon'
            v1_POS1 = '0'
        elif variant == 'Met1?':
            self.type = 'translation_initiation_codon'
            v1_POS1 = '1'
            v1_AA1 = 'Met'
            v2_POS1 = '?'

        #TODO: Allele

        #TODO: Repeated sequences (p.aa_1POS[copy_number])

        # substitution
        else:
            self.type = 'substitution'
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = self.variant_parser(variant)
        return {'v1_POS1': v1_POS1, 'v1_AA1': v1_AA1, 'v1_POS2': v1_POS2, 'v1_AA2': v1_AA2, 'v2_POS1': v2_POS1, 'v2_AA1': v2_AA1, 'v2_POS2': v2_POS2, 'v2_AA2':v2_AA2}



    def HGVSp_text(self, HGVSp, aa_pos_dict):
        '''
        parsing HGVSp into text
        '''
        if HGVSp == ".":
            text =  "There is no substitution of amino acid"
        else:
            v1_POS1, v1_AA1, v1_POS2, v1_AA2, v2_POS1, v2_AA1, v2_POS2, v2_AA2 = aa_pos_dict.values()
            # deletion-insertion
            if self.type == 'delins':
                if v1_POS2 == '.':
                    if 'Ter' in v2_AA1:
                        v2_AA1 = v2_AA1[:-3]
                        text = f"This result in a deletion of the {self.ordinal_suffix(v1_POS1)} amino acid {self.aa_decode(v1_AA1)}, replaced with {self.aa_decode(v2_AA1)}, and premature termination"
                    else:
                        text = f"This result in a deletion of the {self.ordinal_suffix(v1_POS1)} amino acid {self.aa_decode(v1_AA1)}, replaced with {self.aa_decode(v2_AA1)}"
                else:
                    text = f"This result in a deletion of {int(v1_POS2)-int(v1_POS1)+1} amino acid from {v1_AA1+v1_POS1} to {v1_AA2+v1_POS2} replaced with {self.aa_decode(v2_AA1)}"
            # insertion   
            elif self.type == 'ins':
                if len(v2_AA1) > 3:
                    if 'Ter' in v2_AA1:
                        v2_AA1 = v2_AA1[:-3]
                        text = f"This results in a insertion of amino acids {self.aa_decode(v2_AA1)} between amino acids {v1_AA1+v1_POS1} and {v1_AA2+v1_POS2}, and premature termination"
                    else:
                        text = f"This results in a insertion of amino acids {self.aa_decode(v2_AA1)} between amino acids {v1_AA1+v1_POS1} and {v1_AA2+v1_POS2}"
                else:
                    text = f"This results in a insertion of amino acid {self.aa_decode(v2_AA1)} between amino acids {v1_AA1+v1_POS1} and {v1_AA2+v1_POS2}"
            # deletion
            elif self.type == 'del':
                if v1_POS2 == '.':
                    ### one amino acid (p.aa_1POSdel, p.(aa_1POSdel))
                    text = f"This results in a deletion at the {self.ordinal_suffix(v1_POS1)} amino acids {self.aa_decode(v1_AA1)}"
                    if v1_AA2 == "=/":
                        ### mosaic(p.aa_1POS=/del)
                        text = f"The variant leads to a mosaic case that besides the normal amino acid {self.aa_decode(v1_AA1)} also protein is found containing a deletion at position {v1_POS1}"
                else:
                    ### several amino acid (p.aa_1POS1_aa_2POS2del, p.(aa_1POS1_aa_2POS2del))
                    text = f"This results in the deletion of {int(v1_POS2)-int(v1_POS1)+1} amino acids (from {v1_AA1+v1_POS1} to {v1_AA2+v1_POS2})"
            
            # duplication
            elif self.type == 'dup':
                if v1_POS2 == '.':
                    ### one amino acid
                    if v1_AA2 == "=/":
                        ### mosaic
                        text = f"The variant leads to a mosaic case that besides the normal amino acid {v1_AA1} also protein is found containing a duplication at position {v1_POS1}"
                    else:
                        text = f"This results in a duplication at the {self.ordinal_suffix(v1_POS1)} amino acids {self.aa_decode(v1_AA1)}"
                else:
                    ### several amino acids
                    text = f"This results in the duplication of {int(v1_POS2)-int(v1_POS1)+1} amino acids (from {v1_AA1+v1_POS1} to {v1_AA2+v1_POS2})"
            # frame-shift
            elif self.type == 'fs':
                if v2_POS1 == '':
                        text = f'The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {self.aa_decode(v1_AA1)} to {self.aa_decode(v1_AA2)}. This results in the translation error of the following amino acids'
                else:
                    text = f'The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {self.aa_decode(v1_AA1)} to {self.aa_decode(v1_AA2)}. This results in the translation error of the following {v2_POS1} amino acids'
            elif self.type == "fsTer":
                text = f"The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {self.aa_decode(v1_AA1)} to {self.aa_decode(v1_AA2)}. This results in the translation error of the following {v2_POS1} amino acids and leads to premature termination"
            elif self.type == "fs*" :
                if v2_POS1 == '?':
                    text = f'The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {self.aa_decode(v1_AA1)} to {self.aa_decode(v1_AA2)}. But the new reading frame does not encounter a new translation termination (stop) codon'
                else:
                    text = f"The {self.ordinal_suffix(v1_POS1)} amino acid was substituted from {self.aa_decode(v1_AA1)} to {self.aa_decode(v1_AA2)}. This results in the translation error of the following {v2_POS1} amino acids and leads to premature termination"

            # extension
            elif self.type == 'ext_N-ter':
                ### N-terminal (p.Met1extNEWPOS)
                text = f"This result in a variant in the 5' UTR activates a new upstream translation initiation site starting with amino acid {v2_POS1}"
            elif self.type == 'ext_C-ter':
                ### C-terminal (p.TerPOSaa_1extTerNEWPOS, p.*POSaa_1ext*NEWPOS)
                if v2_POS1 == "?":
                    text = f"This result in a variant in the stop codon at position {v1_POS1}, changing it to a {self.aa_decode(v1_AA2)} (a no-stop variant) and adding a tail of new amino acids of unknown length"
                else:
                    text = f"This result in a variant in the stop codon at position {v1_POS1}, changing it to a {self.aa_decode(v1_AA2)} (a no-stop variant) and adding a tail of new amino acids to the protein's C-terminus, ending at a new stop codon at position {v2_POS1}"
            # translation initiation codon
            elif self.type == 'translation_initiation_codon':
                if v1_POS1 == '0':
                    text = "As a consequence of a variant in the translation initiation codon no protein is produced"
                else:
                    text = "The consequence of a variant affecting the translation initiation codon can not be predicted at protein level"

            #TODO: Allele

            #TODO: Repeated sequences (p.aa_1POS[copy_number])

            # substitution
            else:
                if v1_AA2 == 'silence change':
                    text = f"The {self.ordinal_suffix(v1_POS1)} codon was affected, but it is a silence change"
                elif "mosaic/" in v1_AA2:
                    v1_AA2 = v1_AA2.split("mosaic/")[-1]
                    text = f"The variant leads to a mosaic case that besides the normal amino acid {self.aa_decode(v1_AA1)} also protein is found containing {self.aa_decode(v1_AA2)} at position {v1_POS1}"
                elif v1_AA2 == 'a stop codon':
                    text = f"This led to the substitution of the {self.ordinal_suffix(v1_POS1)} amino acid from {self.aa_decode(v1_AA1)} to {v1_AA2}"
                elif v1_AA2 == 'unknown consequence':
                    text = f"This led to the substitution of the {self.ordinal_suffix(v1_POS1)} amino acid from {self.aa_decode(v1_AA1)} to a {v1_AA2}"
                else:
                    text = f"This led to the substitution of the {self.ordinal_suffix(v1_POS1)} amino acid from {self.aa_decode(v1_AA1)} to {self.aa_decode(v1_AA2)}"
        return text + f" ({HGVSp})."
