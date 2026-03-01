"""Low-level TCP transport for the hexapod robot server."""

from __future__ import annotations

import logging
import pathlib
import socket
import struct
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Self

from ai_pod.protocol import COMMAND_PORT, VIDEO_PORT, encode_command, parse_response

logger = logging.getLogger(__name__)

RECV_BUFFER = 1024
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"

SERVER_DIR = (
    pathlib.Path(__file__).resolve().parents[3] / "Code" / "Server"
)


class ConnectionError(Exception):
    """Raised when the robot is unreachable or the link drops."""


def _restart_server(server_dir: pathlib.Path) -> None:
    """Kill any running server and start a fresh one.

    The Freenove server has a bug where it never resets after a client
    disconnects (``is_tcp_active`` vs ``tcp_flag`` mismatch), so the only
    way to reconnect is to restart the process.
    """
    logger.info("Restarting hexapod server …")
    subprocess.run(
        ["sudo", "pkill", "-f", "python3 main.py"],
        check=False,
        capture_output=True,
    )
    time.sleep(2)
    subprocess.Popen(
        ["sudo", "python3", "main.py", "-t", "-n"],
        cwd=str(server_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    logger.info("Server restarted")


class RobotConnection:
    """Manages the two TCP sockets (command + video) to the hexapod server.

    Not intended for direct use — the :class:`~ai_pod.robot.Robot` class wraps
    this with a higher-level API.
    """

    def __init__(self, host: str, *, server_dir: pathlib.Path = SERVER_DIR) -> None:
        self._host = host
        self._server_dir = server_dir
        self._cmd_socket: socket.socket | None = None
        self._video_socket: socket.socket | None = None
        self._video_thread: threading.Thread | None = None
        self._stop_video = threading.Event()
        self._lock = threading.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def is_connected(self) -> bool:
        return self._cmd_socket is not None

    def connect(
        self,
        *,
        timeout: float = 5.0,
        retries: int = 3,
        retry_delay: float = 2.0,
        auto_restart: bool = True,
    ) -> Self:
        """Open the command socket to the robot server.

        If initial attempts fail and *auto_restart* is ``True``, the server
        process is killed and restarted automatically before a final round
        of retries.

        :param timeout: Socket connect/recv timeout in seconds.
        :param retries: Number of connection attempts per round.
        :param retry_delay: Base delay between retries in seconds.
        :param auto_restart: Restart the server process when retries are exhausted.
        :raises ConnectionError: If the robot is unreachable after all attempts.
        """
        if self._cmd_socket is not None:
            return self

        exc = self._try_connect(timeout=timeout, retries=retries, retry_delay=retry_delay)
        if exc is None:
            return self

        if not auto_restart:
            raise ConnectionError(
                f"Cannot reach robot at {self._host}:{COMMAND_PORT} after {retries} attempts"
            ) from exc

        logger.info("Connection failed, restarting server and retrying …")
        print("Server not responding — restarting …")
        _restart_server(self._server_dir)

        exc = self._try_connect(timeout=timeout, retries=retries, retry_delay=retry_delay)
        if exc is None:
            return self

        raise ConnectionError(
            f"Cannot reach robot at {self._host}:{COMMAND_PORT} even after server restart"
        ) from exc

    def _try_connect(
        self,
        *,
        timeout: float,
        retries: int,
        retry_delay: float,
    ) -> OSError | None:
        """Attempt to connect, returning the last exception or ``None`` on success."""
        delay = retry_delay
        last_exc: OSError | None = None

        for attempt in range(1, retries + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((self._host, COMMAND_PORT))
                self._cmd_socket = sock
                logger.info("Command channel connected to %s:%d", self._host, COMMAND_PORT)
                return None
            except OSError as exc:
                last_exc = exc
                sock.close()
                if attempt < retries:
                    logger.info(
                        "Connection attempt %d/%d failed, retrying in %.1fs …",
                        attempt,
                        retries,
                        delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * 1.5, 10.0)

        return last_exc

    def disconnect(self) -> None:
        """Close both sockets and stop the video thread."""
        self.stop_video_stream()
        if self._cmd_socket is not None:
            try:
                self._cmd_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._cmd_socket.close()
            self._cmd_socket = None
            logger.info("Disconnected from %s", self._host)

    def send(self, *parts: str | int | float) -> None:
        """Encode and send a command over the command socket.

        :raises ConnectionError: If not connected.
        """
        if self._cmd_socket is None:
            raise ConnectionError("Not connected")
        payload = encode_command(*parts)
        with self._lock:
            try:
                self._cmd_socket.sendall(payload)
            except OSError as exc:
                raise ConnectionError("Send failed") from exc

    def send_and_receive(self, *parts: str | int | float) -> list[str]:
        """Send a command and return the parsed response fields.

        :raises ConnectionError: If not connected or recv fails.
        """
        if self._cmd_socket is None:
            raise ConnectionError("Not connected")
        payload = encode_command(*parts)
        with self._lock:
            try:
                self._cmd_socket.sendall(payload)
                data = self._cmd_socket.recv(RECV_BUFFER)
                if not data:
                    raise ConnectionError("Connection closed by server")
                return parse_response(data)
            except OSError as exc:
                raise ConnectionError("Communication failed") from exc

    def start_video_stream(
        self,
        on_frame: Callable[[bytes], None],
        *,
        timeout: float = 5.0,
    ) -> None:
        """Connect the video socket and call *on_frame* with each JPEG buffer.

        Runs in a background daemon thread.

        :param on_frame: Called with raw JPEG bytes for every frame.
        :param timeout: Socket timeout in seconds.
        """
        if self._video_thread is not None:
            return

        self._stop_video.clear()

        def _reader() -> None:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((self._host, VIDEO_PORT))
                self._video_socket = sock
                logger.info("Video stream connected to %s:%d", self._host, VIDEO_PORT)

                while not self._stop_video.is_set():
                    length_bytes = self._recv_exact(sock, n=4)
                    if length_bytes is None:
                        break
                    frame_len = struct.unpack("<I", length_bytes)[0]
                    frame = self._recv_exact(sock, n=frame_len)
                    if frame is None:
                        break
                    if self._is_valid_jpeg(frame):
                        on_frame(frame)
            except OSError:
                logger.warning("Video stream disconnected")
            finally:
                if self._video_socket is not None:
                    self._video_socket.close()
                    self._video_socket = None

        self._video_thread = threading.Thread(target=_reader, daemon=True, name="video-stream")
        self._video_thread.start()

    def stop_video_stream(self) -> None:
        """Signal the video thread to stop and wait for it to finish."""
        self._stop_video.set()
        if self._video_socket is not None:
            try:
                self._video_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self._video_thread is not None:
            self._video_thread.join(timeout=3.0)
            self._video_thread = None

    @staticmethod
    def _recv_exact(sock: socket.socket, *, n: int) -> bytes | None:
        """Receive exactly *n* bytes or return ``None`` on disconnect."""
        buf = bytearray()
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    @staticmethod
    def _is_valid_jpeg(data: bytes) -> bool:
        return len(data) > 4 and data[:2] == JPEG_SOI and data[-2:] == JPEG_EOI

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()

    def __del__(self) -> None:
        self.disconnect()
