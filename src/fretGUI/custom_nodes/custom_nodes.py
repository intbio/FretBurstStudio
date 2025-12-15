import custom_widgets.path_selector as path_selector
from custom_nodes.abstract_nodes import AbstractRecomputable
import fretbursts
from node_builder import NodeBuilder


from fbs_data import FBSData
from singletons import FBSDataCash
from Qt.QtCore import Signal
from singletons import ThreadSignalManager
from abc import abstractmethod
from NodeGraphQt import BaseNode
import numpy as np
from fretbursts.burstlib import Data
from collections import Counter


class AbstractLoader(AbstractRecomputable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.add_output('out_file')

        self.file_widget = path_selector.PathSelectorWidgetWrapper(self.view)  
        self.add_custom_widget(self.file_widget, tab='Custom')  
        
        self.opened_paths = dict()
        
    @abstractmethod
    def load(self, path: str) -> FBSData:
        pass
    
    def execute(self, fbsdata: FBSData=None):
        selected_paths = self.file_widget.get_value()
        self.__delete_closed_files(selected_paths)
        
        data_list = []
        for cur_path in selected_paths:
            path_hash = hash(cur_path)
            if path_hash in self.opened_paths:
                data_list.append(self.opened_paths[path_hash].copy())
            else:
                loaded_fbsdata = self.load(cur_path)
                self.opened_paths[path_hash] = loaded_fbsdata.copy()
                data_list.append(loaded_fbsdata)
        return data_list
    
    def __delete_closed_files(self, selected_paths: list):
        selected_hashes = set([hash(path) for path in selected_paths])
        saved = set(self.opened_paths.keys())
        for_kill = saved - selected_hashes
        if len(for_kill) > 0:
            for item in for_kill:
                self.opened_paths.pop(item)
        
        
    

             
class PhHDF5Node(AbstractLoader):

    __identifier__ = 'Loaders'
    NODE_NAME  = 'PhHDF5Node'

    def __init__(self):
        super().__init__() 
    
    def laod(self, path):
        data = fretbursts.loader.photon_hdf5(path)
        fbsdata = FBSData(data, path)
        return fbsdata   
        
        
class LSM510Node(AbstractLoader):
    from misc.fcsfiles import ConfoCor2Raw
    __identifier__ = 'Loaders'
    NODE_NAME  = 'LSM510Node'

    def __init__(self):
        super().__init__() 
    
    def load(self, path: str):
        fcs=self.ConfoCor2Raw(path)
        times_acceptor, times_donor = fcs.asarray()
        fcs.frequency

        df = np.hstack([np.vstack( [   times_donor, np.zeros(   times_donor.size)] ),
                        np.vstack( [times_acceptor,  np.ones(times_acceptor.size)] )]).T

        df_sorted = df[np.argsort(df[:,0])].T
        timestamps=df_sorted[0].astype('int64')
        timestamps_unit = 1.0/fcs.frequency

        detectors=df_sorted[1].astype('bool')
        
        data = fretbursts.Data(ph_times_m=[timestamps], A_em=[detectors],
                                     clk_p=timestamps_unit, alternated=False,nch=1,
                                     fname='file_name',meas_type='smFRET')  
        fbsdata = FBSData(data, path)
        return fbsdata   
        
    
class AlexNode(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'AlexNode'
    
    def __init__(self):
        super().__init__()
        self.add_input('inport')
        self.add_output('outport')        
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData) -> list[FBSData]:
        fretbursts.loader.alex_apply_period(fbsdata.data, False)
        return [fbsdata]
    
    
class CalcBGNode(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'CalcBGNode'
    
    def __init__(self):
        super().__init__()
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.time_s_slider = node_builder.build_int_slider('time_s', [1000, 2000, 100])
        self.tail_slider = node_builder.build_int_slider('tail_min_us', [0, 1000, 100], 300)
        
    def __calc_bg(self, data, time_s, tail_min_us):
        data.data.calc_bg(fretbursts.bg.exp_fit, time_s=time_s, tail_min_us=tail_min_us)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData) -> list[FBSData]:
        self.__calc_bg(fbsdata, self.time_s_slider.get_value(), self.tail_slider.get_value())
        return [fbsdata]
    
    
class BurstSearchNodeRate(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'BurstSearchRate'
    
    def __init__(self):
        super().__init__()
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.int_slider = node_builder.build_int_slider('min_rate_cps', [5000, 20000, 1000], 8000)
        
    def __burst_search(self, fbdata: str, min_rate_cps):
        fbdata.data.burst_search(min_rate_cps)
       
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.__burst_search(fbsdata, self.int_slider.get_value())
        return [fbsdata]
        
class BurstSearchNodeFromBG(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'BurstSearchFromBG'
    
    def __init__(self):
        super().__init__()
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.m_slider = node_builder.build_int_slider('m, Photon search window', [3, 100, 1], 10)
        self.L_slider = node_builder.build_int_slider('L, Minimal Burst size', [3, 100, 1], 20)
        self.F_slider = node_builder.build_int_slider('F, Min. Burst rate to bg. ratio', [1, 20, 1], 6)
        
    def __burst_search(self, fbdata: str, m: int,L: int,F: int):
        fbdata.data.burst_search(m=m,L=L,F=F)
       
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.__burst_search(fbsdata,m=self.m_slider.get_value(),
                                    L=self.L_slider.get_value(),
                                    F=self.F_slider.get_value())
        return [fbsdata]    
          
        
