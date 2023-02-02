#!/usr/bin/env python3

"""
Create X-Ray file on macOS: run this script in subprocess to bypass
the ludicrous library validation
"""

import argparse
import json
import sys
from pathlib import Path

from dump_lemmas import dump_kindle_lemmas, dump_wiktionary
from parse_job import create_files

parser = argparse.ArgumentParser()
parser.add_argument("options")
parser.add_argument("prefs")
args = parser.parse_args()

options = json.loads(args.options)
prefs = json.loads(args.prefs)
if "dump_path" in options:
    plugin_path = Path(options["plugin_path"])
    if options["is_kindle"]:
        dump_kindle_lemmas(
            options["lemma_lang"],
            Path(options["db_path"]),
            Path(options["dump_path"]),
            plugin_path,
        )
    else:
        dump_wiktionary(
            options["lemma_lang"],
            Path(options["db_path"]),
            Path(options["dump_path"]),
            plugin_path,
            prefs
        )
else:
    kfx_json = None
    mobi_html = b""
    if options["book_fmt"] == "KFX":
        kfx_json = json.load(sys.stdin)
    elif options["book_fmt"] != "EPUB":
        mobi_html = sys.stdin.buffer.read()

    create_files(
        options["create_ww"],
        options["create_x"],
        options["asin"],
        options["book_path"],
        options["acr"],
        options["revision"],
        options["model"],
        options["lemma_lang"],
        kfx_json,
        mobi_html,
        options["mobi_codec"],
        options["plugin_path"],
        options["useragent"],
        prefs,
        None,
    )
