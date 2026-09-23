import sys

import unittest
import NodeGraphQt
from Qt import QtWidgets, QtCore, QtGui
from unittest.mock import MagicMock
from pathlib import Path
import matplotlib

import fretGUI.custom_nodes.custom_nodes as custom_nodes
import fretGUI.custom_nodes.selector_nodes as selector_nodes
from fretGUI.singletons import ThreadSignalManager
from fretGUI.node_workers import NodeWorker
from fretGUI.custom_widgets.progressbar_widget import ProgressBar2
from fretGUI.custom_widgets.plot_widget import (
    TemplatePlotWidget,
    set_matplotlib_theme,
)
from fretGUI.main import THEME_COLORS, build_theme_palette

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

    def test_compact_wrapped_node_fields(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Analysis.BurstSearchNodeFromBG')
        app.processEvents()

        wrapper = node.widgets()['F, Min. Burst rate to bg. ratio']
        container = wrapper.widget()
        label = container._label

        self.assertTrue(label.wordWrap())
        self.assertEqual(container.layout().spacing(), 0)
        self.assertEqual(container.layout().contentsMargins().bottom(), 3)
        self.assertTrue(
            container.testAttribute(QtCore.Qt.WA_TranslucentBackground)
        )
        self.assertGreater(label.height(), label.fontMetrics().height())
        self.assertLess(node.view.boundingRect().width(), 180)

    def test_compact_port_display_names_preserve_internal_names(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Analysis.BurstSearchNodeFromBG')
        app.processEvents()

        input_port = node.input_ports()[0]
        output_port = node.output_ports()[0]
        input_text = node.view._input_items[input_port.view]
        output_text = node.view._output_items[output_port.view]

        self.assertEqual(input_port.name(), 'inport')
        self.assertEqual(output_port.name(), 'outport')
        self.assertEqual(input_text.toPlainText(), 'in')
        self.assertEqual(output_text.toPlainText(), 'out')

    def test_closing_file_removes_worker_state_before_widget_deletion(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Loaders.PhHDF5Node')
        path_widget = node.file_widget.path_widget
        path_widget.process_files(['/tmp/deleted-file.h5'])

        path_id, _, _ = path_widget.get_file_entries()[0]
        row_widget = path_widget.rowwidget_map[path_id]
        self.assertEqual(row_widget.del_button.text(), '×')
        self.assertTrue(row_widget.del_button.icon().isNull())
        row_widget.on_button_click()
        QtCore.QCoreApplication.sendPostedEvents(
            None,
            QtCore.QEvent.DeferredDelete,
        )

        self.assertEqual(path_widget.get_file_entries(), [])
        self.assertNotIn(path_id, path_widget.rowwidget_map)
        self.assertEqual(node.execute(), [])

    def test_plot_fills_width_and_controls_share_row(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Plot.ScatterRateDaPlotterNode')
        node.restore_size(450, 400)
        node._on_view_resized(450, 400)
        app.processEvents()

        plot_geometry = node.get_widget('plot_widget').geometry()
        file_geometry = node.items_to_plot.geometry()
        regression_geometry = node.regression_checkbox.geometry()
        input_port = node.input_ports()[0]
        input_text = node.view._input_items[input_port.view]

        self.assertEqual(plot_geometry.x(), 3)
        self.assertEqual(plot_geometry.y(), 25)
        self.assertEqual(plot_geometry.width(), 444)
        self.assertEqual(file_geometry.y(), regression_geometry.y())
        self.assertLess(file_geometry.right(), regression_geometry.left())
        self.assertLess(
            node.get_widget('plot_widget').zValue(),
            input_port.view.zValue(),
        )
        self.assertGreater(
            input_text.zValue(),
            node.get_widget('plot_widget').zValue(),
        )

        plot_widget = node.get_widget('plot_widget').get_custom_widget()
        self.assertEqual(plot_widget.figure.patch.get_alpha(), 0)
        self.assertTrue(
            plot_widget.canvas.testAttribute(
                QtCore.Qt.WA_TranslucentBackground
            )
        )
        self.assertTrue(
            plot_widget.toolbar.testAttribute(
                QtCore.Qt.WA_TranslucentBackground
            )
        )
        expected_inset = round(
            input_text.pos().x()
            + input_text.boundingRect().width()
            - node.LEFT_RIGHT_MARGIN
            + 6
        )
        self.assertEqual(plot_widget._toolbar_left_inset, expected_inset)
        self.assertEqual(
            plot_widget._toolbar_left_spacer.width(),
            expected_inset,
        )
        history_actions = {
            action.text().replace('&', '').strip().lower(): action
            for action in plot_widget.toolbar.actions()
            if action.text()
        }
        self.assertFalse(history_actions['back'].isVisible())
        self.assertFalse(history_actions['forward'].isVisible())

        file_container = node.items_to_plot.widget()
        regression_container = node.regression_checkbox.widget()
        self.assertEqual(
            file_container._label.alignment(),
            regression_container._label.alignment(),
        )
        self.assertEqual(
            file_container._label.font().pointSize(),
            regression_container._label.font().pointSize(),
        )

        regression_container.set_text_color((12, 34, 56))
        label_color = regression_container._label.palette().color(
            regression_container._label.foregroundRole()
        )
        checkbox = node.regression_checkbox.get_custom_widget().checkbox
        checkbox_color = checkbox.palette().color(checkbox.foregroundRole())
        self.assertEqual(label_color.getRgb()[:3], (12, 34, 56))
        self.assertEqual(checkbox_color.getRgb()[:3], (12, 34, 56))

        checkbox.setChecked(False)
        self.assertFalse(node.get_property('show_regression'))

    def test_combobox_popup_temporarily_raises_owning_node(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Plot.ScatterRateDaPlotterNode')
        node.items_to_plot.set_items(['first', 'second'])
        app.processEvents()

        combo = node.items_to_plot.get_custom_widget().combobox
        original_node_z = node.view.zValue()
        original_proxy_z = node.items_to_plot.zValue()

        combo.showPopup()
        self.assertGreater(node.view.zValue(), 1000)
        self.assertGreater(node.items_to_plot.zValue(), node.view.zValue())

        combo.hidePopup()
        self.assertEqual(node.view.zValue(), original_node_z)
        self.assertEqual(node.items_to_plot.zValue(), original_proxy_z)

    def test_plot_limits_survive_replot_per_node(self):
        graph = BaseUtils.init_graph()
        first_node = graph.create_node('Plot.ScatterRateDaPlotterNode')
        second_node = graph.create_node('Plot.ScatterRateDaPlotterNode')
        first_plot = first_node.get_widget('plot_widget').get_custom_widget()
        second_plot = second_node.get_widget('plot_widget').get_custom_widget()

        first_ax = first_plot.figure.add_subplot()
        first_ax.plot([0, 10], [0, 20])
        first_plot.canvas.draw()
        first_ax.set_xlim(2, 4)
        first_ax.set_ylim(6, 9)
        first_plot.canvas.draw()

        first_plot.figure.clear()
        replotted_ax = first_plot.figure.add_subplot()
        replotted_ax.plot([0, 100], [0, 200])
        first_plot.canvas.draw()

        self.assertEqual(replotted_ax.get_xlim(), (2.0, 4.0))
        self.assertEqual(replotted_ax.get_ylim(), (6.0, 9.0))

        first_plot.toolbar._actions['home'].trigger()
        first_plot.canvas.draw()
        self.assertNotEqual(replotted_ax.get_xlim(), (2.0, 4.0))
        self.assertNotEqual(replotted_ax.get_ylim(), (6.0, 9.0))
        self.assertEqual(
            replotted_ax.get_xlim(),
            first_plot._default_limits[0][0],
        )
        self.assertEqual(
            replotted_ax.get_ylim(),
            first_plot._default_limits[0][1],
        )

        second_ax = second_plot.figure.add_subplot()
        second_ax.plot([0, 100], [0, 200])
        second_plot.canvas.draw()
        self.assertEqual(second_ax.get_xlim(), replotted_ax.get_xlim())

        unretained_plot = TemplatePlotWidget(retain_limits=False)
        unretained_ax = unretained_plot.figure.add_subplot()
        unretained_ax.plot([0, 10], [0, 20])
        unretained_plot.canvas.draw()
        unretained_ax.set_xlim(2, 4)
        unretained_plot.canvas.draw()
        unretained_plot.figure.clear()
        unretained_ax = unretained_plot.figure.add_subplot()
        unretained_ax.plot([0, 100], [0, 200])
        unretained_plot.canvas.draw()
        self.assertNotEqual(unretained_ax.get_xlim(), (2.0, 4.0))

    def test_dark_theme_updates_qt_controls_and_matplotlib(self):
        original_palette = app.palette()
        graph = BaseUtils.init_graph()
        node = graph.create_node('Plot.ScatterRateDaPlotterNode')
        plot_widget = node.get_widget('plot_widget').get_custom_widget()
        combo = node.items_to_plot.get_custom_widget().combobox
        container = node.items_to_plot.widget()
        ax = plot_widget.figure.add_subplot()
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_title('Title')
        ax.plot([0, 1], [0, 1], label='line')
        ax.legend()

        home_action = plot_widget.toolbar._actions['home']
        light_icon_key = home_action.icon().cacheKey()

        try:
            dark = THEME_COLORS['dark']
            app.setPalette(build_theme_palette('dark'))
            container.set_theme('dark', dark)
            plot_widget.set_theme('dark', dark)
            node.set_color(*dark['plot_node'])

            combo_palette = combo.palette()
            self.assertEqual(
                combo_palette.color(QtGui.QPalette.Base).getRgb()[:3],
                dark['base'],
            )
            self.assertEqual(
                combo.view().palette().color(
                    QtGui.QPalette.WindowText
                ).getRgb()[:3],
                dark['text'],
            )
            self.assertEqual(tuple(node.color()), dark['plot_node'])
            self.assertEqual(
                matplotlib.colors.to_rgba(
                    matplotlib.rcParams['axes.facecolor']
                ),
                ax.get_facecolor(),
            )
            self.assertEqual(
                matplotlib.colors.to_rgba(
                    matplotlib.rcParams['text.color']
                ),
                matplotlib.colors.to_rgba(
                    ax.xaxis.label.get_color()
                ),
            )
            self.assertEqual(home_action.icon().cacheKey(), light_icon_key)
            self.assertEqual(
                plot_widget.toolbar.palette().color(
                    QtGui.QPalette.WindowText
                ).getRgb()[:3],
                (0, 0, 0),
            )

            light = THEME_COLORS['light']
            app.setPalette(build_theme_palette('light'))
            container.set_theme('light', light)
            plot_widget.set_theme('light', light)
            node.set_color(*light['plot_node'])

            self.assertEqual(
                combo.palette().color(QtGui.QPalette.Base).getRgb()[:3],
                light['base'],
            )
            self.assertEqual(tuple(node.color()), light['plot_node'])
            self.assertEqual(
                matplotlib.colors.to_rgba(
                    matplotlib.rcParams['axes.facecolor']
                ),
                ax.get_facecolor(),
            )
        finally:
            app.setPalette(original_palette)
            set_matplotlib_theme('light')
    
        
        
        
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

    def test_worker_thread_started_signals(self):
        ThreadSignalManager().disconnect()
        graph = self.__load_template("test_signals.json")
        lsm_node = graph.get_node_by_name('Confocor2 RAW')
        worker = NodeWorker(lsm_node)
        spy = QSignalSpy(ThreadSignalManager().thread_started)
        all_thread_finished_spy = QSignalSpy(ThreadSignalManager().all_thread_finished)
        progress_bar = ProgressBar2()
        ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
        ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
        ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
        worker.run()
        self.assertTrue(all_thread_finished_spy.wait(10000), "thread_started signal was not obtained")
        self.assertEqual(spy.count(), 2, "it should be 2 emitions of thread_started signal")
        
    def test_worker_thread_finished_signals(self):
        ThreadSignalManager().disconnect()
        graph = self.__load_template("test_signals.json")
        lsm_node = graph.get_node_by_name('Confocor2 RAW')
        worker = NodeWorker(lsm_node)
        spy = QSignalSpy(ThreadSignalManager().thread_finished)
        all_thread_finished_spy = QSignalSpy(ThreadSignalManager().all_thread_finished)
        progress_bar = ProgressBar2()
        ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
        ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
        ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
        worker.run()
        self.assertTrue(all_thread_finished_spy.wait(10000))
        self.assertEqual(spy.count(), 2, "it should be 2 emitions of thread_finished signal")
        
    def test_worker_all_thread_finished(self):
        ThreadSignalManager().disconnect()
        graph = self.__load_template("test_signals.json")
        progress_bar = ProgressBar2()
        ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
        ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
        ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
        lsm_node = graph.get_node_by_name('Confocor2 RAW')
        worker = NodeWorker(lsm_node)
        spy = QSignalSpy(ThreadSignalManager().all_thread_finished)
        worker.run()
        self.assertTrue(spy.wait(10000), "all_thread_finished signal was not obtained")
        self.assertEqual(spy.count() , 1, "it should be 1 emition of all_thread_finished signal")
        
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