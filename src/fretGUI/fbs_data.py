from fretbursts.burstlib import Data



class FBSData():
    def __init__(self, data=None, path=None):
        self.__data = data
        self.__path = path
       
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
        
    


