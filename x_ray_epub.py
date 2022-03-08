#!/usr/bin/env python3

import re
import shutil
import zipfile
from collections import defaultdict
from html import escape
from pathlib import Path

try:
    from .mediawiki import MAX_EXLIMIT, SCORE_THRESHOLD
except ImportError:
    from mediawiki import MAX_EXLIMIT, SCORE_THRESHOLD


NAMESPACES = {
    'n': 'urn:oasis:names:tc:opendocument:xmlns:container',
    'opf': 'http://www.idpf.org/2007/opf',
    'ops': 'http://www.idpf.org/2007/ops',
    None: 'http://www.w3.org/1999/xhtml'
}


class X_Ray_EPUB:
    def __init__(self, book_path, search_people, mediawiki):
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
        self.content_folder = None
        self.xhtml_folder = None

    def extract_epub(self):
        from lxml import etree

        with zipfile.ZipFile(self.book_path) as zf:
            zf.extractall(self.extract_folder)

        with self.extract_folder.joinpath(
                'META-INF/container.xml').open('rb') as f:
            root = etree.fromstring(f.read())
            self.opf_path = root.find(
                './/n:rootfile', NAMESPACES).get("full-path")
            content_folder = Path(self.opf_path).parent.name
            if content_folder:
                self.content_folder = content_folder
            elif self.extract_folder.joinpath('OEBPS').is_dir():
                self.content_folder = 'OEBPS'
            elif self.extract_folder.joinpath('epub').is_dir():
                self.content_folder = 'epub'
        with self.extract_folder.joinpath(self.opf_path).open('rb') as opf:
            self.opf_root = etree.fromstring(opf.read())
            item_path = 'opf:manifest/opf:item' \
                '[@media-type="application/xhtml+xml"]'
            for item in self.opf_root.findall(item_path, NAMESPACES):
                xhtml = item.get("href")
                xhtml_folder = Path(xhtml).parent.name
                if xhtml_folder and xhtml_folder != self.xhtml_folder \
                   and xhtml_folder != self.content_folder:
                    self.xhtml_folder = xhtml_folder
                if not xhtml.startswith(self.content_folder):
                    xhtml = f'{self.content_folder}/{xhtml}'
                xhtml_path = self.extract_folder.joinpath(xhtml)
                if xhtml_path.exists():
                    with xhtml_path.open() as f:
                        xhtml_str = f.read()
                        body_start = xhtml_str.index('<body')
                        body_end = xhtml_str.index('</body>') + len('</body>')
                        body_str = xhtml_str[body_start:body_end]
                        for m in re.finditer(r'>[^<]+<', body_str):
                            yield (m.group(0)[1:-1], (m.start() + 1, xhtml))

    def search(self, name, is_person, sent, start, end, xhtml):
        from rapidfuzz.process import extractOne

        if (r := extractOne(
                name, self.entities.keys(), score_cutoff=SCORE_THRESHOLD)):
            ent_id = self.entities[r[0]]['id']
        else:
            ent_id = self.num_ents
            self.num_ents += 1
            self.entities[name] = {
                'id': ent_id, 'summary': sent, 'quote': True}
            if is_person and not self.search_people:
                return
            if name in self.mediawiki.cache_dic and \
               self.mediawiki.cache_dic[name]:
                self.update_summary(name, self.mediawiki.cache_dic[name])
            else:
                self.pending_dic[name] = None
                if len(self.pending_dic) == MAX_EXLIMIT:
                    self.mediawiki.query(self.pending_dic, self.update_summary)
                    self.pending_dic.clear()

        self.ent_dic[xhtml].append((start, end, name, ent_id))

    def update_summary(self, key, summary):
        self.entities[key]['summary'] = summary
        self.entities[key]['quote'] = False

    def modify_epub(self):
        self.insert_a_tags()
        self.create_x_ray_page()
        self.mediawiki.save_cache()

    def insert_a_tags(self):
        for xhtml, ent_list in self.ent_dic.items():
            with self.extract_folder.joinpath(xhtml).open() as f:
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

            with self.extract_folder.joinpath(xhtml).open('w') as f:
                if NAMESPACES['ops'] not in new_xhtml_str:
                    # add epub namespace
                    new_xhtml_str = new_xhtml_str.replace(
                        f'xmlns="{NAMESPACES[None]}"',
                        f'xmlns="{NAMESPACES[None]}" '
                        f'xmlns:epub="{NAMESPACES["ops"]}"')
                f.write(new_xhtml_str)

    def create_x_ray_page(self):
        from lxml import etree

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
            s += '</aside>'

        s += '</body></html>'

        if self.xhtml_folder:
            x_ray_href = f'{self.xhtml_folder}/x_ray.xhtml'
            x_ray_path = self.extract_folder.joinpath(
                f'{self.content_folder}/{x_ray_href}')
        else:
            x_ray_href = f'{self.content_folder}/x_ray.xhtml'
            x_ray_path = self.extract_folder.joinpath(x_ray_href)

        with x_ray_path.open('w') as f:
            f.write(s)

        manifest = self.opf_root.find('opf:manifest', NAMESPACES)
        s = f'<item href="{x_ray_href}" id="x_ray.xhtml" '\
            'media-type="application/xhtml+xml"/>'
        manifest.append(etree.fromstring(s))
        spine = self.opf_root.find('opf:spine', NAMESPACES)
        s = '<itemref idref="x_ray.xhtml"/>'
        spine.append(etree.fromstring(s))

        with self.extract_folder.joinpath(self.opf_path).open('w') as f:
            f.write(etree.tostring(self.opf_root, encoding=str))

        self.book_path = Path(self.book_path)
        shutil.make_archive(self.extract_folder, 'zip', self.extract_folder)
        shutil.move(
            self.extract_folder.with_suffix('.zip'),
            self.book_path.with_name(f'{self.book_path.stem}_x_ray.epub'))
        shutil.rmtree(self.extract_folder)
