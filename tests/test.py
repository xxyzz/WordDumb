#!/usr/bin/env python3

import json
import platform
import sqlite3
import time
import unittest
from itertools import zip_longest

from calibre.library import db
from calibre_plugins.worddumb.database import get_ll_path, get_x_ray_path
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.parse_job import do_job
from calibre_plugins.worddumb.unzip import install_libs, load_json


class TestDumbCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lib_db = db('~/Calibre Library').new_api
        book_1984_id = 0
        for book_id in lib_db.all_book_ids():
            mi = lib_db.get_metadata(book_id)
            if mi.get('title') == '1984':
                book_1984_id = book_id
                break

        data = check_metadata(lib_db, book_1984_id)
        (_, _, cls.asin, cls.book_path, _) = data
        install_libs()
        start_time = time.time()
        do_job(data, load_json('data/lemmas.json'))
        print(f'{time.time() - start_time} seconds')

    def check_db(self, test_json_path, created_db_path, sql):
        with open(test_json_path) as test_json, \
                sqlite3.connect(created_db_path) as created_db:
            for a, b in zip_longest(
                    json.load(test_json), created_db.execute(sql)):
                self.assertEqual(tuple(a), b)

    def test_word_wise(self):
        self.check_db(
            'LanguageLayer.en.B003JTHWKU.json',
            get_ll_path(self.asin, self.book_path),
            'SELECT start, difficulty, sense_id FROM glosses')

    @unittest.skipIf(platform.system() == 'Darwin',
                     "absurd macOS can't load .so files in numpy")
    def test_x_ray(self):
        self.check_db(
            'XRAY.entities.B003JTHWKU.json',
            get_x_ray_path(self.asin, self.book_path),
            'SELECT * FROM occurrence')


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestDumbCode))
