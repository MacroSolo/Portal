"""
Raspberry Pi + Global Shutter Camera (picamera2) + OpenCV + gpiozero.

Fix: 'start_stream=False' prevents the camera driver from timing out
before any key is pressed.
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

# ---- Camera setup ---------------------------------------------------------
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(
    main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
)
picam2.configure(camera_config)

# Вимикаємо AE/AWB, щоб експозицією повністю керував тригер
picam2.set_controls({"AeEnable": False, "AwbEnable": False})

# КЛЮЧОВЕ ВИПРАВЛЕННЯ: start_stream=False запобігає таймауту до першого кадру
picam2.start(start_stream=False)


def show_blank_frame():
    """Display an all-zero (black) frame."""
    blank = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.imshow(WINDOW_NAME, blank)


def pulse_xtr(width_us: int, delay_s: float = 0.002):
    """Drive XTR pin high for width_us microseconds after a tiny delay."""
    time.sleep(delay_s)
    xtr.on()
    time.sleep(width_us / 1_000_000)
    xtr.off()


def trigger_and_capture(pulse_width_us: int):
    """Send pulse asynchronously and grab the triggered frame."""
    # Запускаємо генерацію імпульсу паралельно
    trigger_thread = threading.Thread(target=pulse_xtr, args=(pulse_width_us,))
    trigger_thread.start()

    # Запитуємо кадр (сенсор віддасть його тільки після імпульсу з потоку)
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