#!/usr/bin/env python3

import json
import math
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
    def __init__(self, conn, r):
        self.conn = conn
        self.r = r
        self.entity_id = 1
        self.num_people = 0
        self.num_terms = 0
        self.erl = 0

    def search_wikipedia(self, title, text):
        url = 'https://en.wikipedia.org/w/api.php?format=json&action=query' \
            '&prop=extracts&exintro&explaintext&redirects&exsentences=7' \
            '&titles=' + urllib.parse.quote(title)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as f:
                data = json.loads(f.read())
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
        if data_type == 'PERSON':
            if ' ' in data:  # full name
                for name in data.split(' '):
                    self.r.setnx(f'name:{name}', self.entity_id)
            self.r.set(f'name:{data}', self.entity_id)
            (source, description) = self.description_from_book(text)
            self.num_people += 1
        else:
            self.r.set(f'term:{data}', self.entity_id)
            (source, description) = self.search_wikipedia(data, text)
            self.num_terms += 1

        entity_type = 1 if data_type == 'PERSON' else 2
        insert_x_entity(self.conn, (self.entity_id, data, entity_type))
        insert_x_entity_description(
            self.conn, (description, data, source, self.entity_id))
        self.insert_occurrence(self.entity_id, entity_type, start, len(data))
        self.entity_id += 1

    def insert_occurrence(self, entity_id, entity_type, start, length):
        rank_name = 'person_rank' if entity_type == 1 else 'terms_rank'
        self.r.zincrby(rank_name, 1, entity_id)
        insert_x_occurrence(self.conn, (entity_id, start, length))
        self.erl = start + length - 1

    def search(self, name, tag, start, text):
        if name == '':
            return None
        elif (entity_id := self.r.get(f'name:{name}')):
            self.insert_occurrence(int(entity_id), 1, start, len(name))
        elif (entity_id := self.r.get(f'term:{name}')):
            self.insert_occurrence(int(entity_id), 2, start, len(name))
        else:
            self.insert_entity(name, tag, start, text)

    def finish(self):
        def top_mentioned(data_type):
            rank_name = 'person_rank' if data_type == 1 else 'terms_rank'
            return ','.join(map(lambda x: x.decode('utf-8'),
                                self.r.zrange(rank_name, 0, 9, desc=True)))

        for rank_name in ['person_rank', 'terms_rank']:
            for (entity_id, count) in self.r.zrangebyscore(
                    rank_name, 2, math.inf, withscores=True):
                update_x_entity_count(self.conn, int(count), int(entity_id))

        insert_x_book_metadata(
            self.conn, (self.erl, self.num_people, self.num_terms))
        insert_x_type(self.conn, (1, 14, 15, 1, top_mentioned(1)))
        insert_x_type(self.conn, (2, 16, 17, 2, top_mentioned(2)))

        self.conn.commit()
        self.conn.close()
