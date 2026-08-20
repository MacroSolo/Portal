import time
from gpiozero import RotaryEncoder, Button
from tools.global_vars import global_state


class EncoderController:
    """Universal Rotary Encoder Controller with built-in rotation debouncing/throttling."""

    def __init__(self, mode_config: dict, on_change_callback=None, pin_a=17, pin_b=27, pin_c=22,
                 state_dict=global_state, min_interval=0.1):
        self.state = state_dict
        self.mode_config = mode_config
        self.modes_list = list(mode_config.keys())
        self.on_change_callback = on_change_callback
        self.min_interval = min_interval  # Minimum time between step triggers (in seconds)
        self._last_rotation_time = 0      # Timestamp of the last accepted step

        if not self.modes_list:
            raise ValueError("mode_config dictionary cannot be empty.")

        # Ensure required keys exist in global_state
        if "camera" not in self.state or not isinstance(self.state["camera"], dict):
            self.state["camera"] = {}

        if "encoder" not in self.state or not isinstance(self.state["encoder"], dict):
            self.state["encoder"] = {}

        # Parse initial option indices from default values
        self.mode_indices = {}
        for param_key, param_data in self.mode_config.items():
            options = param_data.get("options", ())
            default_val = param_data.get("default_value")

            if not options:
                raise ValueError(f"Parameter '{param_key}' must have non-empty 'options'.")

            if default_val is not None and default_val in options:
                self.mode_indices[param_key] = options.index(default_val)
            else:
                self.mode_indices[param_key] = 0

        self.current_mode_index = 0

        # Hardware setup
        self.encoder = RotaryEncoder(a=pin_a, b=pin_b, max_steps=0)
        self.button = Button(pin_c, bounce_time=0.1)  # Increased button debounce

        # Attach hardware interrupts
        self.encoder.when_rotated_clockwise = self._on_clockwise
        self.encoder.when_rotated_counter_clockwise = self._on_counter_clockwise
        self.button.when_pressed = self._on_button_click

        # Initial state sync
        self._notify_change()

    @property
    def current_mode(self):
        """Get current active mode key."""
        return self.modes_list[self.current_mode_index]

    def _should_process_rotation(self) -> bool:
        """Rate-limiter: checks if enough time has passed since the last accepted step."""
        now = time.time()
        if now - self._last_rotation_time >= self.min_interval:
            self._last_rotation_time = now
            return True
        return False

    def _notify_change(self):
        """Updates internal/global state and triggers external callback if present."""
        active_mode = self.current_mode
        value_index = self.mode_indices[active_mode]
        current_value = self.mode_config[active_mode]["options"][value_index]

        # Update global state metadata
        self.state["encoder"]["mode"] = active_mode
        self.state["encoder"]["value"] = current_value

        # Call user-defined callback function if provided
        if callable(self.on_change_callback):
            self.on_change_callback(active_mode, current_value)

    def _on_clockwise(self):
        """Step to next option in current mode (throttled)."""
        if not self._should_process_rotation():
            return

        active_mode = self.current_mode
        options_count = len(self.mode_config[active_mode]["options"])
        current_idx = self.mode_indices[active_mode]

        if current_idx < options_count - 1:
            self.mode_indices[active_mode] += 1
            self._notify_change()

    def _on_counter_clockwise(self):
        """Step to previous option in current mode (throttled)."""
        if not self._should_process_rotation():
            return

        active_mode = self.current_mode
        current_idx = self.mode_indices[active_mode]

        if current_idx > 0:
            self.mode_indices[active_mode] -= 1
            self._notify_change()

    def _on_button_click(self):
        """Switch active mode."""
        self.current_mode_index = (self.current_mode_index + 1) % len(self.modes_list)
        self._notify_change()