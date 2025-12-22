from Qt import QtWidgets, QtCore
from Qt.QtCore import Signal
from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper


class PathRowWidget(QtWidgets.QWidget):
    del_signal = Signal()
    
    def __init__(self, parent=None, path_id=None):    
        super(PathRowWidget, self).__init__(parent)
                      
        self.del_button = QtWidgets.QPushButton(parent=self, text='x')
        self.del_button.setFixedSize(30, 25)
        
        # ID label on the left
        self.id_label = QtWidgets.QLabel(parent=self, text='-')
        self.id_label.setFixedSize(40, 25)
        self.id_label.setAlignment(QtCore.Qt.AlignCenter)
        self.id_label.setStyleSheet("background-color: #e0e0e0; border: 1px solid #ccc;")
        
        self.text_field = QtWidgets.QLineEdit(parent=self, text='...')
        self.text_field.setFixedSize(200, 25)
                
        row_layout = QtWidgets.QHBoxLayout(self)
        row_layout.setContentsMargins(2, 2, 2, 2)
        row_layout.addWidget(self.del_button)
        row_layout.addWidget(self.id_label)
        row_layout.addWidget(self.text_field)
        
        # Set ID if provided
        if path_id is not None:
            self.set_id(path_id)
        
        self.wire_signals()
        
    def wire_signals(self):
        self.del_button.clicked.connect(self.on_button_click)
        
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
        self.text_field.setText(new_text)
        
    def get_text(self):
        return self.text_field.text()
    
    def set_id(self, path_id):
        """Set the ID displayed in the label"""
        self.id_label.setText(str(path_id))
    
    def get_id(self):
        """Get the ID from the label"""
        text = self.id_label.text()
        return int(text) if text and text != '-' else None


class PathSelectorWidget(QtWidgets.QWidget):  
    
    del_btn_clicked = Signal()
    paths_added = Signal(list)  # Signal emitted when paths are added, with list of paths
    _get_path_to_id_callback = None  # Callback to get path_to_id mapping
    _wrapper = None  # Reference to the wrapper widget
    
    # Size constants
    BASE_HEIGHT = 60  # Height for button and margins
    ROW_HEIGHT = 40   # Height per path row widget
    MIN_WIDTH = 300   # Minimum node width
    DEFAULT_WIDTH = 350  # Default node width
      
    def __init__(self, parent=None):
        super(PathSelectorWidget, self).__init__()
        
        self.parentView = parent
               
        self.file_dialog = QtWidgets.QFileDialog()
        self.file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        self.file_dialog.setNameFilter("все файлы (*);;Изображения (*.png *.jpg);;Текстовые файлы (*.txt)")
        
        self.open_button = QtWidgets.QPushButton(parent=self, text='Open')
        
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.addWidget(self.open_button, alignment=QtCore.Qt.AlignBottom)
        
        self.wire_signals()
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed,QtWidgets.QSizePolicy.Fixed)
        
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
        count = 0
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
        """Manually update the node size based on current widget count"""
        if not self.parentView:
            return
        
        width, height = self.calculate_required_size()
        
        # Set the node view size directly
        if hasattr(self.parentView, '_width') and hasattr(self.parentView, '_height'):
            self.parentView.prepareGeometryChange()
            self.parentView._width = max(self.MIN_WIDTH, width)
            self.parentView._height = max(150, height)  # Minimum height
            self.parentView.update()
            
            # Also update the scene
            scene = self.parentView.scene()
            if scene:
                scene.update()
        
    def on_button_click(self):
        if self.file_dialog.exec_():
            selected_files = self.file_dialog.selectedFiles()
            # Emit signal before adding widgets so IDs can be assigned (synchronously)
            self.paths_added.emit(selected_files)
            # Get path_to_id mapping after IDs are assigned
            path_to_id = self._get_path_to_id_callback() if self._get_path_to_id_callback else {}
            self.add_row_widgets(selected_files, path_to_id=path_to_id)
            self.update_display()
            
    def add_row_widgets(self, file_paths, path_to_id=None):
        # existing_pahts = set(self.get_paths())
        if path_to_id is None:
            path_to_id = {}
        for path in file_paths:
            # if path in existing_pahts:
            #     continue
            path_id = path_to_id.get(path)
            new_row_widget = PathRowWidget(parent=self, path_id=path_id)
            new_row_widget.del_signal.connect(self.del_btn_clicked.emit)
            new_row_widget.set_text(path)
            self.layout.insertWidget(0, new_row_widget)
    
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
        self.set_custom_widget(self.path_widget)
        
        # Set callback for path widget to get path_to_id
        self.path_widget._get_path_to_id_callback = lambda: self._path_to_id
        # Give path widget reference to this wrapper so it can update geometry
        self.path_widget._wrapper = self  
            
    def get_value(self):
        selected_paths = self.path_widget.get_paths()
        return selected_paths

    def set_value(self, value):
        pass
    
    def update_path_ids(self, path_to_id):
        """Update IDs for paths in the widget"""
        self._path_to_id = path_to_id  # Store the mapping
        self.path_widget.update_path_ids(path_to_id)
    
    def wire_signals(self):
        self.path_widget.open_button.clicked.connect(
            self.widget_changed_signal.emit)
        self.path_widget.del_btn_clicked.connect(
            self.widget_changed_signal.emit)
        # Forward paths_added signal
        self.path_widget.paths_added.connect(self.paths_added.emit)
    
    