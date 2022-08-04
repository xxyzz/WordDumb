#!/usr/bin/env python3

import json
import pickle
import re

try:
    from .tst import TST
except ImportError:
    from tst import TST

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


FILTER_TAGS = frozenset(
    {
        "plural",
        "alternative",
        "obsolete",
        "abbreviation",
        "initialism",
        "form-of",
        "misspelling",
        "alt-of",
    }
)


def extract_wiktionary(download_path, lang, kindle_lemmas, notif):
    if notif:
        notif.put((0, "Extracting Wiktionary file"))
    words = []
    enabled_words_pos = set()
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

            word_pos = f"{word} {pos}"
            enabled = False if word_pos in enabled_words_pos else True
            if kindle_lemmas and enabled:
                enabled = word in kindle_lemmas
            if enabled:
                enabled_words_pos.add(word_pos)
            forms = set()
            for form in map(lambda x: x.get("form"), data.get("forms", [])):
                if form and form != word and len(form) >= len_limit:
                    forms.add(form)

            for sense in data.get("senses", []):
                if "synonyms" in sense:
                    continue
                examples = sense.get("examples", [])
                glosses = sense.get("glosses")
                example_sent = None
                if not glosses:
                    continue
                if len(glosses) > 1:
                    gloss = glosses[1]
                else:
                    gloss = glosses[0]
                tags = set(sense.get("tags", []))
                if tags.intersection(FILTER_TAGS):
                    continue
                for example in examples:
                    example = example.get("text")
                    if example and example != "(obsolete)":
                        example_sent = example
                        break
                short_gloss = short_def(gloss)
                if short_gloss == "of":
                    continue
                words.append(
                    (
                        enabled,
                        word,
                        pos,
                        short_gloss,
                        gloss,
                        example_sent,
                        ",".join(forms),
                        get_ipas(lang, data.get("sounds", [])),
                    )
                )
                enabled = False

    download_path.unlink()
    words.sort(key=lambda x: x[1])
    lemmas_tst = TST()
    lemmas_tst.put_values([(x[1], row) for row, x in enumerate(words)])
    with download_path.parent.joinpath(f"wiktionary_{lang}_tst").open("wb") as f:
        pickle.dump(lemmas_tst, f)
    with open(
        download_path.with_name(f"wiktionary_{lang}.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(words, f)


def get_ipas(lang, sounds):
    ipas = {}
    if lang == "en":
        for sound in sounds:
            ipa = sound.get("ipa")
            if not ipa:
                continue
            tags = sound.get("tags")
            if not tags:
                return ipa
            if ("US" in tags or "General-American" in tags) and "US" not in ipas:
                ipas["US"] = ipa
            if ("UK" in tags or "Received-Pronunciation" in tags) and "UK" not in ipas:
                ipas["UK"] = ipa
    elif lang == "zh":
        for sound in sounds:
            pron = sound.get("zh-pron")
            if not pron:
                continue
            tags = sound.get("tags")
            if not tags:
                return pron
            if "Mandarin" in tags:
                if "Pinyin" in tags and "Pinyin" not in ipas:
                    ipas["Pinyin"] = pron
                elif "bopomofo" in tags and "bopomofo" not in ipas:
                    ipas["bopomofo"] = pron
    else:
        for sound in sounds:
            if "ipa" in sound:
                return sound["ipa"]

    return ipas if ipas else ""


def get_ipa(lang, ipa_tag, ipas):
    if not ipas:
        return ""
    elif lang in ["en", "zh"]:
        if isinstance(ipas, str):
            return ipas
        elif ipa_tag in ipas:
            return ipas[ipa_tag]
        elif lang == "en":
            for ipa in ipas.values():
                return ipa
    else:
        return ipas


def dump_wiktionary(json_path, dump_path, lang, ipa_tag, notif):
    if notif:
        notif.put((0, "Converting Wiktionary file"))

    with open(json_path, encoding="utf-8") as f:
        words = json.load(f)

    if lang in CJK_LANGS:
        import ahocorasick

        automaton = ahocorasick.Automaton()
        for _, word, _, short_gloss, gloss, example, forms, ipas in filter(
            lambda x: x[0] and not automaton.exists(x[1]), words
        ):
            ipa = get_ipa(lang, ipa_tag, ipas)
            automaton.add_word(word, (word, short_gloss, gloss, example, ipa))
            for form in filter(lambda x: not automaton.exists(x), forms.split(",")):
                automaton.add_word(form, (form, short_gloss, gloss, example, ipa))

        automaton.make_automaton()
        automaton.save(str(dump_path), pickle.dumps)
    else:
        from flashtext import KeywordProcessor

        keyword_processor = KeywordProcessor()
        for _, word, _, short_gloss, gloss, example, forms, ipas in filter(
            lambda x: x[0] and x[1] not in keyword_processor, words
        ):
            ipa = get_ipa(lang, ipa_tag, ipas)
            keyword_processor.add_keyword(word, (short_gloss, gloss, example, ipa))
            for form in filter(lambda x: x not in keyword_processor, forms.split(",")):
                keyword_processor.add_keyword(form, (short_gloss, gloss, example, ipa))

        with open(dump_path, "wb") as f:
            pickle.dump(keyword_processor, f)


def short_def(gloss: str) -> str:
    gloss = gloss[0].lower() + gloss[1:]
    gloss = gloss.removesuffix(".")
    gloss = re.sub(r"\([^)]+\) ?", "", gloss)
    gloss = min(gloss.split(";"), key=len)
    gloss = gloss.split(",", 1)[0]
    return gloss.strip()


def download_and_dump_wiktionary(
    json_path, dump_path, lang, kindle_lemmas, useragent, ipa_tag, notif
):
    if useragent:
        download_path = download_wiktionary(
            json_path.parent, lang["kaikki"], useragent, notif
        )
        extract_wiktionary(download_path, lang["wiki"], kindle_lemmas, notif)
    if dump_path:
        dump_wiktionary(json_path, dump_path, lang["wiki"], ipa_tag, notif)
