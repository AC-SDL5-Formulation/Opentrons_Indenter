#!/usr/bin/env python3
"""Indenter dashboard: Flask + SocketIO on localhost:8767."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_socketio import SocketIO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from indenter.hardware.cnc import CNCMotionError, CNC_Machine  # noqa: E402
from indenter.hardware.force import ForceSensor, ForceSensorError  # noqa: E402
from indenter.ot.protocol_gen import DEFAULT_OT, generate_protocol  # noqa: E402
from indenter.paths import DATA_DIR, DEVICES_JSON, HISTORY_JSON, RESULTS_DIR  # noqa: E402
from indenter.run.controller import IndentController  # noqa: E402
from indenter.run.settings import RunSettings  # noqa: E402

UI_DIR = Path(__file__).resolve().parent
HOST = os.environ.get("INDENTER_UI_HOST", "127.0.0.1")
PORT = int(os.environ.get("INDENTER_UI_PORT", "8767"))

app = Flask(__name__, static_folder=str(UI_DIR), static_url_path="")
app.config["SECRET_KEY"] = "indenter-local"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

_lock = threading.Lock()
_virtual = False
cnc = CNC_Machine(virtual=False)
force = ForceSensor(virtual=False)
controller = IndentController(cnc, force, emit=lambda _e, _p: None)
ot_protocol_ready = False
ot_last_settings = dict(DEFAULT_OT)
_last_protocol = ""


def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default


def _save_json(path: Path, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def remembered_devices() -> dict:
    data = _load_json(
        DEVICES_JSON,
        {"cnc_port": CNC_Machine.DEFAULT_PORT, "gdx_name": ""},
    )
    data.setdefault("cnc_port", CNC_Machine.DEFAULT_PORT)
    data.setdefault("gdx_name", "")
    return data


def remember_devices(cnc_port=None, gdx_name=None) -> dict:
    data = remembered_devices()
    if cnc_port:
        data["cnc_port"] = cnc_port
    if gdx_name is not None:
        data["gdx_name"] = gdx_name
    _save_json(DEVICES_JSON, data)
    return data


def append_history(entry: dict) -> None:
    hist = _load_json(HISTORY_JSON, [])
    hist.insert(0, entry)
    _save_json(HISTORY_JSON, hist[:50])


def status_payload() -> dict:
    cnc_state = "disconnected"
    if _virtual or cnc.VIRTUAL:
        cnc_state = "connected" if (cnc.connected or _virtual) else "disconnected"
        if cnc.connected or _virtual:
            cnc.last_status = cnc.last_status or "Idle (virtual)"
    elif cnc.connected:
        cnc_state = "connected"
        if "Idle" not in (cnc.last_status or "") and "virtual" not in (cnc.last_status or "").lower():
            if "Run" in (cnc.last_status or ""):
                cnc_state = "busy"
            elif "Alarm" in (cnc.last_status or "") or "failed" in (cnc.last_status or "").lower():
                cnc_state = "error"
    force_state = "disconnected"
    if force.connected:
        force_state = "connected"
    run_state = "IDLE"
    if controller.stopping:
        run_state = "STOPPING"
    elif controller.running:
        run_state = "RUNNING"
    ready = (_virtual or (cnc.connected and force.connected)) and not controller.running
    return {
        "virtual": _virtual,
        "run": run_state,
        "step": controller.current_step,
        "well": controller.current_well,
        "ready": ready,
        "error": controller.error or force.last_error,
        "ot_protocol_ready": ot_protocol_ready,
        "cnc": {
            "state": cnc_state,
            "status": cnc.last_status,
            "port": cnc.SERIAL_PORT,
            "connected": cnc.connected or _virtual,
            "position": cnc.position(),
            "homed": cnc.homed,
        },
        "force": {
            "state": force_state,
            "connected": force.connected,
            "name": force.device_name,
            "force_n": force.last_force_n,
            "blank": force.blank,
        },
        "remembered": remembered_devices(),
    }


def _heartbeat() -> None:
    while True:
        time.sleep(1.0)
        try:
            if controller.running:
                socketio.emit("status", status_payload())
                continue
            if cnc.connected and not cnc.VIRTUAL:
                try:
                    cnc.ping()
                except CNCMotionError as exc:
                    cnc.last_status = str(exc)
            if force.connected:
                if cnc.z is not None:
                    force.set_virtual_z(cnc.z)
                force.read_raw()
            socketio.emit("status", status_payload())
        except Exception:
            pass


@app.route("/")
def index():
    return send_from_directory(UI_DIR, "index.html")


@app.route("/api/status")
def api_status():
    return jsonify(status_payload())


@app.route("/api/layout")
def api_layout():
    name = request.args.get("location", "main_rack_A")
    return jsonify(cnc.layout(name))


@app.route("/api/ports")
def api_ports():
    return jsonify({"ports": CNC_Machine.list_ports(), "remembered": remembered_devices()})


@app.route("/api/virtual", methods=["POST"])
def api_virtual():
    global _virtual
    body = request.get_json(silent=True) or {}
    _virtual = bool(body.get("virtual"))
    cnc.VIRTUAL = _virtual
    force.VIRTUAL = _virtual
    if _virtual:
        cnc.connected = True
        force.connected = True
        cnc.last_status = "Idle (virtual)"
        force.last_force_n = 0.0
        if cnc.x is None:
            cnc.x = cnc.y = cnc.z = 0.0
    else:
        if cnc._ser is None:
            cnc.connected = False
            cnc.last_status = "not connected"
        if force._gdx is None:
            force.connected = False
            force.last_force_n = None
    socketio.emit("status", status_payload())
    return jsonify(status_payload())


@app.route("/api/cnc/connect", methods=["POST"])
def api_cnc_connect():
    body = request.get_json(silent=True) or {}
    port = body.get("port") or remembered_devices()["cnc_port"]
    try:
        if _virtual:
            cnc.VIRTUAL = True
        status = cnc.connect(port)
        remember_devices(cnc_port=cnc.SERIAL_PORT)
        socketio.emit("status", status_payload())
        return jsonify({"ok": True, "status": status, **status_payload()})
    except CNCMotionError as exc:
        return jsonify({"ok": False, "error": str(exc), **status_payload()}), 400


@app.route("/api/cnc/disconnect", methods=["POST"])
def api_cnc_disconnect():
    cnc.disconnect()
    socketio.emit("status", status_payload())
    return jsonify(status_payload())


@app.route("/api/cnc/home", methods=["POST"])
def api_cnc_home():
    if not (cnc.connected or _virtual):
        return jsonify({"ok": False, "error": "Connect the CNC first."}), 400
    try:
        cnc.home(allow_abort=True)
        socketio.emit("status", status_payload())
        return jsonify({"ok": True, **status_payload()})
    except (CNCMotionError, KeyboardInterrupt) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/cnc/jog", methods=["POST"])
def api_cnc_jog():
    if not (cnc.connected or _virtual):
        return jsonify({"ok": False, "error": "Connect the CNC first."}), 400
    body = request.get_json(silent=True) or {}
    try:
        cnc.jog(
            dx=float(body.get("dx") or 0),
            dy=float(body.get("dy") or 0),
            dz=float(body.get("dz") or 0),
            speed=int(body.get("speed") or 500),
        )
        socketio.emit("status", status_payload())
        return jsonify({"ok": True, **status_payload()})
    except CNCMotionError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/force/scan", methods=["POST"])
def api_force_scan():
    try:
        devices = force.scan_ble()
        if not devices:
            return jsonify(
                {
                    "ok": True,
                    "devices": [],
                    "error": "No Go Direct device found. Turn the sensor on and close Graphical Analysis if it is open. On the Raspberry Pi: sudo systemctl start bluetooth, then bluetoothctl power on. Your user must be in the bluetooth group. If still empty: rfkill unblock bluetooth and check hci0.",
                }
            )
        return jsonify({"ok": True, "devices": devices})
    except ForceSensorError as exc:
        return jsonify({"ok": False, "devices": [], "error": str(exc)}), 400


@app.route("/api/force/connect", methods=["POST"])
def api_force_connect():
    body = request.get_json(silent=True) or {}
    name = body.get("name") or remembered_devices().get("gdx_name") or ""
    try:
        force.VIRTUAL = _virtual
        msg = force.connect(name)
        remember_devices(gdx_name=force.device_name)
        socketio.emit("status", status_payload())
        return jsonify({"ok": True, "message": msg, **status_payload()})
    except ForceSensorError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/force/disconnect", methods=["POST"])
def api_force_disconnect():
    force.disconnect()
    socketio.emit("status", status_payload())
    return jsonify(status_payload())


@app.route("/api/force/zero", methods=["POST"])
def api_force_zero():
    if not force.connected:
        return jsonify({"ok": False, "error": "Connect the force sensor first."}), 400
    blank = force.zero()
    socketio.emit("status", status_payload())
    return jsonify({"ok": True, "blank": blank, **status_payload()})


@app.route("/api/run/start", methods=["POST"])
def api_run_start():
    if controller.running:
        return jsonify({"ok": False, "error": "A run is already in progress."}), 409
    if not _virtual and not (cnc.connected and force.connected):
        return jsonify(
            {
                "ok": False,
                "error": "Connect CNC and force sensor (green lights), or turn on Virtual mode.",
            }
        ), 400
    body = request.get_json(silent=True) or {}
    settings = RunSettings.from_dict(body)
    settings.virtual = _virtual
    cnc.VIRTUAL = _virtual
    force.VIRTUAL = _virtual
    try:
        controller.start(settings)
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    socketio.emit("status", status_payload())
    return jsonify({"ok": True, **status_payload()})


@app.route("/api/run/stop", methods=["POST"])
def api_run_stop():
    if not controller.running:
        try:
            cnc.retract_z(allow_abort=False)
            cnc.home(allow_abort=False)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        socketio.emit("status", status_payload())
        return jsonify({"ok": True, "message": "Retracted and homed.", **status_payload()})
    controller.request_stop()
    socketio.emit("status", status_payload())
    return jsonify({"ok": True, **status_payload()})


@app.route("/api/results")
def api_results():
    hist = _load_json(HISTORY_JSON, [])
    return jsonify(
        {
            "current": controller.results[-400:],
            "csv": controller.last_csv,
            "history": hist,
        }
    )


@app.route("/api/results/csv")
def api_results_csv():
    path = controller.last_csv
    if not path or not Path(path).exists():
        files = sorted(RESULTS_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return jsonify({"ok": False, "error": "No CSV yet. Run an experiment first."}), 404
        path = str(files[0])
    return send_file(path, as_attachment=True, download_name=Path(path).name)


@app.route("/api/ot/defaults")
def api_ot_defaults():
    return jsonify(ot_last_settings)


@app.route("/api/ot/generate", methods=["POST"])
def api_ot_generate():
    global ot_protocol_ready, ot_last_settings, _last_protocol
    body = request.get_json(silent=True) or {}
    ot_last_settings = {**DEFAULT_OT, **body}
    _last_protocol = generate_protocol(ot_last_settings)
    ot_protocol_ready = True
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "generated_protocol.py"
    out.write_text(_last_protocol)
    socketio.emit("status", status_payload())
    return jsonify({"ok": True, "protocol": _last_protocol, "ot_protocol_ready": True})


@app.route("/api/ot/download")
def api_ot_download():
    if not _last_protocol:
        return jsonify({"ok": False, "error": "Generate a protocol first."}), 404
    path = DATA_DIR / "generated_protocol.py"
    path.write_text(_last_protocol)
    return send_file(
        path,
        as_attachment=True,
        download_name="indenter_prep_protocol.py",
        mimetype="text/x-python",
    )


@socketio.on("connect")
def on_connect():
    socketio.emit("status", status_payload())


def _on_run_complete(payload: dict) -> None:
    append_history(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "status": payload.get("status"),
            "csv": payload.get("csv"),
            "rows": payload.get("rows"),
            "error": payload.get("error"),
        }
    )


def _wrap_emit():
    def emit(event, payload):
        socketio.emit(event, payload)
        if event == "run_complete":
            _on_run_complete(payload or {})

    controller._emit = emit


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _wrap_emit()
    threading.Thread(target=_heartbeat, daemon=True, name="indenter-heartbeat").start()
    url = f"http://{HOST}:{PORT}"
    print(f"Indenter dashboard → {url}")
    if os.environ.get("INDENTER_UI_OPEN_BROWSER", "1") != "0":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    socketio.run(app, host=HOST, port=PORT, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
