import time
import threading
from collections import deque

import numpy as np
from picamera2 import Picamera2

from tools.global_vars import global_state


class TriggeredCameraStream:
    """
    Sony IMX296 Global Shutter camera stream using Picamera2 (External Trigger Mode).

    Sensor resolution:
        1440 x 1080

    Output resolution:
        800 x 1280

    Camera ROI:
        800 x 1080, centered horizontally
    """

    SENSOR_WIDTH = 1440
    SENSOR_HEIGHT = 1080

    OUTPUT_WIDTH = 800
    OUTPUT_HEIGHT = 1280

    ROI_WIDTH = 800
    ROI_HEIGHT = 1080

    BLACK_BAR_HEIGHT = (OUTPUT_HEIGHT - ROI_HEIGHT) // 2

    def __init__(
        self,
        default_exposure=4096,
        default_gain=1.0,
        expected_fps=60,
        buffer_size=100,
        size=None,
        format="BGR888",
    ):
        self.exposure = int(default_exposure)
        self.gain = float(default_gain)

        self.target_fps = expected_fps
        self.buffer_size = buffer_size

        self.size = size or (
            self.ROI_WIDTH,
            self.ROI_HEIGHT,
        )

        self.format = format
        self.frames = deque(maxlen=buffer_size)

        self.is_running = False
        self._thread = None

        # Frame duration estimation for internal safeguards (in us)
        self.frame_duration = int(1_000_000 / self.target_fps)

        if self.exposure >= self.frame_duration:
            self.exposure = self.frame_duration - 100

        # ------------------------------------------------------------------
        # Camera ROI Calculation
        # ------------------------------------------------------------------

        self.roi_x = (self.SENSOR_WIDTH - self.ROI_WIDTH) // 2
        self.roi_y = (self.SENSOR_HEIGHT - self.ROI_HEIGHT) // 2
        self.roi = (self.roi_x, self.roi_y, self.ROI_WIDTH, self.ROI_HEIGHT)

        # ------------------------------------------------------------------
        # Global state registry
        # ------------------------------------------------------------------

        if "camera" not in global_state or not isinstance(global_state["camera"], dict):
            global_state["camera"] = {}

        global_state["camera"]["exposure"] = self.exposure
        global_state["camera"]["gain"] = self.gain
        global_state["camera"]["fps"] = 0
        global_state["camera"]["target_fps"] = self.target_fps
        global_state["camera"]["resolution"] = (self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT)
        global_state["camera"]["camera_resolution"] = self.size
        global_state["camera"]["format"] = self.format
        global_state["camera"]["global_shutter"] = True
        global_state["camera"]["roi"] = self.roi
        global_state["camera"]["external_trigger"] = True

        # ------------------------------------------------------------------
        # Camera Initialization
        # КЛЮЧОВЕ ВИПРАВЛЕННЯ: preview=None повністю вимикає preview engine
        # ------------------------------------------------------------------

        self.picam0 = Picamera2(camera_num=0, preview=None)

        config = self.picam0.create_video_configuration(
            main={
                "format": self.format,
                "size": self.size,
            },
            buffer_count=6,
        )

        self.picam0.configure(config)

    # ----------------------------------------------------------------------
    # Context Manager Protocol
    # ----------------------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ----------------------------------------------------------------------
    # Dynamic Controls
    # ----------------------------------------------------------------------

    def set_exposure(self, exposure_time: int):
        """Set exposure time in microseconds (us)."""
        exposure_time = int(exposure_time)
        if exposure_time < 1:
            exposure_time = 1

        self.exposure = exposure_time
        global_state["camera"]["exposure"] = self.exposure

        if self.is_running and self.picam0:
            self.picam0.set_controls({"ExposureTime": self.exposure})

        print(f"[Triggered Camera] Exposure: {self.exposure} us ({self.exposure / 1000:.3f} ms)")

    def set_gain(self, gain_value: float):
        """Change analogue gain."""
        self.gain = float(gain_value)
        global_state["camera"]["gain"] = self.gain

        if self.is_running and self.picam0:
            self.picam0.set_controls({"AnalogueGain": self.gain})

    def set_fps(self, fps: float):
        """Update target FPS tracking (Hardware trigger governs physical rate)."""
        if fps <= 0:
            raise ValueError("FPS must be greater than zero")

        self.target_fps = float(fps)
        self.frame_duration = int(1_000_000 / self.target_fps)
        global_state["camera"]["target_fps"] = self.target_fps

    # ----------------------------------------------------------------------
    # Capture thread engine
    # ----------------------------------------------------------------------

    def _capture_loop(self):
        """Background loop awaiting physical GPIO trigger pulses on IMX296."""
        counter = 0
        start_time = time.monotonic()

        try:
            controls = {
                "AeEnable": False,
                "AwbEnable": False,
                "ScalerCrop": self.roi,
                "ExposureTime": self.exposure,
                "AnalogueGain": self.gain,
            }

            # Передаємо show_preview=False
            self.picam0.start(show_preview=False)
            self.picam0.set_controls(controls)

            time.sleep(0.1)

            counter = 0
            start_time = time.monotonic()

            while self.is_running:
                # Очікує фізичного імпульсу на піні TRIG камери IMX296
                frame = self.picam0.capture_array("main")

                if frame is None:
                    continue

                display_frame = np.zeros(
                    (
                        self.OUTPUT_HEIGHT,
                        self.OUTPUT_WIDTH,
                        frame.shape[2],
                    ),
                    dtype=frame.dtype,
                )

                display_frame[
                    self.BLACK_BAR_HEIGHT : self.BLACK_BAR_HEIGHT + self.ROI_HEIGHT,
                    :,
                ] = frame

                self.frames.append(display_frame)

                counter += 1
                now = time.monotonic()
                elapsed = now - start_time

                if elapsed >= 1.0:
                    measured_fps = counter / elapsed
                    global_state["camera"]["fps"] = int(measured_fps)
                    counter = 0
                    start_time = now

        except Exception as e:
            global_state["camera"]["error"] = str(e)
            print(f"[Triggered Camera] Stream Error: {e}")

        finally:
            try:
                if self.picam0:
                    self.picam0.stop()
            except Exception:
                pass
            global_state["camera"]["fps"] = 0

    # ----------------------------------------------------------------------
    # Lifecycle Management
    # ----------------------------------------------------------------------

    def start(self):
        """Start async listener thread."""
        if self.is_running:
            return

        self.is_running = True
        global_state["camera"]["error"] = None

        self._thread = threading.Thread(
            target=self._capture_loop,
            name="IMX296-TriggeredCapture",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        """Signal thread shutdown and join."""
        self.is_running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._thread = None

    def close(self):
        """Explicitly release libcamera hardware handlers."""
        self.stop()
        if hasattr(self, "picam0") and self.picam0 is not None:
            try:
                self.picam0.close()
            except Exception:
                pass
            finally:
                self.picam0 = None

    # ----------------------------------------------------------------------
    # Consumer Interface
    # ----------------------------------------------------------------------

    def get_latest_frame(self):
        if not self.frames:
            return None
        return self.frames[-1]

    def get_frame(self):
        if not self.frames:
            return None
        return self.frames.popleft()

    def get_buffer_size(self):
        return len(self.frames)


# --------------------------------------------------------------------------
# Usage Example
# --------------------------------------------------------------------------

if __name__ == "__main__":
    from signal import pause

    camera = TriggeredCameraStream(
        default_exposure=4096,
        default_gain=8.0,
        expected_fps=60,
        buffer_size=100,
        size=(800, 1080),
        format="BGR888",
    )

    try:
        camera.start()
        print("[System] Waiting for HW triggers on IMX296...")
        pause()
    except KeyboardInterrupt:
        print("\n[System] Exiting cleanly...")
    finally:
        camera.close()