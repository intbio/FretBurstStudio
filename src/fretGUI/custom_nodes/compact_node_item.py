from Qt import QtCore, QtGui, QtWidgets
from NodeGraphQt.qgraphics.node_base import NodeItem


class CompactNodeItem(NodeItem):
    """Node item that reserves only the space needed beside its widgets."""

    PORT_WIDGET_GAP = 3

    def set_description_tooltip(self, description):
        self._description_tooltip = description
        self.setToolTip(description)

    def draw_node(self):
        super().draw_node()
        description = getattr(self, '_description_tooltip', '')
        if description:
            self.setToolTip(description)

    def set_file_drop_target(self, active):
        """Show or hide the highlight used while files are dragged over this node."""
        highlight = getattr(self, '_file_drop_highlight', None)
        if highlight is None:
            highlight = QtWidgets.QGraphicsRectItem(self)
            highlight.setPen(QtGui.QPen(QtGui.QColor(47, 111, 237), 3))
            highlight.setBrush(QtGui.QColor(47, 111, 237, 40))
            highlight.setZValue(2000)
            highlight.setAcceptedMouseButtons(QtCore.Qt.NoButton)
            highlight.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
            self._file_drop_highlight = highlight
        if active:
            highlight.setRect(self.boundingRect().adjusted(1, 1, -1, -1))
            highlight.show()
        else:
            highlight.hide()

    def _calc_size_horizontal(self):
        _, height = super()._calc_size_horizontal()

        title_width = self._text_item.boundingRect().width()
        port_width = 0.0
        input_text_width = 0.0
        output_text_width = 0.0

        for port, text in self._input_items.items():
            if not port.isVisible():
                continue
            port_width = max(port_width, port.boundingRect().width())
            if text.isVisible():
                input_text_width = max(
                    input_text_width,
                    text.boundingRect().width(),
                )

        for port, text in self._output_items.items():
            if not port.isVisible():
                continue
            port_width = max(port_width, port.boundingRect().width())
            if text.isVisible():
                output_text_width = max(
                    output_text_width,
                    text.boundingRect().width(),
                )

        widget_width = max(
            (
                widget.boundingRect().width()
                for widget in self._widgets.values()
                if widget.isVisible()
            ),
            default=0.0,
        )

        if widget_width:
            side_width = (
                max(input_text_width, output_text_width)
                + self.PORT_WIDGET_GAP
            )
            content_width = widget_width + (2 * side_width)
        else:
            content_width = (
                input_text_width
                + output_text_width
                + port_width
                + (2 * self.PORT_WIDGET_GAP)
            )

        return max(title_width, content_width), height
