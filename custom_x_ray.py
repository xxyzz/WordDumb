import json
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from .custom_lemmas import ComboBoxDelegate
from .x_ray_share import get_custom_x_path

load_translations()  # type: ignore
if TYPE_CHECKING:
    _: Any


NER_LABEL_EXPLANATIONS = {
    "EVENT": _("Named hurricanes, battles, wars, sports events, etc."),
    "FAC": _("Buildings, airports, highways, bridges, etc."),
    "GPE": _("Countries, cities, states"),
    "LAW": _("Named documents made into laws"),
    "LOC": _("Non-GPE locations, mountain ranges, bodies of water"),
    "ORG": _("Companies, agencies, institutions, etc."),
    "PERSON": _("People, including fictional"),
    "PRODUCT": _("Objects, vehicles, foods, etc. (not services)"),
    "MISC": _("Miscellaneous"),
    "PER": _("People, including fictional"),
    "DERIV_PER": _("Personal possessive adjectives"),
    "PS": _("Individual or group"),
    "LC": _("District/province or geographical location"),
    "OG": _("Organization or enterprise"),
    "EVT": _("Event"),
    "GPE_LOC": _("Geo-political entity, with a locative sense"),
    "GPE_ORG": _("Geo-political entity, with an organisation sense"),
    "PROD": _("Product"),
    "geogName": _("Historical and geographical regions, natural structures"),
    "orgName": _("Organizations, institutions, companies"),
    "persName": _("People, including fictional"),
    "placeName": _("Geopolitical names"),
    "ORGANIZATION": _("Organization"),
    "EVN": _("Well-known events and celebrations"),
    "PRS": _("People, including fictional"),
}
WIKINER_LABELS = ["LOC", "MISC", "ORG", "PER"]
ONTONOTES_LABELS = ["EVENT", "FAC", "GPE", "LAW", "LOC", "ORG", "PERSON", "PRODUCT"]
NER_LABELS = {
    "ca": WIKINER_LABELS,
    "zh": ONTONOTES_LABELS,
    "hr": ["DERIV_PER", "LOC", "MISC", "ORG", "PER"],
    "da": WIKINER_LABELS,
    "nl": ONTONOTES_LABELS,
    "en": ONTONOTES_LABELS,
    "fi": ONTONOTES_LABELS,
    "fr": WIKINER_LABELS,
    "de": WIKINER_LABELS,
    "el": ["EVENT", "GPE", "LOC", "ORG", "PERSON", "PRODUCT"],
    "it": WIKINER_LABELS,
    "ja": ONTONOTES_LABELS,
    "ko": ["PS", "LC", "OG"],
    "lt": ["GPE", "LOC", "ORG", "PERSON", "PRODUCT"],
    "mk": ONTONOTES_LABELS,
    "nb": ["EVT", "GPE_LOC", "GPE_ORG", "LOC", "MISC", "ORG", "PER", "PROD"],
    "pl": ["geogName", "orgName", "persName", "placeName"],
    "pt": WIKINER_LABELS,
    "ro": ["EVENT", "GPE", "LOC", "ORGANIZATION", "PERSON", "PRODUCT"],
    "ru": ["LOC", "ORG", "PER"],
    "sl": ["DERIV_PER", "LOC", "MISC", "ORG", "PER"],
    "es": WIKINER_LABELS,
    "sv": ["EVN", "LOC", "ORG", "PRS"],
    "uk": ["LOC", "ORG", "PER"],
}

DESC_SOURCES = {
    None: _("Book quote"),
    1: _("Wikipedia"),
    2: _("Other MediaWiki server"),
}


class CustomXRayDialog(QDialog):
    def __init__(
        self, lang: str, book_path: str, title: str, parent: Any = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Customize X-Ray for {}").format(title))
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.x_ray_table = QTableView(self)
        self.x_ray_table.setAlternatingRowColors(True)
        self.x_ray_model = XRayTableModel(book_path)
        self.x_ray_table.setModel(self.x_ray_model)
        ner_labels = NER_LABELS[lang]
        self.x_ray_table.setItemDelegateForColumn(
            1,
            ComboBoxDelegate(
                self.x_ray_table,
                list(ner_labels),
                {
                    idx: NER_LABEL_EXPLANATIONS.get(label, label)
                    for idx, label in enumerate(ner_labels)
                },
            ),
        )
        self.x_ray_table.setItemDelegateForColumn(
            4, ComboBoxDelegate(self.x_ray_table, DESC_SOURCES)
        )
        self.x_ray_table.horizontalHeader().setMaximumSectionSize(400)
        self.x_ray_table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        self.x_ray_table.hideColumn(6)
        self.x_ray_table.resizeColumnsToContents()
        vl.addWidget(self.x_ray_table)

        search_line = QLineEdit()
        search_line.setPlaceholderText(_("Search"))
        search_line.textChanged.connect(lambda: self.search_x_ray(search_line.text()))
        vl.addWidget(search_line)

        edit_buttons = QHBoxLayout()
        add_button = QPushButton(QIcon.ic("plus.png"), _("Add"))
        add_button.clicked.connect(self.add_x_ray)
        edit_buttons.addWidget(add_button)
        delete_button = QPushButton(QIcon.ic("minus.png"), _("Delete"))
        delete_button.clicked.connect(self.delete_x_ray)
        edit_buttons.addWidget(delete_button)
        edit_button = QPushButton(QIcon.ic("edit_input.png"), _("Edit"))
        edit_button.clicked.connect(self.edit_x_ray)
        edit_buttons.addWidget(edit_button)
        vl.addLayout(edit_buttons)

        save_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button_box.accepted.connect(self.accept)
        save_button_box.rejected.connect(self.reject)
        vl.addWidget(save_button_box)

    def search_x_ray(self, text: str) -> None:
        if matches := self.x_ray_model.match(
            self.x_ray_model.index(0, 0), Qt.ItemDataRole.DisplayRole, text
        ):
            self.x_ray_table.setCurrentIndex(matches[0])
            self.x_ray_table.scrollTo(matches[0])

    def add_x_ray(self) -> None:
        self.open_edit_dlg(True)

    def delete_x_ray(self) -> None:
        self.x_ray_model.delete_data(self.x_ray_table.selectedIndexes())
        self.x_ray_table.resizeColumnsToContents()

    def edit_x_ray(self) -> None:
        self.open_edit_dlg(False)

    def open_edit_dlg(self, is_new: bool):
        add_x_dlg = None
        row = 0
        if is_new:
            add_x_dlg = AddXRayDialog(self)
        else:
            for row in sorted(
                [
                    index.row()
                    for index in self.x_ray_table.selectedIndexes()
                    if index.row() >= 0
                ],
                reverse=True,
            ):
                add_x_dlg = AddXRayDialog(self, self.x_ray_model.x_ray_data[row])
                break
        if (
            add_x_dlg is not None
            and add_x_dlg.exec()
            and (name := add_x_dlg.name_line.text())
        ):
            new_data = [
                name,
                add_x_dlg.ner_label.currentData(),
                add_x_dlg.aliases.text(),
                add_x_dlg.description.toPlainText(),
                add_x_dlg.source.currentData(),
                add_x_dlg.omit.isChecked(),
                "",
            ]
            if is_new:
                self.x_ray_model.insert_data(new_data)
            else:
                self.x_ray_model.x_ray_data[row] = new_data
            self.x_ray_table.resizeColumnsToContents()


class XRayTableModel(QAbstractTableModel):
    def __init__(self, book_path: str) -> None:
        super().__init__()
        self.custom_path = get_custom_x_path(book_path)
        if self.custom_path.exists():
            with open(self.custom_path, encoding="utf-8") as f:
                self.x_ray_data = json.load(f)
        else:
            self.x_ray_data = []
        self.headers = [
            _("Name"),
            _("Named entity label"),
            _("Aliases"),
            _("Description"),
            _("Description source"),
            _("Omit"),
            _("Book quote"),
        ]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        row = index.row()
        column = index.column()
        value = self.x_ray_data[row][column]
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return value
        elif role == Qt.ItemDataRole.ToolTipRole and column == 3:
            return value
        elif role == Qt.ItemDataRole.CheckStateRole and column == 5:
            new_value = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
            if isinstance(new_value, int):  # PyQt5
                return new_value
            else:  # PyQt6 Enum
                return new_value.value

    def rowCount(self, index):
        return len(self.x_ray_data)

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
        if index.column() == 5:
            flag |= Qt.ItemFlag.ItemIsUserCheckable
        else:
            flag |= Qt.ItemFlag.ItemIsEditable
        return flag

    def setData(self, index, value, role):
        if not index.isValid():
            return False
        row = index.row()
        column = index.column()
        if role == Qt.ItemDataRole.EditRole:
            self.x_ray_data[row][column] = value
            self.dataChanged.emit(index, index, [role])
            return True
        elif role == Qt.ItemDataRole.CheckStateRole and column == 5:
            checked_value = (
                Qt.CheckState.Checked
                if isinstance(Qt.CheckState.Checked, int)
                else Qt.CheckState.Checked.value
            )
            self.x_ray_data[row][column] = value == checked_value
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def insert_data(self, data):
        index = QModelIndex()
        self.beginInsertRows(index, self.rowCount(index), self.rowCount(index))
        self.x_ray_data.append(data)
        self.endInsertRows()

    def delete_data(self, indexes):
        for row in sorted(
            [index.row() for index in indexes if index.row() >= 0], reverse=True
        ):
            self.beginRemoveRows(QModelIndex(), row, row)
            self.x_ray_data.pop(row)
            self.endRemoveRows()

    def save_data(self) -> None:
        with open(self.custom_path, "w", encoding="utf-8") as f:
            json.dump(self.x_ray_data, f, indent=2, ensure_ascii=False)


class AddXRayDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle(
            _("Add new X-Ray data") if data is None else _("Edit X-Ray data")
        )
        vl = QVBoxLayout()
        self.setLayout(vl)

        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.name_line = QLineEdit()
        form_layout.addRow(_("Name"), self.name_line)
        if data is not None:
            self.name_line.setText(data[0])

        self.ner_label = QComboBox()
        for index, (label, exp) in zip(
            range(len(NER_LABEL_EXPLANATIONS)), NER_LABEL_EXPLANATIONS.items()
        ):
            self.ner_label.addItem(label, label)
            self.ner_label.setItemData(index, exp, Qt.ItemDataRole.ToolTipRole)
        form_layout.addRow(_("NER label"), self.ner_label)
        if data is not None:
            self.ner_label.setCurrentText(data[1])

        self.aliases = QLineEdit()
        self.aliases.setPlaceholderText(_('Separate by ","'))
        form_layout.addRow(_("Aliases"), self.aliases)
        if data is not None:
            self.aliases.setText(data[2])

        self.description = QPlainTextEdit()
        form_layout.addRow(_("Description"), self.description)
        self.description.setPlaceholderText(
            _(
                "Leave this empty to use description from Wikipedia or other "
                "MediaWiki server"
            )
        )
        if data is not None:
            self.description.setPlainText(data[3])

        self.source = QComboBox()
        for value, text in DESC_SOURCES.items():
            self.source.addItem(text, value)
        form_layout.addRow(_("Description source"), self.source)
        if data is not None:
            self.source.setCurrentText(DESC_SOURCES[data[4]])

        self.omit = QCheckBox()
        form_layout.addRow(_("Omit"), self.omit)
        if data is not None:
            self.omit.setChecked(data[5])
            if len(data[6]) > 0:
                quote = QPlainTextEdit()
                quote.setReadOnly(True)
                quote.setPlainText(data[6])
                form_layout.addRow(_("Book quote"), quote)

        confirm_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        confirm_button_box.accepted.connect(self.accept)
        confirm_button_box.rejected.connect(self.reject)
        vl.addLayout(form_layout)
        vl.addWidget(confirm_button_box)
        self.setLayout(vl)
