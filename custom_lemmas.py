#!/usr/bin/env python3

import sqlite3
import base64
from PyQt5.QtWidgets import (
    QComboBox,
    QVBoxLayout,
    QDialog,
    QDialogButtonBox,
    QTableView,
    QStyledItemDelegate,
    QAbstractItemView,
    QLineEdit,
)
from PyQt5.QtCore import QAbstractTableModel, Qt
from .utils import load_lemmas_dump, get_plugin_path, custom_lemmas_folder


class CustomLemmasDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customize Word Wise lemmas")
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.lemmas_table = QTableView()
        self.lemmas_model = LemmasTableModle()
        self.lemmas_table.setModel(self.lemmas_model)
        self.lemmas_table.hideColumn(2)
        self.lemmas_table.setItemDelegateForColumn(
            4, ComboBoxDelegate(self.lemmas_table, list(map(str, range(1, 6))))
        )
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
        vl.addWidget(save_button_box)

    def search_lemma(self, text):
        if matches := self.lemmas_model.match(
            self.lemmas_model.index(0, 1), Qt.DisplayRole, text
        ):
            self.lemmas_table.setCurrentIndex(matches[0])
            self.lemmas_table.scrollTo(matches[0])


class LemmasTableModle(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        plugin_path = get_plugin_path()
        kw_processor = load_lemmas_dump(plugin_path)
        self.lemmas = []
        klld_conn = sqlite3.connect(
            custom_lemmas_folder(plugin_path).joinpath("kll.en.en.klld")
        )
        sense_ids = {}
        for _, (difficulty, sense_id) in kw_processor.get_all_keywords().items():
            sense_ids[sense_id] = difficulty

        for (lemma, sense_id, short_def) in klld_conn.execute(
            'SELECT lemma, senses.id, short_def FROM lemmas JOIN senses ON lemmas.id = senses.display_lemma_id WHERE (full_def IS NOT NULL OR short_def IS NOT NULL) AND lemma NOT like "-%" ORDER BY lemma'
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
                    base64.b64decode(short_def).decode("utf-8") if short_def else "",
                    difficulty,
                ]
            )
        klld_conn.close()

    def data(self, index, role=Qt.DisplayRole):
        column = index.column()
        value = self.lemmas[index.row()][column]
        if role == Qt.CheckStateRole and column == 0:
            return Qt.Checked if value else Qt.Unchecked
        elif role == Qt.DisplayRole or role == Qt.ItemIsEditable:
            return value

    def rowCount(self, index):
        return len(self.lemmas)

    def columnCount(self, index):
        return len(self.lemmas[0])

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return [
                "Enabled",
                "Lemma",
                "Sense id",
                "Short definition",
                "Difficulty level",
            ][section]

    def flags(self, index):
        flag = QAbstractTableModel.flags(self, index)
        column = index.column()
        if column == 0:
            flag |= Qt.ItemIsUserCheckable
        elif column == 4:
            flag |= Qt.ItemIsEditable
        return flag

    def setData(self, index, value, role):
        column = index.column()
        if role == Qt.CheckStateRole and column == 0:
            self.lemmas[index.row()][0] = True if value == Qt.Checked else False
            return True
        elif role == Qt.EditRole and column == 4:
            self.lemmas[index.row()][4] = int(value)
            return True
        return False


class ComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, parent, options):
        super().__init__(parent)
        self.options = options

    def createEditor(self, parent, option, index):
        comboBox = QComboBox(parent)
        comboBox.addItems(self.options)
        comboBox.currentIndexChanged.connect(self.commit_editor)
        return comboBox

    def commit_editor(self):
        editor = self.sender()
        self.commitData.emit(editor)

    def setEditorData(self, editor, index):
        value = index.data(Qt.DisplayRole)
        num = self.options.index(str(value))
        editor.setCurrentIndex(num)

    def setModelData(self, editor, model, index):
        value = editor.currentText()
        model.setData(index, value, Qt.EditRole)

    def paint(self, painter, option, index):
        if isinstance(self.parent(), QAbstractItemView):
            self.parent().openPersistentEditor(index)
        super().paint(painter, option, index)
