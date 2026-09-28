"""Right-button drag pans the node graph without replacing a right-click menu."""

from Qt import QtCore, QtWidgets
from fretGUI.custom_widgets.plot_widget import matplotlib_tool_active_at


class RightButtonPan(QtCore.QObject):
    """Pan on a right-button drag. A click that does not drag still opens the menu."""

    def __init__(self, viewer):
        super().__init__(viewer)
        self._viewer = viewer
        viewer._rmb_pan = False
        viewer._rmb_plot_tool = False

    def eventFilter(self, obj, event):
        viewer = self._viewer
        try:
            viewport = viewer.viewport()
        except RuntimeError:
            return False
        if obj is not viewport and obj is not viewer:
            return False

        event_type = event.type()
        if (
            obj is viewport
            and event_type == QtCore.QEvent.MouseButtonPress
            and event.button() == QtCore.Qt.RightButton
        ):
            viewer._rmb_plot_tool = matplotlib_tool_active_at(viewer, event.pos())
            return False

        if obj is viewport and event_type == QtCore.QEvent.MouseMove:
            self._pan_if_dragging(event)
            return False

        if (
            obj is viewer.viewport()
            and event_type == QtCore.QEvent.MouseButtonRelease
            and event.button() == QtCore.Qt.RightButton
        ):
            QtCore.QTimer.singleShot(0, self._clear_pan_flag)
            return False

        if event_type == QtCore.QEvent.ContextMenu and viewer._rmb_pan:
            viewer._rmb_pan = False
            event.accept()
            return True
        return False

    def _pan_if_dragging(self, event):
        viewer = self._viewer
        if not viewer.RMB_state or viewer._rmb_plot_tool:
            return
        travel = (event.pos() - viewer._origin_pos).manhattanLength()
        if travel < QtWidgets.QApplication.startDragDistance():
            return
        viewer._rmb_pan = True
        previous_pos = viewer.mapToScene(viewer._previous_pos)
        current_pos = viewer.mapToScene(event.pos())
        delta = previous_pos - current_pos
        viewer._set_viewer_pan(delta.x(), delta.y())

    def _clear_pan_flag(self):
        try:
            self._viewer._rmb_pan = False
            self._viewer._rmb_plot_tool = False
        except RuntimeError:
            return


def enable_right_button_pan(viewer):
    """Install right-button panning on a NodeGraphQt viewer."""
    existing = getattr(viewer, '_right_button_pan', None)
    if existing is not None:
        return existing
    pan = RightButtonPan(viewer)
    viewer.viewport().installEventFilter(pan)
    viewer.installEventFilter(pan)
    viewer._right_button_pan = pan
    return pan
