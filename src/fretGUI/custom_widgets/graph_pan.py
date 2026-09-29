"""Right-button drag pans the node graph without replacing a right-click menu."""

from Qt import QtCore, QtGui, QtWidgets
from fretGUI.custom_widgets.plot_widget import matplotlib_tool_active_at


class RightButtonPan(QtCore.QObject):
    """Pan on a right-button drag. A click that does not drag still opens the menu."""

    def __init__(self, viewer):
        super().__init__(viewer)
        self._viewer = viewer
        viewer._rmb_pan = False
        viewer._rmb_plot_tool = False
        self._menu_deferred = False
        self._menu_pos = QtCore.QPoint()
        self._replaying_menu = False

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
            obj is viewport
            and event_type == QtCore.QEvent.MouseButtonRelease
            and event.button() == QtCore.Qt.RightButton
        ):
            replay = (
                self._menu_deferred
                and not viewer._rmb_pan
                and not viewer._rmb_plot_tool
            )
            menu_pos = QtCore.QPoint(self._menu_pos)
            self._menu_deferred = False
            QtCore.QTimer.singleShot(0, self._clear_pan_flag)
            if replay:
                QtCore.QTimer.singleShot(
                    0, lambda pos=menu_pos: self._replay_context_menu(pos)
                )
            return False

        if event_type == QtCore.QEvent.ContextMenu and viewer._rmb_pan:
            viewer._rmb_pan = False
            event.accept()
            return True
        if (
            event_type == QtCore.QEvent.ContextMenu
            and not self._replaying_menu
            and self._right_button_held(viewer)
        ):
            self._menu_deferred = True
            self._menu_pos = self._viewport_pos(obj, event, viewport, viewer)
            event.accept()
            return True
        return False

    def _right_button_held(self, viewer):
        buttons = QtWidgets.QApplication.mouseButtons()
        return bool(buttons & QtCore.Qt.RightButton) or bool(viewer.RMB_state)

    def _viewport_pos(self, obj, event, viewport, viewer):
        if obj is viewport:
            return QtCore.QPoint(event.pos())
        return viewport.mapFrom(viewer, event.pos())

    def _replay_context_menu(self, pos):
        viewer = self._viewer
        try:
            viewport = viewer.viewport()
        except RuntimeError:
            return
        self._replaying_menu = True
        try:
            QtWidgets.QApplication.sendEvent(
                viewport,
                QtGui.QContextMenuEvent(
                    QtGui.QContextMenuEvent.Mouse,
                    pos,
                    viewport.mapToGlobal(pos),
                ),
            )
        finally:
            self._replaying_menu = False

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
