import cv2
#from tools.mira220 import *
from tools.imx477 import *
from threading import Thread

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
            # Frame preprocessing
            frame = cv2.rotate(frame, cv2.ROTATE_180)

            frame = frame[:, :, 1]

            cv2.imshow("IR", frame)
            key = cv2.waitKey(1)
            if key == ord("q"):
                break

    cv2.destroyAllWindows()
    pin.off()





