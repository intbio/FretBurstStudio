from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from NodeGraphQt import BaseNode
from abc import  abstractmethod, ABC
from fbs_data import FBSData
from node_workers import UpdateWidgetNodeWorker   
from Qt.QtCore import QThreadPool   
from singletons import ThreadSignalManager
from collections import deque
from .resizable_node_item import ResizablePlotNodeItem
from Qt.QtCore import QTimer
            
            
            
class AbstractExecutable(BaseNode, ABC):
    def __init__(self, *args, **kwargs):
        BaseNode.__init__(self, *args, **kwargs)      

    @abstractmethod    
    def execute(self, data: FBSData=None) -> list[FBSData]:
        pass
           
    def is_root(self) -> bool:
        return len(self.input_ports()) == 0
           
    def iter_parent_nodes(self):
        for port in self.input_ports():
            connected_ports = port.connected_ports()
            for connected_port in connected_ports:
                connected_node = connected_port.node()
                yield connected_node
                
    def iter_children_nodes(self):
        for port in self.output_ports():
            connected_ports = port.connected_ports()
            for connected_port in connected_ports:
                connected_node = connected_port.node()
                yield connected_node
                
    def bfs(self):
        visited = set([self])
        q = deque([self])
        while len(q) != 0:
            cur_node = q.popleft()
            for nextnode in cur_node.iter_children_nodes():
                if nextnode in visited:
                    continue
                visited.add(nextnode)
                yield nextnode
                
                                  
class AbstractRecomputable(AbstractExecutable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget_wrappers = []  
        self.__wired = False
        
    def on_widget_changed(self):
        root_nodes = self.find_roots()
        
    def find_roots(self):
        if self.is_root():
            return [self]
        root_nodes = []
        self.__find_roots(self, root_nodes)   
        return root_nodes
    
    def __find_roots(self, node, root_nodes):
        for parent in node.iter_parent_nodes():
            if parent.is_root():
                root_nodes.append(parent)
            self.__find_roots(parent, root_nodes)
    
    def add_custom_widget(self, widget, *args, **kwargs):
        if isinstance(widget, AbstractWidgetWrapper):               
            widget.widget_changed_signal.connect(self.on_widget_changed)
            self.widget_wrappers.append(widget)  
        super().add_custom_widget(widget, *args, **kwargs)
        
    def wire_wrappers(self):
        self.__wired = True
        if len(self.widget_wrappers) == 0:
            return None
        for widget_wrapper in self.widget_wrappers:
            widget_wrapper.widget_changed_signal.connect(self.on_widget_triggered)
            
    def unwire_wrappers(self):
        self.__wired = False
        if len(self.widget_wrappers) == 0:
            return None
        for widget_wrapper in self.widget_wrappers:
            widget_wrapper.widget_changed_signal.disconnect()
            
    def disable_all_node_widgets(self):
        for widget_name, widget in self.widgets().items():
            widget.setEnabled(False)

    def enable_all_node_widgets(self):
        for widget_name, widget in self.widgets().items():
            widget.setEnabled(True)
            
    def on_input_connected(self, in_port, out_port):
        res = super().on_input_connected(in_port, out_port)
        if self.__wired:
            self.on_widget_triggered(self)
        return res
    
    def on_input_disconnected(self, in_port, out_port):
        res = super().on_input_disconnected(in_port, out_port)
        if self.__wired:
            self.on_widget_triggered(self)
            self.on_widget_triggered(out_port.node())
        return res
            
    def on_widget_triggered(self, node=None):
        node = node if node else self
        print("widget trigiered")
        worker = UpdateWidgetNodeWorker(node)
        pool = QThreadPool.globalInstance()
        pool.start(worker)

class ResizableContentNode(AbstractRecomputable):
    """
    Base class for nodes that have a single main widget
    that should follow the node's size.
    """
    # default margins, override in subclasses if you want
    LEFT_RIGHT_MARGIN = 100
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20
    SLIDER_WIDTH = 200  # Fixed width for sliders and other non-plot widgets
    MIN_WIDTH = 300  # Minimum allowed width for the node
    MIN_HEIGHT = 200  # Minimum allowed height for the node

    def __init__(self, widget_name, qgraphics_item=None):
        # if you always use ResizablePlotNodeItem, you can default it here
        super().__init__(qgraphics_item=qgraphics_item or ResizablePlotNodeItem)

        self._content_widget_name = widget_name
        self._initial_layout_done = False  # Track if initial layout has been applied

        # hook up resize callback
        view = self.view            # this is your ResizablePlotNodeItem
        
        # Set minimum width and height from constants
        view.MIN_W = self.MIN_WIDTH
        view.MIN_H = self.MIN_HEIGHT
        
        # Also ensure initial size respects minimums
        if view._width < self.MIN_WIDTH:
            view._width = self.MIN_WIDTH
        if view._height < self.MIN_HEIGHT:
            view._height = self.MIN_HEIGHT
        
        view.add_resize_callback(self._on_view_resized)
        
        # hook up paint callback to do initial layout on first paint
        view.add_paint_callback(self._on_view_painted)

    def _on_view_painted(self):
        """Called every time the node is redrawn/painted."""
        # Do initial layout on first paint when widgets are guaranteed to exist
        if not self._initial_layout_done:
            view = self.view
            # Check if widget exists before applying layout
            if self.get_widget(self._content_widget_name) is not None:
                self._initial_layout_done = True
                self._on_view_resized(view._width, view._height)

    def _on_view_resized(self, w, h):
        wrapper = self.get_widget(self._content_widget_name)
        if wrapper is None:
            return

        inner_w = max(
            1,
            w - 2 * self.LEFT_RIGHT_MARGIN
        )

        # Calculate total height of widgets that come before the plot widget
        # and update their positions to keep them left-aligned
        widgets_before_plot = []
        widgets_after_plot = []
        plot_widget_found = False
        
        for widget_name, widget in self.widgets().items():
            if widget_name == self._content_widget_name:
                plot_widget_found = True
                continue
            if plot_widget_found:
                widgets_after_plot.append((widget_name, widget))
            else:
                widgets_before_plot.append((widget_name, widget))
        
        def get_widget_height(widget):
            """Safely get widget height from various sources."""
            # Try to get from current geometry first
            try:
                geom = widget.geometry()
                if geom.height() > 0:
                    return geom.height()
            except:
                pass
            
            # Try to get from custom widget's size hint
            try:
                custom_widget = widget.get_custom_widget()
                if custom_widget:
                    hint = custom_widget.sizeHint()
                    if hint and hint.height() > 0:
                        return hint.height()
            except:
                pass
            
            # Fallback to a reasonable default (slider height is typically ~50)
            return 50
        
        # Update all non-plot widgets to be left-aligned with fixed width
        current_y = self.TOP_MARGIN
        for widget_name, widget in widgets_before_plot + widgets_after_plot:
            widget_height = get_widget_height(widget)
            
            # Use fixed width for sliders, keep them left-aligned
            widget.setGeometry(
                self.LEFT_RIGHT_MARGIN,
                current_y,
                self.SLIDER_WIDTH,
                widget_height
            )
            current_y += widget_height
        
        # Calculate available height for plot widget
        # Sum up heights of widgets before the plot
        widgets_before_height = sum(
            get_widget_height(widget)
            for _, widget in widgets_before_plot
        )
        
        # Position plot widget below all widgets that come before it
        plot_y = self.TOP_MARGIN + widgets_before_height
        plot_h = max(
            1,
            h - plot_y - self.BOTTOM_MARGIN
        )

        wrapper.setMinimumSize(inner_w, plot_h)
        wrapper.setMaximumSize(inner_w, plot_h)
        wrapper.setGeometry(
            self.LEFT_RIGHT_MARGIN,
            plot_y,
            inner_w,
            plot_h
        )

