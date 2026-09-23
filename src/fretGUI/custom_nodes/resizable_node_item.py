from Qt import QtCore, QtGui, QtWidgets
from NodeGraphQt.qgraphics.node_base import NodeItem


class _ResizeHandleItem(QtWidgets.QGraphicsRectItem):
    """Mouse target kept above embedded QGraphicsProxyWidgets."""

    def __init__(self, owner):
        size = owner.HANDLE_SIZE
        super().__init__(0, 0, size, size, owner)
        self._owner = owner
        self.setPen(QtCore.Qt.NoPen)
        self.setBrush(QtGui.QColor(0, 0, 0, 1))
        self.setZValue(1000)
        self.setAcceptedMouseButtons(QtCore.Qt.LeftButton)
        self.setCursor(QtCore.Qt.SizeFDiagCursor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._owner._begin_resize(event.scenePos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._owner._resizing:
            self._owner._resize_from_scene_pos(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            self._owner._resizing
            and event.button() == QtCore.Qt.LeftButton
        ):
            self._owner._end_resize()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ResizablePlotNodeItem(NodeItem):
    HANDLE_SIZE = 30
    MIN_W = 200
    MIN_H = 150

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._width = 500
        self._height = 250
        self._resizing = False
        self._start_pos = None
        self._start_size = None
        self._handle_color = QtGui.QColor(100, 100, 100)

        # simple python callbacks instead of Qt Signal
        self._resize_callbacks = []
        self._paint_callbacks = []  # Add this back

        self.setAcceptHoverEvents(True)
        # Enable drag and drop
        self.setAcceptDrops(True)
        self._resize_handle = _ResizeHandleItem(self)
        self._position_resize_handle()

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

    def set_size(self, width, height, emit=True):
        """Set both dimensions while keeping QGraphicsScene geometry valid."""
        width = max(float(width), self.MIN_W)
        height = max(float(height), self.MIN_H)
        changed = width != self._width or height != self._height

        if changed:
            self.prepareGeometryChange()
            self._width = width
            self._height = height
            self.update()

        # NodeGraphQt can assign _width/_height directly during its layout.
        # Keep the child handle synchronized even when set_size sees no delta.
        self._position_resize_handle()

        if emit:
            self._emit_resized(self._width, self._height)
        return changed

    # ---- NodeGraphQt layout overrides ---------------------------------

    def _set_base_size(self, add_w=0.0, add_h=0.0):
        # Manual resize / width-height properties own size.
        # Ignoring calc_size avoids feedback with large plot widgets.
        self.set_size(self._width, self._height, emit=False)

    def align_widgets(self, v_offset=0.0):
        """Skip NodeGraphQt centering; keep geometry from _on_view_resized / resize handle."""
        return

    # ---- geometry / drawing -------------------------------------------

    def boundingRect(self):
        """Override to use custom width and height"""
        return QtCore.QRectF(0, 0, self._width, self._height)
    
    def _handle_rect(self):
        r = self.boundingRect()
        return QtCore.QRectF(
            r.right() - self.HANDLE_SIZE,
            r.bottom() - self.HANDLE_SIZE,
            self.HANDLE_SIZE,
            self.HANDLE_SIZE,
        )

    def _position_resize_handle(self):
        if hasattr(self, '_resize_handle'):
            rect = self._handle_rect()
            self._resize_handle.setPos(rect.topLeft())

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

    def _begin_resize(self, scene_pos):
        self._resizing = True
        self._start_pos = scene_pos
        self._start_size = QtCore.QSizeF(self._width, self._height)

    def _resize_from_scene_pos(self, scene_pos):
        delta = scene_pos - self._start_pos
        new_w = max(self.MIN_W, self._start_size.width() + delta.x())
        new_h = max(self.MIN_H, self._start_size.height() + delta.y())
        if new_w != self._width or new_h != self._height:
            self.set_size(new_w, new_h)

    def _end_resize(self):
        self._resizing = False

    def mousePressEvent(self, event):
        if (event.button() == QtCore.Qt.LeftButton and
                self._handle_rect().contains(event.pos())):
            self._begin_resize(event.scenePos())
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            self._resize_from_scene_pos(event.scenePos())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing and event.button() == QtCore.Qt.LeftButton:
            self._end_resize()
            event.accept()
            return

        super().mouseReleaseEvent(event)