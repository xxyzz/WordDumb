#!/usr/bin/env python3

import re
from collections import Counter, defaultdict
from pathlib import Path

try:
    from calibre_plugins.worddumb.database import (create_x_indices,
                                                   insert_x_book_metadata,
                                                   insert_x_entity,
                                                   insert_x_entity_description,
                                                   insert_x_excerpt_image,
                                                   insert_x_occurrence,
                                                   insert_x_type, save_db)
    from calibre_plugins.worddumb.unzip import load_wiki_cache, save_wiki_cache
except ImportError:
    from database import (create_x_indices, insert_x_book_metadata,
                          insert_x_entity, insert_x_entity_description,
                          insert_x_excerpt_image, insert_x_occurrence,
                          insert_x_type, save_db)
    from unzip import load_wiki_cache, save_wiki_cache

MAX_EXLIMIT = 20
SCORE_THRESHOLD = 85.7


class X_Ray:
    def __init__(self, conn, lang, kfx_json, mobi_html, mobi_codec,
                 plugin_path, plugin_version, zh_wiki, search_people):
        self.conn = conn
        self.entity_id = 1
        self.num_people = 0
        self.num_terms = 0
        self.erl = 0
        self.people = {}
        self.people_counter = Counter()
        self.terms = {}
        self.terms_counter = Counter()
        self.pending_terms = {}
        self.pending_people = {}
        self.lang = lang
        self.wikipedia_api = f'https://{lang}.wikipedia.org/w/api.php'
        self.wiki_cache_path = Path(plugin_path).parent.joinpath(
            f'worddumb-wikipedia/{lang}.json')
        self.wiki_cache = load_wiki_cache(self.wiki_cache_path)
        self.num_images = 0
        self.kfx_json = kfx_json
        self.mobi_html = mobi_html
        self.mobi_codec = mobi_codec
        self.search_people = search_people

        import requests
        self.s = requests.Session()
        self.s.params = {
            'format': 'json',
            'action': 'query',
            'prop': 'extracts',
            'exintro': 1,
            'explaintext': 1,
            'redirects': 1,
            'exsentences': 7,
            'formatversion': 2
        }
        self.s.headers.update({
            'user-agent': f'WordDumb/{plugin_version} '
            '(https://github.com/xxyzz/WordDumb)'
        })
        if lang == 'zh':
            self.s.headers.update(
                {'accept-language': f"zh-{zh_wiki}"})

    def insert_wiki_summary(self, pending_dic, key, title, summary):
        # not a disambiguation page
        if any(period in summary for period in ['.', '。']):
            insert_x_entity_description(
                self.conn, (summary, key, 1, pending_dic[key]['id']))
            self.wiki_cache[key] = summary
            del pending_dic[key]
            if key != title and title not in self.wiki_cache:
                self.wiki_cache[title] = summary

    def search_wikipedia(self, pending_dic):
        r = self.s.get(self.wikipedia_api,
                       params={'titles': '|'.join(pending_dic.keys())})
        data = r.json()
        converts = defaultdict(list)
        for t in ['normalized', 'redirects']:
            for d in data['query'].get(t, []):
                # different titles can be redirected to the same page
                converts[d['to']].append(d['from'])

        for v in data['query']['pages']:
            if 'extract' not in v:  # missing or invalid
                continue
            # they are ordered by pageid, ehh
            title = v['title']
            summary = v['extract']
            if title in pending_dic:
                self.insert_wiki_summary(pending_dic, title, title, summary)
            for key in converts.get(title, []):
                if key in pending_dic:
                    self.insert_wiki_summary(pending_dic, key, title, summary)
                for k in converts.get(key, []):
                    if k in pending_dic:  # normalize then redirect
                        self.insert_wiki_summary(
                            pending_dic, k, title, summary)

        self.insert_rest_pending_entities(pending_dic)

    def insert_rest_pending_entities(self, pending_dic):
        for label, entity in pending_dic.items():
            insert_x_entity_description(
                self.conn, (entity['text'], label, None, entity['id']))
            self.wiki_cache[label] = None

        pending_dic.clear()

    def insert_entity(self, data, is_person, start, text, length):
        self.insert_occurrence(self.entity_id, is_person, start, length)
        if is_person:
            self.people[data] = self.entity_id
            self.num_people += 1
            if self.search_people:
                self.insert_description(data, text, self.pending_people)
            else:
                insert_x_entity_description(
                    self.conn, (text, data, None, self.entity_id))
        else:
            self.terms[data] = self.entity_id
            self.num_terms += 1
            self.insert_description(data, text, self.pending_terms)

        self.entity_id += 1

    def insert_description(self, key, desc, pending_dic):
        if key in self.wiki_cache:
            source = None
            if (cached_desc := self.wiki_cache[key]):
                desc = cached_desc
                source = 1
            insert_x_entity_description(
                self.conn, (desc, key, source, self.entity_id))
        else:
            pending_dic[key] = {'text': desc, 'id': self.entity_id}
            if len(pending_dic) == MAX_EXLIMIT:
                self.search_wikipedia(pending_dic)

    def insert_occurrence(self, entity_id, is_person, start, length):
        if is_person:
            self.people_counter[entity_id] += 1
        else:
            self.terms_counter[entity_id] += 1
        insert_x_occurrence(self.conn, (entity_id, start, length))
        self.erl = start + length - 1

    def search(self, name, is_person, start, sent, length):
        from rapidfuzz.process import extractOne

        if (r := extractOne(name, self.terms.keys(),
                            score_cutoff=SCORE_THRESHOLD)):
            self.insert_occurrence(self.terms[r[0]], False, start, length)
        elif (r := extractOne(name, self.people.keys(),
                              score_cutoff=SCORE_THRESHOLD)):
            self.insert_occurrence(self.people[r[0]], True, start, length)
        else:
            self.insert_entity(name, is_person, start, sent, length)

    def finish(self, db_path):
        def top_mentioned(counter):
            return ','.join(map(str, [e[0] for e in counter.most_common(10)]))

        if len(self.pending_terms) > 0:
            self.search_wikipedia(self.pending_terms)
        if len(self.pending_people) > 0:
            self.search_wikipedia(self.pending_people)

        insert_x_entity(
            self.conn,
            [(entity_id, name, 1, self.people_counter[entity_id]) for
             name, entity_id in self.people.items()])
        insert_x_entity(
            self.conn,
            [(entity_id, label, 2, self.terms_counter[entity_id]) for
             label, entity_id in self.terms.items()])

        if self.kfx_json:
            self.find_kfx_images()
        else:
            self.find_mobi_images()
        if self.num_images:
            preview_images = ','.join(map(str, range(self.num_images)))
        else:
            preview_images = None
        insert_x_book_metadata(
            self.conn,
            (self.erl, 1 if self.num_images else 0,
             self.num_people, self.num_terms, self.num_images, preview_images))
        insert_x_type(
            self.conn, (1, 14, 15, 1, top_mentioned(self.people_counter)))
        insert_x_type(
            self.conn, (2, 16, 17, 2, top_mentioned(self.terms_counter)))

        self.s.close()
        create_x_indices(self.conn)
        save_db(self.conn, db_path)
        save_wiki_cache(self.wiki_cache_path, self.wiki_cache)

    def find_kfx_images(self):
        images = set()
        for entry in filter(lambda x: x['type'] == 2, self.kfx_json):
            if entry['content'] in images:
                continue
            images.add(entry['content'])
            insert_x_excerpt_image(
                self.conn, (self.num_images, entry['position'],
                            entry['content'], entry['position']))
            self.num_images += 1

    def find_mobi_images(self):
        images = set()
        for match_tag in re.finditer(b'<img [^>]+/>', self.mobi_html):
            if (match_src := re.search(
                    r'src="([^"]+)"',
                    match_tag.group(0).decode(self.mobi_codec))):
                image = match_src.group(1)
                if image in images:
                    continue
                images.add(image)
                insert_x_excerpt_image(
                    self.conn, (self.num_images, match_tag.start(),
                                image, match_tag.start()))
                self.num_images += 1
