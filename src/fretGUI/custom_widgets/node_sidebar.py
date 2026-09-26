from collections import defaultdict
from html import escape

from Qt import QtCore, QtGui, QtWidgets
from NodeGraphQt.constants import MIME_TYPE, URN_SCHEME


CATEGORY_ROLE = QtCore.Qt.UserRole
NODE_TYPE_ROLE = QtCore.Qt.UserRole + 1


class NodeItemDelegate(QtWidgets.QStyledItemDelegate):
    """Draw node entries as compact draggable cards."""

    def paint(self, painter, option, index):
        if index.data(CATEGORY_ROLE):
            category_option = QtWidgets.QStyleOptionViewItem(option)
            category_option.rect = option.rect.adjusted(16, 0, 0, 0)
            super().paint(painter, category_option, index)

            center_y = option.rect.center().y()
            left = option.rect.left() + 4
            if option.widget.isExpanded(index):
                points = (
                    QtCore.QPointF(left, center_y - 3),
                    QtCore.QPointF(left + 7, center_y - 3),
                    QtCore.QPointF(left + 3.5, center_y + 3),
                )
            else:
                points = (
                    QtCore.QPointF(left + 1, center_y - 4),
                    QtCore.QPointF(left + 1, center_y + 4),
                    QtCore.QPointF(left + 6, center_y),
                )
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(option.palette.text())
            painter.drawPolygon(QtGui.QPolygonF(points))
            painter.restore()
            return

        if not index.data(NODE_TYPE_ROLE):
            super().paint(painter, option, index)
            return

        card_rect = option.rect.adjusted(3, 2, -3, -2)
        selected = option.state & QtWidgets.QStyle.State_Selected
        hovered = option.state & QtWidgets.QStyle.State_MouseOver
        palette = option.palette

        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        background = (
            palette.highlight().color()
            if selected
            else palette.button().color()
        )
        if hovered and not selected:
            background = background.lighter(105)
        painter.setBrush(background)
        painter.setPen(QtGui.QPen(palette.mid().color(), 1))
        painter.drawRoundedRect(card_rect, 4, 4)
        painter.restore()

        item_option = QtWidgets.QStyleOptionViewItem(option)
        item_option.rect = card_rect.adjusted(8, 0, -4, 0)
        item_option.state &= ~QtWidgets.QStyle.State_Selected
        if selected:
            item_option.palette.setColor(
                QtGui.QPalette.Text,
                palette.highlightedText().color(),
            )
        super().paint(painter, item_option, index)


class NodeTreeWidget(QtWidgets.QTreeWidget):
    """Collapsible tree of node types that can be dragged onto a graph."""

    CATEGORY_LABELS = {
        'nodeGraphQt.nodes': 'Builtin Nodes',
        'nodes.custom.ports': 'Custom Port Nodes',
        'nodes.widget': 'Widget Nodes',
        'nodes.basic': 'Basic Nodes',
        'nodes.group': 'Group Nodes',
    }
    CATEGORY_ORDER = ('Loaders', 'Analysis', 'Selectors', 'Plot')

    def __init__(self, node_graph, parent=None):
        super().__init__(parent)
        self._node_graph = node_graph
        self._drag_start_position = None
        self._drag_item = None
        self.setHeaderHidden(True)
        self.setUniformRowHeights(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self.setDragEnabled(True)
        self.setRootIsDecorated(False)
        self.setIndentation(6)
        self.setMouseTracking(True)
        self.setItemDelegate(NodeItemDelegate(self))
        self.refresh()
        node_graph.nodes_registered.connect(self.refresh)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if (
            event.button() == QtCore.Qt.LeftButton
            and item is not None
            and item.data(0, CATEGORY_ROLE)
        ):
            item.setExpanded(not item.isExpanded())
            event.accept()
            return
        if (
            event.button() == QtCore.Qt.LeftButton
            and item is not None
            and item.data(0, NODE_TYPE_ROLE)
        ):
            self._drag_start_position = event.pos()
            self._drag_item = item
            event.accept()
            return
        self._drag_start_position = None
        self._drag_item = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_item is not None
            and event.buttons() & QtCore.Qt.LeftButton
            and (
                event.pos() - self._drag_start_position
            ).manhattanLength() >= QtWidgets.QApplication.startDragDistance()
        ):
            drag = QtGui.QDrag(self)
            drag.setMimeData(self.mimeData([self._drag_item]))
            item_rect = self.visualItemRect(self._drag_item)
            drag.setPixmap(self.viewport().grab(item_rect))
            drag.setHotSpot(self._drag_start_position - item_rect.topLeft())
            drag.exec(QtCore.Qt.CopyAction)
            self._drag_start_position = None
            self._drag_item = None
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_item is not None:
            self._drag_start_position = None
            self._drag_item = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def refresh(self, *_):
        expanded_categories = {
            self.topLevelItem(index).data(0, CATEGORY_ROLE)
            for index in range(self.topLevelItemCount())
            if self.topLevelItem(index).isExpanded()
        }
        first_build = self.topLevelItemCount() == 0

        grouped_nodes = defaultdict(list)
        for node_name, node_ids in self._node_graph.node_factory.names.items():
            for node_id in node_ids:
                category = '.'.join(node_id.split('.')[:-1])
                if category == 'nodeGraphQt.nodes':
                    continue
                node_class = self._node_graph.node_factory.nodes.get(node_id)
                description = getattr(node_class, 'DESCRIPTION', '')
                grouped_nodes[category].append(
                    (node_name, node_id, description)
                )

        priority = {
            category: index for index, category in enumerate(self.CATEGORY_ORDER)
        }

        self.clear()
        for category in sorted(
            grouped_nodes,
            key=lambda value: (priority.get(value, len(priority)), value.lower()),
        ):
            category_item = QtWidgets.QTreeWidgetItem(
                [self.CATEGORY_LABELS.get(category, category)]
            )
            category_item.setData(0, CATEGORY_ROLE, category)
            category_item.setFlags(
                QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
            )
            font = category_item.font(0)
            font.setBold(True)
            category_item.setFont(0, font)
            self.addTopLevelItem(category_item)

            for node_name, node_id, description in sorted(
                grouped_nodes[category], key=lambda value: value[0].lower()
            ):
                node_item = QtWidgets.QTreeWidgetItem([node_name])
                node_item.setData(0, NODE_TYPE_ROLE, node_id)
                node_item.setToolTip(
                    0,
                    (
                        "<div style='white-space: normal; width: 320px;'>"
                        f"{escape(description)}"
                        "</div>"
                    ),
                )
                node_item.setFlags(
                    QtCore.Qt.ItemIsEnabled
                    | QtCore.Qt.ItemIsSelectable
                    | QtCore.Qt.ItemIsDragEnabled
                )
                category_item.addChild(node_item)

            category_item.setExpanded(
                first_build or category in expanded_categories
            )

    def mimeData(self, items):
        node_ids = [
            item.data(0, NODE_TYPE_ROLE)
            for item in items
            if item.data(0, NODE_TYPE_ROLE)
        ]
        mime_data = QtCore.QMimeData()
        if node_ids:
            node_urn = URN_SCHEME + ';'.join(
                'node:{}'.format(node_id) for node_id in node_ids
            )
            mime_data.setData(
                MIME_TYPE,
                QtCore.QByteArray(node_urn.encode()),
            )
        return mime_data


class NodeSidebar(QtWidgets.QFrame):
    """Controls and a node browser that folds up over the graph."""

    WIDTH = 280
    MAX_WIDGET_SIZE = 16777215

    def __init__(
        self,
        node_graph,
        run_button,
        auto_toggle,
        progress_bar,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName('nodeSidebar')
        self.setFixedWidth(self.WIDTH)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(run_button, stretch=1)
        controls.addWidget(auto_toggle)
        layout.addLayout(controls)

        self.progress_container = QtWidgets.QWidget(self)
        self.progress_container.setFixedHeight(36)
        progress_layout = QtWidgets.QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        progress_layout.addWidget(progress_bar)
        layout.addWidget(self.progress_container)

        self.collapse_button = QtWidgets.QToolButton(self)
        self.collapse_button.setObjectName('nodeSidebarCollapseButton')
        self.collapse_button.setCheckable(True)
        self.collapse_button.setFixedHeight(16)
        self.collapse_button.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed,
        )
        self.collapse_button.setText('▲')
        self.collapse_button.setToolTip('Collapse node menu')
        self.collapse_button.setAccessibleName('Collapse node menu')
        self.collapse_button.toggled.connect(self.set_nodes_collapsed)
        layout.addWidget(self.collapse_button)

        self.node_container = QtWidgets.QWidget(self)
        node_layout = QtWidgets.QVBoxLayout(self.node_container)
        node_layout.setContentsMargins(0, 0, 0, 0)
        node_layout.setSpacing(8)

        title = QtWidgets.QLabel('Nodes', self.node_container)
        title.setObjectName('nodeSidebarTitle')
        node_layout.addWidget(title)

        self.node_tree = NodeTreeWidget(node_graph, self.node_container)
        node_layout.addWidget(self.node_tree, stretch=1)
        layout.addWidget(self.node_container, stretch=1)

    def set_nodes_collapsed(self, collapsed):
        """Fold the node menu up while leaving its controls over the graph."""
        self.node_container.setVisible(not collapsed)
        self.setProperty('collapsed', collapsed)
        parent = self.parentWidget()
        parent_layout = parent.layout() if parent is not None else None
        if collapsed:
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Fixed,
                QtWidgets.QSizePolicy.Fixed,
            )
            self.setFixedHeight(self.sizeHint().height())
            if parent_layout is not None:
                parent_layout.setAlignment(
                    self,
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop,
                )
        else:
            self.setMinimumHeight(0)
            self.setMaximumHeight(self.MAX_WIDGET_SIZE)
            self.setSizePolicy(
                QtWidgets.QSizePolicy.Fixed,
                QtWidgets.QSizePolicy.Expanding,
            )
            if parent_layout is not None:
                parent_layout.setAlignment(self, QtCore.Qt.AlignLeft)
        self.collapse_button.setText('▼' if collapsed else '▲')
        action = 'Expand' if collapsed else 'Collapse'
        self.collapse_button.setToolTip(f'{action} node menu')
        self.collapse_button.setAccessibleName(f'{action} node menu')
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_theme(self, colors):
        self.setStyleSheet(
            f"""
            QFrame#nodeSidebar {{
                background-color: rgb{colors['window']};
                border: 0px;
                border-right: 1px solid rgb{colors['grid']};
            }}
            QFrame#nodeSidebar[collapsed="true"] {{
                border-bottom: 1px solid rgb{colors['grid']};
            }}
            QLabel#nodeSidebarTitle {{
                color: rgb{colors['text']};
                font-weight: bold;
                padding: 2px;
            }}
            QToolButton#nodeSidebarCollapseButton {{
                background-color: rgb{colors['button']};
                color: rgb{colors['text']};
                border: 1px solid rgb{colors['grid']};
                border-radius: 3px;
                padding: 0px;
            }}
            QToolButton#nodeSidebarCollapseButton:hover {{
                background-color: rgb{colors['button_hover']};
            }}
            QTreeWidget {{
                background-color: rgb{colors['base']};
                color: rgb{colors['text']};
                border: 1px solid rgb{colors['grid']};
            }}
            QTreeWidget::item {{
                min-height: 24px;
                padding: 2px;
            }}
            QTreeWidget::item:selected {{
                background-color: rgb{colors['highlight']};
                color: rgb{colors['highlighted_text']};
            }}
            """
        )
