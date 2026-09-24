import time
import threading
from collections import deque
from picamera2 import Picamera2
from tools.global_vars import global_state

FRAME_MARGIN_US = 1000   # headroom between exposure and frame duration
EXPOSURE_SETTLE_FRAMES = 3  # frames to wait after changing frame duration


class CameraStream:
    """Manages Mira220 Picamera2 streaming with correct control ordering."""

    def __init__(self, default_exposure=1000, default_gain=8.0, buffer_size=100):
        self.exposure = int(default_exposure)
        self.gain = float(default_gain)
        self.frames = deque(maxlen=buffer_size)
        self.is_running = False
        self._thread = None

        self._lock = threading.Lock()
        self._pending_exposure = None
        self._pending_gain = None
        self._settle_left = 0
        self._exposure_to_apply = None

        if not isinstance(global_state.get("camera"), dict):
            global_state["camera"] = {}
        global_state["camera"].update(
            exposure=self.exposure, gain=self.gain,
            real_gain=0.0, real_exposure=0, fps=0,
        )

        self.picam0 = Picamera2(camera_num=0)
        config0 = self.picam0.create_preview_configuration(
            main={"format": "YUV420", "size": (1600, 1400)},
            buffer_count=4,
            controls={"AeEnable": False},
        )
        self.picam0.configure(config0)

        limits = self.picam0.camera_controls
        self._exp_min, self._exp_max = limits["ExposureTime"][:2]
        self._gain_min, self._gain_max = limits["AnalogueGain"][:2]
        self._min_frame_us = limits["FrameDurationLimits"][0]

    def _frame_duration(self, exposure):
        return int(max(self._min_frame_us, exposure + FRAME_MARGIN_US))

    def set_exposure(self, exposure_time: int):
        """Request exposure change (us); applied by the capture loop."""
        exposure = int(min(max(exposure_time, self._exp_min), self._exp_max))
        self.exposure = exposure
        global_state["camera"]["exposure"] = exposure
        with self._lock:
            self._pending_exposure = exposure

    def set_gain(self, gain_value: float):
        """Request analogue gain change; applied by the capture loop."""
        gain = float(min(max(gain_value, self._gain_min), self._gain_max))
        self.gain = gain
        global_state["camera"]["gain"] = gain
        with self._lock:
            self._pending_gain = gain

    def _apply_pending_controls(self):
        with self._lock:
            exposure, self._pending_exposure = self._pending_exposure, None
            gain, self._pending_gain = self._pending_gain, None

        if gain is not None:
            self.picam0.set_controls({"AnalogueGain": gain})

        if exposure is not None:
            # Step 1: change frame duration first, exposure is clamped by it
            duration = self._frame_duration(exposure)
            self.picam0.set_controls({"FrameDurationLimits": (duration, duration)})
            self._exposure_to_apply = exposure
            self._settle_left = EXPOSURE_SETTLE_FRAMES

        # Step 2: apply exposure after the new frame duration took effect
        if self._exposure_to_apply is not None:
            if self._settle_left <= 0:
                self.picam0.set_controls({"ExposureTime": self._exposure_to_apply})
                self._exposure_to_apply = None
            else:
                self._settle_left -= 1

    def _capture_loop(self):
        duration = self._frame_duration(self.exposure)
        self.picam0.set_controls({
            "AeEnable": False,
            "FrameDurationLimits": (duration, duration),
            "ExposureTime": self.exposure,
            "AnalogueGain": self.gain,
        })
        self.picam0.start()

        counter = 0
        start_time = time.monotonic()

        try:
            while self.is_running:
                self._apply_pending_controls()

                # Single request: frame and metadata come from the same capture
                with self.picam0.captured_request() as request:
                    # Y plane only; copy() releases the DMA buffer reference
                    frame = request.make_array("main")[:1400, :1600].copy()
                    md = request.get_metadata()

                self.frames.append(frame)
                global_state["camera"]["real_gain"] = md.get("AnalogueGain", 0.0)
                global_state["camera"]["real_exposure"] = md.get("ExposureTime", 0)

                counter += 1
                elapsed = time.monotonic() - start_time
                if elapsed >= 1.0:
                    global_state["camera"]["fps"] = int(counter / elapsed)
                    counter = 0
                    start_time = time.monotonic()
        finally:
            self.picam0.stop()

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)