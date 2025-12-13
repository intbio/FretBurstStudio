from custom_nodes.abstract_nodes import AbstractRecomputable
import fretbursts
from node_builder import NodeBuilder
from fbs_data import FBSData
from singletons import FBSDataCash


class BurstSelectorNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelector'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_int_slider('th1', [0, 1000, 10], 40)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=40):
        return fbdata.data.select_bursts(fretbursts.select_bursts.size, add_naa=add_naa, th1=th1)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True, self.get_widget('th1').get_value())
        return [d]


class BurstSelectorENode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorE'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 1.0, 0.01], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 1.0, 0.01], 1.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=1.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.E, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True, 
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


class BurstSelectorBrightnessNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorBrightness'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 10000.0, 100.0], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 10000.0, 100.0], 10000.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=10000.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.brightness, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


class BurstSelectorConsecutiveNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorConsecutive'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.n_slider = node_builder.build_int_slider('n', [1, 100, 1], 1)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, n=1):
        return fbdata.data.select_bursts(fretbursts.select_bursts.consecutive, add_naa=add_naa, n=n)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True, self.get_widget('n').get_value())
        return [d]


class BurstSelectorNANode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorNA'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 1000.0, 10.0], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 1000.0, 10.0], 1000.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=1000.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.na, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


class BurstSelectorNABGNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorNABG'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 1000.0, 10.0], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 1000.0, 10.0], 1000.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=1000.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.na_bg, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


class BurstSelectorNDNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorND'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 1000.0, 10.0], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 1000.0, 10.0], 1000.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=1000.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.nd, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


class BurstSelectorNDBGNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorNDBG'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 1000.0, 10.0], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 1000.0, 10.0], 1000.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=1000.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.nd_bg, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


class BurstSelectorPeakPhrateNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorPeakPhrate'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 100000.0, 1000.0], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 100000.0, 1000.0], 100000.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=100000.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.peak_phrate, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


class BurstSelectorPeriodNode(AbstractRecomputable):
    __identifier__ = 'Selectors'
    NODE_NAME = 'BurstSelectorPeriod'
    
    def __init__(self):
        super().__init__() 
        node_builder = NodeBuilder(self)
        
        self.add_input('inport')
        self.add_output('outport')
        self.th1_slider = node_builder.build_float_slider('th1', [0.0, 1000.0, 1.0], 0.0)
        self.th2_slider = node_builder.build_float_slider('th2', [0.0, 1000.0, 1.0], 1000.0)
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=1000.0):
        return fbdata.data.select_bursts(fretbursts.select_bursts.period, add_naa=add_naa, th1=th1, th2=th2)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1').get_value(),
                                     self.get_widget('th2').get_value())
        return [d]


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
        # Single might not need parameters, but keeping add_naa option
        # If it needs parameters, they can be added later
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True):
        return fbdata.data.select_bursts(fretbursts.select_bursts.single, add_naa=add_naa)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True)
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
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, N=100):
        return fbdata.data.select_bursts(fretbursts.select_bursts.topN_max_rate, add_naa=add_naa, N=N)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True, self.get_widget('N').get_value())
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
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, N=100):
        return fbdata.data.select_bursts(fretbursts.select_bursts.topN_nda, add_naa=add_naa, N=N)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True, self.get_widget('N').get_value())
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
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, N=100):
        return fbdata.data.select_bursts(fretbursts.select_bursts.topN_sbr, add_naa=add_naa, N=N)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True, self.get_widget('N').get_value())
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
        
    def __select_bursts(self, fbdata: FBSData, add_naa=True, th1=0.0, th2=100.0):
        # Convert ms to seconds for the function
        return fbdata.data.select_bursts(fretbursts.select_bursts.width, add_naa=add_naa, th1=th1/1000.0, th2=th2/1000.0)
    
    @FBSDataCash().fbscash
    def execute(self, fbsdata: FBSData):
        d = FBSData(path=fbsdata.path)
        d.data = self.__select_bursts(fbsdata, True,
                                     self.get_widget('th1 (ms)').get_value(),
                                     self.get_widget('th2 (ms)').get_value())
        return [d]

