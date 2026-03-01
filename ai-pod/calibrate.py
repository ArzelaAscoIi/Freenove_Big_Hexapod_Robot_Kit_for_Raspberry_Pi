"""Interactive leg calibration tool for the hexapod robot.

Each leg has 3 axes (x, y, z) as absolute coordinates fed into the
inverse kinematics. The default neutral stance is ``[140, 0, 0]`` per leg.
Small adjustments (±1) around those values tune each servo.

Run while the hexapod server is running:

    uv run python calibrate.py <robot-ip>

Leg layout (top view, front of robot facing up):

        Leg 1 (front-right)     Leg 6 (front-left)
        Leg 2 (mid-right)       Leg 5 (mid-left)
        Leg 3 (rear-right)      Leg 4 (rear-left)

Procedure:
  1. The robot will stand in its neutral pose.
  2. For each leg, nudge x/y/z with + or - until the leg is properly aligned.
  3. Save when all legs look correct.
"""

from __future__ import annotations

import pathlib
import sys
import time

from ai_pod import Robot

LEG_NAMES = ["one", "two", "three", "four", "five", "six"]
LEG_LABELS = [
    "Leg 1 (front-right)",
    "Leg 2 (mid-right)",
    "Leg 3 (rear-right)",
    "Leg 4 (rear-left)",
    "Leg 5 (mid-left)",
    "Leg 6 (front-left)",
]

POINT_FILE = (
    pathlib.Path(__file__).resolve().parents[1] / ".." / "Code" / "Server" / "point.txt"
)
DEFAULT_POSITION = [140, 0, 0]


def load_points(path: pathlib.Path) -> list[list[int]]:
    """Load current calibration from the server's ``point.txt``."""
    if not path.exists():
        return [list(DEFAULT_POSITION) for _ in range(6)]
    lines = path.read_text().strip().splitlines()
    return [list(map(int, line.strip().split("\t"))) for line in lines]


def print_offsets(positions: list[list[int]]) -> None:
    print("\n  Current calibration (absolute coordinates):")
    for label, vals in zip(LEG_LABELS, positions):
        dx = vals[0] - DEFAULT_POSITION[0]
        dy = vals[1] - DEFAULT_POSITION[1]
        dz = vals[2] - DEFAULT_POSITION[2]
        print(
            f"    {label}: x={vals[0]}  y={vals[1]}  z={vals[2]}"
            f"    (Δx={dx:+d}  Δy={dy:+d}  Δz={dz:+d})"
        )
    print()


def main(host: str) -> None:
    positions = load_points(POINT_FILE.resolve())
    print(f"Loaded calibration from {POINT_FILE.resolve()}")
    print_offsets(positions)

    print(f"Connecting to robot at {host} …")
    with Robot(host=host) as bot:
        print("Connected. Activating servos and entering calibration mode.\n")
        bot.activate()
        time.sleep(0.5)
        bot.enter_calibration()
        time.sleep(0.5)

        print("Commands:")
        print("  <leg> <axis> +        — nudge axis up by 1   (e.g. '3 x +')")
        print("  <leg> <axis> -        — nudge axis down by 1 (e.g. '3 x -')")
        print("  <leg> <axis> <value>  — set absolute offset from neutral")
        print("                          (e.g. '3 x 5' → sets x to 145)")
        print("  show                  — display current calibration")
        print("  reset                 — reset all legs to [140, 0, 0]")
        print("  save                  — save calibration to robot and exit")
        print("  quit                  — exit without saving")
        print()

        while True:
            try:
                raw = input("calibrate> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting without saving.")
                break

            if not raw:
                continue

            if raw == "quit":
                print("Exiting without saving.")
                break

            if raw == "show":
                print_offsets(positions)
                continue

            if raw == "reset":
                positions = [list(DEFAULT_POSITION) for _ in range(6)]
                for i in range(6):
                    bot.calibrate_leg(
                        leg=LEG_NAMES[i],
                        x=DEFAULT_POSITION[0],
                        y=DEFAULT_POSITION[1],
                        z=DEFAULT_POSITION[2],
                    )
                    time.sleep(0.1)
                print("All legs reset to neutral [140, 0, 0].")
                continue

            if raw == "save":
                print("Saving calibration …")
                bot.save_calibration()
                time.sleep(0.5)
                print("Calibration saved to robot.")
                print_offsets(positions)
                break

            parts = raw.split()
            if len(parts) == 3:
                try:
                    leg_num = int(parts[0])
                except ValueError:
                    print("  Invalid leg number. Example: '3 x +'")
                    continue

                if leg_num < 1 or leg_num > 6:
                    print("  Leg number must be 1-6.")
                    continue

                axis = parts[1]
                if axis not in ("x", "y", "z"):
                    print("  Axis must be x, y, or z.")
                    continue

                idx = leg_num - 1
                axis_idx = {"x": 0, "y": 1, "z": 2}[axis]

                val_str = parts[2]
                if val_str == "+":
                    positions[idx][axis_idx] += 1
                elif val_str == "-":
                    positions[idx][axis_idx] -= 1
                else:
                    try:
                        offset = int(val_str)
                    except ValueError:
                        print("  Invalid value. Use '+', '-', or a number.")
                        continue
                    positions[idx][axis_idx] = DEFAULT_POSITION[axis_idx] + offset

                bot.calibrate_leg(
                    leg=LEG_NAMES[idx],
                    x=positions[idx][0],
                    y=positions[idx][1],
                    z=positions[idx][2],
                )
                time.sleep(0.1)
                dx = positions[idx][0] - DEFAULT_POSITION[0]
                dy = positions[idx][1] - DEFAULT_POSITION[1]
                dz = positions[idx][2] - DEFAULT_POSITION[2]
                print(
                    f"  {LEG_LABELS[idx]}: x={positions[idx][0]}  y={positions[idx][1]}  z={positions[idx][2]}"
                    f"    (Δx={dx:+d}  Δy={dy:+d}  Δz={dz:+d})"
                )
                continue

            print("  Unknown command. Type 'show', 'save', 'quit', or '<leg> <axis> +/-/value'")

        bot.relax()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <robot-ip>")
        sys.exit(1)
    main(host=sys.argv[1])
