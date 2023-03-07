#!/usr/bin/env python3

import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote

try:
    from .x_ray_share import FUZZ_THRESHOLD, PERSON_LABELS, XRayEntity
except ImportError:
    from x_ray_share import FUZZ_THRESHOLD, PERSON_LABELS, XRayEntity

# https://www.mediawiki.org/wiki/API:Get_the_contents_of_a_page
# https://www.mediawiki.org/wiki/Extension:TextExtracts#API
MEDIAWIKI_API_EXLIMIT = 20

GPE_LABELS = frozenset(["GPE", "GPE_LOC", "GPE_ORG", "placeName", "LC"])


class WikipediaCache(TypedDict):
    intro: str
    item_id: str | None


class Wikipedia:
    def __init__(
        self, lang: str, useragent: str, plugin_path: Path, zh_wiki_variant: str
    ) -> None:
        self.lang = lang
        self.source_id = 1
        self.wiki_api = f"https://{lang}.wikipedia.org/w/api.php"
        self.db_conn = self.init_db(plugin_path, lang)
        self.session = self.init_requests_session(useragent, lang, zh_wiki_variant)

    def init_db(self, plugin_path: Path, lang: str) -> sqlite3.Connection:
        db_path = plugin_path.parent.joinpath(f"worddumb-wikimedia/{lang}.db")
        if not db_path.parent.exists():
            db_path.parent.mkdir()

        db_conn = sqlite3.connect(db_path)
        db_conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS titles (title TEXT PRIMARY KEY COLLATE NOCASE, desc_id INTEGER);
            CREATE TABLE IF NOT EXISTS descriptions (id INTEGER PRIMARY KEY, description TEXT, wikidata_item TEXT);
            """
        )
        return db_conn

    def init_requests_session(self, useragent: str, lang: str, zh_wiki_variant: str):
        import requests

        session = requests.Session()
        session.headers.update({"user-agent": useragent})
        session.params = {"format": "json", "formatversion": 2}
        if lang == "zh":
            session.params["variant"] = f"zh-{zh_wiki_variant}"
        return session

    def close(self):
        self.session.close()
        self.db_conn.execute("CREATE INDEX IF NOT EXISTS idx_titles ON titles(desc_id)")
        self.db_conn.commit()
        self.db_conn.close()

    def add_cache(self, title: str, intro: str, wikidata_item: str | None) -> int:
        desc_id = 0
        for (new_desc_id,) in self.db_conn.execute(
            "INSERT INTO descriptions (description, wikidata_item) VALUES(?, ?) RETURNING id",
            (intro, wikidata_item),
        ):
            desc_id = new_desc_id
        self.add_title(title, desc_id)
        return desc_id

    def has_cache(self, title: str) -> bool:
        for _ in self.db_conn.execute("SELECT * FROM titles WHERE title = ?", (title,)):
            return True
        return False

    def get_cache(self, title: str) -> WikipediaCache | None:
        for desc, wikidata_item in self.db_conn.execute(
            "SELECT description, wikidata_item FROM titles JOIN descriptions ON titles.desc_id = descriptions.id WHERE title = ?",
            (title,),
        ):
            return {"intro": desc, "item_id": wikidata_item}
        return None

    def add_title(self, title: str, desc_id: int | None) -> None:
        self.db_conn.execute(
            "INSERT OR IGNORE INTO titles VALUES(?, ?)", (title, desc_id)
        )

    def redirected_titles(self, title: str) -> list[str]:
        return [
            other_title
            for (other_title,) in self.db_conn.execute(
                "SELECT title FROM titles WHERE desc_id = (SELECT desc_id FROM titles WHERE title = ?) AND title != ?",
                (title, title),
            )
        ]

    def query(self, titles: set[str]) -> None:
        result = self.session.get(
            self.wiki_api,
            params={
                "action": "query",
                "prop": "extracts|pageprops",
                "exintro": 1,
                "explaintext": 1,
                "redirects": 1,
                "ppprop": "wikibase_item|disambiguation",
                "titles": "|".join(titles),
            },
        )
        if not result.ok:
            return
        data = result.json()
        converts = defaultdict(list)
        redirect_to_sections: dict[str, dict[str, str]] = defaultdict(dict)
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
            if "pageprops" in v and "disambiguation" in v["pageprops"]:
                continue
            wikibase_item = v.get("pageprops", {}).get("wikibase_item")
            desc_id = self.add_cache(title, summary, wikibase_item)
            if title in titles:
                titles.remove(title)
            for key in converts.get(title, []):
                self.add_title(key, desc_id)
                if key in titles:
                    titles.remove(key)
                for k in converts.get(key, []):
                    self.add_title(k, desc_id)
                    if k in titles:  # normalize then redirect
                        titles.remove(k)

        self.get_section_text(redirect_to_sections, converts, titles)
        for title in titles:  # use quote next time
            self.add_title(title, None)

    def get_section_text(
        self,
        redirect_to_sections: dict[str, dict[str, str]],
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
            if not r.ok:
                return
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
                    text = html.xpath("string(//p[1])")
                    if not text:
                        continue
                    text = text.strip()
                    redirected_title = section_to_titles[section["line"]]
                    desc_id = self.add_cache(redirected_title, text, None)
                    if redirected_title in titles:
                        titles.remove(redirected_title)
                    for converted_title in converts.get(redirected_title, []):
                        self.add_title(converted_title, desc_id)
                        if converted_title in titles:
                            titles.remove(converted_title)


class Fandom:
    def __init__(self, useragent: str, plugin_path: Path, fandom_url: str) -> None:
        self.source_id = 2
        self.wiki_api = f"{fandom_url}/api.php"
        self.db_conn = self.init_db(plugin_path, fandom_url)
        self.session = self.init_requests_session(useragent)

    def init_db(self, plugin_path: Path, fandom_url: str) -> sqlite3.Connection:
        # Remove "https://" from Fandom URL
        db_path = plugin_path.parent.joinpath(
            f"worddumb-fandom/{fandom_url[8:].replace('/', '')}.db"
        )
        if not db_path.parent.exists():
            db_path.parent.mkdir()
        db_conn = sqlite3.connect(db_path)
        db_conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS titles (title TEXT PRIMARY KEY COLLATE NOCASE, desc_id INTEGER);
            CREATE TABLE IF NOT EXISTS descriptions (id INTEGER PRIMARY KEY, description TEXT);
            """
        )
        return db_conn

    def init_requests_session(self, useragent: str):
        import requests

        session = requests.Session()
        session.headers.update({"user-agent": useragent})
        # Fandom doesn't have TextExtract extension
        # https://www.mediawiki.org/wiki/API:Parse
        session.params = {
            "format": "json",
            "action": "parse",
            "prop": "text|properties|links",
            "section": 0,
            "redirects": 1,
            "disablelimitreport": 1,
            "formatversion": 2,
        }
        return session

    def close(self):
        self.session.close()
        self.db_conn.execute("CREATE INDEX IF NOT EXISTS idx_titles ON titles(desc_id)")
        self.db_conn.commit()
        self.db_conn.close()

    def add_cache(self, title: str, intro: str) -> int:
        desc_id = 0
        for (new_desc_id,) in self.db_conn.execute(
            "INSERT INTO descriptions (description) VALUES(?) RETURNING id",
            (intro,),
        ):
            desc_id = new_desc_id
        self.add_title(title, desc_id)
        return desc_id

    def has_cache(self, title: str) -> bool:
        for _ in self.db_conn.execute("SELECT * FROM titles WHERE title = ?", (title,)):
            return True
        return False

    def get_cache(self, title: str) -> str | None:
        for (desc,) in self.db_conn.execute(
            "SELECT description FROM titles JOIN descriptions ON titles.desc_id = descriptions.id WHERE title = ?",
            (title),
        ):
            return desc
        return None

    def add_title(self, title: str, desc_id: int | None) -> None:
        self.db_conn.execute(
            "INSERT OR IGNORE INTO titles VALUES(?, ?)", (title, desc_id)
        )

    def redirected_titles(self, title: str) -> list[str]:
        return [
            other_title
            for (other_title,) in self.db_conn.execute(
                "SELECT title FROM titles WHERE desc_id = (SELECT desc_id FROM titles WHERE title = ?) AND title != ?",
                (title, title),
            )
        ]

    def query(self, page: str, from_disambiguation_title: str | None = None) -> None:
        from lxml import etree
        from rapidfuzz.fuzz import token_set_ratio
        from rapidfuzz.process import extractOne

        result = self.session.get(self.wiki_api, params={"page": page})
        if not result.ok:
            return
        data = result.json()
        if "parse" in data:
            data = data["parse"]
            if (
                "properties" in data
                and "disambiguation" in data["properties"]
                and from_disambiguation_title is None
            ):
                # Choose the most similar title in disambiguation page
                disambiguation_titles = [
                    link["title"]
                    for link in data.get("links", [])
                    if link["ns"] == 0 and link["exists"]
                ]
                r = extractOne(
                    page,
                    disambiguation_titles,
                    score_cutoff=FUZZ_THRESHOLD,
                    scorer=token_set_ratio,
                )
                if r is not None:
                    chosen_title = r[0]
                    self.query(chosen_title, page)
                else:
                    self.add_title(page, None)
                return

            text = data["text"]
            html = etree.HTML(text)
            # Remove infobox, quote, references, error
            for e in html.xpath(
                "//table | //aside | //dl | //*[contains(@class, 'reference')] | //span[contains(@class, 'error')]"
            ):
                e.getparent().remove(e)
            intro = html.xpath("string()").strip()
            desc_id = self.add_cache(page, intro)
            for redirect in data.get("redirects", []):
                self.add_title(redirect["to"], desc_id)
            if from_disambiguation_title is not None:
                self.add_title(from_disambiguation_title, desc_id)
        else:
            self.add_title(page, None)  # Not found


class Wikimedia_Commons:
    def __init__(self, plugin_path: Path, useragent: str) -> None:
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


class WikidataCache(TypedDict):
    map_filename: str | None
    inception: str | None


class Wikidata:
    def __init__(self, plugin_path: Path, useragent: str) -> None:
        import requests

        self.session = requests.Session()
        self.session.headers.update({"user-agent": useragent})

        cache_db_path = plugin_path.parent.joinpath("worddumb-wikimedia/wikidata.db")
        self.init_db(cache_db_path)

    def init_db(self, db_path: Path) -> None:
        create_db = not db_path.exists()
        self.db_conn = sqlite3.connect(db_path)
        if create_db:
            self.db_conn.execute(
                "CREATE TABLE wikidata (item TEXT PRIMARY KEY, map_filename TEXT, inception TEXT)"
            )

    def close(self):
        self.session.close()
        self.db_conn.commit()
        self.db_conn.close()

    def add_cache(
        self, item: str, map_filename: str | None, inception: str | None
    ) -> None:
        self.db_conn.execute(
            "INSERT INTO wikidata VALUES(?, ?, ?)", (item, map_filename, inception)
        )

    def has_cache(self, item: str) -> bool:
        return self.get_cache(item) is not None

    def get_cache(self, item: str) -> WikidataCache | None:
        for map_filename, inception in self.db_conn.execute(
            "SELECT map_filename, inception FROM wikidata WHERE item = ?", (item,)
        ):
            return {"map_filename": map_filename, "inception": inception}
        return None

    def query(self, items: list[str]) -> None:
        items_str = " ".join(map(lambda x: f"wd:{x}", items))
        query = f"""
        SELECT ?item (SAMPLE(?maps) AS ?map) (MAX(?inceptions) AS ?inception) WHERE {{
          VALUES ?item {{ {items_str} }}
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
        if not result.ok:
            return
        for binding in result.json().get("results", {}).get("bindings"):
            item_id = binding["item"]["value"].split("/")[-1]
            map_url = binding.get("map", {}).get("value")
            inception = binding.get("inception", {}).get("value")
            if inception and inception.startswith("http"):  # unknown value, Q649
                inception = None
            if map_url or inception:
                self.add_cache(
                    item_id,
                    unquote(map_url).split("/")[-1] if map_url else None,
                    inception,
                )
            else:
                self.add_cache(item_id, None, None)


def inception_text(inception_str: str) -> str:
    # don't need to remove the last "Z" in Python 3.11
    inception_str = inception_str.removesuffix("Z")
    if inception_str.startswith("-"):
        bc = int(inception_str[1:5]) + 1  # 2BC: -0001, 1BC: +0000, 1AD: 0001
        years = datetime.now().year + bc
        return f"Inception: {bc} BC({years} years ago)"
    else:
        inception = datetime.fromisoformat(inception_str)
        # Python 3.11: datetime.now(timezone.utc) - inception
        years = (datetime.now() - inception).days // 365
        return f"Inception: {inception.strftime('%d %B %Y').lstrip('0')}({years} years ago)"


def query_mediawiki(
    entities: dict[str, XRayEntity], mediawiki: Wikipedia | Fandom, search_people: bool
) -> None:
    pending_entities: set[str] = set()
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
    if len(pending_entities) and isinstance(mediawiki, Wikipedia):
        mediawiki.query(pending_entities)


def query_wikidata(
    entities: dict[str, XRayEntity], mediawiki: Wikipedia, wikidata: Wikidata
) -> None:
    pending_item_ids: list[str] = []
    for entity, data in entities.items():
        if not is_gpe_label(mediawiki.lang, data["label"]):
            continue
        mediawiki_cache = mediawiki.get_cache(entity)
        if mediawiki_cache is None or mediawiki_cache["item_id"] is None:
            continue
        item_id = mediawiki_cache["item_id"]
        if wikidata.has_cache(item_id):
            continue
        if len(pending_item_ids) == MEDIAWIKI_API_EXLIMIT:
            wikidata.query(pending_item_ids)
            pending_item_ids.clear()
        else:
            pending_item_ids.append(item_id)
    if len(pending_item_ids):
        wikidata.query(pending_item_ids)


def is_gpe_label(lang: str, label: str) -> bool:
    if lang in ["sv", "hr"]:
        return label == "LOC"
    else:
        return label in GPE_LABELS
