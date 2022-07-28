#!/usr/bin/env python3

import json
import pickle
import re

CJK_LANGS = ["zh", "ja", "ko"]
POS_TYPES = ["adj", "adv", "noun", "phrase", "proverb", "verb"]


def download_wiktionary(download_folder, source_language, useragent, notif):
    if not download_folder.exists():
        download_folder.mkdir()
    filename_lang = re.sub(r"[\s-]", "", source_language)
    filename = f"kaikki.org-dictionary-{filename_lang}.json"
    download_path = download_folder.joinpath(filename)
    if not download_path.exists():
        import requests

        with requests.get(
            f"https://kaikki.org/dictionary/{source_language}/{filename}",
            stream=True,
            headers={"user-agent": useragent},
        ) as r, open(download_path, "wb") as f:
            total_len = int(r.headers.get("content-length", 0))
            chunk_size = 2**23
            total_chunks = total_len // chunk_size + 1
            chunk_count = 0
            for chunk in r.iter_content(chunk_size):
                f.write(chunk)
                if notif and total_len > 0:
                    chunk_count += 1
                    notif.put(
                        (
                            chunk_count / total_chunks,
                            f"Downloading {source_language} Wiktionary",
                        )
                    )

    return download_path


def extract_wiktionary(download_path, lang, kindle_lemmas, notif):
    if notif:
        notif.put((0, "Extracting Wiktionary file"))
    words = []
    enabled_words = set()
    len_limit = 2 if lang in CJK_LANGS else 3
    with open(download_path, encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            word = data.get("word")
            pos = data.get("pos")
            if (
                pos not in POS_TYPES
                or len(word) < len_limit
                or re.match(r"\W|\d", word)
            ):
                continue
            if lang in CJK_LANGS and re.fullmatch(r"[a-zA-Z\d]+", word):
                continue

            enabled = False if word in enabled_words else True
            if kindle_lemmas and enabled:
                enabled = word in kindle_lemmas
            if enabled:
                enabled_words.add(word)
            forms = set()
            for form in map(lambda x: x.get("form"), data.get("forms", [])):
                if form and form not in enabled_words and len(form) >= len_limit:
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
                        enabled,
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


def dump_wiktionary(json_path, dump_path, lang, notif):
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
    json_path, dump_path, lang, kindle_lemmas, useragent, notif
):
    if useragent:
        download_path = download_wiktionary(
            json_path.parent, lang["kaikki"], useragent, notif
        )
        extract_wiktionary(download_path, lang["wiki"], kindle_lemmas, notif)
    if dump_path:
        dump_wiktionary(json_path, dump_path, lang["wiki"], notif)
