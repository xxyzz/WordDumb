#!/usr/bin/env python3

import json
import pickle
import re
from pathlib import Path

CJK_LANGS = ["zh", "ja", "ko"]
POS_TYPES = ["adj", "adv", "noun", "phrase", "proverb", "verb"]


def download_wiktionary(download_folder, source_language):
    if not download_folder.exists():
        download_folder.mkdir()
    filename = f"kaikki.org-dictionary-{source_language.replace(' ', '')}.json"
    download_path = download_folder.joinpath(filename)
    if not download_path.exists():
        import requests

        with requests.get(
            f"https://kaikki.org/dictionary/{source_language}/{filename}", stream=True
        ) as r, open(download_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024):
                f.write(chunk)

    return download_path


def extract_wiktionary(download_path, lang, kindle_lemmas):
    words = []
    len_limit = 2 if lang in CJK_LANGS else 3
    with open(download_path) as f:
        for line in f:
            data = json.loads(line)
            word = data.get("word")
            pos = data.get("pos")
            if (
                pos not in POS_TYPES
                or len(word) < len_limit
                or re.fullmatch(r"[\W\d]+", word)
            ):
                continue
            if lang in CJK_LANGS and re.fullmatch(r"[a-zA-Z]+", word):
                continue

            forms = set()
            for form in map(lambda x: x.get("form"), data.get("forms", [])):
                if form and len(form) >= len_limit and form != word:
                    forms.add(form)

            enabled = True
            for sense in data.get("senses", []):
                examples = sense.get("examples", [])
                glosses = sense.get("glosses")
                example_sent = None
                if not glosses:
                    continue
                tags = sense.get("tags", [])
                if any([x in tags for x in ["plural", "alternative"]]):
                    continue
                for example in examples:
                    example = example.get("text")
                    if example and example != "(obsolete)":
                        example_sent = example
                        break
                words.append(
                    (
                        enabled if not kindle_lemmas else word in kindle_lemmas,
                        word,
                        short_def(glosses[0]),
                        glosses[0],
                        example_sent,
                        list(forms),
                    )
                )
                enabled = False

    # download_path.unlink()
    with open(download_path.with_name(f"wiktionary_{lang}.json"), "w") as f:
        json.dump(words, f)


def dump_wikitionary(words, dump_path, lang):
    if lang in CJK_LANGS:
        import ahocorasick

        automaton = ahocorasick.Automaton()
        for _, word, short_gloss, gloss, example, forms in filter(
            lambda x: x[0] and not automaton.exists(x[1]), words
        ):
            automaton.add_word(word, (word, short_gloss, gloss, example))
            for form in filter(lambda x: not automaton.exists(x), forms):
                automaton.add_word(form, (form, short_gloss, gloss, example))

        automaton.make_automaton()
        automaton.save(str(dump_path), pickle.dumps)
    else:
        from flashtext import KeywordProcessor

        keyword_processor = KeywordProcessor()
        for _, word, short_gloss, gloss, example, forms in filter(
            lambda x: x[0] and x[1] not in keyword_processor, words
        ):
            keyword_processor.add_keyword(word, (short_gloss, gloss, example))
            for form in filter(lambda x: x not in keyword_processor, forms):
                keyword_processor.add_keyword(form, (short_gloss, gloss, example))

        with open(dump_path, "wb") as f:
            pickle.dump(keyword_processor, f)


def short_def(gloss):
    return re.split(r"[;,]", re.sub(r"\([^)]+\)", "", gloss), 1)[0].strip()


if __name__ == "__main__":
    json_path = download_wiktionary(
        Path("/Users/x/Library/Preferences/calibre/plugins/worddumb-lemmas"),
        "English",
    )
    lang = "en"
    import zipfile

    with zipfile.ZipFile(
        "/Users/x/Library/Preferences/calibre/plugins/WordDumb.zip"
    ) as zf:
        with zf.open("lemmas_dump") as f:
            extract_wiktionary(json_path, lang, pickle.load(f))
    with open(json_path.with_name(f"wiktionary_{lang}.json")) as f:
        dump_wikitionary(
            json.load(f), json_path.with_name(f"wiktionary_{lang}_dump"), lang
        )
