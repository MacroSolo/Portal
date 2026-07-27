import cv2
import numpy as np
from picamera2 import Picamera2

from gpiozero import OutputDevice
pin = OutputDevice(16, initial_value=False)
pin.on()


def camera_loop():
    picam0 = Picamera2(camera_num=0)
    config0 = picam0.create_preview_configuration(main={"format": "YUV420", "size": (1600, 1400)})
    picam0.configure(config0)
    picam0.start()

    #picam1 = Picamera2(camera_num=1)
    #config1 = picam1.create_preview_configuration(main={"format": "YUV420", "size": (640, 480)})
    #picam1.configure(config1)
    #picam1.start()


    while True:
        frame0 = picam0.capture_array()
        frame0 = frame0[:1400, :1600]  # Crop to 1600x1400

        cv2.imshow("Mira220", frame0)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    picam0.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":

    camera_loop()

    pin.off()
