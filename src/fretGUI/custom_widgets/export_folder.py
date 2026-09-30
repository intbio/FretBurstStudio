"""Folder picker and export button embedded in a node."""

from Qt import QtGui, QtWidgets
from Qt.QtCore import Signal

from fretGUI.custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper


class ExportFolderWidget(QtWidgets.QWidget):
    export_clicked = Signal()
    metadata_clicked = Signal()
    folder_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText('Export folder')
        self.path_edit.setClearButtonEnabled(True)
        self.path_edit.editingFinished.connect(self.folder_changed.emit)

        browse = QtWidgets.QPushButton('Browse')
        browse.clicked.connect(self._browse)

        self.export_button = QtWidgets.QPushButton('Export')
        self.export_button.clicked.connect(self.export_clicked.emit)

        self.metadata_button = QtWidgets.QPushButton('Fill metadata')
        self.metadata_button.clicked.connect(self.metadata_clicked.emit)

        self.metadata_status = QtWidgets.QLabel('No metadata filled.')
        self.metadata_status.setWordWrap(True)

        self.status = QtWidgets.QLabel('No measurements yet')
        self.status.setWordWrap(True)

        folder_row = QtWidgets.QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.addWidget(self.path_edit, stretch=1)
        folder_row.addWidget(browse)

        action_row = QtWidgets.QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addWidget(self.export_button)
        action_row.addWidget(self.metadata_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(folder_row)
        layout.addLayout(action_row)
        layout.addWidget(self.metadata_status)
        layout.addWidget(self.status)
        self.setMinimumWidth(230)

    def folder(self):
        return self.path_edit.text().strip()

    def set_folder(self, path):
        self.path_edit.setText(path or '')

    def set_status(self, text, kind='idle'):
        self.status.setText(text)
        color = {
            'busy': self.palette().color(QtGui.QPalette.Highlight).name(),
            'done': '#2e7d32',
            'error': '#c62828',
        }.get(kind)
        if color:
            self.status.setStyleSheet(f'color: {color};')
        else:
            self.status.setStyleSheet('')

    def set_metadata_status(self, text):
        self.metadata_status.setText(text)

    def set_busy(self, busy):
        self.export_button.setEnabled(not busy)
        self.metadata_button.setEnabled(not busy)
        self.path_edit.setEnabled(not busy)

    def _browse(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            QtWidgets.QApplication.activeWindow(),
            'Export folder',
            self.folder(),
        )
        if path:
            self.set_folder(path)
            self.folder_changed.emit()


class ExportFolderWrapper(AbstractWidgetWrapper):
    export_requested = Signal()
    metadata_requested = Signal()

    def __init__(self, parent=None):
        self.folder_widget = ExportFolderWidget()
        super().__init__(parent)
        self.set_name('export_folder')
        self.set_label('')
        self.set_custom_widget(self.folder_widget)

    def wire_signals(self):
        self.folder_widget.export_clicked.connect(self.export_requested.emit)
        self.folder_widget.metadata_clicked.connect(self.metadata_requested.emit)
        self.folder_widget.folder_changed.connect(self.widget_changed_signal.emit)

    def get_value(self):
        return self.folder_widget.folder()

    def set_value(self, value):
        self.folder_widget.set_folder('' if value is None else str(value))

    def set_status(self, text, kind='idle'):
        self.folder_widget.set_status(text, kind)

    def set_metadata_status(self, text):
        self.folder_widget.set_metadata_status(text)

    def set_busy(self, busy):
        self.folder_widget.set_busy(busy)

    def folder(self):
        return self.folder_widget.folder()
