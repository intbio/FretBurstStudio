from Qt.QtCore import Signal, QTimer
from abc import abstractmethod
from NodeGraphQt import NodeBaseWidget
from abc import abstractmethod    
from singletons import ThreadSignalManager


class AbstractWidgetWrapper(NodeBaseWidget):
    
    widget_changed_signal = Signal()
    debounced_signal = Signal()
    
    def __init__(self, parent=None, emit_time=500):
        super().__init__(parent)
        self.timer = QTimer(self)
        ThreadSignalManager().all_thread_finished.connect(self.__on_all_thread_finished)
        self.timer.setInterval(emit_time)
        self.timer.timeout.connect(self.__on_timeout)
        self.wire_signals()
        self.widget_changed_signal.connect(self.__on_debounced_widget_update)
        self.flag = False
        self.__workers_running = False
        
    def setEnabled(self, bool_value: bool):
        widget = self.get_custom_widget()
        widget.setEnabled(bool_value)
    
    @abstractmethod
    def wire_signals(self):
        pass
    
    def __on_debounced_widget_update(self):
        if not self.timer.isActive():
            self.__workers_running = True
            self.debounced_signal.emit()
            self.timer.start()
        else:
            self.flag = True
            self.timer.start()
        
    def __on_timeout(self):
        if self.flag and not self.__workers_running:
            self.__workers_running = True
            self.debounced_signal.emit()
            self.flag = False
            
    def __on_all_thread_finished(self):
        self.__workers_running = False
            
        
        
        
        
    
    

     
    
    
    

    
    