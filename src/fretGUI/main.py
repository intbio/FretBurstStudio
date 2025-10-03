import custom_nodes
import graph_engene

import sys


import signal
from pathlib import Path
from Qt import QtWidgets, QtCore
from NodeGraphQt import NodeGraph, NodesPaletteWidget
from NodeGraphQt import PropertiesBinWidget
from toogle_widget import IconToggleButton





BASE_PATH = Path(__file__).parent.resolve()


def on_run_btn_clicked(graph):
    engene = graph_engene.GraphEngene(graph)
    topological_iterator = engene.iter_topologicaly()
    for cur_node in topological_iterator:
        input_ports = cur_node.input_ports()
        for port in input_ports:
            connected_ports = port.connected_ports()
            for connected_port in connected_ports:
                prev_node = connected_port.node()
                prev_node_result = prev_node.get_data()
                print(cur_node, prev_node_result)
                cur_node.next_data(prev_node_result)
                print(cur_node, cur_node.data)
                

           
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
    # hotkey_path = Path(BASE_PATH, 'src/hotkeys', 'hotkeys.json')
    # graph.set_context_menu_from_file(hotkey_path, 'graph')
    
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
    
    run_button.clicked.connect(lambda: on_run_btn_clicked(graph))
    top_layout.addWidget(run_button)
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
        

    properties_bin = PropertiesBinWidget(node_graph=graph, parent=graph_widget)
    properties_bin.setWindowFlags(QtCore.Qt.Tool)
    
    
    # nodes_tree = NodesTreeWidget(node_graph=graph)
    # nodes_tree.set_category_label('nodeGraphQt.nodes', 'Builtin Nodes')
    # nodes_tree.set_category_label('nodes.custom.ports', 'Custom Port Nodes')
    # nodes_tree.set_category_label('nodes.widget', 'Widget Nodes')
    # nodes_tree.set_category_label('nodes.basic', 'Basic Nodes')
    # nodes_tree.set_category_label('nodes.group', 'Group Nodes')
    # # nodes_tree.show()

    
    nodes_palette = NodesPaletteWidget(node_graph=graph)
    nodes_palette.set_category_label('nodeGraphQt.nodes', 'Builtin Nodes')
    nodes_palette.set_category_label('nodes.custom.ports', 'Custom Port Nodes')
    nodes_palette.set_category_label('nodes.widget', 'Widget Nodes')
    nodes_palette.set_category_label('nodes.basic', 'Basic Nodes')
    nodes_palette.set_category_label('nodes.group', 'Group Nodes')
    # sidebar_layout.addWidget(nodes_palette)
    # main_layout.addLayout(sidebar_layout)
    nodes_palette.show()
    
    
    app.exec()

    

if __name__ == '__main__':
    main()
    

    