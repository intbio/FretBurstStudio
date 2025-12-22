from NodeGraphQt import NodeBaseWidget  
from Qt import QtWidgets, QtCore      # pyright: ignore[reportMissingModuleSource]
from abc import abstractmethod 
from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper
from Qt.QtCore import Signal


     
class AbstractSliderWidget(QtWidgets.QWidget):
    
    widget_updaeted = Signal()
    
    def __init__(self, parent):
        super().__init__(None)
        
        self.changed = False
        
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setTickPosition(QtWidgets.QSlider.TicksAbove)
        
        self.text_box = QtWidgets.QLineEdit(text='...')
        self.text_box.setFixedSize(60, 30)
        
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.addWidget(self.text_box, alignment=QtCore.Qt.AlignCenter)
        self.layout.addWidget(self.slider, alignment=QtCore.Qt.AlignBottom)
        self.layout.setContentsMargins(3, 3, 3, 3)
        
        self.wire_signals()
        
    def wire_signals(self):
        self.slider.sliderReleased.connect(self.widget_updaeted.emit)
        self.slider.valueChanged.connect(self.on_slider_moved)
        self.text_box.editingFinished.connect(self.on_editing_finished)      
        self.text_box.textEdited.connect(self.on_text_change)
        
    def on_text_change(self, text: str):
        self.changed = True
        
    @abstractmethod
    def on_slider_moved(self):
        pass
        
    def on_editing_finished(self):
        if self.changed:
            self.widget_updaeted.emit()
            self.changed = False
        
        
class IntSliderWidget(AbstractSliderWidget):
    def __init__(self, parent=None, start=0, stop=100, step=1):
        self.start = int(start)
        self.stop = int(stop)
        self.step = int(step)
        
        super().__init__(parent)
        self.slider.setMinimum(self.start)
        self.slider.setMaximum(self.stop)
        self.slider.setTickInterval(self.step)

    def on_slider_moved(self):
        slider_val = self.slider.value()
        index = (slider_val - self.slider.minimum()) // self.step
        lower_val = max(self.slider.minimum() + index * self.step, self.slider.minimum())
        upper_val = min(self.slider.minimum() + (index + 1) * self.step, self.slider.maximum())
        if slider_val - lower_val <= upper_val - slider_val:
            new_val = lower_val
        else:
            new_val = upper_val
        self.slider.setValue(new_val)
        self.text_box.setText(str(new_val))
        
    
    def on_editing_finished(self):
        textbox_val = int(self.text_box.text())
        self.setValue(textbox_val)
        super().on_editing_finished()
    
    def value(self):
        """Возвращает текущее int значение"""
        return self.slider.value()
    
    def setValue(self, int_value):
        """Устанавливает int значение"""
        # clamped_val = max(self.start, min(int(int_value), self.stop))
        clamped_val = int_value
        self.slider.setValue(clamped_val)
        self.text_box.setText(str(clamped_val))
        

class FloatSliderWidget(AbstractSliderWidget):
    def __init__(self, parent=None, start=0.0, stop=100.0, step=1.0, decimals=2):        
        
        self.start = float(start)
        self.stop = float(stop)
        self.step = float(step)
        self.decimals = decimals
        
        super().__init__(parent)

        num_steps = int((self.stop - self.start) / self.step)
        # Set slider range to 0 to num_steps (slider represents step indices)
        self.slider.setMinimum(0)
        self.slider.setMaximum(num_steps)
        self.text_box.setText(self.format_float(self.start))
    
    def format_float(self, value):
        """Форматирование float значения с заданной точностью"""
        return f"{value:.{self.decimals}f}"
    
    def slider_to_float(self, slider_value):
        """Преобразование значения слайдера в float"""
        return self.start + slider_value * self.step
    
    def float_to_slider(self, float_value):
        """Преобразование float значения в значение слайдера"""
        normalized = (float_value - self.start) / self.step
        return int(round(normalized))
    
    def on_slider_moved(self):
        """Обработка движения слайдера"""
        slider_value = self.slider.value() 
        float_value = self.slider_to_float(slider_value)
        formatted_value = self.format_float(float_value)
        self.text_box.setText(formatted_value)
    
    def on_editing_finished(self):
        """Обработка завершения редактирования текстового поля"""
        try:
            text_val = float(self.text_box.text().replace(',', '.'))
            clamped_val = text_val
            slider_val = self.float_to_slider(clamped_val)
            self.slider.setValue(slider_val)
            self.text_box.setText(self.format_float(clamped_val))
        except ValueError:
            current_slider = self.slider.value()
            current_float = self.slider_to_float(current_slider)
            self.text_box.setText(self.format_float(current_float))
        super().on_editing_finished()
    
    def value(self):
        """Возвращает текущее float значение"""
        return self.slider_to_float(self.slider.value())
    
    def setValue(self, float_value):
        """Устанавливает float значение"""
        clamped_val = max(self.start, min(float(float_value), self.stop))
        slider_val = self.float_to_slider(clamped_val)
        self.slider.setValue(slider_val)
        self.text_box.setText(self.format_float(clamped_val))  
    
        
class SliderWidgetWrapper(AbstractWidgetWrapper):
    def __init__(self, parent, slider_widget: AbstractSliderWidget, min_width=None):
        self.slider_widget = slider_widget
        super().__init__(parent)
        
        self.set_name('Slider')
        self.set_custom_widget(self.slider_widget)
        
        # Set minimum width if specified
        if min_width is not None:
            self.setMinimumWidth(min_width)
            # Also set on the custom widget if it's a QWidget
            if hasattr(self.slider_widget, 'setMinimumWidth'):
                self.slider_widget.setMinimumWidth(min_width)
    
    def get_value(self):
        # Return the converted float value, not the raw slider integer
        return self.get_custom_widget().value()
    
    def set_value(self, value):
        # Use the widget's setValue method which handles conversion properly
        self.get_custom_widget().setValue(value)
    
    def wire_signals(self):
        self.slider_widget.widget_updaeted.connect(
            self.widget_changed_signal.emit)


class IntSpinBoxWidget(QtWidgets.QWidget):
    widget_updaeted = Signal()
    
    def __init__(self, parent=None, start=0, stop=100, step=1):
        super().__init__(None)
        
        self.start = int(start)
        self.stop = int(stop)
        self.step = int(step)
        
        self.spinbox = QtWidgets.QSpinBox()
        self.spinbox.setMinimum(self.start)
        self.spinbox.setMaximum(self.stop)
        self.spinbox.setSingleStep(self.step)
        
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.addWidget(self.spinbox)
        self.layout.setContentsMargins(3, 3, 3, 3)
        
        # Use lambda to ignore the value argument from valueChanged
        self.spinbox.valueChanged.connect(lambda val: self.widget_updaeted.emit())
    
    def value(self):
        """Возвращает текущее int значение"""
        return self.spinbox.value()
    
    def setValue(self, int_value):
        """Устанавливает int значение"""
        clamped_val = max(self.start, min(int(int_value), self.stop))
        self.spinbox.setValue(clamped_val)


class FloatSpinBoxWidget(QtWidgets.QWidget):
    widget_updaeted = Signal()
    
    def __init__(self, parent=None, start=0.0, stop=100.0, step=1.0, decimals=2):
        super().__init__(None)
        
        self.start = float(start)
        self.stop = float(stop)
        self.step = float(step)
        self.decimals = decimals
        
        self.spinbox = QtWidgets.QDoubleSpinBox()
        self.spinbox.setMinimum(self.start)
        self.spinbox.setMaximum(self.stop)
        self.spinbox.setSingleStep(self.step)
        self.spinbox.setDecimals(self.decimals)
        
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.addWidget(self.spinbox)
        self.layout.setContentsMargins(3, 3, 3, 3)
        
        # Use lambda to ignore the value argument from valueChanged
        self.spinbox.valueChanged.connect(lambda val: self.widget_updaeted.emit())
    
    def value(self):
        """Возвращает текущее float значение"""
        return self.spinbox.value()
    
    def setValue(self, float_value):
        """Устанавливает float значение"""
        clamped_val = max(self.start, min(float(float_value), self.stop))
        self.spinbox.setValue(clamped_val)


class SpinBoxWidgetWrapper(AbstractWidgetWrapper):
    def __init__(self, parent, spinbox_widget, min_width=None):
        self.spinbox_widget = spinbox_widget
        super().__init__(parent)
        
        self.set_name('SpinBox')
        self.set_custom_widget(self.spinbox_widget)
        
        # Set minimum width if specified
        if min_width is not None:
            self.setMinimumWidth(min_width)
            # Also set on the custom widget if it's a QWidget
            if hasattr(self.spinbox_widget, 'setMinimumWidth'):
                self.spinbox_widget.setMinimumWidth(min_width)
    
    def get_value(self):
        return self.get_custom_widget().value()
    
    def set_value(self, value):
        self.get_custom_widget().setValue(value)
    
    def wire_signals(self):
        self.spinbox_widget.widget_updaeted.connect(
            self.widget_changed_signal.emit)


class ComboBoxWidget(QtWidgets.QWidget):
    widget_updaeted = Signal()
    
    def __init__(self, parent=None, items=None):
        super().__init__(None)
        
        self.combobox = QtWidgets.QComboBox()
        
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.addWidget(self.combobox)
        self.layout.setContentsMargins(3, 3, 3, 3)
        
        if items is not None:
            self.setItems(items)
        
        # Connect signal
        self.combobox.currentTextChanged.connect(lambda text: self.widget_updaeted.emit())
    
    def value(self):
        """Returns the currently selected item text"""
        return self.combobox.currentText()
    
    def setValue(self, value):
        """Sets the selected item by text value"""
        index = self.combobox.findText(str(value))
        if index >= 0:
            self.combobox.setCurrentIndex(index)
        else:
            # If value not found, select first item
            if self.combobox.count() > 0:
                self.combobox.setCurrentIndex(0)
    
    def setItems(self, items):
        """Sets items from a list while preserving selected item if it's in the new list"""
        if not items:
            self.combobox.clear()
            return
        
        # Get current selection before clearing
        current_text = self.combobox.currentText()
        
        # Clear and add new items
        self.combobox.clear()
        self.combobox.addItems([str(item) for item in items])
        
        # Try to restore previous selection if it exists in new items
        item_strings = [str(item) for item in items]
        if current_text in item_strings:
            self.combobox.setCurrentText(current_text)
        else:
            # If previous selection not in new list, select first item
            if self.combobox.count() > 0:
                self.combobox.setCurrentIndex(0)
    
    def items(self):
        """Returns list of all items"""
        return [self.combobox.itemText(i) for i in range(self.combobox.count())]


class ComboBoxWidgetWrapper(AbstractWidgetWrapper):
    def __init__(self, parent, combobox_widget, min_width=None):
        self.combobox_widget = combobox_widget
        super().__init__(parent)
        
        self.set_name('ComboBox')
        self.set_custom_widget(self.combobox_widget)
        
        # Set minimum width if specified
        if min_width is not None:
            self.setMinimumWidth(min_width)
            # Also set on the custom widget if it's a QWidget
            if hasattr(self.combobox_widget, 'setMinimumWidth'):
                self.combobox_widget.setMinimumWidth(min_width)
    
    def get_value(self):
        return self.get_custom_widget().value()
    
    def set_value(self, value):
        self.get_custom_widget().setValue(value)
    
    def set_items(self, items):
        """Convenience method to set items from wrapper"""
        self.get_custom_widget().setItems(items)
    
    def wire_signals(self):
        self.combobox_widget.widget_updaeted.connect(
            self.widget_changed_signal.emit)
        
        
        
