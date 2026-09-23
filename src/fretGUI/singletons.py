from Qt.QtCore import Signal
from Qt.QtCore import QObject
from Qt.QtCore import QMutex, QMutexLocker, QTimer
import time
import queue
import pickle
import hashlib
from threading import RLock


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
    
    def disconnect(self):
        self.thread_started.disconnect()
        self.thread_finished.disconnect()
        self.thread_progress.disconnect()
        self.thread_error.disconnect()
        self.all_thread_finished.disconnect()
        self.run_btn_clicked.disconnect()
        
    
    
class RunContext(QObject):
    """Thread-safe accounting and cancellation state for one graph run."""

    drained = Signal(int)

    def __init__(self, run_id, parent=None):
        super().__init__(parent)
        self.run_id = run_id
        self._worker_uids = set()
        self._obsolete = False
        self._drain_emitted = False
        self._lock = RLock()

    @property
    def obsolete(self):
        with self._lock:
            return self._obsolete

    def invalidate(self):
        with self._lock:
            self._obsolete = True

    def register_worker(self, uid):
        with self._lock:
            if self._drain_emitted:
                raise RuntimeError("Cannot register a worker on a drained run")
            self._worker_uids.add(uid)

    def worker_finished(self, uid):
        should_emit = False
        with self._lock:
            self._worker_uids.discard(uid)
            if not self._worker_uids and not self._drain_emitted:
                self._drain_emitted = True
                should_emit = True
        if should_emit:
            self.drained.emit(self.run_id)

    def finish_if_idle(self):
        should_emit = False
        with self._lock:
            if not self._worker_uids and not self._drain_emitted:
                self._drain_emitted = True
                should_emit = True
        if should_emit:
            self.drained.emit(self.run_id)


class RunCoordinator(QObject, metaclass=SingletonMeta):
    """Single-flight, latest-request-wins graph execution coordinator."""

    run_ready = Signal(object)
    run_started = Signal(int)
    run_completed = Signal(int)
    run_discarded = Signal(int)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._generation = 0
        self._active_context = None
        self._pending = False
        self._lock = RLock()

    @property
    def active_context(self):
        with self._lock:
            return self._active_context

    @property
    def is_busy(self):
        return self.active_context is not None

    def request_run(self):
        with self._lock:
            if self._active_context is not None:
                self._active_context.invalidate()
                self._pending = True
                return None
            context = self._new_context_locked()
        self.busy_changed.emit(True)
        self.run_started.emit(context.run_id)
        self.run_ready.emit(context)
        return context

    def invalidate_active(self):
        with self._lock:
            if self._active_context is not None:
                self._active_context.invalidate()

    def is_run_current(self, run_id):
        with self._lock:
            context = self._active_context
            return (
                context is not None
                and context.run_id == run_id
                and not context.obsolete
            )

    def _new_context_locked(self):
        self._generation += 1
        context = RunContext(self._generation)
        context.drained.connect(self._on_context_drained)
        self._active_context = context
        return context

    def _on_context_drained(self, run_id):
        next_context = None
        with self._lock:
            context = self._active_context
            if context is None or context.run_id != run_id:
                return
            self._active_context = None
            pending = self._pending
            self._pending = False
            if pending:
                next_context = self._new_context_locked()

        if context.obsolete:
            self.run_discarded.emit(context.run_id)
        else:
            self.run_completed.emit(context.run_id)

        if next_context is not None:
            self.run_started.emit(next_context.run_id)
            self.run_ready.emit(next_context)
        else:
            self.busy_changed.emit(False)

    def reset_for_tests(self):
        with self._lock:
            if self._active_context is not None:
                self._active_context.invalidate()
            self._active_context = None
            self._pending = False


class NodeStateManager(QObject, metaclass=SingletonMeta):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.node_status = None
    
    def on_change_node_state(self, status):
        self.node_status = status 
    
    
class EventDebouncer:
        
    def __init__(self, delay_ms: int, on_triggered: callable):
        self.timer = QTimer()
        self.timer.setSingleShot(True)  # Важно: таймер должен быть одноразовым
        self.__on_triggered = on_triggered
        self.timer.timeout.connect(self.__on_timeout)
        self.__delay = delay_ms
        self.isactive = True
        
    def connect(self, foo):
        if not self.isactive:
            self.__on_triggered = foo
            self.timer.timeout.connect(self.__on_timeout)
            self.isactive = True
        
    def disconnect(self):
        if self.isactive: 
            self.timer.timeout.disconnect(self.__on_timeout)
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
        self.__max_size = 50
        self.__table = dict()
        self.__time_q = queue.PriorityQueue()
        self.mutex = QMutex()
        
    @property
    def size(self):
        return len(self.__table)
    
    def fbscash(self, foo):
        def wrapper(node, fbsdata, *args, **kwargs):    
            
            if fbsdata is None:
                return [None]

            run_id = getattr(fbsdata, 'run_id', None)
            if (
                run_id not in (None, 0)
                and not RunCoordinator().is_run_current(run_id)
            ):
                return [fbsdata]
            
            hash = FBSDataCash.make_hash(node, fbsdata)
            with QMutexLocker(self.mutex):
                if hash in self.__table:
                    new_fbsdata = self.get_datacopy(hash, node, fbsdata)
                    return [new_fbsdata]
          
            res = foo(node, fbsdata, *args, **kwargs)
            should_cache = (
                run_id in (None, 0)
                or RunCoordinator().is_run_current(run_id)
            )
            if not should_cache:
                return res
            with QMutexLocker(self.mutex):
                if self.size >= self.__max_size:
                    self.remove_oldest()
                self.put_data(hash, node, res[0])
            return res
        return wrapper
        
    def get_datacopy(self, hash, node, data):
        cur_time = time.perf_counter()
        self.__time_q.put_nowait((cur_time, hash))
        cached_data = self.__table[hash].copy()
        # Plot color is presentation metadata and should follow the current
        # loader row without invalidating expensive analysis cache entries.
        cached_data.color = data.color
        cached_data.run_id = data.run_id
        return cached_data
    
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


class FBSDataIDGenerator(metaclass=SingletonMeta):
    """Singleton to generate unique integer IDs for FBSData objects"""
    def __init__(self):
        self.__counter = 0
        self.mutex = QMutex()
    
    def get_next_id(self):
        """Get the next unique integer ID"""
        with QMutexLocker(self.mutex):
            self.__counter += 1
            return self.__counter
    
    
    