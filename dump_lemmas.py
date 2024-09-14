import sqlite3
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
    plugin_path: Path,
    prefs: Prefs,
):
    import platform

    gloss_lang = prefs["gloss_lang"]
    if is_kindle and not use_kindle_ww_db(lemma_lang, prefs):
        is_kindle = False
    py_version = ".".join(platform.python_version_tuple()[:2])
    path = custom_lemmas_folder(plugin_path).joinpath(
        f"{spacy_model or lemma_lang}_{'kindle' if is_kindle else 'wiktionary'}"
        f"_{gloss_lang}_{model_version}_{py_version}"
    )
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

    nlp = spacy.load(spacy_model) if spacy_model != "" else spacy.blank(lemma_lang)
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
):
    from spacy.tokens import DocBin

    lemmas_doc_bin = DocBin(attrs=["LOWER"])
    difficulty_limit = (
        5 if is_kindle else prefs[f"{lemma_lang}_wiktionary_difficulty_limit"]
    )
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
    for doc in nlp.tokenizer.pipe(
        map(
            lambda x: x[0].lower(),
            lemmas_conn.execute(query_sql, {"difficulty": difficulty_limit}),
        )
    ):
        lemmas_doc_bin.add(doc)
    lemmas_doc_bin.to_disk(
        spacy_doc_path(
            spacy_model, model_version, lemma_lang, is_kindle, plugin_path, prefs
        )
    )
