#!/usr/bin/env python3

import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

from calibre.utils.config import config_dir

LIB_VERSION = '1'
DB_VERSION = '1'
WORDNET_VERSION = '3.0'


def check_folder(plugin_path, folder_name, version, file_name, extract):
    extract_path = Path(config_dir).joinpath('plugins/'
                                             + folder_name + version)
    if not extract_path.is_dir():
        for f in Path(config_dir).joinpath('plugins').iterdir():
            if folder_name in f.name and f.is_dir():
                shutil.rmtree(f)  # delete old folder

        if extract:
            unzip(plugin_path, file_name, extract_path)

    return extract_path


def unzip(plugin_path, file_name, extract_path):
    with ZipFile(plugin_path, 'r') as zf:
        for f in zf.namelist():
            if file_name in f:
                zf.extract(f, path=extract_path)


def install_libs(plugin_path):
    extract_path = check_folder(
        plugin_path, 'worddumb-libs', LIB_VERSION, '.venv', True)

    for dir in extract_path.joinpath('.venv/lib').iterdir():
        sys.path.append(str(dir.joinpath('site-packages')))

    download_wordnet(plugin_path)


def download_wordnet(plugin_path):
    wordnet_path = check_folder(
        plugin_path, 'worddumb-wordnet', WORDNET_VERSION, None, False)

    import nltk
    if not wordnet_path.is_dir():
        nltk.download('wordnet', download_dir=str(wordnet_path))
    nltk.data.path.append(str(wordnet_path))


def unzip_db(plugin_path):
    db_path = check_folder(plugin_path, 'worddumb-db',
                           DB_VERSION, 'dump.rdb', True)
    return str(db_path.joinpath('data'))
