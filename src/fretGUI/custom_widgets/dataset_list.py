"""Checkable, reorderable list of measurements inside a node."""

from Qt import QtCore, QtGui, QtWidgets
from Qt.QtCore import Signal

from fretGUI.custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper


LABEL_WIDTH = 176
ROW_HEIGHT = 32
EMPTY_HEIGHT = 28


def measurement_list_for(widget):
    """The list that owns a row, walking past inner layouts."""
    current = widget
    while current is not None:
        if isinstance(current, DatasetListWidget):
            return current
        current = current.parentWidget()
    return None


def _graphics_proxy(widget):
    """Proxy that embeds this widget. Child widgets do not store it themselves."""
    current = widget
    while current is not None:
        proxy = current.graphicsProxyWidget()
        if proxy is not None:
            return proxy
        current = current.parentWidget()
    return None


def measurement_row_width():
    """Packed row width, so the node matches a loader instead of stretching."""
    cached = getattr(measurement_row_width, 'cached', None)
    if cached is None:
        probe = _DatasetRow(0, '', '#888888', '')
        cached = probe.sizeHint().width()
        probe.deleteLater()
        measurement_row_width.cached = cached
    return cached


class _DragHandle(QtWidgets.QWidget):
    """Grip that reorders a measurement row."""

    def __init__(self, row):
        super().__init__(row)
        self._row = row
        self._pressed = False
        self.setFixedSize(14, 25)
        self.setCursor(QtCore.Qt.SizeVerCursor)
        self.setToolTip('Drag to reorder')

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        color = self.palette().color(QtGui.QPalette.WindowText)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color)
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        for row in range(-1, 2):
            for column in range(-1, 1):
                painter.drawEllipse(
                    QtCore.QPointF(center_x + column * 4, center_y + row * 4),
                    1.2,
                    1.2,
                )

    def _list(self):
        return measurement_list_for(self._row)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._pressed or not (event.buttons() & QtCore.Qt.LeftButton):
            return
        dataset_list = self._list()
        if dataset_list is not None:
            dataset_list.move_row_to_pointer(self._row, event.globalPos())
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._pressed:
            self._pressed = False
            dataset_list = self._list()
            if dataset_list is not None:
                dataset_list.finish_row_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _DatasetRow(QtWidgets.QWidget):
    toggled = Signal()

    def __init__(self, key, label, color, tooltip, checked=True):
        super().__init__()
        self.key = key
        self._full_label = label
        self.checkbox = QtWidgets.QCheckBox()
        self.checkbox.setChecked(checked)
        self.checkbox.stateChanged.connect(lambda _state: self.toggled.emit())

        self._swatch = QtWidgets.QLabel()
        self._swatch.setFixedSize(18, 18)
        self.set_color(color)

        self._label = QtWidgets.QLabel()
        self._label.setFixedWidth(LABEL_WIDTH)
        self.set_label(label, tooltip)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        layout.addWidget(_DragHandle(self))
        layout.addWidget(self._swatch)
        layout.addWidget(self._label)
        layout.addWidget(self.checkbox)
        layout.addStretch(1)
        self.setFixedHeight(ROW_HEIGHT)
        self.setToolTip(tooltip or label)

    def set_label(self, label, tooltip=None):
        self._full_label = label
        tip = tooltip or label
        metrics = self._label.fontMetrics()
        self._label.setText(
            metrics.elidedText(label, QtCore.Qt.ElideRight, LABEL_WIDTH)
        )
        self._label.setToolTip(tip)
        self.setToolTip(tip)

    def label(self):
        return self._full_label

    def set_color(self, color):
        qcolor = _qcolor(color)
        self._swatch.setStyleSheet(
            f'background-color: {qcolor.name()}; border: 1px solid palette(mid);'
        )

    def is_checked(self):
        return self.checkbox.isChecked()

    def set_checked(self, checked):
        self.checkbox.setChecked(bool(checked))

    def apply(self, item):
        self.set_label(item['label'], item.get('tooltip'))
        self.set_color(item.get('color'))


class DatasetListWidget(QtWidgets.QWidget):
    """Rows for incoming measurements. Checked rows stay in visual order."""

    changed = Signal()

    def __init__(self, parent=None, node_view=None):
        super().__init__(parent)
        self._node_view = node_view
        self._rows = {}
        self._updating = False
        self._row_dragged = False
        self._drag_preview = None
        self._drag_row = None

        self._placeholder = QtWidgets.QLabel('Run to list measurements')
        self._placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._placeholder.setFixedHeight(EMPTY_HEIGHT)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(QtCore.Qt.AlignTop)
        self._layout.addWidget(self._placeholder)
        self.setFixedSize(self.sizeHint())

    def sync(self, items):
        """Keep current order, append new keys, and drop keys that disappeared."""
        incoming = {item['key']: item for item in items}
        self._updating = True
        try:
            for key in list(self.keys()):
                if key not in incoming:
                    self._remove_row(key)
            for key in self.keys():
                self._rows[key].apply(incoming[key])
            for item in items:
                if item['key'] not in self._rows:
                    self._append_row(item)
        finally:
            self._updating = False
        self._refresh_empty()

    def keys(self):
        return [row.key for row in self._ordered_rows()]

    def labels(self):
        return [row.label() for row in self._ordered_rows()]

    def checked_keys(self):
        return [row.key for row in self._ordered_rows() if row.is_checked()]

    def is_checked(self, key):
        row = self._rows.get(key)
        return bool(row and row.is_checked())

    def set_checked(self, key, checked):
        row = self._rows.get(key)
        if row is not None:
            row.set_checked(checked)

    def move_key_to_index(self, key, index):
        row = self._rows.get(key)
        if row is None:
            return
        current = self._row_layout_index(row)
        if current < 0 or current == index:
            return
        self._layout.removeWidget(row)
        self._layout.insertWidget(self._row_insert_index(index), row)

    def move_row_to_pointer(self, row_widget, global_pos):
        if hasattr(global_pos, 'toPoint'):
            global_pos = global_pos.toPoint()
        local = self.mapFromGlobal(global_pos)
        self._show_drag_preview(row_widget, local.y())
        insert_at = len(self._ordered_rows())
        for widget in self._ordered_rows():
            if widget is row_widget:
                continue
            if local.y() < widget.geometry().center().y():
                insert_at = self._row_layout_index(widget)
                break
        current = self._row_layout_index(row_widget)
        if current < 0 or current == insert_at:
            return
        if current < insert_at:
            insert_at -= 1
        if current == insert_at:
            return
        self._layout.removeWidget(row_widget)
        self._layout.insertWidget(self._row_insert_index(insert_at), row_widget)
        self._row_dragged = True

    def finish_row_drag(self):
        self._clear_drag_preview()
        if not self._row_dragged:
            return
        self._row_dragged = False
        if not self._updating:
            self.changed.emit()

    def sizeHint(self):
        if not self._rows:
            height = EMPTY_HEIGHT
        else:
            height = len(self._rows) * ROW_HEIGHT
        return QtCore.QSize(measurement_row_width(), height)

    def _append_row(self, item):
        row = _DatasetRow(
            item['key'],
            item['label'],
            item.get('color'),
            item.get('tooltip') or item['label'],
            checked=item.get('checked', True),
        )
        row.toggled.connect(self._on_row_toggled)
        self._rows[item['key']] = row
        self._layout.addWidget(row)

    def _remove_row(self, key):
        row = self._rows.pop(key)
        self._layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()

    def _ordered_rows(self):
        rows = []
        for index in range(self._layout.count()):
            widget = self._layout.itemAt(index).widget()
            if isinstance(widget, _DatasetRow):
                rows.append(widget)
        return rows

    def _row_layout_index(self, row):
        return self._ordered_rows().index(row) if row in self._ordered_rows() else -1

    def _row_insert_index(self, visual_index):
        """Layout index for a visual row index, after the placeholder when it is shown."""
        offset = 1 if self._layout.indexOf(self._placeholder) >= 0 else 0
        return offset + visual_index

    def _on_row_toggled(self):
        if not self._updating:
            self.changed.emit()

    def _refresh_empty(self):
        has_rows = bool(self._rows)
        if has_rows and self._layout.indexOf(self._placeholder) >= 0:
            self._layout.removeWidget(self._placeholder)
            self._placeholder.hide()
        elif not has_rows and self._layout.indexOf(self._placeholder) < 0:
            self._layout.insertWidget(0, self._placeholder)
            self._placeholder.show()
        self._apply_node_size()

    def _apply_node_size(self):
        hint = self.sizeHint()
        self.setFixedSize(hint)
        self.updateGeometry()

        proxy = _graphics_proxy(self)
        if proxy is not None and proxy.widget() is not None:
            container = proxy.widget()
            layout = container.layout()
            if layout is not None:
                layout.activate()
            container.updateGeometry()
            container_hint = container.sizeHint()
            # The proxy grows with its size hint on its own, and keeps that
            # size after rows are removed. Resize it explicitly so the node
            # can shrink as well as grow.
            proxy.setMinimumSize(0, 0)
            proxy.resize(
                max(container_hint.width(), hint.width()),
                max(container_hint.height(), hint.height()),
            )

        view = self._node_view
        if view is None or not hasattr(view, 'draw_node'):
            return
        view.prepareGeometryChange()
        view.draw_node()
        scene = view.scene()
        if scene is not None:
            scene.update()

    def _show_drag_preview(self, row_widget, local_y):
        if self._drag_preview is None or self._drag_row is not row_widget:
            self._clear_drag_preview()
            preview = QtWidgets.QLabel(self)
            preview.setPixmap(row_widget.grab())
            preview.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            preview.resize(row_widget.size())
            effect = QtWidgets.QGraphicsOpacityEffect(row_widget)
            effect.setOpacity(0.35)
            row_widget.setGraphicsEffect(effect)
            self._drag_preview = preview
            self._drag_row = row_widget
        preview_y = local_y - (row_widget.height() // 2)
        upper = max(0, self.height() - row_widget.height())
        preview_y = min(max(preview_y, 0), upper)
        self._drag_preview.move(row_widget.x(), preview_y)
        self._drag_preview.show()
        self._drag_preview.raise_()

    def _clear_drag_preview(self):
        if self._drag_row is not None:
            self._drag_row.setGraphicsEffect(None)
            self._drag_row = None
        if self._drag_preview is not None:
            self._drag_preview.hide()
            self._drag_preview.deleteLater()
            self._drag_preview = None


class DatasetListWrapper(AbstractWidgetWrapper):
    def __init__(self, parent=None):
        self.dataset_list = DatasetListWidget(node_view=parent)
        super().__init__(parent)
        self.set_name('datasets')
        self.set_label('')
        self.set_custom_widget(self.dataset_list)

    def wire_signals(self):
        self.dataset_list.changed.connect(self.widget_changed_signal.emit)

    def get_value(self):
        return [
            {'key': key, 'checked': self.dataset_list.is_checked(key)}
            for key in self.dataset_list.keys()
        ]

    def set_value(self, value):
        return


def _qcolor(color):
    if isinstance(color, QtGui.QColor):
        return color if color.isValid() else QtGui.QColor('#888888')
    if isinstance(color, (tuple, list)):
        qcolor = QtGui.QColor(*color)
        return qcolor if qcolor.isValid() else QtGui.QColor('#888888')
    qcolor = QtGui.QColor(str(color or ''))
    return qcolor if qcolor.isValid() else QtGui.QColor('#888888')
