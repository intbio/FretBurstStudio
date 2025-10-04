import custom_widgets.sliders as sliders
from custom_widgets.plot_widget import TemplatePlotWidgetWtapper

    
    
class NodeBuilder():
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
    
    def build_int_slider(self, widget_name=None, range=[0, 10, 1], value=0):
        widget_name = widget_name if widget_name else f"intslider{len(self.node.widgets())}"
        int_slider = self.__build_slider_widget(widget_name, sliders.IntSliderWidget(widget_name, *range))
        int_slider.set_value(value)
        self.node.add_custom_widget(int_slider, tab='custom')
        return int_slider
        
    def build_float_slider(self, widget_name=None, range=[0, 10, 0.5], value=0):
        widget_name = widget_name if widget_name else f"floatslider{len(self.node.widgets())}"
        float_slider = self.__build_slider_widget(widget_name, sliders.FloatSliderWidget(widget_name, *range))
        float_slider.set_value(value)
        self.node.add_custom_widget(float_slider, tab='custom')
        return float_slider
        
    def __build_slider_widget(self, widget_name, slider_widget):
        slider_widget = sliders.SliderWidgetWrapper(self.node.view, slider_widget)
        slider_widget.set_name(widget_name)
        slider_widget.set_label(widget_name)
        return slider_widget
    
    def build_plot_widget(self, widget_name):
        plot_widget = TemplatePlotWidgetWtapper(parent=self.node.view)
        plot_widget.set_name(widget_name)
        self.node.add_custom_widget(plot_widget, tab='custom')
    

     
            
        





        
