from signal import pause
from gpiozero import RotaryEncoder, Button

from tools.global_vars import global_state



class EncoderController:
    """Controller for a rotary encoder with a push button (GPIO 17, 27, 22).

    Updates values inside the nested 'encoder' dictionary in global_state.
    """

    def __init__(self, pin_a=17, pin_b=27, pin_c=22, state_dict=global_state):
        self.state = state_dict

        # Initialize the rotary encoder (Pin A: GPIO17, Pin B: GPIO27)
        self.encoder = RotaryEncoder(a=pin_a, b=pin_b, max_steps=0)

        # Initialize the button (Pin C / SW: GPIO22) with debounce time
        self.button = Button(pin_c, bounce_time=0.05)

        # Attach event handlers
        self.encoder.when_rotated_clockwise = self._on_clockwise
        self.encoder.when_rotated_counter_clockwise = self._on_counter_clockwise
        self.button.when_pressed = self._on_button_click

    def _on_clockwise(self):
        """Increment the encoder value within the range [0, 100]."""
        if self.state["encoder"]["value"] < 100:
            self.state["encoder"]["value"] += 1
            print(f"Value incremented: {self.state['encoder']['value']} (Mode: {self.state['encoder']['mode']})")

    def _on_counter_clockwise(self):
        """Decrement the encoder value within the range [0, 100]."""
        if self.state["encoder"]["value"] > 0:
            self.state["encoder"]["value"] -= 1
            print(f"Value decremented: {self.state['encoder']['value']} (Mode: {self.state['encoder']['mode']})")

    def _on_button_click(self):
        """Cycle the mode between 1, 2, and 3 upon button press."""
        current_mode = self.state["encoder"]["mode"]
        self.state["encoder"]["mode"] = 1 if current_mode >= 3 else current_mode + 1
        print(f"Mode changed to: {self.state['encoder']['mode']}")


if __name__ == "__main__":
    # Initialize encoder controller
    controller = EncoderController()

    print("Encoder controller started. Listening for inputs...")
    print("Initial global state:", global_state)

    # Keep the main thread alive to handle GPIO events
    pause()