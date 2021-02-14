#!/usr/bin/env python3
import sqlite3
from pathlib import Path


def get_ll_path(asin, book_path):
    lang_layer_name = "LanguageLayer.en.{}.kll".format(asin)
    return Path(book_path).parent.joinpath(lang_layer_name)


def create_lang_layer(asin, book_path):
    # check if LanguageLayer file already exist
    lang_layer_path = get_ll_path(asin, book_path)
    ll_journal = lang_layer_path.parent.joinpath(
        lang_layer_path.name + '-journal')
    if lang_layer_path.is_file():
        if not ll_journal.is_file():
            return None
        else:  # last time failed
            lang_layer_path.unlink()
            ll_journal.unlink()

    # create LanguageLayer database file
    lang_layer_path.parent.mkdir(exist_ok=True)
    lang_layer_path.touch()
    ll_conn = sqlite3.connect(lang_layer_path)
    ll_conn.executescript('''
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
    ll_conn.executemany('INSERT INTO metadata VALUES (?, ?)', metadata)
    return ll_conn


def search_lemma(r, start, word, ll_conn):
    result = r.hgetall('lemma:' + word)
    if result:
        insert_lemma((start,
                      result[b'difficulty'].decode('utf-8'),
                      result[b'sense_id'].decode('utf-8')),
                     ll_conn)


def insert_lemma(data, ll_conn):
    ll_conn.execute('''
        INSERT INTO glosses (start, difficulty, sense_id, low_confidence)
        VALUES (?, ?, ?, 0)
        ''', data)


def start_redis_server(db_path):
    import subprocess
    import platform
    args = ['--dir', db_path, '--save', '']
    if platform.system() == 'Darwin':
        # when launch calibre from desktop instead of terminal
        # it needs the absolute path of redis-server
        args.insert(0, '/usr/local/bin/redis-server')
        subprocess.Popen(args)
    else:
        args.insert(0, 'redis-server')
        subprocess.Popen(args)

    import redis
    return redis.Redis()
