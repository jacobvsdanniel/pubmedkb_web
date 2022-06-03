# pubmedKB web

**Data access API and web server for [pubmedKB](https://github.com/jacobvsdanniel/pubmedkb_core)**

Authors:
- Peng-Hsuan Li (jacobvsdanniel [at] gmail.com)

![NEN](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_nen.png)
![REL](https://github.com/jacobvsdanniel/pubmedkb_web/blob/main/image_dir/web_rel.png)

## Introduction

This is a standalone, lightweight web server for pubmedKB, a knowledge base created from annotations of PubMed.

See [pubmedkb_core](https://github.com/jacobvsdanniel/pubmedkb_core) for the core annotators behind the knowledge base. Or see our paper:

*Peng-Hsuan Li, Ting-Fu Chen, Jheng-Ying Yu, Shang-Hung Shih, Chan-Hung Su, Yin-Hung Lin, Huai-Kuang Tsai, Hsueh-Fen Juan, Chien-Yu Chen and Jia-Hsin Huang, **pubmedKB: an interactive web server to explore biomedical entity relations from biomedical literature**, Nucleic Acids Research, 2022, [https://doi.org/10.1093/nar/gkac310](https://doi.org/10.1093/nar/gkac310)*

Functions
- NEN
  - Look up similar names to query input
  - Also return IDs and aliases for each name
- REL
  - Look up relations and evidence sentences for entity or entity pair
  - Specify an entity by name and/or ID

Requirements
  - Disk: 2GB (for the 1/10 dataset)
  - Memory: 6GB (for the 1/10 dataset)
  - CPU: 1 thread

Dependencies
  - OS-independent
  - python3
  - Flask (a python package)

## How to Run

Download dataset
- https://drive.google.com/file/d/1OET8rVc08ccAS8zByK8iB5CP5T4zb7jc/view?usp=sharing
- 322 MB zip file
- A 1/10 sample of all data
- Unzip to *./kb_1g_data*

Start server
```bash
python server.py
```

Connect to server
- Open browser and connect to *[server_ip]:12345*
- Or, if on the same machine, connect to *localhost:12345*
