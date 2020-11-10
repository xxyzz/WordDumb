#!/usr/bin/env python3

from calibre.customize import InterfaceActionBase

class WordDumbDumb(InterfaceActionBase):
    name = 'WordDumb'
    description = 'Create Kindle Word Wise file.'
    supported_platforms = ['linux', 'osx', 'windows']
    author = 'xxyzz'
    version = (1, 1, 0)
    minimum_calibre_version = (5, 0, 0) # Python3
    actual_plugin = 'calibre_plugins.worddumb.ui:WordDumb'
