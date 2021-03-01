#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path

'''
Convert sqlite file to json file for testing
'''

parser = argparse.ArgumentParser()
parser.add_argument('-l', help='path of LanguageLayer.en.ASIN.kll file.')
parser.add_argument('-x', help='path of XRAY.entities.ASIN.asc file')
args = parser.parse_args()


def convert(path, sql):
    db_file = Path(path)
    if not db_file.is_file():
        raise Exception(f'{path} is not a file')

    test_db = sqlite3.connect(db_file)
    data = []
    for d in test_db.execute(sql):
        data.append(d)
    test_db.close()

    with open(db_file.stem + '.json', 'w') as f:
        json.dump(data, f, indent=2)


if args.l:
    convert(args.l, 'SELECT start, difficulty, sense_id FROM glosses')
if args.x:
    convert(args.x, 'SELECT * FROM occurrence')
