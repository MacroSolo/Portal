import time
from threading import Lock
from gpiozero import PWMOutputDevice


class CameraExposurePWM:
    """
    PWM Exposure Controller for Raspberry Pi 5 using gpiozero.

    :param pin: GPIO pin number (BCM)
    :param fps: Frames per second (Hz)
    :param exposure_us: Exposure duration in microseconds (us)
    """

    def __init__(self, pin: int, fps: float = 30.0, exposure_us: float = 10000.0):
        self.pin = pin
        self.fps = fps
        self.exposure_us = exposure_us
        self.lock = Lock()

        # Initialize hardware/software PWM device on Raspberry Pi 5
        self.pwm = PWMOutputDevice(pin=self.pin)

        # Apply initial settings
        self.update_params(fps=fps, exposure_us=exposure_us)

    def _calculate_duty_cycle(self, fps: float, exposure_us: float):
        """Calculates PWM frequency and duty cycle using microseconds."""
        frame_period_us = 1_000_000.0 / fps

        if exposure_us > frame_period_us:
            raise ValueError(
                f"Exposure ({exposure_us} us) cannot exceed frame period ({frame_period_us:.2f} us for {fps} FPS)"
            )

        duty_cycle = exposure_us / frame_period_us
        return fps, duty_cycle

    def update_params(self, fps: float = None, exposure_us: float = None):
        """Updates FPS and/or Exposure (in us) on the fly safely."""
        with self.lock:
            if fps is not None:
                self.fps = fps
            if exposure_us is not None:
                self.exposure_us = exposure_us

            frequency, duty_cycle = self._calculate_duty_cycle(self.fps, self.exposure_us)

            # Update PWM parameters dynamically
            self.pwm.frequency = frequency
            self.pwm.value = duty_cycle

    def set_fps(self, fps: float):
        """Set a new FPS value on the fly."""
        self.update_params(fps=fps)

    def set_exposure(self, exposure_us: float):
        """Set a new exposure time in microseconds on the fly."""
        self.update_params(exposure_us=exposure_us)

    def stop(self):
        """Stop the PWM signal and release the GPIO pin."""
        with self.lock:
            self.pwm.off()
            self.pwm.close()