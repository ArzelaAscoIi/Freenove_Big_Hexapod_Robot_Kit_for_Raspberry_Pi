"""ai-pod: AI-friendly control interface for the Freenove Big Hexapod Robot."""

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
from ai_pod.robot import Robot

__all__ = [
    "Attitude",
    "BalanceState",
    "BatteryStatus",
    "Color",
    "ConnectionError",
    "ConnectionState",
    "GaitType",
    "HeadAxis",
    "HeadPosition",
    "LedMode",
    "MovementVector",
    "Position",
    "Robot",
    "RobotConnection",
    "RobotState",
    "ServoState",
    "UltrasonicReading",
]
