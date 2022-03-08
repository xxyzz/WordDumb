#!/usr/bin/env python3

import re
from collections import Counter

try:
    from .database import (create_x_indices, insert_x_book_metadata,
                           insert_x_entity, insert_x_entity_description,
                           insert_x_excerpt_image, insert_x_occurrence,
                           insert_x_type, save_db)
    from .mediawiki import MAX_EXLIMIT, SCORE_THRESHOLD
except ImportError:
    from database import (create_x_indices, insert_x_book_metadata,
                          insert_x_entity, insert_x_entity_description,
                          insert_x_excerpt_image, insert_x_occurrence,
                          insert_x_type, save_db)
    from mediawiki import MAX_EXLIMIT, SCORE_THRESHOLD


class X_Ray:
    def __init__(self, conn, kfx_json, mobi_html, mobi_codec,
                 search_people, mediawiki):
        self.conn = conn
        self.entity_id = 1
        self.num_people = 0
        self.num_terms = 0
        self.erl = 0
        self.people = {}
        self.people_counter = Counter()
        self.terms = {}
        self.terms_counter = Counter()
        self.pending_dic = {}
        self.num_images = 0
        self.kfx_json = kfx_json
        self.mobi_html = mobi_html
        self.mobi_codec = mobi_codec
        self.search_people = search_people
        self.mediawiki = mediawiki

    def insert_wiki_summary(self, key, summary):
        insert_x_entity_description(
                self.conn, (summary, key, 1, self.pending_dic[key]['id']))

    def insert_rest_pending_entities(self):
        for label, entity in self.pending_dic.items():
            insert_x_entity_description(
                self.conn, (entity['text'], label, None, entity['id']))

        self.pending_dic.clear()

    def insert_entity(self, data, is_person, start, text, length):
        self.insert_occurrence(self.entity_id, is_person, start, length)
        if is_person:
            self.people[data] = self.entity_id
            self.num_people += 1
            if self.search_people:
                self.insert_description(data, text)
            else:
                insert_x_entity_description(
                    self.conn, (text, data, None, self.entity_id))
        else:
            self.terms[data] = self.entity_id
            self.num_terms += 1
            self.insert_description(data, text)

        self.entity_id += 1

    def insert_description(self, key, desc):
        if key in self.mediawiki.cache_dic:
            source = None
            if (cached_desc := self.mediawiki.cache_dic[key]):
                desc = cached_desc
                source = 1
            insert_x_entity_description(
                self.conn, (desc, key, source, self.entity_id))
        else:
            self.pending_dic[key] = {'text': desc, 'id': self.entity_id}
            if len(self.pending_dic) == MAX_EXLIMIT:
                self.mediawiki.query(
                    self.pending_dic, self.insert_wiki_summary)
                self.insert_rest_pending_entities()

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

        if len(self.pending_dic) > 0:
            self.mediawiki.query(self.pending_dic, self.insert_wiki_summary)
            self.insert_rest_pending_entities()

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

        create_x_indices(self.conn)
        save_db(self.conn, db_path)
        self.mediawiki.save_cache()

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
