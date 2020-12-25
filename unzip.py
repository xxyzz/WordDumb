#!/usr/bin/env python3

import shutil
import sys
from pathlib import Path
from zipfile import ZipFile

from calibre.utils.config import config_dir

LIB_VERSION = '1'
DB_VERSION = '1'


def unzip(plugin_path, folder_name, version, file_name):
    extract_path = Path(config_dir).joinpath('plugins/'
                                             + folder_name + LIB_VERSION)
    if not extract_path.is_dir():
        for f in Path(config_dir).joinpath('plugins').iterdir():
            if folder_name in f.name and f.is_dir():
                shutil.rmtree(f)  # delete old library folder

        with ZipFile(plugin_path, 'r') as zf:
            for f in zf.namelist():
                if file_name in f:
                    zf.extract(f, path=extract_path)

    return extract_path


def install_libs(plugin_path):
    extract_path = unzip(plugin_path, 'worddumb-libs', LIB_VERSION, '.venv')

    for dir in extract_path.joinpath('.venv/lib').iterdir():
        sys.path.append(str(dir.joinpath('site-packages')))
    import nltk
    nltk.data.path.append(str(extract_path.joinpath('.venv/nltk_data')))


def unzip_db(plugin_path):
    db_path = unzip(plugin_path, 'worddumb-db', DB_VERSION, 'dump.rdb')
    return str(db_path.joinpath('data/dump.rdb'))
