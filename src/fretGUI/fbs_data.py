from fretbursts.burstlib import Data
from copy import deepcopy
from singletons import FBSDataIDGenerator


class FBSData():
    def __init__(self, data=None, path=None, id=None):
        self.__data = data if data else Data()
        self.__path = path if path else ''
        self.history = []
        # Assign ID automatically if not provided
        if id is None:
            self.__id = FBSDataIDGenerator().get_next_id()
        else:
            self.__id = id
       
    @property 
    def path(self):
        return self.__path
    
    @path.setter
    def path(self, new_path):
        self.__path =  new_path
        
    @property
    def data(self):
        return self.__data
    
    @data.setter
    def data(self, new_data):
        self.__data = new_data
    
    @property
    def id(self):
        """Returns the integer ID of this FBSData object"""
        return self.__id
        
    def copy(self):
        # Preserve the ID when copying
        new_obj = FBSData(deepcopy(self.__data), self.__path, id=self.__id)
        return new_obj
    
    def __repr__(self):
        return f"fbs_data at {id(self)}, inner at {id(self.__data)}"
        
    


