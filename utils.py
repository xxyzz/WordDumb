#!/usr/bin/env python3

import json
import pickle
import zipfile
import subprocess
import platform
from pathlib import Path
import sys


def load_json_or_pickle(plugin_path, filepath):
    if not plugin_path:
        if not Path(filepath).exists():
            return None
        if filepath.endswith(".json"):
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        else:
            with open(filepath, "rb") as f:
                return pickle.load(f)

    with zipfile.ZipFile(plugin_path) as zf:
        if filepath.endswith(".json"):
            path = zipfile.Path(zf, filepath)
            if path.exists():
                with path.open() as f:
                    return json.load(f)
            return None
        with zf.open(filepath) as f:
            return pickle.load(f)


def run_subprocess(args):
    if platform.system() == "Windows":
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        return subprocess.run(args, check=True, capture_output=True, text=True)


def homebrew_mac_bin_path(package):
    # stupid macOS loses PATH when calibre is not launched in terminal
    if platform.machine() == "arm64":
        return f"/opt/homebrew/bin/{package}"
    else:
        return f"/usr/local/bin/{package}"


def insert_lib_path(path):
    if path not in sys.path:
        sys.path.insert(0, path)


def insert_flashtext_path(plugin_path):
    insert_lib_path(str(Path(plugin_path).joinpath("libs")))


def load_lemmas_dump(plugin_path):
    insert_flashtext_path(plugin_path)
    lemmas_dump_path = Path(plugin_path).parent.joinpath("worddumb-lemmas/lemmas_dump")
    if lemmas_dump_path.exists():
        return load_json_or_pickle(None, lemmas_dump_path)
    else:
        return load_json_or_pickle(plugin_path, "lemmas_dump")
