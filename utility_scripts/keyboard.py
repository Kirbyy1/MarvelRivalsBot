#!/usr/bin/env python3
"""
human_like_keyboard.py

A module to simulate human-like keyboard input for educational purposes.
This module provides functions to simulate natural typing behavior including
random delays between key presses, realistic key press durations, and optional
typo simulation with correction.

Usage:
    import human_like_keyboard

    # Type a sentence with human-like behavior
    human_like_keyboard.human_like_type(
        "Hello, world!",
        min_interval=0.05,
        max_interval=0.2,
        simulate_typo=True,
        typo_probability=0.05
    )
"""

import time
import random
import pyautogui

pyautogui.FAILSAFE = False

class KeyboardInputError(Exception):
    """Custom exception for errors during keyboard input simulation."""
    pass

def press_key(key: str, press_duration_min: float = 0.05, press_duration_max: float = 0.15) -> None:
    """
    Simulate pressing and releasing a key with a randomized key press duration.

    Args:
        key (str): The key to press. For example, 'a', 'enter', 'space', etc.
        press_duration_min (float): Minimum duration (in seconds) to hold the key down.
        press_duration_max (float): Maximum duration (in seconds) to hold the key down.
    """
    duration = random.uniform(press_duration_min, press_duration_max)
    pyautogui.keyDown(key)
    time.sleep(duration)
    pyautogui.keyUp(key)

def human_like_type(
    text: str,
    min_interval: float = 0.05,
    max_interval: float = 0.2,
    simulate_typo: bool = False,
    typo_probability: float = 0.05
) -> None:
    """
    Simulate human-like typing of the provided text.

    The function types each character individually with randomized delays between
    keystrokes and simulates realistic key press durations. Optionally, it can simulate
    occasional typos and then correct them by sending a backspace before typing the
    correct character.

    Args:
        text (str): The text to be typed.
        min_interval (float): Minimum delay (in seconds) between key presses.
        max_interval (float): Maximum delay (in seconds) between key presses.
        simulate_typo (bool): If True, simulate occasional typos.
        typo_probability (float): The probability (0.0 to 1.0) of a typo on any given character.

    Raises:
        KeyboardInputError: If an error occurs during keyboard simulation.
    """
    try:
        for char in text:
            # Optionally simulate a typo before the correct key is pressed.
            if simulate_typo and random.random() < typo_probability:
                # Choose a random wrong character from a set of letters.
                wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                # Match case if needed.
                if char.isupper():
                    wrong_char = wrong_char.upper()
                # Simulate pressing the wrong key.
                if wrong_char.isupper():
                    pyautogui.keyDown('shift')
                    press_key(wrong_char.lower())
                    pyautogui.keyUp('shift')
                else:
                    press_key(wrong_char)
                # Wait a short random interval.
                time.sleep(random.uniform(min_interval, max_interval))
                # Press backspace to delete the wrong character.
                press_key('backspace')
                time.sleep(random.uniform(min_interval, max_interval))

            # Now type the intended character.
            # For letters that require shift (uppercase), press shift.
            if char.isupper():
                pyautogui.keyDown('shift')
                press_key(char.lower())
                pyautogui.keyUp('shift')
            # For space characters, use 'space'
            elif char == ' ':
                press_key('space')
            # For common punctuation and digits, use the character directly.
            elif char.islower() or char.isdigit() or char in ".,;:'\"!?/\\|[]{}()-_=+<>@#$%^&*`~":
                press_key(char)
            else:
                # If the character is unhandled, fallback to pyautogui.write
                pyautogui.write(char)

            # Wait a randomized interval before typing the next character.
            time.sleep(random.uniform(min_interval, max_interval))
    except Exception as e:
        raise KeyboardInputError("Error during human-like typing: " + str(e))

# Optional: Test the human_like_type function when running this module directly.
if __name__ == "__main__":
    sample_text = "Hello, world! This is a test of human-like typing."
    print("Typing sample text...")
    human_like_type(
        sample_text,
        min_interval=0.05,
        max_interval=0.08,
        simulate_typo=True,
        typo_probability=0.1
    )
    print("Done typing.")
