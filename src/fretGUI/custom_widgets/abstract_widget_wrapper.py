from Qt import QtCore, QtGui, QtWidgets
from Qt.QtCore import Signal, QTimer
from abc import abstractmethod
from NodeGraphQt import NodeBaseWidget
from functools import wraps


class _CompactNodeWidgetContainer(QtWidgets.QWidget):
    """Compact replacement for NodeGraphQt's non-wrapping group-box title."""

    def __init__(self, label='', parent=None):
        super().__init__(parent)
        self._node_widget = None
        self.setObjectName('compactNodeWidgetContainer')
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setStyleSheet(
            'QWidget#compactNodeWidgetContainer { background: transparent; }'
        )

        self._label = QtWidgets.QLabel()
        self._label.setWordWrap(True)
        self._label.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        label_font = self._label.font()
        label_font.setPointSize(8)
        self._label.setFont(label_font)
        self._apply_label_style()
        self._label.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Minimum,
        )

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 3)
        self._layout.setSpacing(0)
        self._layout.addWidget(self._label)
        self.setTitle(label)

    def setTitle(self, text):
        self._label.setText(text)
        self._label.setVisible(bool(text))

    def setTitleAlign(self, align='center'):
        alignments = {
            'left': QtCore.Qt.AlignLeft,
            'center': QtCore.Qt.AlignHCenter,
            'right': QtCore.Qt.AlignRight,
        }
        self._label.setAlignment(
            alignments.get(align, QtCore.Qt.AlignHCenter)
            | QtCore.Qt.AlignTop
        )

    def _apply_label_style(self, color=None):
        color_rule = ''
        if color is not None:
            qcolor = (
                color
                if isinstance(color, QtGui.QColor)
                else QtGui.QColor(*color)
            )
            color_rule = (
                f' color: rgb({qcolor.red()}, {qcolor.green()}, '
                f'{qcolor.blue()});'
            )
        self._label.setStyleSheet(
            'QLabel { background: transparent; margin: 0; padding: 0;'
            f'{color_rule} }}'
        )

    def set_text_color(self, color):
        """Apply the active graph theme to labels and embedded controls."""
        qcolor = color if isinstance(color, QtGui.QColor) else QtGui.QColor(*color)
        self._apply_label_style(qcolor)
        for child in [self, *self.findChildren(QtWidgets.QWidget)]:
            palette = child.palette()
            palette.setColor(QtGui.QPalette.WindowText, qcolor)
            palette.setColor(QtGui.QPalette.Text, qcolor)
            palette.setColor(QtGui.QPalette.ButtonText, qcolor)
            child.setPalette(palette)

    def set_theme(self, kind, colors):
        """Apply control backgrounds immediately inside a graphics proxy."""
        self.set_text_color(colors['text'])
        role_colors = {
            QtGui.QPalette.Window: colors['window'],
            QtGui.QPalette.WindowText: colors['text'],
            QtGui.QPalette.Base: colors['base'],
            QtGui.QPalette.AlternateBase: colors['alternate_base'],
            QtGui.QPalette.Text: colors['text'],
            QtGui.QPalette.Button: colors['button'],
            QtGui.QPalette.ButtonText: colors['text'],
            QtGui.QPalette.Highlight: colors['highlight'],
            QtGui.QPalette.HighlightedText: colors['highlighted_text'],
        }
        widgets = [self, *self.findChildren(QtWidgets.QWidget)]
        for widget in widgets:
            palette = widget.palette()
            for role, color in role_colors.items():
                palette.setColor(role, QtGui.QColor(*color))
            widget.setPalette(palette)

        self.setStyleSheet(f"""
            QWidget#compactNodeWidgetContainer {{
                background: transparent;
            }}
            QLineEdit {{
                background-color: rgb{colors['base']};
                color: rgb{colors['text']};
                border: 1px solid rgb{colors['grid']};
            }}
            QComboBox QAbstractItemView {{
                background-color: rgb{colors['base']};
                color: rgb{colors['text']};
                selection-background-color: rgb{colors['highlight']};
                selection-color: rgb{colors['highlighted_text']};
            }}
        """)
        for widget in widgets:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            if isinstance(widget, QtWidgets.QAbstractItemView):
                widget.viewport().update()
            else:
                widget.update()

    def add_node_widget(self, widget):
        self._node_widget = widget
        self._layout.addWidget(widget)

    def get_node_widget(self):
        return self._node_widget


def debounce(wait_ms):
    timer = QTimer()
    timer.setSingleShot(True)
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            timer.stop()
            try:
                timer.timeout.disconnect()
            except TypeError:
                pass # Ignore if not connected yet
            timer.timeout.connect(lambda: func(*args, **kwargs))
            timer.start(wait_ms)
        wrapper.timer = timer
        return wrapper
    return decorator



class AbstractWidgetWrapper(NodeBaseWidget):
    
    widget_changed_signal = Signal()
    debounced_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wire_signals()
        self.widget_changed_signal.connect(self.__on_debounced_widget_update)

    def set_custom_widget(self, widget):
        """Embed a control under a compact, word-wrapped field label."""
        if self.widget():
            raise RuntimeError('Custom node widget already set.')
        container = _CompactNodeWidgetContainer(self.get_label())
        container.add_node_widget(widget)
        self.setWidget(container)
        
    def setEnabled(self, bool_value: bool):
        widget = self.get_custom_widget()
        widget.setEnabled(bool_value)
    
    @abstractmethod
    def wire_signals(self):
        pass
    
    @debounce(500)
    def __on_debounced_widget_update(self):
        self.debounced_signal.emit()
            
        
        
        
        
    
    

     
    
    
    

    
    