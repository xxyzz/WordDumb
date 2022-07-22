#!/usr/bin/env python3

import base64
import json
import sqlite3
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QAbstractTableModel, Qt, QVariant
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
)

from .data.anki import extract_apkg, extract_csv
from .utils import (
    get_klld_path,
    get_plugin_path,
    load_lemmas_dump,
    wiktionary_json_path,
)


class CustomLemmasDialog(QDialog):
    def __init__(self, parent, lang=None, title=None):
        super().__init__(parent)
        self.setWindowTitle(f"Customize {title if lang else 'Kindle Word Wise'}")
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.lemmas_table = QTableView()
        self.lemmas_table.setAlternatingRowColors(True)
        self.lemmas_model = WiktionaryTableModel(lang) if lang else LemmasTableModel()
        self.lemmas_table.setModel(self.lemmas_model)
        self.lemmas_table.hideColumn(4 if lang else 2)
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

        save_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button_box.accepted.connect(self.accept)
        save_button_box.rejected.connect(self.reject)
        import_button = QPushButton(QIcon.ic("document-import.png"), "Import")
        import_button.clicked.connect(self.select_import_file)
        save_button_box.addButton(import_button, QDialogButtonBox.ButtonRole.ActionRole)
        vl.addWidget(save_button_box)

    def search_lemma(self, text):
        if matches := self.lemmas_model.match(
            self.lemmas_model.index(0, 1), Qt.ItemDataRole.DisplayRole, text
        ):
            self.lemmas_table.setCurrentIndex(matches[0])
            self.lemmas_table.scrollTo(matches[0])

    def select_import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select file",
            str(Path.home()),
            "Anki Deck Package (*.apkg);;CSV (*.csv)",
        )
        if file_path.endswith(".apkg"):
            self.lemmas_model.import_anki(extract_apkg(Path(file_path)))
        elif file_path.endswith(".csv"):
            self.lemmas_model.import_csv(extract_csv(file_path))


class LemmasTableModel(QAbstractTableModel):
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
        klld_conn.close()
        self.headers = [
            "Enabled",
            "Lemma",
            "Sense id",
            "POS type",
            "Definition",
            "Difficulty",
        ]

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
        elif role == Qt.ItemDataRole.DisplayRole and column == 3:
            return self.pos_types[value]
        elif role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return value
        elif role == Qt.ItemDataRole.ToolTipRole and column == 4:
            return value

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

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        flag = QAbstractTableModel.flags(self, index)
        column = index.column()
        if column == 0:
            flag |= Qt.ItemFlag.ItemIsUserCheckable
        elif column == 5:
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
        elif role == Qt.ItemDataRole.EditRole and column == 5:
            self.lemmas[index.row()][5] = int(value)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def import_anki(self, anki_cards: dict[str, int]) -> None:
        enabled_words = set()
        for row in range(self.rowCount(None)):
            word = self.lemmas[row][1]
            enable = Qt.CheckState.Unchecked.value
            difficulty = 1
            if word not in enabled_words and word in anki_cards:
                enable = Qt.CheckState.Checked.value
                difficulty = anki_cards[word]
                enabled_words.add(word)
            self.setData(
                self.createIndex(row, 0), enable, Qt.ItemDataRole.CheckStateRole
            )
            self.setData(self.createIndex(row, 5), difficulty, Qt.ItemDataRole.EditRole)

    def import_csv(self, csv_words: dict[str, list[int, bool]]) -> None:
        for row in range(self.rowCount(None)):
            word = self.lemmas[row][1]
            enable = Qt.CheckState.Unchecked.value
            difficulty = 1
            csv_data = csv_words.get(word)
            if csv_data and csv_data[1]:
                enable = Qt.CheckState.Checked.value
                difficulty = csv_data[0]
                csv_words[word][1] = False
            self.setData(
                self.createIndex(row, 0), enable, Qt.ItemDataRole.CheckStateRole
            )
            self.setData(self.createIndex(row, 5), difficulty, Qt.ItemDataRole.EditRole)


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


class WiktionaryTableModel(QAbstractTableModel):
    def __init__(self, lang):
        super().__init__()
        self.headers = ["Enabled", "Lemma", "Short gloss", "Gloss", "Example", "Forms"]
        self.editable_columns = [2, 5]
        self.json_path = wiktionary_json_path(get_plugin_path(), lang)
        with open(self.json_path, encoding="utf-8") as f:
            self.lemmas = json.load(f)

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
        elif role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return value
        elif role == Qt.ItemDataRole.ToolTipRole and column == 3:
            return value

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
            self.lemmas[index.row()][column] = value
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def save_json_file(self):
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.lemmas, f)

    def import_anki(self, anki_cards: dict[str, int]) -> None:
        enabled_words = set()
        for row in range(self.rowCount(None)):
            word = self.lemmas[row][1]
            enable = Qt.CheckState.Unchecked.value
            if word not in enabled_words and word in anki_cards:
                enable = Qt.CheckState.Checked.value
                enabled_words.add(word)
            self.setData(
                self.createIndex(row, 0), enable, Qt.ItemDataRole.CheckStateRole
            )

    def import_csv(self, csv_words: dict[str, list[int, bool]]) -> None:
        for row in range(self.rowCount(None)):
            word = self.lemmas[row][1]
            enable = Qt.CheckState.Unchecked.value
            csv_data = csv_words.get(word)
            if csv_data and csv_data[1]:
                enable = Qt.CheckState.Checked.value
                csv_words[word][1] = False
            self.setData(
                self.createIndex(row, 0), enable, Qt.ItemDataRole.CheckStateRole
            )
