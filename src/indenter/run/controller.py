"""Indent / relaxation run loop driven by RunSettings (no commented-out branches)."""

from __future__ import annotations

import csv
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from indenter.hardware.cnc import CNCMotionError, CNC_Machine
from indenter.hardware.force import ForceSensor
from indenter.paths import RESULTS_DIR
from indenter.run.settings import RunSettings
from indenter.run.stress import stress_mpa

EmitFn = Callable[[str, Dict[str, Any]], None]


class IndentController:
    def __init__(self, cnc: CNC_Machine, force: ForceSensor, emit: Optional[EmitFn] = None):
        self.cnc = cnc
        self.force = force
        self._emit = emit or (lambda _event, _payload: None)
        self._abort = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.running = False
        self.stopping = False
        self.current_well: Optional[int] = None
        self.current_step = "Idle"
        self.results: List[Dict[str, Any]] = []
        self.last_csv = ""
        self.error = ""
        self.cnc.should_abort = self._abort.is_set

    def request_stop(self) -> None:
        self.stopping = True
        self._abort.set()

    def start(self, settings: RunSettings) -> None:
        if self.running:
            raise RuntimeError("A run is already in progress")
        self._abort.clear()
        self.stopping = False
        self.error = ""
        self.results = []
        self.last_csv = ""
        self._thread = threading.Thread(
            target=self._run, args=(settings,), daemon=True, name="indent-run"
        )
        self._thread.start()

    def _emit_step(self, step: str, extra: Optional[dict] = None) -> None:
        self.current_step = step
        payload = {"step": step, "well": self.current_well}
        if extra:
            payload.update(extra)
        self._emit("step", payload)

    def _read_force(self) -> float:
        if self.cnc.z is not None:
            self.force.set_virtual_z(self.cnc.z)
        return self.force.read_stable()

    def _safe_stop_motion(self, settings: RunSettings) -> None:
        try:
            self._emit_step("Retract")
            self.cnc.retract_z(z_safe=self.cnc.Z_HIGH_BOUND, allow_abort=False)
        except Exception as exc:
            self._emit("log", {"message": f"Retract failed: {exc}"})
        if settings.home_at_end or self.stopping:
            try:
                self._emit_step("Home")
                self.cnc.home(allow_abort=False)
            except Exception as exc:
                self._emit("log", {"message": f"Home failed: {exc}"})

    def _run(self, settings: RunSettings) -> None:
        self.running = True
        self.cnc.VIRTUAL = settings.virtual
        self.force.VIRTUAL = settings.virtual
        self.cnc.should_abort = self._abort.is_set
        well_states = {int(w): "pending" for w in settings.wells}
        self._emit("run_started", {"wells": list(well_states.keys()), "mode": settings.mode})
        try:
            self._emit_step("Zero force")
            self.force.zero()
            blanked = self._read_force()
            self._emit("force", {"force_n": blanked, "blank": self.force.blank})

            for well in settings.wells:
                if self._abort.is_set():
                    break
                self.current_well = well
                well_states[well] = "active"
                self._emit("well", {"index": well, "state": "active"})
                try:
                    rows = self._run_well(settings, well)
                    self.results.extend(rows)
                    well_states[well] = "done"
                    self._emit("well", {"index": well, "state": "done"})
                    try:
                        self.cnc.retract_z(z_safe=self.cnc.Z_HIGH_BOUND, allow_abort=True)
                    except KeyboardInterrupt:
                        break
                except KeyboardInterrupt:
                    well_states[well] = "skipped"
                    self._emit("well", {"index": well, "state": "skipped"})
                    break
                except CNCMotionError as exc:
                    well_states[well] = "skipped"
                    self.error = str(exc)
                    self._emit("well", {"index": well, "state": "skipped"})
                    self._emit("log", {"message": str(exc)})
                    break

            csv_path = self._write_csv(settings)
            self.last_csv = str(csv_path)
            if self._abort.is_set():
                self._safe_stop_motion(settings)
                self._emit("run_complete", {"status": "stopped", "csv": self.last_csv, "rows": len(self.results)})
            else:
                if settings.home_at_end:
                    self._emit_step("Home")
                    self.cnc.home(allow_abort=False)
                self._emit_step("Idle")
                self._emit(
                    "run_complete",
                    {"status": "complete", "csv": self.last_csv, "rows": len(self.results)},
                )
        except Exception as exc:
            self.error = str(exc)
            self._emit("log", {"message": str(exc)})
            self._safe_stop_motion(settings)
            self._emit("run_complete", {"status": "error", "error": str(exc), "csv": self.last_csv})
        finally:
            self.running = False
            self.stopping = False
            self.current_well = None
            self.current_step = "Idle"
            self._abort.clear()

    def _run_well(self, settings: RunSettings, well: int) -> List[Dict[str, Any]]:
        self._emit_step(f"Moving to well {well}")
        self.cnc.move_to_location(
            settings.location_name, well, safe=True, speed=settings.speed
        )
        self._emit("position", self.cnc.position())

        z_value = -(settings.expected_height)
        last_fine_r = 0

        if settings.coarse_approach:
            self._emit_step("Coarse approach")
            found = False
            z = z_value
            for k in range(settings.coarse_max_steps):
                if self._abort.is_set():
                    raise KeyboardInterrupt("Stop requested")
                z = -settings.expected_height - (settings.coarse_step * k)
                self.cnc.move_to_point(z=z, speed=settings.speed)
                self.force.set_virtual_z(z)
                force_n = self._read_force()
                self._emit(
                    "force",
                    {"force_n": force_n, "z": z, "well": well, "stage": "coarse"},
                )
                if force_n > settings.coarse_force:
                    z_value = z + settings.coarse_backoff
                    found = True
                    break
            if not found:
                z_value = z
            self.cnc.move_to_point(z=z_value, speed=settings.speed)

        if settings.fine_approach:
            self._emit_step("Fine approach")
            found = False
            z = z_value
            for r in range(settings.fine_max_steps):
                if self._abort.is_set():
                    raise KeyboardInterrupt("Stop requested")
                last_fine_r = r
                z = z_value - (settings.fine_step * r)
                self.cnc.move_to_point(z=z, speed=settings.speed)
                self.force.set_virtual_z(z)
                force_n = self._read_force()
                self._emit(
                    "force",
                    {"force_n": force_n, "z": z, "well": well, "stage": "fine"},
                )
                if force_n > settings.fine_force:
                    z_value = z + settings.fine_backoff
                    found = True
                    break
            if not found:
                z_value = z

        height = (z_value - (settings.indent_step * last_fine_r)) + settings.height_offset
        if height <= 0:
            height = max(abs(z_value), 0.01)

        rows: List[Dict[str, Any]] = []
        if settings.mode == "relaxation":
            rows = self._relaxation(settings, well, z_value, height)
        elif settings.do_indent:
            rows = self._indent(settings, well, z_value, height)
        return rows

    def _indent(
        self, settings: RunSettings, well: int, z_value: float, height: float
    ) -> List[Dict[str, Any]]:
        self._emit_step("Indent")
        force_hist: List[float] = []
        rows: List[Dict[str, Any]] = []
        for r in range(settings.indent_max_steps):
            if self._abort.is_set():
                raise KeyboardInterrupt("Stop requested")
            z = z_value - (settings.indent_step * r)
            self.cnc.move_to_point(z=z, speed=settings.speed)
            self.force.set_virtual_z(z)
            force_n = round(self._read_force(), 4)
            distance = round(settings.indent_step * r, 4)
            stress = stress_mpa(force_n, settings.contact_area_mm2)
            strain = round((distance / height) * 100, 4) if height else 0.0
            force_hist.append(force_n)
            point = {
                "sample_label": settings.experiment_name or f"well {well}",
                "well": well,
                "point_index": r + 1,
                "mode": "stress_strain",
                "height": height,
                "distance_mm": distance,
                "z": z,
                "force_N": force_n,
                "strain_percent": strain,
                "stress_mPa": stress,
                "contact_area_mm2": settings.contact_area_mm2,
                "time_secs": "",
            }
            rows.append(point)
            self._emit("point", point)
            self._emit("force", {"force_n": force_n, "z": z, "well": well, "stage": "indent"})
            if force_n > settings.force_stop_n:
                break
            if (
                settings.stop_on_crack
                and len(force_hist) > 2
                and force_hist[-1] < settings.crack_drop_frac * force_hist[-2]
                and force_hist[-1] > 0.1
            ):
                break
        return rows

    def _relaxation(
        self, settings: RunSettings, well: int, z_value: float, height: float
    ) -> List[Dict[str, Any]]:
        self._emit_step("Hold (relaxation)")
        compression = height * settings.relaxation_hold_frac
        hold_z = z_value - compression
        self.cnc.move_to_point(z=hold_z, speed=settings.speed)
        self.force.set_virtual_z(hold_z)
        start = time.time()
        rows: List[Dict[str, Any]] = []
        force_hist: List[float] = []
        for r in range(settings.relaxation_samples):
            if self._abort.is_set():
                raise KeyboardInterrupt("Stop requested")
            force_n = round(self._read_force(), 4)
            elapsed = time.time() - start
            stress = stress_mpa(force_n, settings.contact_area_mm2)
            force_hist.append(force_n)
            point = {
                "sample_label": settings.experiment_name or f"well {well}",
                "well": well,
                "point_index": r + 1,
                "mode": "relaxation",
                "height": height,
                "distance_mm": round(compression, 4),
                "z": hold_z,
                "force_N": force_n,
                "strain_percent": round(settings.relaxation_hold_frac * 100, 4),
                "stress_mPa": stress,
                "contact_area_mm2": settings.contact_area_mm2,
                "time_secs": round(elapsed, 3),
            }
            rows.append(point)
            self._emit("point", point)
            self._emit(
                "force",
                {"force_n": force_n, "z": hold_z, "well": well, "stage": "relaxation"},
            )
            if force_n > settings.force_stop_n:
                break
            if (
                settings.stop_on_crack
                and len(force_hist) > 2
                and force_hist[-1] < settings.crack_drop_frac * force_hist[-2]
                and force_hist[-1] > 0.1
            ):
                break
            time.sleep(0.2)
        return rows

    def _write_csv(self, settings: RunSettings) -> Path:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = settings.experiment_name.strip() or "indent"
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
        path = RESULTS_DIR / f"{safe}_{stamp}.csv"
        fields = [
            "sample_label",
            "well",
            "point_index",
            "mode",
            "height",
            "distance_mm",
            "z",
            "force_N",
            "strain_percent",
            "stress_mPa",
            "contact_area_mm2",
            "time_secs",
        ]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self.results)
        return path
