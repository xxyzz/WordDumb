#!/usr/bin/env python3

import random
import re
import string
from io import BytesIO
from struct import pack

from calibre.ebooks.metadata.mobi import MetadataUpdater, MobiError


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

    # check ASIN, create a random one if doesn't exist
    book_path = db.format_abspath(book_id, book_fmt)
    identifiers = mi.get_identifiers()
    if 'mobi-asin' in identifiers and \
       re.fullmatch('B[0-9A-Z]{9}', identifiers['mobi-asin']):
        asin = identifiers['mobi-asin']
    else:
        asin = random_asin()
        mi.set_identifier('mobi-asin', asin)
        db.set_metadata(book_id, mi)
        if fmt.lower() == 'kfx':
            set_kfx_asin(book_path, asin)
        else:
            with open(book_path, 'r+b') as stream:
                mu = UpdateMobiEXTH(stream)
                mu.update(asin)

    return book_fmt, asin, book_path, mi


class UpdateMobiEXTH(MetadataUpdater):
    def update(self, asin):
        def update_exth_record(rec):
            recs.append(rec)
            if rec[0] in self.original_exth_records:
                self.original_exth_records.pop(rec[0])

        if self.type != b"BOOKMOBI":
            raise MobiError("Setting metadata only supported for MOBI"
                            "files of type 'BOOK'.\n"
                            "\tThis is a %r file of type %r"
                            % (self.type[0:4], self.type[4:8]))

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


def random_asin():
    'return an invalid ASIN'
    asin = 'BB'
    asin += ''.join(random.choices(string.ascii_uppercase +
                                   string.digits, k=8))
    return asin


def get_acr(book_path):
    if book_path[-3:] == 'kfx':
        from calibre_plugins.kfx_input.kfxlib import YJ_Book

        book = YJ_Book(book_path)
        book.get_metadata()
        return book.get_asset_id()
    else:
        with open(book_path, 'rb') as f:
            return f.read(32).rstrip(b'\x00').decode('utf-8')  # Palm db name


def get_book_revision(book_path):
    if book_path[-3:] == 'kfx':
        return None

    # modified from calibre.ebooks.mobi.reader.headers:MetadataHeader.header
    with open(book_path, 'rb') as f:
        f.seek(78)
        f.seek(int.from_bytes(f.read(4), 'big') + 32)
        return f.read(4).hex()  # Unique-ID MOBI header


def set_kfx_asin(book_path, asin):
    from calibre_plugins.kfx_input.kfxlib import YJ_Book, YJ_Metadata

    book = YJ_Book(book_path)
    md = YJ_Metadata()
    md.asin = asin
    md.cde_content_type = "EBOK"
    book.decode_book(set_metadata=md)
    updated_book = book.convert_to_single_kfx()

    with open(book_path, 'wb') as f:
        f.write(updated_book)
