from NodeGraphQt import NodeGraph
from collections import deque
        

class GraphEngene:
    def __init__(self, graph: NodeGraph):
        self.graph = graph    
        
    def find_root_nodes(self):
        """Find nodes that have no input connections"""
        root_nodes = []
        for node in self.graph.all_nodes():
            has_inputs = False
            for port in node.input_ports():
                if port.connected_ports():
                    has_inputs = True
                    break
            if not has_inputs:
                root_nodes.append(node)
        return root_nodes
    
    def find_leafs(self):
        leafs = []
        for node in self.graph.all_nodes():
            for port in node.output_ports():
                if port.connected_ports():
                    break
            else:
                print(f"leave found {node}")
                leafs.append(node)
        return leafs
            
    
    def make_nodes_static(self):
        for node in self.graph.all_nodes():
            node.unwire_wrappers()
    
    def make_nodes_dinamic(self):
        for node in self.graph.all_nodes():
            node.wire_wrappers()

    
    