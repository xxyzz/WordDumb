#!/usr/bin/env python3

import uuid

class ParseBook():
    def __init__(self, gui):
        self.gui = gui

    def parse(self):
        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        ids = list(map(self.gui.library_view.model().id, rows))
        db = self.gui.current_db.new_api
        for book_id in ids:
            # Get the current metadata for this book from the db
            mi = db.get_metadata(book_id)
            fmts = db.formats(book_id)
            book_fmt = None

            # check book format
            has_kindle_format = False
            for fmt in fmts:
                if fmt.lower() in ['mobi', 'azw', 'azw3', 'kfx-zip']:
                    has_kindle_format = True
                    book_fmt = fmt
                    break
            if not has_kindle_format:
                continue

            # check ASIN
            identifiers = mi.get_identifiers()
            asin = None
            if identifiers and 'mobi-asin' in identifiers:
                asin = identifiers['mobi-asin']
            else:
                # create a stupid fake ASIN
                asin = str(uuid.uuid4())
                mi.set_identifier('mobi-asin', asin)
                db.set_metadata(book_id, mi)
