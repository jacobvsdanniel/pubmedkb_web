import re

def find_CDS_pos(split_var):
    '''
    find the position of the nucleotide(s) in coding sequence (CDS) that affected by the variant (based on HGVS annotation)
        d: exon region
        d+d, d-d: intron region
        d1_d2, d1+d11_d2+d21, ...: from position1 to position2
        *d: 3'-UTR region
        -d: 5'-UTR region
    '''
    pos=[]
    start = re.search(r"[\d\*\-]", split_var).span()[0] # exon/intron region or 3'-, 5'- UTR region
    for i in split_var[start:]:
        if i.isdigit() or i in ['+', '-', '*', '_']:
            pos.append(i)
        else: break
    return ''.join(pos)

def ordinal_suffix(num):
    '''
    add ordinal suffix after number
    '''
    match_punc =  re.findall(r"[\*\-\+]", num, flags=0)
    tmp_num = num.split(match_punc[-1])[-1] if match_punc else num
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

def clinvar_translate(ClinVar_record):
    ClinVar_record = ClinVar_record.lower()
    cinvar_cls_zhtw = {'benign':'良性', 'likely benign': '高度懷疑良性', 'uncertain significance': '臨床意義尚未明確（VUS）', 'likely pathogenic': '高度懷疑致病', 'pathogenic': '致病',
                        'likely pathogenic, low penetrance': '高度懷疑致病, 低外顯率', 'pathogenic, low penetrance':'致病, 低外顯率', 
                        'not provided':'未提供', 'other':'其他', 'risk factor':'風險因子', 
                        'uncertain risk allele':'不確定的風險等位基因', 'likely risk allele':'可能的風險等位基因', 
                        'established risk allele':'已知的風險等位基因', 'drug response':'影響藥物反應',
                        'association':'可推論', 'protective':'保護因子','affects':'非疾病性影響'}

    if ClinVar_record in cinvar_cls_zhtw.keys():
        return f'『{cinvar_cls_zhtw[ClinVar_record.lower()]}』（{ClinVar_record}）'
    elif ClinVar_record == 'conflicting':
        return f'『致病性判讀有衝突』（{ClinVar_record}）'
    elif ClinVar_record == 'conflicting plp':
        return f'『致病性判讀有衝突』（{ClinVar_record}）（有些紀錄為「致病（pathogenic）」或「高度懷疑致病（likely pathogenic）」）'
    else:
        return f'『{ClinVar_record}』'

def vep_consequence_translate(consequences):
    vep_conseqeunce_dict = {'transcript_ablation':'轉錄消融', 'splice_acceptor_variant':'剪接受體', 'splice_donor_variant':'剪接供體', 
                            'stop_gained':'終止密碼子提前', 'stop_lost':'終止密碼子丟失', 'start_lost':'起始密碼子丟失', 
                            'frameshift_variant':'框移', 'transcript_amplification':'轉錄擴增','feature_elongation':'特徵延伸', 
                            'feature_truncation':'特徵截斷', 'inframe_insertion':'框內插入', 'inframe_deletion':'框內的缺失', 'missense_variant':'錯義', 
                            'protein_altering_variant':'蛋白質改變', 'splice_donor_5th_base_variant':'剪接供體第五鹼基對',
                            'splice_region_variant':'剪接區域', 'splice_donor_region_variant':'剪接供體區域', 
                            'splice_polypyrimidine_tract_variant':'剪接聚嘧啶束區域',
                            'incomplete_terminal_codon_variant':'未完全註釋的轉錄本之最終密碼子', 'start_retained_variant':'起始密碼子保留', 
                            'stop_retained_variant':'終止密碼子保留',
                            'synonymous_variant':'同義', 'coding_sequence_variant':'編碼序列', 'mature_miRNA_variant':'成熟小分子核糖核酸',
                            '5_prime_UTR_variant':'五端非轉譯區', '3_prime_UTR_variant':'三端非轉譯區', 
                            'non_coding_transcript_exon_variant':'非編碼轉錄本外顯子', 'non_coding_transcript_variant':'非編碼轉錄本',
                            'intron_variant':'內含子', 'NMD_transcript_variant':'無義介導mRNA降解轉錄本', 
                            'coding_transcript_variant':'編碼轉錄本', 'upstream_gene_variant':'上游基因', 'downstream_gene_variant':'下游基因', 
                            'TFBS_ablation':'轉錄因子結合位消融', 'TFBS_amplification':'轉錄因子結合位擴增', 'TF_binding_site_variant':'轉錄因子結合位', 
                            'regulatory_region_ablation':'調控區域消融', 'regulatory_region_amplification':'調控區域擴增', 'regulatory_region_variant':'調控區域',
                            'intergenic_variant':'基因間', 'sequence_variant':'序列'}
    consequences_ls = [cons.strip() for cons in consequences.split(',')]
    consequence_out_ls = [' '.join(cons.split('_')[:-1]) if cons.split('_')[-1] == 'variant' else ' '.join(cons.split('_')) for cons in consequences_ls]
    consequence_out_zhtw = [vep_conseqeunce_dict[cons[0]]+f"（{cons[1]}）" if cons[0] in vep_conseqeunce_dict.keys() else cons[1] for cons in zip(consequences_ls, consequence_out_ls)]
    return consequence_out_zhtw, consequence_out_ls