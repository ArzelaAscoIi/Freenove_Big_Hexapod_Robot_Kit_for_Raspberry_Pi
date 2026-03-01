"""Domain models for the hexapod robot."""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class GaitType(IntEnum):
    """Locomotion gait pattern.

    Tripod is faster (3 legs move simultaneously), wave is more stable
    (one leg at a time).
    """

    TRIPOD = 1
    WAVE = 2


class LedMode(IntEnum):
    """Built-in LED animation modes."""

    OFF = 0
    STATIC = 1
    BREATH = 2
    RAINBOW = 3
    RAINBOW_CYCLE = 4
    THEATER_CHASE = 5


class HeadAxis(IntEnum):
    """Head servo axis selection."""

    VERTICAL = 0
    HORIZONTAL = 1


class ServoState(StrEnum):
    """Whether servos are energised or relaxed."""

    ACTIVE = "active"
    RELAXED = "relaxed"


class BalanceState(StrEnum):
    """IMU-based auto-balance mode."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class ConnectionState(StrEnum):
    """TCP connection lifecycle."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


class Color(BaseModel):
    """RGB colour value (0-255 per channel)."""

    r: Annotated[int, Field(ge=0, le=255)] = 0
    g: Annotated[int, Field(ge=0, le=255)] = 0
    b: Annotated[int, Field(ge=0, le=255)] = 0

    @classmethod
    def red(cls) -> Color:
        return cls(r=255, g=0, b=0)

    @classmethod
    def green(cls) -> Color:
        return cls(r=0, g=255, b=0)

    @classmethod
    def blue(cls) -> Color:
        return cls(r=0, g=0, b=255)

    @classmethod
    def white(cls) -> Color:
        return cls(r=255, g=255, b=255)

    @classmethod
    def off(cls) -> Color:
        return cls(r=0, g=0, b=0)


class Position(BaseModel):
    """Body position offset from neutral stance (in mm)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Attitude(BaseModel):
    """Body orientation angles (in degrees)."""

    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


class HeadPosition(BaseModel):
    """Head servo angles (in degrees, 0-180)."""

    vertical: Annotated[float, Field(ge=0, le=180)] = 90.0
    horizontal: Annotated[float, Field(ge=0, le=180)] = 90.0


class MovementVector(BaseModel):
    """Desired movement direction and speed.

    :param x: Left/right component (-35 to 35).
    :param y: Forward/backward component (-35 to 35).
    :param speed: Step speed (1-10, higher = faster).
    :param angle: Body rotation angle while walking (degrees).
    """

    x: Annotated[float, Field(ge=-35, le=35)] = 0.0
    y: Annotated[float, Field(ge=-35, le=35)] = 0.0
    speed: Annotated[int, Field(ge=1, le=10)] = 8
    angle: float = 0.0


class BatteryStatus(BaseModel):
    """Battery voltage readings from the two ADC channels."""

    voltage_1: float = 0.0
    voltage_2: float = 0.0

    @property
    def is_low(self) -> bool:
        """True when either cell is below 3.5 V (typical LiPo warning)."""
        return self.voltage_1 < 3.5 or self.voltage_2 < 3.5


class UltrasonicReading(BaseModel):
    """Single distance measurement from the ultrasonic sensor."""

    distance_cm: float = 0.0

    @property
    def has_obstacle(self) -> bool:
        """True if obstacle is closer than 30 cm."""
        return 0 < self.distance_cm < 30


class RobotState(BaseModel):
    """Aggregate snapshot of the robot's known state."""

    connection: ConnectionState = ConnectionState.DISCONNECTED
    servos: ServoState = ServoState.RELAXED
    balance: BalanceState = BalanceState.DISABLED
    gait: GaitType = GaitType.TRIPOD
    position: Position = Position()
    attitude: Attitude = Attitude()
    head: HeadPosition = HeadPosition()
    led_mode: LedMode = LedMode.OFF
    led_color: Color = Color()
    battery: BatteryStatus = BatteryStatus()
    last_distance: UltrasonicReading = UltrasonicReading()
