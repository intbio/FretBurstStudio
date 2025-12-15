from custom_nodes.abstract_nodes import AbstractContentNode
import fretbursts
from node_builder import NodeBuilder

from fbs_data import FBSData
from singletons import ThreadSignalManager
from abc import abstractmethod



         
    
    
class BGPlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'BGPlotterNode'
   

    # if you want different margins just for this node:
    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20
    PLOT_NODE = True
    MIN_WIDTH = 450  # Minimum allowed width for the node
    MIN_HEIGHT = 300  # Minimum allowed height for the node

    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)

        node_builder = NodeBuilder(self)
        
        self.add_input('inport')

        node_builder.build_plot_widget('plot_widget')      
                         
        
    def _on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        fig = plot_widget.figure
        fig.clear()
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        for cur_data in self.data_to_plot:
            fretbursts.dplot(cur_data.data, fretbursts.hist_bg, show_fit=True, ax=ax1)
            fretbursts.dplot(cur_data.data, fretbursts.timetrace_bg, ax=ax2)
        plot_widget.canvas.draw()
        self.on_plot_data_clear()
        
    
class EHistPlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'EHistPlotterNode'

    # if you want different margins just for this node:
    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20
    PLOT_NODE = True
    MIN_WIDTH = 450  # Minimum allowed width for the node
    MIN_HEIGHT = 300  # Minimum allowed height for the node


    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)

        node_builder = NodeBuilder(self)

        self.add_input('inport')
        self.BinWidth_slider = node_builder.build_float_slider('Bin Width', [0.01, 0.2, 0.01], 0.03)
        node_builder.build_plot_widget('plot_widget')

    def _on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        plot_widget.figure.clf()
        ax1 = plot_widget.figure.add_subplot()
        ax1.cla()
        for cur_data in self.data_to_plot:
            fretbursts.dplot(cur_data.data, fretbursts.hist_fret, ax=ax1, binwidth=self.BinWidth_slider.get_value(),
            hist_style = 'bar' if len(self.data_to_plot)==1 else 'line')
        plot_widget.canvas.draw()
        print("plot", self)
        self.on_plot_data_clear()
