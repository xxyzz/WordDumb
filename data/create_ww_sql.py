#!/usr/bin/env python3

# https://docs.python.org/3/library/argparse.html
import argparse
# https://docs.python.org/3/library/pathlib.html
from pathlib import Path
# https://docs.python.org/3/library/sqlite3.html
import sqlite3

'''
Build a word wise sql file from LanguageLayer.en.ASIN.kll files
and WordWise.kll.en.en.db file. Get 'difficulty' from
LanguageLayer.en.ASIN.kll, get 'lemma' and 'sense_id' from
WordWise.kll.en.en.db.
'''

dump_filename = "wordwise.sql"
parser = argparse.ArgumentParser()
parser.add_argument("word_wise", help="path of WordWise.kll.en.X.db file.")
parser.add_argument("language_layers", nargs='+',
                    help="path of LanguageLayer.en.ASIN.kll files.")
parser.add_argument("-v", "--verbose", help="verbose output", action="store_true")
args = parser.parse_args()

if not Path(args.word_wise).is_file():
    raise Exception(dump_filename)
ww_kll_conn = sqlite3.connect(args.word_wise)
ww_kll_cur = ww_kll_conn.cursor()
ww_conn = sqlite3.connect(":memory:")
ww_cur = ww_conn.cursor()
total_words = 0
ww_kll_cur.execute("SELECT COUNT(*) FROM lemmas")
ww_kll_words = ww_kll_cur.fetchone()[0]

if Path(dump_filename).is_file():
    with open(dump_filename) as f:
        ww_cur.executescript(f.read())
    ww_cur.execute("SELECT COUNT(*) FROM words")
    total_words = ww_cur.fetchone()
    if total_words:
        total_words = total_words[0]
else:
    ww_cur.execute(
        "CREATE TABLE words (lemma TEXT, sense_id INTEGER, difficulty INTEGER)")

for language_layer in args.language_layers:
    if not Path(language_layer).is_file():
        continue
    ll_conn = sqlite3.connect(language_layer)
    ll_cur = ll_conn.cursor()

    print ("Processing {}".format(Path(language_layer).name))
    for lemma, sense_id in ww_kll_cur.execute('''
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
            total_words += 1

print ("WordWise.kll.en.db has {} words".format(ww_kll_words))
print ("Processed words: {}".format(total_words))
Path(dump_filename).unlink(missing_ok=True)
ww_conn.commit()
with open(dump_filename, "w") as f:
    for line in ww_conn.iterdump():
        f.write("%s\n" % line)
ww_conn.close()
