
from Qt.QtCore import QRunnable, QThreadPool
import itertools as it
import uuid
from singletons import ThreadSignalManager
from abc import abstractmethod
from singletons import FBSDataCash
from collections import deque



class AbstractNodeWorker(QRunnable):
    def __init__(self, start_node, data=None, node_seq=None):
        super().__init__()
        self.start_node = start_node
        self.data = data
        self.node_seq = node_seq if node_seq else deque()
        self.uid = uuid.uuid4().hex
        
    @abstractmethod
    def fill_nodeseq(self):
        pass
    
    @abstractmethod
    def _run(self):
        pass
    
    @abstractmethod
    def need_fill(self) -> bool:
        pass

    def run(self):
        if self.need_fill():
            self.fill_nodeseq()
        ThreadSignalManager().thread_started.emit(self.uid, len(self.node_seq) - 1)
        try:
            self._run()
        except Exception as error:
            print(f"__________ERROR_____________: {error}")
            ThreadSignalManager().thread_error.emit(self.uid)
        finally:
            ThreadSignalManager().thread_finished.emit(self.uid)
            
    def run_in_new_thread(self, node, data, q):
        new_worker = type(self)(node, data, q)
        pool = QThreadPool.globalInstance()
        pool.start(new_worker)


class NodeWorker(AbstractNodeWorker):    
    def __init__(self, start_node, data=None, node_seq=None):
        super().__init__(start_node, data, node_seq)   
        self.__need_fill = True
        
    def __copy__(self):
        new_worker = NodeWorker(self.start_node, 
                                self.data.copy(), 
                                self.node_seq.copy())
        return new_worker
    
    def need_fill(self):
        return self.__need_fill
        
    def _run(self):
        if self.start_node == self.node_seq[-1]:
            self.fill_nodeseq()
        while len(self.node_seq) != 0:
            ThreadSignalManager().thread_progress.emit(self.uid)
            cur_node = self.node_seq.popleft()
            data_container = cur_node.execute(self.data)
            for i, cur_data in enumerate(data_container):
                if i >= 1:
                    q_copy = self.node_seq.copy()
                    self.run_in_new_thread(q_copy[0], cur_data.copy(), q_copy)
                else:
                    self.data = cur_data
                    
    def fill_nodeseq(self):
        self.node_seq.append(self.start_node)
        self.__fill_nodeseq(self.start_node)
        self.need_fill = False
    
    def __fill_nodeseq(self, node):
        for i, next_node in enumerate(node.iter_children_nodes()):
            self.node_seq.append(next_node)
            if i == 0:
                self.__fill_nodeseq(next_node) 
            else:
                self.run_in_new_thread(next_node, self.data, self.node_seq.copy())
        
        
class UpdateWidgetNodeWorker(NodeWorker):
    def __init__(self, start_node, data=None, node_seq=None):
        super().__init__(start_node, data, node_seq)
        self.__need_backwards = True
        
    def fill_nodeseq(self):
        super().fill_nodeseq()
        self.fill_nodeseq_backwards()
        self.__need_backwards = False
        print(self.node_seq)
    
    def fill_nodeseq_backwards(self):
        self.__fill_nodeseq_backwards(self.start_node)
        
    def __fill_nodeseq_backwards(self, node):
        for i, next_node in enumerate(node.iter_parent_nodes()):
            self.node_seq.appendleft(next_node)
            if i == 0:
                self.__fill_nodeseq_backwards(next_node) 
            else:
                self.run_in_new_thread(next_node, self.data, self.node_seq.copy())

    def need_fill(self) -> bool:
        return super().need_fill() or self.__need_backwards
          
    
                    
    # def __run(self, node):
    #     try:
    #         data_container = node.execute(self.data)
    #     except Exception as error:
    #         print(f"_______________________________ERROR: node: {node}, {error}")
    #         ThreadSignalManager().thread_error.emit(self.uid)
    #         raise error
    #     else:
    #         ThreadSignalManager().thread_progress.emit(self.uid)
    #         for i, (child_node, cur_data) in enumerate(it.product(
    #             node.iter_children_nodes(), data_container)):
    #             if i > 0:
    #                 self.__run_in_new_thread(child_node, cur_data)
    #             else:
    #                 self.data = cur_data
    #                 self.__run(child_node)
                
    # def __run_in_new_thread(self, node, data):
    #     new_worker = NodeWorker(node, data.copy())
    #     pool = QThreadPool.globalInstance()
    #     pool.start(new_worker)
        
    # def __cont_computing_nodes(self):
    #     visited = set()
    #     visited = self.__dfs_first_child(self.node, visited)
    #     return len(visited)
            
    # def __dfs_first_child(self, node, visited):
    #     for child in node.iter_children_nodes():  
    #         visited.add(child)
    #         return self.__dfs_first_child(child, visited)
    #     return visited