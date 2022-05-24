#!/usr/bin/env python3

import json
import pickle
import platform
import subprocess
import sys
import webbrowser
import zipfile
from pathlib import Path


def load_json_or_pickle(plugin_path, filepath):
    if not plugin_path:
        if not filepath.exists():
            return None
        if filepath.name.endswith(".json"):
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


def run_subprocess(args, input_str=None):
    if platform.system() == "Windows":
        return subprocess.run(
            args,
            input=input_str,
            check=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        return subprocess.run(
            args, input=input_str, check=True, capture_output=True, text=True
        )


def homebrew_mac_bin_path(package):
    # stupid macOS loses PATH when calibre is not launched in terminal
    if platform.machine() == "arm64":
        return f"/opt/homebrew/bin/{package}"
    else:
        return f"/usr/local/bin/{package}"


def insert_lib_path(path):
    if path not in sys.path:
        sys.path.insert(0, path)


def insert_installed_libs(plugin_path):
    for path in plugin_path.parent.glob("worddumb-libs-py*"):
        insert_lib_path(str(path))


def insert_flashtext_path(plugin_path):
    insert_lib_path(str(plugin_path.joinpath("libs")))


def load_lemmas_dump(plugin_path):
    insert_flashtext_path(plugin_path)
    custom_path = custom_lemmas_dump_path(plugin_path)
    if custom_path.exists():
        return load_json_or_pickle(None, custom_path)
    else:
        return load_json_or_pickle(plugin_path, "lemmas_dump")


def get_plugin_path():
    from calibre.utils.config import config_dir

    return Path(config_dir).joinpath("plugins/WordDumb.zip")


def custom_lemmas_folder(plugin_path):
    return plugin_path.parent.joinpath("worddumb-lemmas")


def custom_lemmas_dump_path(plugin_path):
    return custom_lemmas_folder(plugin_path).joinpath("lemmas_dump")


def get_klld_path(plugin_path):
    custom_folder = custom_lemmas_folder(plugin_path)
    for path in custom_folder.glob("*.klld"):
        return path
    for path in custom_folder.glob("*.db"):
        return path
    return None


def donate():
    webbrowser.open("https://liberapay.com/xxyzz/donate")