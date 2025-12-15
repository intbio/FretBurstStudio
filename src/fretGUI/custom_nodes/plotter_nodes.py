import fretbursts
from node_builder import NodeBuilder

from fbs_data import FBSData
from singletons import ThreadSignalManager
from abc import abstractmethod
from custom_nodes.abstract_nodes import AbstractRecomputable

from Qt import QtCore, QtGui
from NodeGraphQt.qgraphics.node_base import NodeItem


class ResizablePlotNodeItem(NodeItem):
    HANDLE_SIZE = 30
    MIN_W = 200
    MIN_H = 150

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._width = 350
        self._height = 250
        self._resizing = False
        self._start_pos = None
        self._start_size = None
        self._handle_color = QtGui.QColor(100, 100, 100)

        # simple python callbacks instead of Qt Signal
        self._resize_callbacks = []
        self._paint_callbacks = []  # Add this back

        self.setAcceptHoverEvents(True)

    # ---- public API for BGPlotterNode ---------------------------------

    def add_resize_callback(self, func):
        """Register a Python callback called as func(w, h) on resize."""
        if callable(func):
            self._resize_callbacks.append(func)

    def add_paint_callback(self, func):
        """Register a Python callback called as func() on paint/redraw."""
        if callable(func):
            self._paint_callbacks.append(func)

    def _emit_resized(self, w, h):
        for cb in list(self._resize_callbacks):
            try:
                cb(w, h)
            except Exception:
                pass  # don't crash the view on user callback errors

    def _emit_painted(self):
        """Call all registered paint callbacks."""
        for cb in list(self._paint_callbacks):
            try:
                cb()
            except Exception:
                pass  # don't crash the view on user callback errors

    # ---- geometry / drawing -------------------------------------------

    def _handle_rect(self):
        r = self.boundingRect()
        return QtCore.QRectF(
            r.right() - self.HANDLE_SIZE,
            r.bottom() - self.HANDLE_SIZE,
            self.HANDLE_SIZE,
            self.HANDLE_SIZE,
        )

    def paint(self, painter, option, widget):
        # Call paint callbacks before drawing
        self._emit_painted()
        
        # draw normal node
        super().paint(painter, option, widget)

        # draw resize handle (simple triangular corner grip)
        painter.save()
        
        margin = 1.0
        handle_rect = self._handle_rect()
        rect = QtCore.QRectF(
            handle_rect.left() + margin,
            handle_rect.top() + margin,
            handle_rect.width() - (margin * 2),
            handle_rect.height() - (margin * 2),
        )
        
        color = self._handle_color
        
        # Create triangular path: topRight -> bottomRight -> bottomLeft
        path = QtGui.QPainterPath()
        path.moveTo(rect.topRight())
        path.lineTo(rect.bottomRight())
        path.lineTo(rect.bottomLeft())
        
        painter.setBrush(color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.fillPath(path, painter.brush())
        
        painter.restore()

    def set_handle_color(self, color):
        """Set grip color (accepts QColor or iterable of ints)."""
        try:
            self._handle_color = QtGui.QColor(color)
        except Exception:
            try:
                self._handle_color = QtGui.QColor(*color)
            except Exception:
                self._handle_color = QtGui.QColor(100, 100, 100)

    # ---- mouse interaction --------------------------------------------

    def mousePressEvent(self, event):
        if (event.button() == QtCore.Qt.LeftButton and
                self._handle_rect().contains(event.pos())):
            self._resizing = True
            self._start_pos = event.scenePos()
            self._start_size = QtCore.QSizeF(self._width, self._height)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.scenePos() - self._start_pos
            new_w = max(self.MIN_W, self._start_size.width() + delta.x())
            new_h = max(self.MIN_H, self._start_size.height() + delta.y())

            if new_w != self._width or new_h != self._height:
                self.prepareGeometryChange()
                self._width = new_w
                self._height = new_h
                self._emit_resized(new_w, new_h)

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing and event.button() == QtCore.Qt.LeftButton:
            self._resizing = False
            event.accept()
            return

        super().mouseReleaseEvent(event)



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




class AbstractContentNode(ResizableContentNode):
    def __init__(self, widget_name, qgraphics_item=None):
        super().__init__(widget_name, qgraphics_item)
        self.data_to_plot = []
        ThreadSignalManager().all_thread_finished.connect(self.on_refresh_canvas)
        ThreadSignalManager().run_btn_clicked.connect(self.on_plot_data_clear)
        self.was_executed = False
        
    def on_refresh_canvas(self):
        if self.was_executed:
            self._on_refresh_canvas()
        
    @abstractmethod
    def _on_refresh_canvas(self):
        pass
    
    def on_plot_data_clear(self):
        self.data_to_plot.clear()
        self.was_executed = False
    
    def execute(self, fbsdata: FBSData=None):
        self.was_executed = True
        if fbsdata is not None:
            self.data_to_plot.append(fbsdata)
        return [fbsdata]  
    

class BGPlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'BGPlotterNode'
   

    # if you want different margins just for this node:
    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20
    PLOT_NODE = True
    MIN_WIDTH = 450  # Minimum allowed width for the node
    MIN_HEIGHT = 300  # Minimum allowed height for the node

    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)

        node_builder = NodeBuilder(self)
        
        self.add_input('inport')

        node_builder.build_plot_widget('plot_widget')      
                         
        
    def _on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        fig = plot_widget.figure
        fig.clear()
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        for cur_data in self.data_to_plot:
            fretbursts.dplot(cur_data.data, fretbursts.hist_bg, show_fit=True, ax=ax1)
            fretbursts.dplot(cur_data.data, fretbursts.timetrace_bg, ax=ax2)
        plot_widget.canvas.draw()
        self.on_plot_data_clear()
        
    
class EHistPlotterNode(AbstractContentNode):
    __identifier__ = 'Plot'
    NODE_NAME = 'EHistPlotterNode'

    # if you want different margins just for this node:
    LEFT_RIGHT_MARGIN = 67
    TOP_MARGIN = 35
    BOTTOM_MARGIN = 20
    PLOT_NODE = True
    MIN_WIDTH = 450  # Minimum allowed width for the node
    MIN_HEIGHT = 300  # Minimum allowed height for the node


    def __init__(self, widget_name='plot_widget', qgraphics_item=None):
        # tell the base which widget name to resize
        super().__init__(widget_name, qgraphics_item)

        node_builder = NodeBuilder(self)

        self.add_input('inport')
        self.BinWidth_slider = node_builder.build_float_slider('Bin Width', [0.01, 0.2, 0.01], 0.03)
        node_builder.build_plot_widget('plot_widget')

    def _on_refresh_canvas(self):
        plot_widget = self.get_widget('plot_widget').plot_widget
        plot_widget.figure.clf()
        ax1 = plot_widget.figure.add_subplot()
        ax1.cla()
        for cur_data in self.data_to_plot:
            fretbursts.dplot(cur_data.data, fretbursts.hist_fret, ax=ax1, binwidth=self.BinWidth_slider.get_value(),
            hist_style = 'bar' if len(self.data_to_plot)==1 else 'line')
        plot_widget.canvas.draw()
        print("plot", self)
        self.on_plot_data_clear()
