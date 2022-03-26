#!/usr/bin/env python3

import re

from lxml import etree

RE = r"(?:\([^)]+\)|\[[^]]+\]|‹[^›]+›|<[^>]+>|«[^»]+»|:)"


def parse_es_dict(rawml_path, dic, en_klld):
    for _, element in etree.iterparse(
        rawml_path, tag="hr", html=True, remove_blank_text=True, remove_comments=True
    ):
        lemma = element.xpath("following-sibling::div[1]/div[1]/b/text()")
        if len(lemma) == 0:
            element.clear(keep_tail=True)
            continue
        lemma = lemma[0]
        if lemma not in en_klld:
            element.clear(keep_tail=True)
            continue
        defs = []
        for s in element.xpath("following-sibling::div[2]//a/following-sibling::span"):
            definition = s.xpath("descendant-or-self::text()")
            examples = s.xpath("following-sibling::*/descendant-or-self::text()")
            definition.extend(examples)
            defs.append("".join(definition).strip())
        defs = [(x, re.sub(RE, "", re.split(r"[;•]", x, 1)[0]).strip()) for x in defs]
        dic[lemma].extend(filter(lambda x: len(x[1]), defs))
        element.clear(keep_tail=True)
