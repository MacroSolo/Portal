"""
Raspberry Pi + Global Shutter Camera (picamera2) + OpenCV + gpiozero.

Logic:
- Show a black (zero) frame and wait for a keypress.
- On keys '1'..'9', send a pulse of (digit * 1000) microseconds on GPIO11 (XTR pin),
  then capture and show the resulting frame.
- Press 'q' or ESC to quit.
"""

import time

import cv2
import numpy as np
from gpiozero import DigitalOutputDevice
from picamera2 import Picamera2

# ---- Configuration ----------------------------------------------------
XTR_GPIO_PIN = 11          # BCM numbering: GPIO11
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
WINDOW_NAME = "Frame"

# ---- GPIO setup ---------------------------------------------------------
xtr = DigitalOutputDevice(XTR_GPIO_PIN, initial_value=False)

# ---- Camera setup ---------------------------------------------------------
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(
    main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
)
picam2.configure(camera_config)
picam2.start()
# Let the sensor/AE settle before the first real capture
time.sleep(1.0)


def show_blank_frame():
    """Display an all-zero (black) frame."""
    blank = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.imshow(WINDOW_NAME, blank)


def pulse_xtr(width_us: int):
    """Drive XTR pin high for width_us microseconds, then low.

    Note: time.sleep() on a non-realtime OS is only accurate to roughly
    tens of microseconds at best. For tighter/more repeatable timing,
    consider pigpio's hardware-timed pulses instead of gpiozero.
    """
    xtr.on()
    time.sleep(width_us / 1_000_000)
    xtr.off()


def capture_and_show():
    """Grab a frame from the camera and display it."""
    frame = picam2.capture_array()  # RGB888
    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    cv2.imshow(WINDOW_NAME, frame_bgr)


def main():
    cv2.namedWindow(WINDOW_NAME)
    show_blank_frame()

    try:
        while True:
            key = cv2.waitKey(1) & 0xFF
            print(f"Key pressed: {key} (char: {chr(key) if 32 <= key <= 126 else 'non-printable'})")

            if key in (27, ord("q")):  # ESC or 'q'
                break

            if ord("1") <= key <= ord("9"):
                digit = key - ord("0")
                pulse_width_us = digit * 1000  # 1000..9000 us
                pulse_xtr(pulse_width_us)
                capture_and_show()

    finally:
        picam2.stop()
        xtr.off()
        xtr.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()