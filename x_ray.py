import re
from collections import defaultdict
from functools import partial
from pathlib import Path
from sqlite3 import Connection

try:
    from .database import (
        create_x_indices,
        insert_x_book_metadata,
        insert_x_entities,
        insert_x_entity_description,
        insert_x_excerpt_image,
        insert_x_occurrences,
        insert_x_types,
        save_db,
    )
    from .mediawiki import (
        MediaWiki,
        Wikidata,
        inception_text,
        query_wikidata,
    )
    from .metadata import KFXJson
    from .utils import Prefs
    from .x_ray_share import (
        FUZZ_THRESHOLD,
        PERSON_LABELS,
        CustomXDict,
        XRayEntity,
        is_full_name,
    )
except ImportError:
    from database import (
        create_x_indices,
        insert_x_book_metadata,
        insert_x_entities,
        insert_x_entity_description,
        insert_x_excerpt_image,
        insert_x_occurrences,
        insert_x_types,
        save_db,
    )
    from mediawiki import (
        MediaWiki,
        Wikidata,
        inception_text,
        query_wikidata,
    )
    from metadata import KFXJson
    from utils import Prefs
    from x_ray_share import (
        FUZZ_THRESHOLD,
        PERSON_LABELS,
        CustomXDict,
        XRayEntity,
        is_full_name,
    )


class X_Ray:
    def __init__(
        self,
        conn: Connection,
        mediawiki: MediaWiki | None,
        wikidata: Wikidata | None,
        custom_x_ray: CustomXDict,
    ) -> None:
        self.conn = conn
        self.entity_id = 1
        self.entities: dict[str, XRayEntity] = {}
        self.num_images = 0
        self.mediawiki = mediawiki
        self.wikidata = wikidata
        self.entity_occurrences: dict[int, list[tuple[int, int]]] = defaultdict(list)
        self.custom_x_ray = custom_x_ray

    def insert_descriptions(self, search_people: bool) -> None:
        for entity_name, entity_data in self.entities.items():
            if custom_data := self.custom_x_ray.get(entity_name):
                if custom_data.desc is not None and len(custom_data.desc) > 0:
                    insert_x_entity_description(
                        self.conn,
                        (
                            custom_data.desc,
                            entity_name,
                            custom_data.source_id,
                            entity_data.id,
                        ),
                    )
                    continue

            if (
                self.mediawiki is not None
                and (search_people or entity_data.label not in PERSON_LABELS)
                and (intro_cache := self.mediawiki.get_cache(entity_name))
            ):
                summary = intro_cache.intro
                if self.wikidata is not None and (
                    wikidata_cache := self.wikidata.get_cache(
                        intro_cache.wikidata_item_id
                    )
                ):
                    if inception := wikidata_cache.get("inception"):
                        summary += "\n" + inception_text(inception)
                insert_x_entity_description(
                    self.conn,
                    (
                        summary,
                        entity_name,
                        1 if self.mediawiki.is_wikipedia else 2,
                        entity_data.id,
                    ),
                )
            else:
                insert_x_entity_description(
                    self.conn, (entity_data.quote, entity_name, None, entity_data.id)
                )

    def add_entity(
        self, entity: str, ner_label: str, start: int, quote: str, entity_len: int
    ) -> None:
        from rapidfuzz.fuzz import token_set_ratio
        from rapidfuzz.process import extractOne
        from rapidfuzz.utils import default_process

        if entity_data := self.entities.get(entity):
            entity_id = entity_data.id
            entity_data.count += 1
        elif entity not in self.custom_x_ray and (
            r := extractOne(
                entity,
                self.entities.keys(),
                score_cutoff=FUZZ_THRESHOLD,
                scorer=partial(token_set_ratio, processor=default_process),
            )
        ):
            matched_name = r[0]
            matched_entity = self.entities[matched_name]
            matched_entity.count += 1
            entity_id = matched_entity.id
            if is_full_name(matched_name, matched_entity.label, entity, ner_label):
                # replace partial name with full name
                self.entities[entity] = self.entities[matched_name]
                del self.entities[matched_name]
        else:
            entity_id = self.entity_id
            self.entities[entity] = XRayEntity(entity_id, quote, ner_label, 1)
            self.entity_id += 1

        self.entity_occurrences[entity_id].append((start, entity_len))

    def merge_entities(self, prefs: Prefs) -> None:
        for entity_name, entity_data in self.entities.copy().items():
            if entity_name in self.custom_x_ray:
                continue
            if self.mediawiki is not None:
                redirect_to = self.mediawiki.redirect_to_page(entity_name)
                if redirect_to in self.entities:
                    self.entity_occurrences[self.entities[redirect_to].id].extend(
                        self.entity_occurrences[entity_data.id]
                    )
                    self.entities[redirect_to].count += entity_data.count
                    del self.entity_occurrences[entity_data.id]
                    del self.entities[entity_name]
                    continue
            has_cache = (
                self.mediawiki is not None
                and self.mediawiki.get_cache(entity_name) is not None
            )
            is_person = entity_data.label in PERSON_LABELS
            if entity_data.count < prefs["minimal_x_ray_count"] and (
                (prefs["search_people"] and not has_cache)
                or (
                    not prefs["search_people"]
                    and (is_person or (not is_person and not has_cache))
                )
            ):
                del self.entity_occurrences[entity_data.id]
                del self.entities[entity_name]

    def finish(
        self,
        db_path: Path,
        erl: int,
        kfx_json: list[KFXJson],
        mobi_html: bytes,
        mobi_codec: str,
        prefs: Prefs,
    ) -> None:
        if self.mediawiki is not None:
            self.mediawiki.query(self.entities, prefs["search_people"])
        if self.wikidata is not None:
            query_wikidata(self.entities, self.mediawiki, self.wikidata)
        self.merge_entities(prefs)

        insert_x_entities(
            self.conn,
            (
                (
                    entity_data.id,
                    entity_name,
                    1 if entity_data.label in PERSON_LABELS else 2,
                    entity_data.count,
                )
                for entity_name, entity_data in self.entities.items()
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
        self.insert_descriptions(prefs["search_people"])

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
            erl,
            self.num_images,
            preview_images,
        )
        insert_x_types(self.conn)
        create_x_indices(self.conn)
        save_db(self.conn, db_path)
        if self.mediawiki is not None:
            self.mediawiki.close()
        if self.wikidata is not None:
            self.wikidata.close()

    def find_kfx_images(self, kfx_json: list[KFXJson]) -> None:
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

    def find_mobi_images(self, mobi_html: bytes, mobi_codec: str) -> None:
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
