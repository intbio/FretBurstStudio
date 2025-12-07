from Qt import QtWidgets
from Qt.QtWidgets import QVBoxLayout, QProgressBar
import Qt


class ProgressBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        self.container_widget = QtWidgets.QWidget()
        self.container_layout = QVBoxLayout(self.container_widget)
        # self.container_layout.setAlignment(Qt.AlignTop)
        self.container_layout.setSpacing(5)
        
        self.layout.addWidget(self.container_widget)
        self.setLayout(self.layout)
    
    def on_thread_started(self, uid:str):
        print('started', uid)
        new_pbar = QProgressBar(self)
        new_pbar.setRange(0, 100)
        new_pbar.setValue(50)
        self.layout.addWidget(new_pbar)
        
    def on_thread_finished(self):
        pass
    
    def on_thread_processed(self):
        pass
        
    def on_thread_error(self):
        pass
            
    