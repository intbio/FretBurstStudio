import sys

import unittest
import NodeGraphQt
from Qt import QtWidgets, QtCore
from unittest.mock import MagicMock
from pathlib import Path

import fretGUI.custom_nodes.custom_nodes as custom_nodes
import fretGUI.custom_nodes.selector_nodes as selector_nodes
from fretGUI.singletons import ThreadSignalManager
from fretGUI.node_workers import NodeWorker

from PySide6.QtTest import QSignalSpy



app = QtWidgets.QApplication(sys.argv)


class BaseUtils():
    
    def __init__(self, methodName = "runTest"):
        super().__init__(methodName)
        
    @staticmethod
    def init_graph():
        graph = NodeGraphQt.NodeGraph()  
             
        graph.register_nodes(
                [
                    custom_nodes.LSM510Node,    
                    custom_nodes.PhHDF5Node,  
                    custom_nodes.CalcBGNode,
                    custom_nodes.CorrectionsNode,
                    custom_nodes.BurstSearchNodeFromBG,
                    custom_nodes.BurstSearchNodeRate,            
                    custom_nodes.FuseBurstsNode,
                    custom_nodes.DitherNode,
                    selector_nodes.BurstSelectorSizeNode,
                    selector_nodes.BurstSelectorWidthNode,
                    selector_nodes.BurstSelectorBrightnessNode,
                    selector_nodes.BurstSelectorTimeNode,
                    selector_nodes.BurstSelectorSingleNode,
                    selector_nodes.BurstSelectorENode,     
                    selector_nodes.BurstSelectorPeakPhrateNode,
                    selector_nodes.BurstSelectorNDNode,
                    selector_nodes.BurstSelectorNDBGNode,
                    selector_nodes.BurstSelectorConsecutiveNode,
                    selector_nodes.BurstSelectorNANode,
                    selector_nodes.BurstSelectorNABGNode,               
                    selector_nodes.BurstSelectorTopNMaxRateNode,
                    selector_nodes.BurstSelectorTopNNDANode,
                    selector_nodes.BurstSelectorTopNSBRNode,
                    selector_nodes.BurstSelectorSBRNode,
                    selector_nodes.BurstSelectorPeriodNode,
                    custom_nodes.BGFitPlotterNode,
                    custom_nodes.BGTimeLinePlotterNode,
                    custom_nodes.EHistPlotterNode,
                    custom_nodes.ScatterWidthSizePlotterNode,
                    custom_nodes.ScatterDaPlotterNode,
                    custom_nodes.ScatterRateDaPlotterNode,
                    custom_nodes.ScatterFretSizePlotterNode,
                    custom_nodes.ScatterFretNdNaPlotterNode,
                    custom_nodes.ScatterFretWidthPlotterNode,
                    custom_nodes.HistBurstSizeAllPlotterNode,
                    custom_nodes.HistBurstWidthPlotterNode,
                    custom_nodes.HistBurstBrightnessPlotterNode,
                    custom_nodes.HistBurstSBRPlotterNode,
                    custom_nodes.HistBurstPhratePlotterNode,  
                    custom_nodes.BVAPlotterNode
                ]
            )
        return graph
    
    
class TestGraph(unittest.TestCase):

    def test_create_nodes(self):
        graph = BaseUtils.init_graph()
        for i, node_name in enumerate(graph.registered_nodes()):
            print(f"{i + 1}: {node_name}")
            graph.create_node(node_name)
            
    def test_connections(self):
        graph = BaseUtils.init_graph()
        lsm510 = graph.create_node('Loaders.LSM510Node')
        red_outport = lsm510.add_output("red_outport", color=(255, 0, 0))
        
        histplot = graph.create_node('Plot.HistBurstSBRPlotterNode')
        red_inport = histplot.add_input("red_inport", color=(255, 0, 0))
        green_inport = histplot.add_input("green_inport", color=(0, 255, 0))
        
        try:
            lsm510.set_output(lsm510.output_ports().index(red_outport), red_inport)
        except Exception:
            self.fail("propper connection error")
        
        try:    
            lsm510.set_output(lsm510.output_ports().index(red_outport), green_inport)
        except AttributeError as error:
            print(error)
            pass
        else:
            self.fail("impropper connection was created")
         
            
class TestWidgets(unittest.TestCase):
    def test_run_btn(self):
        signal_manager = ThreadSignalManager()
        mock_listener = MagicMock()
        
        signal_manager.run_btn_clicked.connect(mock_listener)
        signal_manager.run_btn_clicked.emit()
        
        mock_listener.assert_called_once()
    
        
        
        
class TestWorkers(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        super().__init__(methodName)
        self.config_path = Path(__file__).parent.resolve() / "test_templates"
        
    def __load_template(self, template_path):
        template_path = str(self.config_path / template_path)
        graph = BaseUtils.init_graph()
        graph.load_session(template_path)
        return graph        
        
    def test_path1(self):
        graph = self.__load_template("test1.json")
        lsm_node = graph.get_node_by_name('Confocor2 RAW')
        worker = NodeWorker(lsm_node)
        paths = []
        worker._fill_nodeseq(worker.start_node, worker.node_seq, paths)
        paths = [list(map(lambda x: x.name(), seq)) for seq in paths]
        print(paths)
        propper_path = [
            ['Confocor2 RAW', 'Calc.Background', 'Corrections'],
            ['Confocor2 RAW', 'Calc.Background', 'Background TimeLine']
        ]
        self.assertEqual(len(paths), len(propper_path), "wrong lengths of paths")
        self.assertEqual(paths, propper_path)

    def test_worker_signals(self):
        graph = self.__load_template("test1.json")
        lsm_node = graph.get_node_by_name('Confocor2 RAW')
        worker = NodeWorker(lsm_node)
        signal_manager = ThreadSignalManager()
        spy = QSignalSpy(signal_manager.thread_started)
        worker.run()
        self.assertTrue(spy.wait(5000), "thread_started was not obtained")
        self.assertEqual(spy.count() , 2, "is should be 2 emitions of thread started signal")
        
    def test_path2(self):
        graph = self.__load_template("test2.json")
        loader1 = graph.get_node_by_name('Confocor2 RAW')
        answer1 = [['Confocor2 RAW', 'Calc.Background', 'Corrections', 'BurstSearch by BG', 'FRET histogram']]
        self.__subtest2(loader1, answer1)
        
        loader2 = graph.get_node_by_name('Confocor2 RAW 1')
        answer2 = [['Confocor2 RAW 1', 'Calc.Background 1', 'Corrections 1', 'BurstSearch by BG 1', 'FRET histogram']]
        self.__subtest2(loader2, answer2)
        
    def __subtest2(self, loader, answer):
        worker = NodeWorker(loader)
        paths = []
        worker._fill_nodeseq(worker.start_node, worker.node_seq, paths)
        paths = [list(map(lambda x: x.name(), seq)) for seq in paths]
        self.assertEqual(paths, answer, "paths are not equal")
        
        
            
        
        

        
        
        
        
            
        
if __name__ == '__main__':
    unittest.main()