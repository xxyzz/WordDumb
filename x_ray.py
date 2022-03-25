#!/usr/bin/env python3

import re
from collections import Counter

try:
    from .database import (create_x_indices, insert_x_book_metadata,
                           insert_x_entity, insert_x_entity_description,
                           insert_x_excerpt_image, insert_x_occurrence,
                           insert_x_type, save_db)
    from .mediawiki import FUZZ_THRESHOLD, MEDIAWIKI_API_EXLIMIT, regime_type
except ImportError:
    from database import (create_x_indices, insert_x_book_metadata,
                          insert_x_entity, insert_x_entity_description,
                          insert_x_excerpt_image, insert_x_occurrence,
                          insert_x_type, save_db)
    from mediawiki import FUZZ_THRESHOLD, MEDIAWIKI_API_EXLIMIT, regime_type

# https://github.com/explosion/spaCy/blob/master/spacy/glossary.py#L318
NER_LABELS = [
    "EVENT",  # OntoNotes 5: English, Chinese
    "FAC",
    "GPE",
    "LAW",
    "LOC",
    "ORG",
    "PERSON",
    "PRODUCT",
    "WORK_OF_ART",
    "MISC",  # Catalan
    "PER",
    "EVT",  # Norwegian Bokmål: https://github.com/ltgoslo/norne#entity-types
    "GPE_LOC",
    "GPE_ORG",
    "PROD",
    "geogName",  # Polish: https://arxiv.org/pdf/1811.10418.pdf#subsection.2.1
    "orgName",
    "persName",
    "placeName",
    "ORGANIZATION",  # Romanian: https://arxiv.org/pdf/1909.01247.pdf#section.4
]
PERSON_LABELS = ["PERSON", "PER", "persName"]
GPE_LABELS = ["GPE", "GPE_LOC", "GPE_ORG", "placeName"]


class X_Ray:
    def __init__(
        self, conn, kfx_json, mobi_html, mobi_codec, search_people, mediawiki, wikidata
    ):
        self.conn = conn
        self.entity_id = 1
        self.num_people = 0
        self.num_terms = 0
        self.erl = 0
        self.entities = {}
        self.people_counter = Counter()
        self.terms_counter = Counter()
        self.num_images = 0
        self.kfx_json = kfx_json
        self.mobi_html = mobi_html
        self.mobi_codec = mobi_codec
        self.search_people = search_people
        self.mediawiki = mediawiki
        self.wikidata = wikidata

    def insert_descriptions(self):
        for entity, data in self.entities.items():
            intro_cache = self.mediawiki.get_cache(entity)
            if (
                not self.search_people and data["label"] in PERSON_LABELS
            ) or intro_cache is None:
                insert_x_entity_description(
                    self.conn, (data["quote"], entity, None, data["id"])
                )
            elif self.wikidata and (
                wikidata_cache := self.wikidata.get_cache(intro_cache["item_id"])
            ):
                summary = intro_cache["intro"]
                if democracy_index_score := wikidata_cache["democracy_index"]:
                    summary += "\n" + regime_type(float(democracy_index_score))
                insert_x_entity_description(self.conn, (summary, entity, 1, data["id"]))
            else:
                insert_x_entity_description(
                    self.conn, (intro_cache["intro"], entity, 1, data["id"])
                )

    def insert_occurrence(self, entity_id, ner_label, start, entity_len):
        if ner_label in PERSON_LABELS:
            self.people_counter[entity_id] += 1
        else:
            self.terms_counter[entity_id] += 1
        insert_x_occurrence(self.conn, (entity_id, start, entity_len))
        self.erl = start + entity_len - 1

    def add_entity(self, entity, ner_label, start, quote, entity_len):
        from rapidfuzz.process import extractOne

        entity_id = self.entity_id
        entity_label = ner_label
        if r := extractOne(entity, self.entities.keys(), score_cutoff=FUZZ_THRESHOLD):
            entity_data = self.entities[r[0]]
            entity_id = entity_data["id"]
            entity_label = entity_data["label"]
        else:
            self.entities[entity] = {
                "id": self.entity_id,
                "label": ner_label,
                "quote": quote,
            }
            if ner_label in PERSON_LABELS:
                self.num_people += 1
            else:
                self.num_terms += 1
            self.entity_id += 1
        self.insert_occurrence(entity_id, entity_label, start, entity_len)

    def query_wiki_intro(self):
        pending_entities = []
        for entity, data in self.entities.items():
            if len(pending_entities) == MEDIAWIKI_API_EXLIMIT:
                self.mediawiki.query(pending_entities)
                pending_entities.clear()
            elif not self.mediawiki.has_cache(entity) and (
                self.search_people or data["label"] not in PERSON_LABELS
            ):
                pending_entities.append(entity)
        if len(pending_entities):
            self.mediawiki.query(pending_entities)

    def query_wikidata(self):
        pending_item_ids = []
        for item_id in filter(
            lambda x: x and not self.wikidata.has_cache(x),
            (
                self.mediawiki.get_cache(entity).get("item_id")
                for entity, data in self.entities.items()
                if data["label"] in GPE_LABELS and self.mediawiki.get_cache(entity)
            ),
        ):
            if len(pending_item_ids) == MEDIAWIKI_API_EXLIMIT:
                self.wikidata.query(pending_item_ids)
                pending_item_ids.clear()
            else:
                pending_item_ids.append(item_id)
        if len(pending_item_ids):
            self.wikidata.query(pending_item_ids)

    def finish(self, db_path):
        def top_mentioned(counter):
            return ",".join(map(str, [e[0] for e in counter.most_common(10)]))

        insert_x_entity(
            self.conn,
            (
                (
                    data["id"],
                    entity,
                    1 if data["label"] in PERSON_LABELS else 2,
                    self.people_counter[data["id"]]
                    if data["label"] in PERSON_LABELS
                    else self.terms_counter[data["id"]],
                )
                for entity, data in self.entities.items()
            ),
        )

        self.query_wiki_intro()
        if self.wikidata:
            self.query_wikidata()
        self.insert_descriptions()

        if self.kfx_json:
            self.find_kfx_images()
        else:
            self.find_mobi_images()
        if self.num_images:
            preview_images = ",".join(map(str, range(self.num_images)))
        else:
            preview_images = None
        insert_x_book_metadata(
            self.conn,
            (
                self.erl,
                1 if self.num_images else 0,
                self.num_people,
                self.num_terms,
                self.num_images,
                preview_images,
            ),
        )
        insert_x_type(self.conn, (1, 14, 15, 1, top_mentioned(self.people_counter)))
        insert_x_type(self.conn, (2, 16, 17, 2, top_mentioned(self.terms_counter)))

        create_x_indices(self.conn)
        save_db(self.conn, db_path)
        self.mediawiki.save_cache()
        if self.wikidata:
            self.wikidata.save_cache()

    def find_kfx_images(self):
        images = set()
        for entry in filter(lambda x: x["type"] == 2, self.kfx_json):
            if entry["content"] in images:
                continue
            images.add(entry["content"])
            insert_x_excerpt_image(
                self.conn,
                (
                    self.num_images,
                    entry["position"],
                    entry["content"],
                    entry["position"],
                ),
            )
            self.num_images += 1

    def find_mobi_images(self):
        images = set()
        for match_tag in re.finditer(b"<img [^>]+/>", self.mobi_html):
            if match_src := re.search(
                r'src="([^"]+)"', match_tag.group(0).decode(self.mobi_codec)
            ):
                image = match_src.group(1)
                if image in images:
                    continue
                images.add(image)
                insert_x_excerpt_image(
                    self.conn,
                    (self.num_images, match_tag.start(), image, match_tag.start()),
                )
                self.num_images += 1
