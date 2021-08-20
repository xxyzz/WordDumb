#!/usr/bin/env python3

import base64
import re

from lxml import etree


def add_ja_def(dic, lemma, defs):
    if len(defs) > 1 and defs[0].startswith('['):
        defs.pop(0)
    for full_def in defs:
        example = None
        if '¶' in full_def:
            full_def, example = full_def.split('¶', maxsplit=1)
            example = example.split('¶', maxsplit=1)[0]
        short_def = re.sub(
            r'(?:\(+[^)]+\)+|〔[^〕]+〕|\[[^]]+\]|〈[^〉]+〉|（[^）]+）|［[^］]+］)',
            '', full_def)
        if '；' in short_def:
            short_def = short_def.split('；', maxsplit=1)[0]
        dic[lemma].append((
            base64.b64encode(full_def.encode('utf-8')).decode('utf-8'),
            base64.b64encode(short_def.encode('utf-8')).decode('utf-8'),
            base64.b64encode(
                example.encode('utf-8')).decode('utf-8') if example else None))


def parse_ja_dict(rawml_path, dic):
    for _, element in etree.iterparse(
            rawml_path, tag='hr', html=True,
            remove_blank_text=True, remove_comments=True):
        sibling = element.getnext()
        lemma = ''
        defs = ['']
        while sibling is not None and sibling.tag != 'hr':
            if sibling.tag == 'b':
                if sibling.text:
                    tmp = sibling.text.replace('·', '')
                    if lemma != '' and re.fullmatch(r'\d', tmp) \
                       and sibling.tail:
                        # next definition
                        defs.append(
                            sibling.tail.strip().removeprefix('/'))
                    elif re.fullmatch(r'\(\d+\)', tmp) and sibling.tail:
                        # sub definition
                        defs[-1] += sibling.tail.strip().removeprefix('/')
                    elif not re.fullmatch(r'[a-zA-Z]{3,}', tmp):
                        break
                    elif lemma == '':
                        lemma = tmp  # new lemma
                        defs = ['']
                    elif sibling.tail:
                        defs[-1] += sibling.tail.strip().removeprefix('/')
                elif len(sibling) > 0:
                    if sibling[0].tag == 'i':  # filter phrase
                        add_ja_def(dic, lemma, defs)
                        break
                    # <b><sup>*</sup>a·ban·don<sup>1</sup></b>
                    for t in sibling:
                        if t.tail:
                            tmp = t.tail.replace('·', '')
                            if not re.fullmatch(r'[a-zA-Z]{3,}', tmp):
                                continue
                            lemma = tmp
                            break
            else:
                if sibling.text:
                    defs[-1] += sibling.text.strip().removeprefix('/')
                if sibling.tail:
                    defs[-1] += sibling.tail.strip().removeprefix('/')

            sibling = sibling.getnext()
            if sibling is not None and sibling.tag == 'hr':
                add_ja_def(dic, lemma, defs)
