"""Go Direct force sensor wrapper. Bluetooth only for V1; no terminal prompts.

Scan and connect use GoDirect(use_ble=True) the same way the Pi Test B command
does. The gdx helper re-inits BLE from use_ble=False and finds nothing on Linux.
"""

from __future__ import annotations

import random
import time
from typing import List, Optional


class ForceSensorError(Exception):
    pass


def _device_name(device) -> str:
    return str(getattr(device, "name", None) or getattr(device, "_name", None) or device)


def _device_rssi(device):
    rssi = getattr(device, "rssi", None)
    if rssi is None:
        rssi = getattr(device, "_rssi", None)
    return rssi


class ForceSensor:
    def __init__(self, virtual: bool = False):
        self.VIRTUAL = virtual
        self.connected = False
        self.device_name = ""
        self.last_force_n: Optional[float] = None
        self.blank = 0.0
        self.last_error = ""
        self._godirect = None
        self._device = None
        self._sensors = []
        self._virtual_z = 0.0
        self._contact_z = -2.0

    def set_virtual_z(self, z: float) -> None:
        self._virtual_z = z if z is not None else 0.0

    def scan_ble(self) -> List[dict]:
        if self.VIRTUAL:
            return [{"name": "GDX-FOR VIRTUAL", "rssi": -40}]
        GoDirect = self._import_godirect()
        adapter = GoDirect(use_ble=True, use_usb=False)
        try:
            found = adapter.list_devices() or []
            devices = []
            for device in found:
                devices.append({"name": _device_name(device), "rssi": _device_rssi(device)})
            return devices
        except Exception as exc:
            self.last_error = str(exc)
            raise ForceSensorError(
                "Bluetooth scan failed. Turn the sensor on and close Graphical Analysis "
                "if it is open. On the Raspberry Pi run: sudo systemctl start bluetooth "
                "then bluetoothctl power on. Your user must be in the bluetooth group. "
                "If the list is still empty: rfkill unblock bluetooth and check hci0."
            ) from exc
        finally:
            self._quit_adapter(adapter)

    def connect(self, device_name: str, sensor_number: int = 1) -> str:
        self.device_name = device_name
        if self.VIRTUAL:
            self.connected = True
            self.last_force_n = 0.0
            self.last_error = ""
            return "virtual force sensor"
        if not device_name:
            raise ForceSensorError("Pick a Go Direct device from the scan list.")
        self.disconnect()
        GoDirect = self._import_godirect()
        adapter = GoDirect(use_ble=True, use_usb=False)
        try:
            found = adapter.list_devices() or []
            match = None
            names = []
            for device in found:
                name = _device_name(device)
                names.append(name)
                if name == device_name:
                    match = device
                    break
            if match is None:
                raise ForceSensorError(
                    f"Could not find {device_name}. Seen: {', '.join(names) or 'none'}. "
                    "Turn the sensor on, then Scan again."
                )
            if not match.open():
                raise ForceSensorError(
                    f"Could not open {device_name}. Close Graphical Analysis and Scan again."
                )
            match.enable_sensors(sensors=[sensor_number])
            self._sensors = match.get_enabled_sensors() or []
            match.start(period=200)
            self._godirect = adapter
            self._device = match
        except ForceSensorError:
            self._quit_adapter(adapter)
            raise
        except Exception as exc:
            self._quit_adapter(adapter)
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
        if self._device is not None:
            try:
                self._device.stop()
            except Exception:
                pass
            try:
                self._device.close()
            except Exception:
                pass
        self._quit_adapter(self._godirect)
        self._godirect = None
        self._device = None
        self._sensors = []
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
        if self._device is None:
            return None
        try:
            if not self._device.read():
                return self.last_force_n
            sensors = self._sensors or self._device.get_enabled_sensors() or []
            if not sensors:
                return self.last_force_n
            values = list(sensors[0].values or [])
            try:
                sensors[0].clear()
            except Exception:
                pass
            if not values:
                return self.last_force_n
            # gdx.read() returns the negated raw value; keep that sign for thresholds.
            val = -float(values[0])
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

    def _import_godirect(self):
        try:
            from godirect import GoDirect
        except ImportError as exc:
            raise ForceSensorError(
                "The godirect library is missing. In the project folder, with "
                "(.venv) active, run: pip install -r requirements.txt"
            ) from exc
        return GoDirect

    @staticmethod
    def _quit_adapter(adapter) -> None:
        if adapter is None:
            return
        for method in ("quit", "stop"):
            fn = getattr(adapter, method, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
                return
