#!/usr/bin/env python3

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
        self.people = {}
        self.names = {}
        self.terms = {}
        self.erl = 0

    def search_wikipedia(self, title, entity, text):
        url = 'https://en.wikipedia.org/w/api.php?format=json&action=query' \
            '&prop=extracts&exintro&explaintext&redirects&exsentences=7' \
            '&titles=' + urllib.parse.quote(title)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as f:
                data = json.loads(f.read())
                data = data['query']
                for v in data['pages'].values():
                    if 'missing' not in v:
                        entity['description'] = v['extract']
                        entity['source'] = 1
                    else:
                        self.add_description(entity, text)
        except HTTPError:
            self.add_description(entity, text)

    def add_description(self, entity, text):
        entity['description'] = text[:text.find(
            '.') + 1] if '.' in text else text
        entity['source'] = 0

    def insert_entity(self, data, data_type, start, text):
        if data_type == 'PERSON':
            if ' ' in data:  # full name
                for name in data.split(' '):
                    self.names[name] = data
            self.names[data] = data
            self.num_people += 1
        else:
            self.num_terms += 1
        entity = {}
        entity['type'] = 1 if data_type == 'PERSON' else 2
        entity['count'] = 0
        entity['label'] = data
        entity['id'] = self.entity_id
        self.entity_id += 1
        if data_type != 'PERSON':
            self.terms[data] = entity
            self.search_wikipedia(data, entity, text)
        else:
            self.people[data] = entity
            self.add_description(entity, text)

        insert_x_entity_description(
            self.conn, (entity['description'], entity['label'],
                        entity['source'], entity['id']))
        self.insert_occurrence(entity, start, len(data))

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
        else:
            self.insert_entity(name, tag, start, text)

    def finish(self):
        def top_mentioned(data_type):
            entities = self.people if data_type == 1 else self.terms
            arr = [e['id'] for e in sorted(entities.values(),
                                           key=lambda x: x['count'],
                                           reverse=True)][:10]
            return ','.join(map(str, arr))

        for d in [self.people, self.terms]:
            for v in d.values():
                insert_x_entity(
                    self.conn, (v['id'], v['label'], v['type'], v['count']))

        insert_x_book_metadata(
            self.conn, (self.erl, self.num_people, self.num_terms))
        insert_x_type(self.conn, (1, 14, 15, 1, top_mentioned(1)))
        insert_x_type(self.conn, (2, 16, 17, 2, top_mentioned(2)))

        self.conn.commit()
        self.conn.close()
