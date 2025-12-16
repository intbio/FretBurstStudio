from Qt.QtCore import Signal
from Qt.QtCore import QObject
from Qt.QtCore import QMutex, QMutexLocker, QTimer
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
    all_thread_finished = Signal()
    run_btn_clicked = Signal()
    
    
class EventDebouncer(metaclass=SingletonMeta):
        
    def __init__(self, delay_ms: int, on_triggered: callable):
        print('________________________init________________-')
        self.timer = QTimer()
        self.timer.setSingleShot(True)  # Важно: таймер должен быть одноразовым
        self.__on_triggered = on_triggered
        self.timer.timeout.connect(self.__on_timeout)
        self.__delay = delay_ms
        self.isactive = True
        
    def connect(self, foo):
        self.__on_triggered = foo
        self.timer.timeout.connect(self.__on_timeout)
        self.isactive = True
        
    def disconnect(self):
        self.timer.disconnect(self.__on_timeout)
        self.isactive = False
        
    def push_event(self, event):
        if self.isactive:
            self._last_event = event
            self.timer.stop()  # Останавливаем текущий таймер
            self.timer.start(self.__delay)  # Запускаем заново
            
    def __on_timeout(self):
        self.__on_triggered(self._last_event)
        
           
    
    
class FBSDataCash(metaclass=SingletonMeta):
    def __init__(self):
        self.__max_size = 30
        self.__table = dict()
        self.__time_q = queue.PriorityQueue()
        self.mutex = QMutex()
        
    @property
    def size(self):
        return len(self.__table)
    
    def fbscash(self, foo):
        def wrapper(node, fbsdata, *args, **kwargs):           
            hash = FBSDataCash.make_hash(node, fbsdata)
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
        cur_time = time.perf_counter()
        self.__time_q.put_nowait((cur_time, hash))
        return self.__table[hash].copy()
    
    def put_data(self, hash, node, data):
        cur_time = time.perf_counter()
        self.__table[hash] = data.copy()
        self.__time_q.put_nowait((cur_time, hash))
            
    def remove_oldest(self):
        while self.__time_q.not_empty:
            time, hash = self.__time_q.get_nowait()
            if hash in self.__table:
                self.__table.pop(hash)
                break

    @staticmethod        
    def make_hash(node, data):
        values = [widget.get_value() for name, widget in node.widgets().items()]
        values.append(data.data)
        values.append(id(node))
        pickle_ = pickle.dumps(values)
        hash_hex = hashlib.sha256(pickle_).hexdigest()
        return hash_hex

    
    
