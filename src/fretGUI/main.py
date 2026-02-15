# Essential imports only - these are fast
import sys
import os
import signal
from pathlib import Path
from Qt import QtWidgets, QtCore, QtGui


def main():
    THEME = 'light'
    # handle SIGINT to make the app terminate on CTRL+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # Create QApplication immediately
    app = QtWidgets.QApplication(sys.argv)
    
    # Show splash screen ASAP
    BASE_PATH = Path(__file__).parent.resolve()
    
    # Load logo image
    logo_path = BASE_PATH / 'static' / 'fb_logo.png'
    
    if logo_path.exists():
        # Use the logo as the base pixmap
        splash_pixmap = QtGui.QPixmap(str(logo_path))
        # Scale if needed (optional)
        # splash_pixmap = splash_pixmap.scaled(600, 400, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    else:
        # Fallback if logo not found
        splash_pixmap = QtGui.QPixmap(500, 300)
        splash_pixmap.fill(QtGui.QColor(240, 240, 240))
    
    splash = QtWidgets.QSplashScreen(splash_pixmap)
    
    splash.setStyleSheet("""
        QSplashScreen {
            background-color: rgb(240, 240, 240);
            color: rgb(30, 30, 30);
            font-size: 16pt;
            font-weight: bold;
        }
    """)
    
    splash.showMessage(
        "FRETBursts Studio Loading...",
        QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom,
        QtGui.QColor(30, 30, 30)
    )
    splash.show()
    app.processEvents()
    
    # Now import heavy modules while splash is showing
    splash.showMessage("Loading modules...", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom, QtGui.QColor(30, 30, 30))
    app.processEvents()
    
    import custom_nodes.custom_nodes as custom_nodes
    import custom_nodes.selector_nodes as selector_nodes
    import graph_engene
    from custom_widgets.toogle_widget import IconToggleButton
    from singletons import ThreadSignalManager, NodeStateManager
    from custom_widgets.progressbar_widget import ProgressBar, ProgressBar2
    from custom_nodes.custom_nodes import PhHDF5Node
    from node_workers import NodeWorker
    from Qt.QtCore import QThreadPool
    from NodeGraphQt import NodeGraph, NodesPaletteWidget, constants
    from NodeGraphQt import PropertiesBinWidget
    
    splash.showMessage("Initializing graph...", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom, QtGui.QColor(30, 30, 30))
    app.processEvents()
    
    # create graph controller.
    graph = NodeGraph()  
    
    graph_widget = graph.widget 
    
    main_layout = QtWidgets.QVBoxLayout(graph_widget)
    main_layout.setContentsMargins(2, 2, 2, 2)
    
    
    top_layout = QtWidgets.QHBoxLayout()
    top_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
    
    # set up context menu for the node graph.
    hotkey_path = Path(BASE_PATH, 'hotkeys', 'hotkeys.json')
    graph.set_context_menu_from_file(hotkey_path, 'graph')
    
    splash.showMessage("Loading nodes...", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom, QtGui.QColor(30, 30, 30))
    app.processEvents()
    
    # registered example nodes.
    graph.register_nodes(
        [
             
            custom_nodes.LSM510Node,    
            custom_nodes.PhHDF5Node,  

            
            custom_nodes.CalcBGNode,
            custom_nodes.CorrectionsNode,
            custom_nodes.BurstSearchNodeFromBG,
            

            custom_nodes.BurstSearchNodeRate,            
            custom_nodes.FuseBurstsNode,
            custom_nodes.DitherNode,
            # custom_nodes.AlexNode,

            selector_nodes.BurstSelectorSizeNode,
            selector_nodes.BurstSelectorWidthNode,
            selector_nodes.BurstSelectorBrightnessNode,

            selector_nodes.BurstSelectorTimeNode,
            selector_nodes.BurstSelectorSingleNode,
            selector_nodes.BurstSelectorENode,     

            selector_nodes.BurstSelectorPeakPhrateNode,
            selector_nodes.BurstSelectorNDNode,
            selector_nodes.BurstSelectorNDBGNode,

            selector_nodes.BurstSelectorConsecutiveNode,
            selector_nodes.BurstSelectorNANode,
            selector_nodes.BurstSelectorNABGNode,
                              
            selector_nodes.BurstSelectorTopNMaxRateNode,
            selector_nodes.BurstSelectorTopNNDANode,
            selector_nodes.BurstSelectorTopNSBRNode,

            selector_nodes.BurstSelectorSBRNode,
            selector_nodes.BurstSelectorPeriodNode,
            
            custom_nodes.BGFitPlotterNode,
            custom_nodes.BGTimeLinePlotterNode,
            custom_nodes.EHistPlotterNode,
            custom_nodes.ScatterWidthSizePlotterNode,
            custom_nodes.ScatterDaPlotterNode,
            custom_nodes.ScatterRateDaPlotterNode,
            custom_nodes.ScatterFretSizePlotterNode,
            custom_nodes.ScatterFretNdNaPlotterNode,
            custom_nodes.ScatterFretWidthPlotterNode,
            custom_nodes.HistBurstSizeAllPlotterNode,
            custom_nodes.HistBurstWidthPlotterNode,
            custom_nodes.HistBurstBrightnessPlotterNode,
            custom_nodes.HistBurstSBRPlotterNode,
            custom_nodes.HistBurstPhratePlotterNode  
        ]
    )
    
    splash.showMessage("Initializing UI...", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom, QtGui.QColor(30, 30, 30))
    app.processEvents()
    
    # Define helper functions that are needed for the UI
    def on_run_btn_clicked(graph, btn):
        engene = graph_engene.GraphEngene(graph)
        roots = engene.find_root_nodes()
        pool = QThreadPool.globalInstance()
        for root_node in roots:
            new_worker = NodeWorker(root_node)
            pool.start(new_worker)
    
    def on_toogle_clicked(graph, toggle_btn):
        engene = graph_engene.GraphEngene(graph)
        toggle_state = toggle_btn.isChecked()
        if not toggle_state:
            print('static')
            engene.make_nodes_static()
        else:
            print('auto')
            engene.make_nodes_dinamic()
            on_run_btn_clicked(graph, toggle_btn)

    
    def on_block_ui(graph):
        pass
        # for node in graph.all_nodes():
        #     node.disable_all_node_widgets()
    
    def on_release_ui(graph):
        pass
        # for node in graph.all_nodes():
        #     node.enable_all_node_widgets()
    
    run_button = QtWidgets.QPushButton("Run", parent=graph_widget)
    # run_button.setFixedSize(50, 50)    
    run_button.setStyleSheet("""
        QPushButton {
                    background-color: #e3f2fd;
                    color: #1565c0;
                    border: 2px solid #90caf9;
                    border-radius: 20px;
                    font-weight: bold;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #bbdefb;
                }
            """)
    run_button.clicked.connect(lambda: on_run_btn_clicked(graph, run_button))
    run_button.clicked.connect(ThreadSignalManager().run_btn_clicked.emit)
    
    toggle_btn = IconToggleButton(parent=graph_widget)
    toggle_btn.toggled.connect(lambda: on_toogle_clicked(graph, toggle_btn))   
    toggle_btn.toggled.connect(NodeStateManager().on_change_node_state) 
    
    progress_bar = ProgressBar2(parent=graph_widget)
    ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
    ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
    ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
    progress_bar.block_ui.connect(lambda: run_button.setDisabled(True))
    progress_bar.block_ui.connect(lambda: on_block_ui(graph))
    progress_bar.release_ui.connect(lambda: run_button.setDisabled(False))
    progress_bar.release_ui.connect(lambda: on_release_ui(graph))
    # progress_bar.show()

    
    
    top_layout.addWidget(progress_bar)
    top_layout.addWidget(run_button)
    top_layout.addWidget(toggle_btn)
    
    main_layout.addLayout(top_layout)
    run_button.show()
    
    
    graph_widget.resize(1280, 800)
    graph_widget.setWindowTitle("FretBurstsStudio")
    
    # Close splash screen before showing main window
    splash.finish(graph_widget)
    
    graph_widget.show()
    
    
    # file_node = graph.create_node(
    #     'Loaders.PhHDF5Node')
    # file_node.set_disabled(False)
    
    # # photon_node = graph.create_node(
    # #     'nodes.custom.PhotonNode', text_color='#feab20')
    # # photon_node.set_disabled(False)
    
    # alex_node = graph.create_node(
    #     'Analysis.AlexNode')
    # alex_node.set_disabled(False)
    
    # calc_bgnode = graph.create_node(
    #     'Analysis.CalcBGNode')
    # calc_bgnode.set_disabled(False)
    
    # search_node = graph.create_node(
    #     'Analysis.BurstSearchNodeFromBG')
    # search_node.set_disabled(False)
    
    # plot_node = graph.create_node(
    #     'Plot.BGPlotterNode')
    # plot_node.set_disabled(False)
    

    
    # file_node.set_output(0, alex_node.input(0))
    # # photon_node.set_output(0, alex_node.input(0))
    # alex_node.set_output(0, calc_bgnode.input(0))
    # calc_bgnode.set_output(0, search_node.input(0))
    # search_node.set_output(0, plot_node.input(0))
    
    
    # graph.auto_layout_nodes()
    # graph.clear_selection()
    # graph.fit_to_selection()
    # graph.reset_zoom()

    graph.set_zoom(zoom=-0.9)
        

    properties_bin = PropertiesBinWidget(node_graph=graph, parent=graph_widget)
    properties_bin.setWindowFlags(QtCore.Qt.Tool)
    
    
    # nodes_tree = NodesTreeWidget(node_graph=graph)
    # nodes_tree.set_category_label('nodeGraphQt.nodes', 'Builtin Nodes')
    # nodes_tree.set_category_label('nodes.custom.ports', 'Custom Port Nodes')
    # nodes_tree.set_category_label('nodes.widget', 'Widget Nodes')
    # nodes_tree.set_category_label('nodes.basic', 'Basic Nodes')
    # nodes_tree.set_category_label('nodes.group', 'Group Nodes')
    # nodes_tree.show()


    
    nodes_palette = NodesPaletteWidget(node_graph=graph)
    nodes_palette.set_category_label('nodeGraphQt.nodes', 'Builtin Nodes')
    nodes_palette.set_category_label('nodes.custom.ports', 'Custom Port Nodes')
    nodes_palette.set_category_label('nodes.widget', 'Widget Nodes')
    nodes_palette.set_category_label('nodes.basic', 'Basic Nodes')
    nodes_palette.set_category_label('nodes.group', 'Group Nodes')
    
    #moving builtin to the last
    tabs = nodes_palette.tab_widget()

    w = tabs.widget(0)
    icon = tabs.tabIcon(0)
    text = tabs.tabText(0)
    tabs.removeTab(0)
    tabs.addTab(w, icon, text)
    
    sidebar_layout = QtWidgets.QVBoxLayout()
    sidebar_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
    sidebar_layout.setSpacing(0)  # Remove spacing
    sidebar_layout.addStretch()
    sidebar_layout.addWidget(nodes_palette)
    sidebar_widget = QtWidgets.QWidget()
    # Keep the sidebar chrome light/transparent so no dark strip shows
    sidebar_widget.setStyleSheet("background: transparent;")
    sidebar_widget.setLayout(sidebar_layout)
    sidebar_widget.setFixedSize(500, 200)
    main_layout.addWidget(sidebar_widget)


#styling
    # those are needed later to apply node theme after copy and paste
    original_paste_nodes = graph.paste_nodes
    original_duplicate_nodes = graph.duplicate_nodes
    def apply_theme(kind=None):
        global THEME
        if kind is None:
            kind = THEME
        else:
            THEME = kind
        color_dict = {
            'light': {
                'background': (240, 240, 240),
                'grid': (210, 210, 210),
                'node': (150, 150, 150),
                'text': (30, 30, 30)
            },
            'dark': {
                'background': (50, 50, 50),
                'grid': (80, 80, 80),
                'node': (100, 100, 100),
                'text': (240, 240, 240)
            }
        }
        
        graph.set_background_color(*color_dict[kind]['background'])
        graph.set_grid_color(*color_dict[kind]['grid'])
        # Also tint the top-level widget so the app background matches the theme
        bg = color_dict[kind]['background']
        graph_widget.setStyleSheet(
            f"""
            background-color: rgb{bg};
            color: rgb{color_dict[kind]['text']};
            /* border: 1px solid rgb{color_dict[kind]['grid']}; */
            """
        )
            
                
        def theme_node(node):
            
            node.set_property('text_color',color_dict[kind]['text'])
            # update resize handle color if the view supports it
            if hasattr(node, 'view') and hasattr(node.view, 'set_handle_color'):
                node.view.set_handle_color(color_dict[kind]['grid'])
            if hasattr(node, 'PLOT_NODE') and node.PLOT_NODE:
                node.set_color( 255,255,255)
            else:
                node.set_color( *color_dict[kind]['node'])

            for w in node.widgets().values():
                box = w.widget()  # this is _NodeGroupBox (a QGroupBox)
                # Replace the stylesheet completely with your own.
                box.setStyleSheet(f"""
                QGroupBox {{
                    background-color: transparent;
                    border: 0px;
                    margin-top: 1px;
                    padding: 14px 1px 2px 1px;
                    font-size: 8pt;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    color: rgb(*color_dict[{kind}]['text']); 
                    padding: 0px;
                    margin-left: 4px;
                }}
                """)

        for n in graph.all_nodes():
            theme_node(n)
        graph.node_created.connect(theme_node)

        ## a hacky way to apply  theme upon copy paste
        def paste_nodes_wrapper(adjust_graph_style=True):
            nodes_before = set(graph.all_nodes())
            result = original_paste_nodes(adjust_graph_style)
            nodes_after = set(graph.all_nodes())
            new_nodes = nodes_after - nodes_before
            for node in new_nodes:
                theme_node(node)
            return result
        
        def duplicate_nodes_wrapper(nodes):
            nodes_before = set(graph.all_nodes())
            result = original_duplicate_nodes(nodes)
            nodes_after = set(graph.all_nodes())
            new_nodes = nodes_after - nodes_before
            for node in new_nodes:
                theme_node(node)
            return result
        
        graph.paste_nodes = paste_nodes_wrapper
        graph.duplicate_nodes = duplicate_nodes_wrapper
        
        nodes_palette.setStyleSheet(f"""
            background-color: rgb{color_dict[kind]['background']};
            color: rgb{color_dict[kind]['text']};
        """)

        # Style tab headers separately from the palette background
        tabs.setStyleSheet(f"""
            QTabBar::tab    {{
                background: rgb{color_dict[kind]['background']};
                color: rgb{color_dict[kind]['text']};
                padding: 6px 10px;
                border: 1px solid rgb{color_dict[kind]['grid']};
                border-bottom: 0px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: rgb{color_dict[kind]['node']};
                border-color: rgb{color_dict[kind]['grid']};
            }}   
            QTabWidget::pane {{
                background: rgb{color_dict[kind]['background']}; /* match palette body instead of black */
                border: 1px solid rgb{color_dict[kind]['grid']};
                top: -1px;
            }}
        """)
       
    # ----- menu bar -----
    def open_file():
        path = QtWidgets.QFileDialog.getOpenFileName(graph_widget, "Open File",filter="*.json")
        if path:
            graph.load_session(path[0])
            apply_theme()

    def save_file():
        path = QtWidgets.QFileDialog.getSaveFileName(graph_widget, "Save File",filter="*.json")
        if path[0]:
            graph.save_session(path[0])

    def close_app():
        app.quit()

    def show_about():
        QtWidgets.QMessageBox.information(graph_widget, "About", "FretBurstStudio based on FretBursts library<br><br>Version 0.0.1 <br><br>Developed by: Dmitry Ryabov and Grigory Armeev")

    def load_template(template_path):
        """Load a template session from the configs folder."""
        if template_path and Path(template_path).exists():
            graph.load_session(template_path)
            apply_theme()

    menu_bar = QtWidgets.QMenuBar(graph_widget)
    file_menu = menu_bar.addMenu("File")
    file_menu.addAction("Open").triggered.connect(open_file)
    file_menu.addAction("Save").triggered.connect(save_file)
    file_menu.addSeparator()
    file_menu.addAction("Close").triggered.connect(close_app)

    theme_menu = menu_bar.addMenu("Theme")
    theme_menu.addAction("Light").triggered.connect(lambda: apply_theme('light'))
    theme_menu.addAction("Dark").triggered.connect(lambda: apply_theme('dark'))

    templates_menu = menu_bar.addMenu("Templates")
    configs_folder = BASE_PATH / 'configs'
    if configs_folder.exists():
        json_files = sorted(configs_folder.glob('*.json'))
        if json_files:
            for json_file in json_files:
                template_name = json_file.stem  # filename without extension
                action = templates_menu.addAction(template_name)
                action.triggered.connect(lambda checked, path=str(json_file): load_template(path))
        else:
            no_templates_action = templates_menu.addAction("No templates available")
            no_templates_action.setEnabled(False)
    else:
        no_templates_action = templates_menu.addAction("Configs folder not found")
        no_templates_action.setEnabled(False)

    about_menu = menu_bar.addMenu("About")
    about_menu.addAction("About").triggered.connect(show_about)

    main_layout.setMenuBar(menu_bar)

    apply_theme('light')
    app.exec()

    

if __name__ == '__main__':
    main()
    

    