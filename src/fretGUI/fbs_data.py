from fretbursts.burstlib import Data
import hashlib
import pickle
from dataclasses import dataclass


@dataclass
class FBSDataItem:
    operation: str
    operation_hash: str
    node_id: int



class FBSData(dict):
    def __init__(self, data=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__history = []
        self.__data = data if data else Data()
        self.__call_counter = 0
        
    def __hash__(self):
        return FBSData.__hash_arguments(self)

    @property
    def history(self):
        return self.__history
    
    @property
    def data(self):
        return self.__data
    
    @data.setter
    def data(self, new_data):
        self.__data = new_data
    
    def clear_history(self):
        self.__history = []
    
    @staticmethod
    def execution_trace(func):
        def wrapper(node, fbsdata, *args, **kwargs):
            new_hash = FBSData.__hash_arguments(id(node), *args, **kwargs)
            if node.is_root():
                fbsdata.__call_counter = 0
            return fbsdata.__trace(new_hash, fbsdata.__call_counter, func, node, *args, **kwargs)
        return wrapper
    
    def __trace(self, new_hash, i, func, node, *args, **kwargs):
        self.__call_counter += 1
        if len(self.history) == 0:
            new_item = FBSDataItem(type(node).__name__, new_hash, id(node))
            self.__history.append(new_item)
            print("CALL1", node)
            return func(node, self, *args, **kwargs)
        if i >= len(self.history):
            print("CALL2", node)
            self.__history.append(FBSDataItem(type(node).__name__, new_hash, id(node)))
            return func(node, self, *args, **kwargs)
        if new_hash != self.history[i].operation_hash:
            if id(node) != self.history[i].node_id:
                print("CALL4", node)
                self.__history = self.__history[: i + 1]
            new_item = FBSDataItem(type(node).__name__, new_hash, id(node))
            self.__history[i] = new_item
            return func(node, self, *args, **kwargs)
        return self          
            
    @staticmethod
    def __hash_arguments(*args, **kwargs) -> int:
        list_args = [str(arg) for arg in args]
        list_kwargs = [str(v) for v in kwargs.values()]
        key = sorted(list_args + list_kwargs)
        return int(hashlib.md5(pickle.dumps(key)).hexdigest(), 16)
    
    
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

        
    
    
   