#!/usr/bin/env python3

import webbrowser

from calibre.utils.config import JSONConfig
from PyQt5.Qt import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton,
                      QVBoxLayout, QWidget)

prefs = JSONConfig('plugins/worddumb')
prefs.defaults['search_people'] = False
prefs.defaults['zh_wiki_variant'] = 'cn'


class ConfigWidget(QWidget):
    def __init__(self):
        super().__init__()

        vl = QVBoxLayout()
        self.setLayout(vl)

        self.search_people_box = QCheckBox('Search people')
        self.search_people_box.setChecked(prefs['search_people'])
        vl.addWidget(self.search_people_box)

        zh_wiki_hl = QHBoxLayout()
        zh_label = QLabel('Chinese Wikipedia variant')
        self.zh_wiki_box = QComboBox()
        zh_variants = {
            'cn': '大陆简体',
            'hk': '香港繁體',
            'mo': '澳門繁體',
            'my': '大马简体',
            'sg': '新加坡简体',
            'tw': '臺灣正體'
        }
        for variant, text in zh_variants.items():
            self.zh_wiki_box.addItem(text, variant)
        self.zh_wiki_box.setCurrentText(zh_variants[prefs['zh_wiki_variant']])
        zh_wiki_hl.addWidget(zh_label)
        zh_wiki_hl.addWidget(self.zh_wiki_box)
        vl.addLayout(zh_wiki_hl)

        donate_button = QPushButton('Donate')
        donate_button.clicked.connect(self.donate)
        vl.addWidget(donate_button)

        github_button = QPushButton('Source code')
        github_button.clicked.connect(self.github)
        vl.addWidget(github_button)

    @staticmethod
    def donate():
        webbrowser.open('https://liberapay.com/xxyzz/donate')

    def github(self):
        webbrowser.open('https://github.com/xxyzz/WordDumb')

    def save_settings(self):
        prefs['search_people'] = self.search_people_box.isChecked()
        prefs['zh_wiki_variant'] = self.zh_wiki_box.currentData()
