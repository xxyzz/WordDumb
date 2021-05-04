#!/usr/bin/env python3

import gzip
import json
import urllib.parse
import urllib.request
from collections import Counter
from urllib.error import HTTPError

from calibre_plugins.worddumb import VERSION
from calibre_plugins.worddumb.database import (insert_x_book_metadata,
                                               insert_x_entity,
                                               insert_x_entity_description,
                                               insert_x_occurrence,
                                               insert_x_type)


class X_Ray():
    def __init__(self, conn):
        self.conn = conn
        self.entity_id = 1
        self.num_people = 0
        self.num_terms = 0
        self.erl = 0
        self.names = {}
        self.people = {}
        self.people_counter = Counter()
        self.terms = {}
        self.terms_counter = Counter()
        self.pending_terms = {}

    def search_wikipedia(self):
        def insert_wiki_intro(title, intro):
            entity = self.pending_terms[title]
            self.terms[title] = entity
            del self.pending_terms[title]
            insert_x_entity_description(
                self.conn, (intro, title, 1, entity['id']))

        titles = '|'.join(self.pending_terms.keys())
        url = 'https://en.wikipedia.org/w/api.php?format=json&action=query' \
            '&prop=extracts&exintro&explaintext&redirects&exsentences=7' \
            '&formatversion=2&titles=' + urllib.parse.quote(titles)
        version = '.'.join(map(str, VERSION))
        req = urllib.request.Request(url, headers={
            'Accept-Encoding': 'gzip',
            'User-Agent': f'WordDumb/{version} '
            '(https://github.com/xxyzz/WordDumb)'
        })
        try:
            with urllib.request.urlopen(req) as f:
                gz = gzip.GzipFile(fileobj=f)
                data = json.loads(gz.read())
                for v in data['query']['pages']:
                    if 'missing' in v:
                        continue
                    # they are ordered by pageid, ehh
                    if v['title'] in self.pending_terms:
                        insert_wiki_intro(v['title'], v['extract'])
                    elif ' ' in v['title']:
                        for term in v['title'].split(' '):
                            if term in self.pending_terms:
                                insert_wiki_intro(term, v['extract'])
                                break
        except HTTPError:
            pass

        self.insert_rest_pending_terms()

    def insert_rest_pending_terms(self):
        for label, term in self.pending_terms.items():
            insert_x_entity_description(
                self.conn, (term['text'], label, None, term['id']))

        self.terms.update(self.pending_terms)
        self.pending_terms.clear()

    def insert_entity(self, data, data_type, start, text):
        self.insert_occurrence(self.entity_id, data_type, start, len(data))
        if data_type == 'PERSON':
            if ' ' in data:  # full name
                for name in data.split(' '):
                    if name not in self.names:
                        self.names[name] = self.entity_id
            self.names[data] = self.entity_id
            self.people[data] = self.entity_id
            insert_x_entity_description(
                self.conn, (text, data, None, self.entity_id))
            self.num_people += 1
        else:
            entity = {'text': text, 'id': self.entity_id}
            self.pending_terms[data] = entity
            if len(self.pending_terms) == 20:  # max exlimit
                self.search_wikipedia()
            self.num_terms += 1

        self.entity_id += 1

    def insert_occurrence(self, entity_id, entity_type, start, length):
        if entity_type == 'PERSON':
            self.people_counter[entity_id] += 1
        else:
            self.terms_counter[entity_id] += 1
        insert_x_occurrence(self.conn, (entity_id, start, length))
        self.erl = start + length - 1

    def search(self, name, tag, start, text):
        if name == '':
            return None
        elif name in self.names:
            self.insert_occurrence(
                self.names[name], 'PERSON', start, len(name))
        elif name in self.terms:
            self.insert_occurrence(
                self.terms[name]['id'], 'TERMS', start, len(name))
        elif name in self.pending_terms:
            self.insert_occurrence(
                self.pending_terms[name]['id'], 'TERMS', start, len(name))
        else:
            entity_text = text[:text.find('.') + 1] if '.' in text else text
            self.insert_entity(name, tag, start, entity_text)

    def finish(self):
        def top_mentioned(counter):
            return ','.join(map(str, [e[0] for e in counter.most_common(10)]))

        self.insert_rest_pending_terms()

        for name, entity_id in self.people.items():
            insert_x_entity(
                self.conn,
                (entity_id, name, 1, self.people_counter[entity_id]))
        for label, value in self.terms.items():
            insert_x_entity(
                self.conn,
                (value['id'], label, 2, self.terms_counter[value['id']]))

        insert_x_book_metadata(
            self.conn, (self.erl, self.num_people, self.num_terms))
        insert_x_type(
            self.conn, (1, 14, 15, 1, top_mentioned(self.people_counter)))
        insert_x_type(
            self.conn, (2, 16, 17, 2, top_mentioned(self.terms_counter)))

        self.conn.commit()
        self.conn.close()
