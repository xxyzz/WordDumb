#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path

'''
Build a word wise sql file from LanguageLayer.en.ASIN.kll files
and cn-kll.en.en.klld file. Get 'difficulty' from
LanguageLayer.en.ASIN.kll, get 'lemma' and 'sense_id' from
cn-kll.en.en.klld.
'''

parser = argparse.ArgumentParser()
parser.add_argument("word_wise", help="path of cn-kll.en.en.klld file.")
parser.add_argument("language_layers", nargs='+',
                    help="path of LanguageLayer.en.ASIN.kll files.")
parser.add_argument("-v", "--verbose",
                    help="verbose output", action="store_true")
args = parser.parse_args()

if not Path(args.word_wise).is_file():
    raise Exception(args.word_wise)
ww_klld_conn = sqlite3.connect(args.word_wise)
ww_klld_lemmas = 0
for count, in ww_klld_conn.execute("SELECT COUNT(*) FROM lemmas"):
    ww_klld_lemmas = count

lemmas = {}
with open('lemmas.json') as f:
    lemmas = json.load(f)
origin_count = len(lemmas)

for language_layer in args.language_layers:
    if not Path(language_layer).is_file():
        continue
    ll_conn = sqlite3.connect(language_layer)
    ll_cur = ll_conn.cursor()

    print(f'Processing {Path(language_layer).name}')
    for lemma, sense_id in ww_klld_conn.execute('''
    SELECT l.lemma, s.id FROM senses s JOIN lemmas l
    ON (s.term_lemma_id = l.id)
    '''):
        if lemma in lemmas:
            continue
        ll_cur.execute(
            "SELECT difficulty FROM glosses WHERE sense_id = ?", (sense_id, ))
        if (difficulty := ll_cur.fetchone()):
            lemmas[lemma] = [difficulty[0], sense_id]
            if args.verbose:
                print(f'Insert {lemma} {difficulty[0]} {sense_id}')
    ll_conn.close()

current_count = len(lemmas)
print(f"cn-kll.en.en.klld has {ww_klld_lemmas} lemmas")
print(f"added {current_count - origin_count} lemmas")
print(f"lemmas.json has {current_count} lemmas")
ww_klld_conn.close()
with open('lemmas.json', 'w') as f:
    json.dump(lemmas, f, indent=2)
