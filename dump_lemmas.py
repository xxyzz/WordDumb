import pickle
import sqlite3
from pathlib import Path
from typing import Any

try:
    from .utils import (
        CJK_LANGS,
        Prefs,
        custom_lemmas_folder,
        insert_installed_libs,
        insert_plugin_libs,
        kindle_db_path,
        wiktionary_db_path,
    )
except ImportError:
    from utils import (
        CJK_LANGS,
        Prefs,
        custom_lemmas_folder,
        insert_installed_libs,
        insert_plugin_libs,
        kindle_db_path,
        wiktionary_db_path,
    )

LEMMAS_DUMP_VERSION = "0"


def kindle_dump_path(plugin_path: Path, lemma_lang: str) -> Path:
    return custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/kindle_{lemma_lang}_en_dump_v{LEMMAS_DUMP_VERSION}"
    )


def wiktionary_dump_path(plugin_path: Path, lemma_lang: str, gloss_lang: str) -> Path:
    return custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/wiktionary_{lemma_lang}_{gloss_lang}_dump_v{LEMMAS_DUMP_VERSION}"
    )


def load_lemmas_dump(
    is_kindle: bool, lemma_lang: str, gloss_lang: str, plugin_path: Path, prefs: Prefs
) -> Any:
    if lemma_lang in CJK_LANGS:
        insert_installed_libs(plugin_path)
    else:
        insert_plugin_libs(plugin_path)

    dump_path = (
        kindle_dump_path(plugin_path, lemma_lang)
        if is_kindle
        else wiktionary_dump_path(plugin_path, lemma_lang, gloss_lang)
    )
    if not dump_path.exists():
        if is_kindle:
            dump_kindle_lemmas(
                lemma_lang,
                kindle_db_path(plugin_path, lemma_lang),
                dump_path,
                plugin_path,
            )
        else:
            dump_wiktionary(
                lemma_lang,
                wiktionary_db_path(plugin_path, lemma_lang, gloss_lang),
                dump_path,
                plugin_path,
                prefs,
            )

    if lemma_lang in CJK_LANGS:
        import ahocorasick

        return ahocorasick.load(str(dump_path), pickle.loads)
    elif dump_path.exists():
        with open(dump_path, "rb") as f:
            return pickle.load(f)


def dump_kindle_lemmas(
    lemma_lang: str, db_path: Path, dump_path: Path, plugin_path: Path
) -> None:
    is_cjk = lemma_lang in CJK_LANGS
    if is_cjk:
        insert_installed_libs(plugin_path)
        import ahocorasick

        kw_processor = ahocorasick.Automaton()
    else:
        insert_plugin_libs(plugin_path)
        from flashtext import KeywordProcessor

        kw_processor = KeywordProcessor()

    conn = sqlite3.connect(db_path)
    for lemma, difficulty, sense_id, lemma_id in conn.execute(
        "SELECT lemma, difficulty, sense_id, lemma_id FROM senses JOIN lemmas ON senses.lemma_id = lemmas.id WHERE enabled = 1 ORDER BY lemma"
    ):
        if is_cjk:
            kw_processor.add_word(lemma, (lemma, difficulty, sense_id))
        else:
            kw_processor.add_keyword(lemma, (difficulty, sense_id))
        for form in conn.execute(
            "SELECT form FROM forms WHERE lemma_id = ?", (lemma_id,)
        ):
            if is_cjk:
                kw_processor.add_word(form, (form, difficulty, sense_id))
            else:
                kw_processor.add_keyword(form, (difficulty, sense_id))

    conn.close()
    if is_cjk:
        kw_processor.make_automaton()
        kw_processor.save(str(dump_path), pickle.dumps)
    else:
        with open(dump_path, "wb") as f:
            pickle.dump(kw_processor, f)


def dump_wiktionary(
    lemma_lang: str, db_path: Path, dump_path: Path, plugin_path: Path, prefs: Prefs
) -> None:
    is_cjk = lemma_lang in CJK_LANGS
    if is_cjk:
        insert_installed_libs(plugin_path)
        import ahocorasick

        kw_processor = ahocorasick.Automaton()
    else:
        insert_plugin_libs(plugin_path)
        from flashtext import KeywordProcessor

        kw_processor = KeywordProcessor()

    difficulty_limit = prefs[f"{lemma_lang}_wiktionary_difficulty_limit"]
    conn = sqlite3.connect(db_path)
    query_sql = "SELECT lemma, lemma_id, short_def, full_def, example, "
    if lemma_lang == "en":
        query_sql += prefs["en_ipa"]
    elif lemma_lang == "zh":
        query_sql += prefs["zh_ipa"]
    else:
        query_sql += "ipa"
    query_sql += " FROM senses JOIN lemmas ON senses.lemma_id = lemmas.id WHERE enabled = 1 AND difficulty <= ? ORDER BY lemma"
    for lemma, lemma_id, short_def, full_def, example, ipa in conn.execute(
        query_sql, (difficulty_limit,)
    ):
        if is_cjk:
            kw_processor.add_word(lemma, (lemma, short_def, full_def, example, ipa))
        else:
            kw_processor.add_keyword(lemma, (short_def, full_def, example, ipa))
        for (form,) in conn.execute(
            "SELECT form FROM forms WHERE lemma_id = ?", (lemma_id,)
        ):
            if is_cjk:
                kw_processor.add_word(form, (form, short_def, full_def, example, ipa))
            else:
                kw_processor.add_keyword(form, (short_def, full_def, example, ipa))

    conn.close()
    if is_cjk:
        kw_processor.make_automaton()
        kw_processor.save(str(dump_path), pickle.dumps)
    else:
        with open(dump_path, "wb") as f:
            pickle.dump(kw_processor, f)


def spacy_doc_path(
    spacy_model: str,
    model_version: str,
    lemma_lang: str,
    gloss_lang: str,
    is_kindle: bool,
    is_phrase: bool,
    plugin_path: Path,
):
    import platform

    py_version = ".".join(platform.python_version_tuple()[:2])
    return custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/{spacy_model}_{'kindle' if is_kindle else 'wiktionary'}_{gloss_lang}_{model_version}_{py_version}{'_phrase' if is_phrase else ''}"
    )


def dump_lemmas_pos(
    spacy_model: str,
    is_kindle: bool,
    lemma_lang: str,
    gloss_lang: str,
    db_path: Path,
    plugin_path: Path,
    prefs: Prefs,
):
    insert_installed_libs(plugin_path)
    import spacy
    from spacy.util import get_package_version

    excluded_components = ["ner", "parser"]
    if lemma_lang == "zh":
        excluded_components.extend(
            ["tok2vec", "morphologizer", "tagger", "attribute_ruler", "lemmatizer"]
        )
    nlp = spacy.load(spacy_model, exclude=excluded_components)
    lemmas_conn = sqlite3.connect(db_path)
    dump_spacy_docs(
        nlp,
        spacy_model,
        get_package_version(spacy_model),
        lemma_lang,
        gloss_lang,
        is_kindle,
        lemmas_conn,
        plugin_path,
        prefs,
    )
    lemmas_conn.close()


def dump_spacy_docs(
    nlp,
    spacy_model: str,
    model_version: str,
    lemma_lang: str,
    gloss_lang: str,
    is_kindle: bool,
    lemmas_conn: sqlite3.Connection,
    plugin_path: Path,
    prefs: Prefs,
):
    from spacy.tokens import DocBin

    has_lemmatizer = "lemmatizer" in nlp.component_names
    disabled_pipes = ["ner", "parser", "senter"]
    if not has_lemmatizer:
        disabled_pipes.extend(
            ["tok2vec", "morphologizer", "tagger", "attribute_ruler", "lemmatizer"]
        )
    lemmas_doc_bin = DocBin(attrs=["LEMMA"])
    if lemma_lang not in CJK_LANGS:
        phrases_doc_bin = DocBin(attrs=["LOWER"])
    disabled_pipes = list(set(disabled_pipes) & set(nlp.pipe_names))
    difficulty_limit = (
        None if is_kindle else prefs[f"{lemma_lang}_wiktionary_difficulty_limit"]
    )
    with nlp.select_pipes(disable=disabled_pipes):
        for lemma_doc in create_lemma_patterns(
            lemma_lang, lemmas_conn, nlp, False, has_lemmatizer, difficulty_limit
        ):
            lemmas_doc_bin.add(lemma_doc)
        if lemma_lang not in CJK_LANGS:
            for phrase_doc in create_lemma_patterns(
                lemma_lang, lemmas_conn, nlp, True, has_lemmatizer, difficulty_limit
            ):
                phrases_doc_bin.add(phrase_doc)

    with open(
        spacy_doc_path(
            spacy_model,
            model_version,
            lemma_lang,
            gloss_lang,
            is_kindle,
            False,
            plugin_path,
        ),
        "wb",
    ) as f:
        f.write(lemmas_doc_bin.to_bytes())
    if lemma_lang not in CJK_LANGS:
        with open(
            spacy_doc_path(
                spacy_model,
                model_version,
                lemma_lang,
                gloss_lang,
                is_kindle,
                True,
                plugin_path,
            ),
            "wb",
        ) as f:
            f.write(phrases_doc_bin.to_bytes())


def create_lemma_patterns(
    lemma_lang, conn, nlp, add_phrases, has_lemmatizer, difficulty_limit
):
    query_sql = "SELECT DISTINCT lemma, lemma_id FROM senses JOIN lemmas ON senses.lemma_id = lemmas.id WHERE enabled = 1"
    if add_phrases:
        query_sql += " AND lemma LIKE '% %'"
    else:
        query_sql += " AND lemma NOT LIKE '% %'"
    if difficulty_limit is not None:
        query_sql += f" AND difficulty <= {difficulty_limit}"
    for lemma, lemma_id in conn.execute(query_sql):
        if add_phrases or not has_lemmatizer or lemma_lang == "zh":
            if lemma_lang == "zh":
                yield nlp(lemma)  # Traditional Chinese
            for (form,) in conn.execute(
                "SELECT form FROM forms WHERE lemma_id = ?", (lemma_id,)
            ):
                yield nlp(form)
        else:
            yield nlp(lemma)
