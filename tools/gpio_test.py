"""
IMX296 External Trigger PWM Signal Generator
--------------------------------------------
Generates a hardware-based PWM signal on GPIO11 (BCM) to provide timing
pulses for the IMX296 camera in Slave/External Trigger mode.
"""

import time
import sys
import lgpio

# Configuration Parameters
GPIO_PIN = 11  # BCM GPIO11 (Physical Pin 23)
PWM_FREQ_HZ = 30  # Trigger frequency: 10 Hz (100 ms frame cycle = 10 FPS)
INITIAL_DUTY_PCT = 10.0  # 30% duty cycle = 30 ms HIGH pulse duration (exposure time)


def main():
    print("=== IMX296 External Trigger PWM Generator ===")

    # Determine the correct GPIO chip index for Raspberry Pi OS (Bookworm)
    # Typically gpiochip4 on RPi 5/4, or fallback to gpiochip0
    chip_num = 4
    chip_handle = None

    try:
        chip_handle = lgpio.gpiochip_open(chip_num)
        print(f"[SUCCESS] Connected to gpiochip{chip_num}")
    except lgpio.error:
        print(f"[INFO] gpiochip4 not available, trying gpiochip0...")
        try:
            chip_num = 0
            chip_handle = lgpio.gpiochip_open(chip_num)
            print(f"[SUCCESS] Connected to gpiochip{chip_num}")
        except lgpio.error as err:
            print(f"[FATAL] Failed to open GPIO chip interface: {err}")
            sys.exit(1)

    try:
        # Start continuous hardware PWM signal on specified GPIO pin
        # Parameters: (handle, gpio_pin, frequency_hz, duty_cycle_percent)
        lgpio.tx_pwm(chip_handle, GPIO_PIN, PWM_FREQ_HZ, INITIAL_DUTY_PCT)

        pulse_ms = (INITIAL_DUTY_PCT / 100.0) * (1000.0 / PWM_FREQ_HZ)
        print(f"[ACTIVE] PWM enabled on GPIO{GPIO_PIN}")
        print(f"         - Frequency: {PWM_FREQ_HZ} Hz")
        print(f"         - Duty Cycle: {INITIAL_DUTY_PCT}% ({pulse_ms:.1f} ms HIGH exposure pulse)")
        print("--------------------------------------------------")
        print("System is broadcasting pulses. Press Ctrl+C to stop.")

        # Keep the main process alive to maintain the active PWM output
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received. Stopping PWM generator...")

    finally:
        if chip_handle is not None:
            # Safely disable the PWM signal and release GPIO hardware resources
            lgpio.tx_pwm(chip_handle, GPIO_PIN, 0, 0)
            lgpio.gpiochip_close(chip_handle)
            print("[CLEANUP] PWM disabled and GPIO handle closed successfully.")


if __name__ == "__main__":
    main()