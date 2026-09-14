"""
Raspberry Pi + IMX296 Global Shutter Camera (XTR Trigger Control)
Control exposure manually via GPIO11 pulse width using keys 1..9.
"""

import threading
import time

import cv2
import numpy as np
from gpiozero import DigitalOutputDevice
from picamera2 import Picamera2

# ---- Configuration ----------------------------------------------------
XTR_GPIO_PIN = 11          # BCM numbering: GPIO11 (Physical Pin 23)
FRAME_WIDTH = 1456         # Нативна роздільна здатність IMX296
FRAME_HEIGHT = 1088
WINDOW_NAME = "IMX296 Exposure Test"

# Таблиця експозицій для клавіш 1..9 (у мікросекундах)
# 1 -> 2ms (дуже темне), 9 -> 50ms (дуже яскраве)
EXPOSURE_MAP_US = {
    ord("1"): 2_000,    # 2 ms
    ord("2"): 8_000,    # 8 ms
    ord("3"): 14_000,   # 14 ms
    ord("4"): 20_000,   # 20 ms
    ord("5"): 26_000,   # 26 ms
    ord("6"): 32_000,   # 32 ms
    ord("7"): 38_000,   # 38 ms
    ord("8"): 44_000,   # 44 ms
    ord("9"): 50_000,   # 50 ms
}

# ---- GPIO Setup ---------------------------------------------------------
xtr = DigitalOutputDevice(XTR_GPIO_PIN, initial_value=False)

# Глобальні змінні контролю фонового тригера
current_exposure_us = 10_000  # Фонова експозиція за замовчуванням (10 мс)
running = True

def pulse_trigger_loop():
    """Continuous background trigger loop (~10 Hz) to keep IMX296 active."""
    global current_exposure_us, running
    while running:
        pulse_len = current_exposure_us

        # Наростаючий фронт — початок експозиції
        xtr.on()
        time.sleep(pulse_len / 1_000_000)
        # Спадаючий фронт — кінець експозиції та запуск Readout
        xtr.off()

        # Час на зчитування кадру (Readout Time ~14.5ms) + пауза між кадрами
        time.sleep(0.08)

# ---- Start Trigger Thread -----------------------------------------------
trigger_thread = threading.Thread(target=pulse_trigger_loop, daemon=True)
trigger_thread.start()

# ---- Camera Setup -------------------------------------------------------
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(
    main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
)
picam2.configure(camera_config)
picam2.start()

# Фіксуємо підсилення для чистоти тесту експозиції
try:
    picam2.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "AnalogueGain": 4.0,  # Фіксоване підсилення x4
    })
except Exception as err:
    print(f"Warning setting controls: {err}")


def show_blank_frame():
    """Display empty frame with key bindings guidance."""
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(blank, "Press 1..9 to capture with exposure pulse", (30, 220),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(blank, "1: 2ms | 5: 26ms | 9: 50ms", (30, 260),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
    cv2.imshow(WINDOW_NAME, blank)


def capture_with_exposure(exp_us: int):
    """Set exposure pulse, wait for camera pipeline to receive it, show frame."""
    global current_exposure_us
    current_exposure_us = exp_us

    # Чекаємо 100 мс, щоб фоновий потік встиг згенерувати імпульс із оновленою довжиною
    time.sleep(0.10)

    frame = picam2.capture_array()
    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # Розрахунок середньої яскравості та вивід інформації на екран
    avg_brightness = np.mean(frame_bgr)
    info_text = f"Exposure: {exp_us / 1000:.1f} ms | Avg Brightness: {avg_brightness:.1f}"

    cv2.putText(frame_bgr, info_text, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    print(f"Captured: {info_text}")
    cv2.imshow(WINDOW_NAME, frame_bgr)


def main():
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 960, 720)
    show_blank_frame()

    try:
        while True:
            key = cv2.waitKey(0) & 0xFF

            if key in (27, ord("q")):  # ESC or 'q'
                break

            if key in EXPOSURE_MAP_US:
                exp_us = EXPOSURE_MAP_US[key]
                capture_with_exposure(exp_us)

    finally:
        global running
        running = False
        picam2.stop()
        xtr.off()
        xtr.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()