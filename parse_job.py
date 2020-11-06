#!/usr/bin/env python3

from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.compression.palmdoc import decompress_doc
from calibre.ebooks.mobi import MobiError
from calibre.utils.logging import default_log
from pathlib import Path
import sqlite3
import re

def parse_job(books):
    ww_conn = sqlite3.connect(":memory:")
    ww_cur = ww_conn.cursor()
    with open(Path("data/wordwise.sql")) as f:
        ww_cur.executescript(f.read())

    for (book_id, book_fmt, asin, book_path) in books:
        ll_conn, ll_cur = create_lang_layer(book_id, book_fmt, asin, book_path)
        if ll_conn is None:
            continue

        for (start, lemma) in parse_book(book_path):
            match_word(start, lemma, ll_cur, ww_cur)

        ll_conn.commit()
        ll_conn.close()

    ww_conn.close()

def create_lang_layer(book_id, book_fmt, asin, book_path):
    # check LanguageLayer file
    book_path = Path(book_path)
    lang_layer_path = book_path.parent
    folder_name = book_path.stem + ".sdr"
    lang_layer_path = lang_layer_path.joinpath(folder_name)
    lang_layer_name = "LanguageLayer.en.{}.kll".format(asin)
    lang_layer_path = lang_layer_path.joinpath(lang_layer_name)
    if lang_layer_path.is_file():
        return None, None

    # create LanguageLayer database file
    lang_layer_path.parent.mkdir(exist_ok=True)
    lang_layer_path.touch()
    ll_conn = sqlite3.connect(lang_layer_path)
    ll_cur = ll_conn.cursor()
    ll_cur.executescript('''
        CREATE TABLE metadata (
            key TEXT,
            value TEXT
        );

        CREATE TABLE glosses (
            start INTEGER,
            end INTEGER,
            difficulty INTEGER,
            sense_id INTEGER,
            low_confidence INTEGER
        );
    ''' )
    metadata = [('acr', 'CR!AX4P53SCH15WF68KNBX4NWWVZXKG'), # Palm DB name
                ('targetLanguages', 'en'),
                ('sidecarRevision', '9'),
                ('bookRevision', '8d271dc3'),
                ('sourceLanguage', 'en'),
                ('enDictionaryVersion', '2016-09-14'),
                ('enDictionaryRevision', '57'),
                ('enDictionaryId', 'kll.en.en'),
                ('sidecarFormat', '1.0')]
    ll_cur.executemany('INSERT INTO metadata VALUES (?, ?)', metadata)

    return ll_conn, ll_cur

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

def match_word(start, lemma, ll_cur, ww_cur):
    ww_cur.execute("SELECT * FROM words WHERE lemma = ?", (lemma.lower(), ))
    result = ww_cur.fetchone()
    if result is not None:
        (_, sense_id, difficulty) = result
        ll_cur.execute('''
            INSERT INTO glosses (start, difficulty, sense_id, low_confidence)
            VALUES (?, ?, ?, ?)
        ''', (start, difficulty, sense_id, 0))

class WDMobiReader(MobiReader):
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
