#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path

"""
Convert sqlite file to json file for testing
"""

parser = argparse.ArgumentParser()
parser.add_argument("-l", help="path of LanguageLayer.en.ASIN.kll file.")
parser.add_argument("-x", help="path of XRAY.entities.ASIN.asc file")
args = parser.parse_args()


def convert(path, table, sql):
    db_file = Path(path)
    if not db_file.is_file():
        raise Exception(f"{path} is not a file")

    test_db = sqlite3.connect(db_file)
    dic = {table: []}
    for d in test_db.execute(sql):
        dic[table].append(d)
    test_db.close()

    with open(
        f'{".".join(db_file.stem.split(".")[:2])}.json', "r+", encoding="utf_8"
    ) as f:
        new_dic = json.load(f)
        new_dic.update(dic)
        f.seek(0)
        f.truncate()
        json.dump(new_dic, f, indent=2, sort_keys=True)


LIMIT = 42
if args.l:
    convert(
        args.l,
        "glosses",
        "SELECT start, difficulty, sense_id FROM glosses "
        f"ORDER BY start LIMIT {LIMIT}",
    )
    convert(args.l, "count", "SELECT count(*) FROM glosses")
    convert(args.l, "metadata", "SELECT * FROM metadata")
if args.x:
    convert(
        args.x, "occurrence", f"SELECT * FROM occurrence ORDER BY start LIMIT {LIMIT}"
    )
    convert(
        args.x, "book_metadata", "SELECT erl, num_people, num_terms FROM book_metadata"
    )
    convert(args.x, "type", "SELECT top_mentioned_entities FROM type")
