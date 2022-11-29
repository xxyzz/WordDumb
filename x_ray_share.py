import json
import re
from pathlib import Path
from typing import TypedDict

try:
    from .utils import Prefs
except ImportError:
    from utils import Prefs


FUZZ_THRESHOLD = 85.7

# https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L325
NER_LABELS = frozenset(
    [
        "EVENT",  # OntoNotes 5: English, Chinese
        "FAC",
        "GPE",
        "LAW",
        "LOC",
        "ORG",
        "PERSON",
        "PRODUCT",
        "MISC",  # Catalan
        "PER",
        "EVT",  # Norwegian Bokmål: https://github.com/ltgoslo/norne#entity-types
        "GPE_LOC",
        "GPE_ORG",
        "PROD",
        "geogName",  # Polish: https://arxiv.org/pdf/1811.10418.pdf#subsection.2.1
        "orgName",
        "persName",
        "placeName",
        "ORGANIZATION",  # Romanian: https://arxiv.org/pdf/1909.01247.pdf#section.4
        "PS",  # Korean: https://arxiv.org/pdf/2105.09680.pdf#subsubsection.3.4.1
        "LC",
        "OG",
        "EVN",  # Swedish: https://core.ac.uk/reader/33724960
        "PRS",
        "DERIV_PER",  # Croatian: https://nl.ijs.si/janes/wp-content/uploads/2017/09/SlovenianNER-eng-v1.1.pdf
    ]
)
PERSON_LABELS = frozenset(["PERSON", "PER", "persName", "PS", "PRS", "DERIV_PER"])


# https://en.wikipedia.org/wiki/Interpunct
NAME_DIVISION_REG = r"\s|\u00B7|\u2027|\u30FB|\uFF65"


def is_full_name(
    partial_name: str, partial_label: str, full_name: str, full_label: str
) -> bool:
    return (
        re.search(NAME_DIVISION_REG, partial_name) is None
        and re.search(NAME_DIVISION_REG, full_name) is not None
        and partial_label in PERSON_LABELS
        and full_label in PERSON_LABELS
    )


def x_ray_source(source_id: int, prefs: Prefs, lang: str) -> tuple[str, str | None]:
    if source_id == 1:
        source_link = (
            f"https://{lang}.wikipedia.org/wiki/"
            if lang != "zh"
            else f"https://zh.wikipedia.org/zh-{prefs['zh_wiki_variant']}/"
        )
        return "Wikipedia", source_link
    else:
        return "Fandom", prefs["fandom"] + "/wiki" if prefs["fandom"] else None


class XRayEntity(TypedDict):
    id: int
    quote: str
    label: str
    count: int


def get_custom_x_path(book_path: str | Path) -> Path:
    if isinstance(book_path, str):
        book_path = Path(book_path)
    return book_path.parent.joinpath("worddumb-custom-x-ray.json")


CustomX = dict[str, tuple[str, int, bool]]


def load_custom_x_desc(book_path: str | Path) -> CustomX:
    custom_path = get_custom_x_path(book_path)
    if custom_path.exists():
        with custom_path.open(encoding="utf-8") as f:
            return {
                name: (desc, source_id, omit)
                for name, *_, desc, source_id, omit in json.load(f)
            }
    else:
        return {}
