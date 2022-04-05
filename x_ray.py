#!/usr/bin/env python3

import re
from collections import Counter, defaultdict

try:
    from .database import (
        create_x_indices,
        insert_x_book_metadata,
        insert_x_entities,
        insert_x_entity_description,
        insert_x_excerpt_image,
        insert_x_occurrences,
        insert_x_type,
        save_db,
    )
    from .mediawiki import (
        FUZZ_THRESHOLD,
        PERSON_LABELS,
        query_mediawiki,
        query_wikidata,
        regime_type,
    )
except ImportError:
    from database import (
        create_x_indices,
        insert_x_book_metadata,
        insert_x_entities,
        insert_x_entity_description,
        insert_x_excerpt_image,
        insert_x_occurrences,
        insert_x_type,
        save_db,
    )
    from mediawiki import (
        FUZZ_THRESHOLD,
        PERSON_LABELS,
        query_mediawiki,
        query_wikidata,
        regime_type,
    )


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
        self.entity_occurrences = defaultdict(list)

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
                if democracy_index := wikidata_cache["democracy_index"]:
                    summary += "\n" + regime_type(float(democracy_index))
                insert_x_entity_description(self.conn, (summary, entity, 1, data["id"]))
            else:
                insert_x_entity_description(
                    self.conn, (intro_cache["intro"], entity, 1, data["id"])
                )

    def get_entity_data(self, entity):
        entity_data = self.entities.get(entity)
        if isinstance(entity_data, str):
            return self.entities.get(entity_data)
        return entity_data

    def add_entity(self, entity, ner_label, start, quote, entity_len):
        from rapidfuzz.process import extractOne
        from rapidfuzz.fuzz import token_set_ratio

        if entity_data := self.get_entity_data(entity):
            entity_id = entity_data["id"]
            ner_label = entity_data["label"]
        elif r := extractOne(
            entity,
            self.entities.keys(),
            score_cutoff=FUZZ_THRESHOLD,
            scorer=token_set_ratio,
        ):
            matched_name = r[0]
            matched_entity = self.get_entity_data(matched_name)
            entity_id = matched_entity["id"]
            ner_label = matched_entity["label"]
            if " " in entity and " " not in matched_name:
                self.entities[entity] = matched_name
        else:
            entity_id = self.entity_id
            self.entities[entity] = {
                "id": entity_id,
                "label": ner_label,
                "quote": quote,
            }
            self.entity_id += 1

        if ner_label in PERSON_LABELS:
            self.people_counter[entity_id] += 1
        else:
            self.terms_counter[entity_id] += 1
        self.erl = start + entity_len - 1
        self.entity_occurrences[entity_id].append((start, entity_len))

    def merge_entities(self):
        for src_name, src_entity in self.entities.copy().items():
            dest_name = self.mediawiki.get_direct_cache(src_name)
            if isinstance(dest_name, str) and dest_name in self.entities:
                src_counter = self.get_entity_counter(src_entity["label"])
                src_count = src_counter[src_entity["id"]]
                del src_counter[src_entity["id"]]
                dest_entity = self.entities[dest_name]
                self.get_entity_counter(dest_entity["label"])[
                    dest_entity["id"]
                ] += src_count
                self.entity_occurrences[dest_entity["id"]].extend(
                    self.entity_occurrences[src_entity["id"]]
                )
                del self.entity_occurrences[src_entity["id"]]
                del self.entities[src_name]
            elif src_entity["label"] in PERSON_LABELS:
                self.num_people += 1
            else:
                self.num_terms += 1

    def get_entity_counter(self, entity_label):
        return (
            self.people_counter if entity_label in PERSON_LABELS else self.terms_counter
        )

    def finish(self, db_path):
        def top_mentioned(counter):
            return ",".join(map(str, [e[0] for e in counter.most_common(10)]))

        query_mediawiki(self.entities, self.mediawiki, self.search_people)
        if self.wikidata:
            query_wikidata(self.entities, self.mediawiki, self.wikidata)
        self.merge_entities()

        insert_x_entities(
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
        insert_x_occurrences(
            self.conn,
            (
                (entity_id, start, entity_length)
                for entity_id, occurrence_list in self.entity_occurrences.items()
                for start, entity_length in occurrence_list
            ),
        )
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
