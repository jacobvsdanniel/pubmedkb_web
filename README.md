# pubmedKB web

**Data access API and web server for [pubmedKB](https://github.com/jacobvsdanniel/pubmedkb_core)**

Authors:
- Peng-Hsuan Li (jacobvsdanniel [at] gmail.com)

<!-- ![NEN](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_nen.png) -->
<!-- ![REL](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_rel.png) -->
<img src="https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_nen.png" width="400"><img src="https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_rel.png" width="400">

## Introduction

This is a standalone, lightweight web server wrapped around the data access API of *pubmedKB*, a knowledge base created from annotations of PubMed. See [pubmedkb_core](https://github.com/jacobvsdanniel/pubmedkb_core) for the core annotators behind the knowledge base. Or see our paper:

*Peng-Hsuan Li, Ting-Fu Chen, Jheng-Ying Yu, Shang-Hung Shih, Chan-Hung Su, Yin-Hung Lin, Huai-Kuang Tsai, Hsueh-Fen Juan, Chien-Yu Chen and Jia-Hsin Huang, **pubmedKB: an interactive web server to explore biomedical entity relations from biomedical literature**, Nucleic Acids Research, 2022, [https://doi.org/10.1093/nar/gkac310](https://doi.org/10.1093/nar/gkac310)*

Functions
- NEN
  - Look up similar names to query input
  - Also return IDs and aliases for each name
- REL
  - Look up relations and evidence sentences for entity or entity pair
  - Specify an entity by name and/or ID

Requirements (pubmedKB-PTC-disk)
  - Disk: 13GB
  - Memory: 13GB
  - CPU: 1 thread

Dependencies
  - OS-independent
  - python3
  - Flask (a python package)

## Download Datasets

| dataset | zip size | memory-efficient | #papers | paper section | open access |
| :-- | --: | :-: | --: | :-: | :-: |
| [pubmedKB-PTC-memory](https://drive.google.com/file/d/16QvI9bx-A_hXU0MQIyA9ZqUnGsbZTa1L/view?usp=sharing) | 3.1 GB | X | 10.8 M | abstract | X |
| [pubmedKB-PTC-disk](https://drive.google.com/file/d/10IBsTREtvZQBiaWXEWKPKYfwFBkv7c64/view?usp=sharing) | 3.4 GB | O | 10.8 M | abstract | X |
| [pubmedKB-PTC-disk-small](https://drive.google.com/file/d/1EnrnGBkbrInu58bkoe9vSn-oRARWtbX0/view?usp=sharing) | 605 MB | O | 2.0 M | abstract | O |
| [pubmedKB-PTC-FT-disk](https://drive.google.com/file/d/1a-6Vg1SINpZsA4PXsiAnRwZvvJMe0nti/view?usp=sharing) | 3.7 GB | O | 1.7 M | full text | X |
| [pubmedKB-PTC-FT-disk-small](https://drive.google.com/file/d/13Y5JWWAhbWRY5IiUu2D9b0JO31OjxECj/view?usp=sharing) | 781 MB | O | 336 K | full text | O |
| [pubmedKB-BERN-disk](https://drive.google.com/file/d/1lzQg-Ng4E5M-o4pjy3WVS9aH-JDYaB2p/view?usp=sharing) | 1.6 GB | O | 4.3 M | abstract | X |
| [pubmedKB-BERN-disk-small](https://drive.google.com/file/d/1-kgaI-wK12CWGhgMnPtuARDzOu5tbWT8/view?usp=sharing) | 336 MB | O | 884 K | abstract | O |



## Programmable API

- [slides](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/pubmedKB_api.pdf)
- [wiki](https://github.com/jacobvsdanniel/pubmedkb_web/wiki)
- [demo.py](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/demo.py)

## Host the Web

#### Start server
```bash
python server.py -host [host_ip] -port [host_port] --kb_dir [unzipped_dataset_folder] --kb_type [disk/memory]
```

#### Connect to server

Open browser and connect to *[host_ip]:[host_port]*

