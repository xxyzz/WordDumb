#!/usr/bin/env python3

import random
import re
import string

from calibre.ebooks.metadata.mobi import MetadataUpdater


def check_metadata(db, book_id, languages):
    # Get the current metadata for this book from the db
    mi = db.get_metadata(book_id, get_cover=True)
    fmts = db.formats(book_id)
    book_fmt = None

    book_language = mi.get("languages")
    if book_language is None or len(book_language) == 0:
        return None

    book_language = book_language[0]
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

    return (book_id, book_fmt, db.format_abspath(book_id, book_fmt),
            mi, languages[book_language])


def random_asin():
    'return an invalid ASIN'
    asin = 'BB'
    asin += ''.join(random.choices(string.ascii_uppercase +
                                   string.digits, k=8))
    return asin


def validate_asin(asin, mi):
    # check ASIN, create a random one if doesn't exist
    update_asin = False
    if asin is None or re.fullmatch('B[0-9A-Z]{9}', asin) is None:
        asin = random_asin()
        mi.set_identifier('mobi-asin', asin)
        update_asin = True
    return asin, update_asin


def get_asin_etc(book_path, is_kfx, mi):
    asin = None
    acr = None
    revision = None
    yj_book = None
    codec = 'utf-8'

    if is_kfx:
        from calibre_plugins.kfx_input.kfxlib import YJ_Book, YJ_Metadata

        yj_book = YJ_Book(book_path)
        yj_md = yj_book.get_metadata()
        asin = getattr(yj_md, 'asin', None)
        acr = getattr(yj_md, 'asset_id', None)
        asin, update_asin = validate_asin(asin, mi)
        if update_asin:
            yj_book = YJ_Book(book_path)
            yj_md = YJ_Metadata()
            yj_md.asin = asin
            yj_md.content_type = "EBOK"
            yj_book.decode_book(set_metadata=yj_md)
            with open(book_path, 'wb') as f:
                f.write(yj_book.convert_to_single_kfx())
    else:
        with open(book_path, 'r+b') as f:
            acr = f.read(32).rstrip(b'\x00').decode('utf-8')  # Palm db name
            revision = get_mobi_revision(f)
            f.seek(0)
            mu = MetadataUpdater(f)
            codec = mu.codec
            if (asin := mu.original_exth_records.get(113)) is None:
                asin = mu.original_exth_records.get(504)
            asin = asin.decode(mu.codec) if asin else None
            asin, update_asin = validate_asin(asin, mi)
            if update_asin:
                mu.update(mi, asin=asin)

    return asin, acr, revision, update_asin, yj_book, codec


def get_mobi_revision(f):
    # modified from calibre.ebooks.mobi.reader.headers:MetadataHeader.header
    f.seek(78)
    f.seek(int.from_bytes(f.read(4), 'big') + 32)
    return f.read(4).hex()  # Unique-ID MOBI header
