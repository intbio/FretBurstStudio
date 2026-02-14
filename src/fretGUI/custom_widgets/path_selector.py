from Qt import QtWidgets, QtCore, QtGui
from Qt.QtCore import Signal
from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from Qt.QtWidgets import QCheckBox
import os


class PathRowWidget(QtWidgets.QWidget):
    del_signal = Signal()
    changed_state = Signal(bool)
    
    def __init__(self, parent=None, path_id=None):    
        super(PathRowWidget, self).__init__(parent)
        
        self.checkbox = QCheckBox(parent=parent, checked=True)
                      
        self.del_button = QtWidgets.QPushButton(parent=self)
        self.del_button.setFixedSize(25, 25)
        style = self.del_button.style()
        close_icon = style.standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton)
        self.del_button.setIcon(close_icon)
        self.del_button.setIconSize(QtCore.QSize(16, 16))
        self.del_button.setToolTip("Close file")
        
        # ID label on the left
        self.id_label = QtWidgets.QLabel(parent=self, text='-')
        self.id_label.setFixedSize(25, 25)
        self.id_label.setAlignment(QtCore.Qt.AlignCenter)
        self.id_label.setStyleSheet("background-color: #e0e0e0; border: 1px solid #ccc;")
        
        self.text_field = QtWidgets.QLineEdit(parent=self, text='...')
        self.text_field.setFixedSize(200, 25)
        self.text_field.setReadOnly(True)  # Make it read-only
        
        # Store full path internally while displaying only basename
        self._full_path = ''
                
        row_layout = QtWidgets.QHBoxLayout(self)
        row_layout.setContentsMargins(2, 2, 2, 2)
        
        row_layout.addWidget(self.id_label)
        row_layout.addWidget(self.text_field)
        row_layout.addWidget(self.del_button)
        row_layout.addWidget(self.checkbox)
        
        # Set ID if provided
        if path_id is not None:
            self.set_id(path_id)
        
        # Set default tooltip
        self.set_tooltip("Not loaded, press RUN")
        
        self.wire_signals()
        
    def wire_signals(self):
        self.del_button.clicked.connect(self.on_button_click)
        self.checkbox.stateChanged.connect(self.on_state_chenged)
        
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
        """Set the full path, but display only the basename"""
        self._full_path = new_text
        # Display only the basename
        basename = os.path.basename(new_text) if new_text else '...'
        self.text_field.setText(basename)
        
    def get_text(self):
        """Return the full path"""
        return self._full_path if self._full_path else self.text_field.text()
    
    def set_id(self, path_id):
        """Set the ID displayed in the label"""
        self.id_label.setText(str(path_id))
    
    def get_id(self):
        """Get the ID from the label"""
        text = self.id_label.text()
        return int(text) if text and text != '-' else None
    
    def set_tooltip(self, tooltip_text):
        """Set tooltip for the row widget"""
        self.setToolTip(tooltip_text)
        
    def is_checked(self):
        return self.checkbox.isChecked()


class PathSelectorWidget(QtWidgets.QWidget):  
    
    del_btn_clicked = Signal()
    checkbox_clicked = Signal()
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
        
    def get_paths(self) -> list:
        existing_paths = []
        total_widgets = self.layout.count()
        for i in range(total_widgets):
            item = self.layout.itemAt(i)
            if item is None:
                continue
            row_widget = item.widget()
            if row_widget and isinstance(item.widget(), PathRowWidget):
                text = row_widget.get_text()
                existing_paths.append(text)
        return existing_paths
    
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
        for path in file_paths:
            path_id = path_to_id.get(path)
            new_row_widget = PathRowWidget(parent=self, path_id=path_id)
            self.__wire_row_widget(new_row_widget)
            self.rowwidget_map[path_id] = new_row_widget
            
            new_row_widget.set_text(path)
            self.layout.addWidget(new_row_widget)
            
    def __wire_row_widget(self, row_widget):
        row_widget.changed_state.connect(
            lambda state: self.checkbox_clicked.emit()
        )        
        row_widget.del_signal.connect(self.del_btn_clicked.emit)
        
    
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
        total_widgets = self.layout.count()
        for i in range(total_widgets):
            item = self.layout.itemAt(i)
            if item is None:
                continue
            row_widget = item.widget()
            if row_widget and isinstance(item.widget(), PathRowWidget):
                if row_widget.get_text() == path:
                    row_widget.set_tooltip(tooltip_text)
                    break
            
    def on_del_bttn_clicked(self):
        print(self.get_paths())
            
    def update_display(self):
        # Update layout
        if hasattr(self, 'layout'):
            self.layout.activate()
        self.adjustSize()
        self.updateGeometry()
        
        # Manually update node size based on widget count
        self.update_node_size()
        
        # Explicitly resize the wrapper's border frame if it exists
        if self._wrapper and hasattr(self._wrapper, 'resize_border_frame'):
            self._wrapper.resize_border_frame()
        
        # Process events to ensure updates are applied
        QtWidgets.QApplication.processEvents()           
                
               

class PathSelectorWidgetWrapper(AbstractWidgetWrapper):    
    paths_added = Signal(list)  # Forward the signal from PathSelectorWidget
    
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
            
    def get_value(self):
        selected_paths = self.path_widget.get_paths()
        return selected_paths
    
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
        self.path_widget.update_tooltip_for_path(path, tooltip_text)
    
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
        
        # Forward paths_added signal
        self.path_widget.paths_added.connect(self.paths_added.emit)
        # self.path_widget./
    
    