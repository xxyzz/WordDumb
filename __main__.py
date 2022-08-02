#!/usr/bin/env python3

"""
Create X-Ray file on macOS: run this script in subprocess to bypass
the ludicrous library validation
"""

import argparse
import json
import sys
from pathlib import Path

from data.dump_lemmas import dump_lemmas
from data.wiktionary import dump_wiktionary
from parse_job import create_files
from utils import insert_flashtext_path, insert_installed_libs

parser = argparse.ArgumentParser()
parser.add_argument("-l", help="create word wise", action="store_true")
parser.add_argument("-x", help="create x-ray", action="store_true")
parser.add_argument("-s", help="search people", action="store_true")
parser.add_argument("-m", help="add locator map", action="store_true")
parser.add_argument("asin")
parser.add_argument("book_path")  # Wiktionary JSON
parser.add_argument("acr")  # ipa tag
parser.add_argument("revision")
parser.add_argument("model")
parser.add_argument("wiki_lang")
parser.add_argument("mobi_codec")
parser.add_argument("useragent")
parser.add_argument("zh_wiki")
parser.add_argument("fandom")
parser.add_argument("book_fmt")
parser.add_argument("minimal_x_ray_count")
parser.add_argument("plugin_path")
parser.add_argument("dump_path")
args = parser.parse_args()

if args.dump_path:
    plugin_path = Path(args.plugin_path)
    insert_installed_libs(plugin_path)
    if args.wiki_lang:
        dump_wiktionary(args.book_path, args.dump_path, args.wiki_lang, args.acr, None)
    else:
        insert_flashtext_path(plugin_path)
        dump_lemmas(json.load(sys.stdin), args.dump_path)
else:
    kfx_json = None
    mobi_html = None
    if args.book_fmt == "KFX":
        kfx_json = json.load(sys.stdin)
    elif args.book_fmt != "EPUB":
        mobi_html = sys.stdin.read().encode(args.mobi_codec)

    create_files(
        args.l,
        args.x,
        args.asin,
        args.book_path,
        args.acr,
        args.revision,
        args.model,
        args.wiki_lang,
        kfx_json,
        mobi_html,
        args.mobi_codec,
        args.plugin_path,
        args.useragent,
        {
            "search_people": args.s,
            "zh_wiki_variant": args.zh_wiki,
            "fandom": args.fandom,
            "add_locator_map": args.m,
            "minimal_x_ray_count": int(args.minimal_x_ray_count),
        },
        None,
    )
