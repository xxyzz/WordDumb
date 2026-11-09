import shutil
import tarfile
from pathlib import Path
from typing import Any
from urllib.request import ProxyHandler, build_opener, getproxies

from calibre.constants import ismacos

from .utils import (
    PROFICIENCY_RELEASE_URL,
    Prefs,
    custom_lemmas_folder,
    get_plugin_path,
    get_spacy_model_version,
    get_user_agent,
    load_plugin_json,
    mac_bin_path,
    run_subprocess,
)

PYTHON_VERSION = "3.15"


class DownloadException(Exception):
    pass


def install_deps(model_name: str, notif: Any) -> None:
    plugin_path = get_plugin_path()
    uv_path = which_uv()
    libs_path = plugin_path.parent.joinpath(f"worddumb-libs-py{PYTHON_VERSION}")
    if not libs_path.is_dir():
        for old_libs_path in libs_path.parent.glob("worddumb-libs-py*"):
            shutil.rmtree(old_libs_path)

    run_subprocess([uv_path, "python", "install", PYTHON_VERSION])
    dep_versions = load_plugin_json(plugin_path, "data/deps.json")
    for pkg, pkg_v in dep_versions.items():
        if pkg != "spacy_cpu_model":
            pip_install(uv_path, libs_path, pkg, pkg_v, notif=notif)
    model_version = get_spacy_model_version(pkg, dep_versions)
    url = (
        "https://github.com/explosion/spacy-models/releases/download/"
        f"{model_name}-{model_version}/{model_name}-{model_version}-py3-none-any.whl"
    )
    pip_install(uv_path, libs_path, "", model_version, url=url, notif=notif)


def which_uv() -> str:
    uv = "uv"
    if ismacos:
        uv = mac_bin_path("uv")
    if shutil.which(uv) is None:
        raise FileNotFoundError("UvNotFound")
    return uv


def pip_install(
    uv_path: str,
    libs_path: str,
    pkg: str,
    pkg_version: str,
    url: str | None = None,
    extra_index: str | None = None,
    no_deps: bool = False,
    notif: Any = None,
) -> None:
    if notif:
        notif.put((0, f"Installing {pkg}"))
    args = [
        uv_path,
        "pip",
        "install",
        "-t",
        libs_path,
        "--python-version",
        PYTHON_VERSION,
    ]
    if no_deps:
        args.append("--no-deps")
    if url:
        args.append(url)
    elif pkg_version:
        args.append(f"{pkg}=={pkg_version}")
    else:
        args.append(pkg)
    if extra_index is not None:
        args.extend(["--extra-index-url", extra_index])
    run_subprocess(args)


def download_word_wise_file(
    is_kindle: bool,
    lemma_lang: str,
    prefs: Prefs,
    abort=None,
    log=None,
    notifications=None,
) -> None:
    gloss_lang = prefs["gloss_lang"]
    if notifications:
        notifications.put(
            (
                0,
                f"Downloading {lemma_lang}-{gloss_lang} {'Kindle' if is_kindle else 'Wiktionary'} file",
            )
        )
    plugin_path = get_plugin_path()
    bz2_filename = f"{lemma_lang}_{gloss_lang}.tar.bz2"
    url = f"{PROFICIENCY_RELEASE_URL}/{bz2_filename}"
    download_folder = custom_lemmas_folder(plugin_path)
    if not download_folder.is_dir():
        download_folder.mkdir()
    checksum = download_checksum()
    download_path = download_folder / bz2_filename
    download_extract_bz2(url, download_path, checksum.get(bz2_filename, ""))


def download_extract_bz2(url: str, download_path: Path, sha256: str) -> None:
    download_file(url, download_path, sha256)
    with tarfile.open(name=download_path, mode="r:bz2") as tar_f:
        tar_f.extractall(download_path.parent)
    download_path.unlink()


def download_checksum() -> dict[str, str]:
    import json

    opener = build_opener(ProxyHandler(getproxies()))
    opener.addheaders = [("User-agent", get_user_agent())]
    with opener.open(f"{PROFICIENCY_RELEASE_URL}/sha256.json") as r:
        return json.load(r)


def download_file(
    url: str, download_path: Path, sha256: str, range: int = 0, retry: int = 10
):
    import hashlib

    opener = build_opener(ProxyHandler(getproxies()))
    headers = [("User-agent", get_user_agent())]
    if range > 0:
        headers.append(("Range", f"bytes={range}-"))
    opener.addheaders = headers
    saved_bytes = 0
    content_length = 0
    with opener.open(url) as r, open(download_path, "wb" if range == 0 else "ab") as f:
        shutil.copyfileobj(r, f)
        saved_bytes = f.tell()
        content_length = int(r.headers.get("content-length"))

    if saved_bytes < content_length + range:
        if retry == 1:
            download_path.unlink()
            raise DownloadException("DownloadFailed")
        else:
            download_file(url, download_path, sha256, saved_bytes, retry - 1)
    else:
        with download_path.open("rb", buffering=0) as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != sha256:
                download_path.unlink()
                if retry == 1:
                    raise DownloadException("DownloadFailed")
                else:
                    download_file(url, download_path, sha256, retry=retry - 1)


def download_wikipedia_titles_db(db_path: Path, notifications=None):
    import bz2

    if notifications:
        notifications.put((0, "Downloading Wikipedia titles db"))
    checksum = download_checksum()
    bz2_path = db_path.with_name(db_path.name + ".bz2")
    if not bz2_path.parent.is_dir():
        bz2_path.parent.mkdir()
    download_file(
        f"{PROFICIENCY_RELEASE_URL}/{bz2_path.name}",
        bz2_path,
        checksum.get(bz2_path.name, ""),
    )
    with bz2.open(bz2_path, "rb") as in_f, db_path.open("wb") as out_f:
        shutil.copyfileobj(in_f, out_f)
    bz2_path.unlink()
