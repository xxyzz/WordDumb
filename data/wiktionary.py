#!/usr/bin/env python3

import json
import pickle
import re

CJK_LANGS = ["zh", "ja", "ko"]
POS_TYPES = ["adj", "adv", "noun", "phrase", "proverb", "verb"]


def download_wiktionary(download_folder, source_language, notif):
    if not download_folder.exists():
        download_folder.mkdir()
    filename_lang = re.sub(r"[\s-]", "", source_language)
    filename = f"kaikki.org-dictionary-{filename_lang}.json"
    download_path = download_folder.joinpath(filename)
    if not download_path.exists():
        import requests

        if notif:
            message = f"Downloading {source_language} Wiktionary"
            notif.put((0, message))

        with requests.get(
            f"https://kaikki.org/dictionary/{source_language}/{filename}", stream=True
        ) as r, open(download_path, "wb") as f:
            total_len = int(r.headers.get("content-length"))
            current_len = 0
            for chunk in r.iter_content(chunk_size=4096):
                f.write(chunk)
                current_len += len(chunk)
                if notif:
                    notif.put((current_len / total_len, message))

    return download_path


def extract_wiktionary(download_path, lang, kindle_lemmas, notif):
    if notif:
        notif.put((0, "Extracting Wiktionary file"))
    words = []
    word_set = set()
    len_limit = 2 if lang in CJK_LANGS else 3
    with open(download_path, encoding="utf-8") as f:
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
            if lang in CJK_LANGS and re.fullmatch(r"[a-zA-Z\d]+", word):
                continue

            enabled = False if word in word_set else True
            word_set.add(word)
            forms = set()
            for form in map(lambda x: x.get("form"), data.get("forms", [])):
                if form and form not in word_set and len(form) >= len_limit:
                    forms.add(form)

            for sense in data.get("senses", []):
                examples = sense.get("examples", [])
                glosses = sense.get("glosses")
                example_sent = None
                if not glosses:
                    continue
                tags = sense.get("tags", [])
                if any([x in tags for x in ["plural", "alternative", "obsolete"]]):
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
                        ",".join(forms),
                    )
                )
                enabled = False

    download_path.unlink()
    words.sort(key=lambda x: x[1])
    with open(
        download_path.with_name(f"wiktionary_{lang}.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(words, f)


def dump_wikitionary(json_path, dump_path, lang, notif):
    if notif:
        notif.put((0, "Converting Wiktionary file"))

    with open(json_path, encoding="utf-8") as f:
        words = json.load(f)

    if lang in CJK_LANGS:
        import ahocorasick

        automaton = ahocorasick.Automaton()
        for _, word, short_gloss, gloss, example, forms in filter(
            lambda x: x[0] and not automaton.exists(x[1]), words
        ):
            automaton.add_word(word, (word, short_gloss, gloss, example))
            for form in filter(lambda x: not automaton.exists(x), forms.split(",")):
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
            for form in filter(lambda x: x not in keyword_processor, forms.split(",")):
                keyword_processor.add_keyword(form, (short_gloss, gloss, example))

        with open(dump_path, "wb") as f:
            pickle.dump(keyword_processor, f)


def short_def(gloss):
    return re.split(r"[;,]", re.sub(r"\([^)]+\)", "", gloss), 1)[0].strip()


def download_and_dump_wiktionary(
    json_path, dump_path, lang, kindle_lemmas, notif, enable_extract
):
    download_path = download_wiktionary(json_path.parent, lang["kaikki"], notif)
    if enable_extract:
        extract_wiktionary(download_path, lang["wiki"], kindle_lemmas, notif)
    if dump_path:
        dump_wikitionary(json_path, dump_path, lang["wiki"], notif)
