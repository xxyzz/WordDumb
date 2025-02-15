import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

"""
Convert sqlite file to json file for testing
"""

parser = argparse.ArgumentParser()
parser.add_argument("-l", help="path of LanguageLayer.en.ASIN.kll file.")
parser.add_argument("-x", help="path of XRAY.entities.ASIN.asc file")
args = parser.parse_args()


def convert(path, table_sql_list):
    db_file = Path(path)
    if not db_file.is_file():
        raise Exception(f"{path} is not a file")

    test_db = sqlite3.connect(db_file)
    dic = defaultdict(list)
    for table, sql in table_sql_list:
        for d in test_db.execute(sql):
            dic[table].append(d)
    test_db.close()

    with open(
        f"{'.'.join(db_file.stem.split('.')[:2])}.{db_file.suffix.split('_')[-1]}.json",
        "w",
        encoding="utf_8",
    ) as f:
        json.dump(dic, f, indent=2, sort_keys=True)


LIMIT = 42
if args.l:
    table_sql_list = [
        (
            "glosses",
            "SELECT start, difficulty, sense_id FROM glosses "
            f"ORDER BY start LIMIT {LIMIT}",
        ),
        ("count", "SELECT count(*) FROM glosses"),
        ("metadata", "SELECT * FROM metadata"),
    ]
    convert(args.l, table_sql_list)
if args.x:
    table_sql_list = [
        ("occurrence", f"SELECT * FROM occurrence ORDER BY start LIMIT {LIMIT}"),
        ("book_metadata", "SELECT * FROM book_metadata"),
        ("type", "SELECT top_mentioned_entities FROM type"),
        ("excerpt", "SELECT * FROM excerpt"),
    ]
    convert(args.x, table_sql_list)
