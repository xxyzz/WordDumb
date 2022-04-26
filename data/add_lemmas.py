#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path

"""
Build a word wise sql file from LanguageLayer.en.ASIN.kll files
and kll.en.en.klld file. Get 'difficulty' from
LanguageLayer.en.ASIN.kll, get 'lemma' and 'sense_id' from
kll.en.en.klld.
"""

parser = argparse.ArgumentParser()
parser.add_argument("word_wise", help="path of kll.en.en.klld file.")
parser.add_argument(
    "language_layers", nargs="+", help="path of LanguageLayer.en.ASIN.kll files."
)
args = parser.parse_args()

if not Path(args.word_wise).is_file():
    raise Exception(args.word_wise)
ww_klld_conn = sqlite3.connect(args.word_wise)
ww_klld_lemmas = 0
for (count,) in ww_klld_conn.execute("SELECT COUNT(*) FROM lemmas"):
    ww_klld_lemmas = count

lemmas = {}
with open("lemmas.json", encoding="utf-8") as f:
    lemmas = json.load(f)
origin_count = len(lemmas)
updated_count = 0

for language_layer in args.language_layers:
    if not Path(language_layer).is_file():
        continue
    ll_conn = sqlite3.connect(language_layer)

    print(f"Processing {Path(language_layer).name}")
    for difficulty, sense_id in ll_conn.execute(
        "SELECT difficulty, sense_id FROM glosses GROUP by sense_id"
    ):
        for (lemma,) in ww_klld_conn.execute(
            'SELECT lemma FROM senses JOIN lemmas ON display_lemma_id = lemmas.id WHERE senses.id = ? AND length(short_def) > 0 AND lemma NOT LIKE "\'%" AND lemma NOT like "-%"',
            (sense_id,),
        ):
            if lemma.startswith("-"):
                break
            if lemma not in lemmas:
                lemmas[lemma] = [difficulty, sense_id]
            elif lemmas[lemma][0] < difficulty:
                lemmas[lemma] = [difficulty, sense_id]
                updated_count += 1
    ll_conn.close()

current_count = len(lemmas)
print(f"kll.en.en.klld has {ww_klld_lemmas} lemmas")
print(f"added {current_count - origin_count} lemmas")
if updated_count > 0:
    print(f"updated {updated_count} lemmas")
print(f"lemmas.json has {current_count} lemmas")
ww_klld_conn.close()
with open("lemmas.json", "w", encoding="utf-8") as f:
    json.dump(lemmas, f, indent=2, sort_keys=True, ensure_ascii=False)
