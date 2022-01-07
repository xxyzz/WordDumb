#!/usr/bin/env python3

import webbrowser

from calibre.utils.config import JSONConfig
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

prefs = JSONConfig('plugins/worddumb')
prefs.defaults['search_people'] = False
prefs.defaults['model_size'] = 'md'
prefs.defaults['zh_wiki_variant'] = 'cn'


class ConfigWidget(QWidget):
    def __init__(self):
        super().__init__()

        vl = QVBoxLayout()
        self.setLayout(vl)

        self.search_people_box = QCheckBox(
            'Search X-Ray people entities on Wikipedia')
        self.search_people_box.setChecked(prefs['search_people'])
        vl.addWidget(self.search_people_box)

        model_size_hl = QHBoxLayout()
        model_size_label = QLabel(
            '<a href="https://spacy.io/models/en">spaCy model</a> size')
        model_size_label.setOpenExternalLinks(True)
        model_size_label.setToolTip('Larger model improves X-Ray quality')
        self.model_size_box = QComboBox()
        spacy_model_sizes = {
            'sm': 'small',
            'md': 'medium',
            'lg': 'large'
        }
        for size, text in spacy_model_sizes.items():
            self.model_size_box.addItem(text, size)
        self.model_size_box.setCurrentText(
            spacy_model_sizes[prefs['model_size']])
        model_size_hl.addWidget(model_size_label)
        model_size_hl.addWidget(self.model_size_box)
        vl.addLayout(model_size_hl)

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

        donate_button = QPushButton('Tree-fiddy?')
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
        prefs['model_size'] = self.model_size_box.currentData()
        prefs['zh_wiki_variant'] = self.zh_wiki_box.currentData()
