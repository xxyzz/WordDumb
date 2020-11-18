#!/usr/bin/env python3
import json
import re

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.database import (connect_ww_database,
                                               create_lang_layer, match_lemma)


def do_job(gui, books, abort, log, notifications):
    ww_conn, ww_cur = connect_ww_database()

    for (book_id, book_fmt, asin, book_path, _) in books:
        ll_conn, ll_cur, ll_file = create_lang_layer(asin, book_path)
        if ll_conn is None:
            continue

        for (start, word) in parse_book(book_path, book_fmt):
            match_lemma(start, word, ll_cur, ww_cur)

        ll_conn.commit()
        ll_conn.close()

    ww_conn.close()


def parse_book(path_of_book, book_fmt):
    if (book_fmt.lower() == 'kfx'):
        return parse_kfx(path_of_book)
    else:
        return parse_mobi(path_of_book, book_fmt)


def parse_kfx(path_of_book):
    from calibre_plugins.kfx_input.kfxlib import YJ_Book

    book = YJ_Book(path_of_book)
    data = book.convert_to_json_content()
    for entry in json.loads(data)['data']:
        for match_word in re.finditer('[a-zA-Z]+', entry['content']):
            word = entry['content'][match_word.start():match_word.end()]
            yield (entry['position'] + match_word.start(), word)


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
        text = html[match_text.start():match_text.end()]
        # match each word inside text
        for match_word in re.finditer(b"[a-zA-Z]+", text):
            word = text[match_word.start():match_word.end()]
            start = match_text.start() + match_word.start()
            yield (start, word.decode('utf-8'))
