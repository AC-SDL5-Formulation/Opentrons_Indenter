"""Indentation stress: 1 N/mm² = 1 MPa."""


def stress_mpa(force_n: float, contact_area_mm2: float) -> float:
    if contact_area_mm2 is None or contact_area_mm2 <= 0:
        return 0.0
    return round(float(force_n) / float(contact_area_mm2), 6)
