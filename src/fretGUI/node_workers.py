
from Qt.QtCore import QRunnable, QThreadPool
import uuid
from fretGUI.singletons import RunContext, ThreadSignalManager
from abc import abstractmethod
from collections import deque
from copy import deepcopy



class AbstractNodeWorker(QRunnable):
    def __init__(self, start_node, data=None, node_seq=None, context=None):
        super().__init__()
        self.start_node = start_node
        self.data = data
        self.node_seq = node_seq if node_seq else deque()
        self.uid = uuid.uuid4().hex
        self.context = context or RunContext(0)
        self.context.register_worker(self.uid)
        if self.data is not None:
            self.data.run_id = self.context.run_id
        
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
        try:
            if self.need_fill() and not self.context.obsolete:
                self.fill_nodeseq()
            ThreadSignalManager().thread_started.emit(
                self.uid,
                len(self.node_seq) - 1,
            )
            if not self.context.obsolete:
                self._run()
        except Exception as error:
            self.context.invalidate()
            ThreadSignalManager().thread_error.emit(self.uid)
            raise error
        finally:
            ThreadSignalManager().thread_finished.emit(self.uid)
            self.context.worker_finished(self.uid)
            
    def run_in_new_thread(self, node, data, q, *args, **kwargs):
        new_worker = type(self)(
            node,
            deepcopy(data),
            q,
            *args,
            context=self.context,
            **kwargs,
        )
        pool = QThreadPool.globalInstance()
        try:
            pool.start(new_worker)
        except Exception:
            self.context.worker_finished(new_worker.uid)
            raise


class NodeWorker(AbstractNodeWorker):    
    def __init__(
        self,
        start_node,
        data=None,
        node_seq=None,
        need_fill=True,
        context=None,
    ):
        super().__init__(start_node, data, node_seq, context=context)
        self.__need_fill = need_fill
    
    def need_fill(self):
        return self.__need_fill
        
    def _run(self):
        while len(self.node_seq) != 0:
            if self.context.obsolete:
                break
            ThreadSignalManager().thread_progress.emit(self.uid)
            cur_node = self.node_seq.popleft()
            try:
                data_container = cur_node.execute(self.data)
            except AttributeError as error:
                if self.data is None:
                    continue
                else:
                    raise error
            except Exception as error:
                raise error
            else:
                if self.context.obsolete:
                    break
                for i, cur_data in enumerate(data_container):
                    
                    if cur_data is None:
                        self.data = cur_data
                        continue
                    
                    cur_data.run_id = self.context.run_id
                    cur_data.prev_nodeid = id(cur_node)
                    if i >= 1:
                        self.run_in_new_thread(cur_node, cur_data, self.node_seq.copy(), False)
                    else:
                        self.data = cur_data
                    
    def fill_nodeseq(self):
        paths = []
        self._fill_nodeseq(self.start_node, self.node_seq, paths)
        
        for i, cur_pathq in enumerate(paths):
            if i == 0:
                self.node_seq = cur_pathq
                self.__need_fill = False
            else:
                self.run_in_new_thread(self.start_node, self.data, cur_pathq, False)
    
    def _fill_nodeseq(self, node, visited, paths=[]):
        visited.append(node)
        children = list(node.iter_children_nodes())
        if len(children) == 0:
            paths.append(visited.copy())
        elif len(children) == 1:
            next_node = children[0]
            self._fill_nodeseq(next_node, visited, paths)
        else:
            for next_node in children:
                self._fill_nodeseq(next_node, visited.copy(), paths)
    