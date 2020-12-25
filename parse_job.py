#!/usr/bin/env python3
import concurrent.futures
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.utils.config import config_dir
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.database import (connect_ww_database,
                                               create_lang_layer, find_lemma,
                                               insert_lemma)
from calibre_plugins.worddumb.metadata import check_metadata

NLTK_VERSION = '3.5'


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
    worker_count = os.cpu_count()

    for (_, book_fmt, asin, book_path, _) in books:
        ll_conn = create_lang_layer(asin, book_path)
        if ll_conn is None:
            continue

        data = [(start, wn.morphy(word.lower()))
                for (start, word) in parse_book(book_path, book_fmt)]
        words_each_worker = math.floor(len(data) / worker_count)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for i in range(worker_count):
                worker_data = None
                if i == worker_count - 1:
                    worker_data = data[i * words_each_worker:]
                else:
                    worker_data = data[i * words_each_worker:
                                       (i + 1) * words_each_worker]
                futures.append(executor.submit(worker, worker_data))
            for future in concurrent.futures.as_completed(futures):
                insert_lemma(future.result(), ll_conn)
            ll_conn.commit()
            ll_conn.close()


def worker(data):
    ww_conn = connect_ww_database()
    result = find_lemma(data, ww_conn)
    ww_conn.close()
    return result


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


def install_libs(plugin_path):
    extract_path = Path(config_dir).joinpath('plugins/worddumb-nltk'
                                             + NLTK_VERSION)
    if not extract_path.is_dir():
        for f in Path(config_dir).joinpath('plugins').iterdir():
            if 'worddumb' in f.name and f.is_dir():
                shutil.rmtree(f)  # delete old library folder

        with ZipFile(plugin_path, 'r') as zf:
            for f in zf.namelist():
                if '.venv' in f:
                    zf.extract(f, path=extract_path)

    for dir in extract_path.joinpath('.venv/lib').iterdir():
        sys.path.append(str(dir.joinpath('site-packages')))
    import nltk
    nltk.data.path.append(str(extract_path.joinpath('.venv/nltk_data')))
