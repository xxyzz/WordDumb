#!/usr/bin/env python3
import sqlite3
from pathlib import Path

try:
    from .unzip import load_json_or_pickle
except ImportError:
    from unzip import load_json_or_pickle


def get_ll_path(asin, book_path):
    return Path(book_path).parent.joinpath(f"LanguageLayer.en.{asin}.kll")


def create_lang_layer(asin, book_path, acr, revision):
    db_path = get_ll_path(asin, book_path)
    ll_conn = sqlite3.connect(":memory:")
    ll_conn.executescript(
        """
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
        """
    )

    metadata = [
        ("acr", acr),
        ("targetLanguages", "en"),
        ("sidecarRevision", "9"),
        ("bookRevision", revision),
        ("sourceLanguage", "en"),
        ("enDictionaryVersion", "2016-09-14"),
        ("enDictionaryRevision", "57"),
        ("enDictionaryId", "kll.en.en"),
        ("sidecarFormat", "1.0"),
    ]
    ll_conn.executemany("INSERT INTO metadata VALUES (?, ?)", metadata)
    return ll_conn, db_path


def insert_lemma(ll_conn, data):
    ll_conn.execute(
        "INSERT INTO glosses (start, end, difficulty, sense_id, low_confidence) VALUES (?, ?, ?, ?, 0)",
        data,
    )


def get_x_ray_path(asin, book_path):
    return Path(book_path).parent.joinpath(f"XRAY.entities.{asin}.asc")


def create_x_ray_db(asin, book_path, lang, plugin_path, prefs):
    db_path = get_x_ray_path(asin, book_path)
    x_ray_conn = sqlite3.connect(":memory:")
    x_ray_conn.executescript(
        """
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

    CREATE TABLE entity (
    id INTEGER PRIMARY KEY,
    label TEXT,
    loc_label INTEGER,
    type INTEGER,
    count INTEGER,
    has_info_card TINYINT);

    CREATE TABLE entity_description (
    text TEXT,
    source_wildcard TEXT,
    source INTEGER,
    entity INTEGER PRIMARY KEY);

    CREATE TABLE entity_excerpt (
    entity INTEGER,
    excerpt INTEGER);

    CREATE TABLE excerpt (
    id INTEGER PRIMARY KEY,
    start INTEGER,
    length INTEGER,
    image TEXT,
    related_entities TEXT,
    goto INTEGER);

    CREATE TABLE occurrence (
    entity INTEGER,
    start INTEGER,
    length INTEGER);

    CREATE TABLE source (
    id INTEGER PRIMARY KEY,
    label INTEGER,
    url INTEGER,
    license_label INTEGER,
    license_url INTEGER);

    CREATE TABLE string (
    id INTEGER,
    language TEXT,
    text TEXT);

    CREATE TABLE type (
    id INTEGER PRIMARY KEY,
    label INTEGER,
    singular_label INTEGER,
    icon INTEGER,
    top_mentioned_entities TEXT);

    INSERT INTO entity (id, loc_label, has_info_card) VALUES(0, 1, 0);
    INSERT INTO source (id, label, url) VALUES(0, 5, 20);
    INSERT INTO source VALUES(1, 6, 21, 7, 8);
    INSERT INTO source (id, label, url) VALUES(2, 4, 22);
    """
    )

    str_list = load_json_or_pickle(plugin_path, "data/x_ray_strings.json")
    if prefs["fandom"]:
        str_list[-2][-1] = f"{prefs['fandom']}/wiki/%s"
        for d in str_list:
            if d[0] == 6:
                d[-1] = "Fandom"
    elif lang == "zh":
        str_list[-2][-1] = f"https://zh.wikipedia.org/zh-{prefs['zh_wiki_variant']}/%s"
    elif lang != "en":
        str_list[-2][-1] = f"https://{lang}.wikipedia.org/wiki/%s"
    x_ray_conn.executemany("INSERT INTO string VALUES(?, ?, ?)", str_list)

    return x_ray_conn, db_path


def create_x_indices(conn):
    conn.executescript(
        """
        CREATE INDEX idx_entity_type ON entity(type ASC);
        CREATE INDEX idx_entity_excerpt ON entity_excerpt(entity ASC);
        CREATE INDEX idx_occurrence_start ON occurrence(start ASC);
        """
    )


def insert_x_book_metadata(conn, data):
    conn.execute("INSERT INTO book_metadata VALUES(0, ?, ?, 0, 0, ?, ?, ?, ?)", data)


def insert_x_entities(conn, data):
    conn.executemany(
        "INSERT INTO entity (id, label, type, count, has_info_card) VALUES(?, ?, ?, ?, 1)",
        data,
    )


def insert_x_entity_description(conn, data):
    conn.execute("INSERT INTO entity_description VALUES(?, ?, ?, ?)", data)


def insert_x_occurrences(conn, data):
    conn.executemany("INSERT INTO occurrence VALUES(?, ?, ?)", data)


def insert_x_type(conn, data):
    conn.execute("INSERT INTO type VALUES(?, ?, ?, ?, ?)", data)


def insert_x_excerpt_image(conn, data):
    conn.execute(
        "INSERT INTO excerpt (id, start, length, image, goto) VALUES(?, ?, 0, ?, ?)",
        data,
    )


def save_db(source, dest_path):
    source.commit()
    dest_path.parent.mkdir(exist_ok=True)
    dest = sqlite3.connect(dest_path)
    with dest:
        source.backup(dest)
    source.close()
    dest.close()
