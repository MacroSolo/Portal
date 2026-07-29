import time
import cv2
from collections import deque
from picamera2 import Picamera2

frames = deque(maxlen=30)

def camera_loop():
    global frames
    # Initialize the primary camera module
    picam0 = Picamera2(camera_num=0)

    # Set format to BGR888 and resolution to 1280x800
    config0 = picam0.create_preview_configuration(
        main={"format": "BGR888", "size": (1280, 800)},
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
        "ExposureTime": 5_000,     # Exposure in microseconds
        "AnalogueGain": 5.0,        # Fixed analog gain
        #"ColourGains": (1.5, 1.5)   # Fixed red/blue white balance multipliers
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