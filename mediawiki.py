#!/usr/bin/env python3

import json
from collections import defaultdict
from pathlib import Path

try:
    from .unzip import load_json_or_pickle
except ImportError:
    from unzip import load_json_or_pickle

MEDIAWIKI_API_EXLIMIT = 20
FUZZ_THRESHOLD = 85.7


def load_cache(cache_path):
    if cache_path.exists():
        with cache_path.open() as f:
            return json.load(f)
    else:
        return defaultdict(dict)


def save_cache(cache, cache_path):
    if not cache_path.parent.exists():
        cache_path.parent.mkdir()
    with cache_path.open("w") as f:
        json.dump(cache, f)


class MediaWiki:
    def __init__(self, lang, plugin_version, plugin_path, zh_wiki, fandom_url):
        import requests

        if fandom_url:
            self.source_name = 'Fandom'
            self.source_link = f'{fandom_url}/wiki/'
            self.wiki_api = f'{fandom_url}/api.php'
            self.cache_path = Path(plugin_path).parent.joinpath(
                f'worddumb-fandom/{fandom_url[8:]}.json')
        else:
            self.source_name = 'Wikipedia'
            self.source_link = f'https://{lang}.wikipedia.org/wiki/'
            self.wiki_api = f'https://{lang}.wikipedia.org/w/api.php'
            self.cache_path = Path(plugin_path).parent.joinpath(
                f"worddumb-wikimedia/{lang}.json")
        self.cache = load_cache(self.cache_path)

        self.session = requests.Session()
        self.session.params = {
            'format': 'json',
            'action': 'query',
            "prop": "extracts|pageprops",
            'exintro': 1,
            'explaintext': 1,
            'redirects': 1,
            'exsentences': 7,
            'formatversion': 2,
            "ppprop": "wikibase_item"
        }
        self.session.headers.update({
            'user-agent': f'WordDumb/{plugin_version} '
            '(https://github.com/xxyzz/WordDumb)'
        })
        if lang == 'zh' and not fandom_url:
            self.session.params['variant'] = f'zh-{zh_wiki}'
            self.source_link = f'https://zh.wikipedia.org/zh-{zh_wiki}/'

    def save_cache(self):
        save_cache(self.cache, self.cache_path)
        self.session.close()

    def has_cache(self, entity):
        return entity in self.cache

    def get_cache(self, title):
        data = self.cache.get(title)
        if isinstance(data, str):
            return self.cache.get(data)
        return data

    def query(self, titles):
        result = self.session.get(
            self.wiki_api,
            params={'titles': '|'.join(titles)})
        data = result.json()
        converts = defaultdict(list)
        for convert_type in ['normalized', 'redirects']:
            for d in data['query'].get(convert_type, []):
                # different titles can be redirected to the same page
                converts[d['to']].append(d['from'])

        for v in data['query']['pages']:
            if 'extract' not in v:  # missing or invalid
                continue
            # they are ordered by pageid, ehh
            title = v['title']
            summary = v['extract']
            if not any(period in summary for period in ['.', '。']):
                continue  # very likely a disambiguation page
            self.cache[title] = {
                "intro": summary,
                "item_id": v.get("pageprops", {}).get("wikibase_item")
            }
            if title in titles:
                titles.remove(title)
            for key in converts.get(title, []):
                self.cache[key] = title
                if key in titles:
                    titles.remove(key)
                for k in converts.get(key, []):
                    self.cache[k] = title
                    if k in titles:  # normalize then redirect
                        titles.remove(k)

        for title in titles:  # use quote next time
            self.cache[title] = None


class Wikimedia_Commons:
    def __init__(self, lang, plugin_path, plugin_version, zh_variant):
        import requests

        if lang == 'zh':
            maps_json = f'data/maps_zh-{zh_variant}.json'
        else:
            maps_json = f'data/maps_{lang}.json'
        self.maps_local = load_json_or_pickle(plugin_path, maps_json)
        self.cache_folder = Path(plugin_path).parent.joinpath(
            'worddumb-wikipedia')
        self.source_url = 'https://commons.wikimedia.org/wiki/File:'
        self.download_url = 'https://upload.wikimedia.org/wikipedia/commons/'
        if self.maps_local is not None:
            self.session = requests.Session()
            self.session.headers.update({
                'user-agent': f'WordDumb/{plugin_version} '
                '(https://github.com/xxyzz/WordDumb)'
            })
            if lang == 'en':
                self.maps_en = self.maps_local
            else:
                self.maps_en = load_json_or_pickle(
                    plugin_path, 'data/maps_en.json')

    def get_image(self, location):
        if self.maps_local is None:
            return None
        if (url := self.maps_local.get(location)):
            if not url.endswith('.svg'):
                url = self.maps_en[url]
            filename = url.split('/')[-1]
            file_path = self.cache_folder.joinpath(filename)
            if not file_path.exists():
                self.download_image(self.download_url + url, file_path)
            return filename, file_path
        return None

    def download_image(self, url, file_path):
        r = self.session.get(url)
        with file_path.open('w') as f:
            f.write(r.text)

    def close_session(self):
        if self.maps_local is not None:
            self.session.close()


class Wikidata:
    def __init__(self, plugin_path, plugin_version):
        import requests

        self.cache_path = Path(plugin_path).parent.joinpath(
            "worddumb-wikimedia/wikidata.json")
        self.cache = load_cache(self.cache_path)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "user-agent": f"WordDumb/{plugin_version} "
                "(https://github.com/xxyzz/WordDumb)"
            }
        )

    def has_cache(self, item_id):
        return item_id in self.cache

    def get_cache(self, item_id):
        return self.cache.get(item_id)

    def query(self, items):
        items = " ".join(map(lambda x: f"wd:{x}", items))
        query = f"""
        SELECT ?item ?democracy_index (SAMPLE(?locator_map_image) AS ?map_url) WHERE {{
          VALUES ?item {{ {items} }}
          OPTIONAL {{ ?item wdt:P242 ?locator_map_image. }}
          OPTIONAL {{
            ?item wdt:P8328 ?statment.
            ?statment ps:P8328 ?democracy_index;
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
            democracy_index = None
            map_url = None
            if (data := binding.get("democracy_index")):
                democracy_index = data.get("value")
            if (data := binding.get("map_url")):
                map_url = data.get("value")
            if democracy_index or map_url:
                self.cache[item_id] = {
                    "democracy_index": democracy_index,
                    "map_url": map_url
                }
            else:
                self.cache[item_id] = None

    def save_cache(self):
        save_cache(self.cache, self.cache_path)
        self.session.close()


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
