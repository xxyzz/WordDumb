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
    PROFICIENCY_RELEASE_URL,
    PROFICIENCY_VERSION,
    Prefs,
    custom_lemmas_folder,
    get_plugin_path,
    get_wiktionary_klld_path,
    mac_bin_path,
    kindle_db_path,
    load_plugin_json,
    run_subprocess,
    use_kindle_ww_db,
    wiktionary_db_path,
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
    if pkg == "lxml":
        pip_install("lxml", dep_versions["lxml"], notif=notif)
    else:
        # Install X-Ray dependencies
        pip_install("rapidfuzz", dep_versions["rapidfuzz"], notif=notif)

        model_version = dep_versions[
            "spacy_trf_model" if pkg.endswith("_trf") else "spacy_cpu_model"
        ]
        url = f"https://github.com/explosion/spacy-models/releases/download/{pkg}-{model_version}/{pkg}-{model_version}-py3-none-any.whl"
        pip_install(pkg, model_version, url=url, notif=notif)
        if pkg.endswith("_trf"):
            from .config import prefs

            pip_install("cupy-wheel", dep_versions["cupy"], notif=notif)
            # PyTorch's Windows package on pypi.org is CPU build version, reintall the CUDA build version
            if iswindows or prefs["cuda"] == "cu118":
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
    """
    Return Python command or file path and version string
    """
    py = "python3"
    if iswindows:
        py = "py" if shutil.which("py") else "python"
    elif ismacos:
        py = mac_bin_path("python3")

    if shutil.which(py) is None:
        raise Exception("PythonNotFound")

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
    if list(map(int, py_v.split("."))) < [3, 10]:
        raise Exception("OutdatedPython")
    return py, py_v


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
    prefs: Prefs,
    abort=None,
    log=None,
    notifications=None,
) -> None:
    gloss_lang = prefs["kindle_gloss_lang" if is_kindle else "wiktionary_gloss_lang"]
    if notifications:
        notifications.put(
            (
                0,
                f"Downloading {lemma_lang}-{gloss_lang} {'Kindle' if is_kindle else 'Wiktionary'} file",
            )
        )
    plugin_path = get_plugin_path()
    if is_kindle:
        db_path = kindle_db_path(plugin_path, lemma_lang, prefs)
    else:
        db_path = wiktionary_db_path(plugin_path, lemma_lang, gloss_lang)

    extract_folder = custom_lemmas_folder(get_plugin_path())
    if not db_path.exists():
        filename = f"wiktionary_{lemma_lang}_{gloss_lang}_v{PROFICIENCY_VERSION}.bz2"
        if is_kindle and use_kindle_ww_db(lemma_lang, prefs):
            filename = f"kindle_en_en_v{PROFICIENCY_VERSION}.bz2"
        url = f"{PROFICIENCY_RELEASE_URL}/{filename}"
        download_and_extract(url, extract_folder)

    if is_kindle:
        klld_path = get_wiktionary_klld_path(plugin_path, lemma_lang, gloss_lang)
        if not klld_path.exists():
            url = f"{PROFICIENCY_RELEASE_URL}/kll.{lemma_lang}.{gloss_lang}_v{PROFICIENCY_VERSION}.klld.bz2"
            download_and_extract(url, extract_folder)


def download_and_extract(url: str, extract_folder: Path) -> None:
    with urlopen(url) as r:
        with tarfile.open(fileobj=BytesIO(r.read())) as tar:
            tar.extractall(extract_folder)
