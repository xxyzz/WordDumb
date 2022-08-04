#!/usr/bin/env python3

import base64
import json
import pickle
import sqlite3
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, Qt, QVariant
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
)

from .import_lemmas import extract_apkg, extract_csv, query_vocabulary_builder
from .tst import TST
from .utils import (
    custom_lemmas_dump_path,
    get_klld_path,
    get_lemmas_tst_path,
    get_plugin_path,
    load_json_or_pickle,
    load_lemmas_dump,
    wiktionary_json_path,
)
from .wiktionary import get_ipa


class CustomLemmasDialog(QDialog):
    def __init__(self, parent, lang=None, title=None):
        super().__init__(parent)
        self.lang = lang
        self.setWindowTitle(f"Customize {title if lang else 'Kindle Word Wise'}")
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.lemmas_table = QTableView()
        self.lemmas_table.setAlternatingRowColors(True)
        self.lemmas_model = (
            WiktionaryTableModel(lang) if lang else KindleLemmasTableModel()
        )
        self.lemmas_table.setModel(self.lemmas_model)
        self.lemmas_table.hideColumn(5 if lang else 2)
        if lang is None:
            self.lemmas_table.setItemDelegateForColumn(
                5,
                ComboBoxDelegate(
                    self.lemmas_table,
                    list(range(1, 6)),
                    {0: "Fewer Hints", 4: "More Hints"},
                ),
            )
        self.lemmas_table.horizontalHeader().setMaximumSectionSize(400)
        self.lemmas_table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self.lemmas_table.resizeColumnsToContents()
        vl.addWidget(self.lemmas_table)

        search_line = QLineEdit()
        search_line.setPlaceholderText("Search")
        search_line.textChanged.connect(lambda: self.search_lemma(search_line.text()))
        vl.addWidget(search_line)

        if lang in ["en", "zh"]:
            from .config import prefs

            self.ipa_button = QComboBox()
            if lang == "en":
                self.ipa_button.addItems(["US", "UK"])
                self.ipa_button.setCurrentText(prefs["en_ipa"])
            elif lang == "zh":
                self.ipa_button.addItems(["Pinyin", "bopomofo"])
                self.ipa_button.setCurrentText(prefs["zh_ipa"])

            hl = QHBoxLayout()
            hl.addWidget(
                QLabel(
                    "Phonetic transcription system"
                    if lang == "zh"
                    else "International Phonetic Alphabet"
                )
            )
            self.ipa_button.currentIndexChanged.connect(self.change_ipa)
            hl.addWidget(self.ipa_button)
            vl.addLayout(hl)

        dialog_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_button_box.accepted.connect(self.accept)
        dialog_button_box.rejected.connect(self.reject)
        import_button = QPushButton(QIcon.ic("document-import.png"), "Import")
        import_button.clicked.connect(self.select_import_file)
        dialog_button_box.addButton(
            import_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        if lang is None:
            dialog_button_box.addButton(QDialogButtonBox.StandardButton.RestoreDefaults)
            dialog_button_box.button(
                QDialogButtonBox.StandardButton.RestoreDefaults
            ).clicked.connect(self.reset_lemmas)
        vl.addWidget(dialog_button_box)

    def search_lemma(self, text):
        row = self.lemmas_model.lemmas_tst.get_prefix(text)
        if row:
            index = self.lemmas_model.createIndex(row, 1)
            self.lemmas_table.setCurrentIndex(index)
            self.lemmas_table.scrollTo(index)

    def select_import_file(self) -> None:
        retain_lemmas, ok = QInputDialog.getItem(
            self,
            "Import file",
            "Retain current enabled lemmas",
            ["True", "False"],
            editable=False,
        )
        if not ok:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select file",
            str(Path.home()),
            "Anki Deck Package (*.apkg);;CSV (*.csv);;Kindle Vocabulary Builder (*.db)",
        )
        lemmas_dict = {}
        if file_path.endswith(".apkg"):
            lemmas_dict = extract_apkg(Path(file_path))
        elif file_path.endswith(".csv"):
            lemmas_dict = extract_csv(file_path)
        elif file_path.endswith(".db"):
            lemmas_dict = query_vocabulary_builder(
                self.lang if self.lang else "en", file_path
            )
        else:
            return

        self.lemmas_model.import_lemmas(lemmas_dict, retain_lemmas == "True")

    def reset_lemmas(self):
        custom_path = custom_lemmas_dump_path(get_plugin_path())
        if custom_path.exists():
            custom_path.unlink()
            self.reject()

    def change_ipa(self):
        from .config import prefs

        if self.lang == "en":
            prefs["en_ipa"] = self.ipa_button.currentText()
        elif self.lang == "zh":
            prefs["zh_ipa"] = self.ipa_button.currentText()

        self.lemmas_model.change_ipa()


class LemmasTableModel(QAbstractTableModel):
    def rowCount(self, index):
        return len(self.lemmas)

    def columnCount(self, index):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self.headers[section]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        column = index.column()
        value = self.lemmas[index.row()][column]
        if role == Qt.ItemDataRole.CheckStateRole and column == 0:
            new_value = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
            if isinstance(new_value, int):  # PyQt5
                return new_value
            else:  # PyQt6 Enum
                return new_value.value
        elif (
            isinstance(self, KindleLemmasTableModel)
            and role == Qt.ItemDataRole.DisplayRole
            and column == 3
        ):
            return self.pos_types[value]
        elif (
            isinstance(self, WiktionaryTableModel)
            and role == Qt.ItemDataRole.DisplayRole
            and column == 7
        ):
            from .config import prefs

            ipa_tag = prefs["en_ipa"] if self.lang == "en" else prefs["zh_ipa"]
            return get_ipa(self.lang, ipa_tag, value)
        elif role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return value
        elif role == Qt.ItemDataRole.ToolTipRole and column in self.tooltip_columns:
            return value

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        flag = QAbstractTableModel.flags(self, index)
        column = index.column()
        if column == 0:
            flag |= Qt.ItemFlag.ItemIsUserCheckable
        elif column in self.editable_columns:
            flag |= Qt.ItemFlag.ItemIsEditable
        return flag

    def setData(self, index, value, role):
        if not index.isValid():
            return False
        column = index.column()
        if role == Qt.ItemDataRole.CheckStateRole and column == 0:
            checked_value = (
                Qt.CheckState.Checked
                if isinstance(Qt.CheckState.Checked, int)
                else Qt.CheckState.Checked.value
            )
            self.lemmas[index.row()][0] = value == checked_value
            self.dataChanged.emit(index, index, [role])
            return True
        elif role == Qt.ItemDataRole.EditRole and column in self.editable_columns:
            self.lemmas[index.row()][column] = (
                int(value) if isinstance(self, KindleLemmasTableModel) else value
            )
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def import_lemmas(
        self, lemmas_dict: dict[str, list[int, bool]], retain_lemmas: bool
    ) -> None:
        for row in range(self.rowCount(None)):
            lemma = self.lemmas[row][1]
            enable = Qt.CheckState.Unchecked.value
            difficulty = 1
            if retain_lemmas:
                if self.lemmas[row][0]:
                    enable = Qt.CheckState.Checked.value
                else:
                    enable = Qt.CheckState.Unchecked.value
                if isinstance(self, KindleLemmasTableModel):
                    difficulty = self.lemmas[row][5]

            data = lemmas_dict.get(lemma)
            if data and data[1]:
                enable = Qt.CheckState.Checked.value
                difficulty = data[0]
                lemmas_dict[lemma][1] = False
            self.setData(
                self.createIndex(row, 0), enable, Qt.ItemDataRole.CheckStateRole
            )
            if isinstance(self, KindleLemmasTableModel):
                self.setData(
                    self.createIndex(row, 5), difficulty, Qt.ItemDataRole.EditRole
                )


class KindleLemmasTableModel(LemmasTableModel):
    def __init__(self):
        super().__init__()
        plugin_path = get_plugin_path()
        kw_processor = load_lemmas_dump(plugin_path)
        self.lemmas = []
        klld_conn = sqlite3.connect(get_klld_path(plugin_path))
        sense_ids = {}
        for _, (difficulty, sense_id) in kw_processor.get_all_keywords().items():
            sense_ids[sense_id] = difficulty

        self.pos_types = {}
        for pos_type_id, pos_type_lable in klld_conn.execute("SELECT * FROM pos_types"):
            self.pos_types[pos_type_id] = pos_type_lable

        self.lemmas_tst = None
        lemmas_tst_path = get_lemmas_tst_path(plugin_path, None)
        if lemmas_tst_path.exists():
            self.lemmas_tst = load_json_or_pickle(None, lemmas_tst_path)
        else:
            self.lemmas_tst = TST()
        lemmas_count = 0
        lemmas_row = []

        for lemma, sense_id, short_def, full_def, pos_type in klld_conn.execute(
            'SELECT lemma, senses.id, short_def, full_def, pos_type FROM lemmas JOIN senses ON lemmas.id = display_lemma_id WHERE (full_def IS NOT NULL OR short_def IS NOT NULL) AND lemma NOT like "-%" ORDER BY lemma'
        ):
            enabled = False
            difficulty = 1
            if sense_id in sense_ids:
                enabled = True
                difficulty = sense_ids[sense_id]
            self.lemmas.append(
                [
                    enabled,
                    lemma,
                    sense_id,
                    pos_type,
                    base64.b64decode(short_def if short_def else full_def).decode(
                        "utf-8"
                    ),
                    difficulty,
                ]
            )
            if not lemmas_tst_path.exists():
                lemmas_row.append((lemma, lemmas_count))
                lemmas_count += 1

        self.lemmas_tst.put_values(lemmas_row)
        klld_conn.close()
        self.headers = [
            "Enabled",
            "Lemma",
            "Sense id",
            "POS",
            "Definition",
            "Difficulty",
        ]
        self.editable_columns = [5]
        self.tooltip_columns = [4]
        if not lemmas_tst_path.exists():
            with lemmas_tst_path.open("wb") as f:
                pickle.dump(self.lemmas_tst, f)


class ComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, parent, options, tooltips={}):
        super().__init__(parent)
        self.options = options
        self.tooltips = tooltips

    def createEditor(self, parent, option, index):
        comboBox = QComboBox(parent)
        if isinstance(self.options, list):
            for value in self.options:
                comboBox.addItem(str(value), value)
        elif isinstance(self.options, dict):
            for value, text in self.options.items():
                comboBox.addItem(text, value)

        for index, text in self.tooltips.items():
            comboBox.setItemData(index, text, Qt.ItemDataRole.ToolTipRole)
        comboBox.currentIndexChanged.connect(self.commit_editor)

        return comboBox

    def commit_editor(self):
        editor = self.sender()
        self.commitData.emit(editor)

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if isinstance(self.options, list):
            editor.setCurrentText(str(value))
        else:
            editor.setCurrentText(self.options[value])

    def setModelData(self, editor, model, index):
        value = editor.currentData()
        model.setData(index, value, Qt.ItemDataRole.EditRole)

    def paint(self, painter, option, index):
        if isinstance(self.parent(), QAbstractItemView):
            self.parent().openPersistentEditor(index)
        super().paint(painter, option, index)


class WiktionaryTableModel(LemmasTableModel):
    def __init__(self, lang):
        super().__init__()
        self.lang = lang
        self.headers = [
            "Enabled",
            "Lemma",
            "POS",
            "Short gloss",
            "Gloss",
            "Example",
            "Forms",
            "IPA",
        ]
        self.editable_columns = [3, 4]
        self.tooltip_columns = [4]
        plugin_path = get_plugin_path()
        self.json_path = wiktionary_json_path(plugin_path, lang)
        with open(self.json_path, encoding="utf-8") as f:
            self.lemmas = json.load(f)
        self.lemmas_tst = load_json_or_pickle(
            None, get_lemmas_tst_path(plugin_path, lang)
        )

    def save_json_file(self):
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.lemmas, f)

    def change_ipa(self):
        for row in range(self.rowCount(None)):
            if self.lemmas[row][7]:
                index = self.createIndex(row, 7)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
