#!/usr/bin/env python3

import json
from collections import defaultdict
from pathlib import Path

try:
    from .unzip import load_json_or_pickle
except ImportError:
    from unzip import load_json_or_pickle

MAX_EXLIMIT = 20
SCORE_THRESHOLD = 85.7


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
                f'worddumb-wikipedia/{lang}.json')
        self.cache_dic = self.load_cache()

        self.session = requests.Session()
        self.session.params = {
            'format': 'json',
            'action': 'query',
            'prop': 'extracts',
            'exintro': 1,
            'explaintext': 1,
            'redirects': 1,
            'exsentences': 7,
            'formatversion': 2
        }
        self.session.headers.update({
            'user-agent': f'WordDumb/{plugin_version} '
            '(https://github.com/xxyzz/WordDumb)'
        })
        if lang == 'zh' and not fandom_url:
            self.session.params['variant'] = f'zh-{zh_wiki}'
            self.source_link = f'https://zh.wikipedia.org/zh-{zh_wiki}/'

    def load_cache(self):
        if self.cache_path.exists():
            with self.cache_path.open() as f:
                return json.load(f)
        else:
            return {}

    def save_cache(self):
        self.cache_path.parent.mkdir(exist_ok=True)
        with self.cache_path.open('w') as f:
            json.dump(self.cache_dic, f)
        self.session.close()

    def query(self, title_dic, callback):
        result = self.session.get(
            self.wiki_api,
            params={'titles': '|'.join(title_dic.keys())})
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
            self.cache_dic[title] = summary
            if title in title_dic:
                callback(title, summary)
                del title_dic[title]
            for key in converts.get(title, []):
                if key in title_dic:
                    callback(key, summary)
                    del title_dic[key]
                    self.cache_dic[key] = summary
                for k in converts.get(key, []):
                    if k in title_dic:  # normalize then redirect
                        callback(k, summary)
                        del title_dic[k]
                        self.cache_dic[k] = summary

        for title in title_dic:  # use quote next time
            self.cache_dic[title] = None


class Wikimedia_Commons:
    def __init__(self, lang, plugin_path, plugin_version, zh_variant):
        import requests

        if lang == 'zh':
            maps_json = f'data/zh-{zh_variant}.json'
        else:
            maps_json = f'data/maps_{lang}.json'
        self.map_url = load_json_or_pickle(plugin_path, maps_json)
        self.cache_folder = Path(plugin_path).parent.joinpath(
            'worddumb-wikipedia')
        self.source_url = 'https://commons.wikimedia.org/wiki/File:'
        if self.map_url is not None:
            self.session = requests.Session()
            self.session.headers.update({
                'user-agent': f'WordDumb/{plugin_version} '
                '(https://github.com/xxyzz/WordDumb)'
            })

    def get_image(self, location):
        if self.map_url is None:
            return None

        if location in self.map_url:
            url = self.map_url[location]
            filename = url.split('/')[-1]
            file_path = self.cache_folder.joinpath(filename)
            if not file_path.exists():
                self.download_image(url, file_path)
            return filename, file_path
        return None

    def download_image(self, url, file_path):
        r = self.session.get(url)
        with file_path.open('w') as f:
            f.write(r.text)

    def close_session(self):
        if self.map_url is not None:
            self.session.close()
