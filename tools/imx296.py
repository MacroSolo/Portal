import time
import threading
from collections import deque

import numpy as np
from picamera2 import Picamera2

from tools.global_vars import global_state


class CameraStream:
    """
    Sony IMX296 Global Shutter camera stream using Picamera2.

    Sensor resolution:
        1440 x 1080

    Output resolution:
        800 x 1280

    Camera ROI:
        800 x 1080, centered horizontally

    Output frame:
        800 x 1080 camera image
        + 100 px black bar at top
        + 100 px black bar at bottom
    """

    SENSOR_WIDTH = 1440
    SENSOR_HEIGHT = 1080

    OUTPUT_WIDTH = 800
    OUTPUT_HEIGHT = 1280

    ROI_WIDTH = 800
    ROI_HEIGHT = 1080

    BLACK_BAR_HEIGHT = (
        OUTPUT_HEIGHT - ROI_HEIGHT
    ) // 2

    def __init__(
        self,
        default_exposure=4096,
        default_gain=1.0,
        fps=60,
        buffer_size=100,
        size=None,
        format="BGR888",
    ):
        self.exposure = int(default_exposure)
        self.gain = float(default_gain)

        self.target_fps = fps
        self.buffer_size = buffer_size

        # Camera output is exactly the sensor ROI:
        # 800 x 1080
        self.size = size or (
            self.ROI_WIDTH,
            self.ROI_HEIGHT,
        )

        self.format = format

        self.frames = deque(maxlen=buffer_size)

        self.is_running = False
        self._thread = None

        # Frame duration in microseconds
        self.frame_duration = int(
            1_000_000 / self.target_fps
        )

        # Make sure exposure does not exceed one frame.
        if self.exposure >= self.frame_duration:
            self.exposure = self.frame_duration - 100

        # ------------------------------------------------------------------
        # Camera ROI
        # ------------------------------------------------------------------

        self.roi_x = (
            self.SENSOR_WIDTH - self.ROI_WIDTH
        ) // 2

        self.roi_y = (
            self.SENSOR_HEIGHT - self.ROI_HEIGHT
        ) // 2

        self.roi = (
            self.roi_x,
            self.roi_y,
            self.ROI_WIDTH,
            self.ROI_HEIGHT,
        )

        # ------------------------------------------------------------------
        # Global state
        # ------------------------------------------------------------------

        if (
            "camera" not in global_state
            or not isinstance(global_state["camera"], dict)
        ):
            global_state["camera"] = {}

        global_state["camera"]["exposure"] = self.exposure
        global_state["camera"]["gain"] = self.gain
        global_state["camera"]["fps"] = 0
        global_state["camera"]["target_fps"] = self.target_fps
        global_state["camera"]["resolution"] = (
            self.OUTPUT_WIDTH,
            self.OUTPUT_HEIGHT,
        )
        global_state["camera"]["camera_resolution"] = self.size
        global_state["camera"]["format"] = self.format
        global_state["camera"]["global_shutter"] = True
        global_state["camera"]["roi"] = self.roi

        # ------------------------------------------------------------------
        # Camera
        # ------------------------------------------------------------------

        self.picam0 = Picamera2(camera_num=0)

        config = self.picam0.create_preview_configuration(
            main={
                "format": self.format,
                "size": self.size,
            },
            buffer_count=2,
        )

        self.picam0.configure(config)

    # ----------------------------------------------------------------------
    # Camera controls
    # ----------------------------------------------------------------------

    def set_exposure(self, exposure_time: int):
        exposure_time = int(exposure_time)

        if exposure_time < 1:
            exposure_time = 1

        self.exposure = exposure_time

        target_frame_duration = int(
            1_000_000 / self.target_fps
        )

        self.frame_duration = max(
            target_frame_duration,
            exposure_time + 1000
        )

        global_state["camera"]["exposure"] = self.exposure

        if self.is_running:
            self.picam0.set_controls({
                "FrameDurationLimits": (
                    self.frame_duration,
                    self.frame_duration,
                ),
                "ExposureTime": self.exposure,
            })

        actual_fps_limit = (
            1_000_000 / self.frame_duration
        )

        global_state["camera"]["fps_limit"] = actual_fps_limit

        print(
            f"[Camera] Exposure: {self.exposure} us "
            f"({self.exposure / 1000:.3f} ms), "
            f"FrameDuration: {self.frame_duration} us, "
            f"FPS limit: {actual_fps_limit:.2f}"
        )

    def set_gain(self, gain_value: float):
        """
        Change analogue gain.
        """

        self.gain = float(gain_value)

        global_state["camera"]["gain"] = self.gain

        if self.is_running:
            self.picam0.set_controls({
                "AnalogueGain": self.gain,
            })

    def set_fps(self, fps: float):
        """
        Change target FPS.

        Example:
            set_fps(60)
            set_fps(30)
        """

        if fps <= 0:
            raise ValueError(
                "FPS must be greater than zero"
            )

        self.target_fps = float(fps)

        self.frame_duration = int(
            1_000_000 / self.target_fps
        )

        # Make sure exposure fits into the new frame period.
        if self.exposure >= self.frame_duration:
            self.exposure = (
                self.frame_duration - 100
            )

        global_state["camera"]["fps"] = 0
        global_state["camera"]["target_fps"] = (
            self.target_fps
        )
        global_state["camera"]["exposure"] = (
            self.exposure
        )

        if self.is_running:
            self.picam0.set_controls({
                "FrameDurationLimits": (
                    self.frame_duration,
                    self.frame_duration,
                ),
                "ExposureTime": self.exposure,
            })

    # ----------------------------------------------------------------------
    # Capture loop
    # ----------------------------------------------------------------------

    def _capture_loop(self):
        """
        Background camera capture thread.

        Camera frame:
            800 x 1080

        Final frame:
            800 x 1280
        """

        counter = 0
        start_time = time.monotonic()

        try:
            self.picam0.start()

            # Give libcamera/sensor time to start.
            time.sleep(0.2)

            # Manual exposure/gain + central ROI.
            self.picam0.set_controls({
                "AeEnable": False,
                "AwbEnable": False,

                "ScalerCrop": self.roi,

                "FrameDurationLimits": (
                    self.frame_duration,
                    self.frame_duration,
                ),

                "ExposureTime": self.exposure,
                "AnalogueGain": self.gain,
            })

            # Reset FPS measurement.
            counter = 0
            start_time = time.monotonic()

            while self.is_running:

                frame = self.picam0.capture_array()

                # ----------------------------------------------------------
                # Create 800 x 1280 output frame.
                #
                # Camera image:
                #   800 x 1080
                #
                # Black bars:
                #   100 px top
                #   100 px bottom
                # ----------------------------------------------------------

                display_frame = np.zeros(
                    (
                        self.OUTPUT_HEIGHT,
                        self.OUTPUT_WIDTH,
                        frame.shape[2],
                    ),
                    dtype=frame.dtype,
                )

                display_frame[
                    self.BLACK_BAR_HEIGHT:
                    self.BLACK_BAR_HEIGHT + self.ROI_HEIGHT,
                    :
                ] = frame

                self.frames.append(display_frame)

                counter += 1

                now = time.monotonic()
                elapsed = now - start_time

                if elapsed >= 1.0:
                    measured_fps = (
                        counter / elapsed
                    )

                    global_state["camera"]["fps"] = int(
                        measured_fps
                    )

                    counter = 0
                    start_time = now

        except Exception as e:
            global_state["camera"]["error"] = str(e)
            print(
                f"CameraStream error: {e}"
            )

        finally:
            try:
                self.picam0.stop()
            except Exception:
                pass

            global_state["camera"]["fps"] = 0

    # ----------------------------------------------------------------------
    # Start / Stop
    # ----------------------------------------------------------------------

    def start(self):
        """
        Start camera streaming asynchronously.
        """

        if self.is_running:
            return

        self.is_running = True

        global_state["camera"]["error"] = None

        self._thread = threading.Thread(
            target=self._capture_loop,
            name="IMX296-Capture",
            daemon=True,
        )

        self._thread.start()

    def stop(self):
        """
        Stop camera streaming.
        """

        self.is_running = False

        if (
            self._thread
            and self._thread.is_alive()
        ):
            self._thread.join(timeout=2.0)

        self._thread = None

    # ----------------------------------------------------------------------
    # Frame access
    # ----------------------------------------------------------------------

    def get_latest_frame(self):
        """
        Return the newest frame.

        Returns:
            numpy.ndarray or None

        Frame size:
            800 x 1280
        """

        if not self.frames:
            return None

        return self.frames[-1]

    def get_frame(self):
        """
        Return and remove the oldest buffered frame.
        """

        if not self.frames:
            return None

        return self.frames.popleft()

    def get_buffer_size(self):
        """
        Return number of currently buffered frames.
        """

        return len(self.frames)


# --------------------------------------------------------------------------
# Example
# --------------------------------------------------------------------------

if __name__ == "__main__":

    from signal import pause

    camera = CameraStream(
        default_exposure=4096,
        default_gain=8.0,
        fps=60,
        buffer_size=100,
        size=(800, 1080),
        format="BGR888",
    )

    camera.start()

    try:
        pause()

    except KeyboardInterrupt:
        pass

    finally:
        camera.stop()