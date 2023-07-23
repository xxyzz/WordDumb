#!/usr/bin/env python3

import json
import platform
import shutil
import subprocess
import sys
import webbrowser
import zipfile

from pathlib import Path
from typing import Any, TypedDict

CJK_LANGS = ["zh", "ja", "ko"]
PROFICIENCY_VERSION = "0.5.8"
PROFICIENCY_RELEASE_URL = (
    f"https://github.com/xxyzz/Proficiency/releases/download/v{PROFICIENCY_VERSION}"
)
PROFICIENCY_MAJOR_VERSION = PROFICIENCY_VERSION.split(".", 1)[0]


class Prefs(TypedDict):
    use_pos: bool
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
    kindle_gloss_lang: str
    use_gpu: bool
    cuda: str
    last_opened_kindle_lemmas_language: str
    last_opened_wiktionary_lemmas_language: str
    use_wiktionary_for_kindle: bool


def load_plugin_json(plugin_path: Path, filepath: str) -> Any:
    with zipfile.ZipFile(plugin_path) as zf:
        with zipfile.Path(zf, filepath).open(encoding="utf-8") as f:
            return json.load(f)


def run_subprocess(
    args: list[str], input_str: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    from calibre.gui2 import sanitize_env_vars

    with sanitize_env_vars():
        return subprocess.run(
            args,
            input=input_str,
            check=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,  # type: ignore
        )


def mac_bin_path(command: str) -> str:
    # stupid macOS loses PATH when calibre is not launched from terminal
    # search homebrew binary path first
    if platform.machine() == "arm64":
        bin_path = f"/opt/homebrew/bin/{command}"
    else:
        bin_path = f"/usr/local/bin/{command}"

    if (
        shutil.which(bin_path) is None
        and (env_bin_path := shutil.which(command)) is not None
    ):
        # assume PATH is not empty
        return env_bin_path
    return bin_path


def insert_lib_path(path: str) -> None:
    if path not in sys.path:
        sys.path.insert(0, path)


def insert_installed_libs(plugin_path: Path) -> None:
    py_v = ".".join(platform.python_version_tuple()[:2])
    insert_lib_path(str(plugin_path.parent.joinpath(f"worddumb-libs-py{py_v}")))


def get_plugin_path() -> Path:
    from calibre.utils.config import config_dir

    return Path(config_dir).joinpath("plugins/WordDumb.zip")


def custom_lemmas_folder(plugin_path: Path) -> Path:
    return plugin_path.parent.joinpath("worddumb-lemmas")


def use_kindle_ww_db(lemma_lang: str, prefs: Prefs) -> bool:
    return (
        lemma_lang == "en"
        and prefs["kindle_gloss_lang"]
        in [
            "en",
            "zh",
            "zh_cn",
        ]
        and not prefs["use_wiktionary_for_kindle"]
    )


def kindle_db_path(plugin_path: Path, lemma_lang: str, prefs: Prefs) -> Path:
    if use_kindle_ww_db(lemma_lang, prefs):
        return custom_lemmas_folder(plugin_path).joinpath(
            f"{lemma_lang}/kindle_en_en_v{PROFICIENCY_MAJOR_VERSION}.db"
        )
    else:
        return wiktionary_db_path(plugin_path, lemma_lang, prefs["kindle_gloss_lang"])


def wiktionary_db_path(plugin_path: Path, lemma_lang: str, gloss_lang: str) -> Path:
    return custom_lemmas_folder(plugin_path).joinpath(
        f"{lemma_lang}/wiktionary_{lemma_lang}_{gloss_lang}_v{PROFICIENCY_MAJOR_VERSION}.db"
    )


def get_klld_path(plugin_path: Path) -> Path | None:
    custom_folder = custom_lemmas_folder(plugin_path)
    for path in custom_folder.glob("*.en.klld"):
        return path
    for path in custom_folder.glob("*.en.db"):
        return path
    return None


def get_wiktionary_klld_path(
    plugin_path: Path, lemma_lang: str, gloss_lang: str
) -> Path:
    custom_folder = custom_lemmas_folder(plugin_path)
    return custom_folder.joinpath(
        f"{lemma_lang}/kll.{lemma_lang}.{gloss_lang}_v{PROFICIENCY_MAJOR_VERSION}.klld"
    )


def donate() -> None:
    webbrowser.open("https://liberapay.com/xxyzz/donate")


def get_user_agent() -> str:
    from calibre_plugins.worddumb import VERSION

    from .error_dialogs import GITHUB_URL

    return f"WordDumb/{'.'.join(map(str, VERSION))} ({GITHUB_URL})"


def dump_prefs(prefs: Any) -> str:
    prefs_dict = prefs.defaults
    prefs_dict.update(prefs)
    return json.dumps(prefs_dict)


def spacy_model_name(
    lemma_lang: str, languages: dict[str, dict[str, str]], prefs: Prefs
) -> str:
    spacy_model = languages[lemma_lang]["spacy"]
    if prefs["use_gpu"] and languages[lemma_lang]["has_trf"]:
        spacy_model += "trf"
    else:
        spacy_model += prefs["model_size"]
    return spacy_model


def load_languages_data(
    plugin_path: Path,
) -> dict[str, dict[str, str | bool | list[str]]]:
    """
    Add Simplified Chinese `zh_cn` key to languages dict
    """
    supported_languages = load_plugin_json(plugin_path, "data/languages.json")
    supported_languages["zh_cn"] = supported_languages["zh"].copy()
    supported_languages["zh_cn"]["name"] = "Simplified Chinese"
    return supported_languages
