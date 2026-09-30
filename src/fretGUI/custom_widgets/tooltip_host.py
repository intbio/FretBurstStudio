"""Show graph tooltips from a real top-level window.

Wayland refuses QToolTip popups whose parent is a graphics-view widget or a
widget embedded in a QGraphicsProxyWidget, because that popup has no
transient parent. Anchoring the same text to the application window gives
the popup a surface it can attach to.
"""

from Qt import QtCore, QtWidgets


def _global_pos(event):
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()


def _embedded_in_proxy(widget):
    while widget is not None:
        if widget.graphicsProxyWidget() is not None:
            return True
        widget = widget.parentWidget()
    return False


def _graphics_tooltip(viewer, viewport_pos):
    for item in viewer.items(viewport_pos):
        text = item.toolTip()
        if text:
            return text
    return ""


class TooltipPopupParent(QtCore.QObject):
    """Re-show tooltips that Wayland would otherwise drop."""

    def __init__(self, host, viewer):
        super().__init__(host)
        self._host = host
        self._viewer = viewer

    def eventFilter(self, obj, event):
        if event.type() != QtCore.QEvent.ToolTip:
            return False
        if not isinstance(obj, QtWidgets.QWidget):
            return False
        try:
            viewport = self._viewer.viewport()
        except RuntimeError:
            return False

        if obj is viewport or obj is self._viewer:
            if obj is viewport:
                pos = event.pos()
            else:
                pos = viewport.mapFrom(self._viewer, event.pos())
            text = _graphics_tooltip(self._viewer, pos)
        elif _embedded_in_proxy(obj):
            text = obj.toolTip()
        else:
            return False

        if not text:
            return False
        QtWidgets.QToolTip.showText(_global_pos(event), text, self._host)
        return True


def install_tooltip_popup_parent(host, viewer):
    """Anchor graph and embedded-widget tooltips to ``host``."""
    existing = getattr(viewer, "_tooltip_popup_parent", None)
    if existing is not None:
        return existing
    helper = TooltipPopupParent(host, viewer)
    QtWidgets.QApplication.instance().installEventFilter(helper)
    viewer._tooltip_popup_parent = helper
    return helper
