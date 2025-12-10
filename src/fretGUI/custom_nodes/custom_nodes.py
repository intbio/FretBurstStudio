import custom_widgets.path_selector as path_selector
from custom_nodes.abstract_nodes import AbstractRecomputable
import fretbursts
from node_builder import NodeBuilder
from NodeGraphQt import BaseNode, NodeBaseWidget
from .resizable_node_item import ResizablePlotNodeItem
import uuid
from fbs_data import FBSData
from collections import Counter
from singletons import FBSDataCash

             
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
    
    
class BurstSearchNodde(AbstractRecomputable):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'BurstSearchNodde'
    
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
    
    
class BGPlotterNode(ResizableContentNode):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'BGPlotterNode'

    # if you want different margins just for this node:
    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20

    def __init__(self):
        # tell the base which widget name to resize
        super().__init__(widget_name='plot_widget')

        node_builder = NodeBuilder(self)

        self.add_input('inport')
        node_builder.build_plot_widget('plot_widget')

    def __update_plot(self, fretData):
        plot_widget = self.get_widget('plot_widget').plot_widget
        ax1 = plot_widget.figure.add_subplot(211)
        ax2 = plot_widget.figure.add_subplot(212)
        ax1.cla()
        ax2.cla()
        fretbursts.dplot(fretData, fretbursts.hist_bg, show_fit=True, ax=ax1)
        fretbursts.dplot(fretData, fretbursts.timetrace_bg, ax=ax2)
        plot_widget.canvas.draw()

    def execute(self, fbsdata: FBSData):
        self.__update_plot(fbsdata.data)
        return [fbsdata]
    
class EHistPlotterNode(ResizableContentNode):
    __identifier__ = 'nodes.custom'
    NODE_NAME = 'EHistPlotterNode'

    # if you want different margins just for this node:
    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20

    def __init__(self):
        # tell the base which widget name to resize
        super().__init__(widget_name='plot_widget')

        node_builder = NodeBuilder(self)

        self.add_input('inport')
        node_builder.build_plot_widget('plot_widget')

    def __update_plot(self, fretData):
        plot_widget = self.get_widget('plot_widget').plot_widget
        ax1 = plot_widget.figure.add_subplot()
        ax1.cla()
        fretbursts.dplot(fretData, fretbursts.hist_fret, ax=ax1)
        plot_widget.canvas.draw()

    def execute(self, fbsdata: FBSData):
        self.__update_plot(fbsdata.data)
        return [fbsdata]
    
        
        
        
        
    
    
    
    
        
            
            
