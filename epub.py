import operator
import re
import shutil
import sqlite3
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from functools import partial
from html import escape, unescape
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote

try:
    from .mediawiki import (
        MediaWiki,
        Wikidata,
        Wikimedia_Commons,
        inception_text,
        query_wikidata,
    )
    from .utils import CJK_LANGS, Prefs, is_wsd_enabled
    from .wsd import load_wsd_model, wsd
    from .x_ray_share import (
        FUZZ_THRESHOLD,
        PERSON_LABELS,
        CustomXDict,
        XRayEntity,
        is_full_name,
    )
except ImportError:
    from mediawiki import (
        MediaWiki,
        Wikidata,
        Wikimedia_Commons,
        inception_text,
        query_wikidata,
    )
    from utils import CJK_LANGS, Prefs, is_wsd_enabled
    from wsd import load_wsd_model, wsd
    from x_ray_share import (
        FUZZ_THRESHOLD,
        PERSON_LABELS,
        CustomXDict,
        XRayEntity,
        is_full_name,
    )


NAMESPACES = {
    "n": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "ops": "http://www.idpf.org/2007/ops",
    "xml": "http://www.w3.org/1999/xhtml",
}


@dataclass
class Occurrence:
    paragraph_start: int
    paragraph_end: int
    word_start: int
    word_end: int
    entity_id: int = -1
    sense_ids: tuple[int, ...] = ()
    sent: str = ""
    start_in_sent: int = 0
    end_in_sent: int = 0


@dataclass
class Sense:
    pos: str
    short_def: str
    full_def: str
    example: str
    embed: str
    ipas: list[str] = field(default_factory=list)


class EPUB:
    def __init__(
        self,
        book_path_str: str,
        mediawiki: MediaWiki | None,
        wiki_commons: Wikimedia_Commons | None,
        wikidata: Wikidata | None,
        custom_x_ray: CustomXDict,
        lemmas_conn: sqlite3.Connection | None,
        prefs: Prefs,
        lemma_lang: str,
    ) -> None:
        self.book_path = Path(book_path_str)
        self.mediawiki = mediawiki
        self.wiki_commons = wiki_commons
        self.wikidata = wikidata
        self.entity_id = 0
        self.entities: dict[str, XRayEntity] = {}
        self.entity_occurrences: dict[Path, list[Occurrence]] = defaultdict(list)
        self.removed_entity_ids: set[int] = set()
        self.extract_folder = self.book_path.with_name("extract")
        if self.extract_folder.exists():
            shutil.rmtree(self.extract_folder)
        self.xhtml_folder = self.extract_folder
        self.xhtml_href_has_folder = False
        self.image_folder = self.extract_folder
        self.image_href_has_folder = False
        self.image_filenames: set[str] = set()
        self.custom_x_ray = custom_x_ray
        self.sense_id_dict: dict[tuple[int, ...], int] = {}
        self.word_wise_id = 0
        self.lemmas_conn: sqlite3.Connection | None = lemmas_conn
        self.prefs = prefs
        self.lemma_lang = lemma_lang
        self.gloss_lang = prefs["gloss_lang"]
        self.enable_wsd: bool = False
        self.wsd_model = None
        self.wsd_tokenizer = None

    def extract_epub(self) -> Iterator[tuple[str, tuple[int, int, Path]]]:
        from lxml import etree

        with zipfile.ZipFile(self.book_path) as zf:
            zf.extractall(self.extract_folder)

        opf_root = etree.parse(self.extract_folder / "META-INF/container.xml")
        opf_path = unquote(opf_root.find(".//n:rootfile", NAMESPACES).get("full-path"))
        self.opf_path = self.extract_folder.joinpath(opf_path)
        if not self.opf_path.exists():
            self.opf_path = next(self.extract_folder.rglob(opf_path))
        self.opf_root = etree.parse(self.opf_path)

        # find image files folder
        for item in self.opf_root.xpath(
            'opf:manifest/opf:item[starts-with(@media-type, "image/")]',
            namespaces=NAMESPACES,
        ):
            image_href = unquote(item.get("href"))
            image_path = self.extract_folder.joinpath(image_href)
            if not image_path.exists():
                image_path = next(self.extract_folder.rglob(image_href))
            if not image_path.parent.samefile(self.extract_folder):
                self.image_folder = image_path.parent
            if "/" in image_href:
                self.image_href_has_folder = True
                break

        for itemref in self.opf_root.iterfind("opf:spine/opf:itemref", NAMESPACES):
            idref = itemref.get("idref")
            item = self.opf_root.find(
                f'opf:manifest/opf:item[@id="{idref}"]', NAMESPACES
            )
            xhtml_href = unquote(item.get("href"))
            xhtml_path = self.opf_path.parent.joinpath(xhtml_href)
            if not xhtml_path.exists():
                xhtml_path = next(self.extract_folder.rglob(xhtml_href))
            if not xhtml_path.parent.samefile(self.extract_folder):
                self.xhtml_folder = xhtml_path.parent
            if "/" in xhtml_href:
                self.xhtml_href_has_folder = True
            with xhtml_path.open("r", encoding="utf-8") as f:
                # remove soft hyphen, byte order mark, word joiner
                xhtml_text = re.sub(
                    r"\xad|&shy;|&#xad;|&#173;|\ufeff|\u2060|&NoBreak;",
                    "",
                    f.read(),
                    flags=re.I,
                )
            with xhtml_path.open("w", encoding="utf-8") as f:
                f.write(xhtml_text)
            for match_body in re.finditer(r"<body.{3,}?</body>", xhtml_text, re.DOTALL):
                for m in re.finditer(r">[^<]{2,}<", match_body.group(0)):
                    text = m.group(0)[1:-1]
                    yield (
                        unescape(text),
                        (
                            match_body.start() + m.start() + 1,
                            match_body.start() + m.end() - 1,
                            xhtml_path,
                        ),
                    )

    def add_entity(
        self,
        entity_name: str,
        ner_label: str,
        book_quote: str,
        paragraph_start: int,
        paragraph_end: int,
        word_start: int,
        word_end: int,
        xhtml_path: Path,
    ) -> None:
        from rapidfuzz.fuzz import token_set_ratio
        from rapidfuzz.process import extractOne
        from rapidfuzz.utils import default_process

        if entity_data := self.entities.get(entity_name):
            entity_id = entity_data.id
            entity_data.count += 1
        elif entity_name not in self.custom_x_ray and (
            r := extractOne(
                entity_name,
                self.entities.keys(),
                score_cutoff=FUZZ_THRESHOLD,
                scorer=partial(token_set_ratio, processor=default_process),
            )
        ):
            matched_name = r[0]
            matched_entity = self.entities[matched_name]
            matched_entity.count += 1
            entity_id = matched_entity.id
            if is_full_name(matched_name, matched_entity.label, entity_name, ner_label):
                self.entities[entity_name] = matched_entity
                del self.entities[matched_name]
        else:
            entity_id = self.entity_id
            self.entities[entity_name] = XRayEntity(
                self.entity_id, book_quote, ner_label, 1
            )
            self.entity_id += 1

        self.entity_occurrences[xhtml_path].append(
            Occurrence(
                paragraph_start=paragraph_start,
                paragraph_end=paragraph_end,
                word_start=word_start,
                word_end=word_end,
                entity_id=entity_id,
            )
        )

    def add_lemma(
        self,
        lemma: str,
        word: str,
        pos: str,
        paragraph_start: int,
        paragraph_end: int,
        word_start: int,
        word_end: int,
        xhtml_path: Path,
        sent,
    ) -> None:
        sense_ids = self.find_sense_ids(lemma, word, pos)
        if len(sense_ids) == 0:
            return
        if sense_ids in self.sense_id_dict:
            ww_id = self.sense_id_dict[sense_ids]
        else:
            ww_id = self.word_wise_id
            self.word_wise_id += 1
            self.sense_id_dict[sense_ids] = ww_id

        self.entity_occurrences[xhtml_path].append(
            Occurrence(
                paragraph_start=paragraph_start,
                paragraph_end=paragraph_end,
                word_start=word_start,
                word_end=word_end,
                sense_ids=sense_ids,
                sent=sent.text,
                start_in_sent=word_start - sent.start_char,
                end_in_sent=word_end - sent.start_char,
            )
        )

    def remove_entities(self, minimal_count: int) -> None:
        for entity_name, entity_data in self.entities.copy().items():
            if (
                entity_data.count < minimal_count
                and self.mediawiki is not None  # mypy
                and self.mediawiki.get_cache(entity_name) is None
                and entity_name not in self.custom_x_ray
            ):
                del self.entities[entity_name]
                self.removed_entity_ids.add(entity_data.id)

    def modify_epub(self) -> None:
        if len(self.entities) > 0:
            if self.mediawiki is not None:
                self.mediawiki.query(self.entities, self.prefs["search_people"])
                if self.wikidata is not None:
                    query_wikidata(self.entities, self.mediawiki, self.wikidata)
            if self.prefs["minimal_x_ray_count"] > 1:
                self.remove_entities(self.prefs["minimal_x_ray_count"])
            self.create_x_ray_footnotes()

        if is_wsd_enabled(self.prefs, self.lemma_lang):
            self.enable_wsd = True
            self.wsd_model, self.wsd_tokenizer = load_wsd_model(
                self.prefs["torch_compute_platform"]
            )

        self.insert_anchor_elements()
        if len(self.sense_id_dict) > 0:
            self.create_word_wise_footnotes()
        self.modify_opf()
        self.zip_extract_folder()
        if self.mediawiki is not None:
            self.mediawiki.close()
        if self.wikidata is not None:
            self.wikidata.close()
        if self.wiki_commons is not None:
            self.wiki_commons.close()
        if self.lemmas_conn is not None:
            self.lemmas_conn.close()

    def insert_anchor_elements(self) -> None:
        css_rules = ""
        if len(self.sense_id_dict) > 0:
            css_rules += """
            body {line-height: 2;}
            ruby.wordwise * {text-decoration: none;}

            a.x-ray, a.wordwise, ruby.wordwise a {
              text-decoration: none;
              color: inherit;
            }
            """

        for xhtml_path, occurrences in self.entity_occurrences.items():
            if len(self.entities) > 0 and self.lemmas_conn is not None:
                occurrences = sorted(
                    occurrences,
                    key=operator.attrgetter("paragraph_start", "word_start"),
                )
            with xhtml_path.open(encoding="utf-8") as f:
                xhtml_str = f.read()
            new_xhtml_str = ""
            last_p_text = ""
            last_w_end = 0
            last_p_end = 0
            for occurrence in occurrences:
                if occurrence.entity_id in self.removed_entity_ids:
                    continue
                if occurrence.paragraph_end != last_p_end:
                    new_xhtml_str += escape(last_p_text[last_w_end:])
                    new_xhtml_str += xhtml_str[last_p_end : occurrence.paragraph_start]
                    last_w_end = 0

                paragraph_text = unescape(
                    xhtml_str[occurrence.paragraph_start : occurrence.paragraph_end]
                )
                new_xhtml_str += escape(
                    paragraph_text[last_w_end : occurrence.word_start]
                )
                word = paragraph_text[occurrence.word_start : occurrence.word_end]
                if occurrence.entity_id != -1:
                    new_xhtml_str += (
                        f'<a class="x-ray" epub:type="noteref" href="x_ray.xhtml#'
                        f'{occurrence.entity_id}">{escape(word)}</a>'
                    )
                else:
                    new_xhtml_str += self.build_word_wise_tag(occurrence, word)
                last_w_end = occurrence.word_end
                if occurrence.paragraph_end != last_p_end:
                    last_p_end = occurrence.paragraph_end
                    last_p_text = paragraph_text

            new_xhtml_str += escape(last_p_text[last_w_end:])
            new_xhtml_str += xhtml_str[last_p_end:]

            # add epub namespace and CSS
            with xhtml_path.open("w", encoding="utf-8") as f:
                if NAMESPACES["ops"] not in new_xhtml_str:
                    new_xhtml_str = new_xhtml_str.replace(
                        f'xmlns="{NAMESPACES["xml"]}"',
                        f'xmlns="{NAMESPACES["xml"]}" xmlns:epub="{NAMESPACES["ops"]}"',
                    )
                if len(css_rules) > 0:
                    new_xhtml_str = new_xhtml_str.replace(
                        "</head>", f"<style>{css_rules}</style></head>"
                    )
                f.write(new_xhtml_str)

    def build_word_wise_tag(
        self,
        occurrence: Occurrence,
        word: str,
    ) -> str:
        ww_id = self.sense_id_dict[occurrence.sense_ids]
        sense_list = self.get_sense_data(occurrence.sense_ids)
        if self.enable_wsd and len(sense_list) > 1 and occurrence.sent.strip() != word:
            use_sense_index = wsd(
                self.wsd_model,
                self.wsd_tokenizer,
                occurrence.sent,
                (occurrence.start_in_sent, occurrence.end_in_sent),
                [s.embed for s in sense_list],
            )
            short_def = sense_list[use_sense_index].short_def
            len_ratio = 0.0
        else:
            short_def = sense_list[0].short_def
            len_ratio = 3.0 if self.lemma_lang in CJK_LANGS else 2.5
        if not self.enable_wsd and len(short_def) / len(word) > len_ratio:
            return (
                '<a class="wordwise" epub:type="noteref" href="word_wise.xhtml#'
                f'{ww_id}">{escape(word)}</a>'
            )
        else:
            return (
                '<ruby class="wordwise"><a epub:type="noteref" href="word_wise.xhtml#'
                f'{ww_id}">{escape(word)}</a><rp>(</rp><rt>{escape(short_def)}'
                "</rt><rp>)</rp></ruby>"
            )

    def create_x_ray_footnotes(self) -> None:
        image_prefix = ""
        if self.xhtml_href_has_folder:
            image_prefix += "../"
        if self.image_href_has_folder:
            image_prefix += f"{self.image_folder.name}/"
        s = f"""
        <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:epub="http://www.idpf.org/2007/ops"
        lang="{self.lemma_lang}" xml:lang="{self.lemma_lang}">
        <head><title>X-Ray</title><meta charset="utf-8"/></head>
        <body>
        """
        for entity_name, entity_data in self.entities.items():
            if entity_data.id in self.removed_entity_ids:
                continue
            elif custom_data := self.custom_x_ray.get(entity_name):
                s += (
                    f'<aside id="{entity_data.id}" epub:type="footnote">'
                    f"{create_p_tags(custom_data.desc)}"
                )
                if custom_data.source_id is not None and self.mediawiki is not None:
                    s += "<p>Source: "
                    s += (
                        "Wikipedia"
                        if custom_data.source_id == 1
                        else self.mediawiki.sitename
                    )
                    s += "</p>"
                s += "</aside>"
            elif (
                self.mediawiki is not None
                and (
                    self.prefs["search_people"]
                    or entity_data.label not in PERSON_LABELS
                )
                and (intro_cache := self.mediawiki.get_cache(entity_name))
            ):
                s += f'<aside id="{entity_data.id}" epub:type="footnote">'
                s += create_p_tags(intro_cache.intro)
                s += f"<p>Source: {self.mediawiki.sitename}</p>"
                if self.wikidata is not None and (
                    wikidata_cache := self.wikidata.get_cache(
                        intro_cache.wikidata_item_id
                    )
                ):
                    add_wikidata_source = False
                    if inception := wikidata_cache.get("inception"):
                        s += f"<p>{inception_text(inception)}</p>"
                        add_wikidata_source = True
                    if self.wiki_commons is not None and (
                        filename := wikidata_cache.get("map_filename")
                    ):
                        file_path = self.wiki_commons.get_image(filename)
                        if file_path is not None:
                            s += (
                                '<img style="max-width:100%" src="'
                                f'{image_prefix}{filename}" />'
                            )
                            shutil.copy(file_path, self.image_folder.joinpath(filename))
                            self.image_filenames.add(filename)
                            add_wikidata_source = True
                    if add_wikidata_source:
                        s += "<p>Source: Wikidata</p>"
                s += "</aside>"
            else:
                s += (
                    f'<aside id="{entity_data.id}" epub:type="footnote"><p>'
                    f"{escape(entity_data.quote)}</p></aside>"
                )

        s += "</body></html>"
        with self.xhtml_folder.joinpath("x_ray.xhtml").open("w", encoding="utf-8") as f:
            f.write(s)

    def create_word_wise_footnotes(self) -> None:
        page_text = f"""
        <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:epub="http://www.idpf.org/2007/ops"
        lang="{self.gloss_lang}" xml:lang="{self.gloss_lang}">
        <head><title>Word Wise</title><meta charset="utf-8"/></head>
        <body>
        """
        for sense_ids, ww_id in self.sense_id_dict.items():
            page_text += self.create_ww_aside_tag(sense_ids, ww_id)
        page_text += "</body></html>"
        with self.xhtml_folder.joinpath("word_wise.xhtml").open(
            "w", encoding="utf-8"
        ) as f:
            f.write(page_text)

    def create_ww_aside_tag(self, sense_ids: tuple[int, ...], ww_id: int) -> str:
        sense_list = self.get_sense_data(sense_ids)
        tag_str = ""
        tag_str += f'<aside id="{ww_id}" epub:type="footnote">'
        last_pos = ""
        last_ipas: list[str] = []
        for sense_data in sense_list:
            if sense_data.pos != last_pos or sense_data.ipas != last_ipas:
                if last_pos != "":
                    tag_str += "</ol><hr/>"
                tag_str += f"<p>{sense_data.pos.title()}</p>"
                for ipa in sense_data.ipas:
                    tag_str += f"<p>{escape(ipa)}</p>"
                tag_str += f"<ol><li>{escape(sense_data.full_def)}"
                last_pos = sense_data.pos
                last_ipas = sense_data.ipas
            else:
                tag_str += f"<li>{escape(sense_data.full_def)}"
            if sense_data.example != "":
                tag_str += f"<dl><dd><i>{escape(sense_data.example)}</i></dd></dl>"
            tag_str += "</li>"
        tag_str += "</ol><hr/><p>Source: Wiktionary</p></aside>"
        return tag_str

    def modify_opf(self) -> None:
        from lxml import etree

        xhtml_prefix = ""
        image_prefix = ""
        if self.xhtml_href_has_folder:
            xhtml_prefix = f"{self.xhtml_folder.name}/"
        if self.image_href_has_folder:
            image_prefix = f"{self.image_folder.name}/"
        manifest = self.opf_root.find("opf:manifest", NAMESPACES)
        if len(self.entities) > 0:
            s = (
                f'<item href="{xhtml_prefix}x_ray.xhtml" '
                'id="x_ray.xhtml" media-type="application/xhtml+xml"/>'
            )
            manifest.append(etree.fromstring(s))
        if len(self.sense_id_dict) > 0:
            s = (
                f'<item href="{xhtml_prefix}word_wise.xhtml" '
                'id="word_wise.xhtml" media-type="application/xhtml+xml"/>'
            )
            manifest.append(etree.fromstring(s))
        for filename in self.image_filenames:
            filename_lower = filename.lower()
            if filename_lower.endswith(".svg"):
                media_type = "svg+xml"
            elif filename_lower.endswith(".png"):
                media_type = "png"
            elif filename_lower.endswith(".jpg"):
                media_type = "jpeg"
            elif filename_lower.endswith(".webp"):
                media_type = "webp"
            else:
                media_type = Path(filename).suffix.replace(".", "")
            s = (
                f'<item href="{image_prefix}{filename}" id="{filename}" '
                f'media-type="image/{media_type}"/>'
            )
            manifest.append(etree.fromstring(s))
        spine = self.opf_root.find("opf:spine", NAMESPACES)
        if len(self.entities) > 0:
            spine.append(etree.fromstring('<itemref idref="x_ray.xhtml"/>'))
        if len(self.sense_id_dict) > 0:
            spine.append(etree.fromstring('<itemref idref="word_wise.xhtml"/>'))
        with self.opf_path.open("w", encoding="utf-8") as f:
            f.write(etree.tostring(self.opf_root, encoding=str))

    def zip_extract_folder(self) -> None:
        shutil.make_archive(str(self.extract_folder), "zip", self.extract_folder)
        self.extract_folder.with_suffix(".zip").replace(self.book_path)
        shutil.rmtree(self.extract_folder)

    def find_sense_ids(self, lemma: str, word: str, pos: str) -> tuple[int, ...]:
        if pos != "":
            return self.find_sense_ids_with_pos(lemma, word, pos)
        else:
            return self.find_sense_ids_without_pos(word)

    def find_sense_ids_with_pos(
        self, lemma: str, word: str, pos: str
    ) -> tuple[int, ...]:
        if self.lemmas_conn is None:
            return ()
        difficulty_limit = self.prefs.get(
            f"{self.lemma_lang}_wiktionary_difficulty_limit", 5
        )
        sense_ids = []
        for (sense_id,) in self.lemmas_conn.execute(
            """
            SELECT id FROM senses
            WHERE lemma = ? AND pos = ? AND difficulty <= ? AND enabled = 1
            """,
            (lemma, pos, difficulty_limit),
        ):
            sense_ids.append(sense_id)
        if len(sense_ids) == 0:
            for (sense_id,) in self.lemmas_conn.execute(
                """
                SELECT DISTINCT s.id
                FROM senses s JOIN forms f ON s.form_group_id = f.form_group_id
                WHERE form = ? AND pos = ? AND difficulty <= ? AND enabled = 1
                """,
                (word, pos, difficulty_limit),
            ):
                sense_ids.append(sense_id)

        return tuple(sense_ids)

    def find_sense_ids_without_pos(self, word: str) -> tuple[int, ...]:
        if self.lemmas_conn is None:
            return ()
        difficulty_limit = self.prefs.get(
            f"{self.lemma_lang}_wiktionary_difficulty_limit", 5
        )
        sense_ids = []
        for (sense_id,) in self.lemmas_conn.execute(
            "SELECT id FROM senses WHERE lemma = ? AND difficulty <= ? AND enabled = 1",
            (word, difficulty_limit),
        ):
            sense_ids.append(sense_id)
        if len(sense_ids) > 0:
            return tuple(sense_ids)
        for (sense_id,) in self.lemmas_conn.execute(
            """
            SELECT DISTINCT s.id
            FROM senses s JOIN forms f ON s.form_group_id = f.form_group_id
            WHERE form = ? AND difficulty <= ? AND enabled = 1
            """,
            (word, difficulty_limit),
        ):
            sense_ids.append(sense_id)

        return tuple(sense_ids)

    def get_sense_data(self, sense_ids: tuple[int, ...]) -> list[Sense]:
        if self.lemmas_conn is None:
            return []
        sql = """
        SELECT
        pos, short_def, full_def, example, embed_vector,
        ipa, ga_ipa, rp_ipa, pinyin, bopomofo
        FROM senses LEFT JOIN sounds ON senses.sound_id = sounds.id
        WHERE senses.id = ?
        """
        sense_list: list[Sense] = []
        for sense_id in sense_ids:
            for (
                pos,
                short_def,
                full_def,
                example,
                embed,
                *ipas,
            ) in self.lemmas_conn.execute(sql, (sense_id,)):
                sense_list.append(
                    Sense(
                        pos=pos,
                        short_def=short_def,
                        full_def=full_def,
                        example=example,
                        ipas=[
                            ipa for ipa in ipas if isinstance(ipa, str) and len(ipa) > 0
                        ],
                        embed=embed,
                    )
                )
        return sense_list


def spacy_to_wiktionary_pos(pos: str) -> str:
    # spaCy POS: https://universaldependencies.org/u/pos
    # Wiktioanry POS: https://github.com/tatuylonen/wiktextract/blob/master/wiktextract/data/en/pos_subtitles.json
    # Proficiency POS: https://github.com/xxyzz/Proficiency/blob/master/extract_wiktionary.py#L31
    match pos:
        case "NOUN":
            return "noun"
        case "ADJ":
            return "adj"
        case "VERB":
            return "verb"
        case "ADV":
            return "adv"
        # case "ADP":
        #     return "prep"
        # case "CCONJ" | "SCONJ":
        #     return "conj"
        # case "DET":
        #     return "det"
        # case "INTJ":
        #     return "intj"
        # case "NUM":
        #     return "num"
        # case "PART":
        #     return "particle"
        # case "PRON":
        #     return "pron"
        # case "PROPN":
        #     return "name"
        # case "PUNCT":
        #     return "punct"
        # case "SYM":
        #     return "symbol"
        case _:
            return "other"


def create_p_tags(intro: str) -> str:
    return "".join(f"<p>{escape(line)}</p>" for line in intro.splitlines())
