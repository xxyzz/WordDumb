#!/usr/bin/env python3

import platform
import re
import shutil

from calibre.constants import ismacos, iswindows

from .utils import (
    get_plugin_path,
    homebrew_mac_bin_path,
    load_json_or_pickle,
    run_subprocess,
)

PLUGINS_PATH = get_plugin_path()
SPACY_MODEL_VERSION = "3.4.0"


def install_deps(model, book_fmt, notif):
    global PY_PATH, PY_VERSION, LIBS_PATH
    PY_PATH, PY_VERSION = which_python()
    LIBS_PATH = PLUGINS_PATH.parent.joinpath(f"worddumb-libs-py{PY_VERSION}")

    reinstall = False if LIBS_PATH.exists() else True
    if reinstall:
        for old_path in LIBS_PATH.parent.glob("worddumb-libs-py*"):
            old_path.rename(LIBS_PATH)
    if model == "lemminflect":
        install_lemminflect(reinstall, notif)
    elif model.startswith("wiktionary"):
        install_wiktionary_deps(model, reinstall, notif)
    else:
        install_x_ray_deps(model, reinstall, notif)
        install_extra_deps(model, book_fmt, reinstall, notif)


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


def install_x_ray_deps(model, reinstall, notif):
    pip_install_pkgs(
        load_json_or_pickle(PLUGINS_PATH, "data/spacy.json"), reinstall, notif
    )
    url = f"https://github.com/explosion/spacy-models/releases/download/{model}-{SPACY_MODEL_VERSION}/{model}-{SPACY_MODEL_VERSION}-py3-none-any.whl"
    pip_install(model, SPACY_MODEL_VERSION, url=url, notif=notif)


def pip_install(
    pkg, pkg_version, compiled=False, url=None, reinstall=False, notif=None
):
    pattern = f"{pkg.replace('-', '_')}-{pkg_version}*"
    if not any(LIBS_PATH.glob(pattern)) or (reinstall and compiled):
        if notif:
            notif.put((0, f"Installing {pkg}"))
        args = [
            PY_PATH,
            "-m",
            "pip",
            "install",
            "-U",
            "-t",
            LIBS_PATH,
            "--no-deps",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "--no-user",
        ]
        if compiled:
            args.extend(["--python-version", PY_VERSION])
        if url:
            args.append(url)
        elif pkg_version:
            args.append(f"{pkg}=={pkg_version}")
        else:
            args.append(pkg)
        run_subprocess(args)


def pip_install_pkgs(pkgs, reinstall, notif):
    for pkg, value in pkgs.items():
        pip_install(
            pkg, value["version"], value["compiled"], reinstall=reinstall, notif=notif
        )


def install_extra_deps(model, book_fmt, reinstall, notif):
    # https://spacy.io/usage/models#languages
    data = load_json_or_pickle(PLUGINS_PATH, "data/spacy_extra.json")
    if (lang := model[:2]) in data:
        pip_install_pkgs(data[lang], reinstall, notif)

    if ismacos:
        if book_fmt == "EPUB":
            pip_install_pkgs(data["mac_epub"], reinstall, notif)
        if platform.machine() == "arm64":
            pip_install_pkgs(data["mac_arm"], reinstall, notif)


def upgrade_pip(py_path):
    r = run_subprocess(
        [py_path, "-m", "pip", "--version", "--disable-pip-version-check"]
    )
    m = re.match(r"pip (\d+)\.", r.stdout)
    if m and int(m.group(1)) < 22:
        run_subprocess(
            [
                py_path,
                "-m",
                "pip",
                "install",
                "--user",
                "-U",
                "--no-cache-dir",
                "pip",
            ]
        )


def install_lemminflect(reinstall, notif):
    data = load_json_or_pickle(PLUGINS_PATH, "data/spacy_extra.json")
    pip_install_pkgs(data["lemminflect"], reinstall, notif)


def install_wiktionary_deps(dep_type, reinstall, notif):
    data = load_json_or_pickle(PLUGINS_PATH, "data/spacy_extra.json")
    pip_install_pkgs(data["wiktionary"], reinstall, notif)
    if dep_type == "wiktionary_cjk":
        pip_install_pkgs(data["wiktionary_cjk"], reinstall, notif)
