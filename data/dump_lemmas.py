#!/usr/bin/env python3

import json
import pickle

from flashtext import KeywordProcessor
from lemminflect import getAllInflections

with open('data/lemmas.json') as f:
    lemmas = json.load(f)

keywords = set()
keyword_processor = KeywordProcessor()
for lemma, values in lemmas.items():
    keyword_processor.add_keyword(lemma, values)
    keywords.add(lemma)
    for _, inflections in getAllInflections(lemma).items():
        for inflection in inflections:
            if inflection not in keywords:
                keyword_processor.add_keyword(inflection, values)
                keywords.add(inflection)
    if ' ' in lemma:  # phrasae
        words = lemma.split(' ')
        for i, word in enumerate(words):
            words_copy = words.copy()
            for _, inflections in getAllInflections(word).items():
                for inflection in inflections:
                    words_copy[i] = inflection
                    keyword_processor.add_keyword(' '.join(words_copy), values)

with open('lemmas_dump', 'wb') as f:
    pickle.dump(keyword_processor, f)
