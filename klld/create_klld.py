#!/usr/bin/env python3

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path

from parse_ja import parse_ja_dict

DICT_TITLES = {
    'de': 'Oxford English - German',
    'es': 'Oxford English - Spanish',
    'ja': 'Progressive English-Japanese'
}

parser = argparse.ArgumentParser()
parser.add_argument("en_klld", help="path of kll.en.en.klld file.")
parser.add_argument("dict_rawml", help="path of dictionary rawml file.")
parser.add_argument("lang", help="dictionary language: de|es|ja.")
args = parser.parse_args()

dic = defaultdict(list)
if args.lang == 'ja':
    parse_ja_dict(args.dict_rawml, dic)

klld_conn = sqlite3.connect(args.en_klld)
en_klld = defaultdict(list)
for lemma, sense_id in klld_conn.execute(
        '''
        SELECT lemmas.lemma, senses.id FROM lemmas JOIN senses
        ON lemmas.id = senses.display_lemma_id
        WHERE short_def IS NOT NULL
        '''):
    en_klld[lemma].append(sense_id)

conn = sqlite3.connect(':memory:')
klld_conn.backup(conn)
klld_conn.close()
conn.executescript(
    '''
    UPDATE metadata SET value = 'zh' WHERE key = 'definitionLanguage';
    UPDATE metadata SET value = 'kll.en.zh' WHERE key = 'id';
    UPDATE metadata SET value = '2016-04-07' WHERE key = 'version';
    ''')
conn.execute('UPDATE sources SET label = ? WHERE id = 3',
             (DICT_TITLES[args.lang],))
replace_count = 0

for lemma, sense_ids in en_klld.items():
    if lemma not in dic:
        continue
    replace_count += 1
    for sense_id, def_tuple in zip(sense_ids, dic[lemma]):
        conn.execute(
            'UPDATE senses SET source_id = 3, full_def = ?, short_def = ?,'
            'example_sentence = ? WHERE id = ?', def_tuple + (sense_id,))

conn.commit()
new_klld = Path(f'kll.en.{args.lang}.klld')
new_klld.unlink(missing_ok=True)
new_klld.touch()
new_klld_conn = sqlite3.connect(new_klld)
with new_klld_conn:
    conn.backup(new_klld_conn)
new_klld_conn.close()
print(f'Replaced {replace_count} sences')
