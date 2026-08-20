import time
from collections import deque
from picamera2 import Picamera2
from tools.global_vars import global_state


class CameraStream:
    """Manages Picamera2 streaming, frame buffer deque, and controls hardware parameters."""

    def __init__(self, default_exposure=4096, default_gain=8, buffer_size=100):
        self.exposure = default_exposure
        self.gain = default_gain
        self.frames = deque(maxlen=buffer_size)
        self.is_running = False

        # Ensure global state dictionary structure exists
        if "camera" not in global_state or not isinstance(global_state["camera"], dict):
            global_state["camera"] = {}

        # Set default values in global state
        global_state["camera"]["exposure"] = self.exposure
        global_state["camera"]["gain"] = self.gain
        global_state["camera"]["fps"] = 0

        # Initialize Picamera2
        self.picam0 = Picamera2(camera_num=0)
        config0 = self.picam0.create_preview_configuration(
            main={"format": "BGR888", "size": (800, 1280)},
            buffer_count=2,
        )
        self.picam0.configure(config0)

    def set_exposure(self, exposure_time: int):
        """Dynamically update camera exposure time in microseconds."""
        self.exposure = exposure_time
        global_state["camera"]["exposure"] = self.exposure

        if self.is_running:
            self.picam0.set_controls({"ExposureTime": self.exposure})

    def set_gain(self, gain_value: float):
        """Dynamically update camera analogue gain."""
        self.gain = gain_value
        global_state["camera"]["gain"] = self.gain

        if self.is_running:
            self.picam0.set_controls({"AnalogueGain": self.gain})

    def start_loop(self):
        """Start hardware stream and run continuous frame capture loop."""
        self.picam0.start()
        time.sleep(0.5)

        # Apply initial hardware settings
        self.picam0.set_controls({
            "AeEnable": False,
            "AwbEnable": False,
            "ExposureTime": self.exposure,
            "AnalogueGain": self.gain,
            "ColourGains": (1.5, 1.5)
        })

        self.is_running = True
        counter = 0
        start_time = time.time()

        try:
            while self.is_running:
                frame0 = self.picam0.capture_array()
                self.frames.append(frame0)

                # Update real-time FPS calculation every second
                counter += 1
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    global_state["camera"]["fps"] = int(counter / elapsed)
                    counter = 0
                    start_time = time.time()

        finally:
            self.stop()

    def stop(self):
        """Safely stop hardware stream."""
        self.is_running = False
        self.picam0.stop()


# --- Example Usage ---
if __name__ == "__main__":
    camera = CameraStream()

    # Call these setter methods directly whenever your encoder turns:
    # camera.set_exposure(10000)
    # camera.set_gain(4.0)

    # Start capture (blocking loop)
    # camera.start_loop()