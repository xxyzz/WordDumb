#!/usr/bin/env python3

import platform
import re
import shutil
import tarfile
from io import BytesIO
from urllib.request import urlopen

from calibre.constants import isfrozen, ismacos, iswindows

from .utils import (
    CJK_LANGS,
    PROFICIENCY_VERSION,
    custom_lemmas_folder,
    get_plugin_path,
    homebrew_mac_bin_path,
    load_json_or_pickle,
    run_subprocess,
)

PY_PATH = None
LIBS_PATH = None
RUNNABLE_PIP = None
USE_SYSTEM_PYTHON = False


def install_deps(model, book_fmt, notif):
    global PY_PATH, LIBS_PATH, CALIBRE_DEBUG_PATH, RUNNABLE_PIP, USE_SYSTEM_PYTHON
    plugin_path = get_plugin_path()
    USE_SYSTEM_PYTHON = ismacos or (isfrozen and model.endswith("_trf"))

    if PY_PATH is None:
        PY_PATH, py_version = which_python(USE_SYSTEM_PYTHON)
        upgrade_pip(PY_PATH)
        LIBS_PATH = plugin_path.parent.joinpath(f"worddumb-libs-py{py_version}")
        if not USE_SYSTEM_PYTHON:
            RUNNABLE_PIP = get_runnable_pip(PY_PATH)

    dep_versions = load_json_or_pickle(plugin_path, "data/deps.json")
    if model == "lemminflect":
        pip_install("lemminflect", dep_versions["lemminflect"], notif=notif)
    elif model == "wiktionary_cjk":
        pip_install("pyahocorasick", dep_versions["pyahocorasick"], notif=notif)
    else:
        # Install X-Ray dependencies
        pip_install("rapidfuzz", dep_versions["rapidfuzz"], notif=notif)

        spacy_model_version = "3.4.1" if model.startswith("en") else "3.4.0"
        url = f"https://github.com/explosion/spacy-models/releases/download/{model}-{spacy_model_version}/{model}-{spacy_model_version}-py3-none-any.whl"
        pip_install(model, spacy_model_version, url=url, notif=notif)
        if model.endswith("_trf"):
            from .config import prefs

            pip_install(prefs["cupy"], dep_versions["cupy"], notif=notif)

        if ismacos and platform.machine() == "arm64":
            pip_install("thinc-apple-ops", dep_versions["thinc-apple-ops"], notif=notif)
        if USE_SYSTEM_PYTHON:
            from .config import prefs

            if book_fmt == "EPUB" or prefs["fandom"]:
                pip_install("lxml", dep_versions["lxml"], notif=notif)


def which_python(use_system_python=False):
    py = "python3"
    py_v = ".".join(platform.python_version_tuple()[:2])
    if iswindows:
        py = "py" if shutil.which("py") else "python"
    elif ismacos:
        py = mac_python()
        use_system_python = True

    if use_system_python:
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
    pip_path = r.stdout.split()[3]
    if iswindows:
        pip_path = pip_path.replace("\\", "/")
    return pip_path + "/__pip-runner__.py"


def pip_install(pkg, pkg_version, url=None, notif=None):
    pattern = f"{pkg.replace('-', '_')}-{pkg_version}*"
    if not any(LIBS_PATH.glob(pattern)):
        if notif:
            notif.put((0, f"Installing {pkg}"))

        if USE_SYSTEM_PYTHON:
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
    if lemma_lang in CJK_LANGS:
        install_deps("wiktionary_cjk", None, notifications)

    url = f"https://github.com/xxyzz/Proficiency/releases/download/v{PROFICIENCY_VERSION}/wiktionary_{lemma_lang}_{gloss_lang}_v{PROFICIENCY_VERSION}.tar.gz"
    extract_folder = custom_lemmas_folder(get_plugin_path())
    with urlopen(url) as r:
        with tarfile.open(fileobj=BytesIO(r.read())) as tar:
            tar.extractall(extract_folder)
