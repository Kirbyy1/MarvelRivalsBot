#!/usr/bin/env python3
"""
mouse_position_calculator.py

A module to calculate and move the mouse cursor to a target position within
a specified window's client area. The target position is determined by relative
percentages of the client area's dimensions.

Usage:
    Create your window instance (with methods such as set_foreground,
    get_window_region, and get_client_region) in your main file, then pass it
    to these functions as follows:

        window = WindowController.from_title("Loading Bay")
        move_to_target_position(window, 0.488, 0.682)
"""

import time
from typing import Any

import pyautogui
import random
import math

class MousePositionCalculationError(Exception):
    """Custom exception for mouse position calculation errors."""
    pass


def random_click(button: str = 'left', min_press_duration: float = 0.05, max_press_duration: float = 0.2) -> None:
    """
    Simulates a mouse click with a randomized delay between the press and release actions.

    Args:
        button (str): The mouse button to click. Valid values include 'left', 'right', and 'middle'.
        min_press_duration (float): The minimum time (in seconds) to hold the mouse button down.
        max_press_duration (float): The maximum time (in seconds) to hold the mouse button down.
    """
    # Press the specified mouse button down.
    pyautogui.mouseDown(button=button)

    # Wait for a random duration between min_press_duration and max_press_duration.
    delay = random.uniform(min_press_duration, max_press_duration)
    time.sleep(delay)

    # Release the mouse button.
    pyautogui.mouseUp(button=button)

def get_bezier_point(t, p0, p1, p2, p3):
    """
    Calculate a point in a cubic Bezier curve.
    t: parameter between 0 and 1
    p0, p1, p2, p3: control points (tuples of x, y)
    """
    x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
    y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
    return x, y


def human_like_mouse_move(target_x, target_y):
    """
    Moves the mouse to the target position using a Bezier curve with human-like acceleration and slight path variation.
    """
    start_x, start_y = pyautogui.position()
    max_jitter = 2  # Maximum jitter for final position

    if (start_x, start_y) == (target_x, target_y):
        return

    # Calculate displacement for control points
    dx = target_x - start_x
    dy = target_y - start_y
    distance = math.hypot(dx, dy)

    # Generate perpendicular direction vector
    perp_dx = dy / distance if distance != 0 else 0
    perp_dy = -dx / distance if distance != 0 else 0

    # Create control points with slight random displacement
    disp_factor = distance * 0.1  # Up to 10% of distance displacement
    cp1_disp = random.uniform(-disp_factor, disp_factor)
    cp2_disp = random.uniform(-disp_factor, disp_factor)

    # Cubic Bezier control points
    p0 = (start_x, start_y)
    p1 = (start_x + dx / 3 + perp_dx * cp1_disp,
          start_y + dy / 3 + perp_dy * cp1_disp)
    p2 = (start_x + 2 * dx / 3 + perp_dx * cp2_disp,
          start_y + 2 * dy / 3 + perp_dy * cp2_disp)
    p3 = (target_x, target_y)

    # Dynamic step calculation based on distance
    steps = max(10, min(30, int(distance / 5)))  # 10-30 steps
    points = []

    # Generate points with sinusoidal easing
    for i in range(steps):
        t = i / (steps - 1)
        t_ease = 0.5 * (1 - math.cos(t * math.pi))  # Ease-in-out
        bx, by = get_bezier_point(t_ease, p0, p1, p2, p3)
        points.append((bx, by))

    # Calculate dynamic movement time (faster for shorter distances)
    base_speed = random.uniform(0.0003, 0.0006)  # pixels per second
    total_time = distance * base_speed
    total_time = max(min(total_time, 0.25), 0.08)  # 80-250ms

    # Move through the points
    for i, (bx, by) in enumerate(points):
        if i == 0:
            continue

        # Calculate step duration with some randomness
        step_ratio = (i / steps) * random.uniform(0.9, 1.1)
        duration = (total_time / steps) * step_ratio

        pyautogui.moveTo(bx, by, duration=max(duration, 0.001))

    # Add final precision jitter
    jitter_x = random.randint(-max_jitter, max_jitter)
    jitter_y = random.randint(-max_jitter, max_jitter)
    pyautogui.moveTo(target_x + jitter_x, target_y + jitter_y, duration=0.03)

def calculate_target_position(window, relative_x: float, relative_y: float, stabilization_time: float = 1.0) -> tuple:
    """
    Calculate the absolute screen coordinates for a target position based on the
    relative position within the window's client area.

    Args:
        window: An instance of your window controller for the target window.
                It is expected to have methods such as set_foreground(),
                get_window_region(), and get_client_region().
        relative_x (float): Relative x-coordinate (0.0 to 1.0) of the client area's width.
        relative_y (float): Relative y-coordinate (0.0 to 1.0) of the client area's height.
        stabilization_time (float): Time in seconds to wait after setting the window to the foreground.

    Returns:
        tuple: (target_x, target_y) representing the absolute screen coordinates.

    Raises:
        MousePositionCalculationError: If any error occurs during the calculation.
    """
    try:
        # Bring the window to the foreground and allow it to stabilize.
        window.set_foreground()
        time.sleep(stabilization_time)
    except Exception as e:
        raise MousePositionCalculationError("Error setting window to foreground: " + str(e))

    try:
        # Retrieve full window and client area regions.
        full_region = window.get_window_region()  # Expected: (left, top, right, bottom)
        client_region = window.get_client_region()  # Expected: (left, top, right, bottom)
    except Exception as e:
        raise MousePositionCalculationError("Error retrieving window regions: " + str(e))

    if not (full_region and client_region and len(full_region) == 4 and len(client_region) == 4):
        raise MousePositionCalculationError("Invalid window region(s) returned.")

    try:
        # Compute the client area's width and height.
        client_left, client_top, client_right, client_bottom = client_region
        client_width = client_right - client_left
        client_height = client_bottom - client_top

        # Calculate the absolute target position using the relative percentages.
        target_x = client_left + (client_width * relative_x)
        target_y = client_top + (client_height * relative_y)
    except Exception as e:
        raise MousePositionCalculationError("Error calculating target position: " + str(e))

    return target_x, target_y


def move_to_target_position(window, relative_x: float, relative_y: float) -> tuple[Any, Any]:
    """
    Moves the mouse cursor to the target position determined by relative coordinates
    within the client area of the specified window.

    Args:
        window: An instance of your window controller for the target window.
        relative_x (float): Relative x-coordinate (0.0 to 1.0) of the client area's width.
        relative_y (float): Relative y-coordinate (0.0 to 1.0) of the client area's height.

    Raises:
        MousePositionCalculationError: If any error occurs during the movement process.
    """
    try:
        target_x, target_y = calculate_target_position(window, relative_x, relative_y)
        human_like_mouse_move(target_x, target_y)
        return target_x, target_y
    except MousePositionCalculationError as e:
        raise MousePositionCalculationError("Failed to calculate target position: " + str(e))

