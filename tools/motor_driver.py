from gpiozero import OutputDevice
import time

MOTOR_A = [OutputDevice(9), OutputDevice(11)]
MOTOR_B = [OutputDevice(17), OutputDevice(27)]

def motor(ch, state):
    motor = [MOTOR_A, MOTOR_B][ch]
    if state == 1:
        motor[1].value = 0
        motor[0].value = 1
    elif state == 2:
        motor[0].value = 0
        motor[1].value = 1
    else:
        motor[0].value = 0
        motor[1].value = 0

def switch_filter(ch, direction, pulse_ms=100):
    """
    ch: 0 or 1 - channel
    direction: 1 - , 2 -
    pulse_ms: pulse duration in milliseconds
    """
    motor(ch, direction)
    time.sleep(pulse_ms / 1000)
    motor(ch, 0)


if __name__ == "__main__":

    for i in range(10):

        ch = int(input("Select motor channel (0 for A, 1 for B): "))
        state = int(input("Select motor state (0 for off, 1 for forward, 2 for backward): "))
        #motor(ch, state)
        switch_filter(ch, state, pulse_ms=100)

