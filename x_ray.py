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
        is_full_name,
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
        is_full_name,
        query_mediawiki,
        query_wikidata,
        regime_type,
    )


class X_Ray:
    def __init__(self, conn, mediawiki, wikidata):
        self.conn = conn
        self.entity_id = 1
        self.num_people = 0
        self.num_terms = 0
        self.entities = {}
        self.people_counter = Counter()
        self.terms_counter = Counter()
        self.num_images = 0
        self.mediawiki = mediawiki
        self.wikidata = wikidata
        self.entity_occurrences = defaultdict(list)

    def insert_descriptions(self, search_people):
        for entity, data in self.entities.items():
            intro_cache = self.mediawiki.get_cache(entity)
            if (
                not search_people and data["label"] in PERSON_LABELS
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

    def add_entity(self, entity, ner_label, start, quote, entity_len):
        from rapidfuzz.fuzz import token_set_ratio
        from rapidfuzz.process import extractOne

        if entity_data := self.entities.get(entity):
            entity_id = entity_data["id"]
            ner_label = entity_data["label"]
        elif r := extractOne(
            entity,
            self.entities.keys(),
            score_cutoff=FUZZ_THRESHOLD,
            scorer=token_set_ratio,
        ):
            matched_name = r[0]
            matched_entity = self.entities[matched_name]
            matched_label = matched_entity["label"]
            entity_id = matched_entity["id"]
            if is_full_name(matched_name, matched_label, entity, ner_label):
                # replace partial name with full name
                self.entities[entity] = self.entities[matched_name]
                del self.entities[matched_name]
            ner_label = matched_label
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

    def finish(self, db_path, erl, kfx_json, mobi_html, mobi_codec, search_people):
        def top_mentioned(counter):
            return ",".join(map(str, [e[0] for e in counter.most_common(10)]))

        query_mediawiki(self.entities, self.mediawiki, search_people)
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
        self.insert_descriptions(search_people)

        if kfx_json:
            self.find_kfx_images(kfx_json)
        else:
            self.find_mobi_images(mobi_html, mobi_codec)
        if self.num_images:
            preview_images = ",".join(map(str, range(self.num_images)))
        else:
            preview_images = None
        insert_x_book_metadata(
            self.conn,
            (
                erl,
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

    def find_kfx_images(self, kfx_json):
        images = set()
        for index, image in filter(lambda x: x[1]["type"] == 2, enumerate(kfx_json)):
            if image["content"] in images:
                continue
            images.add(image["content"])
            caption_start = image["position"]
            caption_length = 0
            if (
                index + 1 < len(kfx_json)
                and kfx_json[index + 1]["type"] == 1
                and len(kfx_json[index + 1]["content"]) < 450
            ):
                caption = kfx_json[index + 1]
                caption_start = caption["position"]
                caption_length = len(caption["content"])
            insert_x_excerpt_image(
                self.conn,
                (
                    self.num_images,
                    caption_start,
                    caption_length,
                    image["content"],
                    image["position"],
                ),
            )
            self.num_images += 1

    def find_mobi_images(self, mobi_html, mobi_codec):
        images = set()
        for match_img in re.finditer(b"<img [^>]+/>", mobi_html):
            if match_src := re.search(
                r'src="([^"]+)"', match_img.group(0).decode(mobi_codec)
            ):
                image_src = match_src.group(1)
                if image_src in images:
                    continue
                images.add(image_src)
                caption_start = match_img.start()
                caption_length = 0
                previous_match_end = match_img.end()
                for _ in range(2):
                    match_caption = re.search(
                        b">[^<]{2,}<", mobi_html[previous_match_end:]
                    )
                    if not match_caption:
                        break
                    if not match_caption.group(0)[1:-1].strip():
                        previous_match_end += match_caption.end()
                        continue
                    if not re.match(
                        b"<html|<img",
                        mobi_html[
                            previous_match_end : previous_match_end
                            + match_caption.start()
                        ],
                    ):
                        caption_start = previous_match_end + match_caption.start() + 1
                        caption_length = match_caption.end() - match_caption.start() - 2
                    break

                insert_x_excerpt_image(
                    self.conn,
                    (
                        self.num_images,
                        caption_start,
                        caption_length,
                        image_src,
                        match_img.start(),
                    ),
                )
                self.num_images += 1
