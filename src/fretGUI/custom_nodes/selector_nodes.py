from fretGUI.custom_nodes.abstract_nodes import AbstractRecomputable
import fretbursts
from fretGUI.node_builder import NodeBuilder
from fretGUI.fbs_data import FBSData
from fretGUI.singletons import FBSDataCash





class BaseSelectorNode(AbstractRecomputable):
    SELECT_FUNC = None

    def __init__(self):
        super().__init__() 
        self.node_builder = NodeBuilder(self)
        self.SELECT_KWARGS = {}
        
        self.add_input('inport')
        self.add_output('outport')
    
    def update_select_kwargs(self):
        pass

    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.update_select_kwargs()
        fbsdata.data = fbsdata.data.select_bursts(self.SELECT_FUNC, **self.SELECT_KWARGS)
        return [fbsdata]

class BurstSelectorSizeNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Size'
    DESCRIPTION = 'Keep bursts whose photon count is between the selected lower and upper thresholds.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.size)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000, 1], 500)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

class BurstSelectorENode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'FRET'
    DESCRIPTION = 'Keep bursts whose corrected FRET efficiency (E) is within the selected range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.E)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [-0.5, 1.5, 0.01], -0.5)
        self.th2 = self.node_builder.build_float_spinbox('High Threshold', [-0.5, 1.5, 0.01], 1.5)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['E1'] = self.th1.get_value()
        self.SELECT_KWARGS['E2'] = self.th2.get_value()


class BurstSelectorBrightnessNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Brightness'
    DESCRIPTION = 'Keep bursts whose brightness (burst size divided by width) is within the selected cps range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.brightness)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

class BurstSelectorConsecutiveNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Consecutive?'
    DESCRIPTION = 'Keep consecutive bursts separated by a time within the selected range in seconds.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.consecutive)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

class BurstSelectorNANode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'N Acceptor'
    DESCRIPTION = 'Keep bursts whose acceptor-channel photon count is within the selected range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.na)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

class BurstSelectorNABGNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'N Acc. to Bg'
    DESCRIPTION = 'Keep bursts whose acceptor photon count is at least F times the acceptor background.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.na_bg)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100, 1], 0)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['F'] = self.th1.get_value()

class BurstSelectorNDNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'N Donor'
    DESCRIPTION = 'Keep bursts whose donor-channel photon count is within the selected range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.nd)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

class BurstSelectorNDBGNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'N Don. to Bg'
    DESCRIPTION = 'Keep bursts whose donor photon count is at least F times the donor background.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.nd_bg)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100, 1], 0)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['F'] = self.th1.get_value()

class BurstSelectorPeakPhrateNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Peak Phrate'
    DESCRIPTION = 'Keep bursts whose peak photon rate is within the selected counts-per-second range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.peak_phrate)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('High Threshold', [0, 10000000, 1], 10000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

class BurstSelectorPeriodNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Period?'
    DESCRIPTION = 'Keep bursts detected between the selected background-period indices, inclusive.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.period)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['bp1'] = self.th1.get_value()
        self.SELECT_KWARGS['bp2'] = self.th2.get_value()

class BurstSelectorSBRNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Signal to BG ratio'
    DESCRIPTION = 'Keep bursts whose signal-to-background ratio is within the selected range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.sbr)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('High Threshold', [0, 100, 1], 100)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

class BurstSelectorSingleNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Distant bursts'
    DESCRIPTION = 'Keep isolated bursts that are at least the selected number of milliseconds from other bursts.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.single)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Time, ms', [0, 1000, 1], 0)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th'] = self.th1.get_value()

class BurstSelectorTimeNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Experiment Time'
    DESCRIPTION = 'Keep bursts whose start time falls within the selected experiment-time range in seconds.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.time)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100000, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['time_s1'] = self.th1.get_value()
        self.SELECT_KWARGS['time_s2'] = self.th2.get_value()

class BurstSelectorTopNMaxRateNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Top N by Max.Rate'
    DESCRIPTION = 'Keep the selected number of bursts with the highest maximum photon rate.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.topN_max_rate)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('N', [0, 100000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['N'] = self.th1.get_value()

class BurstSelectorTopNNDANode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Top N by Size'
    DESCRIPTION = 'Keep the selected number of largest bursts by donor-plus-acceptor photon count.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.topN_nda)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('N', [0, 100000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['N'] = self.th1.get_value()

class BurstSelectorTopNSBRNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Top N by S.BG.Rat.'
    DESCRIPTION = 'Keep the selected number of bursts with the highest signal-to-background ratio.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.topN_sbr)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('N', [0, 100000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['N'] = self.th1.get_value()

class BurstSelectorWidthNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Width'
    DESCRIPTION = 'Keep bursts whose duration is within the selected range in milliseconds.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.width)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Longer than, ms', [0, 1000, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('Shorter than, ms', [0, 1000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()