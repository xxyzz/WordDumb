#!/usr/bin/env python3

import gzip
import json
import urllib.parse
import urllib.request
from urllib.error import HTTPError

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
        self.terms = {}
        self.pending_terms = {}

    def search_wikipedia(self):
        def insert_wiki_intro(entity, intro, title):
            entity['source'] = 1
            insert_x_entity_description(
                self.conn, (intro, title, 1, entity['id']))

        titles = '|'.join(self.pending_terms.keys())
        url = 'https://en.wikipedia.org/w/api.php?format=json&action=query' \
            '&prop=extracts&exintro&explaintext&redirects&exsentences=7' \
            '&formatversion=2&titles=' + urllib.parse.quote(titles)
        req = urllib.request.Request(url, headers={
            'Accept-Encoding': 'gzip',
            'User-Agent': 'WordDumb (https://github.com/xxyzz/WordDumb)'
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
                        insert_wiki_intro(self.pending_terms[v['title']],
                                          v['extract'], v['title'])
                    elif ' ' in v['title']:
                        for term in v['title'].split(' '):
                            if term in self.pending_terms and \
                               'source' not in self.pending_terms[term]:
                                insert_wiki_intro(self.pending_terms[term],
                                                  v['extract'], v['title'])
                                break
        except HTTPError:
            pass

        self.insert_rest_pending_terms()

    def insert_rest_pending_terms(self):
        for label, term in filter(lambda x: 'source' not in x[1],
                                  self.pending_terms.items()):
            insert_x_entity_description(
                self.conn, (term['text'], label, None, term['id']))

        self.terms.update(self.pending_terms)
        self.pending_terms.clear()

    def insert_entity(self, data, data_type, start, text):
        entity = {'count': 0, 'id': self.entity_id}
        self.insert_occurrence(entity, start, len(data))
        if data_type == 'PERSON':
            if ' ' in data:  # full name
                for name in data.split(' '):
                    if name not in self.names:
                        self.names[name] = data
            self.names[data] = data
            self.people[data] = entity
            insert_x_entity_description(
                self.conn, (text, data, None, self.entity_id))
            self.num_people += 1
        else:
            entity['text'] = text
            self.pending_terms[data] = entity
            if len(self.pending_terms) == 20:  # max exlimit
                self.search_wikipedia()
            self.num_terms += 1

        self.entity_id += 1

    def insert_occurrence(self, entity, start, length):
        entity['count'] += 1
        insert_x_occurrence(self.conn, (entity['id'], start, length))
        self.erl = start + length - 1

    def search(self, name, tag, start, text):
        if name == '':
            return None
        elif name in self.names:
            self.insert_occurrence(self.people[self.names[name]],
                                   start, len(name))
        elif name in self.terms:
            self.insert_occurrence(self.terms[name], start, len(name))
        elif name in self.pending_terms:
            self.insert_occurrence(self.pending_terms[name], start, len(name))
        else:
            entity_text = text[:text.find('.') + 1] if '.' in text else text
            self.insert_entity(name, tag, start, entity_text)

    def finish(self):
        def insert_entities(dictionary, data_type):
            for label, value in dictionary.items():
                insert_x_entity(
                    self.conn, (value['id'], label, data_type, value['count']))

        def top_mentioned(data_type):
            entities = self.people if data_type == 1 else self.terms
            arr = [e['id'] for e in sorted(entities.values(),
                                           key=lambda x: x['count'],
                                           reverse=True)][:10]
            return ','.join(map(str, arr))

        self.insert_rest_pending_terms()
        insert_entities(self.people, 1)
        insert_entities(self.terms, 2)
        insert_x_book_metadata(
            self.conn, (self.erl, self.num_people, self.num_terms))
        insert_x_type(self.conn, (1, 14, 15, 1, top_mentioned(1)))
        insert_x_type(self.conn, (2, 16, 17, 2, top_mentioned(2)))

        self.conn.commit()
        self.conn.close()
