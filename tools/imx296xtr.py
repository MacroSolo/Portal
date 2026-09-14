"""
Raspberry Pi + IMX296 (Global Shutter) + picamera2 + OpenCV + gpiozero.

Fix for libcamera continuous trigger timeout:
- Background thread sends periodic dummy pulses to keep the sensor active.
- Keypress updates the pulse exposure width for the next captured frame.
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

# Глобальні змінні для керування тригером
current_exposure_us = 100  # Фонова довжина імпульсу за замовчуванням (100 мкс)
running = True
new_frame_ready = threading.Event()

def trigger_loop():
    """Background thread continuously driving XTR pin to prevent camera timeout."""
    global current_exposure_us, running
    while running:
        exposure = current_exposure_us
        xtr.on()
        time.sleep(exposure / 1_000_000)
        xtr.off()

        # Сигналізуємо про завершення тригерного імпульсу
        new_frame_ready.set()

        # Інтервал між кадрами у фоновому режимі (~10 FPS = 100 мс)
        time.sleep(0.1)

# ---- Start Background Trigger Thread ------------------------------------
trigger_thread = threading.Thread(target=trigger_loop, daemon=True)
trigger_thread.start()

# ---- Camera setup ---------------------------------------------------------
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(
    main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
)
picam2.configure(camera_config)

# Запускаємо Picamera2 (сенсор вже отримує фонові імпульси від потоку)
picam2.start()

# Вимикаємо авто-експозицію/підсилення
try:
    picam2.set_controls({"AeEnable": False, "AwbEnable": False})
except Exception as e:
    print(f"Warning setting controls: {e}")


def show_blank_frame():
    """Display an all-zero (black) frame."""
    blank = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.imshow(WINDOW_NAME, blank)


def capture_with_exposure(pulse_width_us: int):
    """Set pulse width for the next frame, capture, and display it."""
    global current_exposure_us

    # Встановлюємо бажану експозицію для наступного імпульсу
    current_exposure_us = pulse_width_us

    # Чекаємо, поки фоновий потік згенерує імпульс з новою експозицією
    new_frame_ready.clear()
    new_frame_ready.wait(timeout=1.0)

    # Захоплюємо експонований кадр
    frame = picam2.capture_array()

    # Повертаємо фонову експозицію за замовчуванням
    current_exposure_us = 100

    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    cv2.imshow(WINDOW_NAME, frame_bgr)


def main():
    global running
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
                capture_with_exposure(pulse_width_us)

    finally:
        running = False
        picam2.stop()
        xtr.off()
        xtr.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()