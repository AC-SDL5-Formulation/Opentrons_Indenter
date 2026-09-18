"""Sainsmart Genmitsu 3018 ProVer V2 driver for the indenter.

Bounds and default serial port stay specific to this mill. Abort / idle-wait /
Alarm-Hold handling is borrowed from the viscometry CNC class, not imported.
"""

from __future__ import annotations

import math
import time
from typing import Callable, List, Optional

import serial
from serial.tools import list_ports
import yaml

from indenter.paths import LOCATION_YAML


class CNCMotionError(Exception):
    """Raised when CNC motion fails (bounds, timeout, alarm, hold)."""


class CNC_Machine:
    BAUD_RATE = 115200
    DEFAULT_PORT = "/dev/tty.usbserial-1110"
    X_LOW_BOUND = 0
    X_HIGH_BOUND = 290
    Y_LOW_BOUND = 0
    Y_HIGH_BOUND = 180
    Z_LOW_BOUND = -40
    Z_HIGH_BOUND = 0

    IDLE_TIMEOUT_S = 120.0
    STATUS_POLL_INTERVAL_S = 0.1

    def __init__(
        self,
        virtual: bool = True,
        port: Optional[str] = None,
        location_file=None,
        idle_timeout_s: Optional[float] = None,
    ):
        self.VIRTUAL = virtual
        self.SERIAL_PORT = port or self.DEFAULT_PORT
        self.LOCATION_FILE = location_file or LOCATION_YAML
        self.LOCATIONS = self._load_locations()
        self.idle_timeout_s = idle_timeout_s if idle_timeout_s is not None else self.IDLE_TIMEOUT_S
        self.should_abort: Optional[Callable[[], bool]] = None
        self._ser: Optional[serial.Serial] = None
        self.connected = False
        self.last_status = "not connected"
        self.x: Optional[float] = None
        self.y: Optional[float] = None
        self.z: Optional[float] = None
        self.homed = False

    def _load_locations(self):
        path = self.LOCATION_FILE
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        return data

    @staticmethod
    def list_ports() -> List[dict]:
        ports = []
        for p in list_ports.comports():
            ports.append(
                {
                    "device": p.device,
                    "description": p.description or "",
                    "hwid": getattr(p, "hwid", "") or "",
                }
            )
        return ports

    def connect(self, port: Optional[str] = None) -> str:
        if port:
            self.SERIAL_PORT = port
        if self.VIRTUAL:
            self.connected = True
            self.last_status = "Idle (virtual)"
            self.x = self.y = self.z = 0.0
            return self.last_status
        self.disconnect()
        try:
            self._ser = serial.Serial(self.SERIAL_PORT, self.BAUD_RATE, timeout=2.0)
        except serial.SerialException as exc:
            self.connected = False
            self.last_status = f"port failed: {exc}"
            raise CNCMotionError(
                f"Could not open CNC port {self.SERIAL_PORT}. "
                "Unplug/replug the USB cable, then Find ports again."
            ) from exc
        self._wake(self._ser)
        self.connected = True
        status = self.ping()
        return status

    def disconnect(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        if not self.VIRTUAL:
            self.connected = False
            self.last_status = "not connected"

    def _wake(self, ser: serial.Serial) -> None:
        ser.write(b"\r\n\r\n")
        time.sleep(1)
        ser.reset_input_buffer()

    def ping(self) -> str:
        if self.VIRTUAL:
            self.connected = True
            self.last_status = "Idle (virtual)"
            return self.last_status
        if self._ser is None or not self._ser.is_open:
            self.connected = False
            self.last_status = "not connected"
            return self.last_status
        try:
            self._ser.reset_input_buffer()
            self._ser.write(b"?\n")
            line = self._ser.readline().decode(errors="ignore").strip()
            if not line:
                line = self._ser.readline().decode(errors="ignore").strip()
            self.last_status = line or "no reply"
            if "Alarm" in line:
                self.connected = True
                raise CNCMotionError(f"GRBL alarm: {line}")
            if "Hold" in line:
                self.connected = True
                raise CNCMotionError(f"GRBL hold: {line}")
            if "Idle" in line or "Run" in line or line.startswith("<"):
                self.connected = True
                self._parse_position(line)
            else:
                self.connected = True
            return self.last_status
        except CNCMotionError:
            raise
        except Exception as exc:
            self.connected = False
            self.last_status = f"ping failed: {exc}"
            return self.last_status

    def _parse_position(self, line: str) -> None:
        for key in ("WPos:", "MPos:"):
            if key not in line:
                continue
            try:
                chunk = line.split(key, 1)[1].split("|", 1)[0]
                parts = chunk.split(",")
                if len(parts) >= 3:
                    self.x, self.y, self.z = (float(parts[0]), float(parts[1]), float(parts[2]))
            except (ValueError, IndexError):
                return
            return

    def idle_ok(self) -> bool:
        if self.VIRTUAL:
            return True
        try:
            status = self.ping()
        except CNCMotionError:
            return False
        return "Idle" in status

    def _wait_idle(self, allow_abort: bool = True) -> None:
        if self.VIRTUAL:
            if allow_abort and self.should_abort and self.should_abort():
                raise KeyboardInterrupt("Stop requested during CNC wait")
            time.sleep(0.05)
            return
        ser = self._ser
        if ser is None:
            raise CNCMotionError("CNC is not connected")
        deadline = time.time() + self.idle_timeout_s
        while True:
            if allow_abort and self.should_abort and self.should_abort():
                raise KeyboardInterrupt("Stop requested during CNC wait")
            if time.time() > deadline:
                raise CNCMotionError(
                    f"Timed out waiting for CNC idle after {self.idle_timeout_s:.0f}s"
                )
            ser.reset_input_buffer()
            ser.write(b"?\n")
            line = ser.readline().decode(errors="ignore").strip()
            self.last_status = line or self.last_status
            if "Alarm" in line:
                raise CNCMotionError(f"GRBL alarm: {line}")
            if "Hold" in line:
                raise CNCMotionError(f"GRBL hold: {line}")
            if "Idle" in line:
                self._parse_position(line)
                break
            time.sleep(self.STATUS_POLL_INTERVAL_S)

    def _within(self, x, y, z) -> bool:
        xb = (x is None) or (self.X_LOW_BOUND <= x <= self.X_HIGH_BOUND)
        yb = (y is None) or (self.Y_LOW_BOUND <= y <= self.Y_HIGH_BOUND)
        zb = (z is None) or (self.Z_LOW_BOUND <= z <= self.Z_HIGH_BOUND)
        return xb and yb and zb

    def _check_bounds(self, x, y, z) -> None:
        if not self._within(x, y, z):
            raise CNCMotionError(
                f"Out of bounds: ({x}, {y}, {z}). "
                f"Allowed X {self.X_LOW_BOUND}–{self.X_HIGH_BOUND}, "
                f"Y {self.Y_LOW_BOUND}–{self.Y_HIGH_BOUND}, "
                f"Z {self.Z_LOW_BOUND}–{self.Z_HIGH_BOUND}."
            )

    def _gcode_to(self, x=None, y=None, z=None, speed=3000, gtype="G1") -> str:
        s = gtype
        if x is not None:
            s += f" X{x}"
        if y is not None:
            s += f" Y{y}"
        if z is not None:
            s += f" Z{z}"
        if speed is not None:
            s += f" F{speed}"
        return s + "\n"

    def follow_gcode_path(
        self, gcode: str, buffer: int = 20, allow_abort: bool = True
    ) -> List[str]:
        cmds = [c for c in gcode.splitlines() if c.strip()]
        if self.VIRTUAL:
            print("VIRTUAL GCODE:\n" + gcode.strip())
            return ["ok"]
        if self._ser is None or not self._ser.is_open:
            raise CNCMotionError("CNC is not connected")
        outs = []
        ser = self._ser
        for i in range(0, len(cmds), buffer):
            chunk = "\n".join(cmds[i : i + buffer]) + "\n"
            ser.write(chunk.encode())
            self._wait_idle(allow_abort=allow_abort)
            out = ser.readline().decode(errors="ignore").strip()
            outs.append(out)
        return outs

    def move_to_point(
        self, x=None, y=None, z=None, speed=3000, gtype="G1", allow_abort: bool = True
    ):
        self._check_bounds(x, y, z)
        g = self._gcode_to(x, y, z, speed, gtype)
        self.follow_gcode_path(g, allow_abort=allow_abort)
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if z is not None:
            self.z = z

    def move_to_point_safe(
        self, x, y, z, speed=3000, gtype="G1", allow_abort: bool = True
    ):
        self._check_bounds(x, y, z)
        g = ""
        g += self._gcode_to(z=self.Z_HIGH_BOUND, speed=speed, gtype=gtype)
        g += self._gcode_to(x=x, y=y, z=self.Z_HIGH_BOUND, speed=speed, gtype=gtype)
        g += self._gcode_to(z=z, speed=speed, gtype=gtype)
        self.follow_gcode_path(g, allow_abort=allow_abort)
        self.x, self.y, self.z = x, y, z

    def retract_z(self, z_safe: float = 0, speed: int = 3000, allow_abort: bool = False) -> None:
        """Raise Z at the current XY. Abort is ignored so Stop can always lift the probe."""
        z_safe = min(self.Z_HIGH_BOUND, max(self.Z_LOW_BOUND, z_safe))
        self._check_bounds(self.x, self.y, z_safe)
        g = self._gcode_to(z=z_safe, speed=speed, gtype="G1")
        self.follow_gcode_path(g, allow_abort=allow_abort)
        self.z = z_safe

    def home(self, allow_abort: bool = True):
        print("Returning CNC to origin")
        self.move_to_point_safe(0, 0, 0, gtype="G0", allow_abort=allow_abort)
        self.homed = True

    def jog(self, dx=0.0, dy=0.0, dz=0.0, speed=500):
        if self.x is None or self.y is None or self.z is None:
            raise CNCMotionError("Home the CNC once before jogging so position is known.")
        nx = self.x + dx
        ny = self.y + dy
        nz = self.z + dz
        self.move_to_point(nx, ny, nz, speed=speed)

    def get_location_position(self, location_name, location_index):
        loc = self.LOCATIONS[location_name]
        x = loc["x_origin"]
        y = loc["y_origin"]
        z = loc["z_origin"]
        if location_index > 0:
            num_x = loc.get("num_x", 1)
            x_offset = loc.get("x_offset", 0)
            y_offset = loc.get("y_offset", 0)
            x = x + (location_index % num_x) * x_offset
            y = y + math.floor(location_index / num_x) * y_offset
        return x, y, z

    def move_to_location(
        self, location_name, location_index, safe=True, speed=3000, allow_abort: bool = True
    ):
        print(f"Moving to location: {location_name} at index {location_index}")
        x, y, z = self.get_location_position(location_name, location_index)
        if safe:
            self.move_to_point_safe(x, y, z, speed=speed, allow_abort=allow_abort)
        else:
            self.move_to_point(x, y, z, speed=speed, allow_abort=allow_abort)

    def layout(self, location_name: str = "main_rack_A") -> dict:
        loc = self.LOCATIONS.get(location_name) or {}
        num_x = int(loc.get("num_x", 6))
        num_y = int(loc.get("num_y", 8))
        wells = []
        for idx in range(num_x * num_y):
            x, y, z = self.get_location_position(location_name, idx)
            wells.append(
                {
                    "index": idx,
                    "col": idx % num_x,
                    "row": idx // num_x,
                    "x": x,
                    "y": y,
                    "z": z,
                }
            )
        return {
            "name": location_name,
            "num_x": num_x,
            "num_y": num_y,
            "wells": wells,
            "bounds": {
                "x": [self.X_LOW_BOUND, self.X_HIGH_BOUND],
                "y": [self.Y_LOW_BOUND, self.Y_HIGH_BOUND],
                "z": [self.Z_LOW_BOUND, self.Z_HIGH_BOUND],
            },
        }

    def position(self) -> dict:
        return {"x": self.x, "y": self.y, "z": self.z, "homed": self.homed}
