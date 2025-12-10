from Qt import QtWidgets
from Qt.QtWidgets import QVBoxLayout, QProgressBar
from Qt.QtCore import QTimer, Signal
import Qt


class ProgressBar(QtWidgets.QWidget):
    block_ui = Signal()
    release_ui = Signal()
    
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.bars = {}
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(5)
    
    def on_thread_started(self, uid: str, max_values: int):
        if len(self.bars) == 0:
            self.block_ui.emit()
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
        pbar = self.bars.pop(uid)
        if len(self.bars) == 0:
            self.release_ui.emit()
        self.layout.removeWidget(pbar)
        pbar.deleteLater()

            
    