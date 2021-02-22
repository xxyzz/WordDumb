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
        self.names = {}
        self.terms = {}
        self.entities = []
        self.occurrences = []
        self.erl = 0

    def search_wikipedia(self, title, entity, text):
        url = 'https://en.wikipedia.org/w/api.php?format=json&action=query' \
            '&prop=extracts&exintro&explaintext&redirects&exsentences=7' \
            '&titles=' + \
            urllib.parse.quote(title)
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

    def add_entity(self, data, data_type, start, text):
        index = self.entity_id - 1
        if data_type == 'PERSON':
            if ' ' in data:  # full name
                for name in data.split(' '):
                    self.names[name] = index
            self.names[data] = index
            self.num_people += 1
        else:
            self.terms[data] = index
            self.num_terms += 1
        entity = {}
        entity['type'] = 1 if data_type == 'PERSON' else 2
        entity['has_info_card'] = 1
        entity['count'] = 1
        entity['source'] = 0
        entity['title'] = data
        entity['id'] = self.entity_id
        self.entity_id += 1
        if data_type != 'PERSON':
            self.search_wikipedia(data, entity, text)
        else:
            self.add_description(entity, text)

        self.entities.append(entity)
        self.add_occurrence(entity, start, len(data))
        insert_x_entity_description(
            self.conn, (entity['description'], entity['title'],
                        entity['source'], entity['id']))

    def add_occurrence(self, entity, start, length):
        entity['count'] += 1
        self.occurrences.append((entity['id'], start, length))
        self.erl = start + length - 1

    def search(self, name, tag, start, text):
        if name == '':
            return None
        elif name in self.names:
            self.add_occurrence(
                self.entities[self.names[name]], start, len(name))
        elif name in self.terms:
            self.add_occurrence(
                self.entities[self.terms[name]], start, len(name))
        else:
            self.add_entity(name, tag, start, text)

    def finish(self):
        def top_mentioned(data_type):
            entities = filter(lambda x: x['type'] == data_type, self.entities)
            arr = [e['id'] for e in sorted(entities,
                                           key=lambda x: x['count'],
                                           reverse=True)][:10]
            return ','.join(map(str, arr))

        for entity in self.entities:
            insert_x_entity(self.conn, (entity['id'], entity['title'],
                                        entity['type'], entity['count']))

        for data in sorted(self.occurrences, key=lambda item: item[0]):
            insert_x_occurrence(self.conn, data)

        insert_x_book_metadata(
            self.conn, (self.erl, self.num_people, self.num_terms))
        insert_x_type(self.conn, (1, 14, 15, 1, top_mentioned(1)))
        insert_x_type(self.conn, (2, 16, 17, 2, top_mentioned(2)))

        self.conn.commit()
        self.conn.close()
