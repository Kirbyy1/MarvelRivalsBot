import json
import win32gui
import time
import win32api
import pydirectinput
import keyboard
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QComboBox, QDoubleSpinBox,
    QTextEdit, QMessageBox, QInputDialog, QListWidgetItem, QDialog,
    QLineEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from typing import Dict, Optional, List
import threading
import ctypes
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPixmap, QPainter, QIcon
from PySide6.QtCore import Qt
def get_svg_pixmap(svg_file, width, height):
    renderer = QSvgRenderer(svg_file)
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


# Enable proper DPI handling
ctypes.windll.shcore.SetProcessDpiAwareness(2)


class PositionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Position")
        self.description = QLineEdit()
        self.description.setPlaceholderText("Enter position description...")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Position Description:"))
        layout.addWidget(self.description)
        layout.addWidget(buttons)
        self.setLayout(layout)


class AutomationThread(QThread):
    log_signal = Signal(str)
    stopped = Signal()

    def __init__(self, parent, config, stop_event):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.stop_event = stop_event

    def run(self):
        self.log_signal.emit("Automation started")
        try:
            while not self.stop_event.is_set():
                start_time = time.time()

                # Get fresh window info
                window_info = self.parent.get_window_info(self.config['window_title'])
                if not window_info or not window_info.get('valid', False):
                    self.log_signal.emit("Target window not found or invalid!")
                    time.sleep(1)
                    continue

                try:
                    hwnd = window_info['hwnd']
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.5)

                    # Get current window dimensions
                    left = window_info['left']
                    top = window_info['top']
                    width = window_info['width']
                    height = window_info['height']

                    # Process positions
                    for pos in self.config['positions']:
                        if self.stop_event.is_set():
                            break

                        x = left + (width * pos['x'] / 100)
                        y = top + (height * pos['y'] / 100)
                        x, y = int(round(x)), int(round(y))

                        # Validate position
                        if not (left <= x <= left + width and top <= y <= top + height):
                            self.log_signal.emit(f"Position out of bounds: {pos['description']}")
                            continue

                        try:
                            pydirectinput.moveTo(x, y)
                            time.sleep(0.1)
                            pydirectinput.click()
                            self.log_signal.emit(f"Clicked {pos['description']} at ({x}, {y})")
                        except Exception as e:
                            self.log_signal.emit(f"Click failed: {str(e)}")

                except Exception as e:
                    self.log_signal.emit(f"Window operation error: {str(e)}")
                    time.sleep(1)

                # Maintain interval
                interval = self.config['interval']
                while time.time() - start_time < interval and not self.stop_event.is_set():
                    time.sleep(0.1)

        except Exception as e:
            self.log_signal.emit(f"Automation error: {str(e)}")
        finally:
            self.stopped.emit()


class GameAutomationApp(QMainWindow):
    capture_triggered = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClickVector - Desktop Automation Tool")
        self.setGeometry(100, 100, 1000, 700)

        # Set the window title icon from an SVG file
        icon_pixmap = get_svg_pixmap("logo.svg", 128, 128)  # Adjust size as needed
        self.setWindowIcon(QIcon(icon_pixmap))


        self.setup_ui()
        self.setup_styles()

        self.running = False
        self.automation_thread = None
        self.stop_event = None
        self.presets = self.load_presets()
        self.current_window_info = None
        self.window_titles = []
        self.positions = []

        # Hotkeys
        keyboard.add_hotkey('ctrl+shift+c', lambda: self.capture_triggered.emit())
        keyboard.add_hotkey('ctrl+shift+x', self.stop_automation)
        self.capture_triggered.connect(self.capture_position)

        self.detect_windows()
        self.update_info_display()
        self.update_preset_list()
        self.statusBar().showMessage("Ready")

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # --- Add your SVG logo at the top of the left panel ---
        # Create a QSvgWidget, load your SVG file, and set a fixed size for the logo.
        # self.logo_widget = QSvgWidget("logo.svg")  # Ensure the file path is correct
        # self.logo_widget.setFixedSize(150, 150)  # Adjust the size as needed
        # left_layout.addWidget(self.logo_widget, alignment=Qt.AlignCenter)

        self.preset_list = QListWidget()
        self.btn_refresh = QPushButton("Refresh Windows")
        self.btn_capture = QPushButton("Capture Position (Ctrl+Shift+C)")
        self.btn_add_pos = QPushButton("Add Position")
        self.btn_remove_pos = QPushButton("Remove Position")
        self.btn_load = QPushButton("Load Preset")
        self.btn_delete = QPushButton("Delete Preset")

        left_layout.addWidget(self.btn_refresh)
        left_layout.addWidget(self.btn_capture)
        left_layout.addWidget(QLabel("Positions:"))
        left_layout.addWidget(self.btn_add_pos)
        left_layout.addWidget(self.btn_remove_pos)
        left_layout.addWidget(QLabel("Presets:"))
        left_layout.addWidget(self.preset_list)
        left_layout.addWidget(self.btn_load)
        left_layout.addWidget(self.btn_delete)

        # Right Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.window_title_combo = QComboBox()
        self.spin_x = QDoubleSpinBox()
        self.spin_y = QDoubleSpinBox()
        self.spin_interval = QDoubleSpinBox()
        self.positions_list = QListWidget()
        self.btn_start = QPushButton("Start Automation")
        self.btn_save = QPushButton("Save Preset")
        self.log_text = QTextEdit()

        self.spin_x.setRange(0, 100)
        self.spin_y.setRange(0, 100)
        self.spin_interval.setRange(0.1, 60)
        self.spin_interval.setValue(1.0)

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Window Title:"))
        form_layout.addWidget(self.window_title_combo)
        form_layout.addWidget(QLabel("X Position (%):"))
        form_layout.addWidget(self.spin_x)
        form_layout.addWidget(QLabel("Y Position (%):"))
        form_layout.addWidget(self.spin_y)
        form_layout.addWidget(QLabel("Interval (seconds):"))
        form_layout.addWidget(self.spin_interval)

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_save)

        right_layout.addLayout(form_layout)
        right_layout.addWidget(QLabel("Saved Positions:"))
        right_layout.addWidget(self.positions_list)
        right_layout.addLayout(control_layout)
        right_layout.addWidget(QLabel("Activity Log:"))
        right_layout.addWidget(self.log_text)

        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 3)

        # Connect signals
        self.btn_refresh.clicked.connect(self.detect_windows)
        self.btn_capture.clicked.connect(self.capture_position)
        self.btn_add_pos.clicked.connect(self.add_position)
        self.btn_remove_pos.clicked.connect(self.remove_position)
        self.btn_load.clicked.connect(self.load_preset)
        self.btn_delete.clicked.connect(self.delete_preset)
        self.btn_start.clicked.connect(self.toggle_automation)
        self.btn_save.clicked.connect(self.save_preset)
        self.window_title_combo.currentTextChanged.connect(self.on_window_select)
        self.positions_list.itemSelectionChanged.connect(self.on_position_select)

    def setup_styles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QPushButton {
                background-color: #3d3d3d;
                border: 1px solid #4d4d4d;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QListWidget, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #3d3d3d;
                border: 1px solid #4d4d4d;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
        """)

    def log_message(self, message: str):
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def get_window_info(self, window_title: str) -> Optional[Dict]:
        if not window_title:
            return None

        try:
            hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd or not win32gui.IsWindowVisible(hwnd):
                return None

            # Get monitor scaling factor
            try:
                scale_factor = ctypes.windll.shcore.GetScaleFactorForMonitor(
                    win32api.MonitorFromWindow(hwnd)
                ) / 100
            except:
                scale_factor = 1.0

            # Get window and client rects
            rect = win32gui.GetWindowRect(hwnd)
            client_rect = win32gui.GetClientRect(hwnd)

            # Convert to physical pixels
            phys_client_width = int(client_rect[2] * scale_factor)
            phys_client_height = int(client_rect[3] * scale_factor)

            if phys_client_width <= 0 or phys_client_height <= 0:
                return None

            # Calculate window chrome
            border_width = max(0, (rect[2] - rect[0] - phys_client_width) // 2)
            title_bar_height = max(0, (rect[3] - rect[1] - phys_client_height - border_width))

            return {
                "hwnd": hwnd,
                "left": rect[0] + border_width,
                "top": rect[1] + title_bar_height,
                "width": phys_client_width,
                "height": phys_client_height,
                "scale_factor": scale_factor,
                "valid": True
            }
        except Exception as e:
            self.log_message(f"Window info error: {str(e)}")
            return None

    def update_info_display(self):
        if not self.running and self.current_window_info:
            try:
                mouse_x, mouse_y = win32api.GetCursorPos()
                rel_x = (mouse_x - self.current_window_info["left"]) / self.current_window_info["width"] * 100
                rel_y = (mouse_y - self.current_window_info["top"]) / self.current_window_info["height"] * 100

                self.statusBar().showMessage(
                    f"Mouse: ({mouse_x}, {mouse_y}) | Relative: ({rel_x:.1f}%, {rel_y:.1f}%) | "
                    f"Window: {self.current_window_info['width']}x{self.current_window_info['height']} "
                    f"@ ({self.current_window_info['left']}, {self.current_window_info['top']})"
                )
            except Exception as e:
                self.log_message(f"Position tracking error: {str(e)}")

        QTimer.singleShot(100, self.update_info_display)

    def add_position(self):
        if not self.current_window_info:
            self.log_message("No window selected!")
            return

        dialog = PositionDialog(self)
        if dialog.exec():
            description = dialog.description.text().strip()
            if not description:
                self.log_message("Position description cannot be empty!")
                return

            try:
                self.positions.append({
                    "description": description,
                    "x": self.captured_x,
                    "y": self.captured_y,
                    "abs_x": self.captured_abs_x,
                    "abs_y": self.captured_abs_y
                })
                self.update_positions_list()
                self.log_message(
                    f"Added position: {description} ({self.captured_x:.1f}%, {self.captured_y:.1f}%) [Absolute: {self.captured_abs_x}, {self.captured_abs_y}]")
            except AttributeError:
                self.log_message("Capture a position first!")
                return

    def remove_position(self):
        selected = self.positions_list.currentRow()
        if selected >= 0:
            removed = self.positions.pop(selected)
            self.update_positions_list()
            self.log_message(f"Removed position: {removed['description']}")

    def update_positions_list(self):
        self.positions_list.clear()
        for pos in self.positions:
            abs_text = f" [Absolute: {pos.get('abs_x', 'N/A')}, {pos.get('abs_y', 'N/A')}]"
            item = QListWidgetItem(f"{pos['description']} ({pos['x']:.1f}%, {pos['y']:.1f}%){abs_text}")
            self.positions_list.addItem(item)

    def on_position_select(self):
        selected = self.positions_list.currentRow()
        if selected >= 0:
            pos = self.positions[selected]
            self.log_message(f"Selected position: {pos['description']}")

    def capture_position(self):
        if not self.current_window_info:
            self.log_message("No window selected!")
            return

        try:
            mouse_x, mouse_y = win32api.GetCursorPos()
            rel_x = ((mouse_x - self.current_window_info["left"]) /
                     self.current_window_info["width"]) * 100
            rel_y = ((mouse_y - self.current_window_info["top"]) /
                     self.current_window_info["height"]) * 100

            rel_x = max(0, min(100, rel_x))
            rel_y = max(0, min(100, rel_y))

            # Store captured values
            self.captured_x = rel_x
            self.captured_y = rel_y
            self.captured_abs_x = mouse_x
            self.captured_abs_y = mouse_y

            confirm_dialog = QMessageBox(self)
            confirm_dialog.setWindowTitle("Confirm Position")
            confirm_dialog.setText(
                f"Absolute: ({mouse_x}, {mouse_y})\n"
                f"Relative: ({rel_x:.1f}%, {rel_y:.1f}%)\n\n"
                f"Save this position?"
            )
            confirm_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

            if confirm_dialog.exec() == QMessageBox.Yes:
                # Prompt for description and save
                dialog = PositionDialog(self)
                if dialog.exec():
                    description = dialog.description.text().strip()
                    if not description:
                        self.log_message("Position description cannot be empty!")
                        return

                    self.positions.append({
                        "description": description,
                        "x": rel_x,
                        "y": rel_y,
                        "abs_x": mouse_x,
                        "abs_y": mouse_y
                    })
                    self.update_positions_list()
                    self.log_message(
                        f"Position saved: {description} ({rel_x:.1f}%, {rel_y:.1f}%) [Absolute: {mouse_x}, {mouse_y}]")
                else:
                    self.log_message("Position capture canceled.")

                # Update spin boxes
                self.spin_x.setValue(rel_x)
                self.spin_y.setValue(rel_y)

        except Exception as e:
            self.log_message(f"Capture failed: {str(e)}")

    def load_presets(self) -> Dict:
        try:
            with open("presets.json", "r") as f:
                presets = json.load(f)
                for name in presets:
                    if 'positions' not in presets[name]:
                        presets[name]['positions'] = [{
                            'description': 'Main Position',
                            'x': presets[name].get('x_pos', 50),
                            'y': presets[name].get('y_pos', 50)
                        }]
                return presets
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_presets(self):
        with open("presets.json", "w") as f:
            json.dump(self.presets, f, indent=2)

    def update_preset_list(self):
        self.preset_list.clear()
        self.preset_list.addItems(sorted(self.presets.keys()))

    def detect_windows(self):
        self.window_titles = []
        ignored_classes = ["Progman", "WorkerW", "IME", "MSCTFIME UI", "Windows.UI.Core.CoreWindow"]

        def enum_windows(hwnd: int, _: int):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                class_name = win32gui.GetClassName(hwnd)
                if class_name in ignored_classes:
                    return
                title = win32gui.GetWindowText(hwnd).strip()
                if title and title not in self.window_titles:
                    self.window_titles.append(title)
            except Exception as e:
                self.log_message(f"Window detection error: {str(e)}")

        win32gui.EnumWindows(enum_windows, None)
        self.window_title_combo.clear()
        self.window_title_combo.addItems(sorted(self.window_titles))
        self.log_message(f"Detected {len(self.window_titles)} valid windows")

    def on_window_select(self, title: str):
        if title:
            self.current_window_info = None
            for _ in range(3):  # Retry up to 3 times
                info = self.get_window_info(title)
                if info and info.get('valid', False):
                    self.current_window_info = info
                    break
                time.sleep(0.1)

            if not self.current_window_info:
                self.log_message(f"Window '{title}' not found or invalid!")
                self.window_title_combo.setCurrentText("")

    def toggle_automation(self):
        if not self.running:
            if not self.positions:
                self.log_message("No positions configured!")
                return
            if not self.current_window_info or not self.current_window_info.get('valid', False):
                self.log_message("Invalid window configuration!")
                return

            config = {
                'window_title': self.window_title_combo.currentText(),
                'interval': self.spin_interval.value(),
                'positions': self.positions.copy()
            }

            self.stop_event = threading.Event()
            self.automation_thread = AutomationThread(self, config, self.stop_event)
            self.automation_thread.log_signal.connect(self.log_message)
            self.automation_thread.stopped.connect(self.on_automation_stop)
            self.automation_thread.start()
            self.btn_start.setText("Stop Automation")
            self.running = True
        else:
            self.stop_automation()

    def stop_automation(self):
        if self.running:
            self.stop_event.set()
            self.btn_start.setText("Start Automation")
            self.running = False
            self.log_message("Automation stopped")

    def on_automation_stop(self):
        self.running = False
        self.btn_start.setText("Start Automation")

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name:
            if name in self.presets:
                reply = QMessageBox.question(
                    self, "Overwrite",
                    f"Preset '{name}' exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            self.presets[name] = {
                'window_title': self.window_title_combo.currentText(),
                'interval': self.spin_interval.value(),
                'positions': self.positions.copy()
            }
            self.save_presets()
            self.update_preset_list()
            self.log_message(f"Preset '{name}' saved")

    def delete_preset(self):
        selected = self.preset_list.currentItem()
        if selected:
            name = selected.text()
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Delete preset '{name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                del self.presets[name]
                self.save_presets()
                self.update_preset_list()
                self.log_message(f"Deleted preset '{name}'")

    def load_preset(self):
        selected = self.preset_list.currentItem()
        if selected:
            name = selected.text()
            preset = self.presets.get(name)
            if preset:
                self.window_title_combo.setCurrentText(preset['window_title'])
                self.spin_interval.setValue(preset['interval'])
                self.positions = preset['positions'].copy()
                self.update_positions_list()
                self.current_window_info = self.get_window_info(preset['window_title'])
                self.log_message(f"Loaded preset '{name}'")

    def closeEvent(self, event):
        if self.running:
            self.stop_event.set()
        keyboard.unhook_all()
        event.accept()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = GameAutomationApp()
    window.show()
    sys.exit(app.exec())

    def on_automation_stop(self):
        self.running = False
        self.btn_start.setText("Start Automation")

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name:
            if name in self.presets:
                reply = QMessageBox.question(
                    self, "Overwrite",
                    f"Preset '{name}' exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            self.presets[name] = {
                'window_title': self.window_title_combo.currentText(),
                'interval': self.spin_interval.value(),
                'positions': self.positions.copy()
            }
            self.save_presets()
            self.update_preset_list()
            self.log_message(f"Preset '{name}' saved")

    def delete_preset(self):
        selected = self.preset_list.currentItem()
        if selected:
            name = selected.text()
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Delete preset '{name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                del self.presets[name]
                self.save_presets()
                self.update_preset_list()
                self.log_message(f"Deleted preset '{name}'")

    def load_preset(self):
        selected = self.preset_list.currentItem()
        if selected:
            name = selected.text()
            preset = self.presets.get(name)
            if preset:
                self.window_title_combo.setCurrentText(preset['window_title'])
                self.spin_interval.setValue(preset['interval'])
                self.positions = preset['positions'].copy()
                self.update_positions_list()
                self.current_window_info = self.get_window_info(preset['window_title'])
                self.log_message(f"Loaded preset '{name}'")

    def closeEvent(self, event):
        if self.running:
            self.stop_event.set()
        keyboard.unhook_all()
        event.accept()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = GameAutomationApp()
    window.show()
    sys.exit(app.exec())
