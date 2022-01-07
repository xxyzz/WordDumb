#!/usr/bin/env python3

'''
Create X-Ray file on macOS: run this script in subprocess to bypass
the ludicrous library validation
'''

import argparse
import json
from pathlib import Path

from parse_job import create_files

parser = argparse.ArgumentParser()
parser.add_argument('-l', help='create word wise', action='store_true')
parser.add_argument('-x', help='create x-ray', action='store_true')
parser.add_argument('-s', help='search people', action='store_true')
parser.add_argument('asin')
parser.add_argument('book_path')
parser.add_argument('acr')
parser.add_argument('revision')
parser.add_argument('model')
parser.add_argument('wiki_lang')
parser.add_argument('extract_file')
parser.add_argument('mobi_codec')
parser.add_argument('plugin_path')
parser.add_argument('version')
parser.add_argument('zh_wiki')
args = parser.parse_args()

kfx_json = None
mobi_html = None
if args.mobi_codec:
    with open(args.extract_file, 'rb') as f:
        mobi_html = f.read()
else:
    with open(args.extract_file) as f:
        kfx_json = json.load(f)

create_files(
    args.l, args.x, args.asin, args.book_path, args.acr, args.revision,
    args.model, args.wiki_lang, kfx_json, mobi_html, args.mobi_codec,
    args.plugin_path, args.version, args.zh_wiki, args.s)
Path(args.extract_file).unlink()
