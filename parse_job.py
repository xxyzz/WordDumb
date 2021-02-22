#!/usr/bin/env python3
import json
import re

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import (create_lang_layer,
                                               create_x_ray_db, search_lemma,
                                               start_redis_server)
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.unzip import install_libs, unzip_db
from calibre_plugins.worddumb.x_ray import X_Ray


def check_books(db, ids):
    books = []
    for book_id in ids:
        if (data := check_metadata(db, book_id)) is None:
            continue
        books.append((book_id, ) + data)
    return books


def do_job(db, ids, abort, log, notifications):
    install_libs()
    from nltk import ne_chunk, pos_tag, word_tokenize
    from nltk.tree import Tree
    r = start_redis_server(unzip_db())

    for (_, book_fmt, asin, book_path, _) in check_books(db, ids):
        if (ll_conn := create_lang_layer(asin, book_path)) is None:
            continue
        if prefs['x-ray']:
            if (x_ray_conn := create_x_ray_db(asin, book_path, r)) is None:
                continue
            x_ray = X_Ray(x_ray_conn)

        for (start, text) in parse_book(book_path, book_fmt):
            records = set()
            for node in ne_chunk(pos_tag(word_tokenize(text.decode('utf-8')))):
                if type(node) is Tree:
                    token = ' '.join([t for t, _ in node.leaves()])
                    if len(token) < 3 or token in records:
                        continue
                    records.add(token)
                    index = text.find(token.encode('utf-8'))
                    token_start = start + index
                    if node.label() != 'PERSON':
                        check_word(r, token_start, token, ll_conn)
                    if prefs['x-ray']:
                        x_ray.search(token, node.label(), token_start,
                                     text[index:].decode('utf-8'))
                elif len(token := node[0]) >= 3 and token not in records:
                    records.add(token)
                    check_word(r, start + text.find(token.encode('utf-8')),
                               token, ll_conn)

        ll_conn.commit()
        ll_conn.close()
        if prefs['x-ray']:
            x_ray.finish()

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
        yield (entry['position'], entry['content'].encode('utf-8'))


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
        yield (match_text.start() + 1, match_text.group(0)[1:-1])


def check_word(r, start, word, ll_conn):
    if re.fullmatch(r'[a-zA-Z]{3,}', word):
        from nltk.corpus import wordnet as wn
        lemma = wn.morphy(word.lower())
        if lemma and len(lemma) >= 3:
            search_lemma(r, start, lemma, ll_conn)
