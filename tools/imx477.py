import time
import cv2
from collections import deque
from picamera2 import Picamera2
from tools.global_vars import global_state

frames = deque(maxlen=60)

def camera_loop(Exposure=4096, Gain=8):

    global_state["camera"]["exposure"] = Exposure
    global_state["camera"]["gain"] = Gain

    picam0 = Picamera2(camera_num=0)

    config0 = picam0.create_preview_configuration(
        main={"format": "BGR888", "size": (800, 1280)},
        buffer_count=2,
    )

    picam0.configure(config0)
    picam0.start()

    time.sleep(0.5)

    picam0.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "ExposureTime": Exposure,
        "AnalogueGain": Gain,
        "ColourGains": (1.5, 1.5)
    })

    counter = 0
    start = time.time()

    try:
        while True:
            frame0 = picam0.capture_array()
            frames.append(frame0)

            counter += 1
            elapsed = time.time() - start

            if elapsed >= 10:
                global_state["camera"]["fps"] = int(counter / elapsed)
                counter = 0
                start = time.time()

    finally:
        picam0.stop()


def camera_loop_0(Exposure=4096, Gain=8):
    global frames
    # Initialize the primary camera module
    picam0 = Picamera2(camera_num=0)

    # Set format to BGR888 and resolution to 1280x800
    config0 = picam0.create_preview_configuration(
        main={"format": "BGR888", "size": (800, 1280)},
        buffer_count=2,
    )
    picam0.configure(config0)
    picam0.start()

    # Wait briefly to ensure the camera hardware pipeline starts
    time.sleep(0.5)

    # Completely lock exposure, gain, and white balance
    # ColourGains is set to fixed red/blue gains to prevent AWB color-shifts
    picam0.set_controls({
        "AeEnable": False,
        "AwbEnable": False,
        "ExposureTime": Exposure,     # Exposure in microseconds
        "AnalogueGain": Gain,        # Fixed analog gain
        "ColourGains": (1.5, 1.5)   # Fixed red/blue white balance multipliers
    })


    try:
        while True:
            # Capture frame as a NumPy array
            frame0 = picam0.capture_array()
            frames.append(frame0)

    finally:
        # Clean up resources
        picam0.stop()



if __name__ == "__main__":
    camera_loop()