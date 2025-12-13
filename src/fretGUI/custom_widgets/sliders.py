from NodeGraphQt import NodeBaseWidget  
from Qt import QtWidgets, QtCore    
from abc import abstractmethod 
from custom_widgets.abstract_widget_wrapper import AbstractWidgetWrapper


     
class AbstractSliderWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(None)
        
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
        self.slider.valueChanged.connect(self.on_slider_moved)
        self.slider.valueChanged.connect(self.on_editing_finished)
        self.text_box.editingFinished.connect(self.on_editing_finished)        
        
    @abstractmethod
    def on_slider_moved(self):
        pass
    
    @abstractmethod
    def on_editing_finished(self):
        pass     
        
        
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
        self.slider.sliderReleased.emit()
    
    def on_editing_finished(self):
        textbox_val = int(self.text_box.text())
        self.slider.setValue(textbox_val)
        

class FloatSliderWidget(AbstractSliderWidget):
    def __init__(self, parent=None, start=0.0, stop=100.0, step=1.0, decimals=2):        
        
        self.start = float(start)
        self.stop = float(stop)
        self.step = float(step)
        self.decimals = decimals
        
        super().__init__(parent)

        num_steps = int((self.stop - self.start) / self.step)
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
    
    def on_slider_moved(self, slider_value):
        """Обработка движения слайдера"""
        float_value = self.slider_to_float(slider_value)
        formatted_value = self.format_float(float_value)
        self.text_box.setText(formatted_value)
    
    def on_editing_finished(self):
        """Обработка завершения редактирования текстового поля"""
        try:
            text_val = float(self.text_box.text().replace(',', '.'))
            clamped_val = max(self.start, min(text_val, self.stop))
            slider_val = self.float_to_slider(clamped_val)
            self.slider.setValue(slider_val)
            self.text_box.setText(self.format_float(clamped_val))
        except ValueError:
            current_slider = self.slider.value()
            current_float = self.slider_to_float(current_slider)
            self.text_box.setText(self.format_float(current_float))
    
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
    def __init__(self, parent, slider_widget: AbstractSliderWidget):
        self.slider_widget = slider_widget
        super().__init__(parent)
        
        self.set_name('Slider')
        self.set_custom_widget(self.slider_widget)
        
    def get_value(self):
        slider = self.get_custom_widget().slider
        slider_val = slider.value()
        return slider_val
    
    def set_value(self, value):
        text_box = self.get_custom_widget().text_box
        text_box.setText(str(value))
        slider = self.get_custom_widget().slider
        slider.setValue(value)
        
    def wire_signals(self):
        self.slider_widget.slider.sliderReleased.connect(
            self.widget_changed_signal.emit)

        
        
