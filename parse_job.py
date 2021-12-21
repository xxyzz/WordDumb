#!/usr/bin/env python3
import re

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
    (asin, acr, revision, update_asin,
     kfx_json, mobi_html, mobi_codec) = get_asin_etc(book_path, is_kfx, mi)

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
        x_ray = X_Ray(
            x_ray_conn, lang['wiki'], kfx_json, mobi_html, mobi_codec)
        for doc, start in nlp.pipe(
                parse_book(kfx_json, mobi_html, mobi_codec), as_tuples=True):
            find_named_entity(start, x_ray, doc, mobi_codec)
            if create_ww:
                find_lemma(
                    start, doc.text, kw_processor, ll_conn, mobi_codec)

        x_ray.finish(x_ray_path)
    elif create_ww:
        for text, start in parse_book(kfx_json, mobi_html, mobi_codec):
            find_lemma(start, text, kw_processor, ll_conn, mobi_codec)

    if create_ww:
        save_db(ll_conn, ll_path)
    return book_id, asin, book_path, mi, update_asin


def parse_book(kfx_json, mobi_html, mobi_codec):
    if kfx_json:
        for entry in filter(lambda x: x['type'] == 1, kfx_json):
            yield (entry['content'], entry['position'])
    else:
        # match text inside HTML tags
        for match_text in re.finditer(b'>[^<>]+<', mobi_html):
            yield (match_text.group(0)[1:-1].decode(mobi_codec),
                   match_text.start() + 1)


def find_lemma(start, text, kw_processor, ll_conn, mobi_codec):
    for data, token_start, token_end in kw_processor.extract_keywords(
            text, span_info=True):
        end = None
        lemma = text[token_start:token_end]
        if mobi_codec:
            index = start + len(text[:token_start].encode(mobi_codec))
        else:
            index = start + token_start
        if ' ' in lemma:
            if mobi_codec:
                end = index + len(lemma.encode(mobi_codec))
            else:
                end = index + len(lemma)
        insert_lemma(ll_conn, (index, end) + tuple(data))


# https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L318
NER_LABELS = {
    'EVENT', 'FAC', 'GPE', 'LANGUAGE', 'LAW', 'LOC', 'NORP', 'ORG',
    'PERSON', 'PRODUCT', 'WORK_OF_ART', 'MISC', 'PER', 'FACILITY',
    'ORGANIZATION', 'NAT_REL_POL',  # Romanian
    'geogName', 'orgName', 'persName', 'placeName'  # Polish
}


def find_named_entity(start, x_ray, doc, mobi_codec):
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
        if mobi_codec:
            ent_start = start + len(
                doc.text[:new_start_char].encode(mobi_codec))
            ent_len = len(text.encode(mobi_codec))
        else:
            ent_start = start + len(doc.text[:new_start_char])
            ent_len = len(text)

        x_ray.search(text, ent.label_ in ['PERSON', 'PER', 'persName'],
                     ent_start, ent.sent.text, ent_len)
