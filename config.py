#!/usr/bin/env python3

import webbrowser
import json
from functools import partial

from calibre.utils.config import JSONConfig
from calibre.gui2 import Dispatcher
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.constants import ismacos
from PyQt5.QtCore import QRegularExpression
from PyQt5.QtGui import QRegularExpressionValidator
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .custom_lemmas import CustomLemmasDialog
from .data.dump_lemmas import dump_lemmas
from .deps import InstallDeps
from .utils import (
    get_plugin_path,
    insert_flashtext_path,
    insert_installed_libs,
    run_subprocess,
    custom_lemmas_dump_path,
    custom_lemmas_folder,
    get_klld_path,
)
from .error_dialogs import job_failed, error_dialog
from .send_file import device_connected, copy_klld_from_android, copy_klld_from_kindle

prefs = JSONConfig("plugins/worddumb")
prefs.defaults["search_people"] = False
prefs.defaults["model_size"] = "md"
prefs.defaults["zh_wiki_variant"] = "cn"
prefs.defaults["fandom"] = ""
prefs.defaults["add_locator_map"] = False


class ConfigWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.plugin_path = get_plugin_path()

        vl = QVBoxLayout()
        self.setLayout(vl)

        customize_ww_button = QPushButton("Customize Word Wise lemmas")
        customize_ww_button.clicked.connect(self.open_custom_lemmas_dialog)
        vl.addWidget(customize_ww_button)

        self.search_people_box = QCheckBox(
            "Fetch X-Ray people descriptions from Wikipedia or Fandom"
        )
        self.search_people_box.setToolTip(
            "Enable this option for nonfiction books and novels that have character pages on Wikipedia/Fandom"
        )
        self.search_people_box.setChecked(prefs["search_people"])
        vl.addWidget(self.search_people_box)

        model_size_hl = QHBoxLayout()
        model_size_label = QLabel(
            '<a href="https://spacy.io/models/en">spaCy model</a> size'
        )
        model_size_label.setOpenExternalLinks(True)
        model_size_label.setToolTip("Larger model improves X-Ray quality")
        self.model_size_box = QComboBox()
        spacy_model_sizes = {"sm": "small", "md": "medium", "lg": "large"}
        for size, text in spacy_model_sizes.items():
            self.model_size_box.addItem(text, size)
        self.model_size_box.setCurrentText(spacy_model_sizes[prefs["model_size"]])
        model_size_hl.addWidget(model_size_label)
        model_size_hl.addWidget(self.model_size_box)
        vl.addLayout(model_size_hl)

        zh_wiki_hl = QHBoxLayout()
        zh_label = QLabel("Chinese Wikipedia variant")
        self.zh_wiki_box = QComboBox()
        zh_variants = {
            "cn": "大陆简体",
            "hk": "香港繁體",
            "mo": "澳門繁體",
            "my": "大马简体",
            "sg": "新加坡简体",
            "tw": "臺灣正體",
        }
        for variant, text in zh_variants.items():
            self.zh_wiki_box.addItem(text, variant)
        self.zh_wiki_box.setCurrentText(zh_variants[prefs["zh_wiki_variant"]])
        zh_wiki_hl.addWidget(zh_label)
        zh_wiki_hl.addWidget(self.zh_wiki_box)
        vl.addLayout(zh_wiki_hl)

        fandom_hl = QHBoxLayout()
        fandom_label = QLabel("Fandom URL")
        fandom_hl.addWidget(fandom_label)
        self.fandom_url = QLineEdit()
        self.fandom_url.setText(prefs["fandom"])
        self.fandom_url.setPlaceholderText("https://*.fandom.com[/language]")
        fandom_re = QRegularExpression(r"https:\/\/[\w-]+\.fandom\.com(\/\w{2})?")
        fandom_validator = QRegularExpressionValidator(fandom_re)
        self.fandom_url.setValidator(fandom_validator)
        fandom_hl.addWidget(self.fandom_url)
        vl.addLayout(fandom_hl)

        self.locator_map_box = QCheckBox("Add locator map to EPUB footnotes")
        self.locator_map_box.setToolTip(
            "Enable this option if your e-reader supports image in footnotes"
        )
        self.locator_map_box.setChecked(prefs["add_locator_map"])
        vl.addWidget(self.locator_map_box)

        donate_button = QPushButton("Tree-fiddy?")
        donate_button.clicked.connect(self.donate)
        vl.addWidget(donate_button)

        github_button = QPushButton("Source code and document")
        github_button.clicked.connect(self.github)
        vl.addWidget(github_button)

    @staticmethod
    def donate():
        webbrowser.open("https://liberapay.com/xxyzz/donate")

    def github(self):
        webbrowser.open("https://github.com/xxyzz/WordDumb")

    def save_settings(self):
        prefs["search_people"] = self.search_people_box.isChecked()
        prefs["model_size"] = self.model_size_box.currentData()
        prefs["zh_wiki_variant"] = self.zh_wiki_box.currentData()
        prefs["fandom"] = self.fandom_url.text()
        prefs["add_locator_map"] = self.locator_map_box.isChecked()

    def open_custom_lemmas_dialog(self):
        klld_path = get_klld_path(self.plugin_path)
        gui = self.parent().parent()
        if klld_path is None:
            package_name = device_connected(gui, "KFX")
            if not package_name:
                error_dialog(
                    "Device not found",
                    "Please connect your Kindle or Android device then try again.",
                    "",
                    self,
                )
                return
            custom_folder = custom_lemmas_folder(self.plugin_path)
            if not custom_folder.exists():
                custom_folder.mkdir()
            if isinstance(package_name, str):
                copy_klld_from_android(package_name, custom_folder)
            else:
                copy_klld_from_kindle(gui, custom_folder)

        custom_lemmas_dlg = CustomLemmasDialog(self)
        if custom_lemmas_dlg.exec():
            job = ThreadedJob(
                "WordDumb's dumb job",
                "Saving customized lemmas",
                self.save_lemmas,
                (
                    {
                        lemma: (difficulty, sense_id)
                        for enabled, lemma, sense_id, _, difficulty in custom_lemmas_dlg.lemmas_model.lemmas
                        if enabled
                    },
                ),
                {},
                Dispatcher(partial(job_failed, parent=gui)),
                killable=False,
            )
            gui.job_manager.run_threaded_job(job)

    def save_lemmas(self, lemmas, abort=None, log=None, notifications=None):
        installdeps = InstallDeps(None, self.plugin_path, None, notifications)
        notifications.put((0, "Saving customized lemmas"))
        custom_path = custom_lemmas_dump_path(self.plugin_path)
        if ismacos:
            plugin_path = str(self.plugin_path)
            args = [installdeps.py, plugin_path]
            args.extend([""] * 11 + [plugin_path, str(custom_path)])
            run_subprocess(args, json.dumps(lemmas))
        else:
            insert_flashtext_path(self.plugin_path)
            insert_installed_libs(self.plugin_path)
            dump_lemmas(lemmas, custom_path)
