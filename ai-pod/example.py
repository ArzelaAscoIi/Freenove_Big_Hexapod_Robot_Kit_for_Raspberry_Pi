"""Quick smoke-test for the ai-pod Robot interface.

Run from the ai-pod directory while the hexapod server is running:

    uv run python example.py <robot-ip>

Example:

    uv run python example.py 192.168.0.58
"""

from __future__ import annotations

import sys
import time

from ai_pod import Attitude, Color, GaitType, Position, Robot


def main(host: str) -> None:
    print(f"Connecting to robot at {host} …")

    with Robot(host=host) as bot:
        print(f"  Connected: {bot}")
        print(f"  State: {bot.state.model_dump_json(indent=2)}\n")

        # --- servos on ---
        print("Activating servos …")
        bot.activate()
        time.sleep(1)

        # --- battery check ---
        battery = bot.read_battery()
        print(f"Battery: {battery.voltage_1:.2f} V / {battery.voltage_2:.2f} V")
        if battery.is_low:
            print("  ⚠ Battery low!")

        # --- ultrasonic ---
        distance = bot.read_distance()
        print(f"Distance: {distance.distance_cm:.1f} cm")

        # --- LEDs ---
        print("LEDs → green")
        bot.set_led_color(Color.green())
        time.sleep(1)

        # --- small walk ---
        print("Walking forward (2 steps) …")
        bot.set_gait(GaitType.TRIPOD)
        for _ in range(2):
            bot.move_forward(speed=6)
            time.sleep(0.5)
        bot.stop()
        time.sleep(0.5)

        # --- body pose ---
        print("Raising body …")
        bot.set_height(z=20)
        time.sleep(1)

        print("Tilting forward …")
        bot.set_attitude(Attitude(pitch=15))
        time.sleep(1)

        print("Reset pose")
        bot.reset_pose()
        time.sleep(1)

        # --- head ---
        print("Looking left …")
        bot.look_left()
        time.sleep(0.8)
        print("Looking right …")
        bot.look_right()
        time.sleep(0.8)
        bot.look_ahead()

        # --- beep ---
        print("Beep!")
        bot.beep(duration_ms=150)

        # --- LEDs off, relax ---
        bot.leds_off()
        bot.relax()
        print("\nDone. Servos relaxed, LEDs off.")
        print(f"Final state: {bot.state.model_dump_json(indent=2)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <robot-ip>")
        sys.exit(1)
    main(host=sys.argv[1])
