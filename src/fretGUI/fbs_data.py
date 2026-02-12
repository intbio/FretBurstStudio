from fretbursts.burstlib import Data
from copy import deepcopy
from singletons import FBSDataIDGenerator


class FBSData():
    def __init__(self, data=None, path=None, id=None, checked=False):
        self.__data = data if data else Data()
        self.__path = path if path else ''
        self.__id = id if id else FBSDataIDGenerator().get_next_id()
        self.__checked = checked
        
    def is_checked(self):
        return self.__checked == True
       
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
        new_obj = FBSData(deepcopy(self.__data), self.__path, id=self.__id, checked=self.__checked)
        return new_obj
    
    def __repr__(self):
        return f"fbs_data at {id(self)}, inner at {id(self.__data)}"
    
    def on_state_changed(self, state: bool):
        self.__checked = state
        print(f"id: {self.id}, new state is {self.__checked}")
        
    


