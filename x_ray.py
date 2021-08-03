#!/usr/bin/env python3

import re
from collections import Counter

from calibre_plugins.worddumb import VERSION
from calibre_plugins.worddumb.config import prefs
from calibre_plugins.worddumb.database import (insert_x_book_metadata,
                                               insert_x_entity,
                                               insert_x_entity_description,
                                               insert_x_occurrence,
                                               insert_x_type, save_db)

# https://en.wikipedia.org/wiki/Title
TITLES = {
    'Master', 'Mr', 'Mrs', 'Miss', 'Ms', 'Mx',  # Common titles
    'Sir', 'Madam', 'Madame', 'Dame', 'Esq',  # Formal titles
    'Dr', 'Professor', 'Prof', 'Doc', 'QC', 'Cl', 'SCl',  # Academic
    'Eur', 'Ing', 'Chancellor', 'Vice', 'Principal', 'President', 'Warden',
    'Dean', 'Regent', 'Rector', 'Provost', 'Director', 'Chief', 'Executive',
    'Fr', 'Father', 'Pr', 'Pastor', 'Br', 'Brother', 'Si',  # Religious titles
    'Sister', 'Elder', 'Pope', 'Rabbi', 'Bishop', 'St', 'Saint'
    'Maid', 'Aunt', 'Auntie', 'Uncle',
    'Hon', 'MP', 'Senator', 'Councillor', 'Secretary',  # Legislative
    'Prince', 'Princess', 'Archduke', 'Archduchess', 'Grand',  # Aristocratic
    'Duke', 'Duchess', 'Marquis', 'Marquess', 'Count', 'Countess', 'Emperor',
    'Empress', 'King', 'Queen', 'Lord', 'Lady', 'Tasr', 'Tsarina', 'Pharaoh'
    'Emperor', 'Empress', 'Viceroy', 'Vicereine', 'Baron', 'Baroness',
    'Admiral', 'Brigadier', 'Captain', 'Colonel', 'Commander',  # Military
    'Commodore', 'Corporal', 'General', 'Lieutenant', 'Major', 'Marshal',
    'Officer', 'Private', 'Sergeant'
}
MAX_EXLIMIT = 20


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
        self.wikipedia_api = f'https://{lang}.wikipedia.org/w/api.php'

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
        if lang == 'zh':
            self.s.headers.update(
                {'accept-language': f"zh-{prefs['zh_wiki_variant']}"})

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

    def match_wiki_result(self, title, converts, dic):
        if title in dic:
            return title
        elif converts.get(title) in dic:
            return converts.get(title)
        elif converts.get(converts.get(title)) in dic:
            # normalize then redirect
            return converts.get(converts.get(title))
        else:
            for name in self.split_name(title):
                if name in dic:
                    return name
        return None

    def search_wikipedia(self, is_people, dic):
        r = self.s.get(self.wikipedia_api,
                       params={'titles': '|'.join(dic.keys())})
        data = r.json()
        converts = {}
        for t in ['normalized', 'redirects']:
            for d in data['query'].get(t, []):
                converts[d['to']] = d['from']
        for v in data['query']['pages']:
            if 'extract' not in v:  # missing or invalid
                continue
            # they are ordered by pageid, ehh
            key = self.match_wiki_result(v['title'], converts, dic)
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

    def insert_entity(self, data, is_person, start, text, length):
        self.insert_occurrence(self.entity_id, is_person, start, length)
        if is_person:
            for name in self.split_name(data):
                self.names[name] = self.entity_id
            self.names[data] = self.entity_id
            self.num_people += 1
            if prefs['search_people']:
                self.pending_people[data] = {'text': text,
                                             'id': self.entity_id}
                if len(self.pending_people) == MAX_EXLIMIT:
                    self.search_wikipedia(True, self.pending_people)
            else:
                self.people[data] = self.entity_id
                insert_x_entity_description(
                    self.conn, (text, data, None, self.entity_id))
        else:
            self.pending_terms[data] = {'text': text, 'id': self.entity_id}
            if len(self.pending_terms) == MAX_EXLIMIT:
                self.search_wikipedia(False, self.pending_terms)
            self.num_terms += 1

        self.entity_id += 1

    def insert_occurrence(self, entity_id, is_person, start, length):
        if is_person:
            self.people_counter[entity_id] += 1
        else:
            self.terms_counter[entity_id] += 1
        insert_x_occurrence(self.conn, (entity_id, start, length))

    def search(self, name, is_person, start, sent, length):
        if self.lang == 'en':
            if re.match(r'chapter', name, re.IGNORECASE):
                return
            name = re.sub(r'(?:\'s|’s)$', '', name)
            name = re.sub(r'^(?:the |an |a )', '', name, flags=re.IGNORECASE)

        if name in self.terms:
            self.insert_occurrence(
                self.terms[name]['id'], False, start, length)
        elif name in self.pending_terms:
            self.insert_occurrence(
                self.pending_terms[name]['id'], False, start, length)
        elif name in self.names:
            self.insert_occurrence(
                self.names[name], True, start, length)
        else:
            for part in self.split_name(name):
                if part in self.names:
                    self.insert_occurrence(
                        self.names[part], True, start, length)
                    return
            self.insert_entity(name, is_person, start, sent, length)

    def finish(self, db_path):
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
        save_db(self.conn, db_path)

    def split_name(self, name):
        if self.lang == 'en':
            return filter(lambda x: len(x) > 1 and x not in TITLES,
                          re.split(r'\W', name))
        else:
            return re.split(r'\W', name)
