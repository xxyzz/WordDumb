#!/usr/bin/env python3

import json
import sqlite3
import timeit

from calibre.library import db
from calibre_plugins.worddumb.database import get_ll_path, get_x_ray_path
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.unzip import install_libs
from calibre_plugins.worddumb.parse_job import do_job  # noqa: F401

db = db('~/Calibre Library').new_api
book_1984_id = 0
for book_id in db.all_book_ids():
    mi = db.get_metadata(book_id)
    if mi.get('title') == '1984':
        book_1984_id = book_id
        break

book = check_metadata(db, book_1984_id)
(_, _, asin, book_path, _) = book
install_libs()
time = timeit.timeit('do_job([book], None, None, None)',
                     number=1, globals=globals())
print(f'{time=} seconds')


def test(test_path, created_path, sql):
    test_file = open(test_path)
    created_db = sqlite3.connect(created_path)

    for a, b in zip(json.load(test_file), created_db.execute(sql)):
        if tuple(a) != b:
            test_file.close()
            created_db.close()
            return (tuple(a), b)

    test_file.close()
    created_db.close()
    return None


raise_exption = False
exception_str = ''

# compare word wise
result = test('LanguageLayer.en.B003JTHWKU.json', get_ll_path(asin, book_path),
              'SELECT start, difficulty, sense_id FROM glosses')
if result is not None:
    raise_exption = True
    (a, b) = result
    exception_str += f'''
        glosses      (start, difficulty, sense_id)
        test    file:{a}
        created file:{b}
        '''

# compare X-Ray
result = test('XRAY.entities.B003JTHWKU.json', get_x_ray_path(asin, book_path),
              'SELECT * FROM occurrence')
if result is not None:
    raise_exption = True
    (a, b) = result
    exception_str += f'''
        occurrence   (entity, start, length)
        test    file:{a}
        created file:{b}
        '''

if raise_exption:
    raise Exception(exception_str)
