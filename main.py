#!/usr/bin/env python3

from calibre.gui2 import Dispatcher, warning_dialog, error_dialog
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre_plugins.worddumb.parse_job import do_job
from pathlib import Path
import sqlite3
import uuid
import re

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

        job = ThreadedJob('Generating Word Wise', 'Generating Word Wise',
                          do_job, (self.gui, books), {}, Dispatcher(self.done))

        self.gui.job_manager.run_threaded_job(job)
        self.gui.status_bar.show_message("Generating Word Wise")

    def done(self, job):
        if job.result:
            # Problems during word wise generation
            # jobs.results is a list - the first entry is the intended title for the dialog
            # Subsequent strings are error messages
            dialog_title = job.result.pop(0)
            if re.search('warning', job.result[0].lower()):
                msg = "Word Wise generation complete, with warnings."
                warning_dialog(self.gui, dialog_title, msg, det_msg='\n'.join(job.result), show=True)
            else:
                job.result.append("Word Wise generation terminated.")
                error_dialog(self.gui, dialog_title,'\n'.join(job.result), show=True)
                return
        if job.failed:
            self.gui.job_exception(job)
        self.gui.status_bar.show_message("Word Wise generated.", 3000)
