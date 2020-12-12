#!/usr/bin/env python3

import re
from io import BytesIO
from struct import pack

from calibre.ebooks.metadata.mobi import MetadataUpdater, MobiError
from calibre_plugins.worddumb.asin import get_asin


def check_metadata(db, book_id):
    # Get the current metadata for this book from the db
    mi = db.get_metadata(book_id)
    fmts = db.formats(book_id)
    book_fmt = None
    asin = None

    # check book language is English
    book_language = mi.format_field("languages")
    if book_language is None or book_language[1] != "eng":
        return None

    # check book format
    has_kindle_format = False
    for fmt in fmts:
        if fmt.lower() in ['mobi', 'azw3', 'kfx']:
            has_kindle_format = True
            book_fmt = fmt
            break
    if not has_kindle_format:
        return None

    # check ASIN
    book_path = db.format_abspath(book_id, book_fmt)
    identifiers = mi.get_identifiers()
    if 'mobi-asin' in identifiers and \
       re.match('B[0-9A-Z]{9}', identifiers['mobi-asin']):
        asin = identifiers['mobi-asin']
    else:
        asin = get_asin(mi.get('title'))
        mi.set_identifier('mobi-asin', asin)
        db.set_metadata(book_id, mi)
        if fmt.lower() in ['mobi', 'azw3']:
            with open(book_path, 'r+b') as stream:
                mu = UpdateMobiASIN(stream)
                mu.update(mi, asin)

    return book_fmt, asin, book_path, mi


class UpdateMobiASIN(MetadataUpdater):
    def update(self, mi, asin):
        def update_exth_record(rec):
            recs.append(rec)
            if rec[0] in self.original_exth_records:
                self.original_exth_records.pop(rec[0])

        recs = []
        # force update asin
        # https://wiki.mobileread.com/wiki/MOBI#EXTH_Header
        update_exth_record((113, asin.encode(self.codec)))
        update_exth_record((504, asin.encode(self.codec)))

        # Include remaining original EXTH fields
        for id in sorted(self.original_exth_records):
            recs.append((id, self.original_exth_records[id]))
        recs = sorted(recs, key=lambda x: (x[0], x[0]))

        exth = BytesIO()
        for code, data in recs:
            exth.write(pack('>II', code, len(data) + 8))
            exth.write(data)
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = b'\0' * (4 - trail)  # Always pad w/ at least 1 byte
        exth = [b'EXTH', pack('>II', len(exth) + 12, len(recs)), exth, pad]
        exth = b''.join(exth)

        if getattr(self, 'exth', None) is None:
            raise MobiError('No existing EXTH record. Cannot update metadata.')

        self.create_exth(exth=exth)
