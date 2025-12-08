from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from NodeGraphQt import BaseNode
from abc import  abstractmethod, ABC
from Qt.QtCore import QObject, Signal, QRunnable, QThreadPool
from fbs_data import FBSData
from copy import deepcopy
import itertools as it
import uuid
from singletons import ThreadSignalManager
import pickle
import hashlib
from copy import deepcopy


class NodeWorker(QRunnable, QObject):
    started = Signal(str)
    finished = Signal(str)
    progress = Signal(str)
    error = Signal(str)
    
    def __init__(self, node, data=None):
        QRunnable.__init__(self)
        QObject.__init__(self)
        
        # self.started.connect(ThreadSignalManager().thread_started.emit)
        
        self.node = node
        self.data = data
        self.uid = str(uuid.uuid4())
       
    def run(self):
        print("RUN")
        self.started.emit(self.uid)
        self.__run(self.node)
                    
    def __run(self, node):
        try:
            data_container = node.execute(self.data)
        except Exception as error:
            print(f"_______________________________ERROR: node: {node}, {error}")
            self.error.emit(id(self))
            raise error
        else:
            for i, (child_node, cur_data) in enumerate(it.product(
                node.iter_children_nodes(), data_container)):
                if i > 0:
                    self.__run_in_new_thread(child_node, cur_data)
                else:
                    self.data = cur_data
                    self.__run(child_node)
                
    def __run_in_new_thread(self, node, data):
        new_worker = NodeWorker(node, data.copy())
        # new_worker.started.connect(ThreadSignalManager().thread_started.emit)
        pool = QThreadPool.globalInstance()
        pool.start(new_worker)
            
            
class AbstractExecutable(BaseNode, ABC):
    def __init__(self):
        BaseNode.__init__(self)
        
    @abstractmethod    
    def execute(self, data: FBSData=None) -> FBSData:
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
                
                                  
class AbstractRecomputable(AbstractExecutable):
    def __init__(self):
        super().__init__()
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
            widget_wrapper.widget_changed_signal.connect(self.update_nodes_and_pbar)
            
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
        
