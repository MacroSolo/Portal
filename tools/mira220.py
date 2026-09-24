import time
import threading
from collections import deque
import cv2
from picamera2 import Picamera2
from tools.global_vars import global_state


class CameraStream:
    """Manages Mira220 Picamera2 streaming, frame buffer deque, cropping/rotation, and controls hardware parameters."""

    def __init__(self, default_exposure=1000, default_gain=8.0, buffer_size=100):
        self.exposure = default_exposure
        self.gain = default_gain
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

    def set_exposure(self, exposure_time: int):
        """Dynamically update exposure time (in microseconds) and auto-adjust frame duration limits."""
        self.exposure = exposure_time
        global_state["camera"]["exposure"] = self.exposure

        if self.is_running:
            # Minimum frame duration must be equal to or greater than exposure time + overhead
            min_frame_duration = exposure_time + 1000
            # Set max frame duration to allow long exposures if needed
            max_frame_duration = max(20_000_000, min_frame_duration)

            self.picam0.set_controls({
                "FrameDurationLimits": (min_frame_duration, max_frame_duration),
                "ExposureTime": self.exposure
            })

    def set_gain(self, gain_value: float):
        """Dynamically update camera analogue gain."""
        self.gain = gain_value
        global_state["camera"]["gain"] = self.gain

        if self.is_running:
            self.picam0.set_controls({"AnalogueGain": self.gain})

    def _capture_loop(self):
        """Internal capture loop executed in a separate background thread."""
        self.picam0.start()
        time.sleep(0.5)

        # Disable auto exposure and set manual hardware parameters
        self.picam0.set_controls({
            "AeEnable": False,
            "ExposureTime": self.exposure,
            "AnalogueGain": self.gain,
        })

        counter = 0
        start_time = time.time()

        try:
            while self.is_running:
                # 1. Capture raw array from sensor
                frame0 = self.picam0.capture_array()

                # 2. Crop to 1600x1400 area
                frame0 = frame0[:1400, :1600]

                # 3. Rotate image 180 degrees
                frame0 = cv2.rotate(frame0, cv2.ROTATE_180)

                # Push processed frame into the deque buffer
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