#!/usr/bin/env python3

import json
from collections import defaultdict
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
    ]
)
PERSON_LABELS = frozenset(["PERSON", "PER", "persName"])
GPE_LABELS = frozenset(["GPE", "GPE_LOC", "GPE_ORG", "placeName"])


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
        if prefs["fandom"]:
            self.source_name = "Fandom"
            self.source_link = f"{prefs['fandom']}/wiki/"
            self.wiki_api = f"{prefs['fandom']}/api.php"
            cache_path = plugin_path.parent.joinpath(
                f"worddumb-fandom/{prefs['fandom'][8:]}.json"
            )
        else:
            self.source_name = "Wikipedia"
            self.source_link = f"https://{lang}.wikipedia.org/wiki/"
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
            self.source_link = (
                f"https://zh.wikipedia.org/zh-{prefs['zh_wiki_variant']}/"
            )

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
        SELECT ?item ?democracy_index (SAMPLE(?maps) AS ?map) WHERE {{
          VALUES ?item {{ {items} }}
          OPTIONAL {{
            ?item (p:P242/ps:P242) ?maps.
            FILTER(REGEX(STR(?maps), "(orthographic|globe)", "i"))
          }}
          OPTIONAL {{ ?item wdt:P242 ?maps. }}
          OPTIONAL {{
            ?item p:P8328 ?statement.
            ?statement ps:P8328 ?democracy_index;
              pq:P585 ?most_recent.
            {{
              SELECT ?item (MAX(?point_in_time) AS ?most_recent) WHERE {{
                VALUES ?item {{ {items} }}
                ?item (p:P8328/pq:P585) ?point_in_time.
              }}
              GROUP BY ?item
            }}
          }}
        }}
        GROUP BY ?item ?democracy_index
        """
        result = self.session.get(
            "https://query.wikidata.org/sparql",
            params={"query": query, "format": "json"},
        )
        result = result.json()
        for binding in result.get("results", {}).get("bindings"):
            item_id = binding["item"]["value"].split("/")[-1]
            democracy_index = binding.get("democracy_index", {}).get("value")
            map_url = binding.get("map", {}).get("value")
            if democracy_index or map_url:
                self.add_cache(
                    item_id,
                    {
                        "democracy_index": democracy_index,
                        "map_filename": unquote(map_url).split("/")[-1]
                        if map_url
                        else None,
                    },
                )
            else:
                self.add_cache(item_id, None)


def regime_type(democracy_index_score):
    if democracy_index_score > 8:
        regime_type = "full democracy"
    elif democracy_index_score > 6:
        regime_type = "flawed democracy"
    elif democracy_index_score > 4:
        regime_type = "hybrid regime"
    else:
        regime_type = "authoritarian regime"

    return f"Democracy Index: {democracy_index_score} {regime_type}"


def query_mediawiki(entities, mediawiki, search_people):
    pending_entities = []
    for entity, data in entities.copy().items():
        if isinstance(data, str):
            del entities[entity]
            continue
        if len(pending_entities) == MEDIAWIKI_API_EXLIMIT:
            mediawiki.query(pending_entities)
            pending_entities.clear()
        elif not mediawiki.has_cache(entity) and (
            search_people or data["label"] not in PERSON_LABELS
        ):
            pending_entities.append(entity)
    if len(pending_entities):
        mediawiki.query(pending_entities)


def query_wikidata(entities, mediawiki, wikidata):
    pending_item_ids = []
    for item_id in filter(
        lambda x: x and not wikidata.has_cache(x),
        (
            mediawiki.get_cache(entity).get("item_id")
            for entity, data in entities.items()
            if data["label"] in GPE_LABELS and mediawiki.get_cache(entity)
        ),
    ):
        if len(pending_item_ids) == MEDIAWIKI_API_EXLIMIT:
            wikidata.query(pending_item_ids)
            pending_item_ids.clear()
        else:
            pending_item_ids.append(item_id)
    if len(pending_item_ids):
        wikidata.query(pending_item_ids)
