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


class LoaderNodeItem(CompactNodeItem):
    """Loader nodes size from file-list content, not CompactNodeItem side pads."""

    LEFT_PAD = 10.0
    RIGHT_PAD = 8.0
    TITLE_PAD = 20.0

    def _loader_content_width(self):
        from fretGUI.custom_widgets.path_selector import PathSelectorWidget
        return float(PathSelectorWidget.DEFAULT_WIDTH)

    def _calc_size_horizontal(self):
        # Width: snug file-list content (no CompactNodeItem mirrored port pads).
        # Height: widget stack only — NodeItem._draw_node_horizontal adds the
        # title via add_h; including it here double-counts and flashes tall.
        content_width = self._loader_content_width()
        widget_width = content_width
        widget_height = 0.0
        for widget in self._widgets.values():
            if not widget.isVisible():
                continue
            rect = widget.boundingRect()
            widget_width = max(widget_width, rect.width())
            widget_height += rect.height()

        width = widget_width + self.LEFT_PAD + self.RIGHT_PAD
        title_width = self._text_item.boundingRect().width() + self.TITLE_PAD
        title_h = self._text_item.boundingRect().height() + 4.0
        body_height = widget_height + 4.0
        # After add_h=title_h, match AbstractLoader's max(90, title+widgets+4).
        height = max(90.0 - title_h, body_height)
        return max(width, title_width), height

    def draw_node(self):
        callback = getattr(self, '_after_draw_callback', None)
        # Pin file/advanced widgets before NodeGraphQt measures them so the
        # first draw_node pass does not flash a wrong size.
        if callable(callback):
            callback()
        super().draw_node()
        if callable(callback):
            callback()
