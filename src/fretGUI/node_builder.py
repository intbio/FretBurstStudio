import custom_widgets.sliders as sliders
from custom_widgets.plot_widget import TemplatePlotWidgetWtapper
import custom_nodes.custom_nodes as custom_nodes

    
    
class NodeBuilder():
    default_w_width= 100
    def __init__(self, node):
        self.__node = node
                
    @property
    def node(self):
        return self.__node
    
    @node.setter
    def node(self, new_node):
        self.__node = new_node         
        
    def build_textbox(self, widget_name=None):
        widget_name = widget_name if widget_name else f"textbox{len(self.node.widgets())}"
        self.node.add_text_input(widget_name, label=widget_name)
    
    def build_int_slider(self, widget_name=None, range=[0, 10, 1], value=0, tooltip=None, min_width=default_w_width):
        widget_name = widget_name if widget_name else f"intslider{len(self.node.widgets())}"
        int_slider = self.__build_slider_widget(widget_name, sliders.IntSliderWidget(widget_name, *range), tooltip, min_width)
        int_slider.set_value(value)
        self.node.add_custom_widget(int_slider, tab='custom')
        return int_slider
    
    def build_int_spinbox(self, widget_name=None, range=[0, 10, 1], value=0, tooltip=None, min_width=default_w_width):
        widget_name = widget_name if widget_name else f"intspinbox{len(self.node.widgets())}"
        int_spinbox = self.__build_spinbox_widget(widget_name, sliders.IntSpinBoxWidget(widget_name, *range), tooltip, min_width)
        int_spinbox.set_value(value)
        self.node.add_custom_widget(int_spinbox, tab='custom')
        return int_spinbox
        
    def build_float_slider(self, widget_name=None, range=[0, 10, 0.5], value=0, tooltip=None, min_width=default_w_width):
        widget_name = widget_name if widget_name else f"floatslider{len(self.node.widgets())}"
        float_slider = self.__build_slider_widget(widget_name, sliders.FloatSliderWidget(widget_name, *range), tooltip, min_width)
        float_slider.set_value(value)
        self.node.add_custom_widget(float_slider, tab='custom')
        return float_slider
    
    def build_float_spinbox(self, widget_name=None, range=[0, 10, 0.5], value=0, tooltip=None, min_width=default_w_width):
        widget_name = widget_name if widget_name else f"floatspinbox{len(self.node.widgets())}"
        float_spinbox = self.__build_spinbox_widget(widget_name, sliders.FloatSpinBoxWidget(widget_name, *range), tooltip, min_width)
        float_spinbox.set_value(value)
        self.node.add_custom_widget(float_spinbox, tab='custom')
        return float_spinbox
        
    def __build_slider_widget(self, widget_name, slider_widget, tooltip=None, min_width=default_w_width):
        slider_widget = sliders.SliderWidgetWrapper(self.node.view, slider_widget, min_width)
        slider_widget.set_name(widget_name)
        slider_widget.set_label(widget_name)
        if tooltip:
            slider_widget.setToolTip(tooltip)
        return slider_widget
    
    def __build_spinbox_widget(self, widget_name, spinbox_widget, tooltip=None, min_width=default_w_width):
        spinbox_widget = sliders.SpinBoxWidgetWrapper(self.node.view, spinbox_widget, min_width)
        spinbox_widget.set_name(widget_name)
        spinbox_widget.set_label(widget_name)
        if tooltip:
            spinbox_widget.setToolTip(tooltip)
        return spinbox_widget
    
    def build_combobox(self, widget_name=None, items=None, value=None, tooltip=None, min_width=default_w_width):
        widget_name = widget_name if widget_name else f"combobox{len(self.node.widgets())}"
        combobox = self.__build_combobox_widget(widget_name, sliders.ComboBoxWidget(widget_name, items), tooltip, min_width)
        if value is not None:
            combobox.set_value(value)
        self.node.add_custom_widget(combobox, tab='custom')
        return combobox
    
    def __build_combobox_widget(self, widget_name, combobox_widget, tooltip=None, min_width=default_w_width):
        combobox_widget = sliders.ComboBoxWidgetWrapper(self.node.view, combobox_widget, min_width)
        combobox_widget.set_name(widget_name)
        combobox_widget.set_label(widget_name)
        if tooltip:
            combobox_widget.setToolTip(tooltip)
        return combobox_widget
        
    def build_html_label(self, widget_name=None, html_text="", word_wrap=True, tooltip=None, min_width=default_w_width):
        widget_name = widget_name if widget_name else f"htmllabel{len(self.node.widgets())}"
        html_label = self.__build_html_label_widget(widget_name, sliders.HtmlLabelWidget(widget_name, html_text, word_wrap), tooltip, min_width)
        if html_text:
            html_label.set_value(html_text)
        self.node.add_custom_widget(html_label, tab='custom')
        return html_label
    
    def __build_html_label_widget(self, widget_name, html_label_widget, tooltip=None, min_width=default_w_width):
        html_label_widget = sliders.HtmlLabelWidgetWrapper(self.node.view, html_label_widget, min_width)
        html_label_widget.set_name(widget_name)
        html_label_widget.set_label(widget_name)
        if tooltip:
            html_label_widget.setToolTip(tooltip)
        return html_label_widget
    
    def build_plot_widget(self, widget_name, mpl_width=None, mpl_height=None):
        plot_widget = TemplatePlotWidgetWtapper(parent=self.node.view, mpl_width=mpl_width, mpl_height=mpl_height)
        plot_widget.set_name(widget_name)
        self.node.add_custom_widget(plot_widget, tab='custom')
    
        





        
