import sqlite3
from pathlib import Path

try:
    from .utils import (
        Prefs,
        custom_lemmas_folder,
        insert_installed_libs,
        load_plugin_json,
        use_kindle_ww_db,
    )
except ImportError:
    from utils import (
        Prefs,
        custom_lemmas_folder,
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
):
    import platform

    gloss_lang = prefs["kindle_gloss_lang" if is_kindle else "wiktionary_gloss_lang"]
    if is_kindle and not use_kindle_ww_db(lemma_lang, prefs):
        is_kindle = False
    py_version = ".".join(platform.python_version_tuple()[:2])
    path = custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/{spacy_model}_{'kindle' if is_kindle else 'wiktionary'}_{gloss_lang}_{model_version}_{py_version}"
    )
    if prefs["use_pos"]:
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

    excluded_components = ["ner", "parser"]
    if lemma_lang == "zh" or not prefs["use_pos"]:
        excluded_components.extend(
            ["tok2vec", "morphologizer", "tagger", "attribute_ruler", "lemmatizer"]
        )
    nlp = spacy.load(spacy_model, exclude=excluded_components)
    lemmas_conn = sqlite3.connect(db_path)
    pkg_versions = load_plugin_json(plugin_path, "data/deps.json")
    save_spacy_docs(
        nlp,
        spacy_model,
        pkg_versions["spacy_model"],
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

    phrases_doc_bin = DocBin(attrs=["LOWER"])
    if prefs["use_pos"] and lemma_lang != "zh":
        lemmas_doc_bin = DocBin(attrs=["LEMMA"])
    difficulty_limit = (
        None if is_kindle else prefs[f"{lemma_lang}_wiktionary_difficulty_limit"]
    )
    if prefs["use_pos"]:
        for doc in create_lemma_patterns_with_pos(
            lemma_lang, lemmas_conn, nlp, difficulty_limit
        ):
            if " " in doc.text or lemma_lang == "zh":
                phrases_doc_bin.add(doc)
            if " " not in doc.text and lemma_lang != "zh":
                lemmas_doc_bin.add(doc)
    else:
        for doc in create_lemma_patterns_without_pos(
            lemmas_conn, nlp, difficulty_limit
        ):
            phrases_doc_bin.add(doc)

    with open(
        spacy_doc_path(
            spacy_model, model_version, lemma_lang, is_kindle, True, plugin_path, prefs
        ),
        "wb",
    ) as f:
        f.write(phrases_doc_bin.to_bytes())

    if prefs["use_pos"] and lemma_lang != "zh":
        with open(
            spacy_doc_path(
                spacy_model,
                model_version,
                lemma_lang,
                is_kindle,
                False,
                plugin_path,
                prefs,
            ),
            "wb",
        ) as f:
            f.write(lemmas_doc_bin.to_bytes())


def create_lemma_patterns_with_pos(lemma_lang, conn, nlp, difficulty_limit):
    query_sql = "SELECT DISTINCT lemma, lemma_id FROM senses JOIN lemmas ON senses.lemma_id = lemmas.id WHERE enabled = 1"
    if difficulty_limit is not None:
        query_sql += f" AND difficulty <= {difficulty_limit}"
    for lemma, lemma_id in conn.execute(query_sql):
        yield nlp(lemma)
        if " " in lemma or lemma_lang == "zh":
            for (form,) in conn.execute(
                "SELECT DISTINCT form FROM forms WHERE lemma_id = ?", (lemma_id,)
            ):
                yield nlp(form)


def create_lemma_patterns_without_pos(conn, nlp, difficulty_limit):
    query_sql = "SELECT DISTINCT lemma FROM senses JOIN lemmas ON senses.lemma_id = lemmas.id WHERE enabled = 1"
    if difficulty_limit is not None:
        query_sql += f" AND difficulty <= {difficulty_limit}"
    for (lemma,) in conn.execute(query_sql):
        yield nlp.make_doc(lemma)

    query_sql = "SELECT DISTINCT form FROM senses JOIN forms ON senses.lemma_id = forms.lemma_id AND senses.pos = forms.pos WHERE enabled = 1"
    if difficulty_limit is not None:
        query_sql += f" AND difficulty <= {difficulty_limit}"
    for (form,) in conn.execute(query_sql):
        yield nlp.make_doc(form)
