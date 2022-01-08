#!/usr/bin/env python3

import json
import pickle
from itertools import chain, product

from flashtext import KeywordProcessor
from lemminflect import getAllInflections

with open('data/lemmas.json') as f:
    lemmas = json.load(f)

keyword_processor = KeywordProcessor()
for lemma, values in lemmas.items():
    if '(' in lemma:  # 'take (something) into account'
        continue

    if ' ' in lemma:  # phrase, for example: 'slick back/down'
        list_of_inflections_list = []
        for word in lemma.split(' '):
            inflections_list = []
            for w in word.split('/'):
                inflections_list.append(w)
                inflections_list.extend(filter(
                    lambda x: x != w, chain(*getAllInflections(w).values())))
            list_of_inflections_list.append(inflections_list)

        for phrase in map(' '.join, product(*list_of_inflections_list)):
            keyword_processor.add_keyword(phrase, values)
    else:
        keyword_processor.add_keyword(lemma, values)
        for inflection in filter(lambda x: x != lemma and x not in lemma,
                                 chain(*getAllInflections(lemma).values())):
            keyword_processor.add_keyword(inflection, values)

    if '-' in lemma:
        keyword_processor.add_keyword(lemma.replace('-', ' '), values)

with open('lemmas_dump', 'wb') as f:
    pickle.dump(keyword_processor, f)
