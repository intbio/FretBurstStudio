from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from NodeGraphQt import BaseNode
from abc import  abstractmethod, ABC
from signal_manager import SignalManager
from Qt.QtCore import QObject, Signal, QThread
from fbs_data import FBSData


class NodeWorker(QObject):
    started = Signal(int)
    finished = Signal()
    
    def __init__(self, node):
        super().__init__()
        self.node = node
        
    def __preprocess_following_nodes(self) -> int:
        self.node.disable_all_node_widgets()
        counter = 0
        for next_node in self.node.dfs():
            next_node.disable_all_node_widgets()
            counter += 1
        return counter
    
    def __enable_next_nodes_widgets(self):  
          self.node.enable_all_node_widgets()
          for next_node in self.node.dfs():
              next_node.enable_all_node_widgets()
         
    def run(self):
        n_next_nodes = self.__preprocess_following_nodes()
        self.started.emit(n_next_nodes)
        try:
            self.node.update_nodes()
        except Exception as error:
            print(error)
        finally:
            self.__enable_next_nodes_widgets()
            self.finished.emit()
              
        
        
class AbstractExecutable(BaseNode, ABC):
    def __init__(self):
        BaseNode.__init__(self)
        self.__data = dict()

    @property
    def data(self):
        return self.__data
    
    @data.setter
    def data(self, new_data: dict):
        self.__data = new_data
        
    @abstractmethod    
    def execute(self, data: FBSData) -> FBSData:
        pass
    
    def execute_many(self, data_container: dict) -> dict:
        for uid, data in data_container.items():
            data_container[uid] = self.execute(data)
        return data_container
            
    def update_nodes(self):
        if self.is_root():
            self.data = self.execute(self.data)
        else:
            combined_data = dict()
            for parent in self.iter_parent_nodes():
                parent_data = parent.get_data()
                combined_data.update(parent_data)
            self.data = self.execute_many(combined_data)
        for next_node in self.iter_children_nodes():
            next_node.update_nodes()
        
    def is_root(self) -> bool:
        return len(self.input_ports()) == 0
        
    def get_data(self):
        if self.data is None:
            if self.is_root():
                self.data = self.execute(self.data)
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
                        
            
class AbstractRecomputable(AbstractExecutable):
    
    def __init__(self):
        super().__init__()
        self.widget_wrappers = []   
    
    def update_nodes_and_pbar(self):
        self._update_thread = QThread()
        self._node_worker = NodeWorker(self)
        self._node_worker.moveToThread(self._update_thread)
        
        self._update_thread.started.connect(self._node_worker.run)
        self._node_worker.finished.connect(self._update_thread.quit)
        self._node_worker.finished.connect(self._node_worker.deleteLater)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._node_worker.started.connect(SignalManager().calculation_begin.emit)
        self._node_worker.finished.connect(SignalManager().calculation_finished.emit)
        
        self._update_thread.start()
        
    def update_nodes(self, *args, **kwargs):
        SignalManager().calculation_processed.emit()
        super().update_nodes(*args, **kwargs)
    
    def dfs(self):
        visited = set()
        for next_node in self.__dfs(visited):
            yield next_node
            
    def __dfs(self, visited):
        for child in self.iter_children_nodes():  
            visited.add(child)
            yield child
            yield from child.__dfs(visited)
    
    def add_custom_widget(self, widget, *args, **kwargs):
        if isinstance(widget, AbstractWidgetWrapper):
                        
            widget.widget_changed_signal.connect(self.update_nodes)
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
        
