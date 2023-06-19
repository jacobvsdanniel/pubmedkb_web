def aa_decode(AA):
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


def find_aa_pos(split_var):
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

def ordinal_suffix(num):
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

def aa_parser(AA):
    '''
    annotate the expression into a description or a amino acid
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
        AA_anno = ' or '.join([aa_decode(aa) for aa in AA.split('^')])
    else:
        AA_anno = AA
    return AA_anno

def variant_parser(split_var):
    '''
    parsing the variant expression to get the amino acid affected by the variant and its position
    '''
    # A region of protein sequence is affected (several amino acid)
    if '_' in split_var:
        AAs = split_var.split('_')
        POS1 = find_aa_pos(AAs[0])
        POS2 = find_aa_pos(AAs[-1])
        AA1 = AAs[0].split(POS1)[0]
        AA2 = AAs[-1].split(POS2)[0]
        AA2 = aa_parser(AA2)
    # single amino acid is affected
    else:
        POS1 = find_aa_pos(split_var)
        AA1 = split_var.split(POS1)[0]
        POS2 = '.'
        if '=/' in split_var.split(POS1)[-1]:
            AA2 = 'mosaic/' +  aa_parser(split_var.split(POS1)[-1])
        else:
            AA2 = split_var.split(POS1)[-1]
            AA2 = aa_parser(AA2)
    return POS1, aa_parser(AA1), POS2, AA2

def HGVSp_parser(HGVSp):
    '''
    parsing HGVSp into text
    '''
    v1_POS1, v1_AA1, v1_POS2, v1_AA2 = ['.', '.', '.', '.']
    v2_POS1, v2_AA1, v2_POS2, v2_AA2 = ['.', '.', '.', '.']

    if HGVSp == ".":
        text =  "There is no substitution of amino acid"
    else:
        if "%3D" in HGVSp:
            HGVSp = HGVSp[:-3]+"="
        variant = HGVSp.split('.')[-1]
        # preprocess
        if variant[0] == "(":
            variant = variant[1:-1]
        # deletion-insertion
        if 'delins' in variant:
            split_var = variant.split('delins')
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(split_var[0])
            v2_AA1 = split_var[1]
            if v1_POS2 == '.':
                if 'Ter' in v2_AA1:
                    v2_AA1 = v2_AA1[:-3]
                    text = f"This result in a deletion of the {ordinal_suffix(v1_POS1)} amino acid {aa_decode(v1_AA1)}, replaced with {aa_decode(v2_AA1)}, and premature termination"
                else:
                    text = f"This result in a deletion of the {ordinal_suffix(v1_POS1)} amino acid {aa_decode(v1_AA1)}, replaced with {aa_decode(v2_AA1)}"
            else:
                text = f"This result in a deletion of {int(v1_POS2)-int(v1_POS1)+1} amino acid from {v1_AA1+v1_POS1} to {v1_AA2+v1_POS2} replaced with {aa_decode(v2_AA1)}"
        # insertion   
        elif 'ins' in variant:
            split_var = variant.split('ins')
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(split_var[0])
            v2_AA1 = split_var[1]
            if len(v2_AA1) > 3:
                if 'Ter' in v2_AA1:
                    v2_AA1 = v2_AA1[:-3]
                    text = f"This results in a insertion of amino acids {aa_decode(v2_AA1)} between amino acids {v1_AA1+v1_POS1} and {v1_AA2+v1_POS2}, and premature termination"
                text = f"This results in a insertion of amino acids {aa_decode(v2_AA1)} between amino acids {v1_AA1+v1_POS1} and {v1_AA2+v1_POS2}"
            else:
                text = f"This results in a insertion of amino acid {aa_decode(v2_AA1)} between amino acids {v1_AA1+v1_POS1} and {v1_AA2+v1_POS2}"
        # deletion
        elif 'del' in variant:
            split_var = variant.split('del')
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(split_var[0])
            if v1_POS2 == '.':
                ### one amino acid (p.aa_1POSdel, p.(aa_1POSdel))
                text = f"This results in a deletion at the {ordinal_suffix(v1_POS1)} amino acids {aa_decode(v1_AA1)}"
                if v1_AA2 == "=/":
                    ### mosaic(p.aa_1POS=/del)
                    text = f"The variant leads to a mosaic case that besides the normal amino acid {aa_decode(v1_AA1)} also protein is found containing a deletion at position {v1_POS1}"
            else:
                ### several amino acid (p.aa_1POS1_aa_2POS2del, p.(aa_1POS1_aa_2POS2del))
                text = f"This results in the deletion of {int(v1_POS2)-int(v1_POS1)+1} amino acids (from {v1_AA1+v1_POS1} to {v1_AA2+v1_POS2})"
        
        # duplication
        elif 'dup' in variant:
            split_var = variant.split('dup')
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(split_var[0])
            if v1_POS2 == '.':
                ### one amino acid
                text = f"This results in a duplication at the {ordinal_suffix(v1_POS1)} amino acids {aa_decode(v1_AA1)}"
                if v1_AA2 == "=/":
                    ### mosaic
                    text = f"The variant leads to a mosaic case that besides the normal amino acid {v1_AA1} also protein is found containing a duplication at position {v1_POS1}"
            else:
                ### several amino acids
                text = f"This results in the duplication of {int(v1_POS2)-int(v1_POS1)+1} amino acids (from {v1_AA1+v1_POS1} to {v1_AA2+v1_POS2})"
        # frame-shift
        elif 'fs' in variant:
            split_var = variant.split('fs')
            if "fsTer" in variant:
                split_var = variant.split('fsTer')
                v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(split_var[0])
                v2_POS1 = split_var[-1]
                text = f"The {ordinal_suffix(v1_POS1)} amino acid was substituted from {aa_decode(v1_AA1)} to {aa_decode(v1_AA2)}. This results in the translation error of the following {v2_POS1} amino acids and leads to premature termination"
            elif "fs*" in variant:
                split_var = variant.split('fs*')
                v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(split_var[0])
                v2_POS1 = split_var[-1]
                if v2_POS1 == '?':
                    text = f'The {ordinal_suffix(v1_POS1)} amino acid was substituted from {aa_decode(v1_AA1)} to {aa_decode(v1_AA2)}. But the new reading frame does not encounter a new translation termination (stop) codon'
                else:
                    text = f"The {ordinal_suffix(v1_POS1)} amino acid was substituted from {aa_decode(v1_AA1)} to {aa_decode(v1_AA2)}. This results in the translation error of the following {v2_POS1} amino acids and leads to premature termination"
            else:
                split_var = variant.split('fs')
                v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(split_var[0])
                v2_POS1 = split_var[-1]
                if v2_POS1 == '':
                    text = f'The {ordinal_suffix(v1_POS1)} amino acid was substituted from {aa_decode(v1_AA1)} to {aa_decode(v1_AA2)}. This results in the translation error of the following amino acids'
                else:
                    text = f'The {ordinal_suffix(v1_POS1)} amino acid was substituted from {aa_decode(v1_AA1)} to {aa_decode(v1_AA2)}. This results in the translation error of the following {v2_POS1} amino acids'
        # extension
        elif 'ext' in variant:
            split_var = variant.split('ext')
            if split_var[0] == 'Met1':
                ### N-terminal (p.Met1extNEWPOS)
                text = f"This result in a variant in the 5' UTR activates a new upstream translation initiation site starting with amino acid {split_var[-1]}"
            else:
                ### C-terminal (p.TerPOSaa_1extTerNEWPOS, p.*POSaa_1ext*NEWPOS)
                v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(split_var[0])
                if "*" in split_var[-1]:
                    v2_POS1 = split_var[-1].split("*")[-1]
                else:
                    v2_POS1 = split_var[-1].split("Ter")[-1]
                if v2_POS1 == "?":
                    text = f"This result in a variant in the stop codon at position {v1_POS1}, changing it to a {aa_decode(v1_AA2)} (a no-stop variant) and adding a tail of new amino acids of unknown length"
                else:
                    text = f"This result in a variant in the stop codon at position {v1_POS1}, changing it to a {aa_decode(v1_AA2)} (a no-stop variant) and adding a tail of new amino acids to the protein's C-terminus, ending at a new stop codon at position {v2_POS1}"
        # translation initiation codon
        elif variant == '0':
            text = "As a consequence of a variant in the translation initiation codon no protein is produced"
        elif variant == 'Met1?':
            text = "The consequence of a variant affecting the translation initiation codon can not be predicted at protein level"

        #TODO: Allele

        #TODO: Repeated sequences (p.aa_1POS[copy_number])

        # substitution
        else:
            v1_POS1, v1_AA1, v1_POS2, v1_AA2 = variant_parser(variant)
            if v1_AA2 == 'silence change':
                text = f"The {ordinal_suffix(v1_POS1)} codon was affected, but it is a silence change"
            elif "mosaic/" in v1_AA2:
                v1_AA2 = v1_AA2.split("mosaic/")[-1]
                text = f"The variant leads to a mosaic case that besides the normal amino acid {aa_decode(v1_AA1)} also protein is found containing {aa_decode(v1_AA2)} at position {v1_POS1}"
            elif v1_AA2 == 'a stop codon':
                text = f"This led to the substitution of the {ordinal_suffix(v1_POS1)} amino acid from {aa_decode(v1_AA1)} to {v1_AA2}"
            elif v1_AA2 == 'unknown consequence':
                text = f"This led to the substitution of the {ordinal_suffix(v1_POS1)} amino acid from {aa_decode(v1_AA1)} to a {v1_AA2}"
            else:
                text = f"This led to the substitution of the {ordinal_suffix(v1_POS1)} amino acid from {aa_decode(v1_AA1)} to {aa_decode(v1_AA2)}"
    return [text + f" ({HGVSp}).", v1_POS1, aa_decode(v1_AA1), v1_POS2, aa_decode(v1_AA2), v2_POS1, aa_decode(v2_AA1), v2_POS2, aa_decode(v2_AA2)]
