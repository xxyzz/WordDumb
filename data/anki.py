import csv
import sqlite3
import zipfile
from pathlib import Path


def extract_apkg(apkg_path: Path) -> dict[str, int]:
    cards = {}
    with zipfile.ZipFile(apkg_path) as zf:
        db_path = zipfile.Path(
            zf, "collection.anki21"
        )  # include scheduling information
        if not db_path.exists():
            db_path = zipfile.Path(zf, "collection.anki2")
        db_path = zf.extract(db_path.name, apkg_path.parent)
        conn = sqlite3.connect(db_path)
        for card_type, fields in conn.execute(
            "SELECT type, flds FROM cards JOIN notes ON cards.nid = notes.id"
        ):
            cards[fields.split("\x1f")[0]] = card_type_to_difficult_level(card_type)

        Path(db_path).unlink()
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


def extract_csv(csv_path: str) -> dict[str, list[int, bool]]:
    csv_words = {}
    with open(csv_path, newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                word, difficulty, *_ = row
                try:
                    difficulty = int(difficulty)
                except ValueError:
                    difficulty = 1
            else:
                word = row[0]
                difficulty = 1
            csv_words[word] = [difficulty, True]

    return csv_words
