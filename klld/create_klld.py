#!/usr/bin/env python3

import argparse
import base64
import sqlite3
from collections import defaultdict
from pathlib import Path

from parse_es import parse_es_dict
from parse_ja import parse_ja_dict

DICT_TITLES = {
    'de': 'Oxford English-German',
    'es': 'Oxford English-Spanish',
    'fr': 'Oxford English-French',
    'it': 'Oxford English-Italian',
    'ja': 'Progressive English-Japanese'
}


def encode_def(full_def, short_def, example):
    return (base64.b64encode(full_def.encode('utf-8')).decode('utf-8'),
            base64.b64encode(short_def.encode('utf-8')).decode('utf-8'),
            base64.b64encode(
                example.encode('utf-8')).decode('utf-8') if example else None)


def break_examples(def_tuple, lang):
    full_def, short_def = def_tuple
    example_symbol = '¶' if lang == 'ja' else '•'
    example = None
    if example_symbol in full_def:
        full_def, example = full_def.split(example_symbol, maxsplit=1)
        example = example.split(example_symbol, maxsplit=1)[0]
    return encode_def(full_def, short_def, example)


parser = argparse.ArgumentParser()
parser.add_argument("en_klld", help="path of kll.en.en.klld file.")
parser.add_argument("dict_rawml", help="path of dictionary rawml file.")
parser.add_argument("lang", choices=DICT_TITLES.keys(),
                    help="dictionary language.")
args = parser.parse_args()

klld_conn = sqlite3.connect(args.en_klld)
en_klld = defaultdict(list)
for lemma, sense_id in klld_conn.execute(
        '''
        SELECT lemmas.lemma, senses.id FROM lemmas JOIN senses
        ON lemmas.id = senses.display_lemma_id
        WHERE short_def IS NOT NULL
        '''):
    en_klld[lemma].append(sense_id)

dic = defaultdict(list)
if args.lang == 'ja':
    parse_ja_dict(args.dict_rawml, dic, en_klld)
else:
    parse_es_dict(args.dict_rawml, dic, en_klld)

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
    for sense_id, def_tuple in zip(sense_ids, dic[lemma]):
        conn.execute(
            'UPDATE senses SET source_id = 3, full_def = ?, short_def = ?,'
            'example_sentence = ? WHERE id = ?',
            break_examples(def_tuple, args.lang) + (sense_id,))
        replace_count += 1

conn.commit()
new_klld = Path(f'kll.en.{args.lang}.klld')
new_klld.unlink(missing_ok=True)
new_klld.touch()
new_klld_conn = sqlite3.connect(new_klld)
with new_klld_conn:
    conn.backup(new_klld_conn)
new_klld_conn.close()
print(f'Replaced {replace_count} sences')
