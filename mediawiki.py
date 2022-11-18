#!/usr/bin/env python3

import json
import re
from collections import defaultdict
from datetime import datetime
from urllib.parse import unquote

# https://www.mediawiki.org/wiki/Special:MyLanguage/Extension:TextExtracts#API
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


class MediaWikiBase:
    def __init__(self, cache_path, useragent):
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

    def get_cache(self, key):
        data = self.get_direct_cache(key)
        if isinstance(data, str):
            return self.get_direct_cache(data)
        return data

    def get_direct_cache(self, key):
        return self.cache.get(key)

    def add_cache(self, key, value):
        self.cache[key] = value
        self.save_cache = True

    def has_cache(self, key):
        return key in self.cache

    def close(self):
        self.session.close()
        if self.save_cache:
            with self.cache_path.open("w") as f:
                json.dump(self.cache, f)


class MediaWiki(MediaWikiBase):
    def __init__(self, lang, useragent, plugin_path, prefs):
        self.lang = lang
        self.prefs = prefs
        if prefs["fandom"]:
            self.source_id = 2
            self.source_name, self.source_link = self.get_source(2)
            self.wiki_api = f"{prefs['fandom']}/api.php"
            cache_path = plugin_path.parent.joinpath(
                f"worddumb-fandom/{prefs['fandom'][8:].replace('/', '')}.json"
            )
        else:
            self.source_id = 1
            self.source_name, self.source_link = self.get_source(1)
            self.wiki_api = f"https://{lang}.wikipedia.org/w/api.php"
            cache_path = plugin_path.parent.joinpath(f"worddumb-wikimedia/{lang}.json")
        super().__init__(cache_path, useragent)
        self.session.params = {
            "format": "json",
            "action": "query",
            "prop": "extracts|pageprops",
            "exintro": 1,
            "explaintext": 1,
            "redirects": 1,
            "exsentences": 7,
            "formatversion": 2,
            "ppprop": "wikibase_item",
        }
        if lang == "zh" and not prefs["fandom"]:
            self.session.params["variant"] = f"zh-{prefs['zh_wiki_variant']}"

    def get_source(self, source_id):
        if source_id == 1:
            return (
                "Wikipedia",
                f"https://{self.lang}.wikipedia.org/wiki/"
                if self.lang != "zh"
                else f"https://zh.wikipedia.org/zh-{self.prefs['zh_wiki_variant']}/",
            )
        elif source_id == 2:
            return (
                "Fandom",
                f"{self.prefs['fandom']}/wiki/" if self.prefs["fandom"] else None,
            )

        return None  # book quote

    def query(self, titles):
        result = self.session.get(self.wiki_api, params={"titles": "|".join(titles)})
        data = result.json()
        converts = defaultdict(list)
        for convert_type in ["normalized", "redirects"]:
            for d in data["query"].get(convert_type, []):
                # different titles can be redirected to the same page
                converts[d["to"]].append(d["from"])

        for v in data["query"]["pages"]:
            if "extract" not in v:  # missing or invalid
                continue
            # they are ordered by pageid, ehh
            title = v["title"]
            summary = v["extract"]
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

        for title in titles:  # use quote next time
            self.add_cache(title, None)


class Wikimedia_Commons:
    def __init__(self, plugin_path, useragent):
        import requests

        self.session = requests.Session()
        self.session.headers.update({"user-agent": useragent})
        self.cache_folder = plugin_path.parent.joinpath("worddumb-wikimedia")

    def get_image(self, filename):
        file_path = self.cache_folder.joinpath(filename)
        if not file_path.exists():
            self.download_image(filename, file_path)
        return file_path

    def download_image(self, filename, file_path):
        r = self.session.get(
            f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
        )
        with file_path.open("wb") as f:
            f.write(r.content)

    def close(self):
        self.session.close()


class Wikidata(MediaWikiBase):
    def __init__(self, plugin_path, useragent):
        super().__init__(
            plugin_path.parent.joinpath("worddumb-wikimedia/wikidata.json"), useragent
        )

    def query(self, items):
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


def inception_text(inception):
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


def query_mediawiki(entities, mediawiki, search_people):
    pending_entities = []
    for entity, data in entities.items():
        if len(pending_entities) == MEDIAWIKI_API_EXLIMIT:
            mediawiki.query(pending_entities)
            pending_entities.clear()
        elif not mediawiki.has_cache(entity) and (
            search_people or data["label"] not in PERSON_LABELS
        ):
            pending_entities.append(entity)
    if len(pending_entities):
        mediawiki.query(pending_entities)
    mediawiki.close()


def query_wikidata(entities, mediawiki, wikidata):
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


def is_full_name(partial_name, partial_label, full_name, full_label):
    return (
        not re.search(NAME_DIVISION_REG, partial_name)
        and re.search(NAME_DIVISION_REG, full_name)
        and partial_label in PERSON_LABELS
        and full_label in PERSON_LABELS
    )
