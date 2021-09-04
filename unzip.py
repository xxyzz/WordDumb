#!/usr/bin/env python3

import json
import pickle
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

from calibre.constants import is64bit, ismacos, iswindows
from calibre.utils.config import config_dir

PLUGIN_PATH = Path(config_dir).joinpath('plugins/WordDumb.zip')
PY_VERSION = '.'.join(platform.python_version_tuple()[:2])
LIBS_PATH = Path(config_dir).joinpath(f"plugins/worddumb-libs-py{PY_VERSION}")


def load_json_or_pickle(filepath, is_json):
    with zipfile.ZipFile(PLUGIN_PATH) as zf:
        with zf.open(filepath) as f:
            if is_json:
                return json.load(f)
            else:
                return pickle.load(f)


def wiki_cache_path(lang):
    return Path(config_dir).joinpath(f'plugins/worddumb-wikipedia/{lang}.json')


def load_wiki_cache(lang):
    cache_path = wiki_cache_path(lang)
    if cache_path.exists():
        with cache_path.open() as f:
            return json.load(f)
    else:
        return {}


def save_wiki_cache(cache_dic, lang):
    cache_path = wiki_cache_path(lang)
    if not cache_path.exists():
        if not cache_path.parent.exists():
            cache_path.parent.mkdir()
        cache_path.touch()
    with cache_path.open('w') as f:
        json.dump(cache_dic, f)


def install_libs(model, create_ww, create_x):
    if create_ww:
        libs_path = str(PLUGIN_PATH.joinpath('libs'))  # flashtext
        if libs_path not in sys.path:
            sys.path.insert(0, libs_path)

    if create_x:
        if (reinstall := False if LIBS_PATH.exists() else True):
            for old_path in LIBS_PATH.parent.glob('worddumb-libs-py*'):
                old_path.rename(LIBS_PATH)

        for pkg, value in load_json_or_pickle('data/spacy.json', True).items():
            pip_install(
                pkg, value['version'], value['compiled'], reinstall=reinstall)
        model_v = '3.1.0'
        url = 'https://github.com/explosion/spacy-models/releases/download/'
        url += f'{model}-{model_v}/{model}-{model_v}-py3-none-any.whl'
        pip_install(model, model_v, url=url)
        install_extra_deps(model)

        if LIBS_PATH not in sys.path:
            sys.path.insert(0, str(LIBS_PATH))


def pip_install(
        pkg, pkg_version=None, compiled=False, url=None, reinstall=False):
    if pkg_version:
        folder = LIBS_PATH.joinpath(
            f"{pkg.replace('-', '_')}-{pkg_version}.dist-info")
    else:
        folder = LIBS_PATH.joinpath(pkg.replace('-', '_').lower())

    if not folder.exists() or (reinstall and compiled):
        args = pip_args(pkg, pkg_version, compiled, url)
        if iswindows:
            subprocess.run(args, check=True, capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(args, check=True, capture_output=True)


def pip_args(pkg, pkg_version, compiled, url):
    py = 'python3'
    if iswindows:
        py = 'py'
    elif ismacos:
        # stupid macOS loses PATH when calibre is not launched in terminal
        if platform.machine() == 'arm64':
            py = '/opt/homebrew/bin/python3'
        else:
            py = '/usr/local/bin/python3'
        if not Path(py).exists():
            py = '/usr/bin/python3'  # command line tools
    args = [py, '-m', 'pip', 'install', '-U', '-t', LIBS_PATH, '--no-deps']
    if compiled:
        args.extend(['--python-version', PY_VERSION])
        if iswindows:
            args.append('--platform')
            if is64bit:
                args.append('win_amd64')
            else:
                args.append('win32')
    if url:
        args.append(url)
    elif pkg_version:
        args.append(f'{pkg}=={pkg_version}')
    else:
        args.append(pkg)
    return args


def install_extra_deps(model):
    # https://spacy.io/usage/models#languages
    data = load_json_or_pickle('data/spacy_extra.json', True)
    if (lang := model[:2]) in data:
        for pkg, value in data[lang].items():
            pip_install(pkg, value['version'], value['compiled'])
