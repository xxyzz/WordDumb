#!/usr/bin/env python3
from calibre.customize import InterfaceActionBase

VERSION = (3, 21, 0)


class WordDumbDumb(InterfaceActionBase):
    name = "WordDumb"
    description = "Create Kindle Word Wise and X-Ray file and EPUB footnotes then send to e-reader."
    supported_platforms = ["linux", "osx", "windows"]
    author = "xxyzz"
    version = VERSION
    minimum_calibre_version = (5, 23, 0)
    actual_plugin = "calibre_plugins.worddumb.ui:WordDumb"

    def is_customizable(self):
        return True

    def config_widget(self):
        from .config import ConfigWidget

        return ConfigWidget()

    def save_settings(self, config_widget):
        config_widget.save_settings()
