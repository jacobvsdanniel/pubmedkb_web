# pubmedKB web

**End-to-end relation extraction for biomedical literature: full datasets, python API, and web GUI**

**The core annotators, pretrained models, and training data can be downloaded at [pubmedKB core](https://github.com/jacobvsdanniel/pubmedkb_core)**

Authors:
- Peng-Hsuan Li @ ailabs.tw (jacobvsdanniel [at] gmail.com)
- Eunice You-Chi Liu @ ailabs.tw (eunicecollege2019 [at] gmail.com)

<!-- ![NEN](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_nen.png) -->
<!-- ![REL](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_rel.png) -->
<img src="https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_nen.png" width="400"><img src="https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_rel.png" width="400">

## Introduction

This repo hosts the full datasets, python API, and web GUI for *pubmedKB*, a knowledge base created from annotations of PubMed. See [pubmedkb_core](https://github.com/jacobvsdanniel/pubmedkb_core) for the core annotators behind the knowledge base. Or see our paper:

*Peng-Hsuan Li, Ting-Fu Chen, Jheng-Ying Yu, Shang-Hung Shih, Chan-Hung Su, Yin-Hung Lin, Huai-Kuang Tsai, Hsueh-Fen Juan, Chien-Yu Chen and Jia-Hsin Huang, **pubmedKB: an interactive web server to explore biomedical entity relations from biomedical literature**, Nucleic Acids Research, 2022, [https://doi.org/10.1093/nar/gkac310](https://doi.org/10.1093/nar/gkac310)*

Functions
- NEN
  - Look up similar names to query input
  - Also return IDs and aliases for each name
- REL
  - Look up relations and evidence sentences for entity or entity pair
  - Specify an entity by name and/or ID

Dependencies
  - OS-independent
  - python3
  - Flask (a python package)

## Datasets

| Support data | content | Disk size (zip size) |
| :-: | :-: | :-: |
| [gene](https://drive.google.com/file/d/1OX629I7fS_mvPbJ_AgQvPUhZ9MX6XWxA/view?usp=share_link) | id, name correspondence | 226 MB (52 MB) |
| [variant](https://drive.google.com/file/d/1Uf74lZHYs4yB3bCmmyv3tjokoTfLAkLi/view?usp=share_link) | id, name, gene correspondence | 133 MB (28 MB) |
| [meta](https://drive.google.com/file/d/17AUaMe0w3xJq3rr0Njs1tok2y3RS5tQ2/view?usp=sharing) | title, author, year, journal, citation, IF | 8.6 GB (1.6 GB) |
| paper | title, abstract, entity | 99 GB (13GB) |

| Relation data | Relations           | # papers with relations* | Section  | Disk size (zip size) | Memory usage |
| :-:                            | :-:                  | :-:     | :-:      | :-:                  | :-:          |
| Full KB    | odds ratio, causal, open relations, etc. | 8.5 M | abstract | 12 GB (2.2 GB) | 15 GB |
| [Partial KB](https://drive.google.com/file/d/14zmuFfNKcTwiSiJPlSUUCwuYJFbq_ouo/view?usp=sharing) | odds ratio, causal, open relations, etc. | 0.3 M | abstract | 487 MB (88 MB) | 10 GB |

*We processed all 35M PubMed citations dumped on 2023/02/17.

## Deprecated Datasets

Checkout the [old version of pubmedkb_web](https://github.com/jacobvsdanniel/pubmedkb_web/tree/2e79a4bbf4258c88dda1ddc7f4e4f3ee37443896) to use these datasets.
```bash
git checkout 2e79a4bbf4258c88dda1ddc7f4e4f3ee37443896
```

| Full dataset | zip size | #papers | section | memory-efficient | open access |
| :-- | --: | --: | :-: | :-: | :-: |
| [pubmedKB-BERN-disk](https://drive.google.com/file/d/1lzQg-Ng4E5M-o4pjy3WVS9aH-JDYaB2p/view?usp=sharing) | 1.6 GB | 4.3 M | abstract | O | O |
| [pubmedKB-PTC-memory](https://drive.google.com/file/d/16QvI9bx-A_hXU0MQIyA9ZqUnGsbZTa1L/view?usp=sharing) | 3.1 GB | 10.8 M | abstract | X | X |
| [pubmedKB-PTC-disk](https://drive.google.com/file/d/10IBsTREtvZQBiaWXEWKPKYfwFBkv7c64/view?usp=sharing) | 3.4 GB | 10.8 M | abstract | O | X |
| [pubmedKB-PTC-FT-disk](https://drive.google.com/file/d/1a-6Vg1SINpZsA4PXsiAnRwZvvJMe0nti/view?usp=sharing) | 3.7 GB | 1.7 M | full text | O | X |

| Partial dataset | zip size | #papers | section | memory-efficient | open access |
| :-- | --: | --: | :-: | :-: | :-: |
| [pubmedKB-BERN-disk-small](https://drive.google.com/file/d/1-kgaI-wK12CWGhgMnPtuARDzOu5tbWT8/view?usp=sharing) | 336 MB | 884 K | abstract | O | O |
| [pubmedKB-PTC-disk-small](https://drive.google.com/file/d/1EnrnGBkbrInu58bkoe9vSn-oRARWtbX0/view?usp=sharing) | 605 MB | 2.0 M | abstract | O | O |
| [pubmedKB-PTC-FT-disk-small](https://drive.google.com/file/d/13Y5JWWAhbWRY5IiUu2D9b0JO31OjxECj/view?usp=sharing) | 781 MB | 336 K | full text | O | O |

## GUI/API server

```bash
python server.py \
--gene_dir [gene_directory] \
--variant_dir [variant_directory] \
--meta_dir [meta_directory] \
--paper_dir [paper_directory] \
--kb_dir [KB_directory] \
--kb_type relation \
--port 8000
```

- Supports both HTTP GET and POST
- Displays results on an HTML webpage or return a JSON file

## GUI/API client

- Open browser and connect to *[server_ip]:[server_port]*
- Also check out [client.py](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/client.py)
