from Qt.QtCore import Signal
from abc import abstractmethod
from NodeGraphQt import NodeBaseWidget
from abc import abstractmethod


class AbstractWidgetWrapper(NodeBaseWidget):
    
    widget_changed_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wire_signals()
        
    def setEnabled(self, bool_value: bool):
        widget = self.get_custom_widget()
        widget.setEnabled(bool_value)
    
    @abstractmethod
    def wire_signals(self):
        pass
    
    
    

    
    