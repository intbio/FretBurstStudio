import sys

import unittest
from types import SimpleNamespace

import NodeGraphQt
import numpy as np
from NodeGraphQt.constants import MIME_TYPE
from Qt import QtWidgets, QtCore, QtGui
from unittest.mock import MagicMock, patch
from pathlib import Path
import matplotlib
from matplotlib import colors as mpl_colors
from matplotlib.figure import Figure

import fretGUI.custom_nodes.custom_nodes as custom_nodes
import fretGUI.custom_nodes.selector_nodes as selector_nodes
from fretGUI.singletons import (
    FBSDataCash,
    RunContext,
    RunCoordinator,
    ThreadSignalManager,
)
from fretGUI.node_workers import NodeWorker
from fretGUI.fbs_data import FBSData
from fretGUI.custom_nodes.abstract_nodes import (
    AbstractRecomputable,
    ResizableContentNode,
)
from fretGUI.custom_widgets.progressbar_widget import ProgressBar2
from fretGUI.custom_widgets.node_sidebar import (
    CATEGORY_ROLE,
    NODE_TYPE_ROLE,
    NodeSidebar,
)
from fretGUI.custom_widgets.graph_file_drop import enable_graph_file_drop
from fretGUI.custom_widgets.graph_pan import enable_right_button_pan
from fretGUI.custom_widgets.graph_scale import keep_graph_scale_on_resize
from fretGUI.custom_widgets.plot_widget import (
    TemplatePlotWidget,
    install_plot_context_menu_guard,
    plot_area_at,
    set_matplotlib_theme,
)
from fretGUI.custom_widgets.sliders import (
    ComboBoxWidget,
    qcolor_from_item_data,
)
from fretGUI.main import THEME_COLORS, build_theme_palette, build_theme_stylesheet

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
                    custom_nodes.JoinDataNode,
                    custom_nodes.MergePhotonsNode,
                    custom_nodes.ExportPhotonHdf5Node,
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
            node = graph.create_node(node_name)
            description = getattr(type(node), 'DESCRIPTION', '')
            if description:
                self.assertEqual(node.view.toolTip(), description)
            
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
    def test_graph_context_menu_keeps_file_edit_and_skips_plot_area(self):
        import json

        hotkeys_path = Path(__file__).resolve().parents[1] / 'fretGUI' / 'hotkeys' / 'hotkeys.json'
        with hotkeys_path.open(encoding='utf-8') as handle:
            menu_items = json.load(handle)

        labels = [
            item.get('label', '').replace('&', '')
            for item in menu_items
            if item.get('type') == 'menu'
        ]
        self.assertEqual(labels, ['File', 'Edit'])

        graph = BaseUtils.init_graph()
        viewer = graph.viewer()
        install_plot_context_menu_guard(viewer)
        node = graph.create_node('Plot.EHistPlotterNode')
        graph.widget.resize(900, 700)
        graph.widget.show()
        app.processEvents()

        plot_proxy = node.get_widget('plot_widget')
        plot_center = viewer.mapFromScene(plot_proxy.sceneBoundingRect().center())
        empty_pos = viewer.mapFromScene(
            plot_proxy.sceneBoundingRect().topRight() + QtCore.QPointF(80, 80)
        )

        self.assertTrue(plot_area_at(viewer, plot_center))
        self.assertFalse(plot_area_at(viewer, empty_pos))

        guard = viewer._plot_context_menu_guard
        plot_event = QtGui.QContextMenuEvent(
            QtGui.QContextMenuEvent.Mouse,
            plot_center,
            viewer.mapToGlobal(plot_center),
        )
        empty_event = QtGui.QContextMenuEvent(
            QtGui.QContextMenuEvent.Mouse,
            empty_pos,
            viewer.mapToGlobal(empty_pos),
        )
        self.assertTrue(guard.eventFilter(viewer, plot_event))
        self.assertTrue(guard.eventFilter(viewer.viewport(), plot_event))
        self.assertFalse(guard.eventFilter(viewer, empty_event))
        self.assertFalse(guard.eventFilter(viewer.viewport(), empty_event))

    def test_window_resize_keeps_graph_scale(self):
        graph = BaseUtils.init_graph()
        viewer = graph.viewer()
        keep_graph_scale_on_resize(viewer)
        viewer.resize(800, 600)
        viewer.show()
        app.processEvents()
        viewer.set_zoom(-0.4)
        app.processEvents()

        def scale():
            return abs(viewer.transform().m11())

        def corner():
            point = viewer.mapToScene(QtCore.QPoint(0, 0))
            return point.x(), point.y()

        start_scale = scale()
        start_corner = corner()
        for width, height in ((820, 600), (1100, 760), (700, 500), (800, 600)):
            viewer.resize(width, height)
            app.processEvents()

        self.assertAlmostEqual(scale(), start_scale, places=2)
        end_corner = corner()
        self.assertAlmostEqual(end_corner[0], start_corner[0], delta=1.5)
        self.assertAlmostEqual(end_corner[1], start_corner[1], delta=1.5)

    def test_startup_zoom_is_readable_with_stable_scale(self):
        graph = BaseUtils.init_graph()
        viewer = graph.viewer()
        keep_graph_scale_on_resize(viewer)
        window = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(graph.widget, 0, 0)
        window.resize(1280, 800)
        window.show()
        app.processEvents()
        graph.set_zoom(-0.9)
        app.processEvents()
        scale = abs(viewer.transform().m11())
        self.assertGreater(scale, 0.8)
        self.assertLess(scale, 1.0)

    def test_right_drag_pans_and_click_does_not(self):
        graph = BaseUtils.init_graph()
        viewer = graph.viewer()
        enable_right_button_pan(viewer)
        keep_graph_scale_on_resize(viewer)
        graph.widget.resize(900, 700)
        graph.widget.show()
        app.processEvents()

        def center():
            point = viewer._scene_range.center()
            return (point.x(), point.y())

        def send(event_type, pos, button, buttons):
            viewport = viewer.viewport()
            local = QtCore.QPointF(pos)
            global_pos = QtCore.QPointF(viewport.mapToGlobal(pos))
            event = QtGui.QMouseEvent(
                event_type,
                local,
                global_pos,
                button,
                buttons,
                QtCore.Qt.NoModifier,
            )
            QtWidgets.QApplication.sendEvent(viewport, event)

        start = QtCore.QPoint(80, 80)
        before_click = center()
        send(
            QtCore.QEvent.MouseButtonPress,
            start,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
        )
        send(
            QtCore.QEvent.MouseButtonRelease,
            start,
            QtCore.Qt.RightButton,
            QtCore.Qt.NoButton,
        )
        app.processEvents()
        self.assertEqual(center(), before_click)
        self.assertFalse(viewer._rmb_pan)

        send(
            QtCore.QEvent.MouseButtonPress,
            start,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
        )
        send(
            QtCore.QEvent.MouseMove,
            start + QtCore.QPoint(4, 0),
            QtCore.Qt.NoButton,
            QtCore.Qt.RightButton,
        )
        self.assertEqual(center(), before_click)

        dragged = start + QtCore.QPoint(80, 30)
        send(
            QtCore.QEvent.MouseMove,
            dragged,
            QtCore.Qt.NoButton,
            QtCore.Qt.RightButton,
        )
        self.assertNotEqual(center(), before_click)
        self.assertTrue(viewer._rmb_pan)
        panned = center()
        viewer.resize(960, 740)
        app.processEvents()
        self.assertNotEqual(center(), before_click)
        moved = (
            abs(center()[0] - panned[0]),
            abs(center()[1] - panned[1]),
        )
        self.assertLess(max(moved), 80)

        menu_event = QtGui.QContextMenuEvent(
            QtGui.QContextMenuEvent.Mouse,
            dragged,
            viewer.viewport().mapToGlobal(dragged),
        )
        self.assertTrue(
            viewer._right_button_pan.eventFilter(viewer, menu_event)
        )
        self.assertFalse(viewer._rmb_pan)

    def test_right_drag_on_active_plot_tool_does_not_pan_graph(self):
        graph = BaseUtils.init_graph()
        viewer = graph.viewer()
        enable_right_button_pan(viewer)
        node = graph.create_node('Plot.EHistPlotterNode')
        graph.widget.resize(900, 700)
        graph.widget.show()
        app.processEvents()

        plot = node.get_widget('plot_widget').get_custom_widget()
        plot.toolbar.mode = 'zoom rect'
        plot_center = viewer.mapFromScene(
            node.get_widget('plot_widget').sceneBoundingRect().center()
        )

        def center():
            point = viewer._scene_range.center()
            return (point.x(), point.y())

        def send(event_type, pos, button, buttons):
            viewport = viewer.viewport()
            event = QtGui.QMouseEvent(
                event_type,
                QtCore.QPointF(pos),
                QtCore.QPointF(viewport.mapToGlobal(pos)),
                button,
                buttons,
                QtCore.Qt.NoModifier,
            )
            QtWidgets.QApplication.sendEvent(viewport, event)

        before = center()
        send(
            QtCore.QEvent.MouseButtonPress,
            plot_center,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
        )
        send(
            QtCore.QEvent.MouseMove,
            plot_center + QtCore.QPoint(80, 40),
            QtCore.Qt.NoButton,
            QtCore.Qt.RightButton,
        )
        self.assertEqual(center(), before)
        self.assertFalse(viewer._rmb_pan)
        self.assertTrue(viewer._rmb_plot_tool)

    def test_file_drop_highlights_loader_and_rejects_other_files(self):
        graph = BaseUtils.init_graph()
        viewer = graph.viewer()
        enable_graph_file_drop(graph)
        graph.widget.resize(900, 700)
        graph.widget.show()
        hdf = graph.create_node('Loaders.PhHDF5Node')
        raw = graph.create_node('Loaders.LSM510Node')
        hdf.set_pos(80, 80)
        raw.set_pos(520, 80)
        app.processEvents()

        def view_pos(node):
            return viewer.mapFromScene(node.view.sceneBoundingRect().center())

        empty = QtCore.QPoint(20, 20)

        def drag(kind, pos, filename):
            mime = QtCore.QMimeData()
            mime.setUrls([QtCore.QUrl.fromLocalFile(filename)])
            event = kind(
                QtCore.QPoint(pos),
                QtCore.Qt.CopyAction,
                mime,
                QtCore.Qt.LeftButton,
                QtCore.Qt.NoModifier,
            )
            return viewer._graph_file_drop.eventFilter(viewer, event), event

        hdf_pos = view_pos(hdf)
        raw_pos = view_pos(raw)

        handled, entered = drag(QtGui.QDragEnterEvent, empty, r'C:\data\trace.h5')
        self.assertTrue(handled)
        self.assertTrue(entered.isAccepted())

        handled, over_hdf = drag(QtGui.QDragMoveEvent, hdf_pos, r'C:\data\trace.h5')
        self.assertTrue(handled)
        self.assertTrue(over_hdf.isAccepted())
        self.assertTrue(hdf.view._file_drop_highlight.isVisible())

        handled, over_empty = drag(QtGui.QDragMoveEvent, empty, r'C:\data\trace.h5')
        self.assertTrue(handled)
        self.assertFalse(over_empty.isAccepted())
        self.assertFalse(hdf.view._file_drop_highlight.isVisible())

        handled, over_json = drag(QtGui.QDragMoveEvent, empty, r'C:\data\session.json')
        self.assertFalse(handled)

        handled, rejected = drag(QtGui.QDragMoveEvent, hdf_pos, r'C:\data\notes.txt')
        self.assertTrue(handled)
        self.assertFalse(rejected.isAccepted())
        self.assertFalse(hdf.view._file_drop_highlight.isVisible())

        handled, over_raw = drag(QtGui.QDragMoveEvent, raw_pos, r'C:\data\measurement.raw')
        self.assertTrue(handled)
        self.assertTrue(over_raw.isAccepted())
        self.assertTrue(raw.view._file_drop_highlight.isVisible())
        self.assertFalse(hdf.view._file_drop_highlight.isVisible())

        handled, dropped = drag(QtGui.QDropEvent, raw_pos, r'C:\data\measurement.raw')
        self.assertTrue(handled)
        self.assertTrue(dropped.isAccepted())
        self.assertEqual(
            [Path(path) for path in raw.file_widget.path_widget.get_paths()],
            [Path(r'C:\data\measurement.raw')],
        )
        self.assertFalse(raw.view._file_drop_highlight.isVisible())

        imported = []
        handler = viewer._graph_file_drop
        handler._original_drop = lambda *args: imported.append(args)
        handler._last_drop = None
        stray = QtCore.QMimeData()
        stray.setUrls([QtCore.QUrl.fromLocalFile(r'C:\data\trace.h5')])
        handler.on_viewer_data_dropped(stray, QtCore.QPoint(-1000, -1000))
        self.assertEqual(imported, [])
        self.assertEqual(hdf.file_widget.path_widget.get_paths(), [])

    def test_timetrace_explorer_is_compact_recomputable_node(self):
        graph = BaseUtils.init_graph()
        graph.register_node(custom_nodes.TimetraceExplorerNode)
        node = graph.create_node('Plot.TimetraceExplorerNode')

        self.assertIsInstance(node, AbstractRecomputable)
        self.assertNotIsInstance(node, ResizableContentNode)
        self.assertFalse(hasattr(node.view, '_resize_handle'))
        self.assertEqual(len(node.input_ports()), 1)
        self.assertGreaterEqual(node.items_to_plot.minimumWidth(), 200)
        self.assertGreaterEqual(
            node.items_to_plot.get_custom_widget().minimumWidth(),
            200,
        )

        data = custom_nodes.Data(
            ph_times_m=[np.arange(5)],
            A_em=[np.zeros(5, dtype=bool)],
            clk_p=1e-6,
            alternated=False,
            nch=1,
            fname='timetrace-test.h5',
        )
        wrapped = FBSData(data, 'timetrace-test.h5', id=7)
        self.assertEqual(node.execute(wrapped), [wrapped])
        self.assertIs(node._selected_data(), data)

    def test_bva_contours_stay_on_each_nodes_own_axes(self):
        class Bursts(list):
            def recompute_index_reduce(self, _ph_times):
                return self

        data = custom_nodes.Data(
            ph_times_m=[np.arange(14)],
            A_em=[np.ones(14, dtype=bool)],
            clk_p=1e-6,
            alternated=False,
            nch=1,
            fname='bva-test.h5',
        )
        data.E = [np.array([0.5])]
        data.mburst = [
            Bursts([SimpleNamespace(istart=0, istop=13)])
        ]
        data.get_ph_times = lambda ph_sel: np.arange(14)
        data.get_ph_mask = lambda ph_sel: np.ones(14, dtype=bool)
        plotted_data = SimpleNamespace(id=1, data=data)

        graph = BaseUtils.init_graph()
        first = graph.create_node('Plot.BVAPlotterNode')
        second = graph.create_node('Plot.BVAPlotterNode')
        self.assertEqual(len(first.input_ports()), 1)
        self.assertEqual(len(second.input_ports()), 1)
        first.data_to_plot = [plotted_data]
        second.data_to_plot = [plotted_data]

        with patch(
            'fretGUI.custom_nodes.custom_nodes.sns.kdeplot'
        ) as kdeplot:
            first._on_refresh_canvas()
            second._on_refresh_canvas()

        first_ax = kdeplot.call_args_list[0].kwargs['ax']
        second_ax = kdeplot.call_args_list[1].kwargs['ax']
        self.assertIsNot(first_ax, second_ax)
        self.assertIs(first_ax, first.plot_widget.figure.axes[0])
        self.assertIs(second_ax, second.plot_widget.figure.axes[0])

    def test_node_sidebar_groups_nodes_and_has_fixed_width(self):
        graph = BaseUtils.init_graph()
        run_button = QtWidgets.QPushButton('Run')
        auto_toggle = QtWidgets.QPushButton('Auto Run')
        progress_bar = ProgressBar2()
        sidebar = NodeSidebar(
            graph,
            run_button,
            auto_toggle,
            progress_bar,
        )

        self.assertEqual(sidebar.minimumWidth(), NodeSidebar.WIDTH)
        self.assertEqual(sidebar.maximumWidth(), NodeSidebar.WIDTH)
        sidebar.resize(NodeSidebar.WIDTH, 600)
        sidebar.collapse_button.setChecked(True)
        self.assertTrue(sidebar.node_container.isHidden())
        self.assertLess(sidebar.height(), 600)
        self.assertEqual(sidebar.width(), NodeSidebar.WIDTH)
        self.assertFalse(run_button.isHidden())
        self.assertFalse(auto_toggle.isHidden())
        self.assertFalse(sidebar.progress_container.isHidden())

        sidebar.collapse_button.setChecked(False)
        self.assertFalse(sidebar.node_container.isHidden())
        self.assertEqual(
            sidebar.maximumHeight(),
            NodeSidebar.MAX_WIDGET_SIZE,
        )
        self.assertEqual(sidebar.node_tree.indentation(), 6)
        self.assertEqual(
            sidebar.node_tree.verticalScrollMode(),
            QtWidgets.QAbstractItemView.ScrollPerPixel,
        )
        self.assertFalse(sidebar.node_tree.rootIsDecorated())
        self.assertEqual(
            sidebar.node_tree.selectionMode(),
            QtWidgets.QAbstractItemView.NoSelection,
        )

        categories = {
            sidebar.node_tree.topLevelItem(index).data(0, CATEGORY_ROLE):
            sidebar.node_tree.topLevelItem(index)
            for index in range(sidebar.node_tree.topLevelItemCount())
        }
        self.assertIn('Loaders', categories)
        self.assertEqual(categories['Loaders'].text(0), 'Data')
        self.assertIn('Analysis', categories)
        self.assertIn('Selectors', categories)
        self.assertIn('Plot', categories)
        self.assertNotIn('nodeGraphQt.nodes', categories)
        self.assertGreater(categories['Analysis'].childCount(), 0)

        for node_id, node_class in graph.node_factory.nodes.items():
            if node_id.startswith('nodeGraphQt.nodes.'):
                continue
            self.assertTrue(
                getattr(node_class, 'DESCRIPTION', '').strip(),
                '{} is missing DESCRIPTION'.format(node_id),
            )

        analysis_node = categories['Analysis'].child(0)
        analysis_node_id = analysis_node.data(0, NODE_TYPE_ROLE)
        description = graph.node_factory.nodes[
            analysis_node_id
        ].DESCRIPTION
        self.assertIn(description, analysis_node.toolTip(0))
        self.assertNotIn(analysis_node_id, analysis_node.toolTip(0))

        categories['Analysis'].setExpanded(False)
        self.assertFalse(categories['Analysis'].isExpanded())
        categories['Analysis'].setExpanded(True)
        self.assertTrue(categories['Analysis'].isExpanded())

    def test_node_sidebar_drag_uses_nodegraphqt_mime_data(self):
        graph = BaseUtils.init_graph()
        sidebar = NodeSidebar(
            graph,
            QtWidgets.QPushButton('Run'),
            QtWidgets.QPushButton('Auto Run'),
            ProgressBar2(),
        )
        tree = sidebar.node_tree
        analysis = next(
            tree.topLevelItem(index)
            for index in range(tree.topLevelItemCount())
            if tree.topLevelItem(index).data(0, CATEGORY_ROLE) == 'Analysis'
        )
        node_item = analysis.child(0)

        mime_data = tree.mimeData([node_item])
        payload = bytes(mime_data.data(MIME_TYPE)).decode()

        self.assertTrue(mime_data.hasFormat(MIME_TYPE))
        self.assertEqual(
            payload,
            'nodegraphqt::node:{}'.format(
                node_item.data(0, NODE_TYPE_ROLE)
            ),
        )

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

        path_id = path_widget.get_file_entries()[0][0]
        row_widget = path_widget.rowwidget_map[path_id]
        self.assertEqual(row_widget.del_button.size(), QtCore.QSize(25, 25))
        row_widget.on_button_click()
        QtCore.QCoreApplication.sendPostedEvents(
            None,
            QtCore.QEvent.DeferredDelete,
        )

        self.assertEqual(path_widget.get_file_entries(), [])
        self.assertNotIn(path_id, path_widget.rowwidget_map)
        self.assertEqual(node.execute(), [])

    def test_file_rows_cycle_colors_and_update_runtime_state(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Loaders.PhHDF5Node')
        path_widget = node.file_widget.path_widget
        path_widget.process_files(['/tmp/color-file.h5'])

        path_id, _, _, initial_color, _display_name = path_widget.get_file_entries()[0]
        color_cycle = matplotlib.rcParams[
            'axes.prop_cycle'
        ].by_key()['color']
        self.assertEqual(
            initial_color,
            QtGui.QColor(color_cycle[(path_id - 1) % len(color_cycle)]).name(),
        )

        row_widget = path_widget.rowwidget_map[path_id]
        row_widget.set_color('#12ab34')
        row_widget.color_changed.emit(row_widget.get_color())
        self.assertEqual(
            path_widget.get_file_entries()[0][3],
            '#12ab34',
        )
        self.assertEqual(row_widget.id_label.text(), '')

    def test_file_row_drag_changes_listed_order(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Loaders.PhHDF5Node')
        path_widget = node.file_widget.path_widget
        path_widget.process_files([
            '/tmp/first.h5',
            '/tmp/second.h5',
            '/tmp/third.h5',
        ])
        app.processEvents()
        rows = path_widget._ordered_rows()
        self.assertEqual(
            [row.get_text() for row in rows],
            ['/tmp/first.h5', '/tmp/second.h5', '/tmp/third.h5'],
        )
        third = rows[2]
        target_y = rows[0].geometry().center().y()
        path_widget.move_row_to_pointer(
            third,
            path_widget.mapToGlobal(QtCore.QPoint(10, target_y)),
        )
        path_widget.finish_row_drag()
        self.assertEqual(
            path_widget.get_paths(),
            ['/tmp/third.h5', '/tmp/first.h5', '/tmp/second.h5'],
        )

    def test_fbsdata_copy_preserves_file_color(self):
        original = FBSData(id=10001, color='#abcdef')
        copied = original.copy()

        self.assertEqual(copied.color, '#abcdef')
        copied.color = '#123456'
        self.assertEqual(original.color, '#abcdef')

    def test_plot_artist_keeps_file_color_and_uses_port_marker(self):
        figure = Figure()
        ax = figure.add_subplot()
        port1 = MagicMock()
        port1.name.return_value = 'port1'
        port2 = MagicMock()
        port2.name.return_value = 'port2'

        first_counts = custom_nodes._artist_counts(ax)
        first_line, = ax.plot([0, 1], [0, 1])
        custom_nodes._style_new_data_artists(
            ax,
            first_counts,
            '#336699',
            marker=custom_nodes._marker_for_port(port1),
            label='port1: file',
        )

        second_counts = custom_nodes._artist_counts(ax)
        second_line, = ax.plot([0, 1], [1, 2])
        custom_nodes._style_new_data_artists(
            ax,
            second_counts,
            '#336699',
            marker=custom_nodes._marker_for_port(port2),
            label='port2: file',
        )

        self.assertEqual(first_line.get_color(), '#336699')
        self.assertEqual(second_line.get_color(), '#336699')
        self.assertEqual(first_line.get_marker(), 'o')
        self.assertEqual(second_line.get_marker(), 's')
        self.assertEqual(first_line.get_label(), 'port1: file')
        self.assertEqual(second_line.get_label(), 'port2: file')

    def test_single_file_color_only_changes_primary_artist(self):
        figure = Figure()
        ax = figure.add_subplot()
        previous_counts = custom_nodes._artist_counts(ax)
        points = ax.scatter([0, 1], [1, 2], color='#000000')
        guide, = ax.plot([0, 1], [2, 3], color='#cc0000')

        custom_nodes._style_new_data_artists(
            ax,
            previous_counts,
            '#2468ac',
            primary_only=True,
        )

        self.assertEqual(
            mpl_colors.to_hex(points.get_facecolors()[0]),
            '#2468ac',
        )
        self.assertEqual(guide.get_color(), '#cc0000')

    def test_multifile_legend_groups_ports_and_uses_file_ids(self):
        port1 = MagicMock()
        port1.name.return_value = 'port1'
        port2 = MagicMock()
        port2.name.return_value = 'port2'
        first = MagicMock()
        first.id = 3
        first.data.name = 'first.h5'
        first.data.num_bursts = [12]

        self.assertEqual(
            custom_nodes._multifile_legend_label(
                first, port1, show_port=False
            ),
            '3: first.h5, N 12',
        )
        self.assertEqual(
            custom_nodes._multifile_legend_label(
                first, port2, show_port=True
            ),
            'port2: 3: first.h5, N 12',
        )

        entries = [(port2, 1), (port1, 5), (port1, 2)]
        entries.sort(
            key=lambda item: (
                custom_nodes._port_number(item[0]),
                item[1],
            )
        )
        self.assertEqual(
            [(port.name(), file_id) for port, file_id in entries],
            [('port1', 2), ('port1', 5), ('port2', 1)],
        )
        self.assertFalse(custom_nodes.BGFitPlotterNode.USE_FILE_COLOR)
        self.assertFalse(custom_nodes.BGTimeLinePlotterNode.USE_FILE_COLOR)
        self.assertFalse(
            custom_nodes.HistBurstSizeAllPlotterNode.USE_FILE_COLOR
        )

    def test_plot_buffers_accept_only_completed_generation(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Plot.ScatterRateDaPlotterNode')
        plotted_ids = []
        node._on_refresh_canvas = lambda: plotted_ids.append(
            [data.id for data in node.data_to_plot]
        )

        node._on_run_started(501)
        node.execute(FBSData(id=1, run_id=501))
        node.execute(FBSData(id=2, run_id=501))
        node._on_run_discarded(501)
        self.assertEqual(plotted_ids, [])

        node._on_run_started(502)
        node.execute(FBSData(id=3, run_id=502))
        node._on_run_completed(502)

        self.assertEqual(plotted_ids, [[3]])
        self.assertEqual(node.data_to_plot, [])

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

    def test_file_combobox_uses_file_colors(self):
        widget = ComboBoxWidget()
        widget.setItems(['one.h5', 'two.h5'], ['#336699', '#ffcc00'])
        combo = widget.combobox

        first = qcolor_from_item_data(
            combo.itemData(0, QtCore.Qt.BackgroundRole)
        )
        second = qcolor_from_item_data(
            combo.itemData(1, QtCore.Qt.BackgroundRole)
        )
        self.assertEqual(first.name(), '#336699')
        self.assertEqual(second.name(), '#ffcc00')
        self.assertIn('#336699', combo.styleSheet())

        combo.setCurrentIndex(1)
        self.assertIn('#ffcc00', combo.styleSheet())

        graph = BaseUtils.init_graph()
        node = graph.create_node('Plot.ScatterRateDaPlotterNode')
        node.items_to_plot.set_items(
            ['port1:1, first.h5', 'port1:2, second.h5'],
            ['#112233', '#aabbcc'],
        )
        plot_combo = node.items_to_plot.get_custom_widget().combobox
        self.assertEqual(
            qcolor_from_item_data(
                plot_combo.itemData(0, QtCore.Qt.BackgroundRole)
            ).name(),
            '#112233',
        )
        self.assertIn('#112233', plot_combo.styleSheet())

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
        self.assertFalse(first_plot.keep_view_check.isChecked())
        self.assertFalse(second_plot.keep_view_check.isChecked())

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
        self.assertNotEqual(replotted_ax.get_xlim(), (2.0, 4.0))
        self.assertNotEqual(replotted_ax.get_ylim(), (6.0, 9.0))

        first_plot.keep_view_check.setChecked(True)
        replotted_ax.set_xlim(2, 4)
        replotted_ax.set_ylim(6, 9)
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

    def test_unchecking_keep_view_requests_recalculation(self):
        graph = BaseUtils.init_graph()
        node = graph.create_node('Plot.ScatterRateDaPlotterNode')
        keep_view = node.get_widget('plot_widget').get_custom_widget().keep_view_check
        keep_view.setChecked(True)
        spy = QSignalSpy(ThreadSignalManager().run_btn_clicked)
        keep_view.setChecked(False)
        self.assertEqual(spy.count(), 1)
        keep_view.setChecked(True)
        self.assertEqual(spy.count(), 1)

    def test_matplotlib_zoom_button_shows_when_checked(self):
        previous_sheet = app.styleSheet()
        app.setStyleSheet(build_theme_stylesheet('light'))
        try:
            graph = BaseUtils.init_graph()
            plot = graph.create_node(
                'Plot.ScatterRateDaPlotterNode'
            ).get_widget('plot_widget').get_custom_widget()
            toolbar = plot.toolbar
            zoom = toolbar._actions['zoom']
            button = toolbar.widgetForAction(zoom)
            toolbar.resize(420, 48)
            toolbar.show()
            app.processEvents()

            def corner_color():
                image = button.grab().toImage()
                return image.pixelColor(2, 2)

            zoom.setChecked(False)
            app.processEvents()
            off = corner_color()
            zoom.setChecked(True)
            app.processEvents()
            on = corner_color()
            self.assertNotEqual(off.rgb(), on.rgb())
            self.assertGreater(on.blue(), on.red())
            self.assertGreater(on.blue(), 180)
        finally:
            app.setStyleSheet(previous_sheet)

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
                mpl_colors.to_hex(ax.get_facecolor()),
                '#303030',
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

    def test_control_free_histograms_keep_resize_handle_above_canvas(self):
        graph = BaseUtils.init_graph()
        node_types = (
            'Plot.HistBurstBrightnessPlotterNode',
            'Plot.HistBurstSBRPlotterNode',
            'Plot.HistBurstPhratePlotterNode',
        )

        for node_type in node_types:
            with self.subTest(node_type=node_type):
                node = graph.create_node(node_type)
                app.processEvents()
                view = node.view
                plot_proxy = node.get_widget('plot_widget')

                self.assertGreater(
                    view._resize_handle.zValue(),
                    plot_proxy.zValue(),
                )
                self.assertEqual(
                    view._resize_handle.pos(),
                    QtCore.QPointF(
                        view._width - view.HANDLE_SIZE,
                        view._height - view.HANDLE_SIZE,
                    ),
                )
                old_size = (view._width, view._height)
                view._begin_resize(QtCore.QPointF(0, 0))
                view._resize_from_scene_pos(QtCore.QPointF(20, 30))
                view._end_resize()

                self.assertEqual(view._width, old_size[0] + 20)
                self.assertEqual(view._height, old_size[1] + 30)
                self.assertFalse(view._resizing)

    def test_join_data_uses_checked_rows_in_list_order(self):
        from collections import deque

        RunCoordinator().reset_for_tests()
        graph = BaseUtils.init_graph()
        node = graph.create_node('Loaders.JoinDataNode')
        node.set_property('result_name', 'Combined', push_undo=False)

        def measurement(name, order, color):
            item = FBSData(data=SimpleNamespace(name=name), path=f'{name}.hdf5', color=color)
            item.display_name = name
            item.source_order = order
            item.run_id = 7
            return item

        alpha = measurement('Alpha', 0, '#aa0000')
        beta = measurement('Beta', 1, '#00aa00')
        gamma = measurement('Gamma', 2, '#0000aa')

        class Child:
            def __init__(self):
                self.received = None

            def execute(self, data):
                self.received = data
                return []

            def iter_children_nodes(self):
                return []

        child = Child()
        calls = []

        def fake_join(d_list, gap=0):
            calls.append((list(d_list), gap))
            return SimpleNamespace()

        self.assertEqual(node.execute(gamma), [])
        self.assertEqual(node.dataset_list.keys(), [])
        node.execute(alpha)
        node.execute(beta)

        with patch('fretbursts.burstlib_ext.join_data', side_effect=fake_join):
            with patch.object(node, 'iter_children_nodes', return_value=[child]):
                node._on_run_completed(7)
                self.assertEqual(
                    node.dataset_list.labels(),
                    ['Alpha', 'Beta', 'Gamma'],
                )
                self.assertTrue(node.dataset_list.is_checked(beta.id))
                self.assertIn('#aa0000', node.dataset_list._rows[alpha.id]._swatch.styleSheet())
                self.assertEqual(
                    [item.name for item in calls[0][0]],
                    ['Alpha', 'Beta', 'Gamma'],
                )
                self.assertEqual(calls[0][1], 0.0)

                node.dataset_list.set_checked(beta.id, False)
                node.dataset_list.move_key_to_index(gamma.id, 0)
                node.gap_spinbox.set_value(1.5)
                node._join_checked()

                joined, gap = calls[-1]
                self.assertEqual([item.name for item in joined], ['Gamma', 'Alpha'])
                self.assertEqual(gap, 1.5)
                self.assertEqual(
                    node.dataset_list.keys(),
                    [gamma.id, alpha.id, beta.id],
                )
                self.assertFalse(node.dataset_list.is_checked(beta.id))
                self.assertEqual(child.received.display_name, 'Combined')
                self.assertEqual(child.received.source_order, 0)

                delta = measurement('Delta', 3, '#111111')
                for item in (gamma, alpha, beta, delta):
                    item.run_id = 8
                    node.execute(item)
                node._on_run_completed(8)
                self.assertEqual(
                    node.dataset_list.keys(),
                    [gamma.id, alpha.id, beta.id, delta.id],
                )
                self.assertFalse(node.dataset_list.is_checked(beta.id))

                alpha.run_id = 9
                node.execute(alpha)
                node._on_run_completed(9)
                self.assertEqual(node.dataset_list.keys(), [alpha.id])

        class Halt:
            halt_downstream = True

            def execute(self, data):
                return []

        class Recorder:
            def __init__(self):
                self.seen = []

            def execute(self, data):
                self.seen.append(data)
                return [data]

        recorder = Recorder()
        context = RunContext(55)
        worker = NodeWorker(
            Halt(),
            FBSData(data=object(), path='x'),
            deque([Halt(), recorder]),
            need_fill=False,
            context=context,
        )
        worker.run()
        self.assertEqual(recorder.seen, [])

    def test_merge_photons_concatenates_checked_streams_in_order(self):
        import fretbursts

        from fretGUI.photon_merge import PhotonMergeError, merge_smfret_streams

        RunCoordinator().reset_for_tests()
        graph = BaseUtils.init_graph()
        node = graph.create_node('Loaders.MergePhotonsNode')
        node.set_property('result_name', 'Combined', push_undo=False)
        self.assertEqual(node.input_ports()[0].color[:3], (255, 0, 0))
        self.assertEqual(node.output_ports()[0].color[:3], (255, 0, 0))

        def stream(name, order, times, mask, clk=12.5e-9):
            data = fretbursts.Data(
                ph_times_m=[np.asarray(times, dtype='int64')],
                A_em=[np.asarray(mask, dtype=bool)],
                clk_p=clk,
                nch=1,
                alternated=False,
                meas_type='smFRET',
            )
            item = FBSData(data, path=f'{name}.hdf5')
            item.display_name = name
            item.source_order = order
            item.run_id = 3
            return item

        alpha = stream('Alpha', 0, [10, 20, 30], [False, True, False])
        beta = stream('Beta', 1, [1, 2], [True, False])
        gamma = stream('Gamma', 2, [5, 9], [False, True])

        class Child:
            def __init__(self):
                self.received = None

            def execute(self, data):
                self.received = data
                return []

            def iter_children_nodes(self):
                return []

        child = Child()
        node.execute(gamma)
        node.execute(alpha)
        node.execute(beta)
        with patch.object(node, 'iter_children_nodes', return_value=[child]):
            node._on_run_completed(3)
            node.dataset_list.set_checked(beta.id, False)
            node.dataset_list.move_key_to_index(gamma.id, 0)
            node.gap_spinbox.set_value(0.1)
            node._join_checked()

        merged = child.received.data
        self.assertIn('ph_times_m', merged)
        self.assertEqual(child.received.display_name, 'Combined')
        self.assertEqual(child.received.source_order, 0)
        self.assertTrue(np.array_equal(
            merged.ph_times_m[0],
            np.array([5, 9, 8000010, 8000020, 8000030], dtype='int64'),
        ))
        self.assertTrue(np.array_equal(
            merged.A_em[0],
            np.array([False, True, False, True, False]),
        ))

        mismatched = graph.create_node('Loaders.MergePhotonsNode')
        slow = stream('Slow', 0, [1, 2, 3], [False, True, False], clk=50e-9)
        fast = stream('Fast', 1, [4, 5], [True, False], clk=12.5e-9)
        slow.run_id = 4
        fast.run_id = 4
        missed = Child()
        mismatched.execute(slow)
        mismatched.execute(fast)
        with patch.object(mismatched, 'iter_children_nodes', return_value=[missed]):
            mismatched._on_run_completed(4)
        self.assertIsNone(missed.received)

        with_nano = {
            'ph_times_m': [np.array([1, 2, 3], dtype='int64')],
            'A_em': [np.array([False, True, False])],
            'nanotimes': [np.array([4, 5, 6])],
            'clk_p': 12.5e-9,
            'nch': 1,
            'meas_type': 'smFRET',
        }
        with_nano_too = {
            'ph_times_m': [np.array([8, 9], dtype='int64')],
            'A_em': [np.array([True, False])],
            'nanotimes': [np.array([1, 2])],
            'clk_p': 12.5e-9,
            'nch': 1,
            'meas_type': 'smFRET',
        }
        combined = merge_smfret_streams([with_nano, with_nano_too], gap=0)
        self.assertTrue(np.array_equal(
            combined.nanotimes[0],
            np.array([4, 5, 6, 1, 2]),
        ))
        plain = {
            'ph_times_m': [np.array([1, 2], dtype='int64')],
            'A_em': [np.array([False, True])],
            'clk_p': 12.5e-9,
            'nch': 1,
            'meas_type': 'smFRET',
        }
        with self.assertRaises(PhotonMergeError):
            merge_smfret_streams([with_nano, plain], gap=0)

    def test_measurement_list_grows_and_drag_targets_the_list(self):
        from fretGUI.custom_widgets.dataset_list import measurement_list_for

        graph = BaseUtils.init_graph()
        node = graph.create_node('Loaders.JoinDataNode')
        before = node.view._height
        first = {
            'key': 1,
            'label': 'L2-dCas-NS_1to500.001-extra-long-measurement-name',
            'color': '#3366cc',
            'tooltip': r'C:\data\L2-dCas-NS_1to500.001',
        }
        second = {
            'key': 2,
            'label': 'L2-dCas-NS_1to500.002',
            'color': '#ff8800',
            'tooltip': r'C:\data\L2-dCas-NS_1to500.002',
        }
        node.dataset_list.sync([first])
        one_row = node.view._height
        node.dataset_list.sync([first, second])
        two_rows = node.view._height
        self.assertGreater(one_row, before)
        self.assertGreaterEqual(two_rows - one_row, 30)
        node.dataset_list.sync([first])
        self.assertEqual(node.view._height, one_row)
        node.dataset_list.sync([])
        self.assertEqual(node.view._height, before)
        node.dataset_list.sync([first, second])
        self.assertEqual(node.view._height, two_rows)
        row = node.dataset_list._rows[1]
        self.assertIs(measurement_list_for(row), node.dataset_list)
        self.assertEqual(
            row.label(),
            'L2-dCas-NS_1to500.001-extra-long-measurement-name',
        )
        self.assertTrue(row._label.text().endswith('\u2026'))
        self.assertIn(r'C:\data\L2-dCas-NS_1to500.001', row._label.toolTip())

        loader = graph.create_node('Loaders.PhHDF5Node')
        join = graph.create_node('Loaders.MergePhotonsNode')
        self.assertAlmostEqual(join.view._width, loader.view._width, delta=8)
        join.dataset_list.sync([
            {
                'key': 1,
                'label': 'a-very-long-measurement-name.h5',
                'color': '#3366cc',
                'tooltip': r'C:\data\long.h5',
            },
        ])
        self.assertAlmostEqual(join.view._width, loader.view._width, delta=8)

    def test_join_clears_rows_when_the_run_has_no_measurements(self):
        RunCoordinator().reset_for_tests()
        graph = BaseUtils.init_graph()
        node = graph.create_node('Loaders.MergePhotonsNode')
        item = FBSData(
            data=SimpleNamespace(name='Alpha'),
            path='alpha.hdf5',
        )
        item.display_name = 'Alpha'
        item.run_id = 1
        node._on_run_started(1)
        node.execute(item)
        node._on_run_completed(1)
        self.assertEqual(node.dataset_list.labels(), ['Alpha'])

        node._on_run_completed(99)
        self.assertEqual(node.dataset_list.labels(), ['Alpha'])

        node._on_run_started(2)
        node.execute(None)
        node._on_run_completed(2)
        self.assertEqual(node.dataset_list.keys(), [])
        self.assertEqual(node._by_key, {})

    def test_join_and_export_stay_on_auto_run(self):
        from fretGUI.singletons import ThreadSignalManager

        graph = BaseUtils.init_graph()
        join = graph.create_node('Loaders.MergePhotonsNode')
        export = graph.create_node('Loaders.ExportPhotonHdf5Node')
        join.unwire_wrappers()
        export.unwire_wrappers()
        spy = QSignalSpy(ThreadSignalManager().run_btn_clicked)

        join.dataset_widget.debounced_signal.emit()
        export.export_panel.debounced_signal.emit()
        join.get_widget('result_name').on_value_changed()

        self.assertGreaterEqual(spy.count(), 3)
        self.assertTrue(join.event_debouncer.isactive)
        self.assertTrue(export.event_debouncer.isactive)

    def test_export_file_name_uses_display_name(self):
        import os
        import tempfile

        graph = BaseUtils.init_graph()
        node = graph.create_node('Loaders.ExportPhotonHdf5Node')
        renamed = FBSData(data={}, path=r'C:\data\original.h5')
        renamed.display_name = 'renamed'
        untouched = FBSData(data={}, path=r'C:\data\original.h5')
        node._datasets = [renamed, untouched]

        with tempfile.TemporaryDirectory() as folder:
            node.export_panel.set_value(folder)
            with patch(
                'fretGUI.photon_hdf5_export.data_dict_from_fretbursts',
                return_value={'description': 'x'},
            ):
                with patch('phconvert.hdf5.save_photon_hdf5') as save:
                    def remember_busy(*_args, **_kwargs):
                        self.assertEqual(
                            node.export_panel.folder_widget.status.text(),
                            'Exporting…',
                        )
                        self.assertFalse(
                            node.export_panel.folder_widget.export_button.isEnabled()
                        )

                    save.side_effect = remember_busy
                    node.export_datasets()

        names = [
            os.path.basename(call.kwargs['h5_fname'])
            for call in save.call_args_list
        ]
        self.assertEqual(names, ['renamed.hdf5', 'original.hdf5'])
        self.assertEqual(
            node.export_panel.folder_widget.status.text(),
            'Finished. Wrote 2 files.',
        )
        self.assertTrue(node.export_panel.folder_widget.export_button.isEnabled())

    def test_photon_hdf5_export_matches_measurement_kind(self):
        import os
        import tempfile

        import tables

        from fretGUI.photon_hdf5_export import (
            PhotonHdf5ExportError,
            data_dict_from_fretbursts,
        )
        import phconvert.hdf5 as photon_hdf5

        with self.assertRaises(PhotonHdf5ExportError):
            data_dict_from_fretbursts({'nch': 1, 'meas_type': 'smFRET'})

        smfret = {
            'ph_times_m': [np.array([10, 20, 30, 40], dtype='int64')],
            'A_em': [np.array([False, True, False, True])],
            'clk_p': 12.5e-9,
            'nch': 1,
            'meas_type': 'smFRET',
            'description': 'single spot',
            'setup': {'excitation_wavelengths': np.array([532e-9])},
            'sample': {'buffer_name': 'TE'},
        }
        usalex = {
            'ph_times_t': [np.arange(8, dtype='int64')],
            'det_t': [np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype='uint8')],
            'clk_p': 12.5e-9,
            'nch': 1,
            'ALEX': True,
            'meas_type': 'smFRET-usALEX',
            'alex_period': 4000,
            'offset': 700,
            'D_ON': (2850, 580),
            'A_ON': (900, 2580),
            'det_donor_accept': [(np.array([0]), np.array([1]))],
        }
        pax = dict(usalex)
        pax['meas_type'] = 'PAX'
        pax['ALEX'] = True
        nsalex = {
            'ph_times_m': [np.arange(8, dtype='int64')],
            'A_em': [np.array([False, True, False, True, False, True, False, True])],
            'nanotimes': [np.array([10, 100, 20, 200, 30, 300, 40, 400], dtype='int64')],
            'clk_p': 12.5e-9,
            'nch': 1,
            'ALEX': True,
            'lifetime': True,
            'meas_type': 'smFRET-nsALEX',
            'laser_repetition_rate': 8e7,
            'D_ON': (10, 1500),
            'A_ON': (2000, 3500),
            'nanotimes_params': [{
                'tcspc_unit': 1e-12,
                'tcspc_num_bins': 4096,
            }],
        }

        smfret_dict = data_dict_from_fretbursts(smfret)
        usalex_dict = data_dict_from_fretbursts(usalex)
        pax_dict = data_dict_from_fretbursts(pax)
        nsalex_dict = data_dict_from_fretbursts(nsalex)
        self.assertEqual(
            smfret_dict['photon_data']['measurement_specs']['measurement_type'],
            'smFRET',
        )
        self.assertEqual(
            float(smfret_dict['setup']['excitation_wavelengths'][0]),
            532e-9,
        )
        self.assertEqual(smfret_dict['sample']['buffer_name'], 'TE')
        self.assertEqual(
            usalex_dict['photon_data']['measurement_specs']['measurement_type'],
            'smFRET-usALEX',
        )
        self.assertEqual(
            nsalex_dict['photon_data']['measurement_specs']['measurement_type'],
            'smFRET-nsALEX',
        )
        self.assertIn('nanotimes', nsalex_dict['photon_data'])
        self.assertEqual(pax_dict['photon_data']['measurement_specs']['measurement_type'], 'generic')
        self.assertEqual(
            tuple(bool(value) for value in pax_dict['setup']['excitation_alternated']),
            (False, True),
        )

        spots = dict(smfret)
        spots['nch'] = 2
        spots['ph_times_m'] = [
            np.array([1, 2, 3], dtype='int64'),
            np.array([4, 5, 6], dtype='int64'),
        ]
        spots['A_em'] = [
            np.array([False, True, False]),
            np.array([True, False, True]),
        ]
        multi = data_dict_from_fretbursts(spots)
        self.assertIn('photon_data0', multi)
        self.assertIn('photon_data1', multi)
        self.assertEqual(multi['setup']['num_spots'], 2)

        with tempfile.TemporaryDirectory() as folder:
            for name, payload in (
                ('smfret.hdf5', smfret_dict),
                ('usalex.hdf5', usalex_dict),
                ('pax.hdf5', pax_dict),
                ('nsalex.hdf5', nsalex_dict),
            ):
                path = os.path.join(folder, name)
                photon_hdf5.save_photon_hdf5(payload, h5_fname=path, overwrite=True)
                with tables.open_file(path) as handle:
                    stored = handle.root.photon_data.measurement_specs.measurement_type.read()
                if isinstance(stored, bytes):
                    stored = stored.decode()
                self.assertEqual(stored, payload['photon_data']['measurement_specs']['measurement_type'])
    
        
        
        
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
        context = RunContext(101)
        worker = NodeWorker(lsm_node, context=context)
        spy = QSignalSpy(ThreadSignalManager().thread_started)
        drained_spy = QSignalSpy(context.drained)
        progress_bar = ProgressBar2()
        ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
        ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
        ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
        worker.run()
        self.assertTrue(
            QtCore.QThreadPool.globalInstance().waitForDone(10000)
        )
        app.processEvents()
        self.assertEqual(drained_spy.count(), 1)
        self.assertEqual(spy.count(), 2, "it should be 2 emitions of thread_started signal")
        
    def test_worker_thread_finished_signals(self):
        ThreadSignalManager().disconnect()
        graph = self.__load_template("test_signals.json")
        lsm_node = graph.get_node_by_name('Confocor2 RAW')
        context = RunContext(102)
        worker = NodeWorker(lsm_node, context=context)
        spy = QSignalSpy(ThreadSignalManager().thread_finished)
        drained_spy = QSignalSpy(context.drained)
        progress_bar = ProgressBar2()
        ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
        ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
        ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
        worker.run()
        self.assertTrue(
            QtCore.QThreadPool.globalInstance().waitForDone(10000)
        )
        app.processEvents()
        self.assertEqual(drained_spy.count(), 1)
        self.assertEqual(spy.count(), 2, "it should be 2 emitions of thread_finished signal")
        
    def test_worker_all_thread_finished(self):
        ThreadSignalManager().disconnect()
        graph = self.__load_template("test_signals.json")
        progress_bar = ProgressBar2()
        ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
        ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
        ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
        lsm_node = graph.get_node_by_name('Confocor2 RAW')
        context = RunContext(103)
        worker = NodeWorker(lsm_node, context=context)
        spy = QSignalSpy(context.drained)
        worker.run()
        self.assertTrue(
            QtCore.QThreadPool.globalInstance().waitForDone(10000)
        )
        app.processEvents()
        self.assertEqual(spy.count(), 1, "run should drain exactly once")

    def test_run_coordinator_coalesces_to_latest_request(self):
        coordinator = RunCoordinator()
        coordinator.reset_for_tests()
        started = QSignalSpy(coordinator.run_started)
        completed = QSignalSpy(coordinator.run_completed)
        discarded = QSignalSpy(coordinator.run_discarded)

        first = coordinator.request_run()
        first.register_worker('first-worker')
        coordinator.request_run()
        coordinator.request_run()
        self.assertTrue(first.obsolete)

        first.worker_finished('first-worker')
        app.processEvents()

        self.assertEqual(discarded.count(), 1)
        self.assertEqual(started.count(), 2)
        second = coordinator.active_context
        self.assertIsNotNone(second)
        second.register_worker('second-worker')
        second.worker_finished('second-worker')
        app.processEvents()

        self.assertEqual(completed.count(), 1)
        self.assertFalse(coordinator.is_busy)
        coordinator.reset_for_tests()

    def test_run_context_waits_for_every_branch(self):
        context = RunContext(104)
        drained = QSignalSpy(context.drained)
        context.register_worker('root')
        context.register_worker('branch')

        context.worker_finished('root')
        self.assertEqual(drained.count(), 0)
        context.worker_finished('branch')
        app.processEvents()

        self.assertEqual(drained.count(), 1)

    def test_invalidated_run_does_not_write_analysis_cache(self):
        coordinator = RunCoordinator()
        coordinator.reset_for_tests()
        context = coordinator.request_run()
        context.register_worker('cache-worker')
        data = FBSData(id=20001, run_id=context.run_id)
        cache = FBSDataCash()
        size_before = cache.size

        class FakeNode:
            def widgets(self):
                return {}

        def calculate(node, fbsdata):
            return [fbsdata]

        coordinator.invalidate_active()
        result = cache.fbscash(calculate)(FakeNode(), data)

        self.assertEqual(result, [data])
        self.assertEqual(cache.size, size_before)
        context.worker_finished('cache-worker')
        app.processEvents()
        coordinator.reset_for_tests()

    def test_worker_error_still_drains_run_context(self):
        class ExplodingNode:
            def iter_children_nodes(self):
                return []

            def execute(self, data):
                raise RuntimeError("expected test failure")

        context = RunContext(105)
        worker = NodeWorker(ExplodingNode(), context=context)
        drained = QSignalSpy(context.drained)

        with self.assertRaisesRegex(RuntimeError, "expected test failure"):
            worker.run()

        app.processEvents()
        self.assertTrue(context.obsolete)
        self.assertEqual(drained.count(), 1)
        
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