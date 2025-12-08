from Qt.QtCore import Signal
from Qt.QtCore import QObject
from Qt.QtCore import QMutex, QMutexLocker
from copy import deepcopy
import time
import queue
import pickle
import hashlib


class SingletonMeta(type(QObject)):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
    
    
class ThreadSignalManager(QObject, metaclass=SingletonMeta):
    thread_started = Signal((str, int))
    thread_finished = Signal(str)
    thread_progress = Signal(str)
    thread_error = Signal(str)
    
    
class FBSDataCash(metaclass=SingletonMeta):
    def __init__(self, max_size=30):
        self.__max_size = max_size
        self.__table = dict()
        self.__time_q = queue.PriorityQueue()
        self.mutex = QMutex()
        
    @property
    def size(self):
        return len(self.__table)
    
    def fbscash(self, foo):
        def wrapper(node, fbsdata, *args, **kwargs):
            hash = self.__make_hash(node, fbsdata)
            with QMutexLocker(self.mutex):
                if hash in self.__table:
                    new_fbsdata = self.get_datacopy(hash, node, fbsdata)
                    return [new_fbsdata]
          
            res = foo(node, fbsdata, *args, **kwargs)
            with QMutexLocker(self.mutex):
                if self.size >= self.__max_size:
                    self.remove_oldest()
                self.put_data(hash, node, res[0])
            return res
        return wrapper
        
    def get_datacopy(self, hash, node, data):
        print(f"___________from cash______________ {node}")
        cur_time = time.perf_counter()
        self.__time_q.put_nowait((cur_time, hash))
        return self.__table[hash].copy()
    
    def put_data(self, hash, node, data):
        cur_time = time.perf_counter()
        self.__table[hash] = data.copy()
        self.__time_q.put_nowait((cur_time, hash))
            
    def remove_oldest(self):
        print("remove oldest")
        while self.__time_q.not_empty:
            time, hash = self.__time_q.get_nowait()
            if hash in self.__table:
                self.__table.pop(hash)
                break
            
    def __make_hash(self, node, data):
        values = [widget.get_value() for name, widget in node.widgets().items()]
        values.append(id(node))
        values.append(data.data)
        pickle_ = pickle.dumps(values)
        hash_hex = hashlib.sha256(pickle_).hexdigest()
        return hash_hex



    
    
