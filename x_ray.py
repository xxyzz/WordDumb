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
                                               insert_x_type,
                                               update_x_entity_count)


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

    def search_wikipedia(self, title, text):
        url = 'https://en.wikipedia.org/w/api.php?format=json&action=query' \
            '&prop=extracts&exintro&explaintext&redirects&exsentences=7' \
            '&titles=' + urllib.parse.quote(title)
        req = urllib.request.Request(url, headers={
            'Accept-Encoding': 'gzip',
            'User-Agent': 'WordDumb (https://github.com/xxyzz/WordDumb)'
        })
        try:
            with urllib.request.urlopen(req) as f:
                gz = gzip.GzipFile(fileobj=f)
                data = json.loads(gz.read())
                data = data['query']
                for v in data['pages'].values():
                    if 'missing' in v:
                        return self.description_from_book(text)
                    else:
                        return (1, v['extract'])
        except HTTPError:
            return self.description_from_book(text)

    def description_from_book(self, text):
        return (None, text[:text.find('.') + 1] if '.' in text else text)

    def insert_entity(self, data, data_type, start, text):
        entity = {}
        entity['count'] = 0
        entity['id'] = self.entity_id
        self.insert_occurrence(entity, start, len(data))
        if data_type == 'PERSON':
            if ' ' in data:  # full name
                for name in data.split(' '):
                    if name not in self.names:
                        self.names[name] = data
            self.names[data] = data
            self.people[data] = entity
            (source, description) = self.description_from_book(text)
            self.num_people += 1
        else:
            self.terms[data] = entity
            (source, description) = self.search_wikipedia(data, text)
            self.num_terms += 1

        entity_type = 1 if data_type == 'PERSON' else 2
        insert_x_entity(self.conn, (self.entity_id, data, entity_type))
        insert_x_entity_description(
            self.conn, (description, data, source, self.entity_id))
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
            for v in filter(lambda x: x['count'] > 1, d.values()):
                update_x_entity_count(self.conn, v['count'], v['id'])

        insert_x_book_metadata(
            self.conn, (self.erl, self.num_people, self.num_terms))
        insert_x_type(self.conn, (1, 14, 15, 1, top_mentioned(1)))
        insert_x_type(self.conn, (2, 16, 17, 2, top_mentioned(2)))

        self.conn.commit()
        self.conn.close()
