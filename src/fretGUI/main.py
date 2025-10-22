import custom_nodes.custom_nodes as custom_nodes
import graph_engene
from custom_widgets.toogle_widget import IconToggleButton
import sys
from signal_manager import SignalManager

from custom_widgets.progressbar_widget import ProgressBar
import signal
from pathlib import Path
from Qt import QtWidgets, QtCore
from NodeGraphQt import NodeGraph, NodesPaletteWidget
from NodeGraphQt import PropertiesBinWidget



BASE_PATH = Path(__file__).parent.resolve()


def on_run_btn_clicked(graph, btn):
    engene = graph_engene.GraphEngene(graph)
    roots = engene.find_root_nodes()
    for root_node in roots:
            root_node.update_nodes_and_pbar()
            SignalManager().calculation_finished.emit()
        
         
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
    graph_widget = graph.widget 
    
    main_layout = QtWidgets.QVBoxLayout(graph_widget)
    main_layout.setContentsMargins(2, 2, 2, 2)
    
    
    top_layout = QtWidgets.QHBoxLayout()
    top_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
    
    # set up context menu for the node graph.
    hotkey_path = Path(BASE_PATH, 'hotkeys', 'hotkeys.json')
    graph.set_context_menu_from_file(hotkey_path, 'graph')
    
    # registered example nodes.
    graph.register_nodes(
        [
            custom_nodes.FileNode,    
            custom_nodes.PhotonNode,     
            custom_nodes.AlexNode,
            custom_nodes.CalcBGNode,
            custom_nodes.BurstSearchNodde,
            custom_nodes.BurstSelectorNode, 
            custom_nodes.BGPlotterNode
        ]
    )
       
    
    
    run_button = QtWidgets.QPushButton("Run", parent=graph_widget)
    run_button.setFixedSize(50, 50)    
    run_button.clicked.connect(lambda: on_run_btn_clicked(graph, run_button))
    
    toggle_btn = IconToggleButton(parent=graph_widget)
    toggle_btn.toggled.connect(lambda: on_toogle_clicked(graph, toggle_btn))
    
    progress_bar = ProgressBar(parent=graph_widget)
    SignalManager().calculation_begin.connect(progress_bar.on_calculation_begin)
    SignalManager().calculation_begin.connect(lambda: run_button.setDisabled(True))
    SignalManager().calculation_finished.connect(progress_bar.on_calculation_finished)
    SignalManager().calculation_finished.connect(lambda: run_button.setDisabled(False))
    SignalManager().calculation_processed.connect(progress_bar.on_calculation_processed)
    progress_bar.show()

    
    
    top_layout.addWidget(run_button)
    top_layout.addWidget(toggle_btn)
    top_layout.addWidget(progress_bar)
    main_layout.addLayout(top_layout)
    run_button.show()
    
    
    graph_widget.resize(1100, 800)
    graph_widget.setWindowTitle("FretGUI")
    graph_widget.show()  
    
    
    file_node = graph.create_node(
        'nodes.custom.FileNode', text_color='#feab20')
    file_node.set_disabled(False)
    
    photon_node = graph.create_node(
        'nodes.custom.PhotonNode', text_color='#feab20')
    photon_node.set_disabled(False)
    
    alex_node = graph.create_node(
        'nodes.custom.AlexNode', text_color='#feab20')
    alex_node.set_disabled(False)
    
    calc_bgnode = graph.create_node(
        'nodes.custom.CalcBGNode', text_color='#feab20')
    calc_bgnode.set_disabled(False)
    
    search_node = graph.create_node(
        'nodes.custom.BurstSearchNodde', text_color='#feab20')
    search_node.set_disabled(False)
    
    plot_node = graph.create_node(
        'nodes.custom.BGPlotterNode', text_color='#feab20')
    plot_node.set_disabled(False)
    

    
    file_node.set_output(0, photon_node.input(0))
    photon_node.set_output(0, alex_node.input(0))
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
    
    sidebar_layout = QtWidgets.QVBoxLayout()
    sidebar_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
    sidebar_layout.setSpacing(0)  # Remove spacing
    sidebar_layout.addStretch()
    sidebar_layout.addWidget(nodes_palette)
    sidebar_widget = QtWidgets.QWidget()
    sidebar_widget.setLayout(sidebar_layout)
    sidebar_widget.setFixedSize(300, 200)
    main_layout.addWidget(sidebar_widget)
        
        
    app.exec()

    

if __name__ == '__main__':
    main()
    

    