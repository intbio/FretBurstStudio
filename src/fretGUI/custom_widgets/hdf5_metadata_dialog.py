"""Form for the descriptive Photon-HDF5 fields stored with an export."""

from Qt import QtWidgets

from fretGUI.photon_hdf5_metadata import METADATA_FIELDS, normalize_metadata


class PhotonHdf5MetadataDialog(QtWidgets.QDialog):
    """Edit metadata that is written onto every file in an export."""

    def __init__(self, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Photon-HDF5 metadata')
        self.setModal(True)
        self._editors = {}
        values = normalize_metadata(fields)

        root = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel(
            'Filled values are written onto every exported file and remembered '
            'for next time. Leave a field blank to keep that measurement\'s own value.'
        )
        note.setWordWrap(True)
        root.addWidget(note)

        current_section = None
        form = None
        self._use_filename = None
        for spec in METADATA_FIELDS:
            if spec.get('checkbox'):
                continue
            if spec['section'] != current_section:
                current_section = spec['section']
                box = QtWidgets.QGroupBox(current_section)
                form = QtWidgets.QFormLayout(box)
                root.addWidget(box)
            editor = self._editor(spec, values[spec['key']])
            self._editors[spec['key']] = editor
            if spec['key'] == 'sample_name':
                form.addRow(spec['label'], self._sample_name_row(editor, values))
            else:
                form.addRow(spec['label'], editor)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.resize(460, 640)

    def values(self):
        stored = {}
        for key, editor in self._editors.items():
            if isinstance(editor, QtWidgets.QPlainTextEdit):
                stored[key] = editor.toPlainText()
            else:
                stored[key] = editor.text()
        if self._use_filename is not None:
            stored['sample_name_from_filename'] = (
                '1' if self._use_filename.isChecked() else ''
            )
        return stored

    def _sample_name_row(self, editor, values):
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(editor, stretch=1)
        checkbox = QtWidgets.QCheckBox('Use filename')
        checkbox.setToolTip('Use each file name as the sample name.')
        checkbox.setChecked(values.get('sample_name_from_filename') == '1')
        checkbox.toggled.connect(editor.setDisabled)
        editor.setDisabled(checkbox.isChecked())
        layout.addWidget(checkbox)
        self._use_filename = checkbox
        return row

    def _editor(self, spec, value):
        if spec.get('multiline'):
            editor = QtWidgets.QPlainTextEdit()
            editor.setPlainText(value)
            editor.setFixedHeight(64)
        else:
            editor = QtWidgets.QLineEdit()
            editor.setText(value)
            placeholder = spec.get('placeholder')
            if placeholder:
                editor.setPlaceholderText(placeholder)
        tooltip = spec.get('tooltip')
        if tooltip:
            editor.setToolTip(tooltip)
        return editor
