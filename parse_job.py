import json
import random
import re
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from html import escape, unescape
from itertools import chain
from pathlib import Path
from sqlite3 import Connection
from typing import Any, Iterator

try:
    from calibre.constants import isfrozen

    from .database import (
        create_lang_layer,
        create_x_ray_db,
        get_ll_path,
        get_x_ray_path,
        insert_lemma,
        save_db,
    )
    from .deps import download_word_wise_file, install_deps, which_python
    from .dump_lemmas import save_spacy_docs, spacy_doc_path
    from .epub import EPUB, spacy_to_wiktionary_pos
    from .interval import Interval, IntervalTree
    from .mediawiki import MediaWiki, Wikidata, Wikimedia_Commons
    from .metadata import KFXJson
    from .utils import (
        CJK_LANGS,
        Prefs,
        dump_prefs,
        get_plugin_path,
        get_spacy_model_version,
        get_user_agent,
        get_wiktionary_klld_path,
        insert_installed_libs,
        kindle_db_path,
        load_languages_data,
        load_plugin_json,
        run_subprocess,
        spacy_model_name,
        use_kindle_ww_db,
        wiktionary_db_path,
    )
    from .x_ray import X_Ray
    from .x_ray_share import (
        NER_LABELS,
        CustomXDict,
        get_custom_x_path,
        load_custom_x_desc,
    )
except ImportError:
    isfrozen = False
    from database import (
        create_lang_layer,
        create_x_ray_db,
        get_ll_path,
        get_x_ray_path,
        insert_lemma,
        save_db,
    )
    from dump_lemmas import save_spacy_docs, spacy_doc_path
    from epub import EPUB, spacy_to_wiktionary_pos
    from interval import Interval, IntervalTree
    from mediawiki import MediaWiki, Wikidata, Wikimedia_Commons
    from metadata import KFXJson
    from utils import (
        CJK_LANGS,
        Prefs,
        get_spacy_model_version,
        insert_installed_libs,
        kindle_db_path,
        load_languages_data,
        load_plugin_json,
        use_kindle_ww_db,
        wiktionary_db_path,
    )
    from x_ray import X_Ray
    from x_ray_share import (
        NER_LABELS,
        CustomXDict,
        get_custom_x_path,
        load_custom_x_desc,
    )


@dataclass
class ParseJobData:
    book_id: int = 0
    book_path: str = ""
    mi: Any = None
    book_fmt: str = ""
    book_lang: str = ""  # 639-2 language code
    useragent: str = ""
    plugin_path: str | Path = ""
    spacy_model: str = ""
    create_ww: bool = True
    create_x: bool = True
    asin: str = ""
    acr: str = ""
    revision: str = ""
    kfx_json: KFXJson | None = None
    mobi_html: bytes | None = b""
    mobi_codec: str = ""


def do_job(
    data: ParseJobData,
    abort: Any = None,
    log: Any = None,
    notifications: Any = None,
) -> ParseJobData:
    from .config import prefs
    from .metadata import get_asin_etc

    set_en_lang = (
        True
        if data.create_ww and data.book_fmt != "EPUB" and data.book_lang != "en"
        else False
    )
    if set_en_lang:
        en_book_path = Path(data.book_path)
        en_book_path = en_book_path.with_stem(en_book_path.stem + "_en")
        if not en_book_path.exists():
            shutil.copy(data.book_path, en_book_path)
        data.book_path = str(en_book_path)

    get_asin_etc(data, set_en_lang=set_en_lang)
    data.plugin_path = get_plugin_path()
    data.useragent = get_user_agent()
    data.spacy_model = spacy_model_name(data.book_lang, prefs)
    if data.book_fmt == "EPUB":
        new_epub_path = Path(data.book_path)
        new_file_stem = new_epub_path.stem
        if data.create_x:
            new_file_stem += "_x_ray"
        if data.create_ww:
            new_file_stem += "_word_wise"
        new_epub_path = new_epub_path.with_stem(new_file_stem)
        data.create_x = data.create_x and not new_epub_path.exists()
        data.create_ww = data.create_ww and not new_epub_path.exists()
        shutil.copy(data.book_path, new_epub_path)
        data.book_path = str(new_epub_path)
        if (
            data.create_ww
            and not wiktionary_db_path(
                data.plugin_path, data.book_lang, prefs["wiktionary_gloss_lang"]
            ).exists()
        ):
            download_word_wise_file(
                False, data.book_lang, prefs, notifications=notifications
            )
    else:
        data.create_ww = (
            data.create_ww and not get_ll_path(data.asin, data.book_path).exists()
        )
        data.create_x = (
            data.create_x and not get_x_ray_path(data.asin, data.book_path).exists()
        )
        if data.create_ww and (
            not kindle_db_path(data.plugin_path, data.book_lang, prefs).exists()
            or not get_wiktionary_klld_path(
                data.plugin_path, data.book_lang, prefs["kindle_gloss_lang"]
            ).exists()
        ):
            download_word_wise_file(
                True, data.book_lang, prefs, notifications=notifications
            )

    if not data.create_ww and not data.create_x:
        return data

    if isfrozen and (data.book_fmt == "EPUB" or data.create_x):
        # parse MediaWiki page and Wikipedia section requires lxml
        install_deps("lxml", notifications)
    install_deps(data.spacy_model, notifications)

    if notifications:
        notifications.put((0, "Creating files"))

    # Run plugin code in another Python process
    # macOS: bypass library validation
    # official calibre build: calibre's optimize level is 2 which removes docstring,
    # but the "transformers" package formats docstrings in their code
    # and calibre-debug can't be used as Python interpreter for pip
    if isfrozen:
        py_path, _ = which_python()
        # copy data can't be converted by `asdict`
        copy_mi = data.mi
        copy_mobi_html = data.mobi_html  # bytes
        copy_kfx_json = data.kfx_json  # too long
        data.mi = None
        data.mobi_html = None
        data.kfx_json = None
        data.plugin_path = str(data.plugin_path)
        args = [
            py_path,
            str(data.plugin_path),
            json.dumps(asdict(data)),
            dump_prefs(prefs),
        ]
        data.mi = copy_mi
        input_str = None
        if data.book_fmt == "KFX":
            input_str = json.dumps(copy_kfx_json).encode("utf-8")
        elif data.book_fmt != "EPUB":
            input_str = copy_mobi_html

        run_subprocess(args, input_str)
    else:
        create_files(data, prefs, notifications)

    return data


def calculate_final_start(data: ParseJobData) -> int:
    match data.book_fmt:
        case "KFX":
            return data.kfx_json[-1]["position"] + len(  # type: ignore
                data.kfx_json[-1]["content"]  # type: ignore
            )
        case "AZW3" | "MOBI":
            return len(data.mobi_html)  # type: ignore
        case _:
            return 0


def create_files(data: ParseJobData, prefs: Prefs, notif: Any) -> None:
    """
    This function runs in system Python subprocess for official(frozen) calibre build.
    """
    is_epub = data.book_fmt == "EPUB"
    data.plugin_path = Path(data.plugin_path)
    insert_installed_libs(data.plugin_path)
    nlp = load_spacy(
        data.spacy_model,
        data.book_path if data.create_x else None,
        prefs["use_pos"],
        data.book_lang,
    )
    lemmas_conn = None
    if data.create_ww:
        lemmas_db_path = (
            wiktionary_db_path(
                data.plugin_path, data.book_lang, prefs["wiktionary_gloss_lang"]
            )
            if is_epub
            else kindle_db_path(data.plugin_path, data.book_lang, prefs)
        )
        lemmas_conn = sqlite3.connect(lemmas_db_path)
        lemma_matcher, phrase_matcher = create_spacy_matcher(
            nlp,
            data.spacy_model,
            data.book_lang,
            not is_epub,
            lemmas_conn,
            data.plugin_path,
            prefs,
        )

    if data.create_x:
        mediawiki = MediaWiki(
            prefs["mediawiki_api"],
            data.book_lang,
            data.useragent,
            data.plugin_path,
            prefs["zh_wiki_variant"],
        )
        wikidata = (
            None
            if len(prefs["mediawiki_api"]) > 0
            else Wikidata(data.plugin_path, data.useragent)
        )
        custom_x_ray = load_custom_x_desc(data.book_path)

    if is_epub:
        if data.create_x:
            wiki_commons = None
            if prefs["mediawiki_api"] == "" and prefs["add_locator_map"]:
                wiki_commons = Wikimedia_Commons(data.plugin_path, data.useragent)
            epub = EPUB(
                data.book_path,
                mediawiki,
                wiki_commons,
                wikidata,
                custom_x_ray,
                lemmas_conn,
            )
        elif data.create_ww:
            epub = EPUB(data.book_path, None, None, None, None, lemmas_conn)

        for doc, (start, end, xhtml_path) in nlp.pipe(
            epub.extract_epub(), as_tuples=True
        ):
            intervals = []
            if data.create_x:
                intervals = find_named_entity(
                    start,
                    epub,
                    doc,
                    "",
                    data.book_lang,
                    None,
                    custom_x_ray,
                    xhtml_path,
                    end,
                )
            if data.create_ww:
                interval_tree = None
                if len(intervals) > 0:
                    random.shuffle(intervals)
                    interval_tree = IntervalTree()
                    interval_tree.insert_intervals(intervals)
                epub_find_lemma(
                    doc,
                    lemma_matcher,
                    phrase_matcher,
                    start,
                    end,
                    interval_tree,
                    epub,
                    xhtml_path,
                    prefs["use_pos"],
                )
        supported_languages = load_languages_data(data.plugin_path)
        gloss_lang = prefs["wiktionary_gloss_lang"]
        gloss_source = supported_languages[gloss_lang]["gloss_source"]
        epub.modify_epub(prefs, data.book_lang, gloss_lang, gloss_source)
        return

    # Kindle
    final_start = calculate_final_start(data)
    if data.create_ww:
        ll_conn, ll_path = create_lang_layer(
            data.asin,
            data.book_path,
            data.acr,
            data.revision,
        )

    if data.create_x:
        x_ray_conn, x_ray_path = create_x_ray_db(
            data.asin,
            data.book_path,
            data.book_lang,
            data.plugin_path,
            prefs,
            mediawiki.sitename,
        )
        x_ray = X_Ray(x_ray_conn, mediawiki, wikidata, custom_x_ray)

    for doc, context in nlp.pipe(parse_book(data), as_tuples=True):
        if data.kfx_json is not None:
            start = context
            escaped_text = None
        else:
            start, escaped_text = context
        if data.create_x:
            find_named_entity(
                start,
                x_ray,
                doc,
                data.mobi_codec,
                data.book_lang,
                escaped_text,
                custom_x_ray,
            )
        if data.create_ww:
            kindle_find_lemma(
                doc,
                lemma_matcher,
                phrase_matcher,
                start,
                data.mobi_codec,
                escaped_text,
                lemmas_conn,
                ll_conn,
                data.book_lang,
                prefs,
            )
        if notif:
            notif.put((start / final_start, "Creating files"))

    if data.create_x:
        x_ray.finish(
            x_ray_path,
            final_start,
            data.kfx_json,
            data.mobi_html,
            data.mobi_codec,
            prefs,
        )
    if data.create_ww:
        save_db(ll_conn, ll_path)
        lemmas_conn.close()  # type: ignore


def parse_book(data: ParseJobData) -> Iterator[tuple[str, tuple[int, str] | int]]:
    if data.kfx_json is not None:
        for entry in filter(lambda x: x["type"] == 1, data.kfx_json):
            # Remove byte order mark and word joiner
            yield re.sub(r"\ufeff|\u2060", " ", entry["content"]), entry["position"]
    elif data.mobi_html is not None:
        # match text inside HTML tags
        for match_body in re.finditer(b"<body.{3,}?</body>", data.mobi_html, re.DOTALL):
            for m in re.finditer(b">[^<]{2,}<", match_body.group(0)):
                text = m.group(0)[1:-1].decode(data.mobi_codec)
                text = re.sub(r"\ufeff|\u2060", " ", text)
                yield unescape(text), (match_body.start() + m.start() + 1, text)


def index_in_escaped_text(
    token: str, escaped_text: str, start_offset: int
) -> tuple[int, int] | None:
    if token not in escaped_text[start_offset:]:
        # replace Unicode character to numeric character reference
        token = escape(token, False).encode("ascii", "xmlcharrefreplace").decode()

    if token in escaped_text[start_offset:]:
        token_start = escaped_text.index(token, start_offset)
        return token_start, token_start + len(token)
    else:
        return None


def match_lemmas(doc, lemma_matcher, phrase_matcher):
    from spacy.util import filter_spans

    phrase_spans = phrase_matcher(doc, as_spans=True)
    if lemma_matcher is not None:
        return filter_spans(chain(phrase_spans, lemma_matcher(doc, as_spans=True)))
    else:
        return filter_spans(phrase_spans)


def kindle_find_lemma(
    doc,
    lemma_matcher,
    phrase_matcher,
    start,
    mobi_codec,
    escaped_text,
    lemmas_conn,
    ll_conn,
    lemma_lang,
    prefs,
):
    lemma_starts: set[int] = set()
    for span in match_lemmas(doc, lemma_matcher, phrase_matcher):
        lemma = getattr(span, "lemma_", "")
        pos = getattr(span.doc[span.start], "pos_", "")
        data = get_kindle_lemma_data(
            span.lemma_ if prefs["use_pos"] and lemma != "" else span.text,
            span.text,
            pos if prefs["use_pos"] and pos != "" else "",
            lemmas_conn,
            lemma_lang,
            prefs,
        )
        if data is not None:
            kindle_add_lemma(
                span.start_char,
                span.end_char,
                start,
                doc.text,
                ll_conn,
                mobi_codec,
                escaped_text,
                lemma_starts,
                data,
            )


def epub_find_lemma(
    doc,
    lemma_matcher,
    phrase_matcher,
    paragraph_start,
    paragraph_end,
    interval_tree,
    epub,
    xhtml_path,
    use_pos,
):
    for span in match_lemmas(doc, lemma_matcher, phrase_matcher):
        if interval_tree is not None and interval_tree.is_overlap(
            Interval(span.start_char, span.end_char - 1)
        ):
            return
        pos = getattr(span.doc[span.start], "pos_", "")
        epub.add_lemma(
            getattr(span, "lemma_", ""),
            span.text,
            spacy_to_wiktionary_pos(pos) if use_pos and pos != "" else "",
            paragraph_start,
            paragraph_end,
            span.start_char,
            span.end_char,
            xhtml_path,
        )


def spacy_to_kindle_pos(pos: str) -> str:
    # spaCy POS: https://universaldependencies.org/u/pos
    match pos:
        case "NOUN":
            return "noun"
        case "VERB":
            return "verb"
        case "ADJ":
            return "adjective"
        case "ADV":
            return "adverb"
        case "CCONJ" | "SCONJ":
            return "conjunction"
        case "ADP":
            return "preposition"
        case "PRON":
            return "pronoun"
        case _:
            return "other"


def get_kindle_lemma_data(
    lemma: str,
    word: str,
    pos: str,
    conn: sqlite3.Connection,
    lemma_lang: str,
    prefs: Prefs,
) -> tuple[int, int] | None:
    if pos != "":
        return get_kindle_lemma_with_pos(lemma, word, pos, conn, lemma_lang, prefs)
    else:
        return get_kindle_lemma_without_pos(word, conn)


def get_kindle_lemma_with_pos(
    lemma: str,
    word: str,
    pos: str,
    conn: sqlite3.Connection,
    lemma_lang: str,
    prefs: Prefs,
) -> tuple[int, int] | None:
    if use_kindle_ww_db(lemma_lang, prefs):
        pos = spacy_to_kindle_pos(pos)
    else:
        pos = spacy_to_wiktionary_pos(pos)
    for data in conn.execute(
        """
        SELECT difficulty, senses.id
        FROM senses JOIN lemmas ON senses.lemma_id = lemmas.id
        WHERE lemma = ? AND pos = ? LIMIT 1
        """,
        (lemma, pos),
    ):
        return data
    return get_kindle_lemma_without_pos(word, conn)


def get_kindle_lemma_without_pos(
    word: str, conn: sqlite3.Connection
) -> tuple[int, int] | None:
    for data in conn.execute(
        """
        SELECT difficulty, senses.id
        FROM senses JOIN lemmas
        ON senses.lemma_id = lemmas.id
        WHERE lemma = ? AND enabled = 1 LIMIT 1
        """,
        (word,),
    ):
        return data
    for data in conn.execute(
        """
        SELECT difficulty, senses.id
        FROM senses JOIN forms
        ON senses.lemma_id = forms.lemma_id AND senses.pos = forms.pos
        WHERE form = ? AND enabled = 1 LIMIT 1
        """,
        (word,),
    ):
        return data
    return None


def kindle_add_lemma(
    token_start: int,
    token_end: int,
    text_start: int,
    text: str,
    ll_conn: Connection,
    mobi_codec: str,
    escaped_text: str,
    starts: set[int],
    data: tuple[int, int],
):
    end = None
    lemma = text[token_start:token_end]
    if mobi_codec:
        result = index_in_escaped_text(lemma, escaped_text, token_start)
        if result is None:
            return
        lemma_start, lemma_end = result
        index = text_start + len(escaped_text[:lemma_start].encode(mobi_codec))
    else:
        index = text_start + token_start

    if index in starts:
        return
    else:
        starts.add(index)

    if " " in lemma:
        if mobi_codec:
            end = index + len(escaped_text[lemma_start:lemma_end].encode(mobi_codec))
        else:
            end = index + len(lemma)
    insert_lemma(ll_conn, (index, end) + data)


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


def process_entity(text: str, lang: str, len_limit: int) -> str | None:
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
    start: int,
    x_ray: X_Ray | EPUB,
    doc: Any,
    mobi_codec: str,
    lang: str,
    escaped_text: str | None,
    custom_x_ray: CustomXDict,
    xhtml_path: Path | None = None,
    end: int = 0,
) -> list[Interval]:
    len_limit = 2 if lang in CJK_LANGS else 3
    starts = set()
    intervals = []
    for ent in filter(lambda x: x.label_ in NER_LABELS, doc.ents):
        text = (
            ent.ent_id_  # customized X-Ray
            if ent.ent_id_
            else process_entity(ent.text, lang, len_limit)
        )
        if text is None or (ent.ent_id_ and custom_x_ray.get(ent.ent_id_).omit):
            continue

        ent_text = ent.text if ent.ent_id_ else text
        if escaped_text is not None:
            result = index_in_escaped_text(ent_text, escaped_text, ent.start_char)
            if result is None:
                continue
            start_char, end_char = result
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

        if isinstance(x_ray, EPUB):
            x_ray.add_entity(
                text,
                ent.label_,
                ent.sent.text.strip(),
                start,
                end,
                start_char,
                end_char,
                xhtml_path,
            )
            intervals.append(Interval(start_char, end_char - 1))
            continue

        # Include the next punctuation so the word can be selected on Kindle
        if re.match(r"[^\w\s]", book_text[end_char : end_char + 1]):
            selectable_text = book_text[start_char : end_char + 1]
        if mobi_codec is not None and escaped_text is not None:
            ent_start = start + len(escaped_text[:start_char].encode(mobi_codec))
            ent_len = len(selectable_text.encode(mobi_codec))
        else:
            ent_start = start + start_char
            ent_len = len(selectable_text)

        x_ray.add_entity(text, ent.label_, ent_start, ent.sent.text.strip(), ent_len)

    return intervals


def load_spacy(
    model: str, book_path: str | None, use_pos: bool, lemma_lang: str
) -> Any:
    import spacy

    if model == "":
        return spacy.blank(lemma_lang)

    excluded_components = []
    if not use_pos:
        excluded_components.extend(
            ["tok2vec", "morphologizer", "tagger", "attribute_ruler", "lemmatizer"]
        )
    if book_path is None:
        excluded_components.append("ner")

    if model.endswith("_trf"):
        spacy.require_gpu()
    else:
        excluded_components.append("parser")

    nlp = spacy.load(model, exclude=excluded_components)
    if not model.endswith("_trf") and book_path is not None:
        # simpler and faster https://spacy.io/usage/linguistic-features#sbd
        nlp.enable_pipe("senter")

    if book_path is not None:
        custom_x_path = get_custom_x_path(book_path)
        if custom_x_path.exists():
            ruler = nlp.add_pipe(
                "entity_ruler", before="ner", config={"phrase_matcher_attr": "LOWER"}
            )
            patterns = []
            with custom_x_path.open(encoding="utf-8") as f:
                for name, label, aliases, *_ in json.load(f):
                    patterns.append({"label": label, "pattern": name, "id": name})
                    for alias in [x.strip() for x in aliases.split(",")]:
                        patterns.append({"label": label, "pattern": alias, "id": name})
            ruler.add_patterns(patterns)

    return nlp


def create_spacy_matcher(
    nlp, model, lemma_lang, is_kindle, lemmas_conn, plugin_path, prefs
):
    from spacy.matcher import PhraseMatcher
    from spacy.tokens import DocBin

    disabled_pipes = list(set(["ner", "parser", "senter"]) & set(nlp.pipe_names))
    pkg_versions = load_plugin_json(plugin_path, "data/deps.json")
    model_version = get_spacy_model_version(model, pkg_versions)
    # Chinese words don't have inflection forms, only use phrase matcher
    use_lemma_matcher = prefs["use_pos"] and lemma_lang != "zh" and model != ""
    phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    phrases_doc_path = spacy_doc_path(
        model,
        model_version,
        lemma_lang,
        is_kindle,
        True,
        plugin_path,
        prefs,
        use_lemma_matcher,
    )
    if not phrases_doc_path.exists():
        save_spacy_docs(
            nlp,
            model,
            model_version,
            lemma_lang,
            is_kindle,
            lemmas_conn,
            plugin_path,
            prefs,
            use_lemma_matcher,
        )
    phrases_doc_bin = DocBin().from_disk(phrases_doc_path)
    if use_lemma_matcher:
        lemma_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        lemmas_doc_path = spacy_doc_path(
            model, model_version, lemma_lang, is_kindle, False, plugin_path, prefs, True
        )
        lemmas_doc_bin = DocBin().from_disk(lemmas_doc_path)

    with nlp.select_pipes(disable=disabled_pipes):
        phrase_matcher.add("phrases", phrases_doc_bin.get_docs(nlp.vocab))
        if use_lemma_matcher:
            lemma_matcher.add("lemmas", lemmas_doc_bin.get_docs(nlp.vocab))
            return lemma_matcher, phrase_matcher
        else:
            return None, phrase_matcher
