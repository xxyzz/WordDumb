#!/usr/bin/env python3

import json
import pickle
import platform
import subprocess
import sys
import webbrowser
import zipfile
from pathlib import Path
from typing import Any, TypedDict

CJK_LANGS = ["zh", "ja", "ko"]
PROFICIENCY_VERSION = "0.3.1"
PROFICIENCY_MAJOR_VERSION = "0"


def load_json_or_pickle(plugin_path: Path | None, filepath: str | Path) -> Any:
    if "_tst_" in str(filepath):
        insert_plugin_libs(get_plugin_path())

    if not plugin_path and isinstance(filepath, Path):
        if not filepath.exists():
            return None
        if filepath.name.endswith(".json"):
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        else:
            with open(filepath, "rb") as f:
                return pickle.load(f)
    elif plugin_path and isinstance(filepath, str):
        with zipfile.ZipFile(plugin_path) as zf:
            if filepath.endswith(".json"):
                path = zipfile.Path(zf, filepath)
                if path.exists():
                    with path.open(encoding="utf-8") as f:
                        return json.load(f)
                return None
            with zf.open(filepath) as f:
                return pickle.load(f)


def run_subprocess(
    args: list[str], input_str: str | None = None
) -> subprocess.CompletedProcess[str]:
    from calibre.gui2 import sanitize_env_vars

    with sanitize_env_vars():
        if platform.system() == "Windows":
            return subprocess.run(
                args,
                input=input_str,
                check=True,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore
            )
        else:
            return subprocess.run(
                args, input=input_str, check=True, capture_output=True, text=True
            )


def homebrew_mac_bin_path(package: str) -> str:
    # stupid macOS loses PATH when calibre is not launched in terminal
    if platform.machine() == "arm64":
        return f"/opt/homebrew/bin/{package}"
    else:
        return f"/usr/local/bin/{package}"


def insert_lib_path(path: str) -> None:
    if path not in sys.path:
        sys.path.insert(0, path)


def insert_installed_libs(plugin_path: Path) -> None:
    py_v = ".".join(platform.python_version_tuple()[:2])
    insert_lib_path(str(plugin_path.parent.joinpath(f"worddumb-libs-py{py_v}")))


def insert_plugin_libs(plugin_path: Path) -> None:
    insert_lib_path(str(plugin_path.joinpath("libs")))


def load_lemmas_dump(plugin_path: Path, lemma_lang: str, gloss_lang: str) -> Any:
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


def get_plugin_path() -> Path:
    from calibre.utils.config import config_dir

    return Path(config_dir).joinpath("plugins/WordDumb.zip")


def custom_lemmas_folder(plugin_path: Path) -> Path:
    return plugin_path.parent.joinpath("worddumb-lemmas")


def custom_kindle_dump_path(plugin_path: Path) -> Path:
    return custom_lemmas_folder(plugin_path).joinpath(
        f"kindle_lemmas_dump_v{PROFICIENCY_MAJOR_VERSION}"
    )


def wiktionary_dump_path(plugin_path: Path, lemma_lang: str, gloss_lang: str) -> Path:
    return custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/wiktionary_{lemma_lang}_{gloss_lang}_dump_v{PROFICIENCY_MAJOR_VERSION}"
    )


def wiktionary_json_path(plugin_path: Path, lemma_lang: str, gloss_lang: str) -> Path:
    return custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/wiktionary_{lemma_lang}_{gloss_lang}_v{PROFICIENCY_MAJOR_VERSION}.json"
    )


def get_klld_path(plugin_path: Path) -> Path | None:
    custom_folder = custom_lemmas_folder(plugin_path)
    for path in custom_folder.glob("*.en.klld"):
        return path
    for path in custom_folder.glob("*.en.db"):
        return path
    return None


def donate() -> None:
    webbrowser.open("https://liberapay.com/xxyzz/donate")


def get_user_agent() -> str:
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


class Prefs(TypedDict):
    search_people: bool
    model_size: str
    zh_wiki_variant: str
    fandom: str
    add_locator_map: str
    preferred_formats: list[str]
    use_all_formats: bool
    mal_x_ray_count: int
    en_ipa: str
    zh_ipa: str
    choose_format_manually: bool
    wiktionary_gloss_lang: str
    use_cpu: bool
    cuda: str
