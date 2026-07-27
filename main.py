from tools.mira220 import *


if __name__ == "__main__":
    from gpiozero import OutputDevice

    pin = OutputDevice(26, initial_value=False)
    pin.on()

    camera_loop()

    pin.off()





