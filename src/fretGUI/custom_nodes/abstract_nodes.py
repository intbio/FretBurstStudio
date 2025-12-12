from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from NodeGraphQt import BaseNode
from abc import  abstractmethod, ABC
from fbs_data import FBSData
from node_workers import UpdateWidgetNodeWorker   
from Qt.QtCore import QThreadPool   
from singletons import ThreadSignalManager
from collections import deque
            
            
            
class AbstractExecutable(BaseNode, ABC):
    def __init__(self, *args, **kwargs):
        BaseNode.__init__(self, *args, **kwargs)
        
    @abstractmethod    
    def execute(self, data: FBSData=None) -> list[FBSData]:
        pass
        
    def is_root(self) -> bool:
        return len(self.input_ports()) == 0
           
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
                
    def bfs(self):
        visited = set([self])
        q = deque([self])
        while len(q) != 0:
            cur_node = q.popleft()
            for nextnode in cur_node.iter_children_nodes():
                if nextnode in visited:
                    continue
                visited.add(nextnode)
                yield nextnode
                
                                  
class AbstractRecomputable(AbstractExecutable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget_wrappers = []  
        
    def on_widget_changed(self):
        root_nodes = self.find_roots()
        
    def find_roots(self):
        if self.is_root():
            return [self]
        root_nodes = []
        self.__find_roots(self, root_nodes)   
        return root_nodes
    
    def __find_roots(self, node, root_nodes):
        for parent in node.iter_parent_nodes():
            if parent.is_root():
                root_nodes.append(parent)
            self.__find_roots(parent, root_nodes)
    
    def add_custom_widget(self, widget, *args, **kwargs):
        if isinstance(widget, AbstractWidgetWrapper):               
            widget.widget_changed_signal.connect(self.on_widget_changed)
            self.widget_wrappers.append(widget)  
        super().add_custom_widget(widget, *args, **kwargs)
        
    def wire_wrappers(self):
        if len(self.widget_wrappers) == 0:
            return None
        for widget_wrapper in self.widget_wrappers:
            widget_wrapper.widget_changed_signal.connect(self.on_widget_triggered)
            
    def unwire_wrappers(self):
        if len(self.widget_wrappers) == 0:
            return None
        for widget_wrapper in self.widget_wrappers:
            widget_wrapper.widget_changed_signal.disconnect()
            
    def disable_all_node_widgets(self):
        for widget_name, widget in self.widgets().items():
            widget.setEnabled(False)

    def enable_all_node_widgets(self):
        for widget_name, widget in self.widgets().items():
            widget.setEnabled(True)
            
    def on_widget_triggered(self):
        print("widget trigiered")
        worker = UpdateWidgetNodeWorker(self)
        pool = QThreadPool.globalInstance()
        pool.start(worker)

