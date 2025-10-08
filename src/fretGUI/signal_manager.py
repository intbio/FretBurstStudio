from Qt.QtCore import Signal
from Qt.QtCore import QObject


class SingletonMeta(type(QObject)):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
    
    
class SignalManager(QObject, metaclass=SingletonMeta):
    _instance = None
    calculation_begin = Signal(int)
    calculation_finished = Signal()
    calculation_processed = Signal()
    
