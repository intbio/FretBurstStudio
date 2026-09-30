from fretGUI.custom_nodes.abstract_nodes import AbstractRecomputable
import fretbursts
from fretGUI.node_builder import NodeBuilder
from fretGUI.fbs_data import FBSData
from fretGUI.singletons import FBSDataCash





KCPS_TO_CPS = 1000


def _kcps_to_cps(value):
    """Selectors and burst search take counts per second; the UI is kcps."""
    return float(value) * KCPS_TO_CPS


def _ensure_photon_counts(data):
    """Count donor and acceptor photons when burst search skipped that step."""
    if 'nd' not in data or 'na' not in data:
        data.calc_ph_num()


def _ensure_fret(data):
    """Compute corrected FRET efficiency when it has not been stored yet."""
    if 'E' not in data:
        _ensure_photon_counts(data)
        data.calc_fret()


def _ensure_max_rate(data):
    """Store each burst's peak photon rate in counts per second.

    calc_max_rate subtracts the background. A fixed-rate burst search
    may have no background, so that path keeps the raw m-photon rate.
    """
    if 'max_rate' in data:
        return
    m = int(getattr(data, 'm', None) or 10)
    if 'bg' in data and 'bp' in data:
        data.calc_max_rate(m=m)
        return
    from fretbursts.phtools import phrates
    rates = data.calc_burst_ph_func(
        func=phrates.mtuple_rates_max,
        func_kw=dict(m=m, c=phrates.default_c),
    )
    data.add(
        max_rate=[rate / data.clk_p for rate in rates],
        max_rate_params={'m': m, 'compact': False},
    )


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

    def prepare(self, data):
        pass

    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        self.update_select_kwargs()
        self.prepare(fbsdata.data)
        fbsdata.data = fbsdata.data.select_bursts(self.SELECT_FUNC, **self.SELECT_KWARGS)
        return [fbsdata]

class BurstSelectorSizeNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Burst Size'
    DESCRIPTION = 'Keep bursts whose photon count is between the selected lower and upper thresholds.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.size)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000, 1], 500)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorENode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'FRET Efficiency'
    DESCRIPTION = 'Keep bursts whose corrected FRET efficiency (E) is within the selected range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.E)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [-0.5, 1.5, 0.01], -0.5)
        self.th2 = self.node_builder.build_float_spinbox('High Threshold', [-0.5, 1.5, 0.01], 1.5)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['E1'] = self.th1.get_value()
        self.SELECT_KWARGS['E2'] = self.th2.get_value()

    def prepare(self, data):
        _ensure_fret(data)


class BurstSelectorBrightnessNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Burst Brightness'
    DESCRIPTION = 'Keep bursts whose brightness (burst size divided by width) is within the selected kcps range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.brightness)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low, kcps', [0, 5000, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('High, kcps', [0, 5000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = _kcps_to_cps(self.th1.get_value())
        self.SELECT_KWARGS['th2'] = _kcps_to_cps(self.th2.get_value())

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorConsecutiveNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Consecutive Bursts'
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
    NODE_NAME = 'Acceptor Photon Count'
    DESCRIPTION = 'Keep bursts whose acceptor-channel photon count is within the selected range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.na)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorNABGNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Acceptor Count vs Background'
    DESCRIPTION = 'Keep bursts whose acceptor photon count is at least F times the acceptor background.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.na_bg)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100, 1], 0)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['F'] = self.th1.get_value()

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorNDNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Donor Photon Count'
    DESCRIPTION = 'Keep bursts whose donor-channel photon count is within the selected range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.nd)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorNDBGNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Donor Count vs Background'
    DESCRIPTION = 'Keep bursts whose donor photon count is at least F times the donor background.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.nd_bg)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100, 1], 0)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['F'] = self.th1.get_value()

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorPeakPhrateNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Peak Photon Rate'
    DESCRIPTION = 'Keep bursts whose peak photon rate is within the selected kcps range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.peak_phrate)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low, kcps', [0, 5000, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('High, kcps', [0, 5000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = _kcps_to_cps(self.th1.get_value())
        self.SELECT_KWARGS['th2'] = _kcps_to_cps(self.th2.get_value())

    def prepare(self, data):
        _ensure_max_rate(data)

class BurstSelectorPeriodNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Background Period'
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
    NODE_NAME = 'Signal-to-Background Ratio'
    DESCRIPTION = 'Keep bursts whose signal-to-background ratio is within the selected range.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.sbr)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('High Threshold', [0, 100, 1], 100)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorSingleNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Isolated Bursts'
    DESCRIPTION = 'Keep isolated bursts that are at least the selected number of milliseconds from other bursts.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.single)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Time, ms', [0, 1000, 1], 0)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th'] = self.th1.get_value()

class BurstSelectorTimeNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Experiment Time Range'
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
    NODE_NAME = 'Top N by Peak Rate'
    DESCRIPTION = 'Keep the selected number of bursts with the highest maximum photon rate.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.topN_max_rate)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('N', [0, 100000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['N'] = self.th1.get_value()

    def prepare(self, data):
        _ensure_max_rate(data)

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

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorTopNSBRNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Top N by Signal-to-Background'
    DESCRIPTION = 'Keep the selected number of bursts with the highest signal-to-background ratio.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.topN_sbr)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('N', [0, 100000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['N'] = self.th1.get_value()

    def prepare(self, data):
        _ensure_photon_counts(data)

class BurstSelectorWidthNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Burst Duration'
    DESCRIPTION = 'Keep bursts whose duration is within the selected range in milliseconds.'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.width)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Longer than, ms', [0, 1000, 1], 0)
        self.th2 = self.node_builder.build_float_spinbox('Shorter than, ms', [0, 1000, 1], 1000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()