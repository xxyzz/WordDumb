#!/usr/bin/env python3

import json
import sqlite3
import sys
import unittest
from itertools import zip_longest

from calibre.constants import ismacos
from calibre.library import db
from calibre_plugins.worddumb.database import get_ll_path, get_x_ray_path
from calibre_plugins.worddumb.metadata import check_metadata, get_asin
from calibre_plugins.worddumb.parse_job import do_job
from convert import LIMIT


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
        (_, cls.fmt, cls.asin, cls.book_path, _, _, _) = data
        create_x = False if ismacos else True
        do_job(data, create_x=create_x)

    def check_db(self, test_json_path, created_db_path, table, sql):
        with open(test_json_path) as test_json, \
                sqlite3.connect(created_db_path) as created_db:
            for a, b in zip_longest(
                    json.load(test_json)[table], created_db.execute(sql)):
                self.assertEqual(tuple(a), b)

    def test_asin(self):
        self.assertEqual(self.asin, get_asin(self.book_path, self.fmt))

    def test_word_wise_glosses(self):
        self.check_db(
            'LanguageLayer.en.json',
            get_ll_path(self.asin, self.book_path),
            'glosses',
            'SELECT start, difficulty, sense_id FROM glosses '
            f'ORDER BY start LIMIT {LIMIT}')

    def test_word_wise_metadata(self):
        self.check_db(
            'LanguageLayer.en.json',
            get_ll_path(self.asin, self.book_path),
            'metadata',
            'SELECT * FROM metadata')

    @unittest.skipIf(ismacos, "absurd macOS can't load .so files in numpy")
    def test_x_ray_occurrence(self):
        self.check_db(
            'XRAY.entities.json',
            get_x_ray_path(self.asin, self.book_path),
            'occurrence',
            f'SELECT * FROM occurrence ORDER BY start LIMIT {LIMIT}')

    @unittest.skipIf(
        ismacos,
        "It does e-mail and Web browsing, and it shits in Kyle's mouth??")
    def test_x_ray_book_metadata(self):
        self.check_db(
            'XRAY.entities.json',
            get_x_ray_path(self.asin, self.book_path),
            'book_metadata',
            'SELECT erl, num_people, num_terms FROM book_metadata')

    @unittest.skipIf(ismacos, "Yes but, can it read?")
    def test_x_ray_top_mentioned(self):
        self.check_db(
            'XRAY.entities.json',
            get_x_ray_path(self.asin, self.book_path),
            'type',
            'SELECT top_mentioned_entities FROM type')


if __name__ == '__main__':
    r = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestDumbCode))
    sys.exit(0 if r.wasSuccessful() else 1)
