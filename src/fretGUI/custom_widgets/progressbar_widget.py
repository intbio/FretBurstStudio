from Qt import QtWidgets
from Qt.QtWidgets import QVBoxLayout, QProgressBar
from Qt.QtCore import Qt, QTimer, Signal
from fretGUI.singletons import ThreadSignalManager


class ProgressBar(QtWidgets.QWidget):
    block_ui = Signal()
    release_ui = Signal()
    
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.bars = {}
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(2)
        
        self.release_ui.connect(ThreadSignalManager().all_thread_finished.emit)
    
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
        pbar = self.bars.pop(uid)
        if len(self.bars) == 0:
            self.release_ui.emit()
        QTimer.singleShot(500, lambda: self.__del_pbar(pbar))

    def on_thread_processed(self, uid: str):
        pbar = self.bars[uid]
        cur_value = pbar.value()
        pbar.setValue(cur_value + 1)
        
    def on_thread_error(self, uid: str):
        print("worker error", uid)
        
    def __del_pbar(self, pbar):
        self.layout.removeWidget(pbar)
        pbar.deleteLater()

            
class ProgressBar2(QtWidgets.QWidget):
    block_ui = Signal()
    release_ui = Signal()
    
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.workers = {}  # Track worker info: {uid: {'max': int, 'current': int}}
        self.total_max = 0
        self.total_current = 0
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(28)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFormat("%p%")
        self.layout.addWidget(self.progress_bar)
        
        self.hide()

    def on_run_started(self, run_id):
        self.workers.clear()
        self.total_max = 0
        self.total_current = 0
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setValue(0)

    def on_busy_changed(self, busy):
        if busy:
            self.block_ui.emit()
            self.show()
        else:
            self.release_ui.emit()
            self.hide()
    
    def on_thread_started(self, uid: str, max_values: int):
        print('worker started', uid)
        self.workers[uid] = {'max': max_values, 'current': 0}
        self.total_max += max_values
        self.progress_bar.setRange(0, self.total_max)
    
    def on_thread_finished(self, uid: str):
        print("worker finished", uid)
        worker_info = self.workers.pop(uid, None)
        if worker_info is None:
            return
        # Ensure we account for any remaining progress from this worker
        remaining = worker_info['max'] - worker_info['current']
        self.total_current += remaining
        self.progress_bar.setValue(self.total_current)
    
    def on_thread_processed(self, uid: str):
        if uid in self.workers:
            self.workers[uid]['current'] += 1
            self.total_current += 1
            self.progress_bar.setValue(self.total_current)
        
    def on_thread_error(self, uid: str):
        print("worker error", uid)
        # On error, treat it as finished to clean up
        if uid in self.workers:
            worker_info = self.workers.pop(uid)
            remaining = worker_info['max'] - worker_info['current']
            self.total_max -= remaining  # Remove remaining from total