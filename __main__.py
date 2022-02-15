#!/usr/bin/env python3

'''
Create X-Ray file on macOS: run this script in subprocess to bypass
the ludicrous library validation
'''

import argparse
import json
import sys

from parse_job import create_files

parser = argparse.ArgumentParser()
parser.add_argument('-l', help='create word wise', action='store_true')
parser.add_argument('-s', help='search people', action='store_true')
parser.add_argument('asin')
parser.add_argument('book_path')
parser.add_argument('acr')
parser.add_argument('revision')
parser.add_argument('model')
parser.add_argument('wiki_lang')
parser.add_argument('mobi_codec')
parser.add_argument('plugin_path')
parser.add_argument('version')
parser.add_argument('zh_wiki')
parser.add_argument('fandom')
args = parser.parse_args()

kfx_json = None
mobi_html = None
if args.mobi_codec:
    mobi_html = sys.stdin.read().encode(args.mobi_codec)
else:
    kfx_json = json.load(sys.stdin)

create_files(
    args.l, True, args.asin, args.book_path, args.acr, args.revision,
    args.model, args.wiki_lang, kfx_json, mobi_html, args.mobi_codec,
    args.plugin_path, args.version, args.zh_wiki, args.s, args.fandom, None)
