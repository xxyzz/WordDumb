#!/usr/bin/env bash

# install packages
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python download_wordnet.py
deactivate
