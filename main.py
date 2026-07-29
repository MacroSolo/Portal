import cv2
#from tools.mira220 import *
from tools.imx477 import *
from threading import Thread

import cv2
import numpy as np


def terminal_log(img, logs=["log1", "log2", "log3"]):
    img = img.copy()
    for i, log in enumerate(logs):
        cv2.putText(img, log, (10, 40 + i * 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 15)
        cv2.putText(img, log, (10, 40 + i * 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1)
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
    from gpiozero import OutputDevice

    pin = OutputDevice(26, initial_value=False)

    thread = Thread(target=camera_loop, daemon=True)
    thread.start()

    pin.on()

    # Create a named window and set it to full screen mode
    window_name = "IR"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


    while True:
        frame = frames[-1] if frames else None
        if frame is not None:

            logs = [
                f"CPU Serial: {123}",
                f"CPU Temp: {int(get_cpu_temperature())} C",
                f"",
                f"",
                f"frames: {len(frames)}",
            ]



            # Frame preprocessing
            frame = cv2.rotate(frame, cv2.ROTATE_180)

            frame = frame[:, :, 2]
            frame = apply_sigmoid_contrast(frame, k=3, midpoint=0.1)

            # add colormap to the frame
            frame = cv2.applyColorMap(frame, cv2.COLORMAP_BONE)

            frame = terminal_log(frame, logs)

            cv2.imshow("IR", frame)
            key = cv2.waitKey(1)
            if key == ord("q"):
                break

    cv2.destroyAllWindows()
    pin.off()





