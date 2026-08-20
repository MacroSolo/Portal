from signal import pause
from gpiozero import RotaryEncoder, Button

try:
    from tools.global_vars import global_state
except ImportError:
    # If the import fails, define a default global_state for testing purposes
    global_state = {}


class EncoderController:
    """Configurable Rotary Encoder Controller that manages predefined modes,

    maintains option memory per mode, supports explicit default values,
    and updates global state dictionary in real time.
    """

    def __init__(self, mode_config: dict, pin_a=17, pin_b=27, pin_c=22, state_dict=global_state):
        self.state = state_dict
        self.mode_config = mode_config
        self.modes_list = list(mode_config.keys())

        if not self.modes_list:
            raise ValueError("mode_config dictionary cannot be empty.")

        # Dictionary to store active index for each mode
        self.mode_indices = {}

        # Parse configuration and set initial indices based on default values
        for mode_key, mode_data in self.mode_config.items():
            options = mode_data.get("options", ())
            default_val = mode_data.get("default_value")

            if not options:
                raise ValueError(f"Mode '{mode_key}' must contain a non-empty 'options' tuple/list.")

            if default_val is not None and default_val in options:
                self.mode_indices[mode_key] = options.index(default_val)
            else:
                # Fallback to the first available option if default is invalid or missing
                self.mode_indices[mode_key] = 0

        # Snapshot initial indices for state reset capabilities
        self._default_indices = self.mode_indices.copy()
        self._default_mode_index = 0

        # Set initial active mode index
        self.current_mode_index = self._default_mode_index

        # Sync values with global_state
        self._update_global_state()

        # Initialize hardware components
        self.encoder = RotaryEncoder(a=pin_a, b=pin_b, max_steps=0)
        self.button = Button(pin_c, bounce_time=0.05)

        # Attach hardware interrupt handlers
        self.encoder.when_rotated_clockwise = self._on_clockwise
        self.encoder.when_rotated_counter_clockwise = self._on_counter_clockwise
        self.button.when_pressed = self._on_button_click

    @property
    def current_mode(self):
        """Get the current mode string key."""
        return self.modes_list[self.current_mode_index]

    def _update_global_state(self):
        """Synchronize class internal state with the global state dictionary."""
        active_mode = self.current_mode
        value_index = self.mode_indices[active_mode]
        active_value = self.mode_config[active_mode]["options"][value_index]

        self.state["encoder"]["mode"] = active_mode
        self.state["encoder"]["value"] = active_value

    def _on_clockwise(self):
        """Move to the next option within the active mode."""
        active_mode = self.current_mode
        options_count = len(self.mode_config[active_mode]["options"])
        current_idx = self.mode_indices[active_mode]

        if current_idx < options_count - 1:
            self.mode_indices[active_mode] += 1
            self._update_global_state()
            print(f"[{active_mode}] Next -> {self.state['encoder']['value']}")

    def _on_counter_clockwise(self):
        """Move to the previous option within the active mode."""
        active_mode = self.current_mode
        current_idx = self.mode_indices[active_mode]

        if current_idx > 0:
            self.mode_indices[active_mode] -= 1
            self._update_global_state()
            print(f"[{active_mode}] Prev -> {self.state['encoder']['value']}")

    def _on_button_click(self):
        """Cycle sequentially to the next mode."""
        self.current_mode_index = (self.current_mode_index + 1) % len(self.modes_list)
        self._update_global_state()
        print(f"Switched Mode -> {self.state['encoder']['mode']} | Current Value: {self.state['encoder']['value']}")

    def reset_to_defaults(self):
        """Reset mode positions back to their defined default settings."""
        self.mode_indices = self._default_indices.copy()
        self.current_mode_index = self._default_mode_index
        self._update_global_state()
        print("Encoder state reset to initial default values.")


# --- Example Usage ---
if __name__ == "__main__":
    # Professional configuration design using 'options' and 'default_value'
    ENCODER_CONFIG = {
        "exposure": {
            "default_value": 4096,
            "options": (64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536)
        },
        "gain": {
            "default_value": 8,
            "options": (1, 2, 4, 8, 16)
        },
                    }

    controller = EncoderController(mode_config=ENCODER_CONFIG)

    print("Encoder controller started.")
    print("Initial global state:", global_state)

    pause()