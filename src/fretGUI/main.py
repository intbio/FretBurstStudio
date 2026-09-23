# Essential imports only - these are fast
import sys
import json
import signal
from pathlib import Path
from Qt import QtWidgets, QtCore, QtGui
import fretGUI.custom_nodes.custom_nodes as custom_nodes
import fretGUI.custom_nodes.selector_nodes as selector_nodes
import fretGUI.graph_engene as graph_engene
from fretGUI.custom_widgets.toogle_widget import IconToggleButton
from fretGUI.singletons import (
    NodeStateManager,
    RunCoordinator,
    ThreadSignalManager,
)
from fretGUI.custom_widgets.progressbar_widget import ProgressBar2
from fretGUI.custom_widgets.node_sidebar import NodeSidebar
from fretGUI.custom_widgets.plot_widget import set_matplotlib_theme
from fretGUI.node_workers import NodeWorker
from Qt.QtCore import QThreadPool
from NodeGraphQt import NodeGraph, PropertiesBinWidget


THEME = 'light'
THEME_COLORS = {
    'light': {
        'background': (240, 240, 240),
        'window': (240, 240, 240),
        'base': (255, 255, 255),
        'alternate_base': (246, 246, 246),
        'button': (232, 232, 232),
        'button_hover': (220, 232, 244),
        'grid': (210, 210, 210),
        'node': (150, 150, 150),
        'plot_node': (255, 255, 255),
        'text': (30, 30, 30),
        'disabled_text': (135, 135, 135),
        'highlight': (47, 111, 237),
        'highlighted_text': (255, 255, 255),
    },
    'dark': {
        'background': (50, 50, 50),
        'window': (45, 45, 45),
        'base': (62, 62, 62),
        'alternate_base': (70, 70, 70),
        'button': (76, 76, 76),
        'button_hover': (88, 88, 88),
        'grid': (80, 80, 80),
        'node': (100, 100, 100),
        'plot_node': (70, 70, 70),
        'text': (240, 240, 240),
        'disabled_text': (155, 155, 155),
        'highlight': (76, 139, 245),
        'highlighted_text': (255, 255, 255),
    },
}


def build_theme_palette(kind):
    colors = THEME_COLORS[kind]
    palette = QtGui.QPalette()
    role_colors = {
        QtGui.QPalette.Window: colors['window'],
        QtGui.QPalette.WindowText: colors['text'],
        QtGui.QPalette.Base: colors['base'],
        QtGui.QPalette.AlternateBase: colors['alternate_base'],
        QtGui.QPalette.ToolTipBase: colors['base'],
        QtGui.QPalette.ToolTipText: colors['text'],
        QtGui.QPalette.Text: colors['text'],
        QtGui.QPalette.Button: colors['button'],
        QtGui.QPalette.ButtonText: colors['text'],
        QtGui.QPalette.BrightText: colors['highlighted_text'],
        QtGui.QPalette.Highlight: colors['highlight'],
        QtGui.QPalette.HighlightedText: colors['highlighted_text'],
    }
    for role, color in role_colors.items():
        palette.setColor(role, QtGui.QColor(*color))

    disabled = QtGui.QColor(*colors['disabled_text'])
    for role in (
        QtGui.QPalette.WindowText,
        QtGui.QPalette.Text,
        QtGui.QPalette.ButtonText,
    ):
        palette.setColor(QtGui.QPalette.Disabled, role, disabled)
    return palette


def build_theme_stylesheet(kind):
    """Style controls whose native Windows rendering ignores QPalette."""
    colors = THEME_COLORS[kind]
    return f"""
        QMenuBar, QMenu {{
            background-color: rgb{colors['window']};
            color: rgb{colors['text']};
        }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background-color: rgb{colors['highlight']};
            color: rgb{colors['highlighted_text']};
        }}
        QMenu::separator {{
            background-color: rgb{colors['grid']};
            height: 1px;
            margin: 4px 8px;
        }}
        QPushButton, QToolButton, QComboBox {{
            background-color: rgb{colors['button']};
            color: rgb{colors['text']};
            border: 1px solid rgb{colors['grid']};
            padding: 2px 4px;
        }}
        QPushButton:hover, QToolButton:hover, QComboBox:hover {{
            background-color: rgb{colors['button_hover']};
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QListView, QTreeView,
        QTableView, QComboBox QAbstractItemView {{
            background-color: rgb{colors['base']};
            color: rgb{colors['text']};
            alternate-background-color: rgb{colors['alternate_base']};
            border: 1px solid rgb{colors['grid']};
            selection-background-color: rgb{colors['highlight']};
            selection-color: rgb{colors['highlighted_text']};
        }}
        QPushButton:disabled, QToolButton:disabled, QComboBox:disabled,
        QLineEdit:disabled {{
            color: rgb{colors['disabled_text']};
        }}
    """


def start_graph_run(graph, context):
    engene = graph_engene.GraphEngene(graph)
    roots = engene.find_root_nodes()
    if not roots:
        context.finish_if_idle()
        return
    pool = QThreadPool.globalInstance()
    # Construct every root worker first so the context knows the full initial
    # worker set before a very short root can finish.
    workers = [
        NodeWorker(root_node, context=context)
        for root_node in roots
    ]
    for index, worker in enumerate(workers):
        try:
            pool.start(worker)
        except Exception:
            context.invalidate()
            context.worker_finished(worker.uid)
            for unscheduled in workers[index + 1:]:
                context.worker_finished(unscheduled.uid)
            raise


def on_run_btn_clicked(graph, btn):
    RunCoordinator().request_run()


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



def main():
    # handle SIGINT to make the app terminate on CTRL+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # Create QApplication immediately
    app = QtWidgets.QApplication(sys.argv)
    # The native Windows style only applies some palette roles (notably text),
    # leaving several controls light when the application palette is dark.
    app.setStyle('Fusion')

    # ---- In-application console logger ----
    class EmittingStream(QtCore.QObject):
        """
        Redirects sys.stdout/sys.stderr into a Qt signal so we can display
        prints and tracebacks inside the GUI, while also mirroring to the
        original terminal stream when one is available.
        """
        text_written = QtCore.Signal(str)

        def __init__(self, original_stream=None, parent=None):
            super().__init__(parent)
            self._original_stream = original_stream

        def write(self, text):
            if not text:
                return
            text = str(text)
            if self._original_stream is not None:
                try:
                    self._original_stream.write(text)
                    self._original_stream.flush()
                except Exception:
                    pass
            self.text_written.emit(text)

        def flush(self):
            if self._original_stream is not None:
                try:
                    self._original_stream.flush()
                except Exception:
                    pass
    
    # Show splash screen ASAP
    BASE_PATH = Path(__file__).parent.resolve()
    
    # Load logo image
    logo_path = BASE_PATH / 'static' / 'fb_logo.png'
    app.setWindowIcon(QtGui.QIcon(str(logo_path)))
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
        QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter,
        QtGui.QColor(30, 30, 30)
    )
    splash.show()
    app.processEvents()
    
    # Now import heavy modules while splash is showing
    splash.showMessage("Loading modules...", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, QtGui.QColor(30, 30, 30))
    app.processEvents()
    
    splash.showMessage("Initializing graph...", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom, QtGui.QColor(30, 30, 30))
    app.processEvents()
    
    # create graph controller.
    graph = NodeGraph()  
    
    graph_widget = graph.widget
    app_window = QtWidgets.QMainWindow()
    app_window.setObjectName('nodeGraphRoot')
    central_widget = QtWidgets.QWidget(app_window)
    main_layout = QtWidgets.QHBoxLayout(central_widget)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)
    app_window.setCentralWidget(central_widget)

    # --- Log / console output window (separate window) ---
    log_window = QtWidgets.QDialog(app_window)
    log_window.setWindowTitle("Console Output")
    log_window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMinMaxButtonsHint)
    log_window.resize(800, 400)
    
    log_widget = QtWidgets.QPlainTextEdit(log_window)
    log_widget.setReadOnly(True)
    log_widget.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
    log_widget.setStyleSheet(
        """
        QPlainTextEdit {
            background-color: #111111;
            color: #EEEEEE;
            font-family: Consolas, monospace;
            font-size: 9pt;
            border: 1px solid #333333;
        }
        """
    )
    
    # Add clear button
    clear_button = QtWidgets.QPushButton("Clear", log_window)
    clear_button.clicked.connect(log_widget.clear)
    
    log_layout = QtWidgets.QVBoxLayout(log_window)
    log_layout.setContentsMargins(4, 4, 4, 4)
    log_layout.setSpacing(4)
    button_layout = QtWidgets.QHBoxLayout()
    button_layout.addStretch()
    button_layout.addWidget(clear_button)
    log_layout.addLayout(button_layout)
    log_layout.addWidget(log_widget)
    
    # Connect stdout/stderr to the log widget, mirroring to the terminal too
    original_stdout = sys.__stdout__ or sys.stdout
    original_stderr = sys.__stderr__ or sys.stderr
    stdout_stream = EmittingStream(original_stdout)
    stderr_stream = EmittingStream(original_stderr)
    stdout_stream.text_written.connect(lambda text: log_widget.appendPlainText(text.rstrip()))
    stderr_stream.text_written.connect(lambda text: log_widget.appendPlainText(text.rstrip()))
    sys.stdout = stdout_stream
    sys.stderr = stderr_stream
    
    # Function to toggle log window visibility
    def toggle_log_window():
        if log_window.isVisible():
            log_window.hide()
        else:
            log_window.show()
            log_window.raise_()
            log_window.activateWindow()
    
    # set up context menu for the node graph.
    hotkey_path = Path(BASE_PATH, 'hotkeys', 'hotkeys.json')
    graph.set_context_menu_from_file(hotkey_path, 'graph')
    
    splash.showMessage("Loading nodes...", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, QtGui.QColor(30, 30, 30))
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
            custom_nodes.HistBurstPhratePlotterNode,  
            custom_nodes.BVAPlotterNode,
            custom_nodes.InterBurstPlotterNode,
            custom_nodes.TimetraceExplorerNode,
        ]
    )
    
    splash.showMessage("Initializing UI...", QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, QtGui.QColor(30, 30, 30))
    app.processEvents()
    
    # Define helper functions that are needed for the UI
    
    run_button = QtWidgets.QPushButton("Run", parent=app_window)
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
    coordinator = RunCoordinator()
    ThreadSignalManager().run_btn_clicked.connect(
        lambda: on_run_btn_clicked(graph, run_button)
    )
    coordinator.run_ready.connect(
        lambda context: start_graph_run(graph, context)
    )
    coordinator.run_completed.connect(
        lambda _run_id: ThreadSignalManager().all_thread_finished.emit()
    )
    coordinator.busy_changed.connect(run_button.setDisabled)
    run_button.clicked.connect(ThreadSignalManager().run_btn_clicked.emit)
    
    toggle_btn = IconToggleButton(parent=app_window)
    toggle_btn.toggled.connect(lambda: on_toogle_clicked(graph, toggle_btn))   
    toggle_btn.toggled.connect(NodeStateManager().on_change_node_state) 
    
    progress_bar = ProgressBar2(parent=app_window)
    ThreadSignalManager().thread_started.connect(progress_bar.on_thread_started)
    ThreadSignalManager().thread_finished.connect(progress_bar.on_thread_finished)
    ThreadSignalManager().thread_progress.connect(progress_bar.on_thread_processed)
    ThreadSignalManager().thread_error.connect(progress_bar.on_thread_error)
    coordinator.run_started.connect(progress_bar.on_run_started)
    coordinator.busy_changed.connect(progress_bar.on_busy_changed)
    progress_bar.block_ui.connect(lambda: on_block_ui(graph))
    progress_bar.release_ui.connect(lambda: on_release_ui(graph))

    sidebar = NodeSidebar(
        graph,
        run_button,
        toggle_btn,
        progress_bar,
        parent=central_widget,
    )
    main_layout.addWidget(sidebar)
    main_layout.addWidget(graph_widget, stretch=1)

    app_window.resize(1280, 800)
    app_window.setWindowTitle("FretBurstsStudio")

    # Close splash screen before showing main window
    splash.finish(app_window)

    app_window.show()
    

    graph.set_zoom(zoom=-0.9)
        

    properties_bin = PropertiesBinWidget(node_graph=graph, parent=app_window)
    properties_bin.setWindowFlags(QtCore.Qt.Tool)


#styling
    # those are needed later to apply node theme after copy and paste
    original_paste_nodes = graph.paste_nodes
    original_duplicate_nodes = graph.duplicate_nodes

    def restore_resizable_node_sizes(node,saved_sizes=None):
        """Restore size for ResizableContentNode instances after loading from JSON."""
        from fretGUI.custom_nodes.abstract_nodes import ResizableContentNode
        try:
            if isinstance(node, ResizableContentNode):
                saved_size = saved_sizes[node.name()]
                node.restore_size(
                    saved_size.get('width'),
                    saved_size.get('height'),
                )
        except (AttributeError, KeyError, TypeError, ValueError):
            pass

    original_load_session = graph.load_session
    def load_session_wrapper(file_path):
        saved_sizes = {}
        with open(file_path, 'r') as f:
            data = json.load(f)
            if 'nodes' in data:
                for node_id, node_data in data['nodes'].items():
                    if 'width' in node_data or 'height' in node_data:
                        saved_sizes[node_data.get('name')] = {
                            'width': node_data.get('width'),
                            'height': node_data.get('height')
                        }

        result = original_load_session(file_path)
        for node in graph.all_nodes():
            restore_resizable_node_sizes(node, saved_sizes)
        return result
    graph.load_session = load_session_wrapper



    def apply_theme(kind=None):
        global THEME
        previous_theme = THEME
        if kind is None:
            kind = THEME
        theme_changed = kind != previous_theme
        THEME = kind
        colors = THEME_COLORS[kind]
        app.setPalette(build_theme_palette(kind))
        app.setStyleSheet(build_theme_stylesheet(kind))
        set_matplotlib_theme(kind)
        
        graph.set_background_color(*colors['background'])
        graph.set_grid_color(*colors['grid'])
        # Also tint the top-level widget so the app background matches the theme
        bg = colors['background']
        app_window.setStyleSheet(
            f"""
            QWidget#nodeGraphRoot {{
                background-color: rgb{bg};
                color: rgb{colors['text']};
            }}
            """
        )

        run_button.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb{colors['button']};
                color: rgb{colors['text']};
                border: 2px solid rgb{colors['highlight']};
                border-radius: 20px;
                font-weight: bold;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: rgb{colors['button_hover']};
            }}
        """)
        toggle_btn.set_theme(kind, colors)
        sidebar.set_theme(colors)
            
                
        def theme_node(node):
           
            node.set_property('text_color', colors['text'])
            # update resize handle color if the view supports it
            if hasattr(node, 'view') and hasattr(node.view, 'set_handle_color'):
                node.view.set_handle_color(colors['grid'])
            if hasattr(node, 'PLOT_NODE') and node.PLOT_NODE:
                node.set_color(*colors['plot_node'])
            else:
                node.set_color(*colors['node'])

            set_node_theme = getattr(node, 'set_theme', None)
            if callable(set_node_theme):
                set_node_theme(kind, colors)

            if hasattr(node, 'widgets'):
                for w in node.widgets().values():
                    box = w.widget()
                    text_color = colors['text']
                    set_box_theme = getattr(box, 'set_theme', None)
                    if callable(set_box_theme):
                        set_box_theme(kind, colors)
                    elif hasattr(box, 'set_text_color'):
                        box.set_text_color(text_color)

                    custom_widget = w.get_custom_widget()
                    set_theme = getattr(custom_widget, 'set_theme', None)
                    if callable(set_theme):
                        set_theme(kind, colors)

                    if callable(set_box_theme) or hasattr(box, 'set_text_color'):
                        continue

                    title = box.title() if hasattr(box, 'title') else ''
                    top_padding = 14 if title else 0
                    box.setStyleSheet(f"""
                    QGroupBox {{
                        background-color: transparent;
                        border: 0px;
                        margin: 0px;
                        padding: {top_padding}px 0px 0px 0px;
                        font-size: 8pt;
                    }}
                    QGroupBox::title {{
                        subcontrol-origin: margin;
                        subcontrol-position: top center;
                        color: rgb{text_color};
                        padding: 0px;
                    }}
                    """)

        for n in graph.all_nodes():
            theme_node(n)
        graph.node_created.connect(theme_node)

        ## a hacky way to apply  theme upon copy paste
        def paste_nodes_wrapper(adjust_graph_style=True):
            nodes_before = set(graph.all_nodes())
            print(nodes_before)
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
        
        app.processEvents()
        if theme_changed:
            QtCore.QTimer.singleShot(
                0,
                ThreadSignalManager().run_btn_clicked.emit,
            )
       
    # ----- menu bar -----
    def open_file():
        path = QtWidgets.QFileDialog.getOpenFileName(app_window, "Open File",filter="*.json")
        if path:
            graph.load_session(path[0])
            apply_theme()

    def save_file():
        path = QtWidgets.QFileDialog.getSaveFileName(app_window, "Save File",filter="*.json")
        if path[0]:
            graph.save_session(path[0])

    def close_app():
        app.quit()

    def show_about():
        QtWidgets.QMessageBox.information(app_window, "About", "FretBurstStudio based on FretBursts library<br><br>Version 0.0.1 <br><br>Developed by: Dmitry Ryabov and Grigory Armeev")

    def load_template(template_path):
        """Load a template session from the configs folder."""
        if template_path and Path(template_path).exists():
            graph.load_session(template_path)
            apply_theme()

    menu_bar = app_window.menuBar()
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

    log_menu = menu_bar.addMenu("Log")
    log_menu.addAction("Show Console").triggered.connect(toggle_log_window)
    
    about_menu = menu_bar.addMenu("About")
    about_menu.addAction("About").triggered.connect(show_about)

    apply_theme('light')
    app.exec()

    

if __name__ == '__main__':
    main()
    

    