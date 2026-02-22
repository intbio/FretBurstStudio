from Qt.QtCore import Signal, QTimer
from abc import abstractmethod
from NodeGraphQt import NodeBaseWidget
from abc import abstractmethod    
from singletons import ThreadSignalManager
from functools import wraps


def debounce(wait_ms):
    timer = QTimer()
    timer.setSingleShot(True)
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            timer.stop()
            try:
                timer.timeout.disconnect()
            except TypeError:
                pass # Ignore if not connected yet
            timer.timeout.connect(lambda: func(*args, **kwargs))
            timer.start(wait_ms)
        wrapper.timer = timer
        return wrapper
    return decorator



class AbstractWidgetWrapper(NodeBaseWidget):
    
    widget_changed_signal = Signal()
    debounced_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wire_signals()
        self.widget_changed_signal.connect(self.__on_debounced_widget_update)
        
    def setEnabled(self, bool_value: bool):
        widget = self.get_custom_widget()
        widget.setEnabled(bool_value)
    
    @abstractmethod
    def wire_signals(self):
        pass
    
    @debounce(500)
    def __on_debounced_widget_update(self):
        self.debounced_signal.emit()
            
        
        
        
        
    
    

     
    
    
    

    
    