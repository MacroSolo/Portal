import time
import threading
from collections import deque
import cv2
from picamera2 import Picamera2
from tools.global_vars import global_state


class CameraStream:
    """Manages Mira220 Picamera2 streaming, frame buffer deque, cropping/rotation, and controls hardware parameters."""

    def __init__(self, default_exposure=1000, default_gain=8.0, buffer_size=100):
        self.exposure = int(default_exposure)
        self.gain = float(default_gain)
        self.frames = deque(maxlen=buffer_size)
        self.is_running = False
        self._thread = None

        if "camera" not in global_state or not isinstance(global_state["camera"], dict):
            global_state["camera"] = {}

        global_state["camera"]["exposure"] = self.exposure
        global_state["camera"]["gain"] = self.gain
        global_state["camera"]["fps"] = 0

        self.picam0 = Picamera2(camera_num=0)
        config0 = self.picam0.create_preview_configuration(
            main={"format": "YUV420", "size": (1600, 1400)},
            buffer_count=2,
        )
        self.picam0.configure(config0)

    def _apply_controls(self):
        """Apply manual exposure and gain parameters to the hardware controls."""
        min_frame_duration = self.exposure + 1000
        max_frame_duration = max(20_000_000, min_frame_duration)

        controls = {
            "AeEnable": False,
            "AwbEnable": False,
            "FrameDurationLimits": (min_frame_duration, max_frame_duration),
            "ExposureTime": self.exposure,
            "AnalogueGain": float(self.gain),
        }

        self.picam0.set_controls(controls)

    def set_exposure(self, exposure_time: int):
        """Dynamically update exposure time (in microseconds)."""
        self.exposure = int(exposure_time)
        global_state["camera"]["exposure"] = self.exposure

        if self.is_running:
            self._apply_controls()

    def set_gain(self, gain_value: float):
        """Dynamically update camera analogue gain."""
        self.gain = float(gain_value)
        global_state["camera"]["gain"] = self.gain

        if self.is_running:
            self._apply_controls()

    def _capture_loop(self):
        """Internal capture loop executed in a separate background thread."""
        self.picam0.start()
        time.sleep(0.5)

        # Apply initial manual settings
        self._apply_controls()

        counter = 0
        start_time = time.time()

        try:
            while self.is_running:
                # Capture raw array from sensor
                frame0 = self.picam0.capture_array()

                # Crop padding if necessary and update frame deque
                frame0 = frame0[:1400, :1600]
                self.frames.append(frame0)

                # FPS Calculation
                counter += 1
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    global_state["camera"]["fps"] = int(counter / elapsed)
                    counter = 0
                    start_time = time.time()
        finally:
            self.picam0.stop()

    def start(self):
        """Start hardware stream asynchronously in a background daemon thread."""
        if not self.is_running:
            self.is_running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Safely stop hardware stream background thread."""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


# --- Example Usage ---
if __name__ == "__main__":
    from signal import pause

    camera = CameraStream(default_exposure=1000, default_gain=8.0, buffer_size=100)

    # Non-blocking async start
    camera.start()

    # Keep main script process alive
    pause()