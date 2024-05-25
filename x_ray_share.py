import json
import re
from dataclasses import dataclass
from pathlib import Path

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
        len(partial_name) < len(full_name)
        and re.search(NAME_DIVISION_REG, partial_name) is None
        and re.search(NAME_DIVISION_REG, full_name) is not None
        and partial_label in PERSON_LABELS
        and full_label in PERSON_LABELS
    )


@dataclass
class XRayEntity:
    id: int
    quote: str
    label: str
    count: int


def get_custom_x_path(book_path: str | Path) -> Path:
    if isinstance(book_path, str):
        book_path = Path(book_path)
    return book_path.parent.joinpath("worddumb-custom-x-ray.json")


@dataclass
class CustomX:
    desc: str
    source_id: int
    omit: bool


CustomXDict = dict[str, CustomX]


def load_custom_x_desc(book_path: str | Path) -> CustomXDict:
    custom_path = get_custom_x_path(book_path)
    if custom_path.exists():
        with custom_path.open(encoding="utf-8") as f:
            return {
                name: CustomX(desc, source_id, omit)
                for name, *_, desc, source_id, omit in json.load(f)
            }
    else:
        return {}
