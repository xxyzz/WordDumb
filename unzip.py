#!/usr/bin/env python3

import json
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from calibre.constants import is64bit, ismacos, iswindows
from calibre.utils.config import config_dir

PLUGIN_PATH = Path(config_dir).joinpath('plugins/WordDumb.zip')


def load_json(filepath):
    with zipfile.ZipFile(PLUGIN_PATH) as zf:
        with zf.open(filepath) as f:
            return json.load(f)


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


def install_libs(model, create_ww=True, create_x=True):
    pkgs = load_json('data/spacy.json')
    if create_x:
        for pkg, value in pkgs.items():
            pip_install(pkg, value['version'], value['compiled'])
        model_v = '3.1.0'
        url = 'https://github.com/explosion/spacy-models/releases/download/'
        url += f'{model}-{model_v}/{model}-{model_v}-py3-none-any.whl'
        pip_install(model, model_v, url=url)
        install_extra_deps(model)

    # NLTK doesn't require certain version of click and tqdm package
    # exclude regex to prevent outdated pip to build it on macOS
    # and calibre has regex
    if create_ww:
        if ismacos:
            nltk_deps = [
                (p, None) for p in ['nltk', 'joblib', 'click', 'tqdm']]
        else:
            nltk_deps = [('nltk', None), ('joblib', None),
                         ('click', pkgs['click']['version']),
                         ('tqdm', pkgs['tqdm']['version'])]
        for pkg, version in nltk_deps:
            pip_install(pkg, version)
        download_nltk_model()


def download_nltk_model():
    import nltk

    nltk_data_path = Path(config_dir).joinpath('plugins/worddumb-nltk')
    nltk_data_path_str = str(nltk_data_path)
    model_path = nltk_data_path.joinpath('corpora/wordnet')  # morphy
    if not model_path.is_dir():
        nltk.download('wordnet', nltk_data_path_str)
        model_path.with_suffix('.zip').unlink()

    if nltk_data_path_str not in nltk.data.path:
        nltk.data.path.append(nltk_data_path_str)


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
    data = load_json('data/spacy_extra.json')
    if (lang := model[:2]) in data:
        for pkg, value in data[lang].items():
            pip_install(pkg, value['version'], value['compiled'])
