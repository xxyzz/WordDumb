#!/usr/bin/env python3

from pathlib import Path
import sqlite3
import uuid

class ParseBook():
    def __init__(self, gui):
        self.gui = gui
        self.db = self.gui.current_db.new_api

    def check_metadata(self, book_id):
        # Get the current metadata for this book from the db
        mi = self.db.get_metadata(book_id)
        fmts = self.db.formats(book_id)
        book_fmt = None
        asin = None

        # check book language is English
        book_language = mi.format_field("languages")
        if book_language is None or book_language[1] != "eng":
            return None, None

        # check book format
        has_kindle_format = False
        for fmt in fmts:
            if fmt.lower() in ['mobi', 'azw', 'azw3', 'kfx-zip']:
                has_kindle_format = True
                book_fmt = fmt
                break
        if not has_kindle_format:
            return None, None

        # check ASIN
        identifiers = mi.get_identifiers()
        if identifiers and 'mobi-asin' in identifiers:
            asin = identifiers['mobi-asin']
        else:
            # create a stupid fake ASIN
            asin = str(uuid.uuid4())
            mi.set_identifier('mobi-asin', asin)
            self.db.set_metadata(book_id, mi)

        return book_fmt, asin

    def create_lang_layer(self, book_id, book_fmt, asin):
        # check LanguageLayer file
        book_path = self.db.format_abspath(book_id, book_fmt)
        lang_layer_path = Path(book_path).parent
        folder_name = Path(book_path).stem + ".sdr"
        lang_layer_path = lang_layer_path.joinpath(folder_name)
        lang_layer_name = "LanguageLayer.en.{}.kll".format(asin)
        lang_layer_path = lang_layer_path.joinpath(lang_layer_name)
        if lang_layer_path.is_file():
            return None, None

        # create LanguageLayer database file
        lang_layer_path.parent.mkdir(exist_ok=True)
        lang_layer_path.touch()
        ll_conn = sqlite3.connect(lang_layer_path)
        ll_cur = ll_conn.cursor()
        ll_cur.executescript('''
            CREATE TABLE metadata (
                acr TEXT,
                targetLanguages TEXT,
                sidecarRevision INTEGER,
                bookRevision TEXT,
                sourceLanguage TEXT,
                enDictionaryVersion TEXT,
                enDictionaryRevision INTEGER,
                enDictionaryId TEXT,
                sidecarFormat REAL
            );

            CREATE TABLE glosses (
                start INTEGER,
                end INTEGER,
                difficulty INTEGER,
                sense_id INTEGER,
                low_confidence INTEGER
            );

            INSERT INTO metadata(
                targetLanguages,
                sidecarRevision,
                sourceLanguage,
                enDictionaryVersion,
                enDictionaryRevision,
                enDictionaryId,
                sidecarFormat)
            VALUES (
                'en',
                9,
                'en',
                '2016-09-14',
                57,
                'kll.en.en',
                1.0
            );
        ''')

        return ll_conn, ll_cur

    def parse(self):
        # get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        ids = list(map(self.gui.library_view.model().id, rows))

        for book_id in ids:
            book_fmt, asin = self.check_metadata(book_id)
            if book_fmt is None:
                continue

            ll_conn, ll_cur = self.create_lang_layer(book_id, book_fmt, asin)
            if ll_conn is None:
                continue

            # parse book

            ll_conn.commit()
            ll_conn.close()
