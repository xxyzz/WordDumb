#!/usr/bin/env python3

import re

from lxml import etree

RE = r'(?:\(+[^)]+\)+|〔[^〕]+〕|\[[^]]+\]|〈[^〉]+〉|（[^）]+）|［[^］]+］|]|］|⇒|・)'


def parse_ja_dict(rawml_path, dic, en_klld):
    for _, element in etree.iterparse(
            rawml_path, tag='hr', html=True,
            remove_blank_text=True, remove_comments=True):
        lemma = element.xpath('following-sibling::b[1]/text()')
        if len(lemma) == 0:
            element.clear(keep_tail=True)
            continue
        lemma = lemma[0].replace('·', '')
        if lemma not in en_klld:
            element.clear(keep_tail=True)
            continue
        sibling = element.getnext()
        defs = ['']
        while sibling is not None and sibling.tag != 'hr':
            if sibling.tag == 'b':
                if len(sibling) > 0 and defs[0] != '':  # phrase
                    break
                elif sibling.tail:
                    if re.fullmatch(r'\W*', sibling.tail):
                        sibling = sibling.getnext()
                        continue
                    tail = sibling.tail.strip().removeprefix('/')
                    if defs[0] == '':
                        defs[-1] = tail
                    elif sibling.text and re.fullmatch(r'\(\d+\)',
                                                       sibling.text):
                        defs[-1] += tail  # sub definition
                    else:
                        defs.append(tail)
            else:
                if sibling.text:
                    defs[-1] += sibling.text.strip().removeprefix('/')
                if sibling.tail:
                    defs[-1] += sibling.tail.strip().removeprefix('/')
            sibling = sibling.getnext()

        if len(defs) > 1 and defs[0].startswith('['):
            defs.pop(0)
        defs = [(x, re.sub(
            RE, '', re.split(r'[¶；]', x, 1)[0]).strip()) for x in defs]
        dic[lemma].extend(filter(lambda x: len(x[1]), defs))
        element.clear(keep_tail=True)
