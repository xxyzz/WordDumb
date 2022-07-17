#!/usr/bin/env python3

import json

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
from .utils import get_custom_x_path

NER_LABEL_EXPLANATIONS = {
    "EVENT": "Named hurricanes, battles, wars, sports events, etc.",
    "FAC": "Buildings, airports, highways, bridges, etc.",
    "GPE": "Countries, cities, states",
    "LAW": "Named documents made into laws",
    "LOC": "Non-GPE locations, mountain ranges, bodies of water",
    "ORG": "Companies, agencies, institutions, etc.",
    "PERSON": "People, including fictional",
    "PRODUCT": "Objects, vehicles, foods, etc. (not services)",
}

DESC_SOURCES = {None: "Book quote", 1: "Wikipedia", 2: "Fandom"}


class CustomXRayDialog(QDialog):
    def __init__(self, book_path, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Customize X-Ray for {title}")
        vl = QVBoxLayout()
        self.setLayout(vl)

        self.x_ray_table = QTableView()
        self.x_ray_table.setAlternatingRowColors(True)
        self.x_ray_model = XRayTableModle(book_path)
        self.x_ray_table.setModel(self.x_ray_model)
        self.x_ray_table.setItemDelegateForColumn(
            1,
            ComboBoxDelegate(
                self.x_ray_table,
                list(NER_LABEL_EXPLANATIONS.keys()),
                {
                    i: exp
                    for i, exp in zip(
                        range(len(NER_LABEL_EXPLANATIONS)),
                        NER_LABEL_EXPLANATIONS.values(),
                    )
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
        self.x_ray_table.resizeColumnsToContents()
        vl.addWidget(self.x_ray_table)

        search_line = QLineEdit()
        search_line.setPlaceholderText("Search")
        search_line.textChanged.connect(lambda: self.search_x_ray(search_line.text()))
        vl.addWidget(search_line)

        edit_buttons = QHBoxLayout()
        add_button = QPushButton(QIcon.ic("plus.png"), "Add")
        add_button.clicked.connect(self.add_x_ray)
        delete_button = QPushButton(QIcon.ic("minus.png"), "Delete")
        delete_button.clicked.connect(self.delete_x_ray)
        edit_buttons.addWidget(add_button)
        edit_buttons.addWidget(delete_button)
        vl.addLayout(edit_buttons)

        save_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button_box.accepted.connect(self.accept)
        save_button_box.rejected.connect(self.reject)
        vl.addWidget(save_button_box)

    def search_x_ray(self, text):
        if matches := self.x_ray_model.match(
            self.x_ray_model.index(0, 0), Qt.ItemDataRole.DisplayRole, text
        ):
            self.x_ray_table.setCurrentIndex(matches[0])
            self.x_ray_table.scrollTo(matches[0])

    def add_x_ray(self):
        add_x_dlg = AddXRayDialog(self)
        if add_x_dlg.exec() and (name := add_x_dlg.name_line.text()):
            self.x_ray_model.insert_data(
                [
                    name,
                    add_x_dlg.ner_label.currentData(),
                    add_x_dlg.aliases.text(),
                    add_x_dlg.description.toPlainText(),
                    add_x_dlg.source.currentData(),
                    add_x_dlg.omit.isChecked(),
                ]
            )
            self.x_ray_table.resizeColumnsToContents()

    def delete_x_ray(self):
        self.x_ray_model.delete_data(self.x_ray_table.selectedIndexes())
        self.x_ray_table.resizeColumnsToContents()


class XRayTableModle(QAbstractTableModel):
    def __init__(self, book_path):
        super().__init__()
        self.custom_path = get_custom_x_path(book_path)
        if self.custom_path.exists():
            with open(self.custom_path, encoding="utf-8") as f:
                self.x_ray_data = json.load(f)
        else:
            self.x_ray_data = []
        self.headers = [
            "Name",
            "Named entity label",
            "Aliases",
            "Description",
            "Description source",
            "Omit",
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

    def save_data(self):
        with open(self.custom_path, "w", encoding="utf-8") as f:
            json.dump(self.x_ray_data, f, indent=2, ensure_ascii=False)


class AddXRayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add new X-Ray data")
        vl = QVBoxLayout()
        self.setLayout(vl)

        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.name_line = QLineEdit()
        form_layout.addRow("Name", self.name_line)

        self.ner_label = QComboBox()
        for index, (label, exp) in zip(
            range(len(NER_LABEL_EXPLANATIONS)), NER_LABEL_EXPLANATIONS.items()
        ):
            self.ner_label.addItem(label, label)
            self.ner_label.setItemData(index, exp, Qt.ItemDataRole.ToolTipRole)
        form_layout.addRow("NER label", self.ner_label)

        self.aliases = QLineEdit()
        self.aliases.setPlaceholderText('Separate by ","')
        form_layout.addRow("Aliases", self.aliases)

        self.description = QPlainTextEdit()
        form_layout.addRow("Description", self.description)
        self.description.setPlaceholderText(
            "Leave this empty to use description from Wikipedia or Fandom"
        )

        self.source = QComboBox()
        for value, text in DESC_SOURCES.items():
            self.source.addItem(text, value)
        form_layout.addRow("Description source", self.source)

        self.omit = QCheckBox()
        form_layout.addRow("Omit", self.omit)

        confirm_button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        confirm_button_box.accepted.connect(self.accept)
        confirm_button_box.rejected.connect(self.reject)
        vl.addLayout(form_layout)
        vl.addWidget(confirm_button_box)
        self.setLayout(vl)
