from fretbursts.burstlib import Data
from copy import deepcopy



class FBSData():
    def __init__(self, data=None, path=None):
        self.__data = data if data else Data()
        self.__path = path if path else ''
        self.history = []
       
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
        
    def copy(self):
        new_obj = FBSData(deepcopy(self.__data), self.__path)
        return new_obj
    
    def __repr__(self):
        return f"fbs_data at {id(self)}, inner at {id(self.__data)}"
        
    


