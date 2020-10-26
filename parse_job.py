#!/usr/bin/env python3

from html.parser import HTMLParser
from pathlib import Path
import sqlite3
import re

def do_parse(books):
    ww_conn = sqlite3.connect(":memory:")
    ww_cur = ww_conn.cursor()
    with open(Path("data/wordwise.sql")) as f:
        ww_cur.executescript(f.read())

    for (book_id, book_fmt, asin, book_path) in books:
        ll_conn, ll_cur = create_lang_layer(book_id, book_fmt, asin, book_path)
        if ll_conn is None:
            continue

        for (start, lemma) in parse_book(book_path):
            match_word(start, lemma, ll_cur, ww_cur)

        ll_conn.commit()
        ll_conn.close()

    ww_conn.close()

def create_lang_layer(book_id, book_fmt, asin, book_path):
    # check LanguageLayer file
    lang_layer_path = Path(book_path).parent
    folder_name = lang_layer_path.stem + ".sdr"
    lang_layer_path = lang_layer_path.joinpath(folder_name)
    lang_layer_name = "LanguageLayer.en.{}.kll".format(asin)
    lang_layer_path = lang_layer_path.joinpath(lang_layer_name)
    if lang_layer_path.is_file():
        return None, None, None

    # create LanguageLayer database file
    lang_layer_path.parent.mkdir(exist_ok=True)
    lang_layer_path.touch()
    ll_conn = sqlite3.connect(lang_layer_path)
    ll_cur = ll_conn.cursor()
    ll_cur.executescript('''
        CREATE TABLE metadata (
            acr TEXT,
            targetLanguages TEXT,
            sidecarRevision INTEGER,
            bookRevision TEXT,
            sourceLanguage TEXT,
            enDictionaryVersion TEXT,
            enDictionaryRevision INTEGER,
            enDictionaryId TEXT,
            sidecarFormat REAL
        );

        CREATE TABLE glosses (
            start INTEGER,
            end INTEGER,
            difficulty INTEGER,
            sense_id INTEGER,
            low_confidence INTEGER
        );

        INSERT INTO metadata
        VALUES (
            'CR!AX4P53SCH15WF68KNBX4NWWVZXKG',
            'en',
            9,
            '8d271dc3',
            'en',
            '2016-09-14',
            57,
            'kll.en.en',
            1.0
        );
    ''')

    return ll_conn, ll_cur

def parse_book(book_path):
    from calibre.ebooks.oeb.polish.container import get_container
    container = get_container(book_path)
    last_file_length = 0
    for file, _ in container.spine_names:
        book_part = container.raw_data(file, decode=True)
        p = BookParser()
        p.feed(book_part)
        for (loc, text) in p.texts:
            for match in re.finditer(r"[a-zA-Z]+", text):
                lemma = text[match.start():match.end()]
                start = last_file_length + loc + match.start()
                print("{}, {}".format(start, lemma))
                yield (start, lemma)
        last_file_length = len(book_part)

def match_word(start, lemma, ll_cur, ww_cur):
    ww_cur.execute("SELECT * FROM words WHERE lemma = ?", (lemma.lower(), ))
    result = ww_cur.fetchone()
    if result is not None:
        (_, sense_id, difficulty) = result
        ll_cur.execute('''
            INSERT INTO glosses (start, difficulty, sense_id, low_confidence)
            VALUES (?, ?, ?, ?)
        ''', (start, difficulty, sense_id, 0))

class BookParser(HTMLParser):
    texts = []

    def handle_data(self, data):
        if len(data.strip()) > 0:
            self.texts.append((self.getpos()[1], data))
