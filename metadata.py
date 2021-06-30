#!/usr/bin/env python3

import random
import re
import string

from calibre.ebooks.metadata.mobi import MetadataUpdater
from calibre_plugins.worddumb.unzip import load_json


def check_metadata(db, book_id):
    # Get the current metadata for this book from the db
    mi = db.get_metadata(book_id, get_cover=True)
    fmts = db.formats(book_id)
    book_fmt = None
    asin = None

    # check book language is English
    book_language = mi.format_field("languages")
    if book_language is None or len(book_language) < 2:
        return None
    languages = load_json('data/languages.json')
    book_language = book_language[1]
    if book_language not in languages:
        return None

    # check book format
    if 'KFX' in fmts:
        book_fmt = 'KFX'
    elif 'AZW3' in fmts:
        book_fmt = 'AZW3'
    elif 'MOBI' in fmts:
        book_fmt = 'MOBI'
    else:
        return None

    # check ASIN, create a random one if doesn't exist
    book_path = db.format_abspath(book_id, book_fmt)
    asin = get_asin(book_path, book_fmt)
    if asin is None or re.fullmatch('B[0-9A-Z]{9}', asin) is None:
        asin = random_asin()
        mi.set_identifier('mobi-asin', asin)
        db.set_metadata(book_id, mi)
        if book_fmt == 'KFX':
            set_kfx_asin(book_path, asin)
        else:
            with open(book_path, 'r+b') as f:
                mu = MetadataUpdater(f)
                mu.update(mi, asin=asin)

    return book_id, book_fmt, asin, book_path, mi, languages[book_language]


def random_asin():
    'return an invalid ASIN'
    asin = 'BB'
    asin += ''.join(random.choices(string.ascii_uppercase +
                                   string.digits, k=8))
    return asin


def get_asin(book_path, book_fmt):
    if book_fmt == 'KFX':
        from calibre_plugins.kfx_input.kfxlib import YJ_Book

        return getattr(YJ_Book(book_path).get_metadata(), 'asin', None)
    else:
        with open(book_path, 'rb') as f:
            mu = MetadataUpdater(f)
            if (asin := mu.original_exth_records.get(113)) is None:
                asin = mu.original_exth_records.get(504)
            return asin.decode('utf-8') if asin else None
    return None


def get_acr(book_path, book_fmt):
    if book_fmt == 'KFX':
        from calibre_plugins.kfx_input.kfxlib import YJ_Book

        return getattr(YJ_Book(book_path).get_metadata(), 'asset_id', None)
    else:
        with open(book_path, 'rb') as f:
            return f.read(32).rstrip(b'\x00').decode('utf-8')  # Palm db name


def get_book_revision(book_path, book_fmt):
    if book_fmt == 'KFX':
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
