#!/usr/bin/env python3

import base64
import json
import pickle
import re
import sqlite3
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QVariant
from PyQt6.QtGui import QIcon
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
)

from .import_lemmas import extract_apkg, extract_csv, query_vocabulary_builder
from .utils import (
    custom_lemmas_folder,
    get_klld_path,
    get_plugin_path,
    kindle_dump_path,
    load_json_or_pickle,
    load_lemmas_dump,
)

load_translations()  # type: ignore
if TYPE_CHECKING:
    _: Any


class CustomLemmasDialog(QDialog):
    def __init__(
        self, parent: QObject, is_kindle: bool, lemma_lang: str, db_path: Path
    ) -> None:
        super().__init__(parent)
        self.lemma_lang = lemma_lang
        self.db_path = db_path
        if is_kindle:
            window_title = _("Customize Kindle Word Wise")
        else:
            window_title = _("Customize Wiktionary")
        self.setWindowTitle(window_title)
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.lemmas_table = QTableView()
        self.lemmas_table.setAlternatingRowColors(True)
        db = QSqlDatabase.addDatabase("QSQLITE")
        db.setDatabaseName(str(db_path))
        db.open()
        self.lemmas_model: WiktionaryTableModel | KindleLemmasTableModel = (
            KindleLemmasTableModel(db, lemma_lang)
            if is_kindle
            else WiktionaryTableModel(db, lemma_lang)
        )
        self.lemmas_model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
        self.lemmas_model.setTable("lemmas")
        self.lemmas_model.setSort(
            self.lemmas_model.lemma_column, Qt.SortOrder.AscendingOrder
        )
        self.lemmas_model.select()

        self.lemmas_table.setModel(self.lemmas_model)
        self.lemmas_table.setItemDelegateForColumn(
            self.lemmas_model.difficulty_column,
            ComboBoxDelegate(
                self.lemmas_table,
                list(range(1, 6)),
                {0: _("Fewer Hints"), 4: _("More Hints")},
            ),
        )
        for column in self.lemmas_model.hide_columns:
            self.lemmas_table.hideColumn(column)
        self.lemmas_table.horizontalHeader().setMaximumSectionSize(400)
        self.lemmas_table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self.lemmas_table.resizeColumnsToContents()
        vl.addWidget(self.lemmas_table)

        search_line = QLineEdit()
        search_line.setPlaceholderText(_("Search"))
        # search_line.textChanged.connect(lambda: self.search_lemma(search_line.text()))
        vl.addWidget(search_line)

        if not is_kindle:
            from .config import prefs

            if lemma_lang in ["en", "zh"]:
                self.ipa_button = QComboBox()
                if lemma_lang == "en":
                    self.ipa_button.addItem(_("General American"), "ga_ipa")
                    self.ipa_button.addItem(_("Received Pronunciation"), "rp_ipa")
                    self.ipa_button.setCurrentText(prefs["en_ipa"])
                elif lemma_lang == "zh":
                    self.ipa_button.addItem(_("Pinyin"), "pinyin")
                    self.ipa_button.addItem(_("Bopomofo"), "bopomofo")
                    self.ipa_button.setCurrentText(_(prefs["zh_ipa"]))

                hl = QHBoxLayout()
                hl.addWidget(
                    QLabel(
                        _("Phonetic transcription system")
                        if lemma_lang == "zh"
                        else _("International Phonetic Alphabet")
                    )
                )
                self.ipa_button.currentIndexChanged.connect(self.change_ipa)
                hl.addWidget(self.ipa_button)
                vl.addLayout(hl)

            hl = QHBoxLayout()
            difficulty_label = QLabel(_("Difficulty limit"))
            difficulty_label.setToolTip(
                _(
                    "Difficult words have lower value. Words have difficulty value higher than this value are disabled."
                )
            )
            hl.addWidget(difficulty_label)
            self.difficulty_limit_box = QComboBox()
            self.difficulty_limit_box.addItems(map(str, range(5, 0, -1)))
            self.difficulty_limit_box.setCurrentText(
                str(prefs[f"{lemma_lang}_wiktionary_difficulty_limit"])
            )
            hl.addWidget(self.difficulty_limit_box)
            vl.addLayout(hl)

        dialog_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_button_box.accepted.connect(self.accept)
        dialog_button_box.rejected.connect(self.reject)
        import_button = QPushButton(QIcon.ic("document-import.png"), _("Import"))
        import_button.clicked.connect(self.select_import_file)
        dialog_button_box.addButton(
            import_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        export_button = QPushButton(QIcon.ic("save.png"), _("Export"))
        export_button.clicked.connect(self.set_export_options)
        dialog_button_box.addButton(
            export_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        dialog_button_box.addButton(QDialogButtonBox.StandardButton.RestoreDefaults)
        dialog_button_box.button(
            QDialogButtonBox.StandardButton.RestoreDefaults
        ).clicked.connect(self.reset_lemmas)
        vl.addWidget(dialog_button_box)

    def search_lemma(self, text: str) -> None:
        row = self.lemmas_model.lemmas_tst.get_prefix(text)
        if row:
            index = self.lemmas_model.createIndex(row, 1)
            self.lemmas_table.setCurrentIndex(index)
            self.lemmas_table.scrollTo(index)

    def select_import_file(self) -> None:
        import_options_dialog = ImportOptionsDialog(self)
        if not import_options_dialog.exec():
            return

        file_path, ignore = QFileDialog.getOpenFileName(
            self,
            _("Select import file"),
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

        self.lemmas_model.import_lemmas(
            lemmas_dict, import_options_dialog.retain_enabled_lemmas.isChecked()
        )

    def reset_lemmas(self):
        plugin_path = get_plugin_path()
        self.lemmas_model.database().close()
        self.db_path.unlink()
        self.reject()

    def change_ipa(self):
        from .config import prefs

        prefs[f"{self.lemma_lang}_ipa"] = self.ipa_button.currentData()

    def set_export_options(self):
        option_dialog = ExportOptionsDialog(self)
        if not option_dialog.exec():
            return

        export_path, ignore = QFileDialog.getSaveFileName(
            self, _("Set export file path"), str(Path.home())
        )
        if not export_path:
            return

        self.lemmas_model.export(
            export_path,
            option_dialog.only_enabled_box.isChecked(),
            int(option_dialog.difficulty_limit_box.currentText()),
        )

    def change_difficulty_limit(self):
        from .config import prefs

        limit = int(self.difficulty_limit_box.currentText())
        prefs[f"{self.lang}_wiktionary_difficulty_limit"] = limit


class LemmasTableModel(QSqlTableModel):
    def __init__(self, db: QSqlDatabase) -> None:
        super().__init__(db=db)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole
    ) -> QVariant:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self.headers[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flag = super().flags(index)
        column = index.column()
        if column == self.checkable_column:
            flag |= Qt.ItemFlag.ItemIsUserCheckable
        elif column in self.editable_columns:
            flag |= Qt.ItemFlag.ItemIsEditable
        else:
            flag &= ~Qt.ItemFlag.ItemIsEditable
        return flag

    def data(
        self, index: QModelIndex, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole
    ) -> QVariant:
        column = index.column()
        if role == Qt.ItemDataRole.CheckStateRole and column == self.checkable_column:
            value = self.record(index.row()).value(column)
            return (
                Qt.CheckState.Checked.value
                if value == 1
                else Qt.CheckState.Unchecked.value
            )
        elif role == Qt.ItemDataRole.ToolTipRole and column in self.tooltip_columns:
            return self.record(index.row()).value(column)
        return super().data(index, role)

    def setData(
        self,
        index: QModelIndex,
        value: QVariant,
        role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid():
            return False
        column = index.column()
        if role == Qt.ItemDataRole.CheckStateRole and column == self.checkable_column:
            row = index.row()
            record = self.record(row)
            record.setValue(column, 1 if value == Qt.CheckState.Checked.value else 0)
            record.setGenerated(column, True)
            self.setRecord(row, record)
            self.dataChanged.emit(index, index, [role])
            return True
        return super().setData(index, value, role)

    def import_lemmas(self, lemmas_dict: dict[str, int], retain_lemmas: bool) -> None:
        if isinstance(self, KindleLemmasTableModel):
            difficulty_column = 5
        else:
            difficulty_column = 8

        for row in range(self.rowCount(None)):
            lemma = self.lemmas[row][1]
            origin_enable = self.lemmas[row][0]
            origin_difficulty = self.lemmas[row][difficulty_column]
            enable = origin_enable
            difficulty = origin_difficulty

            if imported_difficulty := lemmas_dict.get(lemma):
                enable = True
                difficulty = imported_difficulty
            elif not retain_lemmas:
                enable = False

            if origin_enable != enable:
                self.setData(
                    self.createIndex(row, 0),
                    Qt.CheckState.Checked.value
                    if enable
                    else Qt.CheckState.Unchecked.value,
                    Qt.ItemDataRole.CheckStateRole,
                )
            if origin_difficulty != difficulty:
                self.setData(
                    self.createIndex(row, difficulty_column),
                    difficulty,
                    Qt.ItemDataRole.EditRole,
                )


class KindleLemmasTableModel(LemmasTableModel):
    def __init__(self, db: QSqlDatabase, lemma_lang: str) -> None:
        super().__init__(db)
        self.headers = [
            "Sense id",
            _("Enabled"),
            _("Lemma"),
            _("POS"),
            _("Gloss"),
            _("Difficulty"),
            "Example sentence",
            _("Forms"),
        ]
        self.checkable_column = 1
        self.lemma_column = 2
        self.difficulty_column = 5
        self.hide_columns = [0, 6, 7]
        self.tooltip_columns = [2, 4]
        if lemma_lang != "en":
            self.headers.append("display_lemma_id")
            self.editable_columns = [2, 5]
            self.hide_columns.append(8)
        else:
            self.editable_columns = [5]

    def export(
        self, export_path: str, only_enabled: bool, difficulty_limit: int
    ) -> None:
        with open(export_path, "w", encoding="utf-8") as f:
            for enabled, lemma, *_, gloss, difficulty, sentence in self.lemmas:
                if only_enabled and not enabled:
                    continue
                if difficulty > difficulty_limit:
                    continue

                back_text = f"<p>{gloss}</p>"
                if sentence:
                    back_text += f"<i>{base64.b64decode(sentence).decode('utf-8')}</i>"
                f.write(f"{lemma}\t{back_text}\n")


class WiktionaryTableModel(LemmasTableModel):
    def __init__(self, db: QSqlDatabase, lemma_lang: str):
        super().__init__(db)
        self.headers = [
            "id",
            _("Enabled"),
            _("Lemma"),
            _("POS"),
            _("Gloss"),
            "full_def",
            _("Difficulty"),
            "Forms",
            "Example",
        ]
        self.checkable_column = 1
        self.lemma_column = 2
        self.difficulty_column = 6
        self.hide_columns = [0, 5, 7, 8]
        self.editable_columns = [4, 6]
        self.tooltip_columns = [2, 4]
        if lemma_lang == "en":
            self.headers.extend(["General American", "Received Pronunciation"])
            self.hide_columns.extend([9, 10])
        elif lemma_lang == "zh":
            self.headers.extend(["Pinyin", "Bopomofo"])
            self.hide_columns.extend([9, 10])
        else:
            self.headers.append("IPA")
            self.hide_columns.append(9)

    def export(
        self, export_path: str, only_enabled: bool, difficulty_limit: int
    ) -> None:
        with open(export_path, "w", encoding="utf-8") as f:
            for enabled, lemma, *_, gloss, example, _, ipas, difficulty in self.lemmas:
                if only_enabled and not enabled:
                    continue
                if difficulty > difficulty_limit:
                    continue
                back_text = ""
                # if ipas:
                #     back_text += f"<p>{escape(get_ipa(self.lang, ipas))}</p>"
                gloss = escape(re.sub(r"\t|\n", " ", gloss))
                back_text += f"<p>{gloss}</p>"
                if example:
                    example = escape(re.sub(r"\t|\n", " ", example))
                    back_text += f"<i>{example}</i>"
                f.write(f"{lemma}\t{back_text}\n")


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


class ExportOptionsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(_("Set export options"))
        vl = QVBoxLayout()
        self.setLayout(vl)

        text = QLabel(
            _(
                'Export text separated by tab, can be imported to Anki.<br/> "Allow HTML in fields" option needs to be enabled in Anki.'
            )
        )
        vl.addWidget(text)

        self.only_enabled_box = QCheckBox(_("Only export enabled lemmas"))
        vl.addWidget(self.only_enabled_box)

        hl = QHBoxLayout()
        difficulty_label = QLabel(_("Difficulty limit"))
        difficulty_label.setToolTip(
            _("Difficulty higher than this value will not be exported")
        )
        self.difficulty_limit_box = QComboBox()
        self.difficulty_limit_box.addItems(map(str, range(5, 0, -1)))
        hl.addWidget(difficulty_label)
        hl.addWidget(self.difficulty_limit_box)
        vl.addLayout(hl)

        dialog_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_button_box.accepted.connect(self.accept)
        dialog_button_box.rejected.connect(self.reject)
        vl.addWidget(dialog_button_box)


class ImportOptionsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(_("Set import options"))
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.retain_enabled_lemmas = QCheckBox(_("Retain current enabled lemmas"))
        vl.addWidget(self.retain_enabled_lemmas)

        dialog_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_button_box.accepted.connect(self.accept)
        dialog_button_box.rejected.connect(self.reject)
        vl.addWidget(dialog_button_box)
