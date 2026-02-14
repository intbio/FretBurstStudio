from custom_nodes.abstract_nodes import AbstractRecomputable
import fretbursts
from node_builder import NodeBuilder
from fbs_data import FBSData
from singletons import FBSDataCash





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

class BurstSelectorNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Size'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.size)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_slider('Low Threshold', [0, 1000, 1], 0)
        self.th2 = self.node_builder.build_int_slider('High Threshold', [0, 1000, 1], 500)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['th1'] = self.th1.get_value()
        self.SELECT_KWARGS['th2'] = self.th2.get_value()

class BurstSelectorENode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'FRET'
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.E)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_slider('Low Threshold', [-0.5, 1.5, 0.01], -0.5)
        self.th2 = self.node_builder.build_float_slider('High Threshold', [-0.5, 1.5, 0.01], 1.5)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['E1'] = self.th1.get_value()
        self.SELECT_KWARGS['E2'] = self.th2.get_value()


class BurstSelectorBrightnessNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Brightness'
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
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.na_bg)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100, 1], 0)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['F'] = self.th1.get_value()

class BurstSelectorNDNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'N Donor'
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
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.nd_bg)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_float_spinbox('Low Threshold', [0, 100, 1], 0)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['F'] = self.th1.get_value()

class BurstSelectorPeakPhrateNode(BaseSelectorNode):
    __identifier__ = 'Selectors'
    NODE_NAME = 'Peak Phrate'
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
    SELECT_FUNC = staticmethod(fretbursts.select_bursts.period)
    def __init__(self):
        super().__init__()
        self.th1 = self.node_builder.build_int_spinbox('Low Threshold', [0, 1000000, 1], 0)
        self.th2 = self.node_builder.build_int_spinbox('High Threshold', [0, 1000000, 1], 1000000)
    def update_select_kwargs(self):
        self.SELECT_KWARGS['bp1'] = self.th1.get_value()
        self.SELECT_KWARGS['bp2'] = self.th2.get_value()



class BurstSelectorSBRNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorSBR'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 100.0, 0.1], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 100.0, 0.1], 100.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=100.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.sbr, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


class BurstSelectorSingleNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorSingle'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        # Single function doesn't accept add_naa parameter
        
    def __select_bursts(self, fbdata: FBSData):
        return fbdata.data.select_bursts(fretbursts.select_bursts.single)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata)
        return [d]


class BurstSelectorTimeNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorTime'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1 (s)', [0.0, 1000.0, 0.1], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2 (s)', [0.0, 1000.0, 0.1], 1000.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=1000.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.time, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1 (s)').get_value(),
                                     self.get_widget('th2 (s)').get_value())
        return [d]


class BurstSelectorTopNMaxRateNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorTopNMaxRate'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.n_slider = node_builder.build_int_slider('N', [1, 1000, 1], 100)
        
    def __select_bursts(self, fbdata: FBSData, N=100):
        return fbdata.data.select_bursts(fretbursts.select_bursts.topN_max_rate, N=N)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, self.get_widget('N').get_value())
        return [d]


class BurstSelectorTopNNDANode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorTopNNDA'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.n_slider = node_builder.build_int_slider('N', [1, 1000, 1], 100)
        
    def __select_bursts(self, fbdata: FBSData, N=100):
        return fbdata.data.select_bursts(fretbursts.select_bursts.topN_nda, N=N)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, self.get_widget('N').get_value())
        return [d]


class BurstSelectorTopNSBRNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorTopNSBR'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.n_slider = node_builder.build_int_slider('N', [1, 1000, 1], 100)
        
    def __select_bursts(self, fbdata: FBSData, N=100):
        return fbdata.data.select_bursts(fretbursts.select_bursts.topN_sbr, N=N)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, self.get_widget('N').get_value())
        return [d]


class BurstSelectorWidthNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorWidth'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1 (ms)', [0.0, 100.0, 0.1], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2 (ms)', [0.0, 100.0, 0.1], 100.0)
        
    def __select_bursts(self, fbdata: FBSData, th1=0.0, th2=100.0):
        # Convert ms to seconds for the function (width expects seconds)
        return fbdata.data.select_bursts(fretbursts.select_bursts.width, th1=th1/1000.0, th2=th2/1000.0)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata,
                                     self.get_widget('th1 (ms)').get_value(),
                                     self.get_widget('th2 (ms)').get_value())
        return [d]

