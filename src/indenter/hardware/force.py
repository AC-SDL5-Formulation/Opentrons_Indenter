"""Go Direct force sensor wrapper. Bluetooth only for V1; no terminal prompts.

Scan and connect use GoDirect(use_ble=True) the same way the Pi Test B command
does. Flask serves each request on a worker thread; bleak needs an asyncio loop
on that thread, so all BLE work is serialized onto one dedicated thread.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import random
import threading
import time
from typing import List, Optional

log = logging.getLogger(__name__)


class ForceSensorError(Exception):
    pass


def _device_name(device) -> str:
    return str(getattr(device, "name", None) or getattr(device, "_name", None) or device)


def _device_rssi(device):
    rssi = getattr(device, "rssi", None)
    if rssi is None:
        rssi = getattr(device, "_rssi", None)
    return rssi


def _ensure_event_loop():
    """Create an asyncio loop on this thread if bleak/godirect would not find one."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


class _BleExecutor:
    """Run GoDirect calls on one thread that owns the BLE event loop."""

    def __init__(self):
        self._jobs: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._loop, name="gdx-ble", daemon=True)
        self._started = False
        self._guard = threading.Lock()
        self.allow_pump = False

    def _loop(self) -> None:
        loop = _ensure_event_loop()
        while True:
            try:
                job = self._jobs.get(timeout=0.05)
            except queue.Empty:
                # Only pump after the sensor is open. Pumping during open()
                # steals the status packet and godirect raises struct.error.
                if self.allow_pump:
                    try:
                        if not loop.is_closed():
                            loop.run_until_complete(asyncio.sleep(0.02))
                    except Exception:
                        pass
                continue
            if job is None:
                return
            fn, args, kwargs, reply = job
            try:
                reply.put((True, fn(*args, **kwargs)))
            except Exception as exc:
                reply.put((False, exc))

    def submit(self, fn, *args, **kwargs):
        if threading.current_thread() is self._thread:
            return fn(*args, **kwargs)
        with self._guard:
            if not self._started:
                self._thread.start()
                self._started = True
        reply: queue.Queue = queue.Queue()
        self._jobs.put((fn, args, kwargs, reply))
        ok, payload = reply.get()
        if not ok:
            raise payload
        return payload


_ble = _BleExecutor()


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
        self._miss_count = 0
        self._last_miss_log = 0.0
        self._last_printed_n: Optional[float] = None
        self._ok_count = 0

    def set_virtual_z(self, z: float) -> None:
        self._virtual_z = z if z is not None else 0.0

    def scan_ble(self) -> List[dict]:
        if self.VIRTUAL:
            return [{"name": "GDX-FOR VIRTUAL", "rssi": -40}]
        return _ble.submit(self._scan_ble_locked)

    def _scan_ble_locked(self) -> List[dict]:
        _ble.allow_pump = False
        GoDirect = self._import_godirect()
        _ensure_event_loop()
        adapter = GoDirect(use_ble=True, use_usb=False)
        try:
            found = adapter.list_devices() or []
            devices = []
            for device in found:
                devices.append({"name": _device_name(device), "rssi": _device_rssi(device)})
            return devices
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            log.exception("Bluetooth scan failed")
            raise ForceSensorError(
                f"Bluetooth scan failed ({type(exc).__name__}: {exc}). "
                "Turn the sensor on and close Graphical Analysis if it is open."
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
        return _ble.submit(self._connect_locked, device_name, sensor_number)

    def _connect_locked(self, device_name: str, sensor_number: int) -> str:
        _ble.allow_pump = False
        self.disconnect()
        GoDirect = self._import_godirect()
        _ensure_event_loop()
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
            opened = False
            last_exc = None
            for attempt in range(3):
                try:
                    opened = bool(match.open())
                    if opened:
                        break
                except Exception as exc:
                    last_exc = exc
                    try:
                        match.close()
                    except Exception:
                        pass
                    time.sleep(0.5)
            if not opened:
                raise ForceSensorError(
                    f"Could not open {device_name}"
                    + (f" ({type(last_exc).__name__}: {last_exc})" if last_exc else "")
                    + ". Close Graphical Analysis, power-cycle the sensor, then Scan again."
                ) from last_exc
            match.enable_sensors(sensors=[sensor_number])
            match.start(period=200)
            time.sleep(0.3)
            self._sensors = match.get_enabled_sensors() or []
            self._godirect = adapter
            self._device = match
            _ble.allow_pump = True
        except ForceSensorError:
            _ble.allow_pump = False
            self._quit_adapter(adapter)
            raise
        except Exception as exc:
            _ble.allow_pump = False
            self._quit_adapter(adapter)
            self.connected = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            log.exception("Force sensor connect failed")
            raise ForceSensorError(
                f"Could not open {device_name} ({type(exc).__name__}: {exc}). "
                "Close Graphical Analysis, turn the sensor on, then Scan again."
            ) from exc
        sample = None
        for _ in range(8):
            sample = self.read_raw()
            if sample is not None:
                break
            time.sleep(0.15)
        if sample is None:
            raise ForceSensorError(
                "Connected but no force reading yet. Wait a second and click Zero."
            )
        self.connected = True
        self.last_force_n = sample
        self.last_error = ""
        return f"reading {sample:.4f} N"

    def disconnect(self) -> None:
        if threading.current_thread() is _ble._thread:
            self._disconnect_locked()
            return
        if self.VIRTUAL:
            self._disconnect_locked()
            return
        try:
            _ble.submit(self._disconnect_locked)
        except Exception:
            self._disconnect_locked()

    def _disconnect_locked(self) -> None:
        _ble.allow_pump = False
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
            return self._read_virtual()
        if self._device is None:
            return None
        if threading.current_thread() is _ble._thread:
            return self._read_raw_locked()
        return _ble.submit(self._read_raw_locked)

    def _read_virtual(self) -> float:
        depth = self._contact_z - (self._virtual_z or 0.0)
        if depth <= 0:
            val = 0.005 + random.random() * 0.01
        else:
            val = 0.02 + depth * 0.85 + random.random() * 0.01
        self.last_force_n = val
        return val

    def _read_raw_locked(self) -> Optional[float]:
        if self._device is None:
            return None
        try:
            if not self._device.read():
                self._note_read_miss("device.read() returned False")
                return self.last_force_n
            sensors = self._device.get_enabled_sensors() or self._sensors or []
            self._sensors = sensors
            val = self._value_from_sensors(sensors)
            if val is None:
                self._note_read_miss("no sensor values")
                return self.last_force_n
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            print(f"[force] read error: {self.last_error}", flush=True)
            log.exception("Force read failed")
            return self.last_force_n
        self.last_force_n = val
        self.last_error = ""
        self._note_read_ok(val)
        return val

    def _value_from_sensors(self, sensors) -> Optional[float]:
        preferred = []
        others = []
        for sensor in sensors:
            desc = str(getattr(sensor, "sensor_description", "") or "")
            values = list(getattr(sensor, "values", None) or [])
            try:
                sensor.clear()
            except Exception:
                pass
            if not values:
                continue
            # gdx.read() returns the negated raw value; keep that sign for thresholds.
            sample = -float(values[-1])
            if "force" in desc.lower():
                preferred.append(sample)
            else:
                others.append(sample)
        if preferred:
            return preferred[0]
        if others:
            return others[0]
        return None

    def _note_read_miss(self, reason: str) -> None:
        self._miss_count += 1
        now = time.monotonic()
        if now - self._last_miss_log >= 5:
            print(f"[force] {reason} (x{self._miss_count})", flush=True)
            self._last_miss_log = now
            self._miss_count = 0

    def _note_read_ok(self, val: float) -> None:
        self._ok_count += 1
        prev = self._last_printed_n
        jumped = prev is None or abs(val - prev) >= 0.01
        if jumped or self._ok_count % 20 == 0:
            print(f"[force] {val:.4f} N", flush=True)
            self._last_printed_n = val

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
