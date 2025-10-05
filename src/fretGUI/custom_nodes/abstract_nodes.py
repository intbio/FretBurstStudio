from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper

from NodeGraphQt import BaseNode
from abc import  abstractmethod, ABC
        
        
class AbstractExecutable(BaseNode, ABC):
    def __init__(self):
        BaseNode.__init__(self)
        self.__data = None

    @property
    def data(self):
        return self.__data
    
    @data.setter
    def data(self, new_data: dict):
        self.__data = new_data
        
    @abstractmethod
    def execute(self, *args, **kwargs) -> dict:
        pass
        
    def is_root(self) -> bool:
        return len(self.input_ports()) == 0
        
    def get_data(self) -> dict:
        if self.data is None:
            if self.is_root():
                self.data = self.execute()
            else:
                combined_data = {}
                for parent in self.iter_parent_nodes():
                    parent_data = parent.get_data()
                    combined_data.update(parent_data)
                self.data = self.execute(**combined_data)
        return self.data
           
    def iter_parent_nodes(self):
        for port in self.input_ports():
            connected_ports = port.connected_ports()
            for connected_port in connected_ports:
                connected_node = connected_port.node()
                yield connected_node
                
    def iter_children_nodes(self):
        for port in self.output_ports():
            connected_ports = port.connected_ports()
            for connected_port in connected_ports:
                connected_node = connected_port.node()
                yield connected_node
        
    def update_nodes(self):
        if self.is_root():
            self.data = self.execute()
        else:
            combined_data = {}
            for parent in self.iter_parent_nodes():
                parent_data = parent.get_data()
                combined_data.update(parent_data)
            self.data = self.execute(**combined_data)
        for next_node in self.iter_children_nodes():
            next_node.update_nodes()
            
            
class AbstractRecomputable(AbstractExecutable):
    
    def __init__(self):
        super().__init__()
        self.widget_wrappers = []
    
    def add_custom_widget(self, widget, *args, **kwargs):
        if isinstance(widget, AbstractWidgetWrapper):
            widget.widget_changed_signal.connect(self.update_nodes)
            self.widget_wrappers.append(widget)
        super().add_custom_widget(widget, *args, **kwargs)
        
    def wire_wrappers(self):
        if len(self.widget_wrappers) == 0:
            return None
        for widget_wrapper in self.widget_wrappers:
            widget_wrapper.widget_changed_signal.connect(self.update_nodes)
            
    def unwire_wrappers(self):
        if len(self.widget_wrappers) == 0:
            return None
        for widget_wrapper in self.widget_wrappers:
            widget_wrapper.widget_changed_signal.disconnect()
