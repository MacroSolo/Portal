"""
IMX296 External Trigger Control: Early PWM Startup + Picamera2 Init
"""

import time
import cv2
import numpy as np
from gpiozero import PWMOutputDevice
from picamera2 import Picamera2

# ---- Config -------------------------------------------------------------
XTR_GPIO_PIN = 11      # BCM GPIO11 (Physical Pin 23)
PWM_FREQ_HZ = 10       # 10 Гц = період кадру 100 мс (10 FPS)
WINDOW_NAME = "IMX296 PWM Exposure Stream"

EXPOSURE_MAP = {
    ord("1"): (0.02, 2.0),
    ord("2"): (0.05, 5.0),
    ord("3"): (0.10, 10.0),
    ord("4"): (0.20, 20.0),
    ord("5"): (0.30, 30.0),
    ord("6"): (0.40, 40.0),
    ord("7"): (0.50, 50.0),
    ord("8"): (0.60, 60.0),
    ord("9"): (0.70, 70.0),
}

# =========================================================================
# ЕТАП 1: ГАРАНТОВАНИЙ СТАРТ PWM ДО БУДЬ-ЯКИХ ДІЙ З КАМЕРОЮ
# =========================================================================
print("--- [КРОК 1] Запуск системного PWM на GPIO11 ---")
current_duty, current_ms = EXPOSURE_MAP[ord("5")]

# Ініціалізуємо пристрій PWM і примусово активуємо вихід
pwm = PWMOutputDevice(XTR_GPIO_PIN, frequency=PWM_FREQ_HZ, initial_value=0.0)
time.sleep(0.1)

# Встановлюємо робочий Duty Cycle та вмикаємо генератор
pwm.value = current_duty
print(f"PWM активний: {PWM_FREQ_HZ} Гц, тривалість імпульсу: {current_ms} мс")

# Даємо час hardware/software PWM стабілізуватися і видати серію імпульсів
print("Очікування стабілізації тригерного сигналу (1 сек)...")
time.sleep(1.0)

# =========================================================================
# ЕТАП 2: ІНІЦІАЛІЗАЦІЯ КАМЕРИ ПІСЛЯ ПОДАЧІ ТАКТОВОГО СИГНАЛУ
# =========================================================================
print("--- [КРОК 2] Ініціалізація Picamera2 ---")
picam2 = Picamera2()

# Налаштовуємо конфігурацію кадру
config = picam2.create_still_configuration(main={"size": (1456, 1088), "format": "RGB888"})
picam2.configure(config)

# Запускаємо камеру
picam2.start()

# Фіксуємо підсилення сенсора
try:
    picam2.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "AnalogueGain": 4.0,
    })
except Exception as e:
    print(f"Попередження при налаштуванні коефіцієнтів: {e}")

# =========================================================================
# ЕТАП 3: ГОЛОВНИЙ ЦИКЛ ОБРОБКИ КАДРІВ
# =========================================================================
def main():
    global current_duty, current_ms
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 960, 720)

    print("\n[УСПІХ] Камера готово до зчитування кадрів за тригером.")
    print("Клавіші 1..9: Зміна тривалості імпульсу | Q: Вихід\n")

    try:
        while True:
            # Захоплення кадру, синхронізованого з PWM
            frame = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            avg_brightness = np.mean(frame_bgr)
            info_text = f"Pulse: {current_ms:.1f} ms | Avg Brightness: {avg_brightness:.1f}"

            cv2.putText(frame_bgr, info_text, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame_bgr, "Keys 1..9: Exposure | Q: Quit", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow(WINDOW_NAME, frame_bgr)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break

            if key in EXPOSURE_MAP:
                current_duty, current_ms = EXPOSURE_MAP[key]
                pwm.value = current_duty
                print(f"Новий імпульс експозиції: {current_ms} ms (Duty: {current_duty*100:.0f}%)")

    finally:
        picam2.stop()
        pwm.off()
        pwm.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()