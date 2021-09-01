#!/usr/bin/env python3
import json
import re

from calibre.constants import ismacos
from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import (create_lang_layer,
                                               create_x_ray_db, insert_lemma,
                                               save_db)
from calibre_plugins.worddumb.metadata import set_asin
from calibre_plugins.worddumb.unzip import install_libs, load_json
from calibre_plugins.worddumb.x_ray import X_Ray


def do_job(data, create_ww=True, create_x=True,
           abort=None, log=None, notifications=None):
    (_, book_fmt, asin, book_path, mi, updata_asin, lang) = data
    if updata_asin:
        set_asin(mi, asin, book_fmt, book_path)
    model = lang['spacy'] + prefs['model_size']
    install_libs(model, create_ww)
    is_kfx = book_fmt == 'KFX'
    ll_conn = None
    ll_path = None
    lemmas = None
    x_ray_conn = None
    x_ray_path = None

    if create_ww:
        ll_conn, ll_path = create_lang_layer(asin, book_path, book_fmt)
        if ll_conn is None:
            create_ww = False
        else:
            lemmas = load_json('data/lemmas.json')
    if create_x:
        x_ray_conn, x_ray_path = create_x_ray_db(asin, book_path, lang['wiki'])
        if x_ray_conn is None:
            create_x = False

    if not ismacos:
        spacy_job(create_ww, create_x, book_path, is_kfx, lemmas,
                  ll_conn, model, lang, x_ray_conn, x_ray_path)
    elif create_ww:
        for text, start in parse_book(book_path, is_kfx):
            find_lemma(start, text, lemmas, ll_conn, is_kfx)

    if create_ww:
        save_db(ll_conn, ll_path)


def spacy_job(create_ww, create_x, book_path, is_kfx, lemmas,
              ll_conn, model, lang, x_ray_conn, x_ray_path):
    import spacy
    if create_ww:
        from spacy.matcher import PhraseMatcher
        nlp_en = spacy.blank('en')
        matcher = PhraseMatcher(nlp_en.vocab, attr='LOWER')
        patterns = list(
            nlp_en.pipe(
                filter(lambda x: ' ' in x or '-' in x, lemmas.keys())))
        matcher.add("phrases", patterns)
        if not create_x:
            for doc, start in nlp_en.pipe(
                    parse_book(book_path, is_kfx), as_tuples=True):
                find_phrase_and_lemma(
                    doc, matcher, start, lemmas, ll_conn, is_kfx)
    if create_x:
        nlp = spacy.load(model, exclude=[
                'tok2vec', 'morphologizer', 'tagger',
                'parser', 'attribute_ruler', 'lemmatizer'])
        nlp.enable_pipe("senter")
        x_ray = X_Ray(x_ray_conn, lang['wiki'])
        for doc, start in nlp.pipe(
                parse_book(book_path, is_kfx), as_tuples=True):
            find_named_entity(start, x_ray, doc, is_kfx)
            if create_ww:
                find_phrase_and_lemma(
                    doc, matcher, start, lemmas, ll_conn, is_kfx)

        x_ray.finish(x_ray_path)


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


def find_phrase_and_lemma(doc, matcher, start, lemmas, ll_conn, is_kfx):
    ranges = set()
    for span in matcher(doc, as_spans=True):
        lemma = doc.text[span.start_char:span.end_char].lower()
        if is_kfx:
            index = start + span.start_char
            end = index + len(lemma)
        else:
            index = start + len(doc.text[:span.start_char].encode('utf-8'))
            end = index + len(lemma.encode('utf-8'))
        insert_lemma(ll_conn, (index, end) + tuple(lemmas[lemma]))
        ranges.add(span.start_char)
    find_lemma(start, doc.text, lemmas, ll_conn, is_kfx, ranges)


def find_lemma(start, text, lemmas, ll_conn, is_kfx, ranges=None):
    from nltk.corpus import wordnet as wn

    for match in re.finditer(r"[a-zA-Z'\u00AD]{3,}", text):
        if ranges and match.start() in ranges:
            continue
        word = match.group(0).replace('\u00AD', '').lower()  # rm soft hyphens
        lemma = wn.morphy(word)
        lemma = lemma if lemma else word
        if lemma in lemmas:
            if is_kfx:
                index = start + match.start()
            else:
                index = start + len(text[:match.start()].encode('utf-8'))
            insert_lemma(ll_conn, (index, None) + tuple(lemmas[lemma]))


# https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L318
NER_LABELS = {
    'EVENT', 'FAC', 'GPE', 'LANGUAGE', 'LAW', 'LOC', 'NORP', 'ORG',
    'PERSON', 'PRODUCT', 'WORK_OF_ART', 'MISC', 'PER', 'FACILITY',
    'ORGANIZATION', 'NAT_REL_POL',  # Romanian
    'geogName', 'orgName', 'persName', 'placeName'  # Polish
}


def find_named_entity(start, x_ray, doc, is_kfx):
    len_limit = 3 if x_ray.lang == 'en' else 2

    for ent in doc.ents:
        if ent.label_ not in NER_LABELS:
            continue

        text = re.sub(r'^\W+', '', ent.text)
        text = re.sub(r'\W+$', '', text)
        if x_ray.lang == 'en':
            if re.match(r'c?hapter', text, re.IGNORECASE):
                continue
            text = re.sub(r'(?:\'s|’s)$', '', text)
            text = re.sub(r'^(?:the |an |a )', '', text, flags=re.IGNORECASE)

        if len(text) < len_limit or re.fullmatch(r'[\W\d]+', text):
            continue

        new_start_char = ent.start_char + ent.text.index(text)
        if is_kfx:
            ent_start = start + len(doc.text[:new_start_char])
            ent_len = len(text)
        else:
            ent_start = start + len(doc.text[:new_start_char].encode('utf-8'))
            ent_len = len(text.encode('utf-8'))

        x_ray.search(text, ent.label_ in ['PERSON', 'PER', 'persName'],
                     ent_start, ent.sent.text, ent_len)
