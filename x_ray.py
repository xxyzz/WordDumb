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

    def search_wikipedia(self, title, dictionary, text):
        url = 'https://en.wikipedia.org/w/api.php?format=json&action=query' \
            '&prop=extracts&exintro&explaintext&redirects&titles=' + \
            urllib.parse.quote(title)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as f:
                data = json.loads(f.read())
                data = data['query']
                for v in data['pages'].values():
                    if 'missing' not in v:
                        dictionary['description'] = v['extract']
                        dictionary['source'] = 1
                    else:
                        self.add_description(dictionary, text)
        except HTTPError:
            self.add_description(dictionary, text)

    def add_description(self, dictionary, text):
        dictionary['description'] = text[:text.find(
            '.') + 1] if '.' in text else text
        dictionary['source'] = 0

    def add_data(self, data, data_type, text):
        if data_type == 'PERSON':
            dictionary = self.people
            if ' ' in data:  # full name
                for name in data.split(' '):
                    self.names[name] = data
                if data not in self.names:
                    self.names[data] = data
            elif data not in self.names:
                self.names[data] = data
            self.num_people += 1
        else:
            dictionary = self.terms
            self.num_terms += 1
        dictionary[data] = {}
        dictionary = dictionary[data]
        dictionary['type'] = 1 if data_type == 'PERSON' else 2
        dictionary['has_info_card'] = 1
        dictionary['count'] = 1
        dictionary['source'] = 0
        dictionary['title'] = data
        dictionary['id'] = self.entity_id
        self.entity_id += 1
        if data_type != 'PERSON':
            self.search_wikipedia(data, dictionary, text)
        else:
            self.add_description(dictionary, text)
        insert_x_entity_description(
            self.conn, (dictionary['description'], dictionary['title'],
                        dictionary['source'], dictionary['id']))

    def search(self, name, tag, start, text):
        def insert_occurrence(dictionary):
            insert_x_occurrence(
                self.conn, (dictionary['id'], start, len(name)))
            dictionary['count'] += 1
            self.erl = start + len(name) - 1

        if name == '':
            return None
        elif tag == 'PERSON' and name in self.names:
            insert_occurrence(self.people[self.names[name]])
        elif tag != 'PERSON' and name in self.terms:
            insert_occurrence(self.terms[name])
        else:
            self.add_data(name, tag, text)

    def finish(self):
        def top_mentioned(values):
            return ','.join(map(str, [v['id'] for v in sorted(
                values, key=lambda item: item['count'], reverse=True)][:10]))

        for d in [self.people, self.terms]:
            for value in d.values():
                insert_x_entity(self.conn, (value['id'], value['title'],
                                            value['type'], value['count']))

        insert_x_book_metadata(
            self.conn, (self.erl, self.num_people, self.num_terms))
        insert_x_type(self.conn,
                      (1, 14, 15, 1, top_mentioned(self.people.values())))
        insert_x_type(self.conn,
                      (2, 16, 17, 2, top_mentioned(self.terms.values())))

        self.conn.commit()
        self.conn.close()
