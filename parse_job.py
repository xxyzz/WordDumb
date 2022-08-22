#!/usr/bin/env python3
import json
import random
import re
from html import escape, unescape
from pathlib import Path

try:
    from calibre.constants import ismacos

    from .database import (
        create_lang_layer,
        create_x_ray_db,
        get_ll_path,
        get_x_ray_path,
        insert_lemma,
        save_db,
    )
    from .deps import download_wiktionary, install_deps, mac_python
    from .epub import EPUB
    from .interval import Interval, IntervalTree
    from .mediawiki import NER_LABELS, MediaWiki, Wikidata, Wikimedia_Commons
    from .utils import (
        CJK_LANGS,
        get_custom_x_path,
        get_plugin_path,
        get_user_agent,
        insert_installed_libs,
        load_custom_x_desc,
        load_lemmas_dump,
        run_subprocess,
        wiktionary_dump_path,
    )
    from .x_ray import X_Ray
except ImportError:
    from database import (
        create_lang_layer,
        create_x_ray_db,
        get_ll_path,
        get_x_ray_path,
        insert_lemma,
        save_db,
    )
    from epub import EPUB
    from interval import Interval, IntervalTree
    from mediawiki import NER_LABELS, MediaWiki, Wikidata, Wikimedia_Commons
    from utils import (
        CJK_LANGS,
        get_custom_x_path,
        insert_installed_libs,
        load_custom_x_desc,
        load_lemmas_dump,
    )
    from x_ray import X_Ray


def do_job(
    data, create_ww=True, create_x=True, abort=None, log=None, notifications=None
):
    from .config import prefs
    from .metadata import get_asin_etc

    (book_id, book_fmt, book_path, mi, lang) = data
    (asin, acr, revision, update_asin, kfx_json, mobi_html, mobi_codec) = get_asin_etc(
        book_path, book_fmt, mi
    )

    model = lang["spacy"] + prefs["model_size"]
    plugin_path = get_plugin_path()
    useragent = get_user_agent()
    if book_fmt == "EPUB":
        book_path = Path(book_path)
        new_file_stem = book_path.stem
        if create_x:
            new_file_stem += "_x_ray"
        if create_ww:
            new_file_stem += "_word_wise"
        new_epub_path = book_path.with_stem(new_file_stem)
        create_x = create_x and not new_epub_path.exists()
        create_ww = create_ww and not new_epub_path.exists()
        if create_ww and not wiktionary_dump_path(plugin_path, lang["wiki"]).exists():
            download_wiktionary(lang["wiki"], notifications=notifications)
    else:
        create_ww = create_ww and not get_ll_path(asin, book_path).exists()
        create_x = create_x and not get_x_ray_path(asin, book_path).exists()

    return_values = (
        book_id,
        asin,
        new_epub_path if book_fmt == "EPUB" else book_path,
        mi,
        update_asin,
        book_fmt,
        acr,
    )
    if not create_ww and not create_x:
        return return_values

    if create_x:
        install_deps(model, book_fmt, notifications)

    if notifications:
        notifications.put((0, "Creating files"))

    if ismacos and (
        create_x or (book_fmt == "EPUB" and create_ww and lang["wiki"] in CJK_LANGS)
    ):
        plugin_path = str(plugin_path)
        args = [
            mac_python(),
            plugin_path,
            asin,
            book_path,
            acr,
            revision,
            model,
            lang["wiki"],
            mobi_codec,
            useragent,
            prefs["zh_wiki_variant"],
            prefs["fandom"],
            book_fmt,
            str(prefs["minimal_x_ray_count"]),
            plugin_path,
            "",
        ]
        if create_ww:
            args.append("-l")
        if create_x:
            args.append("-x")
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

        run_subprocess(args, input_str)
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
            useragent,
            prefs,
            notifications,
        )

    return return_values


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
    useragent,
    prefs,
    notif,
):
    is_epub = not kfx_json and not mobi_codec
    if isinstance(plugin_path, str):
        plugin_path = Path(plugin_path)
    kw_processor = None
    if create_ww:
        kw_processor = load_lemmas_dump(plugin_path, wiki_lang if is_epub else None)

    if create_x:
        insert_installed_libs(plugin_path)
        nlp = load_spacy(model, book_path)
        mediawiki = MediaWiki(wiki_lang, useragent, plugin_path, prefs)
        wikidata = None if prefs["fandom"] else Wikidata(plugin_path, useragent)
        custom_x_ray = load_custom_x_desc(book_path)

    if is_epub:
        if create_x:
            wiki_commons = None
            if not prefs["fandom"] and prefs["add_locator_map"]:
                wiki_commons = Wikimedia_Commons(plugin_path, useragent)
            epub = EPUB(
                book_path, mediawiki, wiki_commons, wikidata, custom_x_ray, kw_processor
            )
            for doc, (start, escaped_text, xhtml_path) in nlp.pipe(
                epub.extract_epub(), as_tuples=True
            ):
                intervals = find_named_entity(
                    start,
                    epub,
                    doc,
                    None,
                    wiki_lang,
                    escaped_text,
                    custom_x_ray,
                    xhtml_path,
                )
                if create_ww:
                    random.shuffle(intervals)
                    interval_tree = IntervalTree()
                    interval_tree.insert_intervals(intervals)
                    epub_find_lemma(
                        start,
                        doc.text,
                        kw_processor,
                        escaped_text,
                        xhtml_path,
                        epub,
                        interval_tree,
                    )
        elif create_ww:
            epub = EPUB(book_path, None, None, None, None, kw_processor)
            for text, (start, escaped_text, xhtml_path) in epub.extract_epub():
                epub_find_lemma(
                    start, text, kw_processor, escaped_text, xhtml_path, epub
                )
        epub.modify_epub(prefs, wiki_lang)
        return

    # Kindle
    final_start = calulate_final_start(kfx_json, mobi_html)
    if create_ww:
        ll_conn, ll_path = create_lang_layer(asin, book_path, acr, revision)

    if create_x:
        x_ray_conn, x_ray_path = create_x_ray_db(
            asin, book_path, wiki_lang, plugin_path, prefs
        )
        x_ray = X_Ray(x_ray_conn, mediawiki, wikidata, custom_x_ray)
        for doc, context in nlp.pipe(
            parse_book(kfx_json, mobi_html, mobi_codec), as_tuples=True
        ):
            if kfx_json:
                start = context
                escaped_text = None
            else:
                start, escaped_text = context
            find_named_entity(
                start, x_ray, doc, mobi_codec, wiki_lang, escaped_text, custom_x_ray
            )
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
            prefs,
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
                text = m.group(0)[1:-1].decode(mobi_codec).replace("\n", " ")
                yield unescape(text), (match_body.start() + m.start() + 1, text)


def index_in_escaped_text(token, escaped_text, start_offset):
    if token not in escaped_text[start_offset:]:
        # replace Unicode character to numeric character reference
        token = escape(token, False).encode("ascii", "xmlcharrefreplace").decode()

    if token in escaped_text[start_offset:]:
        token_start = escaped_text.index(token, start_offset)
        return token_start, token_start + len(token)
    else:
        return None, None


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
            if lemma_start is None:
                continue
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


def epub_find_lemma(
    start, text, kw_processor, escaped_text, xhtml_path, epub, interval_tree=None
):
    from flashtext import KeywordProcessor

    starts = set()
    if isinstance(kw_processor, KeywordProcessor):
        for data, token_start, token_end in kw_processor.extract_keywords(
            text, span_info=True
        ):
            epub_add_lemma(
                token_start,
                token_end,
                interval_tree,
                text,
                escaped_text,
                start,
                starts,
                epub,
                xhtml_path,
            )
    else:
        for token_end, data in kw_processor.iter_long(text):
            epub_add_lemma(
                token_end + 1 - len(data[0]),
                token_end + 1,
                interval_tree,
                text,
                escaped_text,
                start,
                starts,
                epub,
                xhtml_path,
            )


def epub_add_lemma(
    token_start,
    token_end,
    interval_tree,
    text,
    escaped_text,
    start,
    starts,
    epub,
    xhtml_path,
):
    lemma = text[token_start:token_end]
    lemma_start, lemma_end = index_in_escaped_text(lemma, escaped_text, token_start)
    if lemma_start is None or lemma_start in starts:
        return
    if interval_tree and interval_tree.is_overlap(Interval(lemma_start, lemma_end - 1)):
        return

    starts.add(lemma_start)
    epub.add_lemma(
        lemma,
        start + lemma_start,
        start + lemma_end,
        xhtml_path,
        escaped_text[lemma_start:lemma_end],
    )


DIRECTIONS = frozenset(
    [
        "north",
        "east",
        "south",
        "west",
        "northeast",
        "southeast",
        "southwest",
        "northwest",
    ]
)


def process_entity(text, lang, len_limit):
    if re.search(r"https?:|www\.", text, re.IGNORECASE):
        return None
    text = re.sub(r"^\W+", "", text)
    text = re.sub(r"\W+$", "", text)

    if lang == "en":
        # ignore chapter title(chapter 1) and page number reference(pp. 1-10)
        if re.match(r"c?hapter|p{1,2}[\W\d]{2,}", text, re.IGNORECASE):
            return None
        text = re.sub(r"\W+[sd]$|\s+of$", "", text)
        text = re.sub(r"^(?:the|an?)\s", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^\W+", "", text)
        if text.lower() in DIRECTIONS:
            return None
    elif lang == "es":
        # https://en.wikipedia.org/wiki/Spanish_determiners#Articles
        text = re.sub(
            r"^(?:el|los?|las?|un|unos?|unas?)\s", "", text, flags=re.IGNORECASE
        )
        text = re.sub(r"^\W+", "", text)
    # TODO https://en.wikipedia.org/wiki/Article_(grammar)#Tables

    if len(text) < len_limit or re.fullmatch(r"[\W\d]+", text):
        return None

    return text


def find_named_entity(
    start, x_ray, doc, mobi_codec, lang, escaped_text, custom_x_ray, xhtml_path=None
):
    len_limit = 2 if lang in CJK_LANGS else 3
    starts = set()
    intervals = []
    for ent in filter(lambda x: x.label_ in NER_LABELS, doc.ents):
        text = (
            ent.ent_id_  # customized X-Ray
            if ent.ent_id_
            else process_entity(ent.text, lang, len_limit)
        )
        if text is None or (ent.ent_id_ and custom_x_ray.get(ent.ent_id_)[2]):
            continue

        ent_text = ent.text if ent.ent_id_ else text
        if escaped_text:
            start_char, end_char = index_in_escaped_text(
                ent_text, escaped_text, ent.start_char
            )
            if start_char is None:
                continue
        elif not ent.ent_id_:
            start_char = ent.start_char + ent.text.index(ent_text)
            end_char = start_char + len(ent_text)
        else:
            start_char = ent.start_char
            end_char = ent.end_char
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
            intervals.append(Interval(start_char, end_char - 1))
            continue

        # Include the next punctuation so the word can be selected on Kindle
        if re.match(r"[^\w\s]", book_text[end_char : end_char + 1]):
            selectable_text = book_text[start_char : end_char + 1]
        if mobi_codec:
            ent_start = start + len(escaped_text[:start_char].encode(mobi_codec))
            ent_len = len(selectable_text.encode(mobi_codec))
        else:
            ent_start = start + start_char
            ent_len = len(selectable_text)

        x_ray.add_entity(text, ent.label_, ent_start, ent.sent.text.strip(), ent_len)

    return intervals


def load_spacy(model, book_path):
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
    # simpler and faster https://spacy.io/usage/linguistic-features#sbd
    nlp.enable_pipe("senter")

    custom_x_path = get_custom_x_path(book_path)
    if custom_x_path.exists():
        ruler = nlp.add_pipe("entity_ruler", before="ner")
        patterns = []
        with custom_x_path.open(encoding="utf-8") as f:
            for name, label, aliases, *_ in json.load(f):
                patterns.append({"label": label, "pattern": name, "id": name})
                for alias in [x.strip() for x in aliases.split(",")]:
                    patterns.append({"label": label, "pattern": alias, "id": name})
        ruler.add_patterns(patterns)
    return nlp
