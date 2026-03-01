"""High-level control interface for the Freenove Big Hexapod Robot.

Usage::

    from ai_pod import Robot

    with Robot(host="192.168.1.42") as bot:
        bot.activate()
        bot.move_forward(speed=6)
        bot.stop()
        print(bot.battery)
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Self

from ai_pod.connection import ConnectionError, RobotConnection
from ai_pod.models import (
    Attitude,
    BalanceState,
    BatteryStatus,
    Color,
    ConnectionState,
    GaitType,
    HeadAxis,
    HeadPosition,
    LedMode,
    MovementVector,
    Position,
    RobotState,
    ServoState,
    UltrasonicReading,
)
from ai_pod.protocol import (
    CMD_ATTITUDE,
    CMD_BALANCE,
    CMD_BUZZER,
    CMD_CALIBRATION,
    CMD_HEAD,
    CMD_LED,
    CMD_LED_MOD,
    CMD_MOVE,
    CMD_POSITION,
    CMD_POWER,
    CMD_SERVOPOWER,
    CMD_SONIC,
)

logger = logging.getLogger(__name__)


class Robot:
    """AI-friendly facade for every capability of the hexapod.

    The robot communicates over TCP to the on-board server (``Code/Server``).
    All methods are synchronous, thread-safe, and update :attr:`state`
    automatically.

    :param host: IP address of the Raspberry Pi running the hexapod server.
    :param auto_connect: Connect immediately on construction.
    """

    def __init__(self, host: str, *, auto_connect: bool = False) -> None:
        self._conn = RobotConnection(host=host)
        self._state = RobotState()
        if auto_connect:
            self.connect()

    @property
    def state(self) -> RobotState:
        """Current snapshot — updated by every command."""
        return self._state.model_copy()

    @property
    def host(self) -> str:
        return self._conn.host

    @property
    def is_connected(self) -> bool:
        return self._conn.is_connected

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self, *, timeout: float = 5.0, auto_restart: bool = True) -> Self:
        """Open the command channel.

        If the server is unresponsive (e.g. stuck after a previous session),
        it will be automatically restarted when *auto_restart* is ``True``.

        :raises ConnectionError: If the robot is unreachable.
        """
        self._state.connection = ConnectionState.CONNECTING
        try:
            self._conn.connect(timeout=timeout, auto_restart=auto_restart)
            self._state.connection = ConnectionState.CONNECTED
            logger.info("Connected to robot at %s", self._conn.host)
        except ConnectionError:
            self._state.connection = ConnectionState.DISCONNECTED
            raise
        return self

    def disconnect(self) -> None:
        """Gracefully close all sockets."""
        self._conn.disconnect()
        self._state.connection = ConnectionState.DISCONNECTED

    # ------------------------------------------------------------------
    # Servo power
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """Energise servos so the robot can move."""
        self._conn.send(CMD_SERVOPOWER, 1)
        self._state.servos = ServoState.ACTIVE

    def relax(self) -> None:
        """Cut servo power — the robot will sag in place."""
        self._conn.send(CMD_SERVOPOWER, 0)
        self._state.servos = ServoState.RELAXED

    # ------------------------------------------------------------------
    # Locomotion
    # ------------------------------------------------------------------

    def set_gait(self, gait: GaitType) -> None:
        """Select the gait used by subsequent movement commands."""
        self._state.gait = gait

    def move(self, vector: MovementVector) -> None:
        """Execute a single movement step with the current gait.

        :param vector: Direction, speed, and body rotation.
        """
        self._conn.send(
            CMD_MOVE,
            int(self._state.gait),
            int(vector.x),
            int(vector.y),
            vector.speed,
            int(vector.angle),
        )

    def move_forward(self, *, speed: int = 8) -> None:
        self.move(MovementVector(x=0, y=35, speed=speed))

    def move_backward(self, *, speed: int = 8) -> None:
        self.move(MovementVector(x=0, y=-35, speed=speed))

    def move_left(self, *, speed: int = 8) -> None:
        self.move(MovementVector(x=-35, y=0, speed=speed))

    def move_right(self, *, speed: int = 8) -> None:
        self.move(MovementVector(x=35, y=0, speed=speed))

    def rotate_left(self, *, speed: int = 8, angle: float = -30) -> None:
        """Rotate the body counter-clockwise while walking in place."""
        self.move(MovementVector(x=0, y=0, speed=speed, angle=angle))

    def rotate_right(self, *, speed: int = 8, angle: float = 30) -> None:
        """Rotate the body clockwise while walking in place."""
        self.move(MovementVector(x=0, y=0, speed=speed, angle=angle))

    def walk_toward(self, *, angle_deg: float, speed: int = 8, magnitude: float = 35) -> None:
        """Walk in an arbitrary direction.

        :param angle_deg: 0 = forward, 90 = right, -90 = left, 180 = backward.
        :param magnitude: How far (0-35) to step each cycle.
        """
        rad = math.radians(angle_deg)
        x = magnitude * math.sin(rad)
        y = magnitude * math.cos(rad)
        self.move(MovementVector(x=x, y=y, speed=speed))

    def stop(self) -> None:
        """Send a zero-movement command (robot stands still)."""
        self.move(MovementVector(x=0, y=0, speed=1))

    # ------------------------------------------------------------------
    # Body pose
    # ------------------------------------------------------------------

    def set_position(self, position: Position) -> None:
        """Shift the body centre relative to neutral stance."""
        self._conn.send(CMD_POSITION, int(position.x), int(position.y), int(position.z))
        self._state.position = position

    def set_attitude(self, attitude: Attitude) -> None:
        """Tilt/rotate the body around its centre."""
        self._conn.send(CMD_ATTITUDE, int(attitude.roll), int(attitude.pitch), int(attitude.yaw))
        self._state.attitude = attitude

    def set_height(self, z: float) -> None:
        """Convenience — change body height only."""
        self.set_position(Position(x=self._state.position.x, y=self._state.position.y, z=z))

    def reset_pose(self) -> None:
        """Return body to neutral position and attitude."""
        self.set_position(Position())
        self.set_attitude(Attitude())

    # ------------------------------------------------------------------
    # Head (pan/tilt)
    # ------------------------------------------------------------------

    def set_head(self, head: HeadPosition) -> None:
        """Point the head camera/sensor platform."""
        self._conn.send(CMD_HEAD, int(HeadAxis.VERTICAL), int(head.vertical))
        self._conn.send(CMD_HEAD, int(HeadAxis.HORIZONTAL), int(head.horizontal))
        self._state.head = head

    def look_ahead(self) -> None:
        self.set_head(HeadPosition(vertical=90, horizontal=90))

    def look_up(self) -> None:
        self.set_head(HeadPosition(vertical=60, horizontal=self._state.head.horizontal))

    def look_down(self) -> None:
        self.set_head(HeadPosition(vertical=120, horizontal=self._state.head.horizontal))

    def look_left(self) -> None:
        self.set_head(HeadPosition(vertical=self._state.head.vertical, horizontal=60))

    def look_right(self) -> None:
        self.set_head(HeadPosition(vertical=self._state.head.vertical, horizontal=120))

    # ------------------------------------------------------------------
    # LEDs
    # ------------------------------------------------------------------

    def set_led_color(self, color: Color) -> None:
        """Set all LEDs to a single static colour."""
        self._conn.send(CMD_LED, color.r, color.g, color.b)
        self._state.led_color = color
        self._state.led_mode = LedMode.STATIC

    def set_led_mode(self, mode: LedMode) -> None:
        """Switch to a built-in LED animation."""
        self._conn.send(CMD_LED_MOD, int(mode))
        self._state.led_mode = mode

    def leds_off(self) -> None:
        self.set_led_mode(LedMode.OFF)

    # ------------------------------------------------------------------
    # Buzzer
    # ------------------------------------------------------------------

    def buzzer_on(self) -> None:
        self._conn.send(CMD_BUZZER, 1)

    def buzzer_off(self) -> None:
        self._conn.send(CMD_BUZZER, 0)

    def beep(self, *, duration_ms: int = 200) -> None:
        """Short blocking beep.

        :param duration_ms: Beep length in milliseconds (approximate).
        """
        import time

        self.buzzer_on()
        time.sleep(duration_ms / 1000)
        self.buzzer_off()

    # ------------------------------------------------------------------
    # Balance
    # ------------------------------------------------------------------

    def enable_balance(self) -> None:
        """Turn on IMU-based self-balancing."""
        self._conn.send(CMD_BALANCE, 1)
        self._state.balance = BalanceState.ENABLED

    def disable_balance(self) -> None:
        self._conn.send(CMD_BALANCE, 0)
        self._state.balance = BalanceState.DISABLED

    # ------------------------------------------------------------------
    # Sensors
    # ------------------------------------------------------------------

    def read_distance(self) -> UltrasonicReading:
        """Query the ultrasonic sensor (blocking).

        :returns: Distance reading in centimetres.
        """
        fields = self._conn.send_and_receive(CMD_SONIC)
        distance = 0.0
        if len(fields) >= 2:
            try:
                distance = float(fields[1])
            except (ValueError, IndexError):
                pass
        reading = UltrasonicReading(distance_cm=distance)
        self._state.last_distance = reading
        return reading

    def read_battery(self) -> BatteryStatus:
        """Query battery voltages (blocking).

        :returns: Voltage of each cell/bank.
        """
        fields = self._conn.send_and_receive(CMD_POWER)
        v1 = v2 = 0.0
        if len(fields) >= 3:
            try:
                v1 = float(fields[1])
                v2 = float(fields[2])
            except (ValueError, IndexError):
                pass
        status = BatteryStatus(voltage_1=v1, voltage_2=v2)
        self._state.battery = status
        return status

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def enter_calibration(self) -> None:
        """Put the robot into calibration mode."""
        self._conn.send(CMD_CALIBRATION)

    def calibrate_leg(self, *, leg: str, x: int, y: int, z: int) -> None:
        """Adjust a single leg's calibration offset.

        :param leg: Leg identifier (e.g. ``"one"``, ``"two"`` … ``"six"``).
        """
        self._conn.send(CMD_CALIBRATION, leg, x, y, z)

    def save_calibration(self) -> None:
        """Persist calibration to disk on the robot."""
        self._conn.send(CMD_CALIBRATION, "save")

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------

    def start_video(self, on_frame: Callable[[bytes], None], *, timeout: float = 5.0) -> None:
        """Begin receiving JPEG video frames in a background thread.

        :param on_frame: Callback invoked with raw JPEG bytes per frame.
        """
        self._conn.start_video_stream(on_frame=on_frame, timeout=timeout)

    def stop_video(self) -> None:
        """Stop the video stream and its background thread."""
        self._conn.stop_video_stream()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        return (
            f"Robot(host={self._conn.host!r}, "
            f"connected={self.is_connected}, "
            f"servos={self._state.servos.value})"
        )
