#!/usr/bin/env python3

import sqlite3
import base64
from pathlib import Path
from PyQt5.QtWidgets import (
    QComboBox,
    QVBoxLayout,
    QDialog,
    QDialogButtonBox,
    QTableView,
    QStyledItemDelegate,
    QAbstractItemView,
)
from PyQt5.QtCore import QAbstractTableModel, Qt
from calibre.utils.config import config_dir
from .utils import load_lemmas_dump


class CustomLemmasDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customize Word Wise lemmas")
        vl = QVBoxLayout()
        self.setLayout(vl)

        lemmas_table = QTableView()
        lemmas_model = LemmasTableModle()
        lemmas_table.setModel(lemmas_model)
        lemmas_table.hideColumn(2)
        lemmas_table.setItemDelegateForColumn(
            4, ComboBoxDelegate(lemmas_table, list(map(str, range(1, 6))))
        )
        vl.addWidget(lemmas_table)

        save_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button_box.accepted.connect(self.accept)
        save_button_box.rejected.connect(self.reject)
        vl.addWidget(save_button_box)


class LemmasTableModle(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        lemmas_folder = Path(config_dir).joinpath("plugins/worddumb-lemmas")
        kw_processor = load_lemmas_dump(
            str(Path(config_dir).joinpath("plugins/WordDumb.zip"))
        )
        self.lemmas = []
        klld_conn = sqlite3.connect(lemmas_folder.joinpath("kll.en.en.klld"))
        for (lemma, sense_id, short_def) in klld_conn.execute(
            'SELECT lemma, senses.id, short_def FROM lemmas JOIN senses ON lemmas.id = senses.display_lemma_id WHERE length(short_def) > 0 AND lemma NOT LIKE "\'%" AND lemma NOT like "-%" ORDER BY lemma'
        ):
            enabled = False
            difficulty = 1
            if lemma in kw_processor:
                used_difficulty, used_sense_id = kw_processor[lemma]
                if used_sense_id == sense_id:
                    enabled = True
                    difficulty = used_difficulty
            self.lemmas.append(
                [
                    enabled,
                    lemma,
                    sense_id,
                    base64.b64decode(short_def).decode("utf-8"),
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
