#!/usr/bin/env python3

import json
import sqlite3

from calibre.library import db
from calibre_plugins.worddumb.database import get_ll_path
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job

db = db('~/Calibre Library').new_api
book_1984_id = 0
for book_id in db.all_book_ids():
    mi = db.get_metadata(book_id)
    if mi.get('title') == '1984':
        book_1984_id = book_id
        break

do_job(db, [book_1984_id], None, None, None)
(_, asin, book_path, _) = check_metadata(db, book_1984_id, False)

if asin != 'B003JTHWKU':
    print('Wrong ASIN: {}, should be B003JTHWKU.'.format(asin))

ll_path = get_ll_path(asin, book_path)
test_glosses_file = open('LanguageLayer.en.B003JTHWKU.json')
created_db = sqlite3.connect(ll_path)

# compare word wise
for a, b in zip(json.load(test_glosses_file),
                created_db.execute(
                    'SELECT start, difficulty, sense_id FROM glosses')):
    if tuple(a) != b:
        raise Exception(f'''
        glosses row  (start, difficulty, sense_id)
        test    file:{a}
        created file:{b}
        ''')

test_glosses_file.close()
created_db.close()
