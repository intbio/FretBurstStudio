from Qt import QtWidgets
from Qt.QtWidgets import QVBoxLayout, QProgressBar
from Qt.QtCore import QTimer
import Qt


class ProgressBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.bars = {}
        
        self.layout = QVBoxLayout(self)
        
        # self.container_widget = QtWidgets.QWidget()
        # self.container_layout = QVBoxLayout(self.container_widget)
        # self.container_layout.setAlignment(Qt.AlignTop)
        self.layout.setSpacing(5)
        
        # self.layout.addWidget(self.container_widget)
        # self.setLayout(self.layout)
    
    def on_thread_started(self, uid: str, max_values: int):
        print('worker started', uid)
        new_pbar = QProgressBar()
        new_pbar.setRange(0, max_values)
        self.layout.addWidget(new_pbar)
        self.bars[uid] = new_pbar
        
    def on_thread_finished(self, uid: str):
        print("worker finished", uid)
        QTimer.singleShot(3000, lambda: self.__del_pbar(uid))

    
    def on_thread_processed(self, uid: str):
        print("worker progress", uid)
        pbar = self.bars[uid]
        cur_value = pbar.value()
        pbar.setValue(cur_value + 1)
        
    def on_thread_error(self, uid: str):
        print("worker error", uid)
        
    def __del_pbar(self, uid):
        pbar = self.bars[uid]
        self.layout.removeWidget(pbar)
        pbar.deleteLater()
            
    