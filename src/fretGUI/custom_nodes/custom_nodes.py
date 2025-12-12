import custom_widgets.path_selector as path_selector
from custom_nodes.abstract_nodes import AbstractRecomputable
import fretbursts
from node_builder import NodeBuilder
from .resizable_node_item import ResizablePlotNodeItem

from fbs_data import FBSData
from singletons import FBSDataCash
from Qt.QtCore import Signal
from singletons import ThreadSignalManager
from abc import abstractmethod
from NodeGraphQt import BaseNode
import numpy as np

             
class PhHDF5Node(AbstractRecomputable):

    __identifier__ = 'nodes.custom'
    NODE_NAME  = 'PhHDF5Node'

    def __init__(self):
        super().__init__() 
        self.node_iterator = None
        
        self.add_output('out_file')

        self.file_widget = path_selector.PathSelectorWidgetWrapper(self.view)  
        self.add_custom_widget(self.file_widget, tab='Custom')  
        
    def execute(self, data=None) -> list[FBSData]:
        selected_paths = self.file_widget.get_value()
        data_list = [self.__load_photon_hdf5(
            FBSData(path=cur_path))
                     for cur_path in selected_paths]
        return data_list
    
    def __load_photon_hdf5(self, fbsdata: FBSData):
        data = fretbursts.loader.photon_hdf5(fbsdata.path)
        fbsdata.data = data
        return fbsdata   
        
class LSM510Node(AbstractRecomputable):
    from misc.fcsfiles import ConfoCor2Raw
    __identifier__ = 'nodes.custom'
    NODE_NAME  = 'LSM510Node'

    def __init__(self):
        super().__init__() 
        self.node_iterator = None
        
        self.add_output('out_file')

        self.file_widget = path_selector.PathSelectorWidgetWrapper(self.view)  
        self.add_custom_widget(self.file_widget, tab='Custom')  
        
    def execute(self, data=None) -> list[FBSData]:
        selected_paths = self.file_widget.get_value()
        data_list = [self.__load_confocor2(
            FBSData(path=cur_path))
                     for cur_path in selected_paths]
        return data_list
    
    def __load_confocor2(self, fbsdata: FBSData):
        fcs=self.ConfoCor2Raw(fbsdata.path)
        times_acceptor, times_donor = fcs.asarray()
        fcs.frequency

        df = np.hstack([np.vstack( [   times_donor, np.zeros(   times_donor.size)] ),
                        np.vstack( [times_acceptor,  np.ones(times_acceptor.size)] )]).T

        df_sorted = df[np.argsort(df[:,0])].T
        timestamps=df_sorted[0].astype('int64')
        timestamps_unit = 1.0/fcs.frequency

        detectors=df_sorted[1].astype('bool')
        
        fbsdata.data = fretbursts.Data(ph_times_m=[timestamps], A_em=[detectors],
                                     clk_p=timestamps_unit, alternated=False,nch=1,
                                     fname='file_name',meas_type='smFRET')  
        return fbsdata   
        
    
class AlexNode(AbstractRecomputable):
    __identifier__ = 'nodes.custom'
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
    __identifier__ = 'nodes.custom'
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
    __identifier__ = 'nodes.custom'
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
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'BurstSearchFromBG'
    
    def __init__(self):
        super().__init__()
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.m_slider = node_builder.build_int_slider('m', [3, 100, 1], 10)
        self.L_slider = node_builder.build_int_slider('L', [3, 100, 1], 10)
        self.F_slider = node_builder.build_int_slider('F', [1, 20, 1], 6)
        
    def __burst_search(self, fbdata: str, m: int,L: int,F: int):
        fbdata.data.burst_search(m=m,L=L,F=F)
       
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.__burst_search(fbsdata,m=self.m_slider.get_value(),
                                    L=self.L_slider.get_value(),
                                    F=self.F_slider.get_value())
        return [fbsdata]
    
    
class BurstSelectorNode(AbstractRecomputable):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'BurstSelector'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.int_slider = node_builder.build_int_slider('th1', [0, 100, 10], 40)
        
    def __select_bursts(self, fbdata: str, add_naa=True, th1=40):
        fbdata.data.select_bursts(fretbursts.select_bursts.size, add_naa=add_naa, th1=th1)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.__select_bursts(fbsdata, True, self.get_widget('th1').get_value())
        return [fbsdata]
        
        
class ResizableContentNode(AbstractRecomputable):
    """
    Base class for nodes that have a single main widget
    that should follow the node's size.
    """
    # default margins, override in subclasses if you want
    LEFT_RIGHT_MARGIN = 100
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20

    def __init__(self, widget_name, qgraphics_item=None):
        # if you always use ResizablePlotNodeItem, you can default it here
        super().__init__(qgraphics_item=qgraphics_item or ResizablePlotNodeItem)

        self._content_widget_name = widget_name

        # hook up resize callback
        view = self.view            # this is your ResizablePlotNodeItem
        view.add_resize_callback(self._on_view_resized)

        # initial sync
        self._on_view_resized(view._width, view._height)

    def _on_view_resized(self, w, h):
        wrapper = self.get_widget(self._content_widget_name)
        if wrapper is None:
            return

        inner_w = max(
            1,
            w - 2 * self.LEFT_RIGHT_MARGIN
        )
        inner_h = max(
            1,
            h - self.TOP_MARGIN - self.BOTTOM_MARGIN
        )

        wrapper.setMinimumSize(inner_w, inner_h)
        wrapper.setMaximumSize(inner_w, inner_h)
        
        
        
class AbstractContentNode(ResizableContentNode):
    def __init__(self, widget_name, qgraphics_item=None):
        super().__init__(widget_name, qgraphics_item)
        self.data_to_plot = dict
        ThreadSignalManager().all_thread_finished.connect(self.on_refresh_canvas)
        ThreadSignalManager().run_btn_clicked.connect(self.on_plot_data_clear)
        
    @abstractmethod
    def on_refresh_canvas(self):
        pass
    
    def on_plot_data_clear(self):
        print("CLEAR")
        self.data_to_plot = []
    
    # @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.data_to_plot.append(fbsdata)
        return [fbsdata]
    
    # def execute(self, fbsdata: FBSData):
        
    
    
class BGPlotterNode(AbstractContentNode):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'BGPlotterNode'
   

    # if you want different margins just for this node:
    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20

    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)

        node_builder = NodeBuilder(self)

        self.add_input('inport')
        node_builder.build_plot_widget('plot_widget')                       
        
    def on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        fig = plot_widget.figure
        fig.clear()
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        for cur_data in self.data_to_plot:
            fretbursts.dplot(cur_data.data, fretbursts.hist_bg, show_fit=True, ax=ax1)
            fretbursts.dplot(cur_data.data, fretbursts.timetrace_bg, ax=ax2)
        plot_widget.canvas.draw()
        
    
class EHistPlotterNode(AbstractContentNode):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'EHistPlotterNode'

    # if you want different margins just for this node:
    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20

    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)

        node_builder = NodeBuilder(self)

        self.add_input('inport')
        node_builder.build_plot_widget('plot_widget')

    def on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        plot_widget.figure.clf()
        ax1 = plot_widget.figure.add_subplot()
        ax1.cla()
        for cur_data in self.data_to_plot:
            fretbursts.dplot(cur_data.data, fretbursts.hist_fret, ax=ax1)
        plot_widget.canvas.draw()

    
        
        
        
        
    
    
    
    
        
            
            
