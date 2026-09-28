"""Route external file drags to loader nodes or JSON session import."""

import os

from Qt import QtCore
from NodeGraphQt.qgraphics.node_abstract import AbstractNodeItem


def _event_pos(event):
    position = getattr(event, 'position', None)
    if callable(position):
        return position().toPoint()
    return event.pos()


def local_file_paths(mime):
    if mime is None:
        return []
    paths = []
    if mime.hasUrls():
        for url in mime.urls():
            path = url.toLocalFile()
            if path:
                paths.append(path)
    if paths:
        return paths
    if not mime.hasFormat('text/uri-list'):
        return []
    raw = bytes(mime.data('text/uri-list')).decode('utf-8', errors='replace')
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        path = QtCore.QUrl(line).toLocalFile()
        if path:
            paths.append(path)
    return paths


def _is_json_session(paths):
    return bool(paths) and all(
        os.path.splitext(path)[1].lower() == '.json'
        for path in paths
    )


class GraphFileDrop(QtCore.QObject):
    """Highlight a loader under a file drag and add the files on drop."""

    def __init__(self, graph):
        viewer = graph.viewer()
        super().__init__(viewer)
        self._graph = graph
        self._viewer = viewer
        self._highlighted = None
        self._original_drop = None
        self._last_drop = None

    def eventFilter(self, obj, event):
        viewer = self._viewer
        try:
            viewport = viewer.viewport()
        except RuntimeError:
            return False
        if obj is not viewer and obj is not viewport:
            return False
        event_type = event.type()
        if event_type == QtCore.QEvent.DragEnter:
            self._last_drop = None
        if event_type in (
            QtCore.QEvent.DragEnter,
            QtCore.QEvent.DragMove,
        ):
            return self._on_drag(event, self._view_pos(obj, event))
        if event_type == QtCore.QEvent.DragLeave:
            self._set_highlight(None)
            return False
        if event_type == QtCore.QEvent.Drop:
            return self._on_drop(event, self._view_pos(obj, event))
        return False

    def _view_pos(self, obj, event):
        pos = _event_pos(event)
        viewport = self._viewer.viewport()
        if obj is viewport:
            return pos
        return viewport.mapFrom(self._viewer, pos)

    def _on_drag(self, event, view_pos):
        paths = local_file_paths(event.mimeData())
        if not paths:
            return False
        node, accept, passthrough = self._classify(paths, view_pos)
        self._set_highlight(node if accept and node is not None else None)
        # DragEnter must be accepted or Qt never sends DragMove/Drop after the
        # cursor first touches empty canvas. DragMove then accepts or refuses
        # the current spot, which updates the cursor and the node highlight.
        if event.type() == QtCore.QEvent.DragEnter:
            event.acceptProposedAction()
            return True
        if passthrough:
            return False
        if accept:
            event.acceptProposedAction()
        else:
            event.ignore()
        return True

    def _on_drop(self, event, view_pos):
        paths = local_file_paths(event.mimeData())
        self._set_highlight(None)
        if not paths:
            return False
        node, accept, passthrough = self._classify(paths, view_pos)
        if passthrough:
            return False
        if accept and node is not None:
            self._give_files(node, paths)
            event.acceptProposedAction()
            return True
        event.ignore()
        return True

    def on_viewer_data_dropped(self, mime, scene_pos):
        """Stop NodeGraphQt from importing measurement files as JSON sessions."""
        paths = local_file_paths(mime)
        if not paths:
            self._original_drop(mime, scene_pos)
            return
        node = self._node_at_scene(scene_pos)
        if node is not None and hasattr(node, 'accepts_dropped_files'):
            if node.accepts_dropped_files(paths):
                self._give_files(node, paths)
            return
        if _is_json_session(paths):
            self._original_drop(mime, scene_pos)

    def _give_files(self, node, paths):
        token = tuple(paths)
        if token == self._last_drop:
            return
        self._last_drop = token
        QtCore.QTimer.singleShot(0, self._clear_last_drop)
        node.file_widget.path_widget.process_files(paths)

    def _clear_last_drop(self):
        self._last_drop = None

    def _classify(self, paths, view_pos):
        """Return (loader or None, accept, let the viewer import a session)."""
        node = self._node_at(view_pos)
        if node is not None and hasattr(node, 'accepts_dropped_files'):
            return node, bool(node.accepts_dropped_files(paths)), False
        if _is_json_session(paths):
            return None, True, True
        return None, False, False

    def _node_at(self, view_pos):
        return self._node_at_scene(self._viewer.mapToScene(view_pos))

    def _node_at_scene(self, scene_pos):
        point = QtCore.QPointF(scene_pos)
        for item in self._viewer.scene().items(point):
            node_item = item
            while (
                node_item is not None
                and not isinstance(node_item, AbstractNodeItem)
            ):
                node_item = node_item.parentItem()
            if node_item is None:
                continue
            node = self._graph.get_node_by_id(node_item.id)
            if node is not None:
                return node
        return None

    def _set_highlight(self, node):
        view = None if node is None else getattr(node, 'view', None)
        if view is not None and not hasattr(view, 'set_file_drop_target'):
            view = None
        if self._highlighted is not None and self._highlighted is not view:
            self._highlighted.set_file_drop_target(False)
        self._highlighted = view
        if view is not None:
            view.set_file_drop_target(True)


def enable_graph_file_drop(graph):
    """Install loader-aware file drops on a node graph."""
    viewer = graph.viewer()
    existing = getattr(viewer, '_graph_file_drop', None)
    if existing is not None:
        return existing
    drop = GraphFileDrop(graph)
    viewer.installEventFilter(drop)
    viewer.viewport().installEventFilter(drop)
    drop._original_drop = graph._on_node_data_dropped
    try:
        viewer.data_dropped.disconnect(graph._on_node_data_dropped)
    except (TypeError, RuntimeError):
        pass
    viewer.data_dropped.connect(drop.on_viewer_data_dropped)
    viewer._graph_file_drop = drop
    return drop
