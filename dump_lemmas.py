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
    for lemma, difficulty, sense_id, forms_str in conn.execute(
        "SELECT lemma, difficulty, sense_id, forms FROM lemmas WHERE enabled = 1 ORDER BY lemma"
    ):
        if is_cjk:
            kw_processor.add_word(lemma, (lemma, difficulty, sense_id))
        else:
            kw_processor.add_keyword(lemma, (difficulty, sense_id))
        for form in forms_str.split(","):
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

    prefered_en_ipa = prefs.get("en_ipa", "ga_ipa")
    prefered_zh_ipa = prefs.get("zh_ipa", "pinyin")
    difficulty_limit = prefs.get(f"{lemma_lang}_wiktionary_difficulty_limit", 5)
    conn = sqlite3.connect(db_path)
    if lemma_lang == "en":
        query_sql = "SELECT lemma, short_def, full_def, forms, example, ga_ipa, rp_ipa FROM lemmas WHERE enabled = 1 AND difficulty <= ? ORDER BY lemma"
    elif lemma_lang == "zh":
        query_sql = "SELECT lemma, short_def, full_def, forms, example, pinyin, bopomofo FROM lemmas WHERE enabled = 1 AND difficulty <= ? ORDER BY lemma"
    else:
        query_sql = "SELECT lemma, short_def, full_def, forms, example, ipa FROM lemmas WHERE enabled = 1 AND difficulty <= ? ORDER BY lemma"
    for lemma, short_def, full_def, forms, example, *ipas in conn.execute(
        query_sql, (difficulty_limit,)
    ):
        if lemma_lang == "en":
            ga_ipa, rp_ipa = ipas
            ipa = ga_ipa if prefered_en_ipa == "ga_ipa" else rp_ipa
        elif lemma_lang == "zh":
            pinyin, bopomofo = ipas
            ipa = pinyin if prefered_zh_ipa == "pinyin" else bopomofo
        else:
            ipa = ipas[0]

        if is_cjk:
            kw_processor.add_word(lemma, (lemma, short_def, full_def, example, ipa))
        else:
            kw_processor.add_keyword(lemma, (short_def, full_def, example, ipa))
        for form in forms.split(","):
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
