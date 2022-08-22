#!/usr/bin/env python3

import base64
import json
import pickle
import re
import shutil
import sqlite3
from html import escape
from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, Qt, QVariant
from PyQt6.QtGui import QIcon
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

from .dump_wiktionary import get_ipa
from .import_lemmas import extract_apkg, extract_csv, query_vocabulary_builder
from .utils import (
    custom_kindle_dump_path,
    custom_lemmas_folder,
    get_klld_path,
    get_lemmas_tst_path,
    get_plugin_path,
    load_json_or_pickle,
    load_lemmas_dump,
    wiktionary_json_path,
)

load_translations()


class CustomLemmasDialog(QDialog):
    def __init__(self, parent, lang=None, lang_name=None):
        super().__init__(parent)
        self.lang = lang
        window_title = _("Customize")
        if lang:
            window_title += f" {lang_name} "
            window_title += _("Wiktionary")
        else:
            window_title += " "
            window_title += _("Kindle Word Wise")
        self.setWindowTitle(window_title)
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.lemmas_table = QTableView()
        self.lemmas_table.setAlternatingRowColors(True)
        self.lemmas_model = (
            WiktionaryTableModel(lang) if lang else KindleLemmasTableModel()
        )
        self.lemmas_table.setModel(self.lemmas_model)
        self.lemmas_table.setItemDelegateForColumn(
            8 if lang else 5,
            ComboBoxDelegate(
                self.lemmas_table,
                list(range(1, 6)),
                {0: _("Fewer Hints"), 4: _("More Hints")},
            ),
        )
        if lang is None:
            self.lemmas_table.hideColumn(2)
            self.lemmas_table.hideColumn(6)
        else:
            self.lemmas_table.hideColumn(5)
        self.lemmas_table.horizontalHeader().setMaximumSectionSize(400)
        self.lemmas_table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self.lemmas_table.resizeColumnsToContents()
        vl.addWidget(self.lemmas_table)

        search_line = QLineEdit()
        search_line.setPlaceholderText(_("Search"))
        search_line.textChanged.connect(lambda: self.search_lemma(search_line.text()))
        vl.addWidget(search_line)

        if lang in ["en", "zh"]:
            from .config import prefs

            self.ipa_button = QComboBox()
            if lang == "en":
                self.ipa_button.addItems(["US", "UK"])
                self.ipa_button.setCurrentText(prefs["en_ipa"])
            elif lang == "zh":
                self.ipa_button.addItem(_("Pinyin"), "Pinyin")
                self.ipa_button.addItem(_("Bopomofo"), "bopomofo")
                self.ipa_button.setCurrentText(_(prefs["zh_ipa"]))

            hl = QHBoxLayout()
            hl.addWidget(
                QLabel(
                    _("Phonetic transcription system")
                    if lang == "zh"
                    else _("International Phonetic Alphabet")
                )
            )
            self.ipa_button.currentIndexChanged.connect(self.change_ipa)
            hl.addWidget(self.ipa_button)
            vl.addLayout(hl)

        if lang:
            from .config import prefs

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
                str(prefs[f"{lang}_wiktionary_difficulty_limit"])
            )
            self.difficulty_limit_box.currentIndexChanged.connect(
                self.change_difficulty_limit
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

    def search_lemma(self, text):
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
        if self.lang is None:
            custom_path = custom_kindle_dump_path(plugin_path)
            if custom_path.exists():
                custom_path.unlink()
                self.reject()
        else:
            custom_folder = custom_lemmas_folder(plugin_path).joinpath(self.lang)
            shutil.rmtree(custom_folder)
            self.reject()

    def change_ipa(self):
        from .config import prefs

        if self.lang == "en":
            prefs["en_ipa"] = self.ipa_button.currentText()
        elif self.lang == "zh":
            prefs["zh_ipa"] = self.ipa_button.currentData()

        self.lemmas_model.change_ipa()

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
        self.lemmas_model.change_difficulty_limit(limit)


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
            return get_ipa(self.lang, value)
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
            if isinstance(self, KindleLemmasTableModel) or column == 8:
                value = int(value)
            self.lemmas[index.row()][column] = value
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def import_lemmas(
        self, lemmas_dict: dict[str, list[int, bool]], retain_lemmas: bool
    ) -> None:
        if isinstance(self, KindleLemmasTableModel):
            difficulty_column = 5
        else:
            difficulty_column = 8

        for row in range(self.rowCount(None)):
            lemma = self.lemmas[row][1]
            enable = Qt.CheckState.Unchecked.value
            difficulty = 1
            if retain_lemmas:
                if self.lemmas[row][0]:
                    enable = Qt.CheckState.Checked.value
                else:
                    enable = Qt.CheckState.Unchecked.value
                difficulty = self.lemmas[row][difficulty_column]

            data = lemmas_dict.get(lemma)
            if data and data[1]:
                enable = Qt.CheckState.Checked.value
                difficulty = data[0]
                lemmas_dict[lemma][1] = False
            self.setData(
                self.createIndex(row, 0), enable, Qt.ItemDataRole.CheckStateRole
            )
            self.setData(
                self.createIndex(row, difficulty_column),
                difficulty,
                Qt.ItemDataRole.EditRole,
            )


class KindleLemmasTableModel(LemmasTableModel):
    def __init__(self):
        super().__init__()
        plugin_path = get_plugin_path()
        kw_processor = load_lemmas_dump(plugin_path)
        self.lemmas = []
        klld_conn = sqlite3.connect(get_klld_path(plugin_path))
        sense_ids = set()
        for ignore, sense_id in kw_processor.get_all_keywords().values():
            sense_ids.add(sense_id)

        self.pos_types = {}
        for pos_type_id, pos_type_lable in klld_conn.execute("SELECT * FROM pos_types"):
            self.pos_types[pos_type_id] = pos_type_lable

        lemmas_tst_path = get_lemmas_tst_path(plugin_path, None)
        if lemmas_tst_path.exists():
            self.lemmas_tst = load_json_or_pickle(None, lemmas_tst_path)
        else:
            from tst import TST

            self.lemmas_tst = TST()
            row_num = 0
            lemmas_row = []
            added_lemmas = set()

        for (
            lemma,
            sense_id,
            short_def,
            full_def,
            pos_type,
            sentence,
        ) in klld_conn.execute(
            'SELECT lemma, senses.id, short_def, full_def, pos_type, example_sentence FROM lemmas JOIN senses ON lemmas.id = display_lemma_id WHERE (full_def IS NOT NULL OR short_def IS NOT NULL) AND lemma NOT like "-%" ORDER BY lemma'
        ):
            enabled = False
            difficulty = 1
            if sense_id in sense_ids:
                enabled = True
            if lemma in kw_processor:
                difficulty = kw_processor.get_keyword(lemma)[0]
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
                    sentence,
                ]
            )
            if not lemmas_tst_path.exists():
                if lemma not in added_lemmas:
                    lemmas_row.append((lemma, row_num))
                    added_lemmas.add(lemma)
                row_num += 1

        klld_conn.close()
        self.headers = [
            _("Enabled"),
            _("Lemma"),
            "Sense id",
            _("POS"),
            _("Definition"),
            _("Difficulty"),
            "Example sentence",
        ]
        self.editable_columns = [5]
        self.tooltip_columns = [4]
        if not lemmas_tst_path.exists():
            self.lemmas_tst.put_values(lemmas_row)
            with lemmas_tst_path.open("wb") as f:
                pickle.dump(self.lemmas_tst, f)

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
            _("Enabled"),
            _("Lemma"),
            _("POS"),
            _("Gloss"),
            _("Definition"),
            "Example",
            _("Forms"),
            "IPA",
            _("Difficulty"),
        ]
        self.editable_columns = [3, 4, 8]
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
                if ipas:
                    back_text += f"<p>{escape(get_ipa(self.lang, ipas))}</p>"
                gloss = escape(re.sub(r"\t|\n", " ", gloss))
                back_text += f"<p>{gloss}</p>"
                if example:
                    example = escape(re.sub(r"\t|\n", " ", example))
                    back_text += f"<i>{example}</i>"
                f.write(f"{lemma}\t{back_text}\n")

    def change_difficulty_limit(self, limit: int) -> None:
        for row in range(self.rowCount(None)):
            currently_enabled = self.lemmas[row][0]
            difficulty = self.lemmas[row][8]
            enabled = currently_enabled
            if difficulty > limit:
                enabled = False
            elif not currently_enabled and difficulty > 1:
                enabled = True

            if currently_enabled != enabled:
                self.lemmas[row][0] = enabled
                index = self.createIndex(row, 0)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])


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
