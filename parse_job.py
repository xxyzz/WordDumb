#!/usr/bin/env python3

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
        for (location, word) in parse_book(book_path):
            match_word(location, word, ll_cur, ww_cur)

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

        INSERT INTO metadata(
            targetLanguages,
            sidecarRevision,
            sourceLanguage,
            enDictionaryVersion,
            enDictionaryRevision,
            enDictionaryId,
            sidecarFormat)
        VALUES (
            'en',
            9,
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
    last_word_byte_offset = 0
    for file, _ in container.spine_names:
        last_word_offset = 0
        for text in container.parsed(file).itertext():
            for match in re.finditer(r"[a-zA-Z]+", text):
                word = text[match.start():match.end()]
                offset = len(text[last_word_offset:match.start()].encode("utf-8"))
                word_byte_offset = last_word_byte_offset + offset
                last_word_byte_offset = word_byte_offset + len(word.encode("utf-8"))
                last_word_offset = match.end()
                yield (word_byte_offset, word)

def match_word(location, word, ll_cur, ww_cur):
    ww_cur.execute("SELECT * FROM words WHERE lemma = ?", (word.lower(), ))
    result = ww_cur.fetchone()
    if result is not None:
        (_, sense_id, difficulty) = result
        ll_cur.execute('''
            INSERT INTO glosses (start, difficulty, sense_id, low_confidence)
            VALUES (?, ?, ?, ?)
        ''', (location, difficulty, sense_id, 0))
