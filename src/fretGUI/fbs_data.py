from fretbursts.burstlib import Data
from copy import deepcopy
from singletons import FBSDataIDGenerator


class FBSData():
    def __init__(self, data=None, path=None, id=None, checked=False, node_metadata=None):
        self.__data = data if data else Data()
        self.__path = path if path else ''
        self.__id = id if id else FBSDataIDGenerator().get_next_id()
        self.__checked = checked
        self.__node_metadata = node_metadata if node_metadata else []
        
    def add_node_metadata(self, metadata: dict):
        self.__node_metadata.append(metadata)
        
    @property
    def node_metadata(self):
        return self.__node_metadata
        
    def is_checked(self):
        return self.__checked == True
    
    def set_checked(self, new_state: bool):
        self.__checked = new_state
       
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
        new_obj = FBSData(deepcopy(self.__data), self.__path, id=self.__id, checked=self.__checked, node_metadata=self.node_metadata)
        return new_obj
    
    def __repr__(self):
        return f"fbs_data at {id(self)}, inner at {id(self.__data)}"
    
        
    


