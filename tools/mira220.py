import cv2
from picamera2 import Picamera2


def camera_loop():
    picam0 = Picamera2(camera_num=0)
    config0 = picam0.create_preview_configuration(main={"format": "YUV420", "size": (1600, 1400)})
    picam0.configure(config0)
    picam0.start()

    # Disable auto exposure/gain, then set manual values
    # ExposureTime is in microseconds, AnalogueGain is a float multiplier
    picam0.set_controls({
        "AeEnable": False,
        "ExposureTime": 1_000,
        "AnalogueGain": 8,
    })

    while True:
        frame0 = picam0.capture_array()
        frame0 = frame0[:1400, :1600]  # Crop to 1600x1400

        # Rotate 180 degrees
        frame0 = cv2.rotate(frame0, cv2.ROTATE_180)

        cv2.imshow("Mira220", frame0)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    picam0.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    camera_loop()