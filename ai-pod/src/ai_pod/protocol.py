"""Wire protocol constants and frame encoding for the hexapod TCP interface.

The robot server expects newline-terminated, ``#``-separated commands over
TCP port 5002 and streams JPEG video on TCP port 8002.
"""

from __future__ import annotations

COMMAND_PORT = 5002
VIDEO_PORT = 8002

CMD_MOVE = "CMD_MOVE"
CMD_LED_MOD = "CMD_LED_MOD"
CMD_LED = "CMD_LED"
CMD_SONIC = "CMD_SONIC"
CMD_BUZZER = "CMD_BUZZER"
CMD_HEAD = "CMD_HEAD"
CMD_BALANCE = "CMD_BALANCE"
CMD_ATTITUDE = "CMD_ATTITUDE"
CMD_POSITION = "CMD_POSITION"
CMD_RELAX = "CMD_RELAX"
CMD_POWER = "CMD_POWER"
CMD_CALIBRATION = "CMD_CALIBRATION"
CMD_CAMERA = "CMD_CAMERA"
CMD_SERVOPOWER = "CMD_SERVOPOWER"


def encode_command(*parts: str | int | float) -> bytes:
    """Build a wire-format command from its parts.

    >>> encode_command("CMD_MOVE", 1, 10, 10, 8, 0)
    b'CMD_MOVE#1#10#10#8#0\\n'
    """
    return ("#".join(str(p) for p in parts) + "\n").encode("utf-8")


def parse_response(data: bytes) -> list[str]:
    """Decode a server response into its ``#``-separated fields."""
    return data.decode("utf-8").strip().split("#")
