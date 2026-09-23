from abc import ABC, abstractmethod
from collections import deque

from NodeGraphQt import BaseNode

from fretGUI.custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from fretGUI.custom_nodes.compact_node_item import CompactNodeItem
from fretGUI.fbs_data import FBSData
from fretGUI.singletons import (
    EventDebouncer,
    NodeStateManager,
    RunCoordinator,
    ThreadSignalManager,
)

from fretGUI.custom_nodes.resizable_node_item import ResizablePlotNodeItem
            
            
            
class AbstractExecutable(BaseNode, ABC):
   
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('qgraphics_item', CompactNodeItem)
        BaseNode.__init__(self, *args, **kwargs)
        self._apply_description_tooltip()

    def _apply_description_tooltip(self):
        description = getattr(type(self), 'DESCRIPTION', '')
        if description:
            set_description = getattr(
                self.view,
                'set_description_tooltip',
                None,
            )
            if callable(set_description):
                set_description(description)
            else:
                self.view.setToolTip(description)

    def update(self):
        super().update()
        self._apply_description_tooltip()

    def add_input(self, name='input', *args, **kwargs):
        port = super().add_input(name, *args, **kwargs)
        self._set_port_display_text(port, 'in' if name == 'inport' else name)
        return port

    def add_output(self, name='output', *args, **kwargs):
        port = super().add_output(name, *args, **kwargs)
        self._set_port_display_text(port, 'out' if name == 'outport' else name)
        return port

    def _set_port_display_text(self, port, text):
        """Set a visual port alias without changing its serialized name."""
        items = (
            self.view._input_items
            if port in self.input_ports()
            else self.view._output_items
        )
        text_item = items.get(port.view)
        if text_item is not None:
            text_item.setPlainText(text)
        
    def are_ports_acceptable(self, inport, outport) -> bool:
          return inport.color == outport.color

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
                
    def are_ports_acceptable(self, inport, outport) -> bool:
        return inport.color == outport.color
                
                                  
class AbstractRecomputable(AbstractExecutable):
   
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget_wrappers = []  
        self.__wired = False
        self.event_debouncer = EventDebouncer(50, self.on_connection)   
        self.__rejected_nodes = set()
        
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
            
    def on_state_changed(self, state):
        if state:
            self.wire_wrappers()
            self.event_debouncer.connect(self.on_connection)
        else:
            self.unwire_wrappers()
            self.event_debouncer.disconnect()
            
    
    def add_custom_widget(self, widget, *args, **kwargs):
        connection_status = NodeStateManager().node_status
        if connection_status:
            self.event_debouncer.connect(self.on_connection)
        else:
            self.event_debouncer.disconnect()
        
        if isinstance(widget, AbstractWidgetWrapper):  
            widget.widget_changed_signal.connect(
                self.on_widget_changing
            )
            if connection_status:
                widget.debounced_signal.connect(self.on_widget_triggered)
            self.widget_wrappers.append(widget)  
        super().add_custom_widget(widget, *args, **kwargs)
        
    def wire_wrappers(self):
        self.event_debouncer.connect(self.on_connection)
        if len(self.widget_wrappers) == 0:
            return None
        for widget_wrapper in self.widget_wrappers:
            widget_wrapper.debounced_signal.connect(self.on_widget_triggered)
            
    def unwire_wrappers(self):
        self.event_debouncer.disconnect()
        if len(self.widget_wrappers) == 0:
            return None
        for widget_wrapper in self.widget_wrappers:
            widget_wrapper.debounced_signal.disconnect(self.on_widget_triggered)
            
    def disable_all_node_widgets(self):
        for widget_name, widget in self.widgets().items():
            widget.setEnabled(False)

    def enable_all_node_widgets(self):
        for widget_name, widget in self.widgets().items():
            widget.setEnabled(True)
            
    def on_input_connected(self, in_port, out_port):          
        if self.are_ports_acceptable(in_port, out_port):
            RunCoordinator().invalidate_active()
            self.event_debouncer.push_event(('connect', in_port, out_port))
            return super().on_input_connected(in_port, out_port)
        out_port.disconnect_from(in_port, emit_signal=False)
    
    def on_input_disconnected(self, in_port, out_port):
        RunCoordinator().invalidate_active()
        self.event_debouncer.push_event(('disconnect', in_port, out_port))
        return super().on_input_disconnected(in_port, out_port)
    
    def on_connection(self, event):
        self.on_widget_triggered()

    def on_widget_changing(self):
        RunCoordinator().invalidate_active()
            
    def on_widget_triggered(self):
        print("TRIGGERED", type(self))
        ThreadSignalManager().run_btn_clicked.emit()



class ResizableContentNode(AbstractRecomputable):
    """
    Base class for nodes that have a single main widget
    that should follow the node's size.
    """
    # default margins, override in subclasses if you want
    LEFT_RIGHT_MARGIN = 3
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20
    CONTROL_MIN_WIDTH = 180
    CONTROL_GAP = 3
    MAX_CONTROL_COLUMNS = 2
    PLOT_Z_VALUE = 1
    PORT_Z_VALUE = 2
    PORT_TEXT_Z_VALUE = 4
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
        
        # Check if width/height properties already exist (from JSON loading)
        # If they do, use those instead of defaults
        try:
            node_width = self.get_property('width')
            node_height = self.get_property('height')
            width = node_width if node_width is not None else view._width
            height = node_height if node_height is not None else view._height
            view.set_size(width, height, emit=False)
        except (AttributeError, KeyError, TypeError, ValueError):
            view.set_size(view._width, view._height, emit=False)
        
        view.add_resize_callback(self._on_view_resized)
        
        # hook up paint callback to do initial layout on first paint
        view.add_paint_callback(self._on_view_painted)

    def set_property(self, name, value,push_undo=None):
        """Override to intercept width/height property changes and sync to view."""
        # Call parent first to set the property
        result = super().set_property(name, value)
        
        # If width or height is being set, update the view's internal size
        # This handles deserialization from JSON and copy/paste
        if hasattr(self, 'view') and isinstance(self.view, ResizablePlotNodeItem):
            if name == 'width':
                self.view.set_size(value, self.view._height)
            elif name == 'height':
                self.view.set_size(self.view._width, value)
        
        return result

    def restore_size(self, width, height):
        """Restore a serialized size atomically after the node enters a scene."""
        self.view.set_size(width, height)

    def _on_view_painted(self):
        """Called every time the node is redrawn/painted."""
        view = self.view

        # Embedded Matplotlib canvases need more backing pixels when the graph
        # view enlarges them. The widget debounces the actual DPI update.
        wrapper = self.get_widget(self._content_widget_name)
        scene = view.scene()
        if wrapper is not None and scene is not None and scene.views():
            content_widget = wrapper.get_custom_widget()
            set_graph_scale = getattr(content_widget, 'set_graph_scale', None)
            if callable(set_graph_scale):
                set_graph_scale(abs(scene.views()[0].transform().m11()))
        
        # Enforce minimum size on every paint (in case NodeGraphQt recalculated it)
        size_changed = view.set_size(
            view._width,
            view._height,
            emit=False,
        )
        
        if size_changed:
            self._on_view_resized(view._width, view._height)
            self._initial_layout_done = True
            return

        # Safety net: first paint when widgets exist (draw_node → align_widgets
        # normally re-layouts after checkbox/port changes).
        if not self._initial_layout_done:
            if self.get_widget(self._content_widget_name) is not None:
                self._initial_layout_done = True
                self._on_view_resized(view._width, view._height)

    def _on_view_resized(self, w, h):
        wrapper = self.get_widget(self._content_widget_name)
        if wrapper is None:
            return

        # The full-width canvas may extend under the ports. Keep port shapes
        # and names above it without sacrificing plot width.
        wrapper.setZValue(self.PLOT_Z_VALUE)
        for port, text in [
            *self.view._input_items.items(),
            *self.view._output_items.items(),
        ]:
            port.setZValue(self.PORT_Z_VALUE)
            text.setZValue(self.PORT_TEXT_Z_VALUE)

        content_widget = wrapper.get_custom_widget()
        set_toolbar_left_inset = getattr(
            content_widget,
            'set_toolbar_left_inset',
            None,
        )
        if callable(set_toolbar_left_inset):
            visible_input_labels = [
                text
                for port, text in self.view._input_items.items()
                if port.isVisible() and text.isVisible()
            ]
            label_right = max(
                (
                    text.pos().x() + text.boundingRect().width()
                    for text in visible_input_labels
                ),
                default=self.LEFT_RIGHT_MARGIN,
            )
            set_toolbar_left_inset(
                max(0, label_right - self.LEFT_RIGHT_MARGIN + 6)
            )

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
        
        def get_widget_height(widget, width):
            """Safely get widget height from various sources."""
            try:
                container = widget.widget()
                height = container.heightForWidth(int(width))
                if height > 0:
                    return height
            except:
                pass
            
            try:
                hint = widget.widget().sizeHint()
                if hint and hint.height() > 0:
                    return hint.height()
            except:
                pass
            
            return 50

        def build_control_rows(widgets):
            if not widgets:
                return []

            columns = min(
                self.MAX_CONTROL_COLUMNS,
                max(
                    1,
                    int(
                        (inner_w + self.CONTROL_GAP)
                        // (self.CONTROL_MIN_WIDTH + self.CONTROL_GAP)
                    ),
                ),
            )
            cell_width = (
                inner_w - ((columns - 1) * self.CONTROL_GAP)
            ) / columns

            rows = []
            for start in range(0, len(widgets), columns):
                row_widgets = widgets[start:start + columns]
                row_height = max(
                    get_widget_height(widget, cell_width)
                    for _, widget in row_widgets
                )
                rows.append((row_widgets, cell_width, row_height))
            return rows

        def rows_height(rows):
            if not rows:
                return 0
            return (
                sum(row_height for _, _, row_height in rows)
                + self.CONTROL_GAP * (len(rows) - 1)
            )

        def position_rows(rows, start_y):
            current_y = start_y
            for row_widgets, cell_width, row_height in rows:
                for column, (_, widget) in enumerate(row_widgets):
                    x = (
                        self.LEFT_RIGHT_MARGIN
                        + column * (cell_width + self.CONTROL_GAP)
                    )
                    widget.setGeometry(x, current_y, cell_width, row_height)
                current_y += row_height + self.CONTROL_GAP
            return current_y
        
        # Lay out widgets in three vertical blocks:
        # 1) widgets_before_plot at the top
        # 2) plot widget in the middle
        # 3) widgets_after_plot below the plot

        before_rows = build_control_rows(widgets_before_plot)
        after_rows = build_control_rows(widgets_after_plot)

        current_y = position_rows(before_rows, self.TOP_MARGIN)
        widgets_after_height = rows_height(after_rows)

        # Position the plot widget using remaining space minus the space needed for widgets_after_plot.
        plot_y = current_y
        plot_h = max(
            1,
            h - plot_y - widgets_after_height - self.BOTTOM_MARGIN
        )
        wrapper.setMinimumSize(inner_w, plot_h)
        wrapper.setMaximumSize(inner_w, plot_h)
        wrapper.setGeometry(
            self.LEFT_RIGHT_MARGIN,
            plot_y,
            inner_w,
            plot_h
        )

        # Finally, flow widgets added after the plot into compact rows.
        position_rows(after_rows, plot_y + plot_h)
