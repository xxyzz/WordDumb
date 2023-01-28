#!/usr/bin/env python3

"""
Create X-Ray file on macOS: run this script in subprocess to bypass
the ludicrous library validation
"""

import argparse
import json
import sys
from pathlib import Path

from dump_kindle_lemmas import dump_kindle_lemmas
from dump_wiktionary import dump_wiktionary
from parse_job import create_files
from utils import insert_installed_libs, insert_plugin_libs

parser = argparse.ArgumentParser()
parser.add_argument("-l", help="create word wise", action="store_true")
parser.add_argument("-x", help="create x-ray", action="store_true")
parser.add_argument("-s", help="search people", action="store_true")
parser.add_argument("-m", help="add locator map", action="store_true")
parser.add_argument("asin")
parser.add_argument("book_path")  # or Word Wise db path
parser.add_argument("acr")
parser.add_argument("revision")
parser.add_argument("model")
parser.add_argument("wiki_lang")
parser.add_argument("gloss_lang")
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
    insert_installed_libs(Path(args.plugin_path))
    if args.book_fmt == "EPUB":
        dump_wiktionary(args.wiki_lang, Path(args.book_path), Path(args.dump_path))
    else:
        dump_kindle_lemmas(
            args.wiki_lang in ["zh", "ja", "ko"],
            Path(args.book_path),
            Path(args.dump_path),
        )
else:
    kfx_json = None
    mobi_html = b""
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
            "wiktionary_gloss_lang": args.gloss_lang,
        },
        None,
    )
