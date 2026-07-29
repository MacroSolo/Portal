import cv2
from picamera2 import Picamera2


def camera_loop():
    # Initialize the primary camera module
    picam0 = Picamera2(camera_num=0)

    # Set format to BGR888 and resolution to 1280x800
    config0 = picam0.create_preview_configuration(
        main={"format": "BGR888", "size": (1280, 800)}
    )
    picam0.configure(config0)
    picam0.start()

    # Disable auto exposure/gain and set manual values
    picam0.set_controls({
        "AeEnable": False,
        "ExposureTime": 10_000,
        "AnalogueGain": 2.0,
    })

    window_name = "Raspberry Pi HD Camera"

    # Create a named window and set it to full screen mode
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    try:
        while True:
            # Capture frame as a NumPy array
            frame0 = picam0.capture_array()

            # Rotate image 180 degrees
            frame0 = cv2.rotate(frame0, cv2.ROTATE_180)

            # Display the full screen frame
            cv2.imshow(window_name, frame0)

            # Press 'q' to exit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        # Clean up resources
        picam0.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    camera_loop()