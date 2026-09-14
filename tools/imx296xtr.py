"""
Raspberry Pi + IMX296 (Global Shutter) + picamera2 + pigpio

Fixes low brightness, noise, and flickering:
- Hardware-precise microsecond timing via pigpio Waveforms (DMA).
- Exact exposure pulse triggered synchronously before frame capture.
"""

import time
import cv2
import numpy as np
import pigpio
from picamera2 import Picamera2

# ---- Configuration ----------------------------------------------------
XTR_GPIO_PIN = 11          # BCM numbering: GPIO11 (Physical Pin 23)
FRAME_WIDTH = 1456
FRAME_HEIGHT = 1088
WINDOW_NAME = "IMX296 Stable Exposure"

# Таблиця експозицій для клавіш 1..9 (у мікросекундах)
# 1 -> 5ms, 9 -> 65ms (досить яскраво для кімнати)
EXPOSURE_MAP_US = {
    ord("1"): 5_000,    # 5 ms
    ord("2"): 10_000,   # 10 ms
    ord("3"): 15_000,   # 15 ms
    ord("4"): 120_000,   # 20 ms
    ord("5"): 130_000,   # 30 ms
    ord("6"): 140_000,   # 40 ms
    ord("7"): 500_000,   # 50 ms
    ord("8"): 600_000,   # 60 ms
    ord("9"): 700_000,   # 70 ms
}

# ---- Initialize pigpio --------------------------------------------------
pi = pigpio.pi()
if not pi.connected:
    raise SystemExit("Error: pigpiod daemon is not running! Run 'sudo systemctl start pigpiod' first.")

pi.set_mode(XTR_GPIO_PIN, pigpio.OUTPUT)
pi.write(XTR_GPIO_PIN, 0)


def send_hardware_pulse(width_us: int):
    """Generates an accurate hardware waveform pulse on GPIO11 using pigpio DMA."""
    pi.wave_clear()

    # Формуємо апаратний імпульс: HIGH на width_us мікросекунд, потім LOW
    pulse = [
        pigpio.pulse(1 << XTR_GPIO_PIN, 0, width_us),
        pigpio.pulse(0, 1 << XTR_GPIO_PIN, 100)
    ]

    pi.wave_add_generic(pulse)
    wave_id = pi.wave_create()

    if wave_id >= 0:
        pi.wave_send_once(wave_id)  # Надсилаємо імпульс строго один раз
        while pi.wave_tx_busy():
            time.sleep(0.001)       # Чекаємо завершення імпульсу
        pi.wave_delete(wave_id)


# ---- Camera Setup -------------------------------------------------------
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(
    main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
)
picam2.configure(camera_config)
picam2.start()

# Налаштування сенсора
try:
    picam2.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "AnalogueGain": 8.0,  # Піднімаємо Gain x8 для зниження цифрового шуму в темряві
    })
except Exception as err:
    print(f"Warning setting controls: {err}")


def show_blank_frame():
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(blank, "Press 1..9 for hardware pulse exposure", (30, 220),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(blank, "1: 5ms | 5: 30ms | 9: 70ms", (30, 260),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
    cv2.imshow(WINDOW_NAME, blank)


def capture_with_hardware_pulse(exp_us: int):
    """Send single hardware pulse and read the resulting frame."""
    print(f"Sending pulse: {exp_us / 1000:.1f} ms...")

    # 1. Подаємо один апаратний імпульс
    send_hardware_pulse(exp_us)

    # 2. Невелика пауза на readout сенсора (14.5 мс у IMX296)
    time.sleep(0.02)

    # 3. Захоплюємо експонований кадр
    frame = picam2.capture_array()
    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    avg_brightness = np.mean(frame_bgr)
    info_text = f"Exposure: {exp_us / 1000:.1f} ms | Avg Brightness: {avg_brightness:.1f}"

    cv2.putText(frame_bgr, info_text, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    print(f"Result: {info_text}")
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
                capture_with_hardware_pulse(exp_us)

    finally:
        picam2.stop()
        pi.write(XTR_GPIO_PIN, 0)
        pi.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()