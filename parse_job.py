#!/usr/bin/env python3
import json
import re

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import (create_lang_layer,
                                               create_x_ray_db, insert_lemma)
from calibre_plugins.worddumb.unzip import install_libs, load_json
from calibre_plugins.worddumb.x_ray import X_Ray


def do_job(data, abort=None, log=None, notifications=None):
    (_, book_fmt, asin, book_path, _, lang) = data
    install_libs(lang['spacy'])

    create_ww = False
    if lang['wiki'] == 'en':
        ll_conn = create_lang_layer(asin, book_path, book_fmt)
        if ll_conn is not None:
            create_ww = True
        elif not prefs['x-ray']:
            return

    if prefs['x-ray']:
        x_ray_conn = create_x_ray_db(asin, book_path, lang['wiki'])
        if x_ray_conn is None:
            return
        x_ray = X_Ray(x_ray_conn, lang['wiki'])
        import spacy
        nlp = spacy.load(lang['spacy'],
                         exclude=['tok2vec', 'tagger', 'parser',
                                  'attribute_ruler', 'lemmatizer'])

    if create_ww:
        lemmas = load_json('data/lemmas.json')
    for (start, text) in parse_book(book_path, book_fmt):
        if create_ww:
            find_lemma(start, text, lemmas, ll_conn)
        if prefs['x-ray']:
            find_named_entity(start, text, x_ray, nlp)

    if create_ww:
        ll_conn.commit()
        ll_conn.close()
    if prefs['x-ray']:
        x_ray.finish()


def parse_book(book_path, book_fmt):
    if book_fmt == 'KFX':
        yield from parse_kfx(book_path)  # str
    else:
        yield from parse_mobi(book_path)  # bytes str


def parse_kfx(path_of_book):
    from calibre_plugins.kfx_input.kfxlib import YJ_Book

    data = YJ_Book(path_of_book).convert_to_json_content()
    for entry in json.loads(data)['data']:
        yield (entry['position'], entry['content'])


def parse_mobi(book_path):
    # use code from calibre.ebooks.mobi.reader.mobi8:Mobi8Reader.__call__
    # and calibre.ebook.conversion.plugins.mobi_input:MOBIInput.convert
    try:
        mr = MobiReader(book_path, default_log)
    except Exception:
        mr = MobiReader(book_path, default_log, try_extra_data_fix=True)
    if mr.kf8_type == 'joint':
        raise Exception('JointMOBI')
    mr.check_for_drm()
    mr.extract_text()
    html = mr.mobi_html
    if mr.kf8_type == 'standalone':
        m8r = Mobi8Reader(mr, default_log)
        m8r.kf8_sections = mr.sections
        m8r.read_indices()
        m8r.build_parts()
        html = b''.join(m8r.parts)

    # match text between HTML tags
    for match_text in re.finditer(b'>[^<>]+<', html):
        yield (match_text.start() + 1, match_text.group(0)[1:-1])


def find_lemma(start, text, lemmas, ll_conn):
    from nltk.corpus import wordnet as wn

    if (bytes_str := isinstance(text, bytes)):
        text = text.decode('utf-8')
    for match in re.finditer(r'[a-zA-Z\u00AD]{3,}', text):
        lemma = wn.morphy(match.group(0).replace('\u00AD', '').lower())
        if lemma in lemmas:
            if bytes_str:
                index = start + len(text[:match.start()].encode('utf-8'))
            else:
                index = start + match.start()
            insert_lemma(ll_conn, (index,) + tuple(lemmas[lemma]))


def find_named_entity(start, text, x_ray, nlp):
    if (bytes_str := isinstance(text, bytes)):
        text = text.decode('utf-8')

    # https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L318
    labels = {'EVENT', 'FAC', 'GPE', 'LANGUAGE', 'LAW', 'LOC', 'NORP', 'ORG',
              'PERSON', 'PRODUCT', 'WORK_OF_ART', 'MISC', 'PER', 'FACILITY',
              'ORGANIZATION', 'NAT_REL_POL',  # Romanian
              'geogName', 'orgName', 'persName', 'placeName'}  # Polish
    for ent in nlp(text).ents:
        if ent.label_ not in labels:
            continue
        index = ent.start_char
        ent_start = start
        if bytes_str:
            ent_start += len(text[:index].encode('utf-8'))
            ent_len = len(ent.text.encode('utf-8'))
        else:
            ent_start += len(text[:index])
            ent_len = len(ent.text)
        x_ray.search(ent.text, ent.label_, ent_start, text[index:], ent_len)
