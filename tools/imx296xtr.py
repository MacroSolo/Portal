"""
Raspberry Pi + IMX296 (Global Shutter) + picamera2 + OpenCV + gpiozero.

Fix for Picamera2.start() TypeError and startup timeout:
- Standard picam2.start() call without invalid arguments.
- A background pulse is sent during start() to let libcamera initialize without timing out.
"""

import threading
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


def pulse_xtr(width_us: int, delay_s: float = 0.002):
    """Drive XTR pin high for width_us microseconds."""
    if delay_s > 0:
        time.sleep(delay_s)
    xtr.on()
    time.sleep(width_us / 1_000_000)
    xtr.off()


def show_blank_frame():
    """Display an all-zero (black) frame."""
    blank = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.imshow(WINDOW_NAME, blank)


# ---- Camera setup ---------------------------------------------------------
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(
    main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
)
picam2.configure(camera_config)

# Запускаємо перший імпульс в окремому потоці, щоб picam2.start() не падав за таймаутом
init_trigger = threading.Thread(target=pulse_xtr, args=(2000, 0.1))
init_trigger.start()

# Стандартний запуск без зайвих аргументів
picam2.start()
init_trigger.join()

# Вимикаємо авто-експозицію/підсилення після запуску
try:
    picam2.set_controls({"AeEnable": False, "AwbEnable": False})
except Exception as e:
    print(f"Warning setting controls: {e}")


def trigger_and_capture(pulse_width_us: int):
    """Send pulse asynchronously and grab the triggered frame."""
    trigger_thread = threading.Thread(target=pulse_xtr, args=(pulse_width_us, 0.002))
    trigger_thread.start()

    # Запитуємо кадр у камери
    frame = picam2.capture_array()
    trigger_thread.join()

    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    cv2.imshow(WINDOW_NAME, frame_bgr)


def main():
    cv2.namedWindow(WINDOW_NAME)
    show_blank_frame()

    try:
        while True:
            key = cv2.waitKey(0) & 0xFF
            print(f"Key pressed: {key} (char: {chr(key) if 32 <= key <= 126 else 'non-printable'})")

            if key in (27, ord("q")):  # ESC or 'q'
                break

            if ord("1") <= key <= ord("9"):
                digit = key - ord("0")
                pulse_width_us = digit * 1000  # 1000..9000 us
                trigger_and_capture(pulse_width_us)

    finally:
        picam2.stop()
        xtr.off()
        xtr.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()