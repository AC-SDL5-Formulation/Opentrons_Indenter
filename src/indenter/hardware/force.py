"""Go Direct force sensor wrapper. Bluetooth only for V1; no terminal prompts."""

from __future__ import annotations

import random
import sys
import time
from typing import List, Optional

from indenter.paths import GDX_DIR


class ForceSensorError(Exception):
    pass


class ForceSensor:
    def __init__(self, virtual: bool = False):
        self.VIRTUAL = virtual
        self.connected = False
        self.device_name = ""
        self.last_force_n: Optional[float] = None
        self.blank = 0.0
        self.last_error = ""
        self._gdx = None
        self._virtual_z = 0.0
        self._contact_z = -2.0

    def set_virtual_z(self, z: float) -> None:
        self._virtual_z = z if z is not None else 0.0

    def scan_ble(self) -> List[dict]:
        if self.VIRTUAL:
            return [{"name": "GDX-FOR VIRTUAL", "rssi": -40}]
        gdx_mod = self._import_gdx()
        inst = gdx_mod.gdx()
        try:
            inst.godirect.__init__(use_ble=True, use_ble_bg=False, use_usb=False)
            found, n = inst.find_devices()
            devices = []
            if n and found:
                for d in found:
                    name = str(getattr(d, "name", d))
                    rssi = getattr(d, "rssi", None)
                    if rssi is None:
                        rssi = getattr(d, "_rssi", None)
                    devices.append({"name": name, "rssi": rssi})
            try:
                inst.close()
            except Exception:
                pass
            try:
                inst.godirect.stop()
            except Exception:
                pass
            return devices
        except Exception as exc:
            self.last_error = str(exc)
            raise ForceSensorError(
                "Bluetooth scan failed. Turn the sensor on, confirm Mac Bluetooth "
                "is on, and allow Python Bluetooth access in System Settings → Privacy."
            ) from exc

    def connect(self, device_name: str, sensor_number: int = 1) -> str:
        self.device_name = device_name
        if self.VIRTUAL:
            self.connected = True
            self.last_force_n = 0.0
            self.last_error = ""
            return "virtual force sensor"
        if not device_name:
            raise ForceSensorError("Pick a Go Direct device from the scan list.")
        gdx_mod = self._import_gdx()
        if self._gdx is not None:
            try:
                self._gdx.close()
            except Exception:
                pass
        self._gdx = gdx_mod.gdx()
        try:
            self._gdx.open(connection="ble", device_to_open=device_name)
            self._gdx.select_sensors([sensor_number])
            self._gdx.start(period=200)
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)
            raise ForceSensorError(
                f"Could not open {device_name}. Make sure Graphical Analysis is closed "
                "and the sensor is on, then Scan again."
            ) from exc
        sample = self.read_raw()
        if sample is None:
            raise ForceSensorError(
                "Connected but no force reading yet. Wait a second and click Zero."
            )
        self.connected = True
        self.last_force_n = sample
        self.last_error = ""
        return f"reading {sample:.4f} N"

    def disconnect(self) -> None:
        if self._gdx is not None:
            try:
                self._gdx.stop()
            except Exception:
                pass
            try:
                self._gdx.close()
            except Exception:
                pass
        self._gdx = None
        if not self.VIRTUAL:
            self.connected = False
            self.last_force_n = None

    def read_raw(self) -> Optional[float]:
        if self.VIRTUAL:
            depth = self._contact_z - (self._virtual_z or 0.0)
            if depth <= 0:
                val = 0.005 + random.random() * 0.01
            else:
                val = 0.02 + depth * 0.85 + random.random() * 0.01
            self.last_force_n = val
            return val
        if self._gdx is None:
            return None
        measurements = self._gdx.read()
        if not measurements:
            return self.last_force_n
        try:
            val = float(measurements[0])
        except (TypeError, ValueError, IndexError):
            return self.last_force_n
        self.last_force_n = val
        return val

    def read_stable(self, n: int = 8) -> float:
        val = 0.0
        last = 0.0
        for q in range(n):
            sample = self.read_raw()
            if sample is None:
                sample = 0.0
            last = sample
            if q > 6:
                val = sample - self.blank
        if n < 8:
            val = last - self.blank
        return val

    def zero(self) -> float:
        total = 0.0
        count = 0
        for _ in range(8):
            sample = self.read_raw()
            if sample is not None:
                total += sample
                count += 1
            time.sleep(0.05)
        self.blank = (total / count) if count else 0.0
        return self.blank

    def _import_gdx(self):
        root = str(GDX_DIR)
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            from gdx import gdx as gdx_mod
        except ImportError as exc:
            raise ForceSensorError(
                "The godirect / gdx library is missing. From the repo folder run: "
                "pip install -r requirements.txt"
            ) from exc
        return gdx_mod
