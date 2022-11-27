#!/usr/bin/env python3

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

# https://www.mediawiki.org/wiki/API:Get_the_contents_of_a_page
# https://www.mediawiki.org/wiki/Extension:TextExtracts#API
MEDIAWIKI_API_EXLIMIT = 20
FUZZ_THRESHOLD = 85.7

# https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L325
NER_LABELS = frozenset(
    [
        "EVENT",  # OntoNotes 5: English, Chinese
        "FAC",
        "GPE",
        "LAW",
        "LOC",
        "ORG",
        "PERSON",
        "PRODUCT",
        "MISC",  # Catalan
        "PER",
        "EVT",  # Norwegian Bokmål: https://github.com/ltgoslo/norne#entity-types
        "GPE_LOC",
        "GPE_ORG",
        "PROD",
        "geogName",  # Polish: https://arxiv.org/pdf/1811.10418.pdf#subsection.2.1
        "orgName",
        "persName",
        "placeName",
        "ORGANIZATION",  # Romanian: https://arxiv.org/pdf/1909.01247.pdf#section.4
        "PS",  # Korean: https://arxiv.org/pdf/2105.09680.pdf#subsubsection.3.4.1
        "LC",
        "OG",
        "EVN",  # Swedish: https://core.ac.uk/reader/33724960
        "PRS",
        "DERIV_PER",  # Croatian: https://nl.ijs.si/janes/wp-content/uploads/2017/09/SlovenianNER-eng-v1.1.pdf
    ]
)
PERSON_LABELS = frozenset(["PERSON", "PER", "persName", "PS", "PRS", "DERIV_PER"])
GPE_LABELS = frozenset(["GPE", "GPE_LOC", "GPE_ORG", "placeName", "LC"])


class MediaWiki:
    def __init__(self, cache_path: Path, useragent: str) -> None:
        import requests

        self.cache_path = cache_path
        if not cache_path.parent.exists():
            cache_path.parent.mkdir()
        if cache_path.exists():
            with cache_path.open() as f:
                self.cache = json.load(f)
        else:
            self.cache = {}
        self.save_cache = False
        self.session = requests.Session()
        self.session.headers.update({"user-agent": useragent})

    def get_cache(self, key: str) -> Any:
        data = self.get_direct_cache(key)
        if isinstance(data, str):
            return self.get_direct_cache(data)
        return data

    def get_direct_cache(self, key: str) -> Any:
        return self.cache.get(key)

    def add_cache(self, key: str, value: Any) -> None:
        self.cache[key] = value
        self.save_cache = True

    def has_cache(self, key: str) -> bool:
        return key in self.cache

    def close(self) -> None:
        self.session.close()
        if self.save_cache:
            with self.cache_path.open("w") as f:
                json.dump(self.cache, f)


class Wikipedia(MediaWiki):
    def __init__(
        self, lang: str, useragent: str, plugin_path: Path, prefs: dict[str, str]
    ) -> None:
        self.lang = lang
        self.source_id = 1
        self.source_name = "Wikipedia"
        self.source_link = (
            f"https://{lang}.wikipedia.org/wiki/"
            if lang != "zh"
            else f"https://zh.wikipedia.org/zh-{prefs['zh_wiki_variant']}/"
        )
        self.wiki_api = f"https://{lang}.wikipedia.org/w/api.php"
        cache_path = plugin_path.parent.joinpath(f"worddumb-wikimedia/{lang}.json")

        super().__init__(cache_path, useragent)
        self.session.params = {"format": "json", "formatversion": 2}
        if lang == "zh":
            self.session.params["variant"] = f"zh-{prefs['zh_wiki_variant']}"

    def query(self, titles: set[str]) -> None:
        result = self.session.get(
            self.wiki_api,
            params={
                "action": "query",
                "prop": "extracts|pageprops",
                "exintro": 1,
                "explaintext": 1,
                "redirects": 1,
                "exsentences": 7,
                "ppprop": "wikibase_item",
                "titles": "|".join(titles),
            },
        )
        data = result.json()
        converts = defaultdict(list)
        redirect_to_sections = defaultdict(dict)
        for convert_type in ["normalized", "redirects"]:
            for d in data["query"].get(convert_type, []):
                # different titles can be redirected to the same page
                converts[d["to"]].append(d["from"])
                if "tofragment" in d:
                    redirect_to_sections[d["to"]][d["tofragment"]] = d["from"]

        for v in data["query"]["pages"]:
            if "extract" not in v:  # missing or invalid
                continue
            # they are ordered by pageid, ehh
            title = v["title"]
            summary = v["extract"]
            if title in redirect_to_sections and title not in titles:
                continue
            if not any(period in summary for period in [".", "。"]):
                continue  # very likely a disambiguation page
            self.add_cache(
                title,
                {
                    "intro": summary,
                    "item_id": v.get("pageprops", {}).get("wikibase_item"),
                },
            )
            if title in titles:
                titles.remove(title)
            for key in converts.get(title, []):
                self.add_cache(key, title)
                if key in titles:
                    titles.remove(key)
                for k in converts.get(key, []):
                    self.add_cache(k, title)
                    if k in titles:  # normalize then redirect
                        titles.remove(k)

        self.get_section_text(redirect_to_sections, converts, titles)
        for title in titles:  # use quote next time
            self.add_cache(title, None)

    def get_section_text(
        self,
        redirect_to_sections: dict[dict[str, str]],
        converts: dict[str, list[str]],
        titles: set[str],
    ) -> None:
        from lxml import etree

        for page, section_to_titles in redirect_to_sections.items():
            r = self.session.get(
                self.wiki_api,
                params={
                    "action": "parse",
                    "prop": "sections",
                    "page": page,
                },
            )
            result = r.json()
            for section in result.get("parse", {}).get("sections", []):
                if section["line"] in section_to_titles:
                    r = self.session.get(
                        self.wiki_api,
                        params={
                            "action": "parse",
                            "prop": "text",
                            "section": section["index"],
                            "disabletoc": 1,
                            "disableeditsection": 1,
                            "disablelimitreport": 1,
                            "page": page,
                        },
                    )
                    section_result = r.json()
                    html_text = section_result.get("parse", {}).get("text")
                    if not html_text:
                        continue
                    html = etree.HTML(html_text)
                    # Remove references
                    for e in html.xpath("//p[1]/sup[contains(@class, 'reference')]"):
                        e.getparent().remove(e)
                    text = e.xpath("string(//p[1])")
                    if not text:
                        continue
                    text = text.strip()
                    redirected_title = section_to_titles[section["line"]]
                    self.add_cache(redirected_title, text)
                    if redirected_title in titles:
                        titles.remove(redirected_title)
                    for converted_title in converts.get(redirected_title, []):
                        self.add_cache(converted_title, text)
                        if converted_title in titles:
                            titles.remove(converted_title)


class Fandom(MediaWiki):
    def __init__(
        self, useragent: str, plugin_path: Path, prefs: dict[str, str]
    ) -> None:
        self.source_id = 2
        self.source_name = "Fandom"
        self.source_link = f"{prefs['fandom']}/wiki/"
        self.wiki_api = f"{prefs['fandom']}/api.php"
        # Remove "https://" from Fandom URL
        cache_path = plugin_path.parent.joinpath(
            f"worddumb-fandom/{prefs['fandom'][8:].replace('/', '')}.json"
        )

        super().__init__(cache_path, useragent)
        # Fandom doesn't have TextExtract extension
        # https://www.mediawiki.org/wiki/API:Parse
        self.session.params = {
            "format": "json",
            "action": "parse",
            "prop": "text",
            "section": 0,
            "redirects": 1,
            "disablelimitreport": 1,
            "formatversion": 2,
        }

    def query(self, page: str) -> None:
        from lxml import etree

        result = self.session.get(self.wiki_api, params={"page": page})
        data = result.json()
        if "parse" in data:
            data = data["parse"]
            text = data["text"]
            html = etree.HTML(text)
            # Remove infobox and quote element
            for e in html.xpath("//table | //aside | //dl"):
                e.getparent().remove(e)
            intro = html.xpath("string()").strip()
            self.add_cache(page, {"intro": intro})
            for redirect in data.get("redirects", []):
                self.add_cache(redirect["to"], redirect["from"])
        else:
            self.add_cache(page, None)  # Not found


class Wikimedia_Commons:
    def __init__(self, plugin_path: str, useragent: str) -> None:
        import requests

        self.session = requests.Session()
        self.session.headers.update({"user-agent": useragent})
        self.cache_folder = plugin_path.parent.joinpath("worddumb-wikimedia")

    def get_image(self, filename: str) -> Path:
        file_path = self.cache_folder.joinpath(filename)
        if not file_path.exists():
            self.download_image(filename, file_path)
        return file_path

    def download_image(self, filename: str, file_path: Path) -> None:
        r = self.session.get(
            f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
        )
        with file_path.open("wb") as f:
            f.write(r.content)

    def close(self) -> None:
        self.session.close()


class Wikidata(MediaWiki):
    def __init__(self, plugin_path: str, useragent: str) -> None:
        super().__init__(
            plugin_path.parent.joinpath("worddumb-wikimedia/wikidata.json"), useragent
        )

    def query(self, items: list[str]) -> None:
        items = " ".join(map(lambda x: f"wd:{x}", items))
        query = f"""
        SELECT ?item (SAMPLE(?maps) AS ?map) (MAX(?inceptions) AS ?inception) WHERE {{
          VALUES ?item {{ {items} }}
          OPTIONAL {{
            ?item (p:P242/ps:P242) ?maps.
            FILTER(REGEX(STR(?maps), "(orthographic|globe)", "i"))
          }}
          OPTIONAL {{ ?item wdt:P242 ?maps. }}
          OPTIONAL {{ ?item wdt:P571 ?inceptions. }}
        }}
        GROUP BY ?item
        """
        result = self.session.get(
            "https://query.wikidata.org/sparql",
            params={"query": query, "format": "json"},
        )
        result = result.json()
        for binding in result.get("results", {}).get("bindings"):
            item_id = binding["item"]["value"].split("/")[-1]
            map_url = binding.get("map", {}).get("value")
            inception = binding.get("inception", {}).get("value")
            if inception and inception.startswith("http"):  # unknown value, Q649
                inception = None
            if map_url or inception:
                self.add_cache(
                    item_id,
                    {
                        "map_filename": unquote(map_url).split("/")[-1]
                        if map_url
                        else None,
                        "inception": inception,
                    },
                )
            else:
                self.add_cache(item_id, None)


def inception_text(inception: str) -> str:
    if inception.startswith("-"):
        bc = int(inception[1:5]) + 1  # 2BC: -0001, 1BC: +0000, 1AD: 0001
        years = datetime.now().year + bc
        return f"Inception: {bc} BC({years} years ago)"
    else:
        # don't need to remove the last "Z" in Python 3.11
        inception = datetime.fromisoformat(inception[:-1])
        # Python 3.11: datetime.now(timezone.utc) - inception
        years = (datetime.now() - inception).days // 365
        return f"Inception: {inception.strftime('%d %B %Y').lstrip('0')}({years} years ago)"


def query_mediawiki(
    entities: dict[str, dict[str, str]], mediawiki: MediaWiki, search_people: bool
) -> None:
    pending_entities = set()
    for entity, data in entities.items():
        if (
            isinstance(mediawiki, Wikipedia)
            and len(pending_entities) == MEDIAWIKI_API_EXLIMIT
        ):
            mediawiki.query(pending_entities)
            pending_entities.clear()
        elif not mediawiki.has_cache(entity) and (
            search_people or data["label"] not in PERSON_LABELS
        ):
            if isinstance(mediawiki, Wikipedia):
                pending_entities.add(entity)
            else:
                mediawiki.query(entity)
    if len(pending_entities):
        mediawiki.query(pending_entities)
    mediawiki.close()


def query_wikidata(
    entities: dict[str, dict[str, str]], mediawiki: MediaWiki, wikidata: Wikidata
) -> None:
    pending_item_ids = []
    for item_id in filter(
        lambda x: x and not wikidata.has_cache(x),
        (
            mediawiki.get_cache(entity).get("item_id")
            for entity, data in entities.items()
            if is_gpe_label(mediawiki.lang, data["label"])
            and mediawiki.get_cache(entity)
        ),
    ):
        if len(pending_item_ids) == MEDIAWIKI_API_EXLIMIT:
            wikidata.query(pending_item_ids)
            pending_item_ids.clear()
        else:
            pending_item_ids.append(item_id)
    if len(pending_item_ids):
        wikidata.query(pending_item_ids)
    wikidata.close()


def is_gpe_label(lang: str, label: str) -> bool:
    if lang in ["sv", "hr"]:
        return label == "LOC"
    else:
        return label in GPE_LABELS


# https://en.wikipedia.org/wiki/Interpunct
NAME_DIVISION_REG = r"\s|\u00B7|\u2027|\u30FB|\uFF65"


def is_full_name(
    partial_name: str, partial_label: str, full_name: str, full_label: str
) -> bool:
    return (
        not re.search(NAME_DIVISION_REG, partial_name)
        and re.search(NAME_DIVISION_REG, full_name)
        and partial_label in PERSON_LABELS
        and full_label in PERSON_LABELS
    )
