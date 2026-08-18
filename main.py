import cv2
import numpy as np
#from tools.mira220 import *
from tools.imx477 import *
#from tools.motor_driver import *
from threading import Thread
import matplotlib.pyplot as plt
from MQTT.MQTT_connector import *

from tools.CloudConfigClient import get_config
config = get_config()

from tools.AWS_S3_recorder import *
s3_client = boto3.client('s3',
                         region_name='eu-central-1',
                         aws_access_key_id=config['s3_id'],
                         aws_secret_access_key=config['s3_secret'])


from gpiozero import Button, OutputDevice

mode = 0
sw_9 = Button(18, pull_up=True)
sw_11 = Button(15, pull_up=True)


def on_switch_change():
    global mode

    if sw_9.is_pressed:
        mode = 1
    elif sw_11.is_pressed:
        mode = 2
    else:
        mode = 0


def get_mpl_lut(cmap_name: str) -> np.ndarray:
    """Convert a Matplotlib colormap into an OpenCV BGR LUT array (256x1x3 uint8)."""
    cmap = plt.get_cmap(cmap_name)
    # Sample 256 RGBA values in range [0.0, 1.0]
    colors = cmap(np.linspace(0, 1, 256))
    # Extract RGB, scale to [0, 255], and convert to uint8
    rgb_colors = (colors[:, :3] * 255).astype(np.uint8)
    # Convert RGB to BGR for OpenCV compatibility
    bgr_colors = rgb_colors[:, ::-1]
    # Reshape to required OpenCV LUT layout: (256, 1, 3)
    return np.reshape(bgr_colors, (256, 1, 3))


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


def rank_normalize_image(img: np.ndarray) -> np.ndarray:
    """
    Performs fast rank-based histogram normalization on a grayscale image.
    Maps unique intensity values to evenly spaced ranks in the [0, 255] range
    using a Lookup Table (LUT).

    Parameters:
        img (np.ndarray): Input 2D grayscale image (uint8).

    Returns:
        np.ndarray: Normalized 2D grayscale image (uint8).
    """
    # 1. Extract unique pixel values present in the image
    unique_vals = np.unique(img)
    num_unique = len(unique_vals)

    # Edge case: If image is empty or uniform (0 or 1 unique intensity)
    if num_unique <= 1:
        return img.copy()

    # 2. Compute target normalized values (0 to 255) for each unique rank
    ranks = np.linspace(0, 255, num_unique, dtype=np.uint8)

    # 3. Initialize a 256-element Lookup Table (LUT)
    lut = np.zeros(256, dtype=np.uint8)

    # 4. Map target rank values to corresponding original pixel intensities
    lut[unique_vals] = ranks

    # 5. Fast replacement of pixel values using OpenCV C-implementation
    return cv2.LUT(img, lut)


def command_main(topic, payload):
    print(f"[command] topic={topic}  payload={payload}")
    if payload.lower().startswith("s3/"):
        try:
            label = payload.lower()[3:]
            frames_copy = frames[-1].copy()
            cv2.putText(frames_copy, f"RECORDING", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)
            cv2.imshow("IR", frames_copy)
            cv2.waitKey(1)
            save_frame_series_s3(frames, label, s3_client, bucket='merlin-ds', timestamp=int(time.time()))
        except Exception as e:
            print(f"Error saving frames to S3: {e}")


if __name__ == "__main__":

    mqcmd_main = MQTTClient(
        host="521fa758f36d406f82650a9a06bdefc2.s1.eu.hivemq.cloud",
        port=8883,
        username="Merlin",
        password="Merlin6m",
        subscription="portal/commands",
        on_message=command_main,
    )

    mqcmd_main.connect()


    lut_colormap = get_mpl_lut("CMRmap")

    pin = OutputDevice(25, initial_value=False)

    sw_9.when_pressed = on_switch_change
    sw_9.when_released = on_switch_change
    sw_11.when_pressed = on_switch_change
    sw_11.when_released = on_switch_change
    on_switch_change()

    cpu_serial = get_cpu_serial()

    thread = Thread(target=camera_loop, kwargs={"Exposure": 4096, "Gain": 8}, daemon=True)
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

            cpu_temp = 0.9 * cpu_temp + 0.1 * get_cpu_temperature()

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

            if mode == 0:
                colored_frame = cv2.applyColorMap(frame, cv2.COLORMAP_BONE)

            elif mode == 2:
                frame = rank_normalize_image(frame)
                colored_frame = cv2.applyColorMap(frame, lut_colormap)

            else:
                frame = rank_normalize_image(frame)
                colored_frame = cv2.applyColorMap(frame, cv2.COLORMAP_BONE)

            frame = colored_frame

            frame = terminal_log(frame, logs)

            cv2.imshow("IR", frame)
            key = cv2.waitKey(30)
            if key == ord("q"):
                break

    cv2.destroyAllWindows()
    pin.off()
