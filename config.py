#!/usr/bin/env python3
import webbrowser

from calibre.utils.config import JSONConfig
from PyQt5.Qt import QPushButton, QRadioButton, QVBoxLayout, QWidget

prefs = JSONConfig('plugins/worddumb')
prefs.defaults['lemmatize'] = True


class ConfigWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.vl = QVBoxLayout()
        self.setLayout(self.vl)

        self.lemmatize_button = QRadioButton('Lemmatize', self)
        self.lemmatize_button.setChecked(prefs['lemmatize'])
        self.vl.addWidget(self.lemmatize_button)

        self.donate_button = QPushButton('Donate', self)
        self.donate_button.clicked.connect(self.donate)
        self.vl.addWidget(self.donate_button)

        self.github_button = QPushButton('Source code', self)
        self.github_button.clicked.connect(self.github)
        self.vl.addWidget(self.github_button)

    def donate(self):
        webbrowser.open('https://liberapay.com/xxyzz/donate')

    def github(self):
        webbrowser.open('https://github.com/xxyzz/WordDumb')

    def save_settings(self):
        prefs['lemmatize'] = self.lemmatize_button.isChecked()
