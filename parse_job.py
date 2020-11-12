#!/usr/bin/env python3

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.database import connect_ww_database, \
    create_lang_layer, match_word
from pathlib import Path
import re

def do_job(gui, books, abort, log, notifications):
    ww_conn, ww_cur = connect_ww_database()

    for (book_id, book_fmt, asin, book_path, _) in books:
        ll_conn, ll_cur, ll_file = create_lang_layer(asin, book_path)
        if ll_conn is None:
            continue

        for (start, lemma) in parse_book(book_path, book_fmt):
            match_word(start, lemma, ll_cur, ww_cur)

        ll_conn.commit()
        ll_conn.close()

    ww_conn.close()

def parse_book(pathtoebook, book_fmt):
    mobiReader = MobiReader(pathtoebook, default_log)
    html = b''
    offset = 1
    # use code from calibre.ebooks.mobi.reader.mobi8:Mobi8Reader.__call__
    if book_fmt.lower() == 'azw3' and mobiReader.kf8_type == 'joint':
        offset = mobiReader.kf8_boundary + 2
    mobiReader.extract_text(offset=offset)
    html = mobiReader.mobi_html

    # match text between HTML tags
    for match_text in re.finditer(b">[^<>]+<", html):
        text = html[match_text.start():match_text.end()]
        # match each word inside text
        for match_word in re.finditer(b"[a-zA-Z]+", text):
            lemma = text[match_word.start():match_word.end()]
            start = match_text.start() + match_word.start()
            if book_fmt.lower() == 'azw3':
                start -= 14 # I have no idea, may not work
            yield (start, lemma.decode('utf-8'))
