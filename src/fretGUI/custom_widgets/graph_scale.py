"""Keep the node graph at the same scale when its widget is resized."""

from Qt import QtCore, QtWidgets


def _same_rect(a, b):
    return (
        abs(a.x() - b.x()) < 0.5
        and abs(a.y() - b.y()) < 0.5
        and abs(a.width() - b.width()) < 0.5
        and abs(a.height() - b.height()) < 0.5
    )


def keep_graph_scale_on_resize(viewer):
    """Replace NodeGraphQt's resize zoom with a larger or smaller view of the same scale.

    Layout shows the view through a few small sizes before the window is up.
    Fitting those and then keeping the scale leaves the graph zoomed out, so
    the original scene rectangle is only refitted until the user zooms or pans.
    After that, the rectangle grows with the viewport. fitInView can re-enter
    this handler; the nested call must not move the view under a right-drag.
    """
    if getattr(viewer, '_stable_scale_resize', False):
        return
    viewer._stable_base_range = QtCore.QRectF(viewer._scene_range)
    viewer._stable_viewport = None
    viewer._stable_resize_busy = False
    viewer._scale_locked = False

    def resize_event(event):
        if viewer._stable_resize_busy:
            return
        if event.size().width() <= 0 or event.size().height() <= 0:
            viewer.resize(viewer._last_size)
            return
        viewer._stable_resize_busy = True
        try:
            QtWidgets.QGraphicsView.resizeEvent(viewer, event)
            if not viewer._scale_locked and _same_rect(
                viewer._scene_range, viewer._stable_base_range
            ):
                viewer._update_scene()
                viewer._stable_viewport = viewer.viewport().size()
                viewer._last_size = viewer.size()
                return
            viewer._scale_locked = True
            viewport = viewer.viewport().size()
            previous = viewer._stable_viewport
            if (
                previous is not None
                and previous.width() > 0
                and previous.height() > 0
                and viewport != previous
            ):
                rect = viewer._scene_range
                viewer._scene_range = QtCore.QRectF(
                    rect.x(),
                    rect.y(),
                    rect.width() * viewport.width() / previous.width(),
                    rect.height() * viewport.height() / previous.height(),
                )
                viewer._update_scene()
                viewport = viewer.viewport().size()
            viewer._stable_viewport = viewport
            viewer._last_size = viewer.size()
        finally:
            viewer._stable_resize_busy = False

    viewer.resizeEvent = resize_event
    viewer._stable_scale_resize = True
