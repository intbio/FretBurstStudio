import fretGUI.custom_widgets.path_selector as path_selector
from fretGUI.custom_nodes.abstract_nodes import AbstractRecomputable, ResizableContentNode
import fretbursts, os
from fretGUI.node_builder import NodeBuilder
import NodeGraphQt
from fretGUI.singletons import NodeStateManager


from fretGUI.fbs_data import FBSData
from fretGUI.singletons import FBSDataCash, ThreadSignalManager
from Qt.QtWidgets import QAction, QFileDialog  # pyright: ignore[reportMissingModuleSource]
from abc import abstractmethod
import numpy as np
from fretbursts.burstlib import Data
import pandas as pd
import seaborn as sns
from fretGUI.singletons import FBSDataIDGenerator


class AbstractLoader(AbstractRecomputable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ConstraintsBuilder.add_loader_constraints(self) CONSTRAInts EXAMPLE
        
        p = self.add_output('out_file', color=(255, 0, 0))
        # p.type_ = lambda: 'no_burst'

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
    def load(self, path: str, id: int = None, checked: bool=False) -> FBSData:
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
            
            rowwidget = self.file_widget.get_rowwidget(assigned_id)
            if path_hash in self.opened_paths:
                # Use existing FBSData (which already has an ID)
                existing_fbsdata = self.opened_paths[path_hash]
                fbsdata_copy = existing_fbsdata.copy()
                fbsdata_copy.set_checked(rowwidget.is_checked())
                data_list.append(fbsdata_copy)
                # Update tooltip for loaded file
                tooltip_text = self._format_metadata_tooltip(existing_fbsdata)
                self.file_widget.update_tooltip_for_path(cur_path, tooltip_text)
            else:
                # Load new FBSData with the pre-assigned ID
                loaded_fbsdata = self.load(cur_path, id=assigned_id, checked=rowwidget.is_checked())
                self.opened_paths[path_hash] = loaded_fbsdata.copy()
                # self.__wire_fbsdata(self.opened_paths[path_hash])
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
    NODE_NAME  = 'Photon HDF5'

    def __init__(self):
        super().__init__() 
    
    def load(self, path, id=None, checked=False):
        data = fretbursts.loader.photon_hdf5(path)
        fbsdata = FBSData(data, path, id=id, checked=checked)
        return fbsdata   
        
        
class LSM510Node(AbstractLoader):
    from fretGUI.misc.fcsfiles import ConfoCor2Raw
    __identifier__ = 'Loaders'
    NODE_NAME  = 'Confocor2 RAW'

    def __init__(self):
        super().__init__() 
    
    def load(self, path: str, id=None, checked=False):
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
        data.name = os.path.basename(path)
        fbsdata = FBSData(data, path, id=id, checked=checked)
        return fbsdata   
        
    
class AlexNode(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'AlexNode'
    
    def __init__(self):
        super().__init__()
        self.add_input('inport', color=(255, 0, 0))
        self.add_output('outport', color=(255, 0, 0))        
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData) -> list[FBSData]:
        fretbursts.loader.alex_apply_period(fbsdata.data, False)
        return [fbsdata]
    
    
class CalcBGNode(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'Calc.Background'

    def __init__(self):
        super().__init__()
        node_builder = NodeBuilder(self)
        self.add_input('inport', color=(255, 0, 0))
        p = self.add_output('outport', color=(255,255,0))
        # p.type_ = lambda: 'no_burst'
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
        self.view.setToolTip("Apply gamma, leakage, and direct excitation corrections to FRET data")

        node_builder = NodeBuilder(self)
        self.add_input('inport', color=(255,255,0))
        p = self.add_output('outport', color=(255,255,0))  
        # p.type_ = lambda: 'no_burst'
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
            tooltip='ALEX ONLY!!! The coefficient dir_ex_t expresses the direct excitation as n_dir = dir_ex_t * (na + gamma*nd). In terms of physical parameters it is the ratio of acceptor over donor absorption cross-sections at the donor-excitation wavelength.', 
            min_width=self.fields_width)

    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData) -> list[FBSData]:
        fbsdata.data.gamma = self.gamma_spinbox.get_value()
        fbsdata.data.leakage = self.leakage_spinbox.get_value()
        fbsdata.data.dir_ex = self.dir_ex_spinbox.get_value()
        if hasattr(fbsdata.data, 'num_bursts') and fbsdata.data.num_bursts[0] > 0:
            # Recalculate E values for existing bursts
            fbsdata.data.calc_fret()
        return [fbsdata]
    
class DitherNode(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'Dither'
    fields_width = 100
    
    def __init__(self):
        super().__init__()

        node_builder = NodeBuilder(self)
        p = self.add_input('inport')
        # p.type_ = lambda: 'burst'
        # p.add_reject_port_type('outport', 'no_burst', None)
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
    NODE_NAME = 'BurstSearch by Rate'
    
    def __init__(self):
        super().__init__()
        node_builder = NodeBuilder(self)
        
        self.add_input('inport', color=(255,255,0))
        self.add_output('outport')
        self.m_slider = node_builder.build_int_slider(
            'm, Photon search window',
             [3, 100, 1],
              10,
              tooltip='Number of consecutive photons used to compute the photon rate. Typical values 5-20.')
        self.L_slider = node_builder.build_int_slider(
            'L, Minimal Burst size',
            [3, 100, 1],
            20,
            tooltip='Minimum number of photons in burst.')
        self.int_slider = node_builder.build_int_slider(
            'Min. rate cps',
            [1000, 100000, 1000],
            8000,
            tooltip = "Minimum rate in cps for burst start.")
        
    def __burst_search(self, fbdata: str, m, L, min_rate_cps):
        fbdata.data.burst_search(m=m, L=L, min_rate_cps = min_rate_cps)
       
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.__burst_search(fbsdata, m=self.m_slider.get_value(),
                                    L=self.L_slider.get_value(),
                                    min_rate_cps=self.int_slider.get_value())
        return [fbsdata]

class FuseBurstsNode(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'FuseBursts'
    
    def __init__(self):
        super().__init__()
        node_builder = NodeBuilder(self)
        
        p = self.add_input('inport')
        # p.add_reject_port_type(None,'no_burst',None)
        self.add_output('outport')
        self.delay_slider = node_builder.build_float_slider(
            'Delay, ms', 
            [0, 10, 0.1], 
            0,
            tooltip = "Fuse all burst separated by less than Delay millisecs. Note that with ms = 0, overlapping bursts are fused.")
        
       
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        fbsdata.data = fbsdata.data.fuse_bursts(ms=self.delay_slider.get_value())
        return [fbsdata]
        
class BurstSearchNodeFromBG(AbstractRecomputable):
    __identifier__ = 'Analysis'
    NODE_NAME = 'BurstSearch by BG'
    fields_width = 100
    
    def __init__(self):
        super().__init__()
        node_builder = NodeBuilder(self)
        
        self.add_input('inport', color=(255,255,0))
        self.add_output('outport')
        self.m_slider = node_builder.build_int_spinbox(
            'm, Photon search window',
             [3, 100, 1],
              10,
              tooltip='Number of consecutive photons used to compute the photon rate. Typical values 5-20.',
              min_width=self.fields_width)
        self.L_slider = node_builder.build_int_spinbox(
            'L, Minimal Burst size',
            [3, 100, 1],
            20,
            tooltip='Minimum number of photons in burst.',
            min_width=self.fields_width)
        self.F_slider = node_builder.build_int_spinbox(
            'F, Min. Burst rate to bg. ratio',
             [1, 20, 1],
              6,
              tooltip='defines how many times higher than the background rate is the minimum rate used for burst search (min rate = F * bg. rate). Typical values are 3-9.',
              min_width=self.fields_width)
        self.sel_box = node_builder.build_combobox(
            'Channel',
            ['DAem','Dem','Aem'],
            'DAem',
            '“photon selection” to be used for burst search, DAem - both donor and Acceptor, Dem - only donor, Aem - only acceptor')
        
    def __burst_search(self, fbdata: str, m: int,L: int,F: int,sel):
        fbdata.data.burst_search(m=m,L=L,F=F,ph_sel=fretbursts.Ph_sel(Dex=sel))
       
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.__burst_search(fbsdata,m=self.m_slider.get_value(),
                                    L=self.L_slider.get_value(),
                                    F=self.F_slider.get_value(),
                                    sel = self.sel_box.get_value())
        return [fbsdata]    
          
        
class AbstractContentNode(ResizableContentNode):
    def __init__(self, widget_name, qgraphics_item=None, inport_color=None, enable_multiports=True):
        super().__init__(widget_name, qgraphics_item)
        self.__enable_multiports = enable_multiports
        self.__inport_color = inport_color
        self.data_to_plot = []
        ThreadSignalManager().all_thread_finished.connect(self.on_refresh_canvas)
        ThreadSignalManager().all_thread_finished.connect(self.on_check_ports)
        self.__prevnodeid_data_map = dict()
        self.was_executed = False
        
        print(inport_color, "INPORT")
        
        self.add_input('inport1', color=inport_color)
        self.set_port_deletion_allowed(mode=True)
        self.on_check_ports()
        
    def add_input(self, name, *args, **kwargs):
        return super().add_input(name, color=self.__inport_color)
        
    @property
    def plot_widget(self):
        return self.get_widget('plot_widget').plot_widget
    
    def has_plot_data(self) -> bool:
        return len(self.data_to_plot) != 0
        
    def on_refresh_canvas(self):
        if not self.was_executed:
            return
        if self.has_plot_data():
            print("WAS EXECUTED", type(self))
            self._on_refresh_canvas()
            self.plot_widget.canvas.draw()
            self.data_to_plot.clear()
        else:
            print("WAS NOT EXECUTED", type(self))   
            self.__on_plot_data_clear()
            self.plot_widget.canvas.draw()
        
    @abstractmethod
    def _on_refresh_canvas(self):
        pass
    
    def __on_plot_data_clear(self):
        self.data_to_plot.clear()
        self.plot_widget.figure.clear()
        self.__prevnodeid_data_map.clear()
        self.was_executed = False
        
    def get_input_port(self, fbsdata: FBSData) -> NodeGraphQt.Port:
        """function returns port from which current fbsdata came

        Args:
            fbsdata (FBSData): data

        Returns:
            NodeGraphQt.Port: corresponding input port
        """
        prev_nodeid = self.__prevnodeid_data_map.get(fbsdata)
        if prev_nodeid is None:
            return None
        
        connected_inports = self.connected_input_nodes()
        for port, connected_nodes in connected_inports.items():
            connected_node_ids = set([id(node) for node in connected_nodes])
            if prev_nodeid in connected_node_ids:
                return port
        return None
    
    def execute(self, fbsdata: FBSData=None):
        self.was_executed = True
        self.__prevnodeid_data_map[fbsdata] = fbsdata.prev_nodeid
        if fbsdata is not None:
            self.data_to_plot.append(fbsdata)
        return [fbsdata] 
    
    def __get_port_name(self, connected_inputs) -> str:
        connected_inputs = set(connected_inputs)
        for i in range(1, len(connected_inputs) + 1):
            name = f"inport{i}"
            if name not in connected_inputs:
                return name
        return f"inport{i+1}"
    
    def on_input_connected(self, in_port, out_port):
        if self.__enable_multiports:
            self.on_check_ports()
        return super().on_input_connected(in_port, out_port)
    
    def on_input_disconnected(self, in_port, out_port):
        status = NodeStateManager().node_status
        if not status:
            self.on_check_ports()
        return super().on_input_disconnected(in_port, out_port)
        
    def on_check_ports(self):
        if not self.__enable_multiports:
            return 
        
        connected_inputs = self.connected_input_nodes()
        empty_ports = []
        connected_ports = []
        for port, connected_nodes in connected_inputs.items():
            if len(connected_nodes) == 0:
                empty_ports.append(port)
            else:
                connected_ports.append(port)   
                
        if len(connected_ports) != 0 and len(empty_ports) == 0:
            new_portname = self.__get_port_name(self.inputs())
            self.add_input(new_portname)
            self.set_port_deletion_allowed(mode=True)
        
        if len(empty_ports) >= 2:
            for i in range(1, len(empty_ports)):
                cur_port = empty_ports[i]
                try:
                    self.delete_input(cur_port)
                except AttributeError as error:
                    print(error)

            
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

    def __init__(self, 
                 widget_name='plot_widget',
                 qgraphics_item=None,
                 inport_color=None,
                 enable_multiports=True):
        super().__init__(widget_name,
                         qgraphics_item,
                         inport_color=inport_color,
                         enable_multiports=enable_multiports)
        self.PLOT_KWARGS = {}
        self.node_builder = NodeBuilder(self)

        self.node_builder.build_plot_widget('plot_widget', mpl_width=3.0, mpl_height=3.0)
        self.items_to_plot = self.node_builder.build_combobox(
            widget_name="File to plot:",
            items=[],
            value=None,
            tooltip="Select an option"
        )

    def _on_refresh_canvas(self):
        fig = self.plot_widget.figure
        fig.clear()
        ax = fig.add_subplot()

        map_name_to_data = {}
        self.data_to_plot.sort(key = lambda x: x.id)
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
            self.plot_widget.canvas.draw()
            return

        fretbursts.dplot(selected_data, plot_func, ax=ax, **self.PLOT_KWARGS)
        # fig.tight_layout()
        self.plot_widget.canvas.draw()

class BaseMultiFilePlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'BaseMultiFilePlotterNode'

    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 10
    BOTTOM_MARGIN = 0
    PLOT_NODE = True
    MIN_WIDTH = 550
    MIN_HEIGHT = 250
    PLOT_FUNC = None
    

    def __init__(self, widget_name='plot_widget', qgraphics_item=None, inport_color=None, enable_multiports=True):
        super().__init__(widget_name, qgraphics_item, inport_color=inport_color, enable_multiports=enable_multiports)
        self.node_builder = NodeBuilder(self)
        self.PLOT_KWARGS = {}
        
        self.node_builder.build_plot_widget('plot_widget', mpl_width=4.0, mpl_height=3.0)

        plot_widget = self.get_widget('plot_widget').plot_widget
        toolbar = plot_widget.toolbar
        
        save_data_action = QAction('save data', toolbar)
        save_data_action.triggered.connect(lambda: self.export(export_type='file'))
        toolbar.addAction(save_data_action)
        toolbar.widgetForAction(save_data_action).setStyleSheet("border: 1px solid gray;")

        copy_data_action = QAction('copy data', toolbar)
        copy_data_action.triggered.connect(lambda: self.export(export_type='copy'))
        toolbar.addAction(copy_data_action)
        toolbar.widgetForAction(copy_data_action).setStyleSheet("border: 1px solid gray;")
    
    def update_plot_kwargs(self):
        pass

    def _on_refresh_canvas(self):
        self.plot_widget.figure.clf()
        self.ax = self.plot_widget.figure.add_subplot()
        self.ax.cla()

        # Avoid accidental binding and ensure we have a valid plot function
        plot_func = self.PLOT_FUNC.__func__ if isinstance(self.PLOT_FUNC, staticmethod) else self.PLOT_FUNC
        if plot_func is None:
            self.plot_widget.canvas.draw()
            return
        self.update_plot_kwargs()

        self.data_to_plot.sort(key = lambda x: x.id)

        for cur_data in self.data_to_plot:
            if not isinstance(cur_data.data, Data):
                continue
            
            # Call fretbursts.dplot for each item in data_to_plot
            fretbursts.dplot(cur_data.data, plot_func, ax=self.ax, **self.PLOT_KWARGS)

            if len(self.connected_input_nodes())==2:
                name = f'{cur_data.data.name}, N {cur_data.data.num_bursts[0]}'
            else:
                print(type(cur_data))
                
                inport_name = self.get_input_port(cur_data).name()
                print(f"INPORT {inport_name}, NODE: {type(self)}")
                
                name = f'{cur_data.data.name}, N {cur_data.data.num_bursts[0]}'
            if self.ax.lines:
                self.ax.lines[-1].set_label(name)

        # Add legend if multiple files are plotted
        if len(self.data_to_plot) > 1:
            self.ax.legend()
            self.ax.set_title('')
        
        self.plot_widget.canvas.draw()
    def export(self, export_type = 'file'):
        data_dict = {}

        for line in self.ax.get_lines():
            label = line.get_label()
            x_data = line.get_xdata()
            y_data = line.get_ydata()

            data_dict[f"{label}, X"] = x_data
            data_dict[f"{label}, Y"] = y_data

        df = pd.DataFrame(data_dict)
        if not df.empty:
            df.set_index(df.columns[0], inplace=True)
            if export_type == 'file':
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
            else:
                df.to_clipboard()

class BGFitPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'Background Fit'
    PLOT_FUNC = staticmethod(fretbursts.hist_bg)
    PLOT_KWARGS = dict(show_fit=True)
    
    def __init__(self, widget_name='plot_widget', qgraphics_item=None, inport_color=(255,255,0), enable_multiports=False):
        super().__init__(widget_name, qgraphics_item, inport_color, enable_multiports=enable_multiports)

class BGTimeLinePlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'Background TimeLine'
    PLOT_FUNC = staticmethod(fretbursts.timetrace_bg)
    
    def __init__(self, widget_name='plot_widget', qgraphics_item=None, inport_color=(255,255,0), enable_multiports=False):
        super().__init__(widget_name, qgraphics_item, inport_color, enable_multiports=enable_multiports)

class ScatterWidthSizePlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'Burst Width vs Size'
    PLOT_FUNC = staticmethod(fretbursts.scatter_width_size)

class ScatterDaPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'B.Donor vs Acc Size'
    PLOT_FUNC = staticmethod(fretbursts.scatter_da)

class ScatterRateDaPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'B.Donor vs Acc Rate'
    PLOT_FUNC = staticmethod(fretbursts.scatter_rate_da)

class ScatterFretSizePlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'Burst FRET vs Size'
    PLOT_FUNC = staticmethod(fretbursts.scatter_fret_size)

class ScatterFretNdNaPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'B. FRET vs Corr.Size'
    PLOT_FUNC = staticmethod(fretbursts.scatter_fret_nd_na)

class ScatterFretWidthPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'Burst FRET vs Width'
    PLOT_FUNC = staticmethod(fretbursts.scatter_fret_width)
       
    
class EHistPlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'FRET histogram'
    PLOT_FUNC = staticmethod(fretbursts.hist_fret)
    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)        
        self.BinWidth_slider = self.node_builder.build_float_slider('Bin Width', [0.01, 0.2, 0.01], 0.03)    
        self.PLOT_KWARGS['hist_style'] = 'line'
    def update_plot_kwargs(self):
        self.PLOT_KWARGS['binwidth'] = self.BinWidth_slider.get_value()        

class HistBurstSizeAllPlotterNode(BaseSingleFilePlotterNode):
    NODE_NAME = 'Burst Size hist.'
    PLOT_FUNC = staticmethod(fretbursts.hist_size_all)

class HistBurstWidthPlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'Burst Width hist'
    PLOT_FUNC = staticmethod(fretbursts.hist_width)
    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)        
        self.BinWidth_slider = self.node_builder.build_float_slider('Bin Width, ms', [0.01, 3, 0.1], 0.5)
    def update_plot_kwargs(self):
        self.PLOT_KWARGS['bins'] = (0, 15, self.BinWidth_slider.get_value() )   


class HistBurstBrightnessPlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'Burst Brightness hist.'
    PLOT_FUNC = staticmethod(fretbursts.hist_brightness)

class HistBurstSBRPlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'Burst Sig.Bg.Rat. Hist.'
    PLOT_FUNC = staticmethod(fretbursts.hist_sbr)

class HistBurstPhratePlotterNode(BaseMultiFilePlotterNode):
    NODE_NAME = 'Burst Max.Rate Hist.'
    PLOT_FUNC = staticmethod(fretbursts.hist_burst_phrate)




    
class BVAPlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'BVA'

    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 10
    BOTTOM_MARGIN = 0
    PLOT_NODE = True
    MIN_WIDTH = 450
    MIN_HEIGHT = 300

    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        super().__init__(widget_name, qgraphics_item)
        self.PLOT_KWARGS = {}
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
        self.data_to_plot.sort(key = lambda x: x.id)
        for cur_data in self.data_to_plot:
            fname = os.path.basename(cur_data.data.fname)
            fbid = cur_data.id
            map_name_to_data[f'{fbid}, {fname}'] = cur_data.data

        self.items_to_plot.set_items(list(map_name_to_data.keys()))
        selected_val = self.items_to_plot.get_value()
        selected_data = map_name_to_data.get(selected_val)

        if selected_data is None or not isinstance(selected_data, Data):
            plot_widget.canvas.draw()
            return
        def bva_sigma_E(n, bursts, DexAem_mask, out=None):
            """
            Perform BVA analysis computing std.dev. of E for sub-bursts in each burst.
            
            Split each burst in n-photons chunks (sub-bursts), compute E for each sub-burst,
            then compute std.dev. of E across the sub-bursts.

            For details on BVA see:

            - Torella et al. (2011) Biophys. J. doi.org/10.1016/j.bpj.2011.01.066
            - Ingargiola et al. (2016) bioRxiv, doi.org/10.1101/039198

            Arguments:
                n (int): number of photons in each sub-burst
                bursts (Bursts object): burst-data object with indexes relative 
                    to the Dex photon stream.
                DexAem_mask (bool array): mask of A-emitted photons during D-excitation 
                    periods. It is a boolean array indexing the array of Dex timestamps 
                    (`Ph_sel(Dex='DAem')`).
                out (None or list): append the result to the passed list. If None,
                    creates a new list. This is useful to accumulate data from
                    different spots in a single list.

            Returns:
                E_sub_std (1D array): contains for each burst, the standard deviation of 
                sub-bursts FRET efficiency. Same length of input argument `bursts`.
            """
            E_sub_std = [] if out is None else out
            
            for burst in bursts:
                E_sub_bursts = []
                startlist = range(burst.istart, burst.istop + 2 - n, n)
                stoplist = [i + n for i in startlist]
                for start, stop in zip(startlist, stoplist):
                    A_D = DexAem_mask[start:stop].sum()
                    assert stop - start == n
                    E = A_D / n
                    E_sub_bursts.append(E)
                E_sub_std.append(np.std(E_sub_bursts))
                
            return E_sub_std
        ds_FRET = selected_data
        ph_d = ds_FRET.get_ph_times(ph_sel=fretbursts.Ph_sel(Dex='DAem'))
        bursts = ds_FRET.mburst[0]
        bursts_d = bursts.recompute_index_reduce(ph_d)
        Dex_mask = ds_FRET.get_ph_mask(ph_sel=fretbursts.Ph_sel(Dex='DAem'))   
        DexAem_mask = ds_FRET.get_ph_mask(ph_sel=fretbursts.Ph_sel(Dex='Aem')) 
        DexAem_mask_d = DexAem_mask[Dex_mask]
        n = 7
        E_sub_std = bva_sigma_E(n, bursts_d, DexAem_mask_d)

        x = np.arange(0,1.01,0.01)
        y = np.sqrt((x*(1-x))/n)
        ax.plot(x, y, lw=2, color='k', ls='--')
        im = sns.kdeplot(data={'E':ds_FRET.E[0], 'sigma':np.asfarray(E_sub_std)}, x='E', y='sigma', 
                        fill=True, cmap='Spectral_r', thresh=0.05, levels=20)
        ax.set_xlim(0,1)
        ax.set_ylim(0,np.sqrt(0.5**2/7)*2)
        ax.set_xlabel('E', fontsize=16)
        ax.set_ylabel(r'$\sigma_i$', fontsize=16);
        
        # fig.tight_layout()
        plot_widget.canvas.draw()    
        
        
        
    
    
    
    
        
            
            
