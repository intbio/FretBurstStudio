from Qt import QtWidgets, QtCore, QtGui
from Qt.QtCore import Signal
from fretGUI.custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from Qt.QtWidgets import QCheckBox
from matplotlib import rcParams
import os
from threading import RLock


class _CloseButton(QtWidgets.QPushButton):
    """Small circular close button with platform-independent alignment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(25, 25)
        self.setFlat(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        palette = self.palette()
        background = palette.color(QtGui.QPalette.Button)
        border = palette.color(QtGui.QPalette.Mid)
        if self.isDown():
            background = background.darker(115)
        elif self.underMouse():
            background = background.lighter(110)
            border = palette.color(QtGui.QPalette.Highlight)

        painter.setPen(QtGui.QPen(border, 1))
        painter.setBrush(background)
        # QRect.center() is half a pixel off on an odd-sized button, which
        # shifts the cross relative to the circle.
        circle = QtCore.QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.drawEllipse(circle)

        center = circle.center()
        pen = QtGui.QPen(palette.color(QtGui.QPalette.ButtonText), 1.7)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen)
        offset = 4.0
        painter.drawLine(
            QtCore.QPointF(center.x() - offset, center.y() - offset),
            QtCore.QPointF(center.x() + offset, center.y() + offset),
        )
        painter.drawLine(
            QtCore.QPointF(center.x() + offset, center.y() - offset),
            QtCore.QPointF(center.x() - offset, center.y() + offset),
        )


class _ColorIdLabel(QtWidgets.QLabel):
    """Clickable file ID swatch backed by a canonical Matplotlib color."""

    color_changed = Signal(str)

    def __init__(self, parent=None, text='-'):
        super().__init__(parent=parent, text=text)
        self._color = '#ffffff'
        self.setFixedSize(25, 25)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Click to select this file's plot color")
        self.set_color(self._color)

    def color(self):
        return self._color

    def set_color(self, color):
        qcolor = QtGui.QColor(color)
        if not qcolor.isValid():
            return
        self._color = qcolor.name()
        luminance = (
            0.299 * qcolor.red()
            + 0.587 * qcolor.green()
            + 0.114 * qcolor.blue()
        )
        text_color = '#111111' if luminance > 150 else '#ffffff'
        self.setStyleSheet(
            f"background-color: {self._color};"
            f"color: {text_color};"
            "border: 1px solid palette(mid);"
        )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            # Widgets in nodes live inside a QGraphicsProxyWidget. Parenting a
            # dialog to one of them can make Windows embed an empty dialog in
            # the scene. Use the real application window and Qt's widget-based
            # dialog so it is always rendered as a normal top-level window.
            parent_window = QtWidgets.QApplication.activeWindow()
            dialog = QtWidgets.QColorDialog(
                QtGui.QColor(self._color),
                parent_window,
            )
            dialog.setWindowTitle("Select file plot color")
            dialog.setOption(
                QtWidgets.QColorDialog.DontUseNativeDialog,
                True,
            )
            dialog.setWindowModality(QtCore.Qt.ApplicationModal)
            if dialog.exec_():
                selected = dialog.selectedColor()
                new_color = selected.name()
                if new_color != self._color:
                    self.set_color(new_color)
                    self.color_changed.emit(new_color)
            event.accept()
            return
        super().mousePressEvent(event)


class _RowDragHandle(QtWidgets.QWidget):
    """Grip that reorders a file row inside its loader list."""

    def __init__(self, row):
        super().__init__(row)
        self._row = row
        self._pressed = False
        self.setFixedSize(8, 25)
        self.setCursor(QtCore.Qt.SizeVerCursor)
        self.setToolTip("Drag to reorder")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        color = self.palette().color(QtGui.QPalette.WindowText)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color)
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        for row in (-1, 0, 1):
            for column in (-0.5, 0.5):
                painter.drawEllipse(
                    QtCore.QPointF(
                        center_x + column * 3.0,
                        center_y + row * 3.5,
                    ),
                    1.05,
                    1.05,
                )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._pressed or not (event.buttons() & QtCore.Qt.LeftButton):
            return
        parent = self._row.parentWidget()
        if hasattr(parent, 'move_row_to_pointer'):
            parent.move_row_to_pointer(self._row, event.globalPos())
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._pressed:
            self._pressed = False
            parent = self._row.parentWidget()
            if hasattr(parent, 'finish_row_drag'):
                parent.finish_row_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)


_CHIP_LABELS = ('UNKN', 'Pulsed', 'ALEX', '2pol', 'PAX', 'PIE', '1C', 'CW', 'µt')
_UNKNOWN_BADGE = {
    'code': 'UNKN',
    'tooltip': 'Not loaded yet. Press RUN to identify the measurement.',
}


class _MethodChip(QtWidgets.QWidget):
    """Compact excitation or timing label that follows the application palette."""

    def __init__(self, code, tooltip, parent=None):
        super().__init__(parent)
        self._code = code
        self.setToolTip(tooltip)
        font = self.font()
        font.setPointSize(8)
        self.setFont(font)
        self.setFixedHeight(16)
        self.setFixedWidth(self._plaque_width())

    @staticmethod
    def _plaque_width():
        probe = QtWidgets.QWidget()
        font = probe.font()
        font.setPointSize(8)
        probe.setFont(font)
        metrics = probe.fontMetrics()
        probe.deleteLater()
        return max(metrics.horizontalAdvance(label) for label in _CHIP_LABELS) + 12

    def text(self):
        return self._code

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        palette = self.palette()
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QtGui.QPen(palette.color(QtGui.QPalette.Mid), 1))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(palette.color(QtGui.QPalette.Text))
        painter.drawText(self.rect(), QtCore.Qt.AlignCenter, self._code)


class PathRowWidget(QtWidgets.QWidget):
    del_signal = Signal()
    changed_state = Signal(bool)
    color_changed = Signal(str)
    label_changed = Signal(str)
    
    def __init__(self, parent=None, path_id=None, color=None):
        super(PathRowWidget, self).__init__(parent)
        self._path_id = path_id
        
        self.checkbox = QCheckBox(parent=parent, checked=True)
                      
        self.del_button = _CloseButton(parent=self)
        self.del_button.setToolTip("Close file")
        
        self.drag_handle = _RowDragHandle(self)
        self.id_label = _ColorIdLabel(parent=self, text='')
        if color is not None:
            self.id_label.set_color(color)
        
        self.text_field = QtWidgets.QLineEdit(parent=self, text='...')
        self.text_field.setFixedHeight(25)
        # A little under the old 176px name, so a method chip fits in the
        # node without making the node wider.
        self.text_field.setFixedWidth(148)
        self.text_field.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.text_field.setToolTip("Name shown on plots. The file path is unchanged.")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )
        
        self._full_path = ''
        self._display_name = ''
        self._badges = QtWidgets.QWidget(self)
        self._badge_layout = QtWidgets.QHBoxLayout(self._badges)
        self._badge_layout.setContentsMargins(0, 0, 0, 0)
        self._badge_layout.setSpacing(3)
        self._badge_layout.addWidget(
            _MethodChip(_UNKNOWN_BADGE['code'], _UNKNOWN_BADGE['tooltip'], self._badges)
        )
                
        row_layout = QtWidgets.QHBoxLayout(self)
        row_layout.setContentsMargins(0, 2, 2, 2)
        row_layout.setSpacing(4)
        
        row_layout.addWidget(self.drag_handle)
        row_layout.addWidget(self.id_label)
        row_layout.addWidget(self.text_field, stretch=1)
        row_layout.addWidget(self._badges, alignment=QtCore.Qt.AlignVCenter)
        row_layout.addWidget(self.del_button)
        row_layout.addWidget(self.checkbox)
        
        if path_id is not None:
            self.set_id(path_id)
        
        # Set default tooltip
        self.set_tooltip("Not loaded, press RUN")
        
        self.wire_signals()
        
    def wire_signals(self):
        self.del_button.clicked.connect(self.on_button_click)
        self.checkbox.stateChanged.connect(self.on_state_chenged)
        self.id_label.color_changed.connect(self.color_changed.emit)
        self.text_field.editingFinished.connect(self._on_label_edited)
        
    def on_state_chenged(self, state: bool):
        print("state  changed")
        self.changed_state.emit(state)
        
    def on_button_click(self):
        # Remove widget from layout immediately before deletion
        parent = self.parentWidget()
        if parent and hasattr(parent, 'layout'):
            parent.layout.removeWidget(self)
            # Hide the widget immediately so it doesn't affect size calculations
            self.hide()
        self.deleteLater()
        # Update display after widget is removed - this will recalculate size
        if parent:
            # Use a small delay to ensure widget is removed from layout
            from Qt.QtCore import QTimer
            QTimer.singleShot(10, parent.update_display)
        self.del_signal.emit()
        
    def set_text(self, new_text):
        """Remember the full path and show its filename until the user renames it."""
        self._full_path = new_text
        basename = os.path.basename(new_text) if new_text else '...'
        self._display_name = basename
        self.text_field.setText(basename)
        if new_text:
            self.text_field.setToolTip(new_text)

    def get_text(self):
        """Return the full path"""
        return self._full_path if self._full_path else self.text_field.text()

    def get_display_name(self):
        name = (self._display_name or self.text_field.text()).strip()
        if name:
            return name
        return os.path.basename(self._full_path) if self._full_path else 'file'

    def _on_label_edited(self):
        name = self.text_field.text().strip()
        if not name:
            name = os.path.basename(self._full_path) if self._full_path else 'file'
            self.text_field.setText(name)
        if name == self._display_name:
            return
        self._display_name = name
        self.label_changed.emit(name)
    
    def set_id(self, path_id):
        """Keep the internal id. The row shows a color, not the number."""
        self._path_id = path_id
        self.id_label.setText('')
    
    def get_id(self):
        """Get the ID from the label"""
        return self._path_id

    def set_color(self, color):
        self.id_label.set_color(color)

    def get_color(self):
        return self.id_label.color()
    
    def set_tooltip(self, tooltip_text):
        """Set tooltip for the row widget"""
        self.setToolTip(tooltip_text)

    def set_badges(self, badges):
        """Replace the method chips beside the file name."""
        shown = list(badges or []) or [_UNKNOWN_BADGE]
        while self._badge_layout.count():
            item = self._badge_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for badge in shown:
            self._badge_layout.addWidget(
                _MethodChip(badge['code'], badge['tooltip'], self._badges)
            )

    def badge_codes(self):
        codes = []
        for index in range(self._badge_layout.count()):
            widget = self._badge_layout.itemAt(index).widget()
            if isinstance(widget, _MethodChip):
                codes.append(widget.text())
        return codes
        
    def is_checked(self):
        return self.checkbox.isChecked()


class PathSelectorWidget(QtWidgets.QWidget):  
    
    del_btn_clicked = Signal()
    checkbox_clicked = Signal()
    color_changed = Signal()
    label_changed = Signal()
    order_changed = Signal()
    paths_added = Signal(list)  # Signal emitted when paths are added, with list of paths
    _get_path_to_id_callback = None  # Callback to get path_to_id mapping
    _wrapper = None  # Reference to the wrapper widget
    
    # Size constants
    BASE_HEIGHT = 60  # Height for button and margins
    ROW_HEIGHT = 35   # Height per path row widget
    MIN_WIDTH = 360   # Minimum node width
    DEFAULT_WIDTH = 360  # Default node width
      
    def __init__(self, parent=None):
        super(PathSelectorWidget, self).__init__()
        
        self.rowwidget_map = dict()
        self.path_state = dict()
        self._state_lock = RLock()
        self._drag_preview = None
        self._drag_row = None
        
        self.parentView = parent
               
        self.file_dialog = QtWidgets.QFileDialog()
        self.file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        self.file_dialog.setNameFilter("все файлы (*);;Изображения (*.png *.jpg);;Текстовые файлы (*.txt)")
        
        self.open_button = QtWidgets.QPushButton(parent=self, text='Add File')
        self.open_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.open_button.setMinimumSize(100, 30)  # Set minimum button size
        
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.addWidget(self.open_button, alignment=QtCore.Qt.AlignTop)
        

        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        self.wire_signals()
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        
    def wire_signals(self):
        button = self.open_button
        button.clicked.connect(self.on_button_click)
        
    def _ordered_rows(self):
        rows = []
        for index in range(self.layout.count()):
            item = self.layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, PathRowWidget):
                rows.append(widget)
        return rows

    def get_paths(self) -> list:
        return [row.get_text() for row in self._ordered_rows()]

    def get_file_entries(self):
        """Return rows in the order shown in the loader."""
        entries = []
        with self._state_lock:
            for row in self._ordered_rows():
                path_id = row.get_id()
                state = self.path_state.get(path_id)
                if state is None:
                    continue
                entries.append((
                    path_id,
                    state['path'],
                    state['checked'],
                    state['color'],
                    state.get('display_name') or os.path.basename(state['path']),
                ))
        return entries

    def _global_point(self, global_pos):
        if hasattr(global_pos, 'toPoint'):
            return global_pos.toPoint()
        return global_pos

    def move_row_to_pointer(self, row_widget, global_pos):
        """Slide a preview with the pointer and move the row when it crosses another."""
        global_pos = self._global_point(global_pos)
        local = self.mapFromGlobal(global_pos)
        self._show_drag_preview(row_widget, local.y())
        insert_at = self.layout.count()
        for widget in self._ordered_rows():
            if widget is row_widget:
                continue
            if local.y() < widget.geometry().center().y():
                insert_at = self.layout.indexOf(widget)
                break
        current = self.layout.indexOf(row_widget)
        if current < 0:
            return
        if current < insert_at:
            insert_at -= 1
        if current == insert_at:
            return
        self.layout.removeWidget(row_widget)
        self.layout.insertWidget(insert_at, row_widget)
        self._row_dragged = True

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
        lower = self.open_button.geometry().bottom()
        upper = max(lower, self.height() - row_widget.height())
        preview_y = min(max(preview_y, lower), upper)
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

    def finish_row_drag(self):
        self._clear_drag_preview()
        if not getattr(self, '_row_dragged', False):
            return
        self._row_dragged = False
        self.order_changed.emit()
    
    def count_path_rows(self) -> int:
        """Count the number of path row widgets"""
        count = 1
        total_widgets = self.layout.count()
        for i in range(total_widgets):
            item = self.layout.itemAt(i)
            if item is None:
                continue
            row_widget = item.widget()
            if row_widget and isinstance(item.widget(), PathRowWidget):
                count += 1
        return count
    
    def calculate_required_size(self):
        """Calculate the required node size based on number of path rows"""
        num_rows = self.count_path_rows()
        height = self.BASE_HEIGHT + (num_rows * self.ROW_HEIGHT)
        width = self.DEFAULT_WIDTH
        return (width, height)
    
    def update_node_size(self):
        """Manually update the node height based on current widget count (width stays unchanged)"""
        if not self.parentView:
            return
        
        _, height = self.calculate_required_size()
        
        # Only update height, keep width unchanged
        if hasattr(self.parentView, '_height'):
            new_height = max(150, height)  # Minimum height
            if self.parentView._height != new_height:
                self.parentView.prepareGeometryChange()
                self.parentView._height = new_height
                self.parentView.update()
                
                # Also update the scene
                scene = self.parentView.scene()
                if scene:
                    scene.update()
        
    def process_files(self, file_paths):
        """Process file paths: emit signal, assign IDs, and add widgets"""
        if not file_paths:
            return
        
        # Emit signal before adding widgets so IDs can be assigned (synchronously)
        self.paths_added.emit(file_paths)
        # Get path_to_id mapping after IDs are assigned
        path_to_id = self._get_path_to_id_callback() if self._get_path_to_id_callback else {}
        self.add_row_widgets(file_paths, path_to_id=path_to_id)
        self.update_display()
    
    def on_button_click(self):
        if self.file_dialog.exec_():
            selected_files = self.file_dialog.selectedFiles()
            self.process_files(selected_files)
    
    def dragEnterEvent(self, event):
        """Handle drag enter event - accept if files are being dragged"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move event - accept if files are being dragged"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """Handle drop event - extract file paths and process them"""
        print(event)
        if event.mimeData().hasUrls():
            # Extract file paths from dropped URLs
            file_paths = []
            for url in event.mimeData().urls():
                # Convert QUrl to local file path
                file_path = url.toLocalFile()
                if file_path:  # Only add if it's a valid local file
                    file_paths.append(file_path)
            
            if file_paths:
                event.acceptProposedAction()
                print(file_paths)
                self.process_files(file_paths)
            else:
                event.ignore()
        else:
            event.ignore()
            
    def add_row_widgets(self, file_paths, path_to_id=None):
        if path_to_id is None:
            path_to_id = {}
        color_cycle = rcParams['axes.prop_cycle'].by_key().get(
            'color', ['#1f77b4']
        )
        for path in file_paths:
            path_id = path_to_id.get(path)
            color_index = (path_id - 1) if path_id is not None else len(
                self.path_state
            )
            color = color_cycle[color_index % len(color_cycle)]
            new_row_widget = PathRowWidget(
                parent=self,
                path_id=path_id,
                color=color,
            )
            self.__wire_row_widget(new_row_widget)
            self.rowwidget_map[path_id] = new_row_widget
            
            new_row_widget.set_text(path)
            with self._state_lock:
                self.path_state[path_id] = {
                    'path': path,
                    'checked': True,
                    'color': new_row_widget.get_color(),
                    'display_name': new_row_widget.get_display_name(),
                }
            self.layout.addWidget(new_row_widget)
            
    def __wire_row_widget(self, row_widget):
        row_widget.changed_state.connect(
            lambda state, row=row_widget: self._on_checked_changed(row, state)
        )
        row_widget.del_signal.connect(
            lambda row=row_widget: self._remove_row_state(row)
        )
        row_widget.del_signal.connect(self.del_btn_clicked.emit)
        row_widget.color_changed.connect(
            lambda color, row=row_widget: self._on_color_changed(row, color)
        )
        row_widget.label_changed.connect(
            lambda name, row=row_widget: self._on_label_changed(row, name)
        )

    def _on_checked_changed(self, row_widget, checked):
        path_id = row_widget.get_id()
        with self._state_lock:
            if path_id in self.path_state:
                self.path_state[path_id]['checked'] = bool(checked)
        self.checkbox_clicked.emit()

    def _remove_row_state(self, row_widget):
        path_id = row_widget.get_id()
        self.rowwidget_map.pop(path_id, None)
        with self._state_lock:
            self.path_state.pop(path_id, None)

    def _on_color_changed(self, row_widget, color):
        path_id = row_widget.get_id()
        with self._state_lock:
            if path_id in self.path_state:
                self.path_state[path_id]['color'] = color
        self.color_changed.emit()

    def _on_label_changed(self, row_widget, name):
        path_id = row_widget.get_id()
        with self._state_lock:
            if path_id in self.path_state:
                self.path_state[path_id]['display_name'] = name
        self.label_changed.emit()
        
    
    def update_path_ids(self, path_to_id):
        """Update IDs for existing path rows based on path_to_id mapping"""
        total_widgets = self.layout.count()
        for i in range(total_widgets):
            item = self.layout.itemAt(i)
            if item is None:
                continue
            row_widget = item.widget()
            if row_widget and isinstance(item.widget(), PathRowWidget):
                path = row_widget.get_text()
                if path in path_to_id:
                    row_widget.set_id(path_to_id[path])
    
    def update_tooltip_for_path(self, path, tooltip_text):
        """Update tooltip for a specific path row widget"""
        row_widget = self._row_for_path(path)
        if row_widget is not None:
            row_widget.set_tooltip(tooltip_text)

    def update_badges_for_path(self, path, badges):
        """Update method chips for a specific path row widget."""
        row_widget = self._row_for_path(path)
        if row_widget is not None:
            row_widget.set_badges(badges)

    def _row_for_path(self, path):
        total_widgets = self.layout.count()
        for i in range(total_widgets):
            item = self.layout.itemAt(i)
            if item is None:
                continue
            row_widget = item.widget()
            if isinstance(row_widget, PathRowWidget) and row_widget.get_text() == path:
                return row_widget
        return None
            
    def on_del_bttn_clicked(self):
        print(self.get_paths())
            
    def update_display(self):
        # Update layout
        if hasattr(self, 'layout'):
            self.layout.activate()
        self.adjustSize()
        self.updateGeometry()

        # Manually update node height based on widget count. Width stays put.
        self.update_node_size()
        
        # Explicitly resize the wrapper's border frame if it exists
        if self._wrapper and hasattr(self._wrapper, 'resize_border_frame'):
            self._wrapper.resize_border_frame()
        
        # Process events to ensure updates are applied
        QtWidgets.QApplication.processEvents()           
                
               

class PathSelectorWidgetWrapper(AbstractWidgetWrapper):    
    paths_added = Signal(list)  # Forward the signal from PathSelectorWidget
    tooltip_update_requested = Signal(str, str)
    badges_update_requested = Signal(str, object)
    
    def __init__(self, parent=None):
        self.path_widget = PathSelectorWidget(parent=parent)
        self._path_to_id = {}  # Store path_to_id mapping

        super().__init__(parent)       
        self.set_name('File Widget')
        self.set_label('File') 
        
        # Wrap path_widget in a frame with grey border
        self.border_frame = QtWidgets.QFrame()
        self.border_frame.setObjectName("pathSelectorBorderFrame")
        # Use object name selector to prevent stylesheet cascading to children
        # self.border_frame.setStyleSheet("#pathSelectorBorderFrame { border: 1px solid grey; }")
        # Set size policy to allow resizing with content
        self.border_frame.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        frame_layout = QtWidgets.QVBoxLayout(self.border_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.addWidget(self.path_widget)
        
        self.set_custom_widget(self.border_frame)
        
        # Set callback for path widget to get path_to_id
        self.path_widget._get_path_to_id_callback = lambda: self._path_to_id
        # Give path widget reference to this wrapper so it can update geometry
        self.path_widget._wrapper = self  
        self.tooltip_update_requested.connect(
            self.path_widget.update_tooltip_for_path
        )
        self.badges_update_requested.connect(
            self.path_widget.update_badges_for_path
        )
            
    def get_value(self):
        selected_paths = self.path_widget.get_paths()
        return selected_paths

    def get_file_entries(self):
        return self.path_widget.get_file_entries()
    
    def get_rowwidget(self, id: int) -> PathRowWidget:
        return self.path_widget.rowwidget_map[id]

    def set_value(self, value):
        pass
    
    def update_path_ids(self, path_to_id):
        """Update IDs for paths in the widget"""
        self._path_to_id = path_to_id  # Store the mapping
        self.path_widget.update_path_ids(path_to_id)
    
    def update_tooltip_for_path(self, path, tooltip_text):
        """Update tooltip for a specific path"""
        self.tooltip_update_requested.emit(path, tooltip_text)

    def update_badges_for_path(self, path, badges):
        """Update method chips for a specific path."""
        self.badges_update_requested.emit(path, badges)
    
    def resize_border_frame(self):
        """Explicitly resize the border frame to match the path_widget size"""
        if not hasattr(self, 'border_frame') or not hasattr(self, 'path_widget'):
            return
        
        # Force path_widget to update its size first
        self.path_widget.adjustSize()
        self.path_widget.updateGeometry()
        
        # Process events to ensure size calculations are complete
        QtWidgets.QApplication.processEvents()
        
        # Get the size hint from path_widget (preferred size)
        path_widget_size_hint = self.path_widget.sizeHint()
        # Get the actual current size
        path_widget_size = self.path_widget.size()
        
        # Use size hint if valid, otherwise use current size
        target_size = path_widget_size_hint if path_widget_size_hint.isValid() else path_widget_size
        
        if target_size.isValid() and target_size.width() > 0 and target_size.height() > 0:
            # Reset minimum size to allow shrinking
            self.border_frame.setMinimumSize(0, 0)
            # Resize to match the target size
            self.border_frame.resize(target_size)
            # Force layout update
            if self.border_frame.layout():
                self.border_frame.layout().activate()
            self.border_frame.adjustSize()
            self.border_frame.updateGeometry()
        
        # Also update the wrapper widget itself
        self.adjustSize()
        self.updateGeometry()
    
    def wire_signals(self):
        self.path_widget.open_button.clicked.connect(
            self.widget_changed_signal.emit)
        self.path_widget.del_btn_clicked.connect(
            self.widget_changed_signal.emit)
        self.path_widget.checkbox_clicked.connect(
            self.widget_changed_signal.emit)
        self.path_widget.color_changed.connect(
            self.widget_changed_signal.emit)
        self.path_widget.order_changed.connect(
            self.widget_changed_signal.emit)
        self.path_widget.label_changed.connect(
            self.widget_changed_signal.emit)
        
        # Forward paths_added signal
        self.path_widget.paths_added.connect(self.paths_added.emit)
        # self.path_widget./
    
    