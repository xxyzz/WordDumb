#!/usr/bin/env python3

from calibre.utils.config import JSONConfig
from PyQt5.Qt import QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout
import webbrowser

prefs = JSONConfig('plugins/worddumb')

prefs.defaults['offset'] = '0'

class ConfigWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.vl = QVBoxLayout()
        self.setLayout(self.vl)
        self.hl = QHBoxLayout()
        self.vl.addLayout(self.hl)

        self.label = QLabel('Offset:')
        self.hl.addWidget(self.label)

        self.offset = QLineEdit(self)
        self.offset.setText(prefs['offset'])
        self.hl.addWidget(self.offset)
        self.label.setBuddy(self.offset)

        self.donate_button = QPushButton('Donate', self)
        self.donate_button.clicked.connect(self.donate)
        self.vl.addWidget(self.donate_button)

        self.github_button = QPushButton('Source code', self)
        self.github_button.clicked.connect(self.github)
        self.vl.addWidget(self.github_button)

    def save_settings(self):
        prefs['offset'] = self.offset.text()

    def donate(self):
        webbrowser.open('https://liberapay.com/xxyzz/donate')

    def github(self):
        webbrowser.open('https://github.com/xxyzz/WordDumb')
