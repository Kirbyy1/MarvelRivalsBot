import time
import re
import logging
from logging.handlers import RotatingFileHandler
import traceback
import sys
import argparse
import unittest
from unittest.mock import patch
import psutil  # Add this import at the top

# Configuration
config_file = {
    "loading_bay_exe": r'E:\ALL FILES FROM MAIN PC\LoadingBay\LoadingBayLauncher.exe',
    "change_settings": True,
    "confidence": 0.75,
    "grayscale": True,
    "delay": 10,
    "process_name": "LoadingBayInstaller.exe",
    "window_name": "Loading Bay",
    "typing_options": {
        "min_interval": 0.05,
        "max_interval": 0.2,
        "simulate_typo": True,
        "typo_probability": 0.1,
    },
    "key_press_options": {
        "key_press_duration_min": 0.05,
        "key_press_duration_max": 0.15,
    },
    "mouse_options": {
        "button": "left",
        "min_press_duration": 0.05,
        "max_press_duration": 0.2,
        "max_jitter": 2,
    }
}

relative_position = {
    "Launcher": {
        "username": (0.473, 0.463),
        "sign_in": (0.488, 0.682)
    },
    "Game": {
        "my_games": (0.302, 0.137),
        "marvel_rivals": (0.093, 0.185),
        "start_game": (0.783, 0.803)
    }
}

images = {'pfp': 'test.png'}


# Add resource monitoring decorator
def monitor_resources(func):
    def wrapper(*args, **kwargs):
        process = psutil.Process()
        start_time = time.time()
        cpu_samples = []
        mem_samples = []

        result = func(*args, **kwargs)

        # Collect metrics every 0.5 seconds during execution
        while time.time() - start_time < 0.5:
            cpu_samples.append(psutil.cpu_percent())
            mem_samples.append(process.memory_info().rss / (1024 ** 2))  # MB
            time.sleep(0.1)

        avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
        avg_mem = sum(mem_samples) / len(mem_samples) if mem_samples else 0
        logger.info(f"Resource usage - {func.__name__}: {avg_cpu:.1f}% CPU, {avg_mem:.1f}MB RAM")
        return result

    return wrapper


# Logging setup
def setup_logging():
    log_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s'
    )

    file_handler = RotatingFileHandler(
        'automation.log',
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)


def validate_config():
    """Validate configuration values"""
    if not 0 <= config_file["confidence"] <= 1:
        raise ValueError("Confidence must be between 0 and 1")
    if config_file["delay"] < 0:
        raise ValueError("Delay cannot be negative")
    if not isinstance(config_file["window_name"], str):
        raise TypeError("Window name must be a string")


# Utility imports and mock setup
try:
    from utility_scripts.process_manager import run_exe, terminate_process_windows
    from utility_scripts.window_controller import WindowController
    from utility_scripts.keyboard import human_like_type, press_key
    from utility_scripts.image_detection import find_image_position, preprocess_image
    from utility_scripts.mouse_position_calculator import random_click, human_like_mouse_move, calculate_target_position
except ImportError:
    logger.warning("Utility scripts not found - running in test mode")


# Modified login function with resource monitoring
@monitor_resources
def login(username: str, password: str):
    try:
        validate_config()
        logger.info(f"Starting login process for {username}")

        # Process termination
        termination_result = terminate_process_windows(config_file["process_name"])
        if not termination_result.get("success"):
            logger.error(f"Process termination failed: {termination_result.get('error')}")
            return False

        # Application launch
        try:
            run_output = run_exe(config_file["loading_bay_exe"])
        except Exception as e:
            logger.critical(f"EXE launch failed: {str(e)}")
            return False

        # Server startup check
        start_time = time.time()
        server_started = False
        while time.time() - start_time < 30:
            if re.search(r"Server\s+started", run_output):
                server_started = True
                break
            time.sleep(config_file['delay'])
            run_output = run_exe(config_file["loading_bay_exe"])
        if not server_started:
            logger.error("Server startup timeout")
            return False

        # Window management
        try:
            window = WindowController.from_title(config_file['window_name'])
            if window:
                try:
                    window.set_foreground()
                except Exception as e:
                    logger.warning(f"Window focus failed: {str(e)}")
                    window.maximize()
                    time.sleep(1)
                logger.debug("Window focused")
            else:
                logger.error("Window not found")
                return False
        except Exception as e:
            logger.error(f"Window error: {str(e)}")
            return False

        # Image processing
        try:
            template = preprocess_image(images['pfp'], grayscale=True)
            region = window.get_window_region()
        except MemoryError as e:
            logger.critical(f"Memory error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Image error: {str(e)}")
            return False

        # Set window again in foreground:
        window.set_foreground()
        # Authentication workflow
        position, _ = find_image_position(
            template=template,
            confidence=config_file["confidence"],
            screen_region=region
        )

        if position:
            try:
                mouse_opts = config_file["mouse_options"]

                human_like_mouse_move(position[0] + 15, position[1] + 15)
                random_click(button=config_file["mouse_options"]["button"],
                             min_press_duration=config_file["mouse_options"]["min_press_duration"],
                             max_press_duration=config_file["mouse_options"]["max_press_duration"])
                time.sleep(2)

                x, y = calculate_target_position(window, *relative_position['Launcher']['username'])
                human_like_mouse_move(x, y)

                random_click(button=config_file["mouse_options"]["button"],
                             min_press_duration=config_file["mouse_options"]["min_press_duration"],
                             max_press_duration=config_file["mouse_options"]["max_press_duration"])

                human_like_type(text=username, min_interval=config_file["typing_options"]["min_interval"],
                                max_interval=config_file["typing_options"]["max_interval"],
                                simulate_typo=config_file["typing_options"]["simulate_typo"],
                                typo_probability=config_file["typing_options"]["typo_probability"])
                press_key('tab', press_duration_min=config_file['key_press_options']['key_press_duration_min'],
                          press_duration_max=config_file['key_press_options']['key_press_duration_max'])

                human_like_type(text=password, min_interval=config_file["typing_options"]["min_interval"],
                                max_interval=config_file["typing_options"]["max_interval"],
                                simulate_typo=config_file["typing_options"]["simulate_typo"],
                                typo_probability=config_file["typing_options"]["typo_probability"])

                x, y = calculate_target_position(window, *relative_position['Launcher']['sign_in'])
                human_like_mouse_move(x, y)
                random_click(button=config_file["mouse_options"]["button"],
                             min_press_duration=config_file["mouse_options"]["min_press_duration"],
                             max_press_duration=config_file["mouse_options"]["max_press_duration"])

                time.sleep(5)
                new_position, _ = find_image_position(template=template, confidence=config_file["confidence"],
                                                      screen_region=region)
                return not new_position
            except ImportError as e:
                logger.error(f"Authentication error: {str(e)}")
                return False
        else:
            logger.info("Already logged in")
            return True

    except ImportError as e:
        logger.critical(f"Login critical error: {str(e)}\n{traceback.format_exc()}")
        return False


# Modified login function with resource monitoring
@monitor_resources
def launch_game():
    try:
        logger.info("Initiating game launch")
        window = WindowController.from_title(config_file['window_name'])
        if not window:
            logger.error("Game window not found")
            return False

        mouse_opts = config_file["mouse_options"]

        for step in ['my_games', 'marvel_rivals', 'start_game']:
            x, y = calculate_target_position(window, *relative_position['Game'][step])
            human_like_mouse_move(x, y)
            random_click(button=config_file["mouse_options"]["button"],
                         min_press_duration=config_file["mouse_options"]["min_press_duration"],
                         max_press_duration=config_file["mouse_options"]["max_press_duration"])
        time.sleep(2)

        time.sleep(config_file['delay'])
        press_key('left', **config_file["key_press_options"])
        press_key('enter', **config_file["key_press_options"])
        return True

    except Exception as e:
        logger.error(f"Game launch failed: {str(e)}\n{traceback.format_exc()}")
        return False


# class TestAutomation(unittest.TestCase):
#     def setUp(self):
#         self.original_config = config_file.copy()
#         self.valid_username = "test_user"
#         self.valid_password = "test_pass"
#
#     def tearDown(self):
#         config_file.clear()
#         config_file.update(self.original_config)
#
#     @patch('main.terminate_process_windows')
#     @patch('main.run_exe')
#     def test_successful_login(self, mock_run, mock_terminate):
#         mock_terminate.return_value = {"success": True}
#         mock_run.return_value = "Server started"
#         self.assertTrue(login(self.valid_username, self.valid_password))
#
#     @patch('main.terminate_process_windows')
#     def test_process_termination_failure(self, mock_terminate):
#         mock_terminate.return_value = {"success": False, "error": "Access denied"}
#         self.assertFalse(login(self.valid_username, self.valid_password))
#
#     @patch('main.run_exe')
#     def test_server_start_timeout(self, mock_run):
#         mock_run.return_value = "Loading..."
#         self.assertFalse(login(self.valid_username, self.valid_password))
#
#     @patch('main.find_image_position')
#     def test_existing_session_handling(self, mock_image):
#         mock_image.return_value = (None, 0.0)
#         self.assertTrue(login(self.valid_username, self.valid_password))
#
#     @patch('main.preprocess_image')
#     def test_corrupted_image_file(self, mock_preprocess):
#         mock_preprocess.side_effect = FileNotFoundError
#         self.assertFalse(login(self.valid_username, self.valid_password))
#
#     @patch('main.WindowController.from_title')
#     def test_window_not_found(self, mock_window):
#         mock_window.return_value = None
#         self.assertFalse(login(self.valid_username, self.valid_password))
#
#     @patch('main.human_like_type')
#     def test_keyboard_input_failure(self, mock_type):
#         mock_type.side_effect = Exception("Input blocked")
#         self.assertFalse(login(self.valid_username, self.valid_password))
#
#     @patch('main.random_click')
#     def test_mouse_click_failure(self, mock_click):
#         mock_click.side_effect = Exception("Click failed")
#         self.assertFalse(login(self.valid_username, self.valid_password))
#
#     @patch('main.calculate_target_position')
#     def test_ui_layout_changes(self, mock_position):
#         mock_position.return_value = (9999, 9999)
#         self.assertFalse(launch_game())
#
#     @patch('main.find_image_position')
#     def test_low_memory_operation(self, mock_image):
#         mock_image.side_effect = MemoryError
#         self.assertFalse(login(self.valid_username, self.valid_password))
#
#     @patch('main.run_exe')
#     def test_server_connection_loss(self, mock_run):
#         mock_run.side_effect = ["Server started", "Connection lost"]
#         self.assertFalse(login(self.valid_username, self.valid_password))
#
#         # FIXED CONFIG VALIDATION TEST
#
#     def test_invalid_config_values(self):
#         original_confidence = config_file["confidence"]
#         config_file["confidence"] = 1.5
#         try:
#             with self.assertRaises(ValueError):
#                 login(self.valid_username, self.valid_password)
#         finally:
#             config_file["confidence"] = original_confidence
#
#     @patch('main.human_like_type')
#     @patch('main.find_image_position')
#     def test_special_character_handling(self, mock_image, mock_type):
#         mock_image.return_value = (None, 0.0)
#         mock_type.return_value = True
#         self.assertTrue(login("!@#$%^&*()", "\x01\x02\x03\x04"))
#
#     @patch('main.terminate_process_windows')
#     def test_multiple_sessions(self, mock_terminate):
#         mock_terminate.return_value = {"success": False}
#         result1 = login(self.valid_username, self.valid_password)
#         result2 = login(self.valid_username, self.valid_password)
#         self.assertFalse(result1 or result2)


#  IT SAYS WINDOWS FOCUSED EVEN THO IT WASNT
if __name__ == '__main__':
    login = login("test_user", "test_pass")
