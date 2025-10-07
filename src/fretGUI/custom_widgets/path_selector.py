from Qt import QtWidgets, QtCore
from Qt.QtCore import Signal
from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper


class PathRowWidget(QtWidgets.QWidget):
    del_signal = Signal()
    
    def __init__(self, parent=None):    
        super(PathRowWidget, self).__init__(parent)
                      
        self.del_button = QtWidgets.QPushButton(parent=self, text='x')
        self.del_button.setFixedSize(30, 25)
        
        self.text_field = QtWidgets.QLineEdit(parent=self, text='...')
        self.text_field.setFixedSize(200, 25)
                
        row_layout = QtWidgets.QHBoxLayout(self)
        row_layout.setContentsMargins(2, 2, 2, 2)
        row_layout.addWidget(self.del_button)
        row_layout.addWidget(self.text_field)
        
        self.wire_signals()
        
    def wire_signals(self):
        self.del_button.clicked.connect(self.on_button_click)
        
    def on_button_click(self):
        self.deleteLater()
        self.parentWidget().update_display()
        self.del_signal.emit()
        
    def set_text(self, new_text):
        self.text_field.setText(new_text)
        
    def get_text(self):
        return self.text_field.text()


class PathSelectorWidget(QtWidgets.QWidget):    
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
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum,QtWidgets.QSizePolicy.Fixed)
        
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
        
    def on_button_click(self):
        if self.file_dialog.exec_():
            selected_files = self.file_dialog.selectedFiles()
            self.add_row_widgets(selected_files)
            self.update_display()
            
    def add_row_widgets(self, file_paths):
        # existing_pahts = set(self.get_paths())
        for path in file_paths:
            # if path in existing_pahts:
            #     continue
            new_row_widget = PathRowWidget(parent=self)
            new_row_widget.del_signal.connect(self.on_del_bttn_clicked)
            new_row_widget.set_text(path)
            self.layout.insertWidget(0, new_row_widget)
            
    def on_del_bttn_clicked(self):
        self.update_node_signal.emit()
            
    def update_display(self):
        self.adjustSize()
        self.updateGeometry()
        QtWidgets.QApplication.processEvents()
        self.parentView.prepareGeometryChange()
        QtWidgets.QApplication.processEvents()
        self.parentView.draw_node()
        self.parentView.update()           
                
               

class PathSelectorWidgetWrapper(AbstractWidgetWrapper):    
    def __init__(self, parent=None):
        self.path_widget = PathSelectorWidget(parent=parent)
        super().__init__(parent)       
        self.set_name('File Widget')
        self.set_label('File') 
        self.set_custom_widget(self.path_widget)  
            
    def get_value(self):
        selected_paths = self.path_widget.get_paths()
        return selected_paths

    def set_value(self, value):
        pass
    
    def wire_signals(self):
        pass
    
    