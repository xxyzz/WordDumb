#!/usr/bin/env python3

# https://docs.python.org/3/library/argparse.html
import argparse
# https://docs.python.org/3/library/sqlite3.html
import sqlite3
# https://docs.python.org/3/library/pathlib.html
from pathlib import Path

'''
Build a word wise sql file from LanguageLayer.en.ASIN.kll files
and cn-kll.en.en.klld file. Get 'difficulty' from
LanguageLayer.en.ASIN.kll, get 'lemma' and 'sense_id' from
cn-kll.en.en.klld.
'''

dump_file = Path("wordwise.sql")
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
ww_conn = sqlite3.connect(":memory:")
ww_cur = ww_conn.cursor()
total_lemmas = 0
ww_klld_lemmas = 0
for count, in ww_klld_conn.execute("SELECT COUNT(*) FROM lemmas"):
    ww_klld_lemmas = count

if dump_file.is_file():
    with dump_file.open() as f:
        ww_conn.executescript(f.read())
    for count, in ww_conn.execute("SELECT COUNT(*) FROM words"):
        total_lemmas = count
else:
    ww_cur.execute('''
    CREATE TABLE words (lemma TEXT, sense_id INTEGER, difficulty INTEGER)
    ''')

added_lemmas = 0
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
        ww_cur.execute("SELECT * FROM words WHERE sense_id = ?", (sense_id, ))
        find_in_ww = ww_cur.fetchone()

        if difficulty and not find_in_ww:
            if args.verbose:
                print("Insert {} {} {}".format(lemma, sense_id, difficulty[0]))
            ww_cur.execute("INSERT INTO words VALUES (?, ?, ?)",
                           (lemma, sense_id, difficulty[0]))
            added_lemmas += 1
    ll_conn.close()

print("cn-kll.en.en.klld has {} lemmas".format(ww_klld_lemmas))
print("Total processed lemmas: {}".format(total_lemmas + added_lemmas))
if added_lemmas > 0:
    print('Added lemmas: {}'.format(added_lemmas))
    dump_file.unlink(missing_ok=True)
    ww_conn.commit()
    with dump_file.open('w') as f:
        for line in ww_conn.iterdump():
            f.write("%s\n" % line)
ww_conn.close()
ww_klld_conn.close()
