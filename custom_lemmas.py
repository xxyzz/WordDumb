#!/usr/bin/env python3

import base64
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QModelIndex, QObject, Qt, QVariant
from PyQt6.QtGui import QIcon
from PyQt6.QtSql import (
    QSqlDatabase,
    QSqlRelation,
    QSqlRelationalTableModel,
    QSqlTableModel,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
)

from .error_dialogs import device_not_found_dialog, ww_db_not_found_dialog
from .send_file import copy_klld_from_android, copy_klld_from_kindle, device_connected
from .utils import (
    custom_lemmas_folder,
    get_klld_path,
    get_plugin_path,
    load_languages_data,
)

load_translations()  # type: ignore
if TYPE_CHECKING:
    _: Any


class CustomLemmasDialog(QDialog):
    def __init__(
        self,
        parent: QObject,
        is_kindle: bool,
        lemma_lang: str,
        gloss_lang: str,
        db_path: Path,
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
        self.init_sql_table(is_kindle)
        vl.addWidget(self.lemmas_table)
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        vl.addLayout(form_layout)
        self.init_filters(form_layout)
        if not is_kindle:
            self.init_wiktionary_buttons(form_layout, gloss_lang)
        vl.addWidget(self.init_dialog_buttons())

    def init_sql_table(self, is_kindle: bool) -> None:
        self.lemmas_table = QTableView()
        self.lemmas_table.setAlternatingRowColors(True)
        if is_kindle:
            self.check_empty_kindle_gloss()
        self.db_connection_name = "lemmas_connection"
        db = QSqlDatabase.addDatabase("QSQLITE", self.db_connection_name)
        db.setDatabaseName(str(self.db_path))
        db.open()
        self.lemmas_model: LemmasTableModel = LemmasTableModel(db, is_kindle)
        self.lemmas_model.setEditStrategy(QSqlTableModel.EditStrategy.OnFieldChange)
        self.lemmas_model.setTable("senses")
        self.lemmas_model.setRelation(
            self.lemmas_model.lemma_column, QSqlRelation("lemmas", "id", "lemma")
        )
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

    def init_filters(self, form_layout: QFormLayout) -> None:
        self.filter_lemma_line = QLineEdit()
        self.filter_lemma_line.textChanged.connect(self.filter_data)
        form_layout.addRow(_("Filter lemma"), self.filter_lemma_line)

        self.filter_enabled_box = QComboBox()
        self.filter_enabled_box.addItem(_("All"), "all")
        self.filter_enabled_box.addItem(_("Enabled"), "enabled")
        self.filter_enabled_box.addItem(_("Disabled"), "disabled")
        self.filter_enabled_box.currentIndexChanged.connect(self.filter_data)
        form_layout.addRow(_("Filter enabled"), self.filter_enabled_box)

        self.filter_difficulty_box = QComboBox()
        self.filter_difficulty_box.addItem(_("All"), "all")
        for difficulty_level in range(5, 0, -1):
            self.filter_difficulty_box.addItem(str(difficulty_level), difficulty_level)
        self.filter_difficulty_box.currentIndexChanged.connect(self.filter_data)
        form_layout.addRow(_("Filter difficulty"), self.filter_difficulty_box)

    def init_wiktionary_buttons(
        self, form_layout: QFormLayout, gloss_lang: str
    ) -> None:
        from .config import prefs

        supported_languages = load_languages_data(get_plugin_path())
        if (
            self.lemma_lang in ["en", "zh"]
            and supported_languages[gloss_lang]["gloss_source"] == "kaikki"
        ):
            self.ipa_button = QComboBox()
            if self.lemma_lang == "en":
                self.ipa_button.addItem(_("General American"), "ga_ipa")
                self.ipa_button.addItem(_("Received Pronunciation"), "rp_ipa")
                self.ipa_button.setCurrentText(prefs["en_ipa"])
            elif self.lemma_lang == "zh":
                self.ipa_button.addItem(_("Pinyin"), "pinyin")
                self.ipa_button.addItem(_("Bopomofo"), "bopomofo")
                self.ipa_button.setCurrentText(_(prefs["zh_ipa"]))

            form_layout.addRow(
                _("Phonetic transcription system")
                if self.lemma_lang == "zh"
                else _("International Phonetic Alphabet"),
                self.ipa_button,
            )
            self.ipa_button.currentIndexChanged.connect(self.change_ipa)

        difficulty_label = QLabel(_("Difficulty limit"))
        difficulty_label.setToolTip(
            _(
                "Difficult words have lower value. Words have difficulty value higher "
                "than this value are disabled."
            )
        )
        self.difficulty_limit_box = QComboBox()
        self.difficulty_limit_box.addItems(map(str, range(5, 0, -1)))
        self.difficulty_limit_box.setCurrentText(
            str(prefs[f"{self.lemma_lang}_wiktionary_difficulty_limit"])
        )
        self.difficulty_limit_box.currentIndexChanged.connect(
            self.change_difficulty_limit
        )
        form_layout.addRow(difficulty_label, self.difficulty_limit_box)

    def init_dialog_buttons(self) -> QDialogButtonBox:
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
        return dialog_button_box

    def check_empty_kindle_gloss(self) -> None:
        custom_db_conn = sqlite3.connect(self.db_path)
        for (gloss,) in custom_db_conn.execute("SELECT short_def FROM senses LIMIT 1"):
            empty_gloss = len(gloss) == 0
        if not empty_gloss:
            custom_db_conn.close()
            return
        plugin_path = get_plugin_path()
        klld_path = get_klld_path(plugin_path)
        if klld_path is None:
            gui = self.parent().parent()
            package_name = device_connected(gui, "KFX")
            if not package_name:
                device_not_found_dialog(self)
                return
            custom_folder = custom_lemmas_folder(plugin_path)
            if isinstance(package_name, str):
                copy_klld_from_android(package_name, custom_folder)
            else:
                copy_klld_from_kindle(gui, custom_folder)

        klld_path = get_klld_path(plugin_path)
        if klld_path is None:
            ww_db_not_found_dialog(self)
            return

        klld_conn = sqlite3.connect(klld_path)
        for sense_id, short_def, full_def, example in klld_conn.execute(
            """
            SELECT senses.id, short_def, full_def, example_sentence
            FROM lemmas JOIN senses ON lemmas.id = display_lemma_id
            WHERE (full_def IS NOT NULL OR short_def IS NOT NULL)
            AND lemma NOT like '-%'
            """
        ):
            short_def = base64.b64decode(short_def if short_def else full_def).decode(
                "utf-8"
            )
            full_def = base64.b64decode(full_def).decode("utf-8") if full_def else ""
            example = base64.b64decode(example).decode("utf-8") if example else ""
            custom_db_conn.execute(
                "UPDATE senses SET short_def = ?, full_def = ?, example = ? "
                "WHERE id = ?",
                (short_def, full_def, example, sense_id),
            )
        klld_conn.close()
        custom_db_conn.commit()
        custom_db_conn.close()

    def filter_data(self) -> None:
        filter_lemma = self.filter_lemma_line.text()
        filter_enabled = self.filter_enabled_box.currentData()
        filter_difficulty = self.filter_difficulty_box.currentData()
        filter_sql = (
            f"relTblAl_{self.lemmas_model.lemma_column}.lemma LIKE '{filter_lemma}%'"
            if filter_lemma
            else ""
        )
        if filter_enabled != "all":
            if filter_sql:
                filter_sql += " AND "
            filter_sql += f"enabled = {1 if filter_enabled == 'enabled' else 0}"
        if filter_difficulty != "all":
            if filter_sql:
                filter_sql += " AND "
            filter_sql += f"difficulty = {filter_difficulty}"
        self.lemmas_model.setFilter(filter_sql)
        self.lemmas_model.select()

    def select_import_file(self) -> None:
        import_options_dialog = ImportOptionsDialog(self)
        if not import_options_dialog.exec():
            return

        file_path, ignored_ = QFileDialog.getOpenFileName(
            self,
            _("Select import file"),
            str(Path.home()),
            "Anki Deck Package (*.apkg);;CSV (*.csv);;Kindle Vocabulary Builder (*.db)",
        )
        self.import_lemmas_path = file_path
        self.retain_enabled_lemmas = (
            import_options_dialog.retain_enabled_lemmas.isChecked()
        )
        self.reject()

    def reset_lemmas(self):
        QSqlDatabase.removeDatabase(self.db_connection_name)
        self.db_path.unlink()
        self.reject()

    def change_ipa(self):
        from .config import prefs

        prefs[f"{self.lemma_lang}_ipa"] = self.ipa_button.currentData()

    def set_export_options(self):
        option_dialog = ExportOptionsDialog(self)
        if not option_dialog.exec():
            return

        export_path, ignored_ = QFileDialog.getSaveFileName(
            self, _("Set export file path"), str(Path.home())
        )
        if not export_path:
            return

        self.export_path = export_path
        self.only_export_enabled = option_dialog.only_enabled_box.isChecked()
        self.export_difficulty_limit = int(
            option_dialog.difficulty_limit_box.currentText()
        )
        self.reject()

    def change_difficulty_limit(self):
        from .config import prefs

        limit = int(self.difficulty_limit_box.currentText())
        prefs[f"{self.lemma_lang}_wiktionary_difficulty_limit"] = limit


class LemmasTableModel(QSqlRelationalTableModel):
    def __init__(self, db: QSqlDatabase, is_kindle: bool) -> None:
        super().__init__(db=db)
        self.headers = [
            "sense_id",
            _("Enabled"),
            _("Lemma"),
            _("POS"),
            _("Gloss"),
            "full_def",
            "example",
            _("Difficulty"),
        ]
        self.checkable_column = 1
        self.lemma_column = 2
        self.difficulty_column = 7
        self.hide_columns = [0, 5, 6]
        self.tooltip_columns = [2, 4]
        self.editable_columns = [7] if is_kindle else [4, 7]

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
                "Export text separated by tab, can be imported to Anki.<br/> "
                '"Allow HTML in fields" option needs to be enabled in Anki.'
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
        self.retain_enabled_lemmas.setCheckState(Qt.CheckState.Checked)
        vl.addWidget(self.retain_enabled_lemmas)

        dialog_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_button_box.accepted.connect(self.accept)
        dialog_button_box.rejected.connect(self.reject)
        vl.addWidget(dialog_button_box)
