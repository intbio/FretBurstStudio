from Qt.QtCore import Signal
from abc import abstractmethod
from NodeGraphQt import NodeBaseWidget
from abc import abstractmethod


class AbstractWidgetWrapper(NodeBaseWidget):
    
    widget_changed_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wire_signals()
    
    @abstractmethod
    def wire_signals(self, slot):
        pass
    
    

    
    