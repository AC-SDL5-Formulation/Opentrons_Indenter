from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
REPO_ROOT = SRC_DIR.parent
LOCATION_YAML = REPO_ROOT / "location_status.yaml"
WEB_UI_DIR = REPO_ROOT / "web_ui"
DATA_DIR = WEB_UI_DIR / "data"
RESULTS_DIR = REPO_ROOT / "results"
DEVICES_JSON = DATA_DIR / "devices.json"
HISTORY_JSON = DATA_DIR / "history.json"
GDX_DIR = REPO_ROOT
