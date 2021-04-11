#!/usr/bin/env python3
import sqlite3
from pathlib import Path

from calibre_plugins.worddumb.unzip import load_json
from calibre_plugins.worddumb.metadata import get_acr, get_book_revision


def get_ll_path(asin, book_path):
    return Path(book_path).parent.joinpath(f'LanguageLayer.en.{asin}.kll')


def check_db_file(path):
    '''
    if file exists return None otherwise create file
    then return sqlite connection
    '''
    journal = path.parent.joinpath(path.name + '-journal')
    if path.is_file():
        if not journal.is_file():
            return None
        else:  # last time failed
            path.unlink()
            journal.unlink()

    path.parent.mkdir(exist_ok=True)
    path.touch()
    return sqlite3.connect(path)


def create_lang_layer(asin, book_path):
    if (ll_conn := check_db_file(get_ll_path(asin, book_path))) is None:
        return None
    ll_conn.executescript('''
        CREATE TABLE metadata (
            key TEXT,
            value TEXT
        );

        CREATE TABLE glosses (
            start INTEGER PRIMARY KEY,
            end INTEGER,
            difficulty INTEGER,
            sense_id INTEGER,
            low_confidence BOOLEAN
        );
    ''')

    metadata = [('acr', get_acr(book_path)),
                ('targetLanguages', 'en'),
                ('sidecarRevision', '9'),
                ('bookRevision', get_book_revision(book_path)),
                ('sourceLanguage', 'en'),
                ('enDictionaryVersion', '2016-09-14'),
                ('enDictionaryRevision', '57'),
                ('enDictionaryId', 'kll.en.en'),
                ('sidecarFormat', '1.0')]
    ll_conn.executemany('INSERT INTO metadata VALUES (?, ?)', metadata)
    return ll_conn


def insert_lemma(ll_conn, data):
    ll_conn.execute('''
    INSERT INTO glosses (start, difficulty, sense_id, low_confidence)
    VALUES (?, ?, ?, 0)
    ''', data)


def get_x_ray_path(asin, book_path):
    return Path(book_path).parent.joinpath(f'XRAY.entities.{asin}.asc')


def create_x_ray_db(asin, book_path):
    if (x_ray_conn := check_db_file(get_x_ray_path(asin, book_path))) is None:
        return None
    x_ray_conn.executescript('''
    PRAGMA user_version = 1;

    CREATE TABLE book_metadata (
    srl INTEGER,
    erl INTEGER,
    has_images TINYINT,
    has_excerpts TINYINT,
    show_spoilers_default TINYINT,
    num_people INTEGER,
    num_terms INTEGER,
    num_images INTEGER,
    preview_images TEXT);

    CREATE TABLE bookmentions_entity (
    id INTEGER,
    asin TEXT,
    title TEXT,
    authors TEXT,
    description TEXT,
    ratings INTEGER,
    totalRatings INTEGER,
    type TEXT,
    PRIMARY KEY(id));

    CREATE TABLE bookmentions_occurrence (
    entity INTEGER,
    start INTEGER,
    length INTEGER);

    CREATE TABLE entity (
    id INTEGER,
    label TEXT,
    loc_label INTEGER,
    type INTEGER,
    count INTEGER,
    has_info_card TINYINT,
    PRIMARY KEY(id));
    CREATE INDEX idx_entity_type ON entity(type ASC);

    CREATE TABLE entity_description (
    text TEXT,
    source_wildcard TEXT,
    source INTEGER,
    entity INTEGER,
    PRIMARY KEY(entity));

    CREATE TABLE entity_excerpt (
    entity INTEGER,
    excerpt INTEGER);
    CREATE INDEX idx_entity_excerpt ON entity_excerpt(entity ASC);

    CREATE TABLE excerpt (
    id INTEGER,
    start INTEGER,
    length INTEGER,
    image TEXT,
    related_entities TEXT,
    goto INTEGER,
    PRIMARY KEY(id));

    CREATE TABLE occurrence (
    entity INTEGER,
    start INTEGER,
    length INTEGER);
    CREATE INDEX idx_occurrence_start ON occurrence(start ASC);

    CREATE TABLE source (
    id INTEGER,
    label INTEGER,
    url INTEGER,
    license_label INTEGER,
    license_url INTEGER,
    PRIMARY KEY(id));

    CREATE TABLE string (
    id INTEGER,
    language TEXT,
    text TEXT);

    CREATE TABLE type (
    id INTEGER,
    label INTEGER,
    singular_label INTEGER,
    icon INTEGER,
    top_mentioned_entities TEXT,
    PRIMARY KEY(id));

    INSERT INTO entity (id, loc_label, has_info_card) VALUES(0, 1, 0);
    INSERT INTO source (id, label, url) VALUES(0, 5, 20);
    INSERT INTO source VALUES(1, 6, 21, 7, 8);
    INSERT INTO source (id, label, url) VALUES(2, 4, 22);
    ''')

    x_ray_conn.executemany('INSERT INTO string VALUES(?, ?, ?)',
                           load_json('data/x_ray_strings.json'))

    return x_ray_conn


def insert_x_book_metadata(conn, data):
    conn.execute('''
    INSERT INTO book_metadata (srl, erl, has_images, has_excerpts,
    show_spoilers_default, num_people, num_terms, num_images)
    VALUES(0, ?, 0, 0, 1, ?, ?, 0)
    ''', data)


def insert_x_entity(conn, data):
    conn.execute('''
    INSERT INTO entity (id, label, type, count, has_info_card)
    VALUES(?, ?, ?, ?, 1)
    ''', data)


def insert_x_entity_description(conn, data):
    conn.execute('INSERT INTO entity_description VALUES(?, ?, ?, ?)', data)


def insert_x_occurrence(conn, data):
    conn.execute('INSERT INTO occurrence VALUES(?, ?, ?)', data)


def insert_x_type(conn, data):
    conn.execute('INSERT INTO type VALUES(?, ?, ?, ?, ?)', data)
