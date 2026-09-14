"""
Raspberry Pi + IMX296 (Global Shutter) + picamera2 + gpiozero (PWM)

Continuous PWM Trigger approach:
- GPIO11 generates a steady PWM signal at 10 Hz (10 FPS stream).
- Keys '1'..'9' change the PWM duty cycle (exposure high-time) in real time.
"""

import time
import cv2
import numpy as np
from gpiozero import PWMOutputDevice
from picamera2 import Picamera2

# ---- Configuration ----------------------------------------------------
XTR_GPIO_PIN = 11          # BCM numbering: GPIO11 (Physical Pin 23)
PWM_FREQ_HZ = 10           # Частота кадрового тригера = 10 Гц (10 FPS)
FRAME_WIDTH = 1456
FRAME_HEIGHT = 1088
WINDOW_NAME = "IMX296 Continuous PWM Control"

# Період одного кадру при 10 Гц дорівнює 100 мс (100,000 мкс)
PERIOD_MS = 1000 / PWM_FREQ_HZ  # 100 ms

# Таблиця duty_cycle (від 2% до 70% від періоду в 100 мс -> від 2 мс до 70 мс експозиції)
EXPOSURE_MAP = {
    ord("1"): (0.02, 2.0),   # Duty 2%  ->  2 ms (дуже темне)
    ord("2"): (0.05, 5.0),   # Duty 5%  ->  5 ms
    ord("3"): (0.10, 10.0),  # Duty 10% -> 10 ms
    ord("4"): (0.20, 20.0),  # Duty 20% -> 20 ms
    ord("5"): (0.30, 30.0),  # Duty 30% -> 30 ms (нормальне для кімнати)
    ord("6"): (0.40, 40.0),  # Duty 40% -> 40 ms
    ord("7"): (0.50, 50.0),  # Duty 50% -> 50 ms
    ord("8"): (0.60, 60.0),  # Duty 60% -> 60 ms
    ord("9"): (0.70, 70.0),  # Duty 70% -> 70 ms (дуже яскраве)
}

# ---- Initialize PWM Hardware/Software -----------------------------------
# Запускаємо PWM з початковим Duty Cycle 30% (30 мс) на частоті 10 Гц
current_duty, current_ms = EXPOSURE_MAP[ord("5")]
pwm = PWMOutputDevice(XTR_GPIO_PIN, frequency=PWM_FREQ_HZ, initial_value=current_duty)

# ---- Camera Setup -------------------------------------------------------
picam2 = Picamera2()
camera_config = picam2.create_still_configuration(
    main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
)
picam2.configure(camera_config)

# Запускаємо камеру (вона одразу підхоплює постійний PWM-сигнал з GPIO11)
picam2.start()

# Вимикаємо авто-експозицію та налаштовуємо підсилення
try:
    picam2.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "AnalogueGain": 4.0,  # Фіксоване аналогове підсилення x4
    })
except Exception as err:
    print(f"Warning setting controls: {err}")


def main():
    global current_duty, current_ms
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 960, 720)

    print("PWM Control started at 10 Hz.")
    print("Press '1'..'9' to change exposure duration in real time.")
    print("Press 'q' or ESC to quit.")

    try:
        while True:
            # 1. Захоплюємо поточний кадр з безперервного потоку
            frame = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # 2. Інформація про експозицію та яскравість
            avg_brightness = np.mean(frame_bgr)
            info_text = f"Exposure: {current_ms:.1f} ms (Duty: {current_duty*100:.0f}%) | Brightness: {avg_brightness:.1f}"

            cv2.putText(frame_bgr, info_text, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame_bgr, "Keys 1..9: Change exposure | Q: Quit", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow(WINDOW_NAME, frame_bgr)

            # 3. Обробка натискань клавіш у реальному часі (10 мс таймаут)
            key = cv2.waitKey(10) & 0xFF

            if key in (27, ord("q")):  # ESC або 'q'
                break

            if key in EXPOSURE_MAP:
                current_duty, current_ms = EXPOSURE_MAP[key]
                # Змінюємо тривалість високого імпульсу прямо під час роботи
                pwm.value = current_duty
                print(f"Set PWM Duty Cycle to {current_duty*100:.0f}% ({current_ms} ms exposure)")

    finally:
        picam2.stop()
        pwm.off()
        pwm.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()