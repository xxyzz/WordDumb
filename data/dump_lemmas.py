#!/usr/bin/env python3

import json
import pickle
import re
from itertools import chain, product

# https://lemminflect.readthedocs.io/en/latest/tags
POS_TYPE = {0: "NOUN", 1: "VERB", 2: "ADJ", 3: "ADV", 9: "PROPN"}


def get_inflections(lemma, pos):
    from lemminflect import getAllInflections, getAllInflectionsOOV

    inflections = set(chain(*getAllInflections(lemma, pos).values()))
    if not inflections and pos:
        inflections = set(chain(*getAllInflectionsOOV(lemma, pos).values()))
    return inflections


def add_lemma(lemma, pos, data, keyword_processor):
    if " " in lemma:
        if "/" in lemma:  # "be/get togged up/out"
            words = [word.split("/") for word in lemma.split()]
            for phrase in map(" ".join, product(*words)):
                add_lemma(phrase, pos, data, keyword_processor)
        elif pos == "VERB":
            # inflect the first word of the phrase verb
            first_word, rest_words = lemma.split(maxsplit=1)
            for inflation in {first_word}.union(get_inflections(first_word, "VERB")):
                keyword_processor.add_keyword(f"{inflation} {rest_words}", data)
        else:
            keyword_processor.add_keyword(lemma, data)
    elif "-" in lemma:
        keyword_processor.add_keyword(lemma, data)
    else:
        for inflection in {lemma}.union(get_inflections(lemma, pos)):
            keyword_processor.add_keyword(inflection, data)


def dump_lemmas(lemmas, dump_path):
    from flashtext import KeywordProcessor

    keyword_processor = KeywordProcessor()
    for lemma, (difficulty, sense_id, pos) in lemmas.items():
        pos = POS_TYPE.get(pos)
        data = (difficulty, sense_id)
        if "(" in lemma:  # "(as) good as new"
            add_lemma(re.sub(r"[()]", "", lemma), pos, data, keyword_processor)
            add_lemma(
                " ".join(re.sub(r"\([^)]+\)", "", lemma).split()),
                pos,
                data,
                keyword_processor,
            )
        else:
            add_lemma(lemma, pos, data, keyword_processor)

    with open(dump_path, "wb") as f:
        pickle.dump(keyword_processor, f)


if __name__ == "__main__":
    with open("data/lemmas.json", encoding="utf-8") as f:
        dump_lemmas(json.load(f), "lemmas_dump")
