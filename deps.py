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

PY_PATH = None
LIBS_PATH = None
RUNNABLE_PIP = None


def install_deps(model, book_fmt, notif):
    global PY_PATH, LIBS_PATH, CALIBRE_DEBUG_PATH, RUNNABLE_PIP
    plugin_path = get_plugin_path()

    if PY_PATH is None:
        PY_PATH, py_version = which_python()
        upgrade_pip(PY_PATH)
        LIBS_PATH = plugin_path.parent.joinpath(f"worddumb-libs-py{py_version}")
        if not ismacos:
            RUNNABLE_PIP = get_runnable_pip(PY_PATH)

    if not LIBS_PATH.exists():
        for old_path in LIBS_PATH.parent.glob("worddumb-libs-py*"):
            shutil.rmtree(old_path)

    dep_versions = load_json_or_pickle(plugin_path, "data/deps.json")
    if model == "lemminflect":
        pip_install("lemminflect", dep_versions["lemminflect"], notif=notif)
    elif model.startswith("wiktionary"):
        pip_install("requests", dep_versions["requests"], notif=notif)
        if model == "wiktionary_cjk":
            pip_install("pyahocorasick", dep_versions["pyahocorasick"], notif=notif)
    else:
        # Install X-Ray dependencies
        pip_install("rapidfuzz", dep_versions["rapidfuzz"], notif=notif)

        spacy_model_version = "3.4.1" if model.startswith("en") else "3.4.0"
        url = f"https://github.com/explosion/spacy-models/releases/download/{model}-{spacy_model_version}/{model}-{spacy_model_version}-py3-none-any.whl"
        pip_install(model, spacy_model_version, url=url, notif=notif)
        if model.endswith("_trf"):
            pip_install("cupy-wheel", dep_versions["cupy-wheel"], notif=notif)

        if ismacos:
            if platform.machine() == "arm64":
                pip_install(
                    "thinc-apple-ops", dep_versions["thinc-apple-ops"], notif=notif
                )
            if book_fmt == "EPUB":
                pip_install("lxml", dep_versions["lxml"], notif=notif)


def which_python():
    py = "python3"
    py_v = ".".join(platform.python_version_tuple()[:2])
    if iswindows:
        py = "py" if shutil.which("py") else "python"
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
    return py, py_v


def mac_python():
    py = homebrew_mac_bin_path("python3")
    if not shutil.which(py):
        py = "/usr/bin/python3"  # Command Line Tools
    return py


def get_runnable_pip(py_path):
    r = run_subprocess(
        [py_path, "-m", "pip", "--version", "--disable-pip-version-check"]
    )
    # pip "--python" option
    # https://github.com/pypa/pip/blob/6d131137cf7aa8c1c64f1fadca4770879e9f407f/src/pip/_internal/cli/main_parser.py#L82-L105
    # https://github.com/pypa/pip/blob/6d131137cf7aa8c1c64f1fadca4770879e9f407f/src/pip/_internal/build_env.py#L43-L56
    return r.stdout.split()[3] + "/__pip-runner__.py"


def pip_install(pkg, pkg_version, url=None, notif=None):
    pattern = f"{pkg.replace('-', '_')}-{pkg_version}*"
    if not any(LIBS_PATH.glob(pattern)):
        if notif:
            notif.put((0, f"Installing {pkg}"))

        if ismacos:
            args = [PY_PATH, "-m", "pip"]
        else:
            args = ["calibre-debug", "-e", RUNNABLE_PIP, "--"]
        args.extend(
            [
                "--disable-pip-version-check",
                "install",
                "-U",
                "-t",
                LIBS_PATH,
                "--no-user",  # disable "--user" option which conflicts with "-t"
            ]
        )

        if url:
            args.append(url)
        elif pkg_version:
            args.append(f"{pkg}=={pkg_version}")
        else:
            args.append(pkg)
        run_subprocess(args)


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


def download_wiktionary(
    lemma_lang: str, gloss_lang: str, abort=None, log=None, notifications=None
) -> None:
    plugin_path = get_plugin_path()
    install_deps(
        "wiktionary_cjk" if lemma_lang in CJK_LANGS else "wiktionary",
        None,
        notifications,
    )
    insert_installed_libs(plugin_path)
    import requests

    filename = f"wiktionary_{lemma_lang}_{gloss_lang}_v{PROFICIENCY_VERSION}.tar.gz"
    url = f"https://github.com/xxyzz/Proficiency/releases/download/v{PROFICIENCY_VERSION}/{filename}"
    extract_folder = custom_lemmas_folder(plugin_path)
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
