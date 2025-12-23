from typing import Any
import custom_widgets.path_selector as path_selector
from custom_nodes.abstract_nodes import AbstractRecomputable, ResizableContentNode
import fretbursts, os
from node_builder import NodeBuilder


from fbs_data import FBSData
from singletons import FBSDataCash
from Qt.QtCore import Signal  # pyright: ignore[reportMissingModuleSource]
from singletons import ThreadSignalManager
from abc import abstractmethod
from NodeGraphQt import BaseNode
import numpy as np
from fretbursts.burstlib import Data
from collections import Counter
from misc import enable_legend_toggle


class AbstractLoader(AbstractRecomputable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.add_output('out_file')

        self.file_widget = path_selector.PathSelectorWidgetWrapper(self.view)  
        self.add_custom_widget(self.file_widget, tab='Custom')  
        
        self.opened_paths = dict()  # path_hash -> FBSData
        self.path_to_id = dict()    # path -> id mapping
        
        # Connect to paths_added signal to assign IDs immediately (use DirectConnection for synchronous execution)
        from Qt.QtCore import Qt
        self.file_widget.paths_added.connect(self.on_paths_added, Qt.DirectConnection)
        
    def on_paths_added(self, paths):
        """Assign IDs immediately when paths are added"""
        from singletons import FBSDataIDGenerator
        for path in paths:
            if path not in self.path_to_id:
                # Assign new ID immediately
                new_id = FBSDataIDGenerator().get_next_id()
                self.path_to_id[path] = new_id
        # Update the widget wrapper with assigned IDs (so it can pass to add_row_widgets)
        self.file_widget.update_path_ids(self.path_to_id)
        
    @abstractmethod
    def load(self, path: str, id: int = None) -> FBSData:
        pass
    
    def _format_metadata_tooltip(self, fbsdata: FBSData) -> str:
        """Format metadata from FBSData into a tooltip string"""
        if fbsdata is None or fbsdata.data is None:
            return "Not loaded, press RUN"
        
        data = fbsdata.data
        path = fbsdata.path
        
        # Start with "loaded" and path
        tooltip_parts = [f"Loaded: {path}"]
        
        try:
            # Get experiment type
            if hasattr(data, 'meas_type') and data.meas_type:
                tooltip_parts.append(f"Type: {data.meas_type}")
            
            # Get number of channels
            if hasattr(data, 'nch'):
                tooltip_parts.append(f"Channels: {data.nch}")
            
            # Calculate experiment length and total photons per channel
            if hasattr(data, 'ph_times_m') and data.ph_times_m:
                # ph_times_m is a list of arrays, one per channel
                if hasattr(data, 'clk_p') and data.clk_p:
                    clk_period = data.clk_p
                else:
                    clk_period = 1.0  # Default if not available
                
                total_photons = []
                experiment_lengths = []
                
                for ch_idx, ph_times in enumerate(data.ph_times_m):
                    if ph_times is not None and len(ph_times) > 0:
                        num_photons = len(ph_times)
                        total_photons.append(num_photons)
                        # Calculate experiment length in seconds
                        max_time = ph_times[-1] if len(ph_times) > 0 else 0
                        exp_length = max_time * clk_period
                        experiment_lengths.append(exp_length)
                    else:
                        total_photons.append(0)
                        experiment_lengths.append(0.0)
                
                # Add experiment length (use max if multiple channels)
                if experiment_lengths:
                    max_length = max(experiment_lengths)
                    tooltip_parts.append(f"Length: {max_length:.2f} s")
                
                # Add total photons per channel
                if total_photons:
                    photons_str = ", ".join([f"Ch{i}: {count}" for i, count in enumerate(total_photons) if count > 0])
                    if photons_str:
                        tooltip_parts.append(f"Photons: {photons_str}")
            
        except Exception as e:
            # If there's an error extracting metadata, just show basic info
            tooltip_parts.append(f"(Metadata extraction error: {str(e)})")
        
        return "\n".join(tooltip_parts)
    
    def execute(self, fbsdata: FBSData=None):
        selected_paths = self.file_widget.get_value()
        self.__delete_closed_files(selected_paths)
        
        # Ensure all selected paths have IDs assigned
        from singletons import FBSDataIDGenerator
        for path in selected_paths:
            if path not in self.path_to_id:
                # Assign ID if somehow missing (shouldn't happen, but safety check)
                new_id = FBSDataIDGenerator().get_next_id()
                self.path_to_id[path] = new_id
        
        data_list = []
        for cur_path in selected_paths:
            path_hash = hash(cur_path)
            # Get the pre-assigned ID for this path
            assigned_id = self.path_to_id[cur_path]
            
            if path_hash in self.opened_paths:
                # Use existing FBSData (which already has an ID)
                existing_fbsdata = self.opened_paths[path_hash]
                data_list.append(existing_fbsdata.copy())
                # Update tooltip for loaded file
                tooltip_text = self._format_metadata_tooltip(existing_fbsdata)
                self.file_widget.update_tooltip_for_path(cur_path, tooltip_text)
            else:
                # Load new FBSData with the pre-assigned ID
                loaded_fbsdata = self.load(cur_path, id=assigned_id)
                self.opened_paths[path_hash] = loaded_fbsdata.copy()
                data_list.append(loaded_fbsdata)
                # Update tooltip for newly loaded file
                tooltip_text = self._format_metadata_tooltip(loaded_fbsdata)
                self.file_widget.update_tooltip_for_path(cur_path, tooltip_text)
        
        # Update the path widget with IDs (in case any were missing)
        self.file_widget.update_path_ids(self.path_to_id)
        return data_list
    
    def __delete_closed_files(self, selected_paths: list):
        selected_hashes = set([hash(path) for path in selected_paths])
        saved = set(self.opened_paths.keys())
        for_kill = saved - selected_hashes
        if len(for_kill) > 0:
            for item in for_kill:
                self.opened_paths.pop(item)
        
        # Also clean up path_to_id mapping
        selected_paths_set = set(selected_paths)
        paths_to_remove = [path for path in self.path_to_id.keys() if path not in selected_paths_set]
        for path in paths_to_remove:
            self.path_to_id.pop(path, None)
        
        
    

             
class PhHDF5Node(AbstractLoader):

    __identifier__ = 'Loaders'
    NODE_NAME  = 'PhHDF5Node'

    def __init__(self):
        super().__init__() 
    
    def load(self, path, id=None):
        data = fretbursts.loader.photon_hdf5(path)
        fbsdata = FBSData(data, path, id=id)
        return fbsdata   
        
        
class LSM510Node(AbstractLoader):
    from misc.fcsfiles import ConfoCor2Raw
    __identifier__ = 'Loaders'
    NODE_NAME  = 'LSM510Node'

    def __init__(self):
        super().__init__() 
    
    def load(self, path: str, id=None):
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
                                     fname=path,meas_type='smFRET')  
        fbsdata = FBSData(data, path, id=id)
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
        self.time_s_spinbox = node_builder.build_int_spinbox('Period, s', [1, 1000, 10],60, tooltip='Time for BG calculation, s', min_width=80)
        self.tail_spinbox = node_builder.build_int_spinbox('Min. lag, μs', [1, 1000, 100], 300,tooltip='Threshold in μs for photon waiting times', min_width=80)

        
    def __calc_bg(self, data, time_s, tail_min_us):
        data.data.calc_bg(fretbursts.bg.exp_fit, time_s=time_s, tail_min_us=tail_min_us)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData) -> list[FBSData]:
        self.__calc_bg(fbsdata, time_s = self.time_s_spinbox.get_value(),
                       tail_min_us = self.tail_spinbox.get_value())
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
          
        
class AbstractContentNode(ResizableContentNode):
    def __init__(self, widget_name, qgraphics_item=None):
        super().__init__(widget_name, qgraphics_item)
        self.data_to_plot = []
        ThreadSignalManager().all_thread_finished.connect(self.on_refresh_canvas)
        ThreadSignalManager().run_btn_clicked.connect(self.on_plot_data_clear)
        self.was_executed = False
        
    def on_refresh_canvas(self):
        if self.was_executed:
            self._on_refresh_canvas()
        
    @abstractmethod
    def _on_refresh_canvas(self):
        pass
    
    def on_plot_data_clear(self):
        self.data_to_plot.clear()
        self.was_executed = False
    
    def execute(self, fbsdata: FBSData=None):
        self.was_executed = True
        if fbsdata is not None:
            self.data_to_plot.append(fbsdata)
        return [fbsdata]        
    
    
class BGFitPlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'BGFitPlotterNode'
   

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

        node_builder.build_plot_widget('plot_widget', mpl_width=4.0, mpl_height=3.0)
        self.items_to_plot = node_builder.build_combobox(
            widget_name="File to plot:",
            items=[],
            value=None,
            tooltip="Select an option"
            )  
                
                         
        
    def _on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        fig = plot_widget.figure
        fig.clear()
        ax = fig.add_subplot()

        map_name_to_data = {}
        for cur_data in self.data_to_plot:
            fname = os.path.basename(cur_data.data.fname)
            fbid = cur_data.id
            map_name_to_data[f'{fbid}, {fname}'] = cur_data.data
        self.items_to_plot.set_items(list(map_name_to_data.keys()))
        selected_val = self.items_to_plot.get_value()
        if selected_val != None:
            fretbursts.dplot(map_name_to_data[selected_val], fretbursts.hist_bg, show_fit=True, ax=ax)
        else:
            for cur_data in self.data_to_plot:
                fretbursts.dplot(cur_data.data, fretbursts.hist_bg, show_fit=True, ax=ax)

        plot_widget.canvas.draw()
        self.on_plot_data_clear()

class BGTimeLinePlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'BGTimeLinePlotterNode'
   

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
        node_builder.build_plot_widget('plot_widget', mpl_width=3.0, mpl_height=3.0)   
        self.items_to_plot = node_builder.build_combobox(
            widget_name="File to plot:",
            items=[],
            value=None,
            tooltip="Select an option"
            )
          
         
                         
        
    def _on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        fig = plot_widget.figure
        fig.clear()
        ax = fig.add_subplot()
        
        map_name_to_data = {}
        for cur_data in self.data_to_plot:
            fname = os.path.basename(cur_data.data.fname)
            fbid = cur_data.id
            map_name_to_data[f'{fbid}, {fname}'] = cur_data.data
        self.items_to_plot.set_items(list(map_name_to_data.keys()))
        selected_val = self.items_to_plot.get_value()
        if selected_val != None:
            fretbursts.dplot(map_name_to_data[selected_val], fretbursts.timetrace_bg, ax=ax)
        else:
            for cur_data in self.data_to_plot:
                fretbursts.dplot(cur_data.data, fretbursts.timetrace_bg, ax=ax)
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
        node_builder.build_plot_widget('plot_widget', mpl_width=4.0, mpl_height=3.0)   

    def _on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        plot_widget.figure.clf()
        ax1 = plot_widget.figure.add_subplot()
        ax1.cla()
        for cur_data in self.data_to_plot:
            fretbursts.dplot(cur_data.data, fretbursts.hist_fret, ax=ax1, binwidth=self.BinWidth_slider.get_value(),
            hist_style = 'bar' if len(self.data_to_plot)==1 else 'line')
        # ax.legend(fancybox=True, shadow=True)
        # enable_legend_toggle(ax1)
        plot_widget.canvas.draw()
        print("plot", self)
        self.on_plot_data_clear()

class TestPlotterNode(AbstractContentNode):
    import matplotlib.pyplot as plt
    __identifier__ = 'Plot'
    NODE_NAME = 'Test'

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
        plot_widget.figure.clf()
        fig = plot_widget.figure
        ax = plot_widget.figure.add_subplot()
        t = np.linspace(0, 1)
        y1 = 2 * np.sin(2 * np.pi * t)
        y2 = 4 * np.sin(2 * np.pi * 2 * t)

        line1, = ax.plot(t, y1, lw=2, label='1 Hz')
        line2, = ax.plot(t, y2, lw=2, label='2 Hz')
        leg = ax.legend(fancybox=True, shadow=True)

        # Enable click-to-toggle functionality
        enable_legend_toggle(ax)
        
        plot_widget.canvas.draw()



    
        
        
        
        
    
    
    
    
        
            
            
