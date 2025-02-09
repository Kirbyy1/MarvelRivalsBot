import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSplitter, QWidget, QTabWidget, QGroupBox,
                             QLineEdit, QPushButton, QTextEdit, QFormLayout, QHBoxLayout, QVBoxLayout,
                             QFileDialog, QDoubleSpinBox, QLabel, QMenuBar, QMenu)
from PyQt5.QtGui import QPalette, QColor, QFont

from PyQt5.QtCore import Qt, QTimer, QDateTime  # Modified line

class MarvelRivalsBotUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marvel Rivals Bot Debugger")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize dark theme
        self.init_dark_theme()

        # Create main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Create vertical splitter
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)

        # Create configuration panel
        config_panel = self.create_config_panel()
        splitter.addWidget(config_panel)

        # Create log panel
        log_panel = self.create_log_panel()
        splitter.addWidget(log_panel)

        # Create menu bar
        self.create_menu()

        # Test data
        self.test_log_messages()

    def init_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)

        # Set font
        font = QFont("Segoe UI", 9)
        self.setFont(font)

    def create_config_panel(self):
        tab_widget = QTabWidget()
        tab_widget.addTab(self.create_general_settings(), "Configuration")

        # Style tabs
        tab_widget.setStyleSheet("""
            QTabBar::tab { 
                background: #353535; 
                color: white; 
                padding: 8px; 
                border-top-left-radius: 4px; 
                border-top-right-radius: 4px; 
            }
            QTabBar::tab:selected { 
                background: #2a82da; 
            }
            QTabWidget::pane { 
                border: none; 
            }
        """)

        return tab_widget

    def create_general_settings(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # General Settings Group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout()
        general_group.setLayout(general_layout)

        # Executable Path
        self.exe_path = QLineEdit()
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_executable)
        browse_btn.setStyleSheet("QPushButton { padding: 5px 10px; }")

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.exe_path)
        path_layout.addWidget(browse_btn)
        general_layout.addRow("Executable Path:", path_layout)

        # Confidence Level
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0)
        self.confidence.setSingleStep(0.1)
        self.confidence.setValue(0.8)
        self.confidence.setToolTip("Detection confidence threshold (0.0 to 1.0)")

        # Delay
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.0, 10.0)
        self.delay.setSingleStep(0.1)
        self.delay.setValue(1.0)
        self.delay.setToolTip("Delay between actions in seconds")

        general_layout.addRow("Confidence Level:", self.confidence)
        general_layout.addRow("Action Delay:", self.delay)

        # Start Bot Button
        start_btn = QPushButton("Start Bot")
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a82da;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1f62a4;
            }
        """)
        start_btn.clicked.connect(self.start_bot)

        layout.addWidget(general_group)
        layout.addWidget(start_btn)

        return widget

    def create_log_panel(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Log Label
        log_label = QLabel("Logs:")
        log_label.setStyleSheet("color: white; font-weight: bold; padding: 5px;")

        # Log Display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: none;
                padding: 10px;
                font-family: 'Consolas';
            }
        """)

        layout.addWidget(log_label)
        layout.addWidget(self.log_display)

        return widget

    def create_menu(self):
        menu_bar = QMenuBar()
        file_menu = QMenu("&File", self)
        edit_menu = QMenu("&Edit", self)
        help_menu = QMenu("&Help", self)

        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(edit_menu)
        menu_bar.addMenu(help_menu)
        self.setMenuBar(menu_bar)

    def browse_executable(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "", "Executable Files (*.exe)"
        )
        if path:
            self.exe_path.setText(path)

    def start_bot(self):
        self.log("Bot started with configuration:")
        self.log(f" - Executable: {self.exe_path.text()}")
        self.log(f" - Confidence: {self.confidence.value()}")
        self.log(f" - Delay: {self.delay.value()}s")

    def log(self, message):
        self.log_display.append(f"[{QDateTime.currentDateTime().toString('hh:mm:ss')}] {message}")

    def test_log_messages(self):
        self.log("System initialized successfully")
        self.log("Waiting for game detection...")
        self.log("Connection established with game process")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MarvelRivalsBotUI()
    window.show()
    sys.exit(app.exec_())