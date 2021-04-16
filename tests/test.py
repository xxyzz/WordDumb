#!/usr/bin/env python3

import json
import platform
import sqlite3
import sys
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

    def check_db(self, test_json_path, created_db_path, table, sql):
        with open(test_json_path) as test_json, \
                sqlite3.connect(created_db_path) as created_db:
            for a, b in zip_longest(
                    json.load(test_json)[table], created_db.execute(sql)):
                self.assertEqual(tuple(a), b)

    def test_word_wise_glosses(self):
        self.check_db(
            'LanguageLayer.en.json',
            get_ll_path(self.asin, self.book_path),
            'glosses',
            'SELECT start, difficulty, sense_id FROM glosses')

    def test_word_wise_metadata(self):
        self.check_db(
            'LanguageLayer.en.json',
            get_ll_path(self.asin, self.book_path),
            'metadata',
            'SELECT * FROM metadata')

    @unittest.skipIf(platform.system() == 'Darwin',
                     "absurd macOS can't load .so files in numpy")
    def test_x_ray_occurrence(self):
        self.check_db(
            'XRAY.entities.json',
            get_x_ray_path(self.asin, self.book_path),
            'occurrence',
            'SELECT * FROM occurrence')

    @unittest.skipIf(
        platform.system() == 'Darwin',
        "It does e-mail and Web browsing, and it shits in Kyle's mouth??")
    def test_x_ray_book_metadata(self):
        self.check_db(
            'XRAY.entities.json',
            get_x_ray_path(self.asin, self.book_path),
            'book_metadata',
            'SELECT srl, erl, num_people, num_terms FROM book_metadata')

    @unittest.skipIf(
        platform.system() == 'Darwin', "Yes but, can it read?")
    def test_x_ray_type(self):
        self.check_db(
            'XRAY.entities.json',
            get_x_ray_path(self.asin, self.book_path),
            'type',
            'SELECT top_mentioned_entities FROM type')


if __name__ == '__main__':
    r = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestDumbCode))
    sys.exit(0 if r.wasSuccessful() else 1)
