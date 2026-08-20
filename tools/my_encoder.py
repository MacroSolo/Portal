from signal import pause
from gpiozero import RotaryEncoder, Button


try:
    from tools.global_vars import global_state
except ImportError:
    # If the import fails, define a default global_state for testing purposes
    global_state = {}


class EncoderController:
    """Configurable Rotary Encoder Controller.

    Automatically initializes missing dictionary keys in global_state.
    """

    def __init__(self, mode_config: dict, pin_a=17, pin_b=27, pin_c=22, state_dict=global_state):
        self.state = state_dict
        self.mode_config = mode_config
        self.modes_list = list(mode_config.keys())

        if not self.modes_list:
            raise ValueError("mode_config dictionary cannot be empty.")

        # Ensure required top-level keys exist in global_state automatically
        if "camera" not in self.state or not isinstance(self.state["camera"], dict):
            self.state["camera"] = {}

        if "encoder" not in self.state or not isinstance(self.state["encoder"], dict):
            self.state["encoder"] = {}

        # Store option index per parameter
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

        # Initialize hardware components
        self.encoder = RotaryEncoder(a=pin_a, b=pin_b, max_steps=0)
        self.button = Button(pin_c, bounce_time=0.05)

        # Attach hardware interrupt handlers
        self.encoder.when_rotated_clockwise = self._on_clockwise
        self.encoder.when_rotated_counter_clockwise = self._on_counter_clockwise
        self.button.when_pressed = self._on_button_click

        # Initial sync to populate global_state keys
        self._sync_all_to_global_state()

    @property
    def current_mode(self):
        """Get current target camera parameter name (e.g., 'exposure')."""
        return self.modes_list[self.current_mode_index]

    def _sync_all_to_global_state(self):
        """Writes current selected options directly into global_state['camera'] and ['encoder']."""
        for param_key, idx in self.mode_indices.items():
            value = self.mode_config[param_key]["options"][idx]
            self.state["camera"][param_key] = value

        # Update active encoder status metadata safely
        active_mode = self.current_mode
        self.state["encoder"]["mode"] = active_mode
        self.state["encoder"]["value"] = self.state["camera"][active_mode]

    def _on_clockwise(self):
        """Increase the active parameter value."""
        active_mode = self.current_mode
        options_count = len(self.mode_config[active_mode]["options"])
        current_idx = self.mode_indices[active_mode]

        if current_idx < options_count - 1:
            self.mode_indices[active_mode] += 1
            self._sync_all_to_global_state()
            print(f"Updated {active_mode} -> {self.state['camera'][active_mode]}")

    def _on_counter_clockwise(self):
        """Decrease the active parameter value."""
        active_mode = self.current_mode
        current_idx = self.mode_indices[active_mode]

        if current_idx > 0:
            self.mode_indices[active_mode] -= 1
            self._sync_all_to_global_state()
            print(f"Updated {active_mode} -> {self.state['camera'][active_mode]}")

    def _on_button_click(self):
        """Switch active parameter (exposure -> gain -> fps)."""
        self.current_mode_index = (self.current_mode_index + 1) % len(self.modes_list)
        self._sync_all_to_global_state()
        print(f"Switched control to: {self.current_mode} (Value: {self.state['encoder']['value']})")


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