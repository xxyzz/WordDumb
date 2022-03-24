#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from .database import (create_lang_layer, create_x_ray_db, get_ll_path,
                           get_x_ray_path, insert_lemma, save_db)
    from .mediawiki import MediaWiki, Wikimedia_Commons
    from .unzip import load_json_or_pickle
    from .x_ray import X_Ray
    from .x_ray_epub import X_Ray_EPUB
except ImportError:
    from database import (create_lang_layer, create_x_ray_db, get_ll_path,
                          get_x_ray_path, insert_lemma, save_db)
    from mediawiki import MediaWiki, Wikimedia_Commons
    from unzip import load_json_or_pickle
    from x_ray import X_Ray
    from x_ray_epub import X_Ray_EPUB


def do_job(data, create_ww=True, create_x=True,
           abort=None, log=None, notifications=None):
    from calibre.constants import ismacos
    from calibre.utils.config import config_dir
    from calibre_plugins.worddumb import VERSION

    from .config import prefs
    from .deps import InstallDeps
    from .metadata import get_asin_etc

    (book_id, book_fmt, book_path, mi, lang) = data
    (asin, acr, revision, update_asin,
     kfx_json, mobi_html, mobi_codec) = get_asin_etc(book_path, book_fmt, mi)

    model = lang['spacy'] + prefs['model_size']
    plugin_path = str(Path(config_dir).joinpath('plugins/WordDumb.zip'))
    if book_fmt == 'EPUB':
        book_path = Path(book_path)
        new_epub_path = book_path.with_name(  # Python 3.9, PurePath.with_stem
            f'{book_path.stem}_x_ray.epub')
        create_x = create_x and not new_epub_path.exists()
    else:
        create_ww = create_ww and not get_ll_path(asin, book_path).exists()
        create_x = create_x and not get_x_ray_path(asin, book_path).exists()
    if create_x:
        install_deps = InstallDeps(model, plugin_path, book_fmt, notifications)

    if notifications:
        notifications.put((0, 'Creating files'))

    version = '.'.join(map(str, VERSION))
    if ismacos and create_x:
        args = [install_deps.py, plugin_path, asin, book_path, acr, revision,
                model, lang['wiki'], mobi_codec, plugin_path, version,
                prefs['zh_wiki_variant'], prefs['fandom'], book_fmt]
        if create_ww:
            args.append('-l')
        if prefs['search_people']:
            args.append('-s')
        if book_fmt == 'KFX':
            input_str = json.dumps(kfx_json)
        elif book_fmt == 'EPUB':
            input_str = ''
        else:
            input_str = mobi_html.decode(mobi_codec)

        subprocess.run(
            args, input=input_str, check=True, capture_output=True, text=True)
    else:
        create_files(
            create_ww, create_x, asin, book_path, acr, revision, model,
            lang['wiki'], kfx_json, mobi_html, mobi_codec, plugin_path,
            version, prefs['zh_wiki_variant'], prefs['search_people'],
            prefs['fandom'], notifications)

    if book_fmt == 'EPUB':
        book_path = new_epub_path
    return book_id, asin, book_path, mi, update_asin, book_fmt


def insert_lib_path(path):
    if path not in sys.path:
        sys.path.insert(0, path)


def calulate_last_start(notif, kfx_json, mobi_html):
    if notif:
        if kfx_json:
            return max(d['position'] for d in kfx_json if d['type'] == 1)
        elif mobi_html:
            return len(mobi_html)
    return 0


def create_files(create_ww, create_x, asin, book_path, acr, revision, model,
                 wiki_lang, kfx_json, mobi_html, mobi_codec, plugin_path,
                 plugin_version, zh_wiki, search_people, fandom_url, notif):
    last_start = calulate_last_start(notif, kfx_json, mobi_html)

    if create_ww:
        ll_conn, ll_path = create_lang_layer(asin, book_path, acr, revision)
        insert_lib_path(str(Path(plugin_path).joinpath('libs')))  # flashtext
        kw_processor = load_json_or_pickle(plugin_path, 'lemmas_dump')

    if create_x:
        for path in Path(plugin_path).parent.glob('worddumb-libs-py*'):
            insert_lib_path(str(path))
        import spacy

        nlp = spacy.load(model, exclude=[
            'tok2vec', 'morphologizer', 'tagger',
            'parser', 'attribute_ruler', 'lemmatizer'])
        nlp.enable_pipe("senter")
        mediawiki = MediaWiki(
            wiki_lang, plugin_version, plugin_path, zh_wiki, fandom_url)

        if not kfx_json and not mobi_codec:
            commons = Wikimedia_Commons(
                wiki_lang, plugin_path, plugin_version, zh_wiki)
            x_ray = X_Ray_EPUB(book_path, search_people, mediawiki, commons)
            for doc, data in nlp.pipe(x_ray.extract_epub(), as_tuples=True):
                find_named_entity(
                    data[0], x_ray, doc, None, wiki_lang, data[1])
            x_ray.modify_epub()
            return

        x_ray_conn, x_ray_path = create_x_ray_db(
            asin, book_path, wiki_lang, plugin_path, zh_wiki, fandom_url)
        x_ray = X_Ray(x_ray_conn, kfx_json, mobi_html, mobi_codec,
                      search_people, mediawiki)
        for doc, start in nlp.pipe(
                parse_book(kfx_json, mobi_html, mobi_codec), as_tuples=True):
            find_named_entity(start, x_ray, doc, mobi_codec, wiki_lang)
            if create_ww:
                find_lemma(
                    start, doc.text, kw_processor, ll_conn, mobi_codec)
            if notif:
                notif.put((start / last_start, 'Creating files'))

        x_ray.finish(x_ray_path)
    elif create_ww:
        for text, start in parse_book(kfx_json, mobi_html, mobi_codec):
            find_lemma(start, text, kw_processor, ll_conn, mobi_codec)

    if create_ww:
        save_db(ll_conn, ll_path)


def parse_book(kfx_json, mobi_html, mobi_codec):
    if kfx_json:
        return ((e['content'],
                 e['position']) for e in kfx_json if e['type'] == 1)
    else:
        # match text inside HTML tags
        return ((m.group(0)[1:-1].decode(mobi_codec),
                 m.start() + 1) for m in re.finditer(b'>[^<>]+<', mobi_html))


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
    'EVENT', 'FAC', 'GPE', 'LAW', 'LOC', 'ORG',
    'PERSON', 'PRODUCT', 'WORK_OF_ART',
    'MISC', 'PER',  # Catalan
    'ORGANIZATION',  # Romanian
    "EVT", "GPE_LOC", "GPE_ORG", "PROD",  # Norwegian Bokmål
    'geogName', 'orgName', 'persName', 'placeName'  # Polish
}
PERSON_LABELS = ['PERSON', 'PER', 'persName']


def find_named_entity(start, x_ray, doc, mobi_codec, lang, xhtml_path=None):
    len_limit = 3 if lang == 'en' else 2

    for ent in doc.ents:
        if ent.label_ not in NER_LABELS:
            continue

        text = re.sub(r'^\W+', '', ent.text)
        text = re.sub(r'\W+$', '', text)
        if lang == 'en':
            if re.match(r'c?hapter', text, re.IGNORECASE):
                continue
            text = re.sub(r"['’][sd]$", '', text)
            text = re.sub(r'^(?:the|an?) ', '', text, flags=re.IGNORECASE)
        if lang == 'es':
            # https://en.wikipedia.org/wiki/Spanish_determiners#Articles
            text = re.sub(r'^(?:el|los?|las?|un|unos?|unas?) ', '',
                          text, flags=re.IGNORECASE)
        # TODO https://en.wikipedia.org/wiki/Article_(grammar)#Tables

        if len(text) < len_limit or re.fullmatch(r'[\W\d]+', text):
            continue

        new_start_char = ent.start_char + ent.text.index(text)
        if xhtml_path:  # EPUB
            x_ray.search(text, ent.label_ in PERSON_LABELS,
                         ent.sent.text, start + new_start_char,
                         start + new_start_char + len(text), xhtml_path)
            continue

        selectable_text = text
        if lang == 'en' and (m := re.search(r'\s', doc.text[ent.end_char:])):
            selectable_text = doc.text[new_start_char:ent.end_char + m.start()]
        if mobi_codec:
            ent_start = start + len(
                doc.text[:new_start_char].encode(mobi_codec))
            ent_len = len(selectable_text.encode(mobi_codec))
        else:
            ent_start = start + len(doc.text[:new_start_char])
            ent_len = len(selectable_text)

        x_ray.search(text, ent.label_ in PERSON_LABELS,
                     ent_start, ent.sent.text, ent_len)
