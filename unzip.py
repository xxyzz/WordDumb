#!/usr/bin/env python3

import json
import shutil
import sys
import zipfile
from pathlib import Path

from calibre.utils.config import config_dir
from calibre_plugins.worddumb.config import prefs

NLTK_VERSION = '3.6.1'
NUMPY_VERSION = '1.20.2'
PLUGIN_PATH = Path(config_dir).joinpath('plugins/WordDumb.zip')


def check_folder(folder_name, version):
    extract_path = Path(config_dir).joinpath(f'plugins/{folder_name}{version}')
    if not extract_path.is_dir() and extract_path.parent.is_dir():
        for f in extract_path.parent.iterdir():
            if Path(folder_name).name in f.name and f.is_dir():
                shutil.rmtree(f)  # delete old folder

    return extract_path


def load_json(filepath):
    with zipfile.ZipFile(PLUGIN_PATH) as zf:
        with zf.open(filepath) as f:
            return json.load(f)


def install_libs(abort=None, log=None, notifications=None):
    pip_install('nltk', NLTK_VERSION, update_pip=True)
    download_nltk_data()
    if prefs['x-ray']:
        pip_install('numpy', NUMPY_VERSION,
                    f'{sys.version_info.major}{sys.version_info.minor}')


def download_nltk_data():
    nltk_path = Path(config_dir).joinpath('plugins/worddumb-nltk')
    nltk_path_str = str(nltk_path)

    import nltk
    if not nltk_path.joinpath('corpora/wordnet').is_dir():
        nltk.download('wordnet', nltk_path_str)  # morphy

    if prefs['x-ray']:
        if not nltk_path.joinpath('tokenizers/punkt').is_dir():
            nltk.download('punkt', nltk_path_str)  # word_tokenize
        # pos_tag
        averaged = 'averaged_perceptron_tagger'
        if not nltk_path.joinpath('taggers/' + averaged).is_dir():
            nltk.download(averaged, nltk_path_str)
        # ne_chunk
        if not nltk_path.joinpath('chunkers/maxent_ne_chunker').is_dir():
            nltk.download('maxent_ne_chunker', nltk_path_str)
        if not nltk_path.joinpath('corpora/words').is_dir():
            nltk.download('words', nltk_path_str)

    if nltk_path_str not in nltk.data.path:
        nltk.data.path.append(nltk_path_str)


def pip_install(package, version, py_version=None, update_pip=False):
    folder = check_folder(f'worddumb-libs/{package}', version)
    if not folder.joinpath(package).is_dir():
        import platform
        import subprocess

        pip = 'pip3'
        # stupid macOS loses PATH when calibre is not started from terminal
        if platform.system() == 'Darwin':
            pip = '/usr/local/bin/pip3'  # Homebrew
            if not Path(pip).is_file():
                pip = '/usr/bin/pip3'  # built-in
        if update_pip:
            subprocess.check_call(
                [pip, 'install', '-U', 'pip', 'setuptools', 'wheel'])
        if py_version is not None:
            subprocess.check_call(
                [pip, 'install', '-t', folder, '--python-version',
                 py_version, '--no-deps', f'{package}=={version}'])
        else:
            subprocess.check_call(
                [pip, 'install', '-t', folder, f'{package}=={version}'])
            # calibre has regex and it has .so file like numpy
            if package == 'nltk':
                for f in folder.iterdir():
                    if 'regex' in f.name:
                        shutil.rmtree(f)

    if (p := str(folder)) not in sys.path:
        sys.path.append(p)
