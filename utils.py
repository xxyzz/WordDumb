#!/usr/bin/env python3

import json
import pickle
import platform
import subprocess
import sys
import webbrowser
import zipfile
from pathlib import Path

CJK_LANGS = ["zh", "ja", "ko"]
PROFICIENCY_VERSION = "0.2.0"
PROFICIENCY_MAJOR_VERSION = "0"


def load_json_or_pickle(plugin_path, filepath):
    if "_tst_" in str(filepath):
        insert_plugin_libs(get_plugin_path())

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
    from calibre.gui2 import sanitize_env_vars

    with sanitize_env_vars():
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


def insert_plugin_libs(plugin_path):
    insert_lib_path(str(plugin_path.joinpath("libs")))


def load_lemmas_dump(plugin_path, lemma_lang, gloss_lang):
    insert_plugin_libs(plugin_path)
    custom_kindle_dump = custom_kindle_dump_path(plugin_path)
    if lemma_lang:
        file_path = wiktionary_dump_path(plugin_path, lemma_lang, gloss_lang)
        if lemma_lang in CJK_LANGS:
            insert_installed_libs(plugin_path)
            import ahocorasick

            return ahocorasick.load(str(file_path), pickle.loads)
        else:
            return load_json_or_pickle(None, file_path)
    elif custom_kindle_dump.exists():
        return load_json_or_pickle(None, custom_kindle_dump)
    else:
        return load_json_or_pickle(plugin_path, f"data/{custom_kindle_dump.name}")


def get_plugin_path():
    from calibre.utils.config import config_dir

    return Path(config_dir).joinpath("plugins/WordDumb.zip")


def custom_lemmas_folder(plugin_path):
    return plugin_path.parent.joinpath("worddumb-lemmas")


def custom_kindle_dump_path(plugin_path):
    return custom_lemmas_folder(plugin_path).joinpath(
        f"kindle_lemmas_dump_v{PROFICIENCY_MAJOR_VERSION}"
    )


def wiktionary_dump_path(plugin_path, lemma_lang, gloss_lang):
    return custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/wiktionary_{lemma_lang}_{gloss_lang}_dump_v{PROFICIENCY_MAJOR_VERSION}"
    )


def wiktionary_json_path(plugin_path, lemma_lang, gloss_lang):
    return custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/wiktionary_{lemma_lang}_{gloss_lang}_v{PROFICIENCY_MAJOR_VERSION}.json"
    )


def get_klld_path(plugin_path):
    custom_folder = custom_lemmas_folder(plugin_path)
    for path in custom_folder.glob("*.en.klld"):
        return path
    for path in custom_folder.glob("*.en.db"):
        return path
    return None


def donate():
    webbrowser.open("https://liberapay.com/xxyzz/donate")


def get_custom_x_path(book_path):
    if isinstance(book_path, str):
        book_path = Path(book_path)
    return book_path.parent.joinpath("worddumb-custom-x-ray.json")


def load_custom_x_desc(book_path):
    custom_path = get_custom_x_path(book_path)
    if custom_path.exists():
        with custom_path.open(encoding="utf-8") as f:
            return {
                name: (desc, source, omit)
                for name, *_, desc, source, omit in json.load(f)
            }
    else:
        return {}


def get_user_agent():
    from calibre_plugins.worddumb import VERSION

    from .error_dialogs import GITHUB_URL

    return f"WordDumb/{'.'.join(map(str, VERSION))} ({GITHUB_URL})"


def get_lemmas_tst_path(plugin_path: Path, lemma_lang: str, gloss_lemma: str) -> Path:
    if lemma_lang:
        return custom_lemmas_folder(plugin_path).joinpath(
            f"{lemma_lang}/wiktionary_{lemma_lang}_{gloss_lemma}_tst_v{PROFICIENCY_MAJOR_VERSION}"
        )
    else:
        return custom_lemmas_folder(plugin_path).joinpath(
            f"kindle_lemmas_tst_v{PROFICIENCY_MAJOR_VERSION}"
        )
