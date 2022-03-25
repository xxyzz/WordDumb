#!/usr/bin/env python3

import re
import shutil
import zipfile
from collections import defaultdict
from html import escape
from pathlib import Path

try:
    from .mediawiki import MEDIAWIKI_API_EXLIMIT, FUZZ_THRESHOLD
except ImportError:
    from mediawiki import MEDIAWIKI_API_EXLIMIT, FUZZ_THRESHOLD


NAMESPACES = {
    'n': 'urn:oasis:names:tc:opendocument:xmlns:container',
    'opf': 'http://www.idpf.org/2007/opf',
    'ops': 'http://www.idpf.org/2007/ops',
    'xml': 'http://www.w3.org/1999/xhtml'
}


class X_Ray_EPUB:
    def __init__(self, book_path, search_people, mediawiki, wiki_commons):
        self.book_path = book_path
        self.search_people = search_people
        self.mediawiki = mediawiki
        self.num_ents = 0
        self.ent_dic = defaultdict(list)
        self.entities = {}
        self.pending_dic = {}
        self.extract_folder = Path(book_path).with_name('extract')
        if self.extract_folder.exists():
            shutil.rmtree(self.extract_folder)
        self.xhtml_folder = self.extract_folder
        self.xhtml_href_has_folder = False
        self.wikimedia_commons = wiki_commons
        self.image_folder = self.extract_folder
        self.image_href_has_folder = False

    def extract_epub(self):
        from lxml import etree

        with zipfile.ZipFile(self.book_path) as zf:
            zf.extractall(self.extract_folder)

        with self.extract_folder.joinpath(
                'META-INF/container.xml').open('rb') as f:
            root = etree.fromstring(f.read())
            opf_path = root.find(
                './/n:rootfile', NAMESPACES).get("full-path")
            self.opf_path = self.extract_folder.joinpath(opf_path)
            if not self.opf_path.exists():
                self.opf_path = next(self.extract_folder.rglob(opf_path))
        with self.opf_path.open('rb') as opf:
            self.opf_root = etree.fromstring(opf.read())
            item_path = 'opf:manifest/opf:item' \
                '[starts-with(@media-type, "image/")]'
            for item in self.opf_root.xpath(item_path, namespaces=NAMESPACES):
                image = item.get("href")
                image_path = self.extract_folder.joinpath(image)
                if not image_path.exists():
                    image_path = next(self.extract_folder.rglob(image))
                if not image_path.parent.samefile(self.extract_folder):
                    self.image_folder = image_path.parent
                if '/' in image:
                    self.image_href_has_folder = True
                    break

            item_path = 'opf:manifest/opf:item' \
                '[@media-type="application/xhtml+xml"]'
            for item in self.opf_root.iterfind(item_path, NAMESPACES):
                if item.get('properties') == 'nav':
                    continue
                xhtml = item.get("href")
                xhtml_path = self.extract_folder.joinpath(xhtml)
                if not xhtml_path.exists():
                    xhtml_path = next(self.extract_folder.rglob(xhtml))
                if not xhtml_path.parent.samefile(self.extract_folder):
                    self.xhtml_folder = xhtml_path.parent
                if '/' in xhtml:
                    self.xhtml_href_has_folder = True
                with xhtml_path.open() as f:
                    xhtml_str = f.read()
                    body_start = xhtml_str.index('<body')
                    body_end = xhtml_str.index('</body>') + len('</body>')
                    body_str = xhtml_str[body_start:body_end]
                    for m in re.finditer(r'>[^<]+<', body_str):
                        yield (m.group(0)[1:-1], (m.start() + 1, xhtml_path))

    def search(self, name, is_person, sent, start, end, xhtml_path):
        from rapidfuzz.process import extractOne

        if (r := extractOne(
                name, self.entities.keys(), score_cutoff=FUZZ_THRESHOLD)):
            ent_id = self.entities[r[0]]['id']
        else:
            ent_id = self.num_ents
            self.num_ents += 1
            self.entities[name] = {
                'id': ent_id, 'summary': sent, 'quote': True}
            if not is_person or self.search_people:
                if name in self.mediawiki.cache_dic:
                    if (cached_summary := self.mediawiki.cache_dic[name]):
                        self.update_summary(name, cached_summary)
                else:
                    self.pending_dic[name] = None
                    if len(self.pending_dic) == MEDIAWIKI_API_EXLIMIT:
                        self.mediawiki.query(
                            self.pending_dic, self.update_summary)
                        self.pending_dic.clear()

        self.ent_dic[xhtml_path].append((start, end, name, ent_id))

    def update_summary(self, key, summary):
        self.entities[key]['summary'] = summary
        self.entities[key]['quote'] = False

    def modify_epub(self):
        if len(self.pending_dic):
            self.mediawiki.query(self.pending_dic, self.update_summary)
        self.insert_anchor_elements()
        self.create_x_ray_page()
        self.mediawiki.save_cache()

    def insert_anchor_elements(self):
        for xhtml_path, ent_list in self.ent_dic.items():
            with xhtml_path.open() as f:
                xhtml_str = f.read()
                body_start = xhtml_str.index('<body')
                body_end = xhtml_str.index('</body>') + len('</body>')
                body_str = xhtml_str[body_start:body_end]
            s = ''
            last_end = 0
            for data in ent_list:
                start, end, name, ent_id = data
                s += body_str[last_end:start]
                s += f'<a epub:type="noteref" href="x_ray.xhtml#{ent_id}">'
                s += f'{name}</a>'
                last_end = end
            s += body_str[last_end:]
            new_xhtml_str = xhtml_str[:body_start] + s + xhtml_str[body_end:]

            with xhtml_path.open('w') as f:
                if NAMESPACES['ops'] not in new_xhtml_str:
                    # add epub namespace
                    new_xhtml_str = new_xhtml_str.replace(
                        f'xmlns="{NAMESPACES["xml"]}"',
                        f'xmlns="{NAMESPACES["xml"]}" '
                        f'xmlns:epub="{NAMESPACES["ops"]}"')
                f.write(new_xhtml_str)

    def create_x_ray_page(self):
        from lxml import etree

        images = set()
        image_prefix = ''
        if self.xhtml_href_has_folder:
            image_prefix += '../'
        if self.image_href_has_folder:
            image_prefix += f'{self.image_folder.name}/'
        s = '''
        <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:epub="http://www.idpf.org/2007/ops"
        lang="en-US" xml:lang="en-US">
        <head><title>X-Ray</title><meta charset="utf-8"/></head>
        <body>
        '''
        for entity, data in self.entities.items():
            s += f'''
            <aside id="{data["id"]}" epub:type="footnote">
            {escape(data["summary"])}
            '''
            if not data['quote']:
                s += f'''
                <a href="{self.mediawiki.source_link}{entity}">
                {self.mediawiki.source_name}</a>
                '''
            if not data['quote'] and (
                    result := self.wikimedia_commons.get_image(entity)):
                filename, file_path = result
                s += f'''
                <img style="max-width:100%" src="{image_prefix}{filename}" />
                <a href="{self.wikimedia_commons.source_url}{filename}">
                Wikimedia Commons</a>
                '''
                shutil.copy(file_path, self.image_folder.joinpath(filename))
                images.add(filename)
            s += '</aside>'
        s += '</body></html>'
        self.wikimedia_commons.close_session()
        with self.xhtml_folder.joinpath('x_ray.xhtml').open('w') as f:
            f.write(s)

        xhtml_prefix = ''
        image_prefix = ''
        if self.xhtml_href_has_folder:
            xhtml_prefix = f'{self.xhtml_folder.name}/'
        if self.image_href_has_folder:
            image_prefix = f'{self.image_folder.name}/'
        s = f'<item href="{xhtml_prefix}x_ray.xhtml" id="x_ray.xhtml" ' \
            'media-type="application/xhtml+xml"/>'
        manifest = self.opf_root.find('opf:manifest', NAMESPACES)
        manifest.append(etree.fromstring(s))
        for image_name in images:
            s = f'<item href="{image_prefix}{image_name}" id="{image_name}" '\
                'media-type="image/svg+xml"/>'
            manifest.append(etree.fromstring(s))
        spine = self.opf_root.find('opf:spine', NAMESPACES)
        s = '<itemref idref="x_ray.xhtml"/>'
        spine.append(etree.fromstring(s))
        with self.opf_path.open('w') as f:
            f.write(etree.tostring(self.opf_root, encoding=str))

        self.book_path = Path(self.book_path)
        shutil.make_archive(self.extract_folder, 'zip', self.extract_folder)
        shutil.move(
            self.extract_folder.with_suffix('.zip'),
            self.book_path.with_name(f'{self.book_path.stem}_x_ray.epub'))
        shutil.rmtree(self.extract_folder)
