#!/usr/bin/env python3

import json
import pickle
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from calibre.constants import is64bit, ismacos, iswindows
from calibre.utils.config import config_dir

PLUGIN_PATH = Path(config_dir).joinpath('plugins/WordDumb.zip')


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
        pkgs = load_json_or_pickle('data/spacy.json', True)
        for pkg, value in pkgs.items():
            pip_install(pkg, value['version'], value['compiled'])
        model_v = '3.1.0'
        url = 'https://github.com/explosion/spacy-models/releases/download/'
        url += f'{model}-{model_v}/{model}-{model_v}-py3-none-any.whl'
        pip_install(model, model_v, url=url)
        install_extra_deps(model)


def pip_install(pkg, pkg_version=None, compiled=False, url=None):
    folder = Path(config_dir).joinpath(f'plugins/worddumb-libs/{pkg}')
    py_version = '.'.join(platform.python_version_tuple()[:2])
    if pkg_version:
        folder = folder.with_name(f'{folder.name}_{pkg_version}')
    if compiled:
        folder = folder.with_name(f'{folder.name}_{py_version}')

    if not folder.is_dir():
        for d in folder.parent.glob(f'{pkg}_*'):
            shutil.rmtree(d)  # delete old package

        args = pip_args(folder, pkg, py_version, pkg_version, compiled, url)
        if iswindows:
            subprocess.run(args, check=True, capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(args, check=True, capture_output=True)

    if (p := str(folder)) not in sys.path:
        sys.path.insert(0, p)


def pip_args(folder, pkg, py_version,
             pkg_version=None, compiled=False, url=None):
    python3 = 'python3'
    if iswindows:
        python3 = 'py'
    elif ismacos:
        # stupid macOS loses PATH when calibre is not launched in terminal
        if platform.machine() == 'arm64':
            python3 = '/opt/homebrew/bin/python3'
        else:
            python3 = '/usr/local/bin/python3'
        if not Path(python3).is_file():
            python3 = '/usr/bin/python3'  # command line tools
    args = [python3, '-m', 'pip', 'install', '-t', folder, '--no-deps']
    if compiled:
        args.extend(['--python-version', py_version])
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
