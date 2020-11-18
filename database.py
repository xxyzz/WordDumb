#!/usr/bin/env python3
import sqlite3
from pathlib import Path


def connect_ww_database():
    ww_conn = sqlite3.connect(":memory:")
    ww_cur = ww_conn.cursor()
    ww_cur.executescript(get_resources('data/wordwise.sql').decode('utf-8'))
    return ww_conn, ww_cur


def get_ll_path(asin, book_path):
    lang_layer_name = "LanguageLayer.en.{}.kll".format(asin)
    return Path(book_path).parent.joinpath(lang_layer_name)


def create_lang_layer(asin, book_path):
    # check LanguageLayer file
    lang_layer_path = get_ll_path(asin, book_path)
    ll_journal = lang_layer_path.parent.joinpath(
        lang_layer_path.name + '-journal')
    if lang_layer_path.is_file():
        if not ll_journal.is_file():
            return None, None, lang_layer_path
        else:  # last time failed
            lang_layer_path.unlink()
            ll_journal.unlink()

    # create LanguageLayer database file
    lang_layer_path.parent.mkdir(exist_ok=True)
    lang_layer_path.touch()
    ll_conn = sqlite3.connect(lang_layer_path)
    ll_cur = ll_conn.cursor()
    ll_cur.executescript('''
        CREATE TABLE metadata (
            key TEXT,
            value TEXT
        );

        CREATE TABLE glosses (
            start INTEGER,
            end INTEGER,
            difficulty INTEGER,
            sense_id INTEGER,
            low_confidence INTEGER
        );
    ''')
    metadata = [('acr', 'CR!AX4P53SCH15WF68KNBX4NWWVZXKG'),  # Palm DB name
                ('targetLanguages', 'en'),
                ('sidecarRevision', '9'),
                ('bookRevision', '8d271dc3'),
                ('sourceLanguage', 'en'),
                ('enDictionaryVersion', '2016-09-14'),
                ('enDictionaryRevision', '57'),
                ('enDictionaryId', 'kll.en.en'),
                ('sidecarFormat', '1.0')]
    ll_cur.executemany('INSERT INTO metadata VALUES (?, ?)', metadata)

    return ll_conn, ll_cur, lang_layer_path


def match_lemma(start, word, ll_cur, ww_cur):
    ww_cur.execute("SELECT * FROM words WHERE lemma = ?", (word.lower(), ))
    result = ww_cur.fetchone()
    if result is not None:
        (_, sense_id, difficulty) = result
        ll_cur.execute('''
            INSERT INTO glosses (start, difficulty, sense_id, low_confidence)
            VALUES (?, ?, ?, ?)
        ''', (start, difficulty, sense_id, 0))
