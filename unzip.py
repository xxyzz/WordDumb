#!/usr/bin/env python3

import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

from calibre.utils.config import config_dir
from calibre_plugins.worddumb.config import prefs

NLTK_AND_DEPENCIES = ['nltk', 'joblib', 'click', 'tqdm']  # exclude regex
PLUGIN_PATH = Path(config_dir).joinpath('plugins/WordDumb.zip')


def load_json(filepath):
    with zipfile.ZipFile(PLUGIN_PATH) as zf:
        with zf.open(filepath) as f:
            return json.load(f)


def install_libs(abort=None, log=None, notifications=None):
    for pkg in NLTK_AND_DEPENCIES:
        pip_install(pkg)
    download_nltk_data()
    if prefs['x-ray']:
        pip_install(
            'numpy', f'{sys.version_info.major}{sys.version_info.minor}')


def download_nltk_data():
    import nltk

    nltk_data_path = Path(config_dir).joinpath('plugins/worddumb-nltk')
    nltk_data_path_str = str(nltk_data_path)
    download_nltk_model(nltk_data_path, 'corpora', 'wordnet')  # morphy
    if prefs['x-ray']:
        models = [
            ('tokenizers', 'punkt'),  # word_tokenize
            ('taggers', 'averaged_perceptron_tagger'),  # pos_tag
            ('chunkers', 'maxent_ne_chunker'),  # ne_chunk
            ('corpora', 'words')
        ]
        for parent, model in models:
            download_nltk_model(nltk_data_path, parent, model)

    if nltk_data_path_str not in nltk.data.path:
        nltk.data.path.append(nltk_data_path_str)


def download_nltk_model(data_folder, parent, model):
    import nltk

    path = data_folder.joinpath(f'{parent}/{model}')
    if not path.is_dir():
        nltk.download(model, str(data_folder))
        path.with_suffix('.zip').unlink()


def pip_install(package, py_version=None):
    folder = Path(config_dir).joinpath(f'plugins/worddumb-libs/{package}')
    if py_version:
        folder = folder.with_name(f'{package}_{py_version}')

    if not folder.is_dir():
        python3 = 'python3'
        # stupid macOS loses PATH when calibre is not started from terminal
        if platform.system() == 'Darwin':
            # Homebrew
            if platform.machine() == 'arm64':
                python3 = '/opt/homebrew/bin/python3'
            else:
                python3 = '/usr/local/bin/python3'
            if not Path(python3).is_file():
                python3 = '/usr/bin/python3'  # built-in
        if py_version:
            subprocess.check_call(
                [python3, '-m', 'pip', 'install', '-t', folder,
                 '--python-version', py_version, '--no-deps', package])
        else:
            subprocess.check_call(
                [python3, '-m', 'pip', 'install', '-t', folder,
                 '--no-deps', package])

    if (p := str(folder)) not in sys.path:
        sys.path.append(p)
