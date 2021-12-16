#!/usr/bin/env python3
import json
import re

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.reader.mobi8 import Mobi8Reader
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import (create_lang_layer,
                                               create_x_ray_db, insert_lemma,
                                               save_db)
from calibre_plugins.worddumb.metadata import get_asin_etc
from calibre_plugins.worddumb.unzip import install_libs, load_json_or_pickle
from calibre_plugins.worddumb.x_ray import X_Ray


def do_job(data, create_ww=True, create_x=True,
           abort=None, log=None, notifications=None):
    (book_id, book_fmt, book_path, mi, lang) = data
    is_kfx = book_fmt == 'KFX'
    asin, acr, revision, update_asin, yj_book, codec = get_asin_etc(
        book_path, is_kfx, mi)
    model = lang['spacy'] + prefs['model_size']
    install_libs(model, create_ww, create_x, notifications)

    if create_ww:
        ll_conn, ll_path = create_lang_layer(asin, book_path, acr, revision)
        if ll_conn is None:
            create_ww = False
        else:
            kw_processor = load_json_or_pickle('lemmas_dump', False)
    if create_x:
        x_ray_conn, x_ray_path = create_x_ray_db(asin, book_path, lang['wiki'])
        if x_ray_conn is None:
            create_x = False

    if notifications:
        notifications.put((0, 'Creating files'))
    if create_x:
        import spacy
        nlp = spacy.load(model, exclude=[
            'tok2vec', 'morphologizer', 'tagger',
            'parser', 'attribute_ruler', 'lemmatizer'])
        nlp.enable_pipe("senter")
        x_ray = X_Ray(x_ray_conn, lang['wiki'])
        for doc, start in nlp.pipe(
                parse_book(book_path, yj_book), as_tuples=True):
            find_named_entity(start, x_ray, doc, is_kfx, codec)
            if create_ww:
                find_lemma(
                    start, doc.text, kw_processor, ll_conn, is_kfx, codec)

        x_ray.finish(x_ray_path)
    elif create_ww:
        for text, start in parse_book(book_path, yj_book):
            find_lemma(start, text, kw_processor, ll_conn, is_kfx, codec)

    if create_ww:
        save_db(ll_conn, ll_path)
    return book_id, asin, book_path, mi, update_asin


def parse_book(book_path, yj_book):
    if yj_book:
        for entry in json.loads(yj_book.convert_to_json_content())['data']:
            yield (entry['content'], entry['position'])
    else:
        yield from parse_mobi(book_path)


def parse_mobi(book_path):
    # use code from calibre.ebooks.mobi.reader.mobi8:Mobi8Reader.__call__
    # and calibre.ebook.conversion.plugins.mobi_input:MOBIInput.convert
    # https://github.com/kevinhendricks/KindleUnpack/blob/master/lib/mobi_k8proc.py#L216
    with open(book_path, 'rb') as f:
        mr = MobiReader(f)
        if mr.kf8_type == 'joint':
            raise Exception('JointMOBI')
        mr.check_for_drm()
        mr.extract_text()
        html = mr.mobi_html
        if mr.kf8_type == 'standalone':
            m8r = Mobi8Reader(mr, mr.log)
            m8r.kf8_sections = mr.sections
            m8r.read_indices()
            m8r.build_parts()
            html = b''.join(m8r.parts)

    # match text between HTML tags
    for match_text in re.finditer(b'>[^<>]+<', html):
        yield (match_text.group(0)[1:-1].decode(mr.book_header.codec),
               match_text.start() + 1)


def find_lemma(start, text, kw_processor, ll_conn, is_kfx, codec):
    for data, token_start, token_end in kw_processor.extract_keywords(
            text, span_info=True):
        end = None
        lemma = text[token_start:token_end]
        if is_kfx:
            index = start + token_start
        else:
            index = start + len(text[:token_start].encode(codec))
        if ' ' in lemma:
            end = index + len(lemma) if is_kfx else index + len(
                lemma.encode(codec))
        insert_lemma(ll_conn, (index, end) + tuple(data))


# https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L318
NER_LABELS = {
    'EVENT', 'FAC', 'GPE', 'LANGUAGE', 'LAW', 'LOC', 'NORP', 'ORG',
    'PERSON', 'PRODUCT', 'WORK_OF_ART', 'MISC', 'PER', 'FACILITY',
    'ORGANIZATION', 'NAT_REL_POL',  # Romanian
    'geogName', 'orgName', 'persName', 'placeName'  # Polish
}


def find_named_entity(start, x_ray, doc, is_kfx, codec):
    len_limit = 3 if x_ray.lang == 'en' else 2

    for ent in doc.ents:
        if ent.label_ not in NER_LABELS:
            continue

        text = re.sub(r'^\W+', '', ent.text)
        text = re.sub(r'\W+$', '', text)
        if x_ray.lang == 'en':
            if re.match(r'c?hapter', text, re.IGNORECASE):
                continue
            text = re.sub(r"['’][sd]$", '', text)
            text = re.sub(r'^(?:the|an?) ', '', text, flags=re.IGNORECASE)

        if len(text) < len_limit or re.fullmatch(r'[\W\d]+', text):
            continue

        new_start_char = ent.start_char + ent.text.index(text)
        if is_kfx:
            ent_start = start + len(doc.text[:new_start_char])
            ent_len = len(text)
        else:
            ent_start = start + len(doc.text[:new_start_char].encode(codec))
            ent_len = len(text.encode(codec))

        x_ray.search(text, ent.label_ in ['PERSON', 'PER', 'persName'],
                     ent_start, ent.sent.text, ent_len)
