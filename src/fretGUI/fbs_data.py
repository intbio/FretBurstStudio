from fretbursts.burstlib import Data
import hashlib
import pickle
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class FBSDataItem:
    operation: str
    operation_hash: str
    node_id: int



class FBSData(dict):
    _execution_cache = {}
    
    @classmethod
    def execution_trace(cls, func):
        def wrapper(self, data: 'FBSData', *args, **kwargs):
            # Создаем ключ кэша
            cache_key = data._create_execution_cache_key(id(self), *args, **kwargs)
            
            # Проверяем кэш
            if cache_key in cls._execution_cache:
                print(f"Cache hit for {type(self).__name__}")
                return data
            
            # Выполняем и кэшируем
            print(f"Cache miss for, executing...")
            func(self, data, *args, **kwargs)
            cls._execution_cache[cache_key] = data
            return data
        return wrapper
    
    def _create_execution_cache_key(self, *args, **kwargs) -> str:
        """Создает ключ кэша на основе узла и входных данных"""
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        return hashlib.sha256(pickle.dumps(key_data)).hexdigest()
    

    
    
if __name__ == '__main__':
    class Test1:
        
        def __init__(self):
            self.root = True
            
        def is_root(self):
            return self.root
        
        @FBSData.execution_trace
        def execute(self, data, widget=1):
            data['path'] = 'path/path'
            return data
        
    class Test2:
        
        def __init__(self):
            self.root = False
            
        def is_root(self):
            return self.root
        
        @FBSData.execution_trace
        def execute(self, data, w=1):
            data['d'] = "my data"
            return data
    
    
    d = FBSData()
    d['path'] = 'qwe'
    print(d['path'])
    
    
    
    # t1 = Test1()
    # t2 = Test2()
    # t1.execute(d, 1)
    # t2.execute(d)
    # print(d.history)
    
    # # t1.execute(d, 2)
    # t2.root = True
    # t2.execute(d, 2)
    # t1.root=False
    # t1.execute(d, 5)
    # t1.execute(d, 5)
    # print(d.history)

        
    
    
   