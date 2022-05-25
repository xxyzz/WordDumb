#!/usr/bin/env python3

import re
import shutil
import zipfile
from collections import defaultdict
from html import escape, unescape
from pathlib import Path
from urllib.parse import quote

try:
    from .mediawiki import (
        FUZZ_THRESHOLD,
        PERSON_LABELS,
        query_mediawiki,
        query_wikidata,
        regime_type,
    )
except ImportError:
    from mediawiki import (
        FUZZ_THRESHOLD,
        PERSON_LABELS,
        query_mediawiki,
        query_wikidata,
        regime_type,
    )


NAMESPACES = {
    "n": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "ops": "http://www.idpf.org/2007/ops",
    "xml": "http://www.w3.org/1999/xhtml",
}


class X_Ray_EPUB:
    def __init__(self, book_path, mediawiki, wiki_commons, wikidata):
        self.book_path = book_path
        self.mediawiki = mediawiki
        self.wiki_commons = wiki_commons
        self.wikidata = wikidata
        self.entity_id = 0
        self.entities = {}
        self.entity_occurrences = defaultdict(list)
        self.extract_folder = Path(book_path).with_name("extract")
        if self.extract_folder.exists():
            shutil.rmtree(self.extract_folder)
        self.xhtml_folder = self.extract_folder
        self.xhtml_href_has_folder = False
        self.image_folder = self.extract_folder
        self.image_href_has_folder = False

    def extract_epub(self):
        from lxml import etree

        with zipfile.ZipFile(self.book_path) as zf:
            zf.extractall(self.extract_folder)

        with self.extract_folder.joinpath("META-INF/container.xml").open("rb") as f:
            root = etree.fromstring(f.read())
            opf_path = root.find(".//n:rootfile", NAMESPACES).get("full-path")
            self.opf_path = self.extract_folder.joinpath(opf_path)
            if not self.opf_path.exists():
                self.opf_path = next(self.extract_folder.rglob(opf_path))
        with self.opf_path.open("rb") as opf:
            self.opf_root = etree.fromstring(opf.read())
            for item in self.opf_root.xpath(
                'opf:manifest/opf:item[starts-with(@media-type, "image/")]',
                namespaces=NAMESPACES,
            ):
                image = item.get("href")
                image_path = self.extract_folder.joinpath(image)
                if not image_path.exists():
                    image_path = next(self.extract_folder.rglob(image))
                if not image_path.parent.samefile(self.extract_folder):
                    self.image_folder = image_path.parent
                if "/" in image:
                    self.image_href_has_folder = True
                    break

            for item in self.opf_root.iterfind(
                'opf:manifest/opf:item[@media-type="application/xhtml+xml"]', NAMESPACES
            ):
                if item.get("properties") == "nav":
                    continue
                xhtml = item.get("href")
                xhtml_path = self.extract_folder.joinpath(xhtml)
                if not xhtml_path.exists():
                    xhtml_path = next(self.extract_folder.rglob(xhtml))
                if not xhtml_path.parent.samefile(self.extract_folder):
                    self.xhtml_folder = xhtml_path.parent
                if "/" in xhtml:
                    self.xhtml_href_has_folder = True
                with xhtml_path.open(encoding="utf-8") as f:
                    for match_body in re.finditer(
                        r"<body.{3,}?</body>", f.read(), re.DOTALL
                    ):
                        for m in re.finditer(r">[^<]{2,}<", match_body.group(0)):
                            text = m.group(0)[1:-1]
                            yield unescape(text), (
                                match_body.start() + m.start() + 1,
                                text,
                                xhtml_path,
                            )

    def add_entity(
        self, entity, ner_label, book_quote, start, end, xhtml_path, origin_entity
    ):
        from rapidfuzz.fuzz import token_set_ratio
        from rapidfuzz.process import extractOne

        if entity_data := self.entities.get(entity):
            entity_id = entity_data["id"]
        elif r := extractOne(
            entity,
            self.entities.keys(),
            score_cutoff=FUZZ_THRESHOLD,
            scorer=token_set_ratio,
        ):
            matched_name = r[0]
            entity_id = self.entities[matched_name]["id"]
            if " " in entity and " " not in matched_name:
                self.entities[entity] = self.entities[matched_name]
                del self.entities[matched_name]
        else:
            entity_id = self.entity_id
            self.entities[entity] = {
                "id": self.entity_id,
                "label": ner_label,
                "quote": book_quote,
            }
            self.entity_id += 1

        self.entity_occurrences[xhtml_path].append(
            (start, end, origin_entity, entity_id)
        )

    def modify_epub(self, search_people):
        query_mediawiki(self.entities, self.mediawiki, search_people)
        if self.wikidata:
            query_wikidata(self.entities, self.mediawiki, self.wikidata)
        self.insert_anchor_elements()
        self.create_footnotes(search_people)
        self.modify_opf()
        self.zip_extract_folder()

    def insert_anchor_elements(self):
        for xhtml_path, entity_list in self.entity_occurrences.items():
            with xhtml_path.open(encoding="utf-8") as f:
                xhtml_str = f.read()
            new_xhtml_str = ""
            last_end = 0
            for start, end, entity, entity_id in entity_list:
                new_xhtml_str += xhtml_str[last_end:start]
                new_xhtml_str += f'<a epub:type="noteref" href="x_ray.xhtml#{entity_id}">{entity}</a>'
                last_end = end
            new_xhtml_str += xhtml_str[last_end:]

            with xhtml_path.open("w", encoding="utf-8") as f:
                if NAMESPACES["ops"] not in new_xhtml_str:
                    # add epub namespace
                    new_xhtml_str = new_xhtml_str.replace(
                        f'xmlns="{NAMESPACES["xml"]}"',
                        f'xmlns="{NAMESPACES["xml"]}" '
                        f'xmlns:epub="{NAMESPACES["ops"]}"',
                    )
                f.write(new_xhtml_str)

    def create_footnotes(self, search_people):
        self.image_filenames = set()
        image_prefix = ""
        if self.xhtml_href_has_folder:
            image_prefix += "../"
        if self.image_href_has_folder:
            image_prefix += f"{self.image_folder.name}/"
        s = """
        <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:epub="http://www.idpf.org/2007/ops"
        lang="en-US" xml:lang="en-US">
        <head><title>X-Ray</title><meta charset="utf-8"/></head>
        <body>
        """
        for entity, data in self.entities.items():
            if (search_people or data["label"] not in PERSON_LABELS) and (
                intro_cache := self.mediawiki.get_cache(entity)
            ):
                s += f"""
                <aside id="{data["id"]}" epub:type="footnote">
                {escape(intro_cache["intro"])}
                <a href="{self.mediawiki.source_link}{quote(entity)}">
                {self.mediawiki.source_name}
                </a>
                """
                if self.wikidata and (
                    wikidata_cache := self.wikidata.get_cache(intro_cache["item_id"])
                ):
                    if democracy_index := wikidata_cache.get("democracy_index"):
                        s += f"<p>{regime_type(float(democracy_index))}</p>"
                    if self.wiki_commons and (
                        filename := wikidata_cache.get("map_filename")
                    ):
                        file_path = self.wiki_commons.get_image(filename)
                        s += f'<img style="max-width:100%" src="{image_prefix}{filename}" />'
                        shutil.copy(file_path, self.image_folder.joinpath(filename))
                        self.image_filenames.add(filename)
                    s += f'<a href="https://www.wikidata.org/wiki/{intro_cache["item_id"]}">Wikidata</a>'
            else:
                s += f'<aside id="{data["id"]}" epub:type="footnote">{escape(data["quote"])}'
            s += "</aside>"
        s += "</body></html>"
        with self.xhtml_folder.joinpath("x_ray.xhtml").open("w", encoding="utf-8") as f:
            f.write(s)
        self.mediawiki.close()
        if self.wikidata:
            self.wikidata.close()
        if self.wiki_commons:
            self.wiki_commons.close()

    def modify_opf(self):
        from lxml import etree

        xhtml_prefix = ""
        image_prefix = ""
        if self.xhtml_href_has_folder:
            xhtml_prefix = f"{self.xhtml_folder.name}/"
        if self.image_href_has_folder:
            image_prefix = f"{self.image_folder.name}/"
        s = f'<item href="{xhtml_prefix}x_ray.xhtml" id="x_ray.xhtml" media-type="application/xhtml+xml"/>'
        manifest = self.opf_root.find("opf:manifest", NAMESPACES)
        manifest.append(etree.fromstring(s))
        for filename in self.image_filenames:
            if filename.endswith(".svg"):
                media_type = "svg+xml"
            elif filename.endswith(".png"):
                media_type = "png"
            elif filename.endswith(".jpg"):
                media_type = "jpeg"
            elif filename.endswith(".webp"):
                media_type = "webp"
            s = f'<item href="{image_prefix}{filename}" id="{filename}" media-type="image/{media_type}"/>'
            manifest.append(etree.fromstring(s))
        spine = self.opf_root.find("opf:spine", NAMESPACES)
        s = '<itemref idref="x_ray.xhtml"/>'
        spine.append(etree.fromstring(s))
        with self.opf_path.open("w", encoding="utf-8") as f:
            f.write(etree.tostring(self.opf_root, encoding=str))

    def zip_extract_folder(self):
        self.book_path = Path(self.book_path)
        shutil.make_archive(self.extract_folder, "zip", self.extract_folder)
        shutil.move(
            self.extract_folder.with_suffix(".zip"),
            self.book_path.with_name(f"{self.book_path.stem}_x_ray.epub"),
        )
        shutil.rmtree(self.extract_folder)
