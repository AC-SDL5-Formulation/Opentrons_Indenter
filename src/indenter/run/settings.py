from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class RunSettings:
    experiment_name: str = ""
    mode: str = "stress_strain"  # stress_strain | relaxation
    wells: List[int] = field(default_factory=lambda: [0])
    location_name: str = "main_rack_A"
    contact_area_mm2: float = 25.52
    expected_height: float = 0.0
    height_offset: float = 22.0
    force_stop_n: float = 2.0
    crack_drop_frac: float = 0.65
    relaxation_hold_frac: float = 0.05
    relaxation_samples: int = 30
    coarse_approach: bool = True
    fine_approach: bool = True
    do_indent: bool = True
    stop_on_crack: bool = True
    home_at_end: bool = True
    virtual: bool = False
    coarse_step: float = 0.5
    coarse_force: float = 0.07
    coarse_backoff: float = 0.6
    coarse_max_steps: int = 50
    fine_step: float = 0.1
    fine_force: float = 0.05
    fine_backoff: float = 0.15
    fine_max_steps: int = 100
    indent_step: float = 0.05
    indent_max_steps: int = 1000
    speed: int = 3000

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "RunSettings":
        if not data:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {}
        for key, value in data.items():
            if key not in known:
                continue
            kwargs[key] = value
        settings = cls(**kwargs)
        if settings.mode not in ("stress_strain", "relaxation"):
            settings.mode = "stress_strain"
        settings.wells = [int(w) for w in (settings.wells or [0])]
        if not settings.wells:
            settings.wells = [0]
        settings.contact_area_mm2 = max(0.001, float(settings.contact_area_mm2))
        return settings
