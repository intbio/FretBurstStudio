import custom_nodes.custom_nodes as custom_nodes
import graph_engene
from custom_widgets.toogle_widget import IconToggleButton
import sys,os
from singletons import ThreadSignalManager

from custom_widgets.progressbar_widget import ProgressBar
from custom_nodes.custom_nodes import PhHDF5Node
from node_workers import NodeWorker

import signal
from pathlib import Path
from Qt import QtWidgets, QtCore, QtGui
from Qt.QtCore import QThreadPool
from NodeGraphQt import NodeGraph, NodesPaletteWidget,constants
from NodeGraphQt import PropertiesBinWidget




BASE_PATH = Path(__file__).parent.resolve()


def on_run_btn_clicked(graph, btn):
    engene = graph_engene.GraphEngene(graph)
    roots = engene.find_root_nodes()
    pool = QThreadPool.globalInstance()
    for root_node in roots:
        new_worker = NodeWorker(root_node)
        pool.start(new_worker)
            
        
         
def on_toogle_clicked(graph, toggle_btn):
    engene = graph_engene.GraphEngene(graph)
    toggle_state = toggle_btn.text()
    if toggle_state == 'static':
        print('static')
        engene.make_nodes_static()
    elif toggle_state == 'automatic':
        print('auto')
        engene.make_nodes_dinamic()
    
    
                
           
def main():
    # handle SIGINT to make the app terminate on CTRL+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    

    app = QtWidgets.QApplication(sys.argv)
    

    # create graph controller.
    graph = NodeGraph()  
    graph.set_background_color(240, 240, 240)
    graph.set_grid_color(210, 210, 210)
    
    
    graph_widget = graph.widget 
    
    main_layout = QtWidgets.QVBoxLayout(graph_widget)
    main_layout.setContentsMargins(2, 2, 2, 2)
    
    
    top_layout = QtWidgets.QHBoxLayout()
    top_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
    
    # set up context menu for the node graph.
    hotkey_path = Path(BASE_PATH, 'hotkeys', 'hotkeys.json')
    graph.set_context_menu_from_file(hotkey_path, 'graph')
    
    ### styling
    # change the background color of the viewport
    #viewer = graph.viewer()
    #viewer.set_background_color(240, 240, 240)   # light grey

    ## change grid color and spacing if you want
    #viewer.set_grid_color(200, 200, 200)
    #viewer.set_grid_size(25)
    
    # registered example nodes.
    graph.register_nodes(
        [
            custom_nodes.PhHDF5Node,    
            custom_nodes.LSM510Node,     
            custom_nodes.AlexNode,
            custom_nodes.CalcBGNode,
            custom_nodes.BurstSearchNodeRate,
            custom_nodes.BurstSearchNodeFromBG,
            custom_nodes.BurstSelectorNode, 
            custom_nodes.BGPlotterNode,
            custom_nodes.EHistPlotterNode
        ]
    )
       
    
    
    run_button = QtWidgets.QPushButton("Run", parent=graph_widget)
    run_button.setFixedSize(50, 50)    
    run_button.clicked.connect(lambda: on_run_btn_clicked(graph, run_button))
    run_button.clicked.connect(ThreadSignalManager().run_btn_clicked.emit)
    
    toggle_btn = IconToggleButton(parent=graph_widget)
    toggle_btn.toggled.connect(lambda: on_toogle_clicked(graph, toggle_btn))
    
    progress_bar = ProgressBar(parent=graph_widget)
    ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
    ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
    ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
    progress_bar.block_ui.connect(lambda: run_button.setDisabled(True))
    progress_bar.release_ui.connect(lambda: run_button.setDisabled(False))
    # ThreadSignalManager().calculation_begin.connect()
    # ThreadSignalManager().calculation_finished.connect(progress_bar.on_calculation_finished)
    # ThreadSignalManager().calculation_finished.connect(lambda: run_button.setDisabled(False))
    # ThreadSignalManager().calculation_processed.connect(progress_bar.on_calculation_processed)
    progress_bar.show()

    
    
    top_layout.addWidget(run_button)
    top_layout.addWidget(toggle_btn)
    top_layout.addWidget(progress_bar)
    main_layout.addLayout(top_layout)
    run_button.show()
    
    
    graph_widget.resize(1100, 800)
    graph_widget.setWindowTitle("FretBurstsStudio")
    graph_widget.show()  
    
    
    file_node = graph.create_node(
        'Loaders.PhHDF5Node')
    file_node.set_disabled(False)
    
    # photon_node = graph.create_node(
    #     'nodes.custom.PhotonNode', text_color='#feab20')
    # photon_node.set_disabled(False)
    
    alex_node = graph.create_node(
        'Analysis.AlexNode')
    alex_node.set_disabled(False)
    
    calc_bgnode = graph.create_node(
        'Analysis.CalcBGNode')
    calc_bgnode.set_disabled(False)
    
    search_node = graph.create_node(
        'Analysis.BurstSearchNodeFromBG')
    search_node.set_disabled(False)
    
    plot_node = graph.create_node(
        'Plot.BGPlotterNode')
    plot_node.set_disabled(False)
    

    
    file_node.set_output(0, alex_node.input(0))
    # photon_node.set_output(0, alex_node.input(0))
    alex_node.set_output(0, calc_bgnode.input(0))
    calc_bgnode.set_output(0, search_node.input(0))
    search_node.set_output(0, plot_node.input(0))
    
    
    graph.auto_layout_nodes()
    graph.clear_selection()
    graph.fit_to_selection()
        

    properties_bin = PropertiesBinWidget(node_graph=graph, parent=graph_widget)
    properties_bin.setWindowFlags(QtCore.Qt.Tool)
    
    
    # nodes_tree = NodesTreeWidget(node_graph=graph)
    # nodes_tree.set_category_label('nodeGraphQt.nodes', 'Builtin Nodes')
    # nodes_tree.set_category_label('nodes.custom.ports', 'Custom Port Nodes')
    # nodes_tree.set_category_label('nodes.widget', 'Widget Nodes')
    # nodes_tree.set_category_label('nodes.basic', 'Basic Nodes')
    # nodes_tree.set_category_label('nodes.group', 'Group Nodes')
    # nodes_tree.show()

    
    
    nodes_palette = NodesPaletteWidget(node_graph=graph)
    nodes_palette.set_category_label('nodeGraphQt.nodes', 'Builtin Nodes')
    nodes_palette.set_category_label('nodes.custom.ports', 'Custom Port Nodes')
    nodes_palette.set_category_label('nodes.widget', 'Widget Nodes')
    nodes_palette.set_category_label('nodes.basic', 'Basic Nodes')
    nodes_palette.set_category_label('nodes.group', 'Group Nodes')
    
        #moving builtin to the last
    tabs = nodes_palette.tab_widget()
    w = tabs.widget(0)
    icon = tabs.tabIcon(0)
    text = tabs.tabText(0)
    tabs.removeTab(0)
    tabs.addTab(w, icon, text)
    
    sidebar_layout = QtWidgets.QVBoxLayout()
    sidebar_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
    sidebar_layout.setSpacing(0)  # Remove spacing
    sidebar_layout.addStretch()
    sidebar_layout.addWidget(nodes_palette)
    sidebar_widget = QtWidgets.QWidget()
    sidebar_widget.setLayout(sidebar_layout)
    sidebar_widget.setFixedSize(500, 200)
    main_layout.addWidget(sidebar_widget)
    
    app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI';
            font-size: 10pt;
        }
        QTabWidget::pane {
            border: 0px;
        }
        QScrollBar:vertical {
            width: 8px;
            margin: 0;
        }
    """)
        
        
    app.exec()

    

if __name__ == '__main__':
    main()
    

    