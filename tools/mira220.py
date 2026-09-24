import time
import threading
from collections import deque
from picamera2 import Picamera2
from tools.global_vars import global_state


class CameraStream:
    """Manages Mira220 Picamera2 streaming, frame buffer deque, and controls hardware parameters."""

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
        global_state["camera"]["real_gain"] = 0.0
        global_state["camera"]["fps"] = 0

        self.picam0 = Picamera2(camera_num=0)
        config0 = self.picam0.create_preview_configuration(
            main={"format": "YUV420", "size": (1600, 1400)},
            buffer_count=2,
        )
        self.picam0.configure(config0)

    def set_exposure(self, exposure_time: int):
        """Dynamically update exposure time and auto-adjust frame duration limits for long exposures."""
        self.exposure = int(exposure_time)
        global_state["camera"]["exposure"] = self.exposure

        if self.is_running:
            # Minimum frame duration must be equal to or greater than exposure time + overhead
            min_frame_duration = self.exposure + 1000
            # Allow long exposures up to 20 seconds
            max_frame_duration = max(20_000_000, min_frame_duration)

            self.picam0.set_controls({
                "AeEnable": False,
                "FrameDurationLimits": (min_frame_duration, max_frame_duration),
                "ExposureTime": self.exposure,
            })

    def set_gain(self, gain_value: float):
        """Dynamically update camera analogue gain."""
        self.gain = float(gain_value)
        global_state["camera"]["gain"] = self.gain

        if self.is_running:
            self.picam0.set_controls({
                "AeEnable": False,
                "AnalogueGain": self.gain,
            })

    def _capture_loop(self):
        """Internal capture loop executed in a separate background thread."""
        self.picam0.start()
        time.sleep(0.5)

        # Apply initial exposure and gain parameters
        min_frame_duration = self.exposure + 1000
        max_frame_duration = max(20_000_000, min_frame_duration)

        self.picam0.set_controls({
            "AeEnable": False,
            "FrameDurationLimits": (min_frame_duration, max_frame_duration),
            "ExposureTime": self.exposure,
            "AnalogueGain": self.gain,
        })

        counter = 0
        start_time = time.time()

        try:
            while self.is_running:
                frame0 = self.picam0.capture_array()

                # Crop padding for Mira220 sensor (1600x1400)
                frame0 = frame0[:1400, :1600]
                self.frames.append(frame0)

                # Diagnostic: update real applied gain from frame metadata
                metadata = self.picam0.capture_metadata()
                global_state["camera"]["real_gain"] = metadata.get("AnalogueGain", 0.0)

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
    camera.start()
    pause()