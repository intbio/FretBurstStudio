from Qt.QtCore import Signal
from Qt.QtCore import QObject


class SingletonMeta(type(QObject)):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
    
    
class ThreadSignalManager(QObject, metaclass=SingletonMeta):
    _instance = None
    thread_started = Signal(str)
    thread_finished = Signal(str)
    thread_progress = Signal(str)
    thread_error = Signal(str)
    


    
    
