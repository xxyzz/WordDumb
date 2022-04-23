#!/usr/bin/env python3

import json
import pickle
import re
from itertools import chain, product

from flashtext import KeywordProcessor
from lemminflect import getAllInflections

with open("data/lemmas.json", encoding="utf-8") as f:
    lemmas = json.load(f)

keyword_processor = KeywordProcessor()


def add_lemma(lemma, data):
    if " " in lemma:  # phrase, for example: 'slick back/down'
        list_of_inflections_list = []
        for word in lemma.split(" "):
            inflections_list = []
            for w in word.split("/"):
                inflections_list.append(w)
                inflections_list.extend(
                    filter(lambda x: x != w, chain(*getAllInflections(w).values()))
                )
            list_of_inflections_list.append(inflections_list)

        for phrase in map(" ".join, product(*list_of_inflections_list)):
            keyword_processor.add_keyword(phrase, data)
    else:
        keyword_processor.add_keyword(lemma, data)
        for inflection in filter(
            lambda x: x != lemma and x not in lemmas,
            chain(*getAllInflections(lemma).values()),
        ):
            keyword_processor.add_keyword(inflection, data)

    if "-" in lemma:
        keyword_processor.add_keyword(lemma.replace("-", " "), data)


for lemma, data in lemmas.items():
    if "(" in lemma:  # "(as) good as new"
        add_lemma(re.sub(r"[()]", "", lemma), data)
        add_lemma(
            " ".join(filter(None, re.sub(r"\([^)]+\)", "", lemma).split(" "))), data
        )
    else:
        add_lemma(lemma, data)

with open("lemmas_dump", "wb") as f:
    pickle.dump(keyword_processor, f)
