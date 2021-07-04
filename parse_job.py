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
                         exclude=['tok2vec', 'morphologizer', 'tagger',
                                  'parser', 'attribute_ruler', 'lemmatizer'])
        nlp.enable_pipe("senter")

    is_kfx = book_fmt == 'KFX'
    if create_ww:
        lemmas = load_json('data/lemmas.json')
        for (text, start) in parse_book(book_path, is_kfx):
            find_lemma(start, text, lemmas, ll_conn, is_kfx)
            if prefs['x-ray']:
                find_named_entity(start, x_ray, nlp(text), is_kfx)

        ll_conn.commit()
        ll_conn.close()
    else:
        for doc, start in nlp.pipe(parse_book(book_path, is_kfx),
                                   as_tuples=True):
            find_named_entity(start, x_ray, doc, is_kfx)

    if prefs['x-ray']:
        x_ray.finish()


def parse_book(book_path, is_kfx):
    if is_kfx:
        yield from parse_kfx(book_path)
    else:
        yield from parse_mobi(book_path)


def parse_kfx(path_of_book):
    from calibre_plugins.kfx_input.kfxlib import YJ_Book

    data = YJ_Book(path_of_book).convert_to_json_content()
    for entry in json.loads(data)['data']:
        yield (entry['content'], entry['position'])


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
        yield (match_text.group(0)[1:-1].decode('utf-8'),
               match_text.start() + 1)


def find_lemma(start, text, lemmas, ll_conn, is_kfx):
    from nltk.corpus import wordnet as wn

    for match in re.finditer(r'[a-zA-Z\u00AD]{3,}', text):
        lemma = wn.morphy(match.group(0).replace('\u00AD', '').lower())
        if lemma in lemmas:
            if is_kfx:
                index = start + match.start()
            else:
                index = start + len(text[:match.start()].encode('utf-8'))
            insert_lemma(ll_conn, (index,) + tuple(lemmas[lemma]))


def find_named_entity(start, x_ray, doc, is_kfx):
    # https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L318
    labels = {'EVENT', 'FAC', 'GPE', 'LANGUAGE', 'LAW', 'LOC', 'NORP', 'ORG',
              'PERSON', 'PRODUCT', 'WORK_OF_ART', 'MISC', 'PER', 'FACILITY',
              'ORGANIZATION', 'NAT_REL_POL',  # Romanian
              'geogName', 'orgName', 'persName', 'placeName'}  # Polish

    for ent in doc.ents:
        if ent.label_ not in labels:
            continue

        if is_kfx:
            ent_start = start + len(doc.text[:ent.start_char])
            ent_len = len(ent.text)
        else:
            ent_start = start + len(doc.text[:ent.start_char].encode('utf-8'))
            ent_len = len(ent.text.encode('utf-8'))

        x_ray.search(ent.text, ent.label_, ent_start, ent.sent.text, ent_len)
