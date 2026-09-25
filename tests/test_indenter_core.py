import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from indenter.hardware.cnc import CNC_Machine
from indenter.hardware.force import ForceSensor, _ensure_event_loop
from indenter.ot.protocol_gen import generate_protocol
from indenter.run.settings import RunSettings
from indenter.run.stress import stress_mpa


class StressFormulaTests(unittest.TestCase):
    def test_one_newton_per_square_mm_is_one_mpa(self):
        self.assertEqual(stress_mpa(25.52, 25.52), 1.0)

    def test_zero_area_is_safe(self):
        self.assertEqual(stress_mpa(1.0, 0), 0.0)


class SettingsTests(unittest.TestCase):
    def test_from_dict_filters_unknown_keys(self):
        s = RunSettings.from_dict({"mode": "relaxation", "wells": [2, 8], "nope": 1})
        self.assertEqual(s.mode, "relaxation")
        self.assertEqual(s.wells, [2, 8])
        self.assertEqual(s.contact_area_mm2, 25.52)


class ProtocolTests(unittest.TestCase):
    def test_generated_protocol_compiles(self):
        src = generate_protocol(
            {
                "dispense_DMAm": True,
                "pipette_mix": True,
                "uv_stand_move": False,
            }
        )
        compile(src, "indenter_prep_protocol.py", "exec")
        self.assertIn("dispense_reagent(DMAm_replicates", src)
        self.assertIn("UV-stand pickup/dropoff skipped", src)
        self.assertNotIn("usbmodem", src)


class ForceScanTests(unittest.TestCase):
    def test_virtual_scan_lists_a_device(self):
        force = ForceSensor(virtual=True)
        devices = force.scan_ble()
        self.assertEqual(devices[0]["name"], "GDX-FOR VIRTUAL")

    def test_event_loop_can_be_created_on_a_worker_thread(self):
        import asyncio
        import threading

        seen = []

        def worker():
            try:
                asyncio.get_event_loop()
            except RuntimeError:
                seen.append("missing")
            _ensure_event_loop()
            asyncio.get_event_loop()
            seen.append("ok")

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertIn("ok", seen)


class LayoutTests(unittest.TestCase):
    def test_main_rack_grid(self):
        cnc = CNC_Machine(virtual=True)
        layout = cnc.layout("main_rack_A")
        self.assertEqual(layout["num_x"], 6)
        self.assertEqual(layout["num_y"], 8)
        self.assertEqual(len(layout["wells"]), 48)
        x, y, z = cnc.get_location_position("main_rack_A", 7)
        self.assertAlmostEqual(x, 77.5 + 13.08)
        self.assertAlmostEqual(y, 72 + 13.08)


if __name__ == "__main__":
    unittest.main()
