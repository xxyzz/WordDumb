#!/usr/bin/env python3

import platform
import shutil
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from calibre.constants import isfrozen, ismacos, iswindows

from .utils import (
    CJK_LANGS,
    PROFICIENCY_VERSION,
    Prefs,
    custom_lemmas_folder,
    get_plugin_path,
    homebrew_mac_bin_path,
    load_plugin_json,
    run_subprocess,
    spacy_model_name,
)

PY_PATH = ""
LIBS_PATH = Path()


def install_deps(pkg: str, notif: Any) -> None:
    global PY_PATH, LIBS_PATH
    plugin_path = get_plugin_path()

    if len(PY_PATH) == 0:
        PY_PATH, py_version = which_python()
        LIBS_PATH = plugin_path.parent.joinpath(f"worddumb-libs-py{py_version}")
        if not LIBS_PATH.is_dir():
            for old_libs_path in LIBS_PATH.parent.glob("worddumb-libs-py*"):
                shutil.rmtree(old_libs_path)

    dep_versions = load_plugin_json(plugin_path, "data/deps.json")
    if pkg == "pyahocorasick":
        pip_install("pyahocorasick", dep_versions["pyahocorasick"], notif=notif)
    elif pkg == "lxml":
        pip_install("lxml", dep_versions["lxml"], notif=notif)
    else:
        # Install X-Ray dependencies
        pip_install("rapidfuzz", dep_versions["rapidfuzz"], notif=notif)

        url = f"https://github.com/explosion/spacy-models/releases/download/{pkg}-{dep_versions['spacy_model']}/{pkg}-{dep_versions['spacy_model']}-py3-none-any.whl"
        pip_install(pkg, dep_versions["spacy_model"], url=url, notif=notif)
        if pkg.endswith("_trf"):
            from .config import prefs

            pip_install("cupy-wheel", dep_versions["cupy"], notif=notif)
            # PyTorch's Windows package on pypi.org is CPU build version, reintall the CUDA build version
            if iswindows or prefs["cuda"] == "cu116":
                pip_install(
                    "torch",
                    dep_versions["torch"],
                    extra_index=f"https://download.pytorch.org/whl/{prefs['cuda']}",
                    notif=notif,
                )

        if ismacos and platform.machine() == "arm64":
            pip_install(
                "thinc-apple-ops",
                dep_versions["thinc-apple-ops"],
                no_deps=True,
                notif=notif,
            )


def which_python() -> tuple[str, str]:
    py = "python3"
    if iswindows:
        py = "py" if shutil.which("py") else "python"
    elif ismacos:
        py = mac_python()

    if isfrozen:
        r = run_subprocess(
            [
                py,
                "-c",
                'import platform; print(".".join(platform.python_version_tuple()[:2]))',
            ]
        )
        py_v = r.stdout.decode().strip()
    else:
        py_v = ".".join(platform.python_version_tuple()[:2])
    return py, py_v


def mac_python() -> str:
    py = homebrew_mac_bin_path("python3")
    if not shutil.which(py):
        py = "/usr/bin/python3"  # Command Line Tools
    return py


def pip_install(
    pkg: str,
    pkg_version: str,
    url: str | None = None,
    extra_index: str | None = None,
    no_deps: bool = False,
    notif: Any = None,
) -> None:
    pattern = f"{pkg.replace('-', '_')}-{pkg_version}*"
    if pkg == "torch" and extra_index:
        pattern = f"torch-{pkg_version}+{extra_index.split('/')[-1]}*"
    if not any(LIBS_PATH.glob(pattern)):
        if notif:
            notif.put((0, f"Installing {pkg}"))

        args = [
            PY_PATH,
            "-m",
            "pip",
            "--disable-pip-version-check",
            "install",
            "-U",
            "-t",
            str(LIBS_PATH),
            "--no-user",  # disable "--user" option which conflicts with "-t"
        ]

        if no_deps:
            args.append("--no-deps")

        if url:
            args.append(url)
        elif pkg_version:
            args.append(f"{pkg}=={pkg_version}")
        else:
            args.append(pkg)

        if extra_index:
            args.extend(["--extra-index-url", extra_index])

        run_subprocess(args)


def download_word_wise_file(
    is_kindle: bool,
    lemma_lang: str,
    gloss_lang: str,
    prefs: Prefs,
    abort=None,
    log=None,
    notifications=None,
) -> None:
    if lemma_lang in CJK_LANGS and not prefs["use_pos"]:
        install_deps("pyahocorasick", notifications)
    if prefs["use_pos"]:
        install_deps(
            spacy_model_name(
                lemma_lang,
                load_plugin_json(get_plugin_path(), "data/languages.json"),
                prefs,
            ),
            notifications,
        )

    if notifications:
        notifications.put(
            (
                0,
                f"Downloading {lemma_lang}-{gloss_lang} {'Kindle' if is_kindle else 'Wiktionary'} file",
            )
        )
    url = f"https://github.com/xxyzz/Proficiency/releases/download/v{PROFICIENCY_VERSION}/{'kindle' if is_kindle else 'wiktionary'}_{lemma_lang}_{gloss_lang}_v{PROFICIENCY_VERSION}.tar.gz"
    extract_folder = custom_lemmas_folder(get_plugin_path())
    with urlopen(url) as r:
        with tarfile.open(fileobj=BytesIO(r.read())) as tar:
            tar.extractall(extract_folder)
