#!/usr/bin/env python3

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.compression.palmdoc import decompress_doc
from calibre.ebooks.mobi import MobiError
from calibre.utils.logging import default_log
from calibre_plugins.worddumb.database import connect_ww_database, \
    create_lang_layer, match_word
import re

def do_job(gui, books, abort, log, notifications):
    ww_conn, ww_cur = connect_ww_database()

    for (book_id, book_fmt, asin, book_path, _) in books:
        ll_conn, ll_cur, ll_file = \
            create_lang_layer(book_id, book_fmt, asin, book_path)
        if ll_conn is None:
            continue

        for (start, lemma) in parse_book(book_path):
            match_word(start, lemma, ll_cur, ww_cur)

        ll_conn.commit()
        ll_conn.close()

    ww_conn.close()

def parse_book(pathtoebook):
    mobiReader = WDMobiReader(pathtoebook, default_log)
    html = mobiReader.extract_text()
    for match_text in re.finditer(b"(?<=>)([^<>]|\s)+?(?=<)", html):
        text = html[match_text.start():match_text.end()]
        if len(text.strip()) == 0:
            continue
        for match_word in re.finditer(b"[a-zA-Z]+", text):
            lemma = text[match_word.start():match_word.end()]
            start = match_text.start() + match_word.start()
            yield (start, lemma.decode('utf-8'))

class WDMobiReader(MobiReader):
    # copied from calibre
    def extract_text(self, offset=1):
        self.log.debug('Extracting text...')
        text_sections = [self.text_section(i) for i in range(offset,
            min(self.book_header.records + offset, len(self.sections)))]

        self.mobi_html = b''

        if self.book_header.compression_type == b'DH':
            huffs = [self.sections[i][0] for i in
                range(self.book_header.huff_offset,
                    self.book_header.huff_offset + self.book_header.huff_number)]
            huff = HuffReader(huffs)
            unpack = huff.unpack

        elif self.book_header.compression_type == b'\x00\x02':
            unpack = decompress_doc

        elif self.book_header.compression_type == b'\x00\x01':
            unpack = lambda x: x
        else:
            raise MobiError('Unknown compression algorithm: %r' % self.book_header.compression_type)
        self.mobi_html = b''.join(map(unpack, text_sections))
        if self.mobi_html.endswith(b'#'):
            self.mobi_html = self.mobi_html[:-1]

        if self.book_header.ancient and b'<html' not in self.mobi_html[:300].lower():
            self.mobi_html = self.mobi_html.replace(b'\r ', b'\n\n ')
        self.mobi_html = self.mobi_html.replace(b'\0', b'')
        if self.book_header.codec == 'cp1252':
            self.mobi_html = self.mobi_html.replace(b'\x1e', b'')  # record separator
            self.mobi_html = self.mobi_html.replace(b'\x02', b'')  # start of text
        return self.mobi_html
