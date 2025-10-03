import path_selector
from NodeGraphQt import BaseNode
from abc import  abstractmethod, ABC

import fretbursts
from node_builder import NodeBuilder
from qtpy.QtCore import Signal


class AbstractExecutable:
    def __init__(self):
        self.__data = None
        self.__iter = None
        
    @property
    def data(self):
        return self.__data
    
    @data.setter
    def data(self, new_data):
        self.__data = new_data
        
    @abstractmethod
    def execute(self, *args, **kwargs):
        pass
    
    def next_data(self, *args, **kwargs):
        if self.__iter is None:
            self.__iter = iter(self.execute(*args, **kwargs))
        self.__data = next(self.__iter)
        return self.__data
        
    def get_data(self, *args, **kwargs):
        if self.__data is None:
            self.next_data(*args, **kwargs)
        return self.__data
        
    def reset_data(self):
        self.__data = None
        self.__iter = None
        
        
class AbstractNodeChainExecutable(BaseNode, ABC):
    def __init__(self):
        BaseNode.__init__(self)
        self.__data = None

    @property
    def data(self):
        return self.__data
    
    @data.setter
    def data(self, new_data: dict):
        self.__data = new_data
        
    @abstractmethod
    def execute(self, *args, **kwargs) -> dict:
        pass
        
    def is_root(self) -> bool:
        return len(self.input_ports()) == 0
        
    def get_data(self) -> dict:
        if self.data is None:
            if self.is_root():
                self.data = self.execute()
            combined_data = {}
            for parent in self.iter_parent_nodes():
                parent_data = parent.get_data()
                combined_data.update(parent_data)
            self.data = self.execute(**combined_data)
        return self.data
           
    def iter_parent_nodes(self):
        for port in self.input_ports():
            connected_ports = port.connected_ports()
            for connected_port in connected_ports:
                connected_node = connected_port.node()
                yield connected_node
                
    def iter_children_nodes(self):
        for port in self.output_ports():
            connected_ports = port.connected_ports()
            for connected_port in connected_ports:
                connected_node = connected_port.node()
                yield connected_node
        
    def update_nodes(self):
        if self.is_root():
            print(f"{self} root executed")
            self.data = self.execute()
        else:
            combined_data = {}
            for parent in self.iter_parent_nodes():
                parent_data = parent.get_data()
                combined_data.update(parent_data)
            self.data = self.execute(**combined_data)
            print(f"{self} executed")
        for next_node in self.iter_children_nodes():
            next_node.update_nodes()



    
    
class FileNode(AbstractNodeChainExecutable):

    __identifier__ = 'nodes.custom'
    NODE_NAME  = 'FileSelector'

    def __init__(self):
        AbstractNodeChainExecutable.__init__(self) 
        
        self.add_output('out_file')

        self.file_widget = path_selector.PathSelectorWidgetWrapper(self.view)       
        self.add_custom_widget(self.file_widget, tab='Custom')  
        self.wire_signals()

    def wire_signals(self):
        self.file_widget.path_widget.open_button.clicked.connect(self.update_nodes)
        # self.file_widget.path_widget.update_node_signal.connect(self.update_nodes)

    def execute(self) -> dict:
        res = {"filename": self.file_widget.get_value()}
        return res


class PhotonNode(AbstractNodeChainExecutable):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'PhotonNode'
    
    def __init__(self):
        AbstractNodeChainExecutable.__init__(self) 
        self.add_input('inport')
        self.add_output('outport')
        
    def __open_hdf5(self, hdf5_path: str):
        return fretbursts.loader.photon_hdf5(hdf5_path)
    
    def execute(self, filename: str) -> dict:
        return {'fbdata': self.__open_hdf5(filename)}
        
    
class AlexNode(AbstractNodeChainExecutable):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'AlexNode'
    
    def __init__(self):
        AbstractNodeChainExecutable.__init__(self)
        self.add_input('inport')
        self.add_output('outport')
        
    def __alex_apply_period(self, fbdata: str):
        return fretbursts.loader.alex_apply_period(fbdata)

    def execute(self, fbdata: str):
        self.__alex_apply_period(fbdata)
        return {'fbdata': fbdata}
    
    
class CalcBGNode(AbstractNodeChainExecutable):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'CalcBGNode'
    
    def __init__(self):
        AbstractNodeChainExecutable.__init__(self)
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.time_s_slider = node_builder.build_int_slider('time_s', [1000, 2000, 100])
        self.tail_slider = node_builder.build_int_slider('tail_min_us', [0, 1000, 100], 300)
        self.wire_signals()
        
    def wire_signals(self):
        self.time_s_slider.slider_widget.slider.sliderReleased.connect(self.update_nodes)
        self.tail_slider.slider_widget.slider.sliderReleased.connect(self.update_nodes)
        
    def __calc_bg(self, d, time_s, tail_min_us):
        return d.calc_bg(fretbursts.bg.exp_fit, time_s=time_s, tail_min_us=tail_min_us)
        
    def execute(self, fbdata: str):
        self.__calc_bg(fbdata, self.time_s_slider.get_value(), self.tail_slider.get_value())
        return {'fbdata': fbdata}
    
    
class BurstSearchNodde(AbstractNodeChainExecutable):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'BurstSearchNodde'
    
    def __init__(self):
        AbstractNodeChainExecutable.__init__(self)
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.int_slider = node_builder.build_int_slider('min_rate_cps', [5000, 20000, 1000], 8000)
        self.wire_signals()
        
    def wire_signals(self):
        self.int_slider.slider_widget.slider.sliderReleased.connect(self.update_nodes)
        
    def __burst_search(self, fbdata: str, min_rate_cps):
        return fbdata.burst_search(min_rate_cps)
        
    def execute(self, fbdata: str):
        self.__burst_search(fbdata, self.int_slider.get_value())
        return {'fbdata': fbdata}
    
    
class BurstSelectorNode(AbstractNodeChainExecutable):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'BurstSelector'
    
    def __init__(self):
        AbstractNodeChainExecutable.__init__(self) 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.int_slider = node_builder.build_int_slider('th1', [0, 100, 10], 40)
        self.wire_signals()
        
    def wire_signals(self):
        self.int_slider.slider_widget.slider.sliderReleased.connect(self.update_nodes)
        
    def __select_bursts(self, fbdata: str, add_naa=True, th1=40):
        return fbdata.select_bursts(fretbursts.select_bursts.size, add_naa=add_naa, th1=th1)
    
    def execute(self, fbdata: str):
        ds = self.__select_bursts(fbdata, True, self.get_widget('th1').get_value())
        return {"fbdata": ds}
    
    
class BGPlotterNode(AbstractNodeChainExecutable):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'BGPlotterNode'
    
    def __init__(self):
        AbstractNodeChainExecutable.__init__(self)
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        node_builder.build_plot_widget('plot_widget')
        # node_builder.build_int_slider('time_s', [1000, 5000, 1000], 1000)
        
    def __update_plot(self, fretData):
        plot_widget = self.get_widget('plot_widget').plot_widget
        ax1 = plot_widget.figure.add_subplot(211)
        ax2 = plot_widget.figure.add_subplot(212)
        ax1.cla() 
        ax2.cla()
        fretbursts.dplot(fretData, fretbursts.hist_bg, show_fit=True, ax=ax1)   
        fretbursts.dplot(fretData, fretbursts.timetrace_bg, ax=ax2)
        plot_widget.canvas.draw()
        
        
    def execute(self, fbdata: str):
        self.__update_plot(fbdata)
        print(f"{self} execute called with {fbdata}")
        return {'fbdata': fbdata}
    
    
        
        
        
        
        
    
    
    
    
        
            
            
