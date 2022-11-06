#!/usr/bin/env python3

import platform
import re
import shutil
import tarfile

from calibre.constants import ismacos, iswindows

from .utils import (
    CJK_LANGS,
    PROFICIENCY_VERSION,
    custom_lemmas_folder,
    get_plugin_path,
    homebrew_mac_bin_path,
    insert_installed_libs,
    load_json_or_pickle,
    run_subprocess,
)

PLUGINS_PATH = get_plugin_path()


def install_deps(model, book_fmt, notif):
    global PY_PATH, PY_VERSION, LIBS_PATH
    PY_PATH, PY_VERSION = which_python()
    LIBS_PATH = PLUGINS_PATH.parent.joinpath(f"worddumb-libs-py{PY_VERSION}")

    if not LIBS_PATH.exists():
        for old_path in LIBS_PATH.parent.glob("worddumb-libs-py*"):
            shutil.rmtree(old_path)
    if model == "lemminflect":
        install_lemminflect(notif)
    elif model.startswith("wiktionary"):
        install_wiktionary_deps(model, notif)
    else:
        install_x_ray_deps(model, notif)
        install_extra_deps(model, book_fmt, notif)


def which_python():
    py = "python3"
    py_v = ".".join(platform.python_version_tuple()[:2])
    if iswindows:
        py = "py" if shutil.which("py") else "python"
        r = run_subprocess([py, "-c", "import sys; print(sys.maxsize > 2**32)"])
        if r.stdout.strip() != "True":
            raise Exception("32BIT_PYTHON")
    elif ismacos:
        py = mac_python()
        r = run_subprocess(
            [
                py,
                "-c",
                'import platform; print(".".join(platform.python_version_tuple()[:2]))',
            ]
        )
        py_v = r.stdout.strip()
    upgrade_pip(py)
    return py, py_v


def mac_python():
    py = homebrew_mac_bin_path("python3")
    if not shutil.which(py):
        py = "/usr/bin/python3"  # Command Line Tools
    return py


def install_x_ray_deps(model, notif):
    pip_install_pkgs(load_json_or_pickle(PLUGINS_PATH, "data/x_ray_deps.json"), notif)
    spacy_model_version = "3.4.1" if model.startswith("en") else "3.4.0"
    url = f"https://github.com/explosion/spacy-models/releases/download/{model}-{spacy_model_version}/{model}-{spacy_model_version}-py3-none-any.whl"
    pip_install(model, spacy_model_version, url=url, notif=notif)


def pip_install(pkg, pkg_version, url=None, notif=None):
    pattern = f"{pkg.replace('-', '_')}-{pkg_version}*"
    if not any(LIBS_PATH.glob(pattern)):
        if notif:
            notif.put((0, f"Installing {pkg}"))
        args = [
            PY_PATH,
            "-m",
            "pip",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "install",
            "-U",
            "-t",
            LIBS_PATH,
            "--no-deps",
            "--no-user",
            "--python-version",
            PY_VERSION,
        ]
        if url:
            args.append(url)
        elif pkg_version:
            args.append(f"{pkg}=={pkg_version}")
        else:
            args.append(pkg)
        run_subprocess(args)


def pip_install_pkgs(pkgs, notif):
    for pkg, version in pkgs.items():
        pip_install(pkg, version, notif=notif)


def install_extra_deps(model, book_fmt, notif):
    # https://spacy.io/usage/models#languages
    data = load_json_or_pickle(PLUGINS_PATH, "data/extra_deps.json")
    if (lang := model[:2]) in data:
        pip_install_pkgs(data[lang], notif)

    if ismacos:
        from .config import prefs

        if book_fmt == "EPUB" or prefs["fandom"]:
            pip_install_pkgs(data["mac_epub"], notif)
        if platform.machine() == "arm64":
            pip_install_pkgs(data["mac_arm"], notif)


def upgrade_pip(py_path):
    r = run_subprocess(
        [py_path, "-m", "pip", "--version", "--disable-pip-version-check"]
    )
    m = re.match(r"pip (\d+\.\d+)", r.stdout)
    # Upgrade pip if its version is lower than 22.3
    # pip 22.3 introduced the "--python" option
    if m and [int(x) for x in m.group(1).split(".")] < [22, 3]:
        run_subprocess(
            [
                py_path,
                "-m",
                "pip",
                "install",
                "--user",
                "-U",
                "pip",
            ]
        )


def install_lemminflect(notif):
    data = load_json_or_pickle(PLUGINS_PATH, "data/extra_deps.json")
    pip_install_pkgs(data["lemminflect"], notif)


def install_wiktionary_deps(dep_type, notif):
    data = load_json_or_pickle(PLUGINS_PATH, "data/extra_deps.json")
    pip_install_pkgs(data["wiktionary"], notif)
    if dep_type == "wiktionary_cjk":
        pip_install_pkgs(data["wiktionary_cjk"], notif)


def download_wiktionary(
    lemma_lang: str, gloss_lang: str, abort=None, log=None, notifications=None
) -> None:
    install_deps(
        "wiktionary_cjk" if lemma_lang in CJK_LANGS else "wiktionary",
        None,
        notifications,
    )
    insert_installed_libs(get_plugin_path())
    import requests

    filename = f"wiktionary_{lemma_lang}_{gloss_lang}_v{PROFICIENCY_VERSION}.tar.gz"
    url = f"https://github.com/xxyzz/Proficiency/releases/download/v{PROFICIENCY_VERSION}/{filename}"
    extract_folder = custom_lemmas_folder(PLUGINS_PATH)
    if not extract_folder.exists():
        extract_folder.mkdir()
    download_path = extract_folder.joinpath(filename)

    with requests.get(url, stream=True) as r, open(download_path, "wb") as f:
        total_len = int(r.headers.get("content-length", 0))
        chunk_size = 2**20
        total_chunks = total_len // chunk_size + 1
        chunk_count = 0
        for chunk in r.iter_content(chunk_size):
            f.write(chunk)
            if notifications and total_len > 0:
                chunk_count += 1
                notifications.put(
                    (
                        chunk_count / total_chunks,
                        f"Downloading {lemma_lang}_{gloss_lang} Wiktionary file",
                    )
                )

    with tarfile.open(download_path) as tar:
        tar.extractall(extract_folder)

    download_path.unlink()
