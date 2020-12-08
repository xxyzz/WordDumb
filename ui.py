#!/usr/bin/env python3
import sys
from pathlib import Path
from zipfile import ZipFile

from calibre.gui2.actions import InterfaceAction
from calibre.utils.config import config_dir
from calibre_plugins.worddumb.main import ParseBook


class WordDumb(InterfaceAction):
    name = 'WordDumb'
    action_spec = ('WordDumb', None, 'Good morning Krusty Crew!', None)

    def genesis(self):
        icon = get_icons('starfish.svg')
        self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.run)
        self.install_libs()

    def run(self):
        p = ParseBook(self.gui)
        p.parse()

    def install_libs(self):
        extarct_path = Path(config_dir).joinpath('plugins/worddumb')
        if not extarct_path.is_dir():
            with ZipFile(self.plugin_path, 'r') as zf:
                for f in zf.namelist():
                    if '.venv' in f:
                        zf.extract(f, path=extarct_path)
        for dir in extarct_path.joinpath('.venv/lib').iterdir():
            sys.path.append(str(dir.joinpath('site-packages')))
        import nltk
        nltk.data.path.append(str(extarct_path.joinpath('.venv/nltk_data')))
