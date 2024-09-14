import platform
import shutil
import tarfile
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from calibre.constants import isfrozen, ismacos, iswindows

from .utils import (
    PROFICIENCY_RELEASE_URL,
    Prefs,
    custom_lemmas_folder,
    get_plugin_path,
    get_spacy_model_version,
    load_plugin_json,
    mac_bin_path,
    run_subprocess,
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

        if pkg == "":
            pip_install("spacy", dep_versions["spacy"], notif=notif)
        else:
            model_version = get_spacy_model_version(pkg, dep_versions)
            url = (
                "https://github.com/explosion/spacy-models/releases/download/"
                f"{pkg}-{model_version}/{pkg}-{model_version}-py3-none-any.whl"
            )
            pip_install(pkg, model_version, url=url, notif=notif)

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
    from .config import prefs

    py = "python3"
    if len(prefs["python_path"]) > 0:
        py = prefs["python_path"]
    elif iswindows:
        py = "py"
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
    if tuple(map(int, py_v.split("."))) < tuple(
        map(int, platform.python_version_tuple()[:2])
    ):
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
            "--no-cache-dir",
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
    gloss_lang = prefs["gloss_lang"]
    if notifications:
        notifications.put(
            (
                0,
                f"Downloading {lemma_lang}-{gloss_lang} "
                f"{'Kindle' if is_kindle else 'Wiktionary'} file",
            )
        )
    plugin_path = get_plugin_path()
    bz2_filename = f"{lemma_lang}_{gloss_lang}.tar.bz2"
    url = f"{PROFICIENCY_RELEASE_URL}/{bz2_filename}"
    download_folder = custom_lemmas_folder(plugin_path)
    if not download_folder.is_dir():
        download_folder.mkdir()
    download_path = download_folder / bz2_filename
    with urlopen(url) as r, open(download_path, "wb") as f:
        shutil.copyfileobj(r, f)
    with tarfile.open(name=download_path, mode="r:bz2") as tar_f:
        tar_f.extractall(download_folder)
    download_path.unlink()
