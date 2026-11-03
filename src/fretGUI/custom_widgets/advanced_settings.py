"""Collapsible Advanced settings panel for loader nodes."""

from Qt import QtCore, QtWidgets
from Qt.QtCore import Signal

from fretGUI.custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from fretGUI.custom_widgets.sliders import FrontmostComboBox


class AdvancedSettingsWidget(QtWidgets.QWidget):
    """Collapsible shell that hosts load-affecting controls."""

    expanded_changed = Signal(bool)
    settings_changed = Signal()

    HEADER_HEIGHT = 22
    CONTENT_ROW_HEIGHT = 30
    CONTENT_MARGINS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._settings = {}
        self._combos = {}
        self._previous_channels = {}
        self._updating = False

        self.setObjectName('loaderAdvancedSettings')

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.collapse_button = QtWidgets.QToolButton(self)
        self.collapse_button.setObjectName('loaderAdvancedCollapseButton')
        self.collapse_button.setCheckable(True)
        self.collapse_button.setChecked(False)
        self.collapse_button.setFixedHeight(self.HEADER_HEIGHT)
        self.collapse_button.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.collapse_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonTextBesideIcon
        )
        self.collapse_button.setArrowType(QtCore.Qt.RightArrow)
        self.collapse_button.setText('Advanced')
        self.collapse_button.setToolTip('Show advanced settings')
        self.collapse_button.toggled.connect(self._on_collapse_toggled)
        layout.addWidget(self.collapse_button)

        self.content = QtWidgets.QWidget(self)
        self.content.setVisible(False)
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(2, 2, 2, 2)
        self.content_layout.setSpacing(4)
        layout.addWidget(self.content)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.pin_to_content_height()

    def add_channel_combobox(self, key, label, channel_count, value, names=None):
        """Add a labeled channel selector. Values are integer channel indices."""
        row = QtWidgets.QWidget(self.content)
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        text = QtWidgets.QLabel(label, row)
        text.setMinimumWidth(90)
        combo = FrontmostComboBox(row)
        for index in range(channel_count):
            item_label = names[index] if names is not None else f'Channel {index}'
            combo.addItem(item_label, index)
        combo.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )

        row_layout.addWidget(text)
        row_layout.addWidget(combo, stretch=1)
        self.content_layout.addWidget(row)

        self._combos[key] = combo
        self._settings[key] = int(value)
        self._previous_channels[key] = int(value)
        self._set_combo_channel(combo, int(value))
        combo.activated.connect(
            lambda _index, settings_key=key: self._on_channel_activated(
                settings_key
            )
        )

    def _set_combo_channel(self, combo, channel):
        index = combo.findData(int(channel))
        if index < 0:
            index = 0
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _combo_channel(self, combo):
        data = combo.currentData()
        if data is None:
            return combo.currentIndex()
        return int(data)

    def _on_channel_activated(self, key):
        if self._updating:
            return
        combo = self._combos[key]
        new_value = self._combo_channel(combo)
        if self._settings.get(key) == new_value:
            return

        other_key = None
        if key == 'donor_channel' and 'acceptor_channel' in self._settings:
            other_key = 'acceptor_channel'
        elif key == 'acceptor_channel' and 'donor_channel' in self._settings:
            other_key = 'donor_channel'

        # With only two channels, picking the other role's channel would
        # collide. Swap instead of silently reverting (which blocked all edits).
        if other_key is not None and self._settings.get(other_key) == new_value:
            previous = self._settings[key]
            self._settings[key] = new_value
            self._settings[other_key] = previous
            self._previous_channels[key] = new_value
            self._previous_channels[other_key] = previous
            self._set_combo_channel(self._combos[other_key], previous)
        else:
            self._settings[key] = new_value
            self._previous_channels[key] = new_value

        self.settings_changed.emit()

    def _on_collapse_toggled(self, expanded):
        self._expanded = bool(expanded)
        self.content.setVisible(self._expanded)
        self.collapse_button.setArrowType(
            QtCore.Qt.DownArrow if self._expanded else QtCore.Qt.RightArrow
        )
        action = 'Hide' if self._expanded else 'Show'
        self.collapse_button.setToolTip(f'{action} advanced settings')
        # Collapse must shrink the widget; hiding content alone leaves the old height.
        self.pin_to_content_height()
        self.expanded_changed.emit(self._expanded)

    def sizeHint(self):
        # Prefer matching the file list width when the loader has pinned it.
        width = max(super().sizeHint().width(), self.minimumWidth(), 200)
        return QtCore.QSize(width, self.required_height())

    def minimumSizeHint(self):
        return QtCore.QSize(0, self.required_height())

    def pin_to_content_height(self):
        """Lock height to collapsed/expanded content so the node can shrink.

        Width tracks the file widget; do not lock a narrow fixed width.
        """
        height = self.required_height()
        self.setMinimumSize(0, 0)
        self.setMaximumHeight(height)
        self.setMinimumHeight(height)
        self.setFixedHeight(height)
        self.setMaximumWidth(16777215)
        self.updateGeometry()
        return self.width(), height

    def is_expanded(self):
        return self._expanded

    def set_expanded(self, expanded):
        expanded = bool(expanded)
        if self.collapse_button.isChecked() == expanded:
            if self._expanded != expanded:
                self._on_collapse_toggled(expanded)
            return
        self.collapse_button.setChecked(expanded)

    def get_settings(self):
        """Load-affecting values only (no presentation state)."""
        return dict(self._settings)

    def get_value(self):
        value = {'expanded': self._expanded}
        value.update(self._settings)
        return value

    def set_value(self, value):
        if not isinstance(value, dict):
            return
        self._updating = True
        try:
            for key, combo in self._combos.items():
                if key not in value:
                    continue
                channel = int(value[key])
                self._settings[key] = channel
                self._previous_channels[key] = channel
                self._set_combo_channel(combo, channel)
            if 'expanded' in value:
                self.set_expanded(value['expanded'])
        finally:
            self._updating = False

    def required_height(self):
        height = self.HEADER_HEIGHT
        if not self._expanded:
            return height
        rows = max(1, len(self._combos))
        height += (
            rows * self.CONTENT_ROW_HEIGHT
            + self.CONTENT_MARGINS
        )
        return height


class AdvancedSettingsWrapper(AbstractWidgetWrapper):
    """NodeGraphQt wrapper around AdvancedSettingsWidget."""

    size_changed = Signal()

    def __init__(self, parent=None):
        self.settings_widget = AdvancedSettingsWidget()
        super().__init__(parent)
        self.set_name('Advanced')
        self.set_label('')
        self.set_custom_widget(self.settings_widget)

    def add_channel_combobox(self, key, label, channel_count, value, names=None):
        self.settings_widget.add_channel_combobox(
            key, label, channel_count, value, names=names
        )

    def get_value(self):
        return self.settings_widget.get_value()

    def set_value(self, value):
        previous = self.settings_widget.get_value()
        # expanded_changed already emits size_changed via wire_signals.
        self.settings_widget.set_value(value)
        current = self.settings_widget.get_value()
        load_keys = set(current) - {'expanded'}
        if any(previous.get(key) != current.get(key) for key in load_keys):
            self.widget_changed_signal.emit()

    def get_load_settings(self):
        return self.settings_widget.get_settings()

    def required_height(self):
        return self.settings_widget.required_height()

    def wire_signals(self):
        self.settings_widget.settings_changed.connect(
            self.widget_changed_signal.emit
        )
        self.settings_widget.expanded_changed.connect(
            lambda _expanded: self.size_changed.emit()
        )


def build_channel_mapping_settings(
    parent=None,
    channel_count=2,
    donor_channel=1,
    acceptor_channel=0,
    channel_names=None,
):
    """Factory used by ConfoCor2 / future multi-channel loaders."""
    wrapper = AdvancedSettingsWrapper(parent)
    wrapper.add_channel_combobox(
        'donor_channel',
        'Donor',
        channel_count,
        donor_channel,
        names=channel_names,
    )
    wrapper.add_channel_combobox(
        'acceptor_channel',
        'Acceptor',
        channel_count,
        acceptor_channel,
        names=channel_names,
    )
    wrapper.settings_widget.pin_to_content_height()
    return wrapper
