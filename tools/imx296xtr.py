"""
IMX296 Direct GPIO11 Hardware Trigger & Exposure Control
"""

import time
import cv2
import numpy as np
from gpiozero import PWMOutputDevice
from picamera2 import Picamera2

# ---- Config -------------------------------------------------------------
XTR_GPIO_PIN = 11  # BCM GPIO11 (Physical Pin 23)
PWM_FREQ_HZ = 10  # 10 Гц = період кадру 100 мс (10 FPS)
WINDOW_NAME = "IMX296 PWM Exposure Stream"

# Карта клавіш 1..9: тривалість імпульсу (Duty Cycle від 100мс періоду)
EXPOSURE_MAP = {
    ord("1"): (0.02, 2.0),  # 2ms HIGH -> Дуже темно
    ord("2"): (0.05, 5.0),  # 5ms
    ord("3"): (0.10, 10.0),  # 10ms
    ord("4"): (0.20, 20.0),  # 20ms
    ord("5"): (0.30, 30.0),  # 30ms -> Нормальне освітлення
    ord("6"): (0.40, 40.0),  # 40ms
    ord("7"): (0.50, 50.0),  # 50ms
    ord("8"): (0.60, 60.0),  # 60ms
    ord("9"): (0.70, 70.0),  # 70ms -> Дуже яскраво
}

# 1. ЗАПУСКАЄМО PWM-СИГНАЛ ДО ІНІЦІАЛІЗАЦІЇ КАМЕРИ
# Це критично: сенсор має отримувати тактову частоту з першої мілісекунди
current_duty, current_ms = EXPOSURE_MAP[ord("5")]
pwm = PWMOutputDevice(XTR_GPIO_PIN, frequency=PWM_FREQ_HZ, initial_value=current_duty)

print("1. PWM сигнал активовано на GPIO11 (10 Гц)...")
time.sleep(0.3)  # Даємо генератору зробити 3 імпульси для стабілізації камери

# 2. ІНІЦІАЛІЗАЦІЯ КАМЕРИ
print("2. Підключаємо Picamera2...")
picam2 = Picamera2()
config = picam2.create_still_configuration(main={"size": (1456, 1088), "format": "RGB888"})
picam2.configure(config)

# Вимикаємо таймаут чекання кадрів у libcamera
picam2.start()

# Вимикаємо авто-експозицію, щоб бачити суто фізичний вплив тригера
try:
    picam2.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "AnalogueGain": 4.0,
    })
except Exception as e:
    print(f"Warning setting controls: {e}")


# 3. ОСНОВНИЙ ЦИКЛ ПЕРЕГЛЯДУ ТА ЗМІНИ ЕКСПОЗИЦІЇ
def main():
    global current_duty, current_ms
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 960, 720)

    print("\n[УСПІХ] Відеопотік за тригером запущено!")
    print("Натискайте клавіші 1..9 для зміни тривалості імпульсу.")
    print("Натисніть Q або ESC для виходу.\n")

    try:
        while True:
            # Отримуємо кадр, згенерований за імпульсом з GPIO11
            frame = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            avg_brightness = np.mean(frame_bgr)
            info_text = f"Pulse: {current_ms:.1f} ms | Avg Brightness: {avg_brightness:.1f}"

            # Малюємо інформаційний оверлей
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
                print(f"Новий імпульс експозиції: {current_ms} ms (Duty: {current_duty * 100:.0f}%)")

    finally:
        picam2.stop()
        pwm.off()
        pwm.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()