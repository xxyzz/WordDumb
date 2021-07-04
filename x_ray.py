#!/usr/bin/env python3

from collections import Counter

from calibre_plugins.worddumb import VERSION
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import (insert_x_book_metadata,
                                               insert_x_entity,
                                               insert_x_entity_description,
                                               insert_x_occurrence,
                                               insert_x_type)


class X_Ray():
    def __init__(self, conn, lang):
        self.conn = conn
        self.entity_id = 1
        self.num_people = 0
        self.num_terms = 0
        self.names = {}
        self.people = {}
        self.people_counter = Counter()
        self.terms = {}
        self.terms_counter = Counter()
        self.pending_terms = {}
        self.pending_people = {}
        self.lang = lang

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
            'user-agent': f"WordDumb/{'.'.join(map(str, VERSION))} "
            '(https://github.com/xxyzz/WordDumb)'
        })

    def insert_wiki_intro(self, is_people, title, intro):
        if is_people:
            entity = self.pending_people[title]
            self.people[title] = entity
            del self.pending_people[title]
        else:
            entity = self.pending_terms[title]
            self.terms[title] = entity
            del self.pending_terms[title]

        if not any(period in intro for period in ['.', '。']):
            # disambiguation page
            insert_x_entity_description(
                self.conn, (entity['text'], title, None, entity['id']))
        else:
            insert_x_entity_description(
                self.conn, (intro, title, 1, entity['id']))

    def search_wikipedia(self, is_people, dic):
        url = f'https://{self.lang}.wikipedia.org/w/api.php'
        params = {'titles': '|'.join(dic.keys())}
        if self.lang == 'zh':
            r = self.s.get(
                url, params=params,
                headers={'accept-language': f"zh-{prefs['zh_wiki_variant']}"})
        else:
            r = self.s.get(url, params=params)
        data = r.json()
        converts = {}
        for t in ['normalized', 'redirects']:
            for d in data['query'].get(t, []):
                converts[d['to']] = d['from']
        for v in data['query']['pages']:
            if 'extract' not in v:  # missing or invalid
                continue
            # they are ordered by pageid, ehh
            key = None
            if v['title'] in dic:
                key = v['title']
            elif converts.get(v['title']) in dic:
                key = converts.get(v['title'])
            elif converts.get(converts.get(v['title'])) in dic:
                # normalize then redirect
                key = converts.get(converts.get(v['title']))
            elif ' ' in v['title']:
                for token in v['title'].split(' '):
                    if token in dic:
                        key = token
                        break
            if key is not None:
                self.insert_wiki_intro(is_people, key, v['extract'])

        if is_people:
            self.insert_rest_pending_entities(self.people, self.pending_people)
        else:
            self.insert_rest_pending_entities(self.terms, self.pending_terms)

    def insert_rest_pending_entities(self, dic, pending_dic):
        for label, entity in pending_dic.items():
            insert_x_entity_description(
                self.conn, (entity['text'], label, None, entity['id']))

        dic.update(pending_dic)
        pending_dic.clear()

    def insert_entity(self, data, data_type, start, text, length):
        self.insert_occurrence(self.entity_id, data_type, start, length)
        if data_type == 'PERSON':
            if ' ' in data:  # full name
                for name in data.split(' '):
                    if name not in self.names:
                        self.names[name] = self.entity_id
            self.names[data] = self.entity_id
            self.num_people += 1
            if prefs['search_people']:
                entity = {'text': text, 'id': self.entity_id}
                self.pending_people[data] = entity
                if len(self.pending_people) == 20:  # max exlimit
                    self.search_wikipedia(True, self.pending_people)
            else:
                self.people[data] = self.entity_id
                insert_x_entity_description(
                    self.conn, (text, data, None, self.entity_id))
        else:
            entity = {'text': text, 'id': self.entity_id}
            self.pending_terms[data] = entity
            if len(self.pending_terms) == 20:  # max exlimit
                self.search_wikipedia(False, self.pending_terms)
            self.num_terms += 1

        self.entity_id += 1

    def insert_occurrence(self, entity_id, entity_type, start, length):
        if entity_type == 'PERSON':
            self.people_counter[entity_id] += 1
        else:
            self.terms_counter[entity_id] += 1
        insert_x_occurrence(self.conn, (entity_id, start, length))

    def search(self, name, tag, start, sent, length):
        if name == '':
            return None
        elif name in self.terms:
            self.insert_occurrence(
                self.terms[name]['id'], 'TERMS', start, length)
        elif name in self.pending_terms:
            self.insert_occurrence(
                self.pending_terms[name]['id'], 'TERMS', start, length)
        elif name in self.names:
            self.insert_occurrence(
                self.names[name], 'PERSON', start, length)
        elif prefs['search_people'] and name in self.pending_people:
            self.insert_occurrence(
                self.pending_people[name]['id'], 'PERSON', start, length)
        else:
            self.insert_entity(name, tag, start, sent, length)

    def finish(self):
        def top_mentioned(counter):
            return ','.join(map(str, [e[0] for e in counter.most_common(10)]))

        if len(self.pending_terms) > 0:
            self.search_wikipedia(False, self.pending_terms)
        if len(self.pending_people) > 0:
            self.search_wikipedia(True, self.pending_people)

        for name, value in self.people.items():
            if prefs['search_people']:
                insert_x_entity(
                    self.conn,
                    (value['id'], name, 1, self.people_counter[value['id']]))
            else:
                insert_x_entity(
                    self.conn, (value, name, 1, self.people_counter[value]))
        for label, value in self.terms.items():
            insert_x_entity(
                self.conn,
                (value['id'], label, 2, self.terms_counter[value['id']]))

        insert_x_book_metadata(
            self.conn, (self.num_people, self.num_terms))
        insert_x_type(
            self.conn, (1, 14, 15, 1, top_mentioned(self.people_counter)))
        insert_x_type(
            self.conn, (2, 16, 17, 2, top_mentioned(self.terms_counter)))

        self.s.close()
        self.conn.commit()
        self.conn.close()
