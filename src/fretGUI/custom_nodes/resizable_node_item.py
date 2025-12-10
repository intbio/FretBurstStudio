from Qt import QtCore, QtGui, QtWidgets
from NodeGraphQt.qgraphics.node_base import NodeItem


class ResizablePlotNodeItem(NodeItem):
    HANDLE_SIZE = 10
    MIN_W = 200
    MIN_H = 150

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._width = 350
        self._height = 250
        self._resizing = False
        self._start_pos = None
        self._start_size = None

        # simple python callbacks instead of Qt Signal
        self._resize_callbacks = []

        self.setAcceptHoverEvents(True)

    # ---- public API for BGPlotterNode ---------------------------------

    def add_resize_callback(self, func):
        """Register a Python callback called as func(w, h) on resize."""
        if callable(func):
            self._resize_callbacks.append(func)

    def _emit_resized(self, w, h):
        for cb in list(self._resize_callbacks):
            try:
                cb(w, h)
            except Exception:
                pass  # don’t crash the view on user callback errors

    # ---- geometry / drawing -------------------------------------------

    def _handle_rect(self):
        r = self.boundingRect()
        return QtCore.QRectF(
            r.right() - self.HANDLE_SIZE,
            r.bottom() - self.HANDLE_SIZE,
            self.HANDLE_SIZE,
            self.HANDLE_SIZE,
        )

    def boundingRect(self):
        base = super().boundingRect()
        return QtCore.QRectF(
            base.x(),
            base.y(),
            max(base.width(), self._width),
            max(base.height(), self._height),
        )

    def paint(self, painter, option, widget):
        # draw normal node
        super().paint(painter, option, widget)

        # draw resize handle
        painter.save()
        painter.drawRect(self._handle_rect())
        painter.restore()

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