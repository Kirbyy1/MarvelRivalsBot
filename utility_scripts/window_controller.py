import win32gui
import win32con
from typing import List, Optional, Dict
import win32api
import win32process

class WindowError(Exception):
    """Base exception for window management errors"""
    pass


class WindowNotFoundError(WindowError):
    """Exception raised when target window is not found"""
    pass


class WindowStateError(WindowError):
    """Exception raised for invalid window state operations"""
    pass

class WindowNotMovableError(WindowError):
    pass

class WindowNotResizableError(WindowError):
    pass



class WindowController:
    """
    Advanced Windows window controller using Win32 API

    Attributes:
        hwnd (int): Windows handle for the target window
    """

    _dpi_initialized = False

    def __init__(self, hwnd: int):
        if not WindowController._dpi_initialized:
            self._init_dpi_awareness()
            WindowController._dpi_initialized = True

        if not win32gui.IsWindow(hwnd):
            raise WindowError("Invalid window handle")
        self.hwnd = hwnd
        self._check_capabilities()

    def debug_window(self):
        """Print detailed window information"""
        print(f"Win32 Position: {self.get_position()}")
        print(f"Style Flags: {hex(win32gui.GetWindowLong(self.hwnd, win32con.GWL_STYLE))}")
        print(f"Extended Style: {hex(win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE))}")

    @classmethod
    def _init_dpi_awareness(cls):
        """Ensure proper DPI scaling handling"""
        try:
            win32gui.SetProcessDPIAware()
            win32api.SetProcessDPIAware()
        except AttributeError:
            pass

    def _check_capabilities(self):
        """Check window style for movement and resize capabilities"""
        style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_STYLE)

        # Check if window has title bar (required for standard moving)
        self.movable = bool(style & win32con.WS_CAPTION)

        # Check if window is resizable
        self.resizable = bool(style & (win32con.WS_THICKFRAME | win32con.WS_SIZEBOX))

    def set_position(self, x: int, y: int):
        """Force window position even for stubborn applications"""
        try:
            self._force_restore()
            width, height = self.get_size()

            # Bypass window style restrictions
            style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_STYLE)
            new_style = style & ~win32con.WS_POPUP
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_STYLE, new_style)

            # Use multiple positioning methods
            for attempt in range(3):
                win32gui.MoveWindow(self.hwnd, x, y, width, height, True)
                win32gui.SetWindowPos(
                    self.hwnd, win32con.HWND_TOP,
                    x, y, 0, 0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED
                )

                if self._verify_position(x, y, margin=2):
                    return

            # Final attempt using alternate coordinates
            screen_x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            screen_y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            win32gui.SetWindowPos(
                self.hwnd, win32con.HWND_TOP,
                screen_x + x, screen_y + y, 0, 0,
                win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
            )

            if not self._verify_position(x, y, margin=2):
                raise WindowError("Window actively resisting positioning")

        except Exception as e:
            raise WindowError(f"Positioning failed: {str(e)}") from e

    @classmethod
    def get_display_info(cls) -> Dict:
        """Get primary display information"""
        primary_monitor = win32api.MonitorFromPoint(
            (0, 0), win32con.MONITOR_DEFAULTTOPRIMARY
        )
        monitor_info = win32api.GetMonitorInfo(primary_monitor)

        return {
            'screen_count': win32api.GetSystemMetrics(win32con.SM_CMONITORS),
            'primary_size': (
                win32api.GetSystemMetrics(win32con.SM_CXSCREEN),
                win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            ),
            'work_area': monitor_info.get('Work', (0, 0, 0, 0)),
            'monitor_area': monitor_info.get('Monitor', (0, 0, 0, 0))
        }
    # Full Window: (246, 104, 1673, 927)
    # Client Area: (246, 103, 1673, 927)
    # Left border: 0px | Title bar: -1px

    def set_foreground(self):
        """Bring window to foreground with robust focus handling"""
        try:
            # Ensure we have the root window handle
            root_hwnd = win32gui.GetAncestor(self.hwnd, win32con.GA_ROOT)

            # 1. Restore if minimized
            if win32gui.IsIconic(root_hwnd):
                win32gui.ShowWindow(root_hwnd, win32con.SW_RESTORE)

            # 2. Bring to top
            win32gui.SetWindowPos(
                root_hwnd,
                win32con.HWND_TOP,
                0, 0, 0, 0,
                win32con.SWP_NOSIZE | win32con.SWP_NOMOVE | win32con.SWP_SHOWWINDOW
            )

            # 3. Thread input handling
            current_thread = win32api.GetCurrentThreadId()
            target_thread = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]

            # Attach to foreground thread's input queue
            if current_thread != target_thread:
                win32process.AttachThreadInput(current_thread, target_thread, True)

            # 4. Try multiple activation strategies
            for attempt in range(3):
                try:
                    # Strategy 1: Standard SetForegroundWindow
                    win32gui.SetForegroundWindow(root_hwnd)

                    # Strategy 2: BringWindowToTop as fallback
                    if win32gui.GetForegroundWindow() != root_hwnd:
                        win32gui.BringWindowToTop(root_hwnd)
                        win32gui.UpdateWindow(root_hwnd)

                    # Strategy 3: Undocumented SwitchToThisWindow (ctypes fallback)
                    if win32gui.GetForegroundWindow() != root_hwnd and attempt == 2:
                        import ctypes
                        ctypes.windll.user32.SwitchToThisWindow(root_hwnd, True)

                    # Verify success
                    if win32gui.GetForegroundWindow() == root_hwnd:
                        break

                except Exception as e:
                    if attempt == 2:
                        raise RuntimeError(f"Final foreground attempt failed: {str(e)}")

            # 5. Simulate click if still not focused (last resort)
            if win32gui.GetForegroundWindow() != root_hwnd:
                rect = win32gui.GetWindowRect(root_hwnd)
                x = rect[0] + (rect[2] - rect[0]) // 2
                y = rect[1] + (rect[3] - rect[1]) // 2
                win32api.SetCursorPos((x, y))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

            # Detach thread input if attached
            if current_thread != target_thread:
                win32process.AttachThreadInput(current_thread, target_thread, False)

        except Exception as e:
            print(f"Foreground activation failed: {str(e)}")
            raise

    def _force_restore(self):
        """Properly restore window using window placement"""
        try:
            placement = list(win32gui.GetWindowPlacement(self.hwnd))
            # Correctly set showCmd to RESTORE (index 2)
            if placement[1] != win32con.SW_SHOWNORMAL:
                placement[1] = win32con.SW_RESTORE
            # Maintain other placement values
            win32gui.SetWindowPlacement(self.hwnd, tuple(placement))
        except Exception as e:
            raise WindowError(f"Restore failed: {str(e)}") from e

    def get_monitor_info(self) -> Dict:
        """Get monitor information for current window"""
        monitor = win32api.MonitorFromWindow(self.hwnd)
        return win32api.GetMonitorInfo(monitor)

    @classmethod
    def from_title(cls, title_part: str) -> 'WindowController':
        """Find window by partial title match"""
        handles = []

        def enum_handler(hwnd, ctx):
            if title_part.lower() in win32gui.GetWindowText(hwnd).lower():
                handles.append(hwnd)

        win32gui.EnumWindows(enum_handler, None)

        if not handles:
            raise WindowNotFoundError(
                f"No window found containing '{title_part}'. "
                f"Available windows: {cls.list_titles()}"
            )
        return cls(handles[0])

    @classmethod
    def list_titles(cls) -> List[str]:
        """Get list of all window titles"""
        titles = []

        def enum_handler(hwnd, ctx):
            if title := win32gui.GetWindowText(hwnd):
                titles.append(title)

        win32gui.EnumWindows(enum_handler, None)
        return titles

    def set_bounds(self, x: int, y: int, width: int, height: int):
        """Set both position and size if possible"""
        try:
            # First try to move (even if resizing fails)
            if self.movable:
                self.set_position(x, y)

            if not self.resizable:
                raise WindowNotResizableError("Window does not allow resizing")

            # If resizable, proceed with resizing
            monitor_info = self.get_monitor_info()
            work_area = monitor_info["Work"]

            width = max(100, min(width, work_area[2] - work_area[0] - 20))
            height = max(100, min(height, work_area[3] - work_area[1] - 20))

            win32gui.MoveWindow(self.hwnd, x, y, width, height, True)
            win32gui.SetWindowPos(
                self.hwnd, win32con.HWND_TOP,
                x, y, width, height,
                win32con.SWP_ASYNCWINDOWPOS | win32con.SWP_SHOWWINDOW
            )

            if not self._verify_bounds(x, y, width, height):
                current = self.get_position() + self.get_size()
                raise WindowError(
                    f"Bounds mismatch\nTarget: {x},{y} {width}x{height}\n"
                    f"Actual: {current}"
                )

        except Exception as e:
            if isinstance(e, WindowNotResizableError):
                print(f"Resize blocked: {str(e)}")
                return
            raise WindowError(f"Set bounds failed: {str(e)}") from e

    def _verify_position(self, x: int, y: int, margin: int = 5) -> bool:
        """Strict position verification"""
        current_x, current_y = self.get_position()
        return (
                abs(current_x - x) <= margin and
                abs(current_y - y) <= margin
        )

    def _verify_bounds(self, x: int, y: int, width: int, height: int) -> bool:
        """Combined position and size verification"""
        return (
            self._verify_position(x, y) and
            abs(self.get_size()[0] - width) <= 100 and
            abs(self.get_size()[1] - height) <= 100
        )

    def set_background(self):
        """
        Send window to background (bottom of Z-order)
        """
        win32gui.SetWindowPos(
            self.hwnd,
            win32con.HWND_BOTTOM,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
        )


    @classmethod
    def list_all(cls) -> List['WindowController']:
        """List all available windows"""
        windows = []

        def enum_handler(hwnd: int, ctx: list):
            if win32gui.GetWindowText(hwnd):
                windows.append(cls(hwnd))

        win32gui.EnumWindows(enum_handler, None)
        return windows


    @property
    def title(self) -> str:
        """Get window title"""
        return win32gui.GetWindowText(self.hwnd)

    def get_position(self) -> tuple[int, int]:
        """Get current window position (x, y) coordinates"""
        rect = win32gui.GetWindowRect(self.hwnd)
        x, y = rect[0], rect[1]

        # Ensure the window is not off-screen (negative coordinates)
        if x < 0:
            x = 0
        if y < 0:
            y = 0

        return (x, y)

    def get_client_region(self) -> tuple[int, int, int, int]:
        """Get the client area coordinates (excluding borders/titlebar)"""
        client_rect = win32gui.GetClientRect(self.hwnd)
        # Convert client-area coordinates to screen coordinates
        (left, top) = win32gui.ClientToScreen(self.hwnd, (client_rect[0], client_rect[1]))
        (right, bottom) = win32gui.ClientToScreen(self.hwnd, (client_rect[2], client_rect[3]))
        return (left, top, right, bottom)

    def get_window_region(self) -> tuple[int, int, int, int]:
        """Get the region (bounding box) of the window in the form (left, top, right, bottom)"""
        rect = win32gui.GetWindowRect(self.hwnd)

        # Optionally, ensure the region is within the screen bounds
        screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        left = max(0, rect[0])
        top = max(0, rect[1])
        right = min(screen_width, rect[2])
        bottom = min(screen_height, rect[3])

        return (left, top, right, bottom)

    def get_window_info(self, window_title: str) -> Optional[Dict]:
        try:
            window = WindowController.from_title(window_title)
            left, top, right, bottom = window.get_window_region()

            # Get screen bounds for the monitor where the window resides
            monitor_info = window.get_monitor_info()
            work_area = monitor_info["Work"]
            screen_left, screen_top, screen_right, screen_bottom = work_area

            # Clamp window coordinates to visible screen area
            clamped_left = max(screen_left, left)
            clamped_top = max(screen_top, top)
            clamped_right = min(screen_right, right)
            clamped_bottom = min(screen_bottom, bottom)

            # Calculate visible window dimensions
            visible_width = clamped_right - clamped_left
            visible_height = clamped_bottom - clamped_top

            # Get client area dimensions (content region)
            client_rect = win32gui.GetClientRect(window.hwnd)
            client_width = client_rect[2] - client_rect[0]
            client_height = client_rect[3] - client_rect[1]

            # Calculate visible client area (adjusted for off-screen)
            border_width = (visible_width - client_width) // 2
            title_bar_height = visible_height - client_height - border_width

            return {
                "hwnd": window.hwnd,
                "left": clamped_left + border_width,
                "top": clamped_top + title_bar_height,
                "width": max(0, client_width - (clamped_left - left)),  # Adjust for clipped area
                "height": max(0, client_height - (clamped_top - top)),  # Adjust for clipped area
                "scale_factor": self.get_dpi_scaling(window.hwnd),
                "valid": True
            }
        except Exception as e:
            print(f"Window error: {str(e)}")
            return None


    def get_size(self) -> tuple[int, int]:
        """Get current window dimensions (width, height)"""
        rect = win32gui.GetWindowRect(self.hwnd)
        return (rect[2] - rect[0], rect[3] - rect[1])

    def move(self, x: int, y: int):
        """
        Move window to new position while maintaining current size

        Args:
            x: New x-coordinate for top-left corner
            y: New y-coordinate for top-left corner
        """
        width, height = self.get_size()
        win32gui.MoveWindow(self.hwnd, x, y, width, height, True)

    def resize(self, width: int, height: int):
        """
        Resize window while maintaining current position

        Args:
            width: New window width in pixels
            height: New window height in pixels
        """
        x, y = self.get_position()
        win32gui.MoveWindow(self.hwnd, x, y, width, height, True)



    def minimize(self):
        """Minimize the window to taskbar"""
        win32gui.ShowWindow(self.hwnd, win32con.SW_MINIMIZE)

    def maximize(self):
        """Maximize the window"""
        win32gui.ShowWindow(self.hwnd, win32con.SW_MAXIMIZE)

    def restore(self):
        """Restore window from minimized/maximized state"""
        win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)

    def is_maximized(self) -> bool:
        """Check if window is currently maximized"""
        placement = win32gui.GetWindowPlacement(self.hwnd)
        return placement[1] == win32con.SW_MAXIMIZE

    def is_minimized(self) -> bool:
        """Check if window is currently minimized"""
        placement = win32gui.GetWindowPlacement(self.hwnd)
        return placement[1] == win32con.SW_MINIMIZE

    def is_visible(self) -> bool:
        """Check if window is currently visible"""
        return win32gui.IsWindowVisible(self.hwnd)


if __name__ == "__main__":
    try:
        print("Available windows:", WindowController.list_titles())

        target = WindowController.from_title("Chrome")
        display = WindowController.get_display_info()
        print(target.get_window_region())
        # Try moving even if resizing fails
        target.set_foreground()
        target.set_position(0, 0)
        print(target.get_position())


    except WindowError as e:
        print(f"Operation failed: {e}")