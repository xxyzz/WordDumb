#!/usr/bin/env python3
import json
import re

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import (create_lang_layer,
                                               create_x_ray_db, insert_lemma)
from calibre_plugins.worddumb.metadata import check_metadata
from calibre_plugins.worddumb.unzip import install_libs, load_json
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
    lemmas = load_json('lemmas.json')

    for (_, book_fmt, asin, book_path, _) in check_books(db, ids):
        ll_conn = create_lang_layer(asin, book_path)
        if ll_conn is None and not prefs['x-ray']:
            continue
        if prefs['x-ray']:
            if (x_ray_conn := create_x_ray_db(asin, book_path)) is None:
                continue
            x_ray = X_Ray(x_ray_conn)

        for (start, text) in parse_book(book_path, book_fmt):
            if ll_conn is not None:
                find_lemma(start, text, lemmas, ll_conn)

            if prefs['x-ray']:
                find_named_entity(start, text, x_ray)

        if ll_conn is not None:
            ll_conn.commit()
            ll_conn.close()
        if prefs['x-ray']:
            x_ray.finish()


def parse_book(path_of_book, book_fmt):
    if (book_fmt.lower() == 'kfx'):
        yield from parse_kfx(path_of_book)  # str
    else:
        yield from parse_mobi(path_of_book, book_fmt)  # bytes str


def parse_kfx(path_of_book):
    from calibre_plugins.kfx_input.kfxlib import YJ_Book

    book = YJ_Book(path_of_book)
    data = book.convert_to_json_content()
    for entry in json.loads(data)['data']:
        yield (entry['position'], entry['content'])


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
    for match_text in re.finditer(b'>[^<>]+<', html):
        yield (match_text.start() + 1, match_text.group(0)[1:-1])


def find_lemma(start, text, lemmas, ll_conn):
    from nltk.corpus import wordnet as wn

    bytes_str = True if isinstance(text, bytes) else False
    pattern = b'[a-zA-Z]{3,}' if bytes_str else r'[a-zA-Z]{3,}'
    for match in re.finditer(pattern, text):
        word = match.group(0).decode('utf-8') if bytes_str else match.group(0)
        lemma = wn.morphy(word.lower())
        if lemma and len(lemma) >= 3 and lemma in lemmas:
            insert_lemma(ll_conn, (start + match.start(),) +
                         tuple(lemmas[lemma]))


def find_named_entity(start, text, x_ray):
    from nltk import ne_chunk, pos_tag, word_tokenize
    from nltk.tree import Tree

    records = set()
    bytes_str = True if isinstance(text, bytes) else False
    if bytes_str:
        text = text.decode('utf-8')
    nodes = ne_chunk(pos_tag(word_tokenize(text)))
    for node in filter(lambda x: type(x) is Tree, nodes):
        token = ' '.join([t for t, _ in node.leaves()])
        if len(token) < 3 or token in records:
            continue
        records.add(token)
        if (match := re.search(r'\b' + token + r'\b', text)) is None:
            continue
        index = match.start()
        token_start = start
        if bytes_str:
            token_start += len(text[:index].encode('utf-8'))
        else:
            token_start += len(text[:index])
        x_ray.search(token, node.label(), token_start, text[index:])
