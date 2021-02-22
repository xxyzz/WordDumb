#!/usr/bin/env python3
import platform
import webbrowser

from calibre.utils.config import JSONConfig
from PyQt5.Qt import QPushButton, QRadioButton, QVBoxLayout, QWidget

prefs = JSONConfig('plugins/worddumb')
prefs.defaults['x-ray'] = True if platform.system() != 'Darwin' else False


class ConfigWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.vl = QVBoxLayout()
        self.setLayout(self.vl)

        self.xray_button = QRadioButton('X-Ray', self)
        self.xray_button.setChecked(prefs['x-ray'])
        self.vl.addWidget(self.xray_button)

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
        prefs['x-ray'] = self.xray_button.isChecked()
