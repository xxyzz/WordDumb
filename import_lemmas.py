import csv
import re
import sqlite3
import zipfile
from html import escape
from pathlib import Path
from typing import Any


def extract_apkg(apkg_path: Path) -> dict[str, int]:
    cards = {}
    with zipfile.ZipFile(apkg_path) as zf:
        db_path = zipfile.Path(zf, "collection.anki21")
        if not db_path.exists():  # no scheduling information
            db_path = zipfile.Path(zf, "collection.anki2")
        ex_db_path = zf.extract(db_path.name, apkg_path.parent)
        conn = sqlite3.connect(ex_db_path)
        for card_type, fields in conn.execute(
            "SELECT type, flds FROM cards JOIN notes ON cards.nid = notes.id"
        ):
            cards[fields.split("\x1f", 1)[0]] = card_type_to_difficult_level(card_type)

        conn.close()
        Path(ex_db_path).unlink()
        return cards


def card_type_to_difficult_level(card_type: int) -> int:
    # https://github.com/ankidroid/Anki-Android/wiki/Database-Structure#cards
    match card_type:
        case 0:  # new
            return 1
        case 1:  # learning
            return 3
        case 2:  # review
            return 5
        case 3:  # relearning
            return 4
        case _:
            return 1


def extract_csv(csv_path: Path) -> dict[str, int]:
    csv_words = {}
    with open(csv_path, newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                word, difficulty_str, *_ = row
                try:
                    difficulty = int(difficulty_str)
                except ValueError:
                    difficulty = 1
            else:
                word = row[0]
                difficulty = 1
            csv_words[word] = difficulty

    return csv_words


def query_vocabulary_builder(lang: str, db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    words = {}
    for stem, category, lookups in conn.execute(
        "SELECT stem, category, count(*) FROM WORDS JOIN LOOKUPS ON LOOKUPS.word_key = WORDS.id WHERE lang = ? GROUP BY stem",
        (lang,),
    ):
        words[stem] = lookups_to_difficulty(lookups, category)
    conn.close()
    return words


def lookups_to_difficulty(lookups: int, category: int) -> int:
    if category == 100:
        return 5  # mastered
    match lookups:
        case 1:
            return 5
        case 2:
            return 4
        case 3:
            return 3
        case 4:
            return 2
        case _:
            return 1


def apply_imported_lemmas_data(
    db_path: Path, import_path: Path, retain_lemmas: bool, lemma_lang: str
) -> None:
    lemmas_dict = {}
    match import_path.suffix:
        case ".apkg":
            lemmas_dict = extract_apkg(import_path)
        case ".csv":
            lemmas_dict = extract_csv(import_path)
        case ".db":
            lemmas_dict = query_vocabulary_builder(lemma_lang, import_path)
        case _:
            return

    conn = sqlite3.connect(db_path)
    for lemma_id, lemma in conn.execute("SELECT id, lemma FROM lemmas"):
        if lemma in lemmas_dict:
            conn.execute(
                "UPDATE senses SET enabled = 1, difficulty = ? WHERE lemma_id = ?",
                (lemmas_dict.get(lemma), lemma_id),
            )
        elif not retain_lemmas:
            conn.execute(
                "UPDATE senses SET enabled = 0, difficulty = 1 WHERE lemma_id = ?",
                (lemma_id,),
            )
    conn.commit()
    conn.close()


def export_lemmas_job(
    db_path: Path,
    export_path: Path,
    only_enabled: bool,
    difficulty_limit: int,
    is_kindle: bool,
    lemma_lang: str,
    gloss_lang: str,
    abort: Any = None,
    log: Any = None,
    notifications: Any = None,
) -> None:
    from .config import prefs
    from .utils import get_plugin_path, load_plugin_json

    conn = sqlite3.connect(db_path)
    with open(export_path, "w", encoding="utf-8") as f:
        query_sql = "SELECT lemma, pos, full_def, example"
        if not is_kindle:
            supported_languages = load_plugin_json(
                get_plugin_path(), "data/languages.json"
            )
            if gloss_lang == "zh_cn":
                gloss_lang = "zh"
            has_multiple_ipas = (
                supported_languages[gloss_lang]["gloss_source"] == "kaikki"
            )
            if has_multiple_ipas:
                if lemma_lang == "en":
                    query_sql = f", {prefs['en_ipa']}"
                elif lemma_lang == "zh":
                    query_sql = f", {prefs['zh_ipa']}"
            else:
                query_sql = ", ipa"
        query_sql += " FROM senses JOIN lemmas ON senses.lemma_id = lemmas.id WHERE difficulty <= ?"

        if only_enabled:
            query_sql += " AND enabled = 1"

        if is_kindle:
            for lemma, pos_type, full_def, example in conn.execute(
                query_sql, (difficulty_limit,)
            ):
                back_text = f"<p>{pos_type}</p><p>{full_def}</p>"
                if example:
                    back_text += f"<i>{example}</i>"
                f.write(f"{lemma}\t{back_text}\n")
        else:
            for lemma, pos_type, full_def, example, ipa in conn.execute(
                query_sql, (difficulty_limit,)
            ):
                back_text = f"<p>{pos_type}</p>"
                if ipa:
                    ipa = escape(re.sub(r"\t|\n", " ", ipa))
                    back_text += f"<p>{ipa}</p>"
                full_def = escape(re.sub(r"\t|\n", " ", full_def))
                back_text += f"<p>{full_def}</p>"
                if example:
                    example = escape(re.sub(r"\t|\n", " ", example))
                    back_text += f"<i>{example}</i>"
                f.write(f"{lemma}\t{back_text}\n")
