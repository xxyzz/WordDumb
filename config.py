#!/usr/bin/env python3

import json
import webbrowser
from functools import partial

from calibre.constants import ismacos
from calibre.gui2 import Dispatcher
from calibre.gui2.threaded_jobs import ThreadedJob
from calibre.utils.config import JSONConfig
from PyQt6.QtCore import QRegularExpression, Qt
from PyQt6.QtGui import QIcon, QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .custom_lemmas import CustomLemmasDialog
from .data.dump_lemmas import dump_lemmas
from .deps import install_deps, mac_python
from .error_dialogs import (
    GITHUB_URL,
    device_not_found_dialog,
    job_failed,
    ww_db_not_found_dialog,
)
from .parse_job import dump_wiktionary_job
from .send_file import copy_klld_from_android, copy_klld_from_kindle, device_connected
from .utils import (
    custom_lemmas_dump_path,
    custom_lemmas_folder,
    donate,
    get_klld_path,
    get_plugin_path,
    get_user_agent,
    insert_flashtext_path,
    insert_installed_libs,
    load_json_or_pickle,
    run_subprocess,
    wiktionary_json_path,
)

prefs = JSONConfig("plugins/worddumb")
prefs.defaults["search_people"] = False
prefs.defaults["model_size"] = "md"
prefs.defaults["zh_wiki_variant"] = "cn"
prefs.defaults["fandom"] = ""
prefs.defaults["add_locator_map"] = False
prefs.defaults["preferred_formats"] = ["KFX", "AZW3", "AZW", "MOBI", "EPUB"]
prefs.defaults["use_all_formats"] = False
prefs.defaults["minimal_x_ray_count"] = 1
prefs.defaults["en_ipa"] = "US"
prefs.defaults["zh_ipa"] = "Pinyin"
prefs.defaults["choose_format_manually"] = True


class ConfigWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.plugin_path = get_plugin_path()

        vl = QVBoxLayout()
        self.setLayout(vl)

        format_order_button = QPushButton("Preferred format order")
        format_order_button.clicked.connect(self.open_format_order_dialog)
        vl.addWidget(format_order_button)

        customize_ww_button = QPushButton("Customize Kindle Word Wise")
        customize_ww_button.clicked.connect(self.open_kindle_lemmas_dialog)
        vl.addWidget(customize_ww_button)

        custom_wiktionary_button = QPushButton("Customize EPUB Wiktionary")
        custom_wiktionary_button.clicked.connect(self.open_wiktionary_dialog)
        vl.addWidget(custom_wiktionary_button)

        self.search_people_box = QCheckBox(
            "Fetch X-Ray people descriptions from Wikipedia/Fandom"
        )
        self.search_people_box.setToolTip(
            "Enable this option for nonfiction books and novels that have character pages on Wikipedia/Fandom"
        )
        self.search_people_box.setChecked(prefs["search_people"])
        vl.addWidget(self.search_people_box)

        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        model_size_label = QLabel(
            '<a href="https://spacy.io/models/en">spaCy model</a> size'
        )
        model_size_label.setOpenExternalLinks(True)
        model_size_label.setToolTip("Larger model improves X-Ray quality")
        self.model_size_box = QComboBox()
        spacy_model_sizes = {"sm": "Small", "md": "Medium", "lg": "Large"}
        for size, text in spacy_model_sizes.items():
            self.model_size_box.addItem(text, size)
        self.model_size_box.setCurrentText(spacy_model_sizes[prefs["model_size"]])
        form_layout.addRow(model_size_label, self.model_size_box)

        self.minimal_x_ray_count = QSpinBox()
        self.minimal_x_ray_count.setMinimum(1)
        self.minimal_x_ray_count.setValue(prefs["minimal_x_ray_count"])
        minimal_x_ray_label = QLabel("Minimal X-Ray occurrences")
        minimal_x_ray_label.setToolTip(
            "X-Ray entities that appear less then this number and don't have description from Wikipedia/Fandom will be removed"
        )
        form_layout.addRow(minimal_x_ray_label, self.minimal_x_ray_count)

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
        form_layout.addRow("Chinese Wikipedia variant", self.zh_wiki_box)

        self.fandom_url = QLineEdit()
        self.fandom_url.setText(prefs["fandom"])
        self.fandom_url.setPlaceholderText("https://*.fandom.com[/language]")
        fandom_re = QRegularExpression(r"https:\/\/[\w-]+\.fandom\.com(\/\w{2})?")
        fandom_validator = QRegularExpressionValidator(fandom_re)
        self.fandom_url.setValidator(fandom_validator)
        form_layout.addRow("Fandom URL", self.fandom_url)

        vl.addLayout(form_layout)

        self.locator_map_box = QCheckBox("Add locator map to EPUB footnotes")
        self.locator_map_box.setToolTip(
            "Enable this option if your e-reader supports image in footnotes"
        )
        self.locator_map_box.setChecked(prefs["add_locator_map"])
        vl.addWidget(self.locator_map_box)

        donate_button = QPushButton(QIcon.ic("donate.png"), "Tree-fiddy?")
        donate_button.clicked.connect(donate)
        vl.addWidget(donate_button)

        github_button = QPushButton("Source code and document")
        github_button.clicked.connect(self.github)
        vl.addWidget(github_button)

    def github(self):
        webbrowser.open(GITHUB_URL)

    def save_settings(self):
        prefs["search_people"] = self.search_people_box.isChecked()
        prefs["model_size"] = self.model_size_box.currentData()
        prefs["zh_wiki_variant"] = self.zh_wiki_box.currentData()
        prefs["fandom"] = self.fandom_url.text()
        prefs["add_locator_map"] = self.locator_map_box.isChecked()
        prefs["minimal_x_ray_count"] = self.minimal_x_ray_count.value()

    def open_kindle_lemmas_dialog(self):
        klld_path = get_klld_path(self.plugin_path)
        gui = self.parent().parent()
        if klld_path is None:
            package_name = device_connected(gui, "KFX")
            if not package_name:
                device_not_found_dialog(self)
                return
            custom_folder = custom_lemmas_folder(self.plugin_path)
            if not custom_folder.exists():
                custom_folder.mkdir()
            if isinstance(package_name, str):
                copy_klld_from_android(package_name, custom_folder)
            else:
                copy_klld_from_kindle(gui, custom_folder)

        klld_path = get_klld_path(self.plugin_path)
        if klld_path is None:
            ww_db_not_found_dialog(self)
            return
        custom_lemmas_dlg = CustomLemmasDialog(self)
        if custom_lemmas_dlg.exec():
            job = ThreadedJob(
                "WordDumb's dumb job",
                "Saving customized lemmas",
                self.save_lemmas,
                (
                    {
                        lemma: (difficulty, sense_id, pos_type)
                        for enabled, lemma, sense_id, pos_type, _, difficulty, _ in custom_lemmas_dlg.lemmas_model.lemmas
                        if enabled
                    },
                ),
                {},
                Dispatcher(partial(job_failed, parent=gui)),
                killable=False,
            )
            gui.job_manager.run_threaded_job(job)

    def save_lemmas(self, lemmas, abort=None, log=None, notifications=None):
        install_deps("lemminflect", None, notifications)
        notifications.put((0, "Saving customized lemmas"))
        custom_path = custom_lemmas_dump_path(self.plugin_path)
        if ismacos:
            plugin_path = str(self.plugin_path)
            args = [mac_python(), plugin_path]
            args.extend([""] * 12 + [plugin_path, str(custom_path)])
            run_subprocess(args, json.dumps(lemmas))
        else:
            insert_flashtext_path(self.plugin_path)
            insert_installed_libs(self.plugin_path)
            dump_lemmas(lemmas, custom_path)

    def open_format_order_dialog(self):
        format_order_dialog = FormatOrderDialog(self)
        if format_order_dialog.exec():
            format_order_dialog.save()

    def open_wiktionary_dialog(self):
        language_dict = load_json_or_pickle(self.plugin_path, "data/languages.json")
        languages = {val["kaikki"]: val["wiki"] for val in language_dict.values()}
        lang, ok = QInputDialog.getItem(
            self,
            "Select Wiktionary source language",
            "Language",
            languages.keys(),
            editable=False,
        )
        if not ok:
            return
        wiki_lang = languages[lang]
        wiktionary_path = wiktionary_json_path(self.plugin_path, wiki_lang)
        if wiktionary_path.exists():
            custom_lemmas_dlg = CustomLemmasDialog(
                self, wiki_lang, f"{lang} Wiktionary"
            )
            if custom_lemmas_dlg.exec():
                self.run_dump_wiktionary_job(
                    wiki_lang, lang, None, custom_lemmas_dlg.lemmas_model
                )
        else:
            self.run_dump_wiktionary_job(wiki_lang, lang, get_user_agent(), None)

    def run_dump_wiktionary_job(self, wiki_lang, lang, useragent, table_model):
        gui = self.parent().parent()
        job = ThreadedJob(
            "WordDumb's dumb job",
            "Download Wiktionary",
            dump_wiktionary_job,
            (
                self.plugin_path,
                {"wiki": wiki_lang, "kaikki": lang},
                useragent,
                table_model,
            ),
            {},
            Dispatcher(partial(job_failed, parent=gui)),
            killable=False,
        )
        gui.job_manager.run_threaded_job(job)


class FormatOrderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferred format order")
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.format_list = QListWidget()
        self.format_list.setAlternatingRowColors(True)
        self.format_list.setDragEnabled(True)
        self.format_list.viewport().setAcceptDrops(True)
        self.format_list.setDropIndicatorShown(True)
        self.format_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.format_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.format_list.addItems(prefs["preferred_formats"])
        vl.addWidget(self.format_list)

        self.choose_format_maunally = QCheckBox("Choose format manually")
        self.choose_format_maunally.setChecked(prefs["choose_format_manually"])
        self.choose_format_maunally.stateChanged.connect(
            self.disable_all_formats_button
        )
        vl.addWidget(self.choose_format_maunally)

        self.use_all_formats = QCheckBox("Create files for all available formats")
        self.use_all_formats.setChecked(prefs["use_all_formats"])
        self.disable_all_formats_button(self.choose_format_maunally.checkState().value)
        vl.addWidget(self.use_all_formats)

        save_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button_box.accepted.connect(self.accept)
        save_button_box.rejected.connect(self.reject)
        vl.addWidget(save_button_box)

    def save(self):
        prefs["preferred_formats"] = [
            self.format_list.item(index).text()
            for index in range(self.format_list.count())
        ]
        prefs["choose_format_manually"] = self.choose_format_maunally.isChecked()
        prefs["use_all_formats"] = self.use_all_formats.isChecked()

    def disable_all_formats_button(self, choose_format_state: int) -> None:
        if choose_format_state == Qt.CheckState.Checked.value:
            self.use_all_formats.setChecked(False)
            self.use_all_formats.setDisabled(True)
        else:
            self.use_all_formats.setEnabled(True)


class ChooseFormatDialog(QDialog):
    def __init__(self, formats: list[str]) -> None:
        super().__init__()
        self.setWindowTitle("Choose book format")
        vl = QVBoxLayout()
        self.setLayout(vl)

        message = QLabel(
            "This book has multiple supported formats. Choose the format you want to use."
        )
        vl.addWidget(message)

        self.choose_format_manually = QCheckBox(
            "Always ask when more than one format is available"
        )
        self.choose_format_manually.setChecked(True)
        vl.addWidget(self.choose_format_manually)

        format_buttons = QDialogButtonBox()
        for book_format in formats:
            button = format_buttons.addButton(
                book_format, QDialogButtonBox.ButtonRole.AcceptRole
            )
            button.clicked.connect(partial(self.accept_format, button.text()))
        vl.addWidget(format_buttons)

    def accept_format(self, chosen_format: str) -> None:
        self.chosen_format = chosen_format
        if not self.choose_format_manually.isChecked():
            prefs["choose_format_manually"] = False
        self.accept()
