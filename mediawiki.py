import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
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


@dataclass
class MediaWikiCache:
    intro: str
    wikidata_item_id: str | None


class MediaWiki:
    def __init__(
        self,
        api_url: str,
        lang: str,
        useragent: str,
        plugin_path: Path,
        lang_variant: str,
    ) -> None:
        self.lang = lang
        self.is_wikipedia = api_url == ""
        self.api_url = (
            f"https://{lang}.wikipedia.org/w/api.php" if self.is_wikipedia else api_url
        )
        self.db_conn = self.init_db(plugin_path)
        self.session = self.init_requests_session(useragent, lang_variant)
        self.sitename = "Wikipedia" if self.is_wikipedia else ""
        self.has_extracts_api = True if self.is_wikipedia else False
        if not self.is_wikipedia:
            self.get_api_info()

    def init_db(self, plugin_path: Path) -> sqlite3.Connection:
        domain = (
            self.api_url.removeprefix("https://")
            .removeprefix("http://")
            .split("/", 1)[0]
        )
        db_path = plugin_path.parent.joinpath(f"worddumb-mediawiki/{domain}.db")
        if not db_path.parent.exists():
            db_path.parent.mkdir()

        db_conn = sqlite3.connect(db_path)
        db_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pages (
              title TEXT PRIMARY KEY COLLATE NOCASE,
              description TEXT,
              wikidata_item TEXT,
              redirect_to TEXT
            )
            """
        )
        return db_conn

    def init_requests_session(self, useragent: str, lang_variant: str):
        import requests

        session = requests.Session()
        session.headers.update({"user-agent": useragent})
        session.params = {"format": "json", "formatversion": 2, "variant": lang_variant}
        return session

    def close(self):
        self.session.close()
        self.db_conn.commit()
        self.db_conn.execute("PRAGMA optimize")
        self.db_conn.close()

    def get_api_info(self) -> None:
        # https://www.mediawiki.org/wiki/API:Siteinfo
        result = self.session.get(
            self.api_url,
            params={"action": "query", "meta": "siteinfo", "siprop": "general"},
        )
        if result.ok:
            data = result.json()
            self.sitename = data.get("query", {}).get("general", {}).get("sitename", "")

        # https://www.mediawiki.org/wiki/API:Parameter_information
        result = self.session.get(
            self.api_url, params={"action": "paraminfo", "modules": "query+extracts"}
        )
        if result.ok:
            data = result.json()
            for module in data.get("paraminfo", {}).get("modules", []):
                if module.get("name", "") == "extracts":
                    self.has_extracts_api = True

    def add_cache(self, title: str, intro: str, wikidata_item: str | None) -> None:
        self.db_conn.execute(
            """
            INSERT OR IGNORE INTO pages
            (title, description, wikidata_item) VALUES(?, ?, ?)
            """,
            (title, intro, wikidata_item),
        )

    def has_cache(self, title: str) -> bool:
        for _ in self.db_conn.execute(
            "SELECT title FROM pages WHERE title = ? LIMIT 1", (title,)
        ):
            return True
        return False

    def get_cache(self, title: str) -> MediaWikiCache | None:
        for desc, wikidata_item in self.db_conn.execute(
            """
            SELECT description, wikidata_item
            FROM pages WHERE title = ?
            UNION ALL
            SELECT a.description, a.wikidata_item
            FROM pages a JOIN pages b ON a.title = b.redirect_to
            WHERE b.title = ?
            LIMIT 1
            """,
            (title, title),
        ):
            if desc is None:
                return None
            return MediaWikiCache(intro=desc, wikidata_item_id=wikidata_item)
        return None

    def add_redirect(self, source_title: str, dest_title: str) -> None:
        self.db_conn.execute(
            "INSERT OR IGNORE INTO pages (title, redirect_to) VALUES(?, ?)",
            (source_title, dest_title),
        )

    def add_no_desc_titles(self, titles: set[str]) -> None:
        # not found this title from MediaWiki
        self.db_conn.executemany(
            "INSERT OR IGNORE INTO pages (title) VALUES(?)", ((t,) for t in titles)
        )

    def redirect_to_page(self, title: str) -> str:
        for (redirect_to,) in self.db_conn.execute(
            "SELECT redirect_to FROM pages WHERE title = ?", (title,)
        ):
            return redirect_to
        return ""

    def query_extracts_api(self, titles: set[str]) -> None:
        # https://www.mediawiki.org/wiki/Extension:TextExtracts#API
        result = self.session.get(
            self.api_url,
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
            if summary == "":  # some wikis return empty string
                self.query_parse_api(title)
            self.add_cache(title, summary, wikibase_item)
            if title in titles:
                titles.remove(title)
            for source_title in converts.get(title, []):
                self.add_redirect(source_title, title)
                if source_title in titles:
                    titles.remove(source_title)
                for another_source_title in converts.get(source_title, []):
                    self.add_redirect(another_source_title, title)
                    if another_source_title in titles:  # normalize then redirect
                        titles.remove(another_source_title)

        self.get_section_text(redirect_to_sections, converts, titles)
        self.add_no_desc_titles(titles)

    def get_section_text(
        self,
        redirect_to_sections: dict[str, dict[str, str]],
        converts: dict[str, list[str]],
        titles: set[str],
    ) -> None:
        from lxml import etree

        for page, section_to_titles in redirect_to_sections.items():
            r = self.session.get(
                self.api_url,
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
                        self.api_url,
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
                    redirected_from = section_to_titles[section["line"]]
                    self.add_cache(redirected_from, text, None)
                    if redirected_from in titles:
                        titles.remove(redirected_from)
                    for source_title in converts.get(redirected_from, []):
                        self.add_redirect(source_title, page)
                        if source_title in titles:
                            titles.remove(source_title)

    def query_parse_api(
        self, page: str, from_disambiguation_title: str | None = None
    ) -> None:
        from lxml import etree
        from rapidfuzz.fuzz import token_set_ratio
        from rapidfuzz.process import extractOne
        from rapidfuzz.utils import default_process

        # some wikis don't have TextExtract extension
        # https://www.mediawiki.org/wiki/API:Parse
        result = self.session.get(
            self.api_url,
            params={
                "action": "parse",
                "prop": "text|properties|links",
                "section": 0,
                "redirects": 1,
                "disablelimitreport": 1,
                "page": page,
            },
        )
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
                    scorer=partial(token_set_ratio, processor=default_process),
                )
                if r is not None:
                    chosen_title = r[0]
                    self.query_parse_api(chosen_title, page)
                else:
                    self.add_no_desc_titles({page})
                return

            text = data["text"]
            html = etree.HTML(text)
            # Remove infobox, quote, references, error
            for e in html.xpath(
                "//table | //aside | //dl | //*[contains(@class, 'reference')] | "
                "//span[contains(@class, 'error')]"
            ):
                e.getparent().remove(e)
            intro = html.xpath("string()").strip()
            self.add_cache(page, intro, None)
            for redirect_data in data.get("redirects", []):
                self.add_redirect(redirect_data["from"], redirect_data["to"])
            if from_disambiguation_title is not None:
                self.add_redirect(from_disambiguation_title, page)
        else:
            self.add_no_desc_titles({page})

    def query(self, entities: dict[str, XRayEntity], search_people: bool) -> None:
        pending_entities: set[str] = set()
        for entity, entity_data in entities.items():
            if self.has_extracts_api and len(pending_entities) == MEDIAWIKI_API_EXLIMIT:
                self.query_extracts_api(pending_entities)
                pending_entities.clear()
            elif not self.has_cache(entity) and (
                search_people or entity_data.label not in PERSON_LABELS
            ):
                if self.has_extracts_api:
                    pending_entities.add(entity)
                else:
                    self.query_parse_api(entity)
        if len(pending_entities) > 0:
            self.query_extracts_api(pending_entities)


class Wikimedia_Commons:
    def __init__(self, plugin_path: Path, useragent: str) -> None:
        import requests

        self.session = requests.Session()
        self.session.headers.update({"user-agent": useragent})
        self.cache_folder = plugin_path.parent.joinpath("worddumb-wikimedia")

    def get_image(self, filename: str) -> Path | None:
        file_path = self.cache_folder.joinpath(filename)
        if not file_path.exists() and not self.download_image(filename, file_path):
            return None
        return file_path

    def download_image(self, filename: str, file_path: Path) -> bool:
        r = self.session.get(
            f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
        )
        if not r.ok:
            return False
        with file_path.open("wb") as f:
            f.write(r.content)
        return True

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
        if not cache_db_path.parent.is_dir():
            cache_db_path.parent.mkdir()
        self.init_db(cache_db_path)

    def init_db(self, db_path: Path) -> None:
        create_db = not db_path.exists()
        self.db_conn = sqlite3.connect(db_path)
        if create_db:
            self.db_conn.execute(
                """
                CREATE TABLE wikidata
                (item TEXT PRIMARY KEY, map_filename TEXT, inception TEXT)
                """
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
    if inception_str.startswith("-"):
        bc = int(inception_str[1:5]) + 1  # 2BC: -0001, 1BC: +0000, 1AD: 0001
        years = datetime.now().year + bc
        return f"Inception: {bc} BC({years} years ago)"
    else:
        inception = datetime.fromisoformat(inception_str)
        years = (datetime.now(timezone.utc) - inception).days // 365
        return (
            f"Inception: {inception.strftime('%d %B %Y').lstrip('0')}"
            f"({years} years ago)"
        )


def query_wikidata(
    entities: dict[str, XRayEntity], mediawiki: MediaWiki, wikidata: Wikidata
) -> None:
    pending_item_ids: list[str] = []
    for entity_name, entity_data in entities.items():
        if not is_gpe_label(mediawiki.lang, entity_data.label):
            continue
        mediawiki_cache = mediawiki.get_cache(entity_name)
        if mediawiki_cache is None or mediawiki_cache.wikidata_item_id is None:
            continue
        item_id = mediawiki_cache.wikidata_item_id
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
