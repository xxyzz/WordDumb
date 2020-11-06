#!/usr/bin/env python3

from calibre.gui2 import Dispatcher
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
            return None, None, None

        # check book format
        has_kindle_format = False
        for fmt in fmts:
            if fmt.lower() in ['mobi']:
                has_kindle_format = True
                book_fmt = fmt
                break
        if not has_kindle_format:
            return None, None, None

        # check ASIN
        identifiers = mi.get_identifiers()
        if identifiers and 'mobi-asin' in identifiers:
            asin = identifiers['mobi-asin']
        else:
            # create a stupid fake ASIN
            asin = str(uuid.uuid4())
            mi.set_identifier('mobi-asin', asin)
            self.db.set_metadata(book_id, mi)

        book_path = self.db.format_abspath(book_id, book_fmt)

        return book_fmt, asin, book_path

    def parse(self):
        # get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        ids = list(map(self.gui.library_view.model().id, rows))
        books = []

        for book_id in ids:
            book_fmt, asin, book_path = self.check_metadata(book_id)
            if book_fmt is None:
                continue
            books.append((book_id, book_fmt, asin, book_path))

        if len(books) == 0:
            return

        self.gui.job_manager.run_job(
            Dispatcher(self.done), 'arbitrary',
            args = ("calibre_plugins.worddumb.parse_job", "parse_job", (books, )),
            description = "Generating Word Wise")

    def done(self, job):
        print("Job done.")
