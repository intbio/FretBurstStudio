from typing import Any
import custom_widgets.path_selector as path_selector
from custom_nodes.abstract_nodes import AbstractRecomputable, ResizableContentNode
import fretbursts, os
from node_builder import NodeBuilder


from fbs_data import FBSData
from singletons import FBSDataCash
from Qt.QtCore import Signal  # pyright: ignore[reportMissingModuleSource]
from Qt.QtWidgets import QAction, QFileDialog  # pyright: ignore[reportMissingModuleSource]
from singletons import ThreadSignalManager
from abc import abstractmethod
from NodeGraphQt import BaseNode
import numpy as np
from fretbursts.burstlib import Data
from collections import Counter
from misc import enable_legend_toggle
import pandas as pd


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
            
            rowwidget = self.file_widget.get_rowwidget(assigned_id)
            if not rowwidget.is_checked():
                continue
            
            if path_hash in self.opened_paths:
                # Use existing FBSData (which already has an ID)
                existing_fbsdata = self.opened_paths[path_hash]
                fbsdata_copy = existing_fbsdata.copy()
                self.__wire_fbsdata(fbsdata_copy)
                # self.__wire_fbsdata(existing_fbsdata)
                data_list.append(fbsdata_copy)
                # Update tooltip for loaded file
                tooltip_text = self._format_metadata_tooltip(existing_fbsdata)
                self.file_widget.update_tooltip_for_path(cur_path, tooltip_text)
            else:
                # Load new FBSData with the pre-assigned ID
                loaded_fbsdata = self.load(cur_path, id=assigned_id)
                self.__wire_fbsdata(loaded_fbsdata)
                self.opened_paths[path_hash] = loaded_fbsdata.copy()
                # self.__wire_fbsdata(self.opened_paths[path_hash])
                data_list.append(loaded_fbsdata)
                # Update tooltip for newly loaded file
                tooltip_text = self._format_metadata_tooltip(loaded_fbsdata)
                self.file_widget.update_tooltip_for_path(cur_path, tooltip_text)
        
        # Update the path widget with IDs (in case any were missing)
        self.file_widget.update_path_ids(self.path_to_id)
        return data_list
    
    def __wire_fbsdata(self, fbsdata):
        pass
        #  rowwidget = self.file_widget.get_rowwidget(fbsdata.id)
        #  rowwidget.changed_state.connect(fbsdata.on_state_changed)
    
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

class CorrectionsNode(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'Corrections'
    fields_width = 100
    
    def __init__(self):
        super().__init__()

        node_builder = NodeBuilder(self)
        self.add_input('inport')
        self.add_output('outport')   
        self.gamma_spinbox = node_builder.build_float_spinbox(    
            'Gamma', 
            [0.01, 10, 0.01],
            1, 
            tooltip='Gamma correction factor (compensates DexDem and DexAem unbalance)',
            min_width=self.fields_width
            )
        self.leakage_spinbox = node_builder.build_float_spinbox(
            'Leakage', 
            [0, 1, 0.01],
            0,
            tooltip='Spectral leakage (bleed-through) of D emission in the A channel', 
            min_width=self.fields_width)
        self.dir_ex_spinbox = node_builder.build_float_spinbox(
            'Direct ex.', 
            [0, 1, 0.01], 
            0,
            tooltip='The coefficient dir_ex_t expresses the direct excitation as n_dir = dir_ex_t * (na + gamma*nd). In terms of physical parameters it is the ratio of acceptor over donor absorption cross-sections at the donor-excitation wavelength.', 
            min_width=self.fields_width)

    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData) -> list[FBSData]:
        fbsdata.data.gamma = self.gamma_spinbox.get_value()
        fbsdata.data.leakage = self.leakage_spinbox.get_value()
        fbsdata.data.dir_ex = self.dir_ex_spinbox.get_value()
        return [fbsdata]
    
class DitherNode(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'Dither'
    fields_width = 100
    
    def __init__(self):
        super().__init__()

        node_builder = NodeBuilder(self)
        self.add_input('inport')
        self.add_output('outport')   
        self.dither_spinbox = node_builder.build_int_spinbox(    
            'LSB', 
            [1, 100, 1],
            2, 
            tooltip="Add dithering (uniform random noise) to burst counts (nd, na,…). The dithering amplitude is the range -0.5*lsb .. 0.5*lsb. LSB represents the smallest possible change in the signal's value",
            min_width=self.fields_width
            )
        
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData) -> list[FBSData]:
        fbsdata.data.dither(self.dither_spinbox.get_value()) 
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
    
    
class BaseSingleFilePlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'BaseSingleFilePlotterNode'

    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 10
    BOTTOM_MARGIN = 0
    PLOT_NODE = True
    MIN_WIDTH = 450
    MIN_HEIGHT = 300
    PLOT_FUNC = None
    PLOT_KWARGS = {}

    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        super().__init__(widget_name, qgraphics_item)

        self.node_builder = NodeBuilder(self)

        self.add_input('inport')
        self.node_builder.build_plot_widget('plot_widget', mpl_width=3.0, mpl_height=3.0)
        self.items_to_plot = self.node_builder.build_combobox(
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
        selected_data = map_name_to_data.get(selected_val)

        # Avoid accidental binding and ensure we pass a Data instance.
        plot_func = self.PLOT_FUNC.__func__ if isinstance(self.PLOT_FUNC, staticmethod) else self.PLOT_FUNC
        if plot_func is None or selected_data is None or not isinstance(selected_data, Data):
            self.on_plot_data_clear()
            plot_widget.canvas.draw()
            return

        fretbursts.dplot(selected_data, plot_func, ax=ax, **self.PLOT_KWARGS)
        # fig.tight_layout()
        plot_widget.canvas.draw()
        self.on_plot_data_clear()

class BaseMultiFilePlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'BaseMultiFilePlotterNode'

    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 10
    BOTTOM_MARGIN = 0
    PLOT_NODE = True
    MIN_WIDTH = 450
    MIN_HEIGHT = 300
    PLOT_FUNC = None
    PLOT_KWARGS = {}
    LAST_PLOTTED_DATA_LIST = []

    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        super().__init__(widget_name, qgraphics_item)

        self.node_builder = NodeBuilder(self)

        self.add_input('inport')
        self.node_builder.build_plot_widget('plot_widget', mpl_width=4.0, mpl_height=3.0)
    
    def update_plot_kwargs(self):
        pass

    def _on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        plot_widget.figure.clf()
        ax = plot_widget.figure.add_subplot()
        ax.cla()
        self.LAST_PLOTTED_DATA_LIST = []

        # Avoid accidental binding and ensure we have a valid plot function
        plot_func = self.PLOT_FUNC.__func__ if isinstance(self.PLOT_FUNC, staticmethod) else self.PLOT_FUNC
        if plot_func is None:
            self.on_plot_data_clear()
            plot_widget.canvas.draw()
            return
        self.update_plot_kwargs()
        
        self.data_to_plot.sort(key = lambda x: x.id)

        for cur_data in self.data_to_plot:
            print(cur_data.id)
            if not isinstance(cur_data.data, Data):
                continue
            
            # Call fretbursts.dplot for each item in data_to_plot
            fretbursts.dplot(cur_data.data, plot_func, ax=ax, **self.PLOT_KWARGS)
            self.LAST_PLOTTED_DATA_LIST.append(cur_data)

            # Set label for the last plotted line/bar if available
            name = f'{cur_data.data.name}, N {cur_data.data.num_bursts[0]}'
            if ax.lines:
                ax.lines[-1].set_label(name)

        # Add legend if multiple files are plotted
        if len(self.data_to_plot) > 1:
            ax.legend()
            ax.set_title('')
        
        plot_widget.canvas.draw()
        self.on_plot_data_clear()

class BGFitPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'BGFitPlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.hist_bg)
    PLOT_KWARGS = dict(show_fit=True)

class BGTimeLinePlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'BGTimeLinePlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.timetrace_bg)

class ScatterWidthSizePlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'ScatterWidthSizePlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.scatter_width_size)

class ScatterDaPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'ScatterDaPlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.scatter_da)

class ScatterRateDaPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'ScatterRateDaPlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.scatter_rate_da)

class ScatterFretSizePlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'ScatterFretSizePlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.scatter_fret_size)

class ScatterFretNdNaPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'ScatterFretNdNaPlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.scatter_fret_nd_na)

class ScatterFretWidthPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'ScatterFretWidthPlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.scatter_fret_width)
       
    
class EHistPlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'EHistPlotterNode'
    PLOT_FUNC = staticmethod(fretbursts.hist_fret)


    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)
        plot_widget = self.get_widget('plot_widget').plot_widget
        toolbar = plot_widget.toolbar
        
        # Add "save data" button to toolbar
        save_data_action = QAction('save data', toolbar)
        save_data_action.triggered.connect(self.export)
        toolbar.addAction(save_data_action)
        
        # Add 1px border around the action button
        action_button = toolbar.widgetForAction(save_data_action)
        if action_button:
            action_button.setStyleSheet("border: 1px solid gray;")
        
        self.BinWidth_slider = self.node_builder.build_float_slider('Bin Width', [0.01, 0.2, 0.01], 0.03)
    
    def update_plot_kwargs(self):
        self.PLOT_KWARGS['binwidth'] = self.BinWidth_slider.get_value()
        self.PLOT_KWARGS['hist_style'] = 'bar' if len(self.data_to_plot)==1 else 'line'

    def export(self):
        data_dict = {}

        for cur_data in self.LAST_PLOTTED_DATA_LIST:
            name = cur_data.data.name
            data_dict['PR%']=cur_data.data.E_fitter.hist_axis
            data_dict[f'PDF {name}']=cur_data.data.E_fitter.hist_pdf[0]
        df = pd.DataFrame(data_dict)
        if not df.empty:
            # Open file save dialog
            from Qt.QtWidgets import QApplication
            parent_window = QApplication.activeWindow()
            filename, selected_filter = QFileDialog.getSaveFileName(
                parent_window,
                "Save Data to CSV",
                os.getcwd(),
                "CSV files (*.csv);;All files (*)"
            )
            
            if filename:
                try:
                    df.to_csv(filename, index=False)
                except Exception as e:
                    from Qt.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        parent_window if parent_window else self.view,
                        "Save Error",
                        f"Failed to save CSV file:\n{str(e)}"
                    )

class HistBurstSizeAllPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'Hist. Burst Size'
    PLOT_FUNC = staticmethod(fretbursts.hist_size_all)

class HistBurstWidthPlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'Hist Burst Width'
    PLOT_FUNC = staticmethod(fretbursts.hist_width)

class HistBurstBrightnessPlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'Hist Burst Brightness'
    PLOT_FUNC = staticmethod(fretbursts.hist_brightness)

class HistBurstSBRPlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'Hist Burst SBR'
    PLOT_FUNC = staticmethod(fretbursts.hist_sbr)

class HistBurstPhratePlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'Hist Burst ph.Rate'
    PLOT_FUNC = staticmethod(fretbursts.hist_burst_phrate)




    
        
        
        
        
    
    
    
    
        
            
            
