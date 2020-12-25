#!/usr/bin/env python3
import json
import re
import time

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.database import (create_lang_layer, insert_lemma,
                                               start_redis_server)
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.unzip import install_libs, unzip_db


def do_job(db, ids, plugin_path, abort, log, notifications):
    books = []
    for book_id in ids:
        data = check_metadata(db, book_id)
        if data is None:
            continue
        books.append((book_id, ) + data)
    if len(books) == 0:
        return

    install_libs(plugin_path)
    from nltk.corpus import wordnet as wn
    start_redis_server(unzip_db(plugin_path))
    import redis
    while True:
        try:
            r = redis.Redis()
            break
        except ConnectionRefusedError:
            pass

    for (_, book_fmt, asin, book_path, _) in books:
        ll_conn = create_lang_layer(asin, book_path)
        if ll_conn is None:
            continue

        for (start, word) in parse_book(book_path, book_fmt):
            word = wn.morphy(word.lower())
            if word is not None and len(word) >= 3:
                result = r.hgetall('lemma:' + word)
                if result:
                    insert_lemma((start,
                                  result[b'difficulty'].decode('utf-8'),
                                  result[b'sense_id'].decode('utf-8')),
                                 ll_conn)
        ll_conn.commit()
        ll_conn.close()
        r.shutdown()


def parse_book(path_of_book, book_fmt):
    if (book_fmt.lower() == 'kfx'):
        yield from parse_kfx(path_of_book)
    else:
        yield from parse_mobi(path_of_book, book_fmt)


def parse_kfx(path_of_book):
    from calibre_plugins.kfx_input.kfxlib import YJ_Book

    book = YJ_Book(path_of_book)
    data = book.convert_to_json_content()
    for entry in json.loads(data)['data']:
        yield from parse_text(entry['position'],
                              entry['content'].encode('utf-8'))


def parse_mobi(pathtoebook, book_fmt):
    mobiReader = MobiReader(pathtoebook, default_log)
    html = b''
    offset = 1
    # use code from calibre.ebooks.mobi.reader.mobi8:Mobi8Reader.__call__
    if book_fmt.lower() == 'azw3' and mobiReader.kf8_type == 'joint':
        offset = mobiReader.kf8_boundary + 2
    mobiReader.extract_text(offset=offset)
    html = mobiReader.mobi_html
    if book_fmt.lower() == 'azw3':
        m8r = Mobi8Reader(mobiReader, default_log)
        m8r.kf8_sections = mobiReader.sections[offset-1:]
        m8r.read_indices()
        m8r.build_parts()
        html = b''.join(m8r.parts)

    # match text between HTML tags
    for match_text in re.finditer(b">[^<>]+<", html):
        yield from parse_text(match_text.start(), match_text.group(0))


def parse_text(start, text):
    for match_word in re.finditer(b'[a-zA-Z]{3,}', text):
        yield (start + match_word.start(), match_word.group(0).decode('utf-8'))
