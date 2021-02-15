#!/usr/bin/env python3

import argparse
import sqlite3
from pathlib import Path

import redis

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
total_lemmas = 0
ww_klld_lemmas = 0
for count, in ww_klld_conn.execute("SELECT COUNT(*) FROM lemmas"):
    ww_klld_lemmas = count

r = redis.Redis()
origin_lemmas = r.dbsize()

for language_layer in args.language_layers:
    if not Path(language_layer).is_file():
        continue
    ll_conn = sqlite3.connect(language_layer)
    ll_cur = ll_conn.cursor()

    print("Processing {}".format(Path(language_layer).name))
    for lemma, sense_id in ww_klld_conn.execute('''
    SELECT l.lemma, s.id FROM senses s JOIN lemmas l
    ON (s.term_lemma_id = l.id)
    '''):
        ll_cur.execute(
            "SELECT difficulty FROM glosses WHERE sense_id = ?", (sense_id, ))
        difficulty = ll_cur.fetchone()
        if difficulty:
            key = 'lemma:' + lemma
            pipe = r.pipeline()
            pipe.hsetnx(key, 'sense_id', sense_id)
            pipe.hsetnx(key, 'difficulty', difficulty[0])
            pipe.execute()
            if args.verbose:
                print("Insert {} {} {}".format(lemma, sense_id, difficulty[0]))
    ll_conn.close()

print("cn-kll.en.en.klld has {} lemmas".format(ww_klld_lemmas))
current_lemmas = r.dbsize()
print("added {} lemmas".format(current_lemmas - origin_lemmas))
print("dump.rdb has {} lemmas".format(current_lemmas))
ww_klld_conn.close()
r.shutdown(save=True)
