from NodeGraphQt import NodeGraph
from collections import deque


class BFSGraphIterator:
    def __init__(self, engene, root):
        self.engene = engene
        self.dequeue = deque([root])
        self.visited = set([root])
        
    def __iter__(self):
        return self
        
    def __next__(self):
        if not self.dequeue:
            raise StopIteration
        new_node = self.dequeue.pop()
        neighbour_nodes = self.get_neighbour_nodes(new_node)
        neighbour_nodes -= self.visited
        if neighbour_nodes:
            self.dequeue.extend(neighbour_nodes)
        return new_node
    
    def get_neighbour_nodes(self, node):
        return self.engene.get_neighbour_nodes(node)
    

class TopologicalGraphIterator:
    def __init__(self, engene, root=None):
        self.engene = engene
        self.root = root
        self.dequeue = deque()
        
    def __count_node_degree(self):
        nodes_degree = {}
        for node in self.engene.graph.all_nodes():
            n_input_ports = len(node.input_ports())
            nodes_degree[node] = n_input_ports
        return nodes_degree
    
    def __find_root_nodes(self):
        for node, degree in self.node_degree.items():
            if degree == 0:
                self.dequeue.append(node)
                
    def get_neighbour_nodes(self, node):
        return self.engene.get_neighbour_nodes(node)
    
    def __iter__(self):
        self.dequeue.clear()
        self.node_degree = self.__count_node_degree()
        self.__find_root_nodes()
        return self
    
    def __next__(self):
        if not self.dequeue:
            raise StopIteration
        new_node = self.dequeue.popleft()
        neighbour_nodes = self.get_neighbour_nodes(new_node)
        for neighbour in neighbour_nodes:
            self.node_degree[neighbour] -= 1
            if self.node_degree[neighbour] <= 0:
                self.dequeue.append(neighbour)
        return new_node
        

class GraphEngene:
    def __init__(self, graph: NodeGraph):
        self.graph = graph
        
    def iter_bfs(self, root=None):
        if root is None:
            roots = self.find_root_nodes()
            if len(roots) != 0:
                root = roots[0]
            else:
                raise Exception("no root was found")
        return BFSGraphIterator(self, root)
    
    def iter_topologicaly(self, root=None):
        return TopologicalGraphIterator(self)
    
        
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
    
    def get_neighbour_nodes(self, node):
        output_nodes = set()
        for port in node.output_ports():
            connected_ports = port.connected_ports()
            for connected_port in connected_ports:
                connected_node = connected_port.node()
                if connected_node not in output_nodes:
                    output_nodes.add(connected_node)
        return output_nodes
    
    