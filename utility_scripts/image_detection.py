import pyautogui

import base64
from collections import namedtuple
import time
import numpy as np
from mss import mss
import cv2

# Define our own Box structure
Box = namedtuple('Box', ['left', 'top', 'width', 'height'])


# Convert base64 back to an OpenCV image
def base64_to_image(b64_string):
    image_data = base64.b64decode(b64_string)
    np_array = np.frombuffer(image_data, np.uint8)
    return cv2.imdecode(np_array, cv2.IMREAD_COLOR)


def preprocess_image(image_path, grayscale=True):
    """Preprocess the target image for faster matching"""
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if grayscale and len(img.shape) > 2:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def find_image_position(template, screen_region=None, confidence=0.8):
    """Returns (position, detection_time) tuple"""
    try:
        start_time = time.time()

        # Capture screen region only once
        if screen_region:
            screen = pyautogui.screenshot(region=screen_region)
        else:
            screen = pyautogui.screenshot()

        screen = np.array(screen)
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)

        # Use preprocessed template
        result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= confidence:
            h, w = template.shape[:2]
            left = max_loc[0] + (screen_region[0] if screen_region else 0)
            top = max_loc[1] + (screen_region[1] if screen_region else 0)
            return Box(left, top, w, h), time.time() - start_time

        return None, time.time() - start_time

    except Exception as e:
        print(f"Error: {str(e)}")
        return None, 0


def benchmark(image_path, num_tests=5, confidence=0.65, region=None):
    results = {
        'success_count': 0,
        'total_time': 0,
        'times': [],
        'failures': 0
    }

    # Preload template outside the loop
    template = preprocess_image(image_path, grayscale=True)

    for i in range(num_tests):
        position, duration = find_image_position(
            template=template,
            screen_region=region,
            confidence=confidence
        )
        results['times'].append(duration)
        results['total_time'] += duration

        if position:
            print(f'position:{position}')
            pyautogui.moveTo(position)
            results['success_count'] += 1
            print(f"Test {i + 1}: Found in {duration:.3f}s")
        else:
            results['failures'] += 1
            print(f"Test {i + 1}: Not found (took {duration:.3f}s)")

    return results


class TemplateScanner:
    def __init__(self, use_gpu=False):
        self.template_cache = {}
        self.sct = mss()
        self.use_gpu = use_gpu
        self.gpu_templates = {}

        if self.use_gpu and cv2.cuda.getCudaEnabledDeviceCount() > 0:
            self.gpu_matcher = cv2.cuda.createTemplateMatching(cv2.CV_8UC1, cv2.TM_CCOEFF_NORMED)
        else:
            self.use_gpu = False

    def preprocess_template(self, template, scale=1.0, cache_key=None):
        """Process and cache a template for repeated use"""
        if not isinstance(template, np.ndarray):
            template = cv2.imread(template, cv2.IMREAD_GRAYSCALE)

        processed = cv2.resize(template, None, fx=scale, fy=scale) if scale != 1.0 else template

        if cache_key:
            self.template_cache[cache_key] = processed
            if self.use_gpu:
                gpu_template = cv2.cuda_GpuMat()
                gpu_template.upload(processed)
                self.gpu_templates[cache_key] = (gpu_template, self.gpu_matcher)

        return processed

    def scan_frame(self, screen_frame, template, confidence=0.7, scale=1.0):
        """Scan a single frame with optional scaling"""
        start_time = time.perf_counter()

        # Convert to grayscale if needed
        if len(screen_frame.shape) == 3:
            screen_gray = cv2.cvtColor(screen_frame, cv2.COLOR_BGR2GRAY)
        else:
            screen_gray = screen_frame

        # Apply scaling
        if scale != 1.0:
            screen_gray = cv2.resize(screen_gray, None, fx=scale, fy=scale)

        # Get template from cache or process
        if isinstance(template, str):
            template = self.template_cache.get(template, None)
            if template is None:
                template = self.preprocess_template(template, scale, template)

        # GPU matching
        if self.use_gpu and isinstance(template, np.ndarray):
            cache_key = id(template)
            if cache_key not in self.gpu_templates:
                gpu_template = cv2.cuda_GpuMat()
                gpu_template.upload(template)
                self.gpu_templates[cache_key] = (gpu_template, self.gpu_matcher)

            gpu_screen = cv2.cuda_GpuMat()
            gpu_screen.upload(screen_gray)
            result = self.gpu_matcher.match(gpu_screen, self.gpu_templates[cache_key][0])
            result = result.download()
        else:
            result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)

        # Find matches
        match_locations = np.where(result >= confidence)
        matches = list(zip(*match_locations[::-1]))

        return matches, time.perf_counter() - start_time

    def continuous_scan(self, region, template, confidence=0.7, scale=0.7):
        """Generator for continuous scanning"""
        monitor = self.sct.monitors[1]
        if region:
            monitor = {
                "left": region[0],
                "top": region[1],
                "width": region[2],
                "height": region[3]
            }

        while True:
            frame = np.array(self.sct.grab(monitor))[:, :, :3]
            matches, scan_time = self.scan_frame(frame, template, confidence, scale)
            yield matches, scan_time
