import sqlite3
from operator import itemgetter
from pathlib import Path

try:
    from .utils import (
        Prefs,
        custom_lemmas_folder,
        get_spacy_model_version,
        insert_installed_libs,
        load_plugin_json,
        use_kindle_ww_db,
    )
except ImportError:
    from utils import (
        Prefs,
        custom_lemmas_folder,
        get_spacy_model_version,
        insert_installed_libs,
        load_plugin_json,
        use_kindle_ww_db,
    )


def spacy_doc_path(
    spacy_model: str,
    model_version: str,
    lemma_lang: str,
    is_kindle: bool,
    is_phrase: bool,
    plugin_path: Path,
    prefs: Prefs,
    use_lemma_matcher: bool,
):
    import platform

    gloss_lang = prefs["kindle_gloss_lang" if is_kindle else "wiktionary_gloss_lang"]
    if is_kindle and not use_kindle_ww_db(lemma_lang, prefs):
        is_kindle = False
    py_version = ".".join(platform.python_version_tuple()[:2])
    path = custom_lemmas_folder(plugin_path, lemma_lang).joinpath(
        f"{spacy_model or lemma_lang}_{'kindle' if is_kindle else 'wiktionary'}"
        f"_{gloss_lang}_{model_version}_{py_version}"
    )
    if use_lemma_matcher:
        if is_phrase:
            path = path.with_name(path.name + "_phrase")
        path = path.with_name(path.name + "_pos")
    return path


def dump_spacy_docs(
    spacy_model: str,
    is_kindle: bool,
    lemma_lang: str,
    db_path: Path,
    plugin_path: Path,
    prefs: Prefs,
):
    insert_installed_libs(plugin_path)
    import spacy

    use_lemma_matcher = prefs["use_pos"] and lemma_lang != "zh" and spacy_model != ""
    excluded_components = ["ner", "parser"]
    if not use_lemma_matcher:
        excluded_components.extend(
            ["tok2vec", "morphologizer", "tagger", "attribute_ruler", "lemmatizer"]
        )
    nlp = (
        spacy.load(spacy_model, exclude=excluded_components)
        if spacy_model != ""
        else spacy.blank(lemma_lang)
    )
    lemmas_conn = sqlite3.connect(db_path)
    pkg_versions = load_plugin_json(plugin_path, "data/deps.json")
    save_spacy_docs(
        nlp,
        spacy_model,
        get_spacy_model_version(spacy_model, pkg_versions),
        lemma_lang,
        is_kindle,
        lemmas_conn,
        plugin_path,
        prefs,
        use_lemma_matcher,
    )
    lemmas_conn.close()


def save_spacy_docs(
    nlp,
    spacy_model: str,
    model_version: str,
    lemma_lang: str,
    is_kindle: bool,
    lemmas_conn: sqlite3.Connection,
    plugin_path: Path,
    prefs: Prefs,
    use_lemma_matcher: bool,
):
    from spacy.tokens import DocBin

    phrases_doc_bin = DocBin(attrs=["LOWER"])
    if use_lemma_matcher:
        lemmas_doc_bin = DocBin(attrs=["LOWER"])
    difficulty_limit = (
        5 if is_kindle else prefs[f"{lemma_lang}_wiktionary_difficulty_limit"]
    )
    if use_lemma_matcher:
        for doc in create_lemma_patterns_with_pos(
            lemma_lang, lemmas_conn, nlp, difficulty_limit
        ):
            if " " in doc.text:
                phrases_doc_bin.add(doc)
            else:
                lemmas_doc_bin.add(doc)
    else:
        for doc in create_lemma_patterns_without_pos(
            lemmas_conn, nlp, difficulty_limit
        ):
            phrases_doc_bin.add(doc)

    phrases_doc_bin.to_disk(
        spacy_doc_path(
            spacy_model,
            model_version,
            lemma_lang,
            is_kindle,
            True,
            plugin_path,
            prefs,
            use_lemma_matcher,
        )
    )
    if use_lemma_matcher:
        lemmas_doc_bin.to_disk(
            spacy_doc_path(
                spacy_model,
                model_version,
                lemma_lang,
                is_kindle,
                False,
                plugin_path,
                prefs,
                use_lemma_matcher,
            )
        )


def create_lemma_patterns_with_pos(lemma_lang, conn, nlp, difficulty_limit):
    if lemma_lang == "zh":
        query_sql = """
        SELECT DISTINCT lemma
        FROM lemmas l
        JOIN senses s ON l.id = s.lemma_id AND enabled = 1 AND difficulty <= :difficulty
        UNION ALL
        SELECT DISTINCT form FROM forms f
        JOIN senses s ON f.lemma_id = s.lemma_id AND f.pos = s.pos
        AND enabled = 1 AND difficulty <= :difficulty
        """
    else:
        query_sql = """
        SELECT DISTINCT lemma
        FROM lemmas l
        JOIN senses s ON l.id = s.lemma_id AND enabled = 1 AND difficulty <= :difficulty
        UNION ALL
        SELECT DISTINCT form
        FROM lemmas l
        JOIN forms f ON l.id = f.lemma_id
        JOIN senses s ON l.id = s.lemma_id AND f.pos = s.pos
        AND enabled = 1 AND difficulty <= :difficulty
        """
    yield from nlp.pipe(
        map(itemgetter(0), conn.execute(query_sql, {"difficulty": difficulty_limit}))
    )


def create_lemma_patterns_without_pos(conn, nlp, difficulty_limit):
    query_sql = """
    SELECT DISTINCT lemma
    FROM lemmas l JOIN senses s ON l.id = s.lemma_id
    AND enabled = 1 AND difficulty <= :difficulty
    UNION ALL
    SELECT DISTINCT form
    FROM forms f JOIN senses s ON f.lemma_id = s.lemma_id
    AND f.pos = s.pos AND enabled = 1 AND difficulty <= :difficulty
    """
    yield from nlp.tokenizer.pipe(
        map(itemgetter(0), conn.execute(query_sql, {"difficulty": difficulty_limit}))
    )
