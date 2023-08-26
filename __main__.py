#!/usr/bin/env python3

"""
Create X-Ray file on macOS: run this script in subprocess to bypass
the ludicrous library validation
"""

import argparse
import json
import sys
from pathlib import Path

from dump_lemmas import dump_spacy_docs
from parse_job import ParseJobData, create_files

parser = argparse.ArgumentParser()
parser.add_argument("job_data")
parser.add_argument("prefs")
args = parser.parse_args()

job_data = json.loads(args.job_data)
prefs = json.loads(args.prefs)
if "db_path" in job_data:
    dump_spacy_docs(
        job_data["model_name"],
        job_data["is_kindle"],
        job_data["lemma_lang"],
        Path(job_data["db_path"]),
        Path(job_data["plugin_path"]),
        prefs,
    )
else:
    data = ParseJobData(**job_data)
    if data.book_fmt == "KFX":
        data.kfx_json = json.load(sys.stdin)
    elif data.book_fmt != "EPUB":
        data.mobi_html = sys.stdin.buffer.read()

    create_files(data, prefs, None)
