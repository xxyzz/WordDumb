#!/usr/bin/env python3

import json
import random
import re
import string


def check_metadata(db, book_id, languages):
    mi = db.get_metadata(book_id, get_cover=True)

    book_language = mi.get("languages")
    if not book_language:
        return None
    book_language = book_language[0]
    if book_language not in languages:
        return None

    book_fmts = db.formats(book_id)
    chosen_fmt = None
    supported_fmts = ['KFX', 'AZW3', 'AZW', 'MOBI']
    if (fmts := [f for f in supported_fmts if f in book_fmts]):
        chosen_fmt = fmts[0]
    else:
        return None

    return (book_id, chosen_fmt, db.format_abspath(book_id, chosen_fmt),
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


def get_asin_etc(book_path, is_kfx, mi, library_asin=None):
    revision = ''
    kfx_json = None
    mobi_html = None
    mobi_codec = ''
    update_asin = False

    if is_kfx:
        from calibre_plugins.kfx_input.kfxlib import YJ_Book, YJ_Metadata

        yj_book = YJ_Book(book_path)
        yj_md = yj_book.get_metadata()
        asin = getattr(yj_md, 'asin', None)
        acr = getattr(yj_md, 'asset_id', '')
        if library_asin is None:
            asin, update_asin = validate_asin(asin, mi)
        elif library_asin != asin:
            update_asin = True
        if update_asin:
            yj_book = YJ_Book(book_path)
            yj_md = YJ_Metadata()
            yj_md.asin = library_asin if library_asin else asin
            yj_md.content_type = "EBOK"
            yj_book.decode_book(set_metadata=yj_md)
            with open(book_path, 'wb') as f:
                f.write(yj_book.convert_to_single_kfx())
        if library_asin is None:
            kfx_json = json.loads(yj_book.convert_to_json_content())['data']
    else:
        from calibre.ebooks.metadata.mobi import MetadataUpdater

        with open(book_path, 'r+b') as f:
            acr = f.read(32).rstrip(b'\x00').decode('utf-8')  # Palm db name
            revision = get_mobi_revision(f)
            f.seek(0)
            mu = MetadataUpdater(f)
            mobi_codec = mu.codec
            if (asin := mu.original_exth_records.get(113)) is None:
                asin = mu.original_exth_records.get(504)
            asin = asin.decode(mu.codec) if asin else None
            if library_asin is None:
                asin, update_asin = validate_asin(asin, mi)
            elif library_asin != asin:
                update_asin = True
            if update_asin:
                mu.update(mi, asin=asin)
        if library_asin is None:
            mobi_html = extract_mobi(book_path)

    return asin, acr, revision, update_asin, kfx_json, mobi_html, mobi_codec


def get_mobi_revision(f):
    # modified from calibre.ebooks.mobi.reader.headers:MetadataHeader.header
    f.seek(78)
    f.seek(int.from_bytes(f.read(4), 'big') + 32)
    return f.read(4).hex()  # Unique-ID MOBI header


def extract_mobi(book_path):
    # use code from calibre.ebooks.mobi.reader.mobi8:Mobi8Reader.__call__
    # and calibre.ebook.conversion.plugins.mobi_input:MOBIInput.convert
    # https://github.com/kevinhendricks/KindleUnpack/blob/master/lib/mobi_k8proc.py#L216
    from calibre.ebooks.mobi.reader.mobi6 import MobiReader
    from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader

    with open(book_path, 'rb') as f:
        mr = MobiReader(f)
        if mr.kf8_type == 'joint':
            raise Exception('JointMOBI')
        mr.check_for_drm()
        mr.extract_text()
        html = mr.mobi_html
        if mr.kf8_type == 'standalone':
            m8r = Mobi8Reader(mr, mr.log)
            m8r.kf8_sections = mr.sections
            m8r.read_indices()
            m8r.build_parts()
            html = b''.join(m8r.parts)  # KindleUnpack
        return html
