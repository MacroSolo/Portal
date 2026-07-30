import cv2
#from tools.mira220 import *
from tools.imx477 import *
from threading import Thread

import cv2
import numpy as np

from gpiozero import Button, OutputDevice
mode = 0
sw_9 = Button(9, pull_up=True)
sw_11 = Button(11, pull_up=True)

def on_switch_change():
    global mode

    if sw_9.is_pressed:
        mode = 1
    elif sw_11.is_pressed:
        mode = 2
    else:
        mode = 0



def terminal_log(img, logs=["log1", "log2", "log3"]):
    img = img.copy()
    for i, log in enumerate(logs):
        x, y = 10, 40 + i * 40
        #cv2.putText(img, log, (x, y), cv2.FONT_HERSHEY_SIMPLEX, fontScale=1.5, color=(0, 0, 0), thickness=700)
        cv2.putText(img, log, (x, y), cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, color=(255, 255, 255), thickness=1)
    return img


def get_cpu_temperature():
    # Reads the temperature from the system file
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_str = f.read()
        # Convert from millidegrees to degrees Celsius
        temp_c = float(temp_str) / 1000.0
    except Exception:
        temp_c = -1.0
    return temp_c

def get_cpu_serial():
    cpu_serial = "Unknown"
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("Serial"):
                    cpu_serial = line.split(":")[1].strip()
                    break
    except Exception:
        pass
    return cpu_serial


def apply_sigmoid_contrast(frame, k=10, midpoint=0.5):
    """
    Transforms linear pixel brightness into an S-shaped (sigmoid) curve.
    Darkens shadows and smoothly boosts highlights.

    :param frame: Input image frame (NumPy array, uint8)
    :param k: Steepness of the sigmoid curve. Higher values mean higher contrast (typical range: 5 to 15)
    :param midpoint: Inflection point in range [0.0, 1.0] (default: 0.5 for neutral center)
    :return: Processed frame with modified brightness curve
    """
    # 1. Create a normalized input array with 256 values (from 0.0 to 1.0)
    x = np.linspace(0, 1, 256)

    # 2. Compute the sigmoid curve: 1 / (1 + e^(-k * (x - midpoint)))
    sigmoid = 1 / (1 + np.exp(-k * (x - midpoint)))

    # 3. Normalize to ensure exact boundary mapping (0.0 to 0.0 and 1.0 to 1.0)
    s_min = 1 / (1 + np.exp(-k * (0 - midpoint)))
    s_max = 1 / (1 + np.exp(-k * (1 - midpoint)))
    sigmoid_normalized = (sigmoid - s_min) / (s_max - s_min)

    # 4. Map normalized values back to uint8 range (0..255) to build the Look-Up Table (LUT)
    lut = (sigmoid_normalized * 255).astype(np.uint8)

    # 5. Apply the LUT instantly across all frame pixels
    return cv2.LUT(frame, lut)

    # Example usage:
    # adjusted_frame = apply_sigmoid_contrast(frame, k=8, midpoint=0.5)


if __name__ == "__main__":
    pin = OutputDevice(26, initial_value=False)

    sw_9.when_pressed = on_switch_change
    sw_9.when_released = on_switch_change
    sw_11.when_pressed = on_switch_change
    sw_11.when_released = on_switch_change
    on_switch_change()

    cpu_serial = get_cpu_serial()

    thread = Thread(target=camera_loop, daemon=True)
    thread.start()

    pin.on()

    # Create a named window and set it to full screen mode
    window_name = "IR"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    cpu_temp = get_cpu_temperature()
    while True:
        frame = frames[-1] if frames else None

        if frame is not None:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            cpu_temo = 0.9 * cpu_temp + 0.1 * get_cpu_temperature()

            logs = [
                f"CPU Serial: {cpu_serial}",
                f"CPU Temp: {int(cpu_temp)} C",
                f"mode: {mode}",
                f"",
                f"frames: {len(frames)}",
            ]



            # Frame preprocessing

            frame = frame[:, :, 2]
            frame = np.clip(frame, 35, 255)
            # normalize to 0-255
            frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX)


            if mode == 0:
                colored_frame = cv2.applyColorMap(frame, cv2.COLORMAP_BONE)
            elif mode == 1:
                colored_frame = cv2.applyColorMap(frame, cv2.COLORMAP_JET)
            else:
                colored_frame = cv2.applyColorMap(frame, cv2.COLORMAP_BONE)
                colored_frame[frame <= 35] = (255, 55, 0)

            frame = colored_frame


            frame = terminal_log(frame, logs)

            cv2.imshow("IR", frame)
            key = cv2.waitKey(30)
            if key == ord("q"):
                break

    cv2.destroyAllWindows()
    pin.off()





