#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path
from html import unescape

try:
    from .database import (
        create_lang_layer,
        create_x_ray_db,
        get_ll_path,
        get_x_ray_path,
        insert_lemma,
        save_db,
    )
    from .mediawiki import NER_LABELS, MediaWiki, Wikidata, Wikimedia_Commons
    from .utils import insert_lib_path, load_lemmas_dump
    from .x_ray import X_Ray
    from .x_ray_epub import X_Ray_EPUB
except ImportError:
    from database import (
        create_lang_layer,
        create_x_ray_db,
        get_ll_path,
        get_x_ray_path,
        insert_lemma,
        save_db,
    )
    from mediawiki import NER_LABELS, MediaWiki, Wikidata, Wikimedia_Commons
    from utils import insert_lib_path, load_lemmas_dump
    from x_ray import X_Ray
    from x_ray_epub import X_Ray_EPUB


def do_job(
    data, create_ww=True, create_x=True, abort=None, log=None, notifications=None
):
    from calibre.constants import ismacos
    from calibre.utils.config import config_dir
    from calibre_plugins.worddumb import VERSION

    from .config import prefs
    from .deps import InstallDeps
    from .metadata import get_asin_etc

    (book_id, book_fmt, book_path, mi, lang) = data
    (asin, acr, revision, update_asin, kfx_json, mobi_html, mobi_codec) = get_asin_etc(
        book_path, book_fmt, mi
    )

    model = lang["spacy"] + prefs["model_size"]
    plugin_path = str(Path(config_dir).joinpath("plugins/WordDumb.zip"))
    if book_fmt == "EPUB":
        book_path = Path(book_path)
        # Python 3.9, PurePath.with_stem
        new_epub_path = book_path.with_name(f"{book_path.stem}_x_ray.epub")
        create_x = create_x and not new_epub_path.exists()
    else:
        create_ww = create_ww and not get_ll_path(asin, book_path).exists()
        create_x = create_x and not get_x_ray_path(asin, book_path).exists()
    if create_x:
        install_deps = InstallDeps(model, plugin_path, book_fmt, notifications)

    if notifications:
        notifications.put((0, "Creating files"))

    version = ".".join(map(str, VERSION))
    if ismacos and create_x:
        args = [
            install_deps.py,
            plugin_path,
            asin,
            book_path,
            acr,
            revision,
            model,
            lang["wiki"],
            mobi_codec,
            plugin_path,
            version,
            prefs["zh_wiki_variant"],
            prefs["fandom"],
            book_fmt,
        ]
        if create_ww:
            args.append("-l")
        if prefs["search_people"]:
            args.append("-s")
        if prefs["add_locator_map"]:
            args.append("-m")
        if book_fmt == "KFX":
            input_str = json.dumps(kfx_json)
        elif book_fmt == "EPUB":
            input_str = ""
        else:
            input_str = mobi_html.decode(mobi_codec)

        subprocess.run(
            args, input=input_str, check=True, capture_output=True, text=True
        )
    else:
        create_files(
            create_ww,
            create_x,
            asin,
            book_path,
            acr,
            revision,
            model,
            lang["wiki"],
            kfx_json,
            mobi_html,
            mobi_codec,
            plugin_path,
            version,
            prefs,
            notifications,
        )

    if book_fmt == "EPUB":
        book_path = new_epub_path
    return book_id, asin, book_path, mi, update_asin, book_fmt, acr


def calulate_final_start(kfx_json, mobi_html):
    if kfx_json:
        return kfx_json[-1]["position"] + len(kfx_json[-1]["content"])
    elif mobi_html:
        return len(mobi_html)
    return 0


def create_files(
    create_ww,
    create_x,
    asin,
    book_path,
    acr,
    revision,
    model,
    wiki_lang,
    kfx_json,
    mobi_html,
    mobi_codec,
    plugin_path,
    plugin_version,
    prefs,
    notif,
):
    final_start = calulate_final_start(kfx_json, mobi_html)

    if create_ww:
        ll_conn, ll_path = create_lang_layer(asin, book_path, acr, revision)
        kw_processor = load_lemmas_dump(plugin_path)

    if create_x:
        for path in Path(plugin_path).parent.glob("worddumb-libs-py*"):
            insert_lib_path(str(path))
        import spacy

        nlp = spacy.load(
            model,
            exclude=[
                "tok2vec",
                "morphologizer",
                "tagger",
                "parser",
                "attribute_ruler",
                "lemmatizer",
            ],
        )
        nlp.enable_pipe("senter")
        useragent = f"WordDumb/{plugin_version} (https://github.com/xxyzz/WordDumb)"
        mediawiki = MediaWiki(wiki_lang, useragent, plugin_path, prefs)
        wikidata = None if prefs["fandom"] else Wikidata(plugin_path, useragent)
        wiki_commons = None

        if not kfx_json and not mobi_codec:  # EPUB
            if not prefs["fandom"] and prefs["add_locator_map"]:
                wiki_commons = Wikimedia_Commons(plugin_path, useragent)
            x_ray = X_Ray_EPUB(book_path, mediawiki, wiki_commons, wikidata)
            for doc, data in nlp.pipe(x_ray.extract_epub(), as_tuples=True):
                find_named_entity(
                    data[0], x_ray, doc, None, wiki_lang, data[1], data[2]
                )
            x_ray.modify_epub(prefs["search_people"])
            return

        x_ray_conn, x_ray_path = create_x_ray_db(
            asin, book_path, wiki_lang, plugin_path, prefs
        )
        x_ray = X_Ray(x_ray_conn, mediawiki, wikidata)
        for doc, context in nlp.pipe(
            parse_book(kfx_json, mobi_html, mobi_codec), as_tuples=True
        ):
            if kfx_json:
                start = context
                escaped_text = None
            else:
                start, escaped_text = context
            find_named_entity(start, x_ray, doc, mobi_codec, wiki_lang, escaped_text)
            if create_ww:
                find_lemma(
                    start, doc.text, kw_processor, ll_conn, mobi_codec, escaped_text
                )
            if notif:
                notif.put((start / final_start, "Creating files"))

        x_ray.finish(
            x_ray_path,
            final_start,
            kfx_json,
            mobi_html,
            mobi_codec,
            prefs["search_people"],
        )
    elif create_ww:
        for text, context in parse_book(kfx_json, mobi_html, mobi_codec):
            find_lemma(
                context if kfx_json else context[0],
                text,
                kw_processor,
                ll_conn,
                mobi_codec,
                None if kfx_json else context[1],
            )

    if create_ww:
        save_db(ll_conn, ll_path)


def parse_book(kfx_json, mobi_html, mobi_codec):
    if kfx_json:
        for entry in filter(lambda x: x["type"] == 1, kfx_json):
            yield entry["content"], entry["position"]
    else:
        # match text inside HTML tags
        for match_body in re.finditer(b"<body.{3,}?</body>", mobi_html, re.DOTALL):
            for m in re.finditer(b">[^<]{2,}<", match_body.group(0)):
                text = m.group(0)[1:-1].decode(mobi_codec)
                yield unescape(text), (match_body.start() + m.start() + 1, text)


def index_in_escaped_text(token, escaped_text, start_offset):
    if token in escaped_text[start_offset:]:
        token_start = escaped_text.index(token, start_offset)
        return token_start, token_start + len(token)
    else:
        words = list(filter(None, re.split(r"\W+", token)))
        token_start = escaped_text.index(words[0], start_offset)
        token_end = escaped_text.index(words[-1], token_start) + len(words[-1])
        return token_start, token_end


def find_lemma(start, text, kw_processor, ll_conn, mobi_codec, escaped_text):
    starts = set()
    for data, token_start, token_end in kw_processor.extract_keywords(
        text, span_info=True
    ):
        end = None
        lemma = text[token_start:token_end]
        if mobi_codec:
            lemma_start, lemma_end = index_in_escaped_text(
                lemma, escaped_text, token_start
            )
            index = start + len(escaped_text[:lemma_start].encode(mobi_codec))
        else:
            index = start + token_start
        if index in starts:
            continue
        else:
            starts.add(index)
        if " " in lemma:
            if mobi_codec:
                end = index + len(
                    escaped_text[lemma_start:lemma_end].encode(mobi_codec)
                )
            else:
                end = index + len(lemma)
        insert_lemma(ll_conn, (index, end) + tuple(data))


def find_named_entity(
    start, x_ray, doc, mobi_codec, lang, escaped_text, xhtml_path=None
):
    len_limit = 3 if lang == "en" else 2
    starts = set()
    for ent in filter(lambda x: x.label_ in NER_LABELS, doc.ents):
        text = re.sub(r"^\W+", "", ent.text)
        text = re.sub(r"\W+$", "", text)
        if lang == "en":
            if re.match(r"c?hapter", text, re.IGNORECASE):
                continue
            text = re.sub(r"['’][sd]$", "", text)
            text = re.sub(r"^(?:the|an?) ", "", text, flags=re.IGNORECASE)
            text = re.sub(r"^\W+", "", text)
            if text.lower() in [
                "north",
                "east",
                "south",
                "west",
                "northeast",
                "southeast",
                "southwest",
                "northwest",
            ]:
                continue
        if lang == "es":
            # https://en.wikipedia.org/wiki/Spanish_determiners#Articles
            text = re.sub(
                r"^(?:el|los?|las?|un|unos?|unas?) ", "", text, flags=re.IGNORECASE
            )
            text = re.sub(r"^\W+", "", text)
        # TODO https://en.wikipedia.org/wiki/Article_(grammar)#Tables

        if len(text) < len_limit or re.fullmatch(r"[\W\d]+", text):
            continue

        if escaped_text:
            start_char, end_char = index_in_escaped_text(
                text, escaped_text, ent.start_char
            )
        else:
            start_char = ent.start_char + ent.text.index(text)
            end_char = start_char + len(text)
        book_text = escaped_text if escaped_text else doc.text
        selectable_text = book_text[start_char:end_char]
        if start_char in starts:
            continue
        else:
            starts.add(start_char)

        if xhtml_path:  # EPUB
            x_ray.add_entity(
                text,
                ent.label_,
                ent.sent.text.strip(),
                start + start_char,
                start + end_char,
                xhtml_path,
                selectable_text,
            )
            continue

        if m := re.search(r"\s", book_text[end_char:]):
            selectable_text = book_text[start_char : end_char + m.start()]
        if mobi_codec:
            ent_start = start + len(escaped_text[:start_char].encode(mobi_codec))
            ent_len = len(selectable_text.encode(mobi_codec))
        else:
            ent_start = start + start_char
            ent_len = len(selectable_text)

        x_ray.add_entity(text, ent.label_, ent_start, ent.sent.text.strip(), ent_len)
