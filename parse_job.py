#!/usr/bin/env python3
import json
import re

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import (create_lang_layer,
                                               create_x_ray_db, insert_lemma,
                                               save_db)
from calibre_plugins.worddumb.unzip import install_libs, load_json
from calibre_plugins.worddumb.x_ray import X_Ray


def do_job(data, create_ww=True, create_x=True,
           abort=None, log=None, notifications=None):
    (_, book_fmt, asin, book_path, _, lang) = data
    model = lang['spacy'] + prefs['model_size']
    install_libs(model, create_ww, create_x)
    is_kfx = book_fmt == 'KFX'

    if create_ww:
        ll_conn, ll_path = create_lang_layer(asin, book_path, book_fmt)
        if ll_conn is None:
            create_ww = False
            if not create_x:
                return
        else:
            lemmas = load_json('data/lemmas.json')

    if create_x:
        x_ray_conn, x_ray_path = create_x_ray_db(asin, book_path, lang['wiki'])
        if x_ray_conn is None:
            return
        x_ray = X_Ray(x_ray_conn, lang['wiki'])
        import spacy
        nlp = spacy.load(model,
                         exclude=['tok2vec', 'morphologizer', 'tagger',
                                  'parser', 'attribute_ruler', 'lemmatizer'])
        nlp.enable_pipe("senter")

        for doc, start in nlp.pipe(parse_book(book_path, is_kfx),
                                   as_tuples=True):
            find_named_entity(start, x_ray, doc, is_kfx)
            if create_ww:
                find_lemma(start, doc.text, lemmas, ll_conn, is_kfx)

        x_ray.finish(x_ray_path)
    elif create_ww:
        for text, start in parse_book(book_path, is_kfx):
            find_lemma(start, text, lemmas, ll_conn, is_kfx)

    if create_ww:
        save_db(ll_conn, ll_path)


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
    # https://github.com/kevinhendricks/KindleUnpack/blob/master/lib/mobi_k8proc.py#L216
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


# https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L318
NER_LABELS = {
    'EVENT', 'FAC', 'GPE', 'LANGUAGE', 'LAW', 'LOC', 'NORP', 'ORG',
    'PERSON', 'PRODUCT', 'WORK_OF_ART', 'MISC', 'PER', 'FACILITY',
    'ORGANIZATION', 'NAT_REL_POL',  # Romanian
    'geogName', 'orgName', 'persName', 'placeName'  # Polish
}


def find_named_entity(start, x_ray, doc, is_kfx):
    for ent in doc.ents:
        if ent.label_ not in NER_LABELS:
            continue
        if len(ent.text) <= 1 or re.fullmatch(r'[\W\d]+', ent.text):
            continue

        text = re.sub(r'^\W+', '', ent.text)
        text = re.sub(r'\W+$', '', text)
        if x_ray.lang == 'en':
            if re.match(r'chapter', text, re.IGNORECASE):
                return
            text = re.sub(r'(?:\'s|’s)$', '', text)
            text = re.sub(r'^(?:the |an |a )', '', text, flags=re.IGNORECASE)

        new_start_char = ent.start_char + ent.text.index(text)
        if is_kfx:
            ent_start = start + len(doc.text[:new_start_char])
            ent_len = len(text)
        else:
            ent_start = start + len(doc.text[:new_start_char].encode('utf-8'))
            ent_len = len(text.encode('utf-8'))

        x_ray.search(text, ent.label_ in ['PERSON', 'PER', 'persName'],
                     ent_start, ent.sent.text, ent_len)
