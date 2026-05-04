"""IWF-style Olympic weight category labels from body mass (demo / display).

Uses standard upper bounds: men 61–109 kg classes and +109; women 49–87 and +87.
Bodyweight at or below the bound maps to that category; above the heaviest
non-super bound maps to the superheavy label.
"""

from __future__ import annotations

from decimal import Decimal


def competitive_weight_class_label(bodyweight_kg, gender: str | None) -> str | None:
    """Return a short display label like ``71 kg`` or ``+109 kg``, or None if unknown."""
    if bodyweight_kg is None:
        return None
    g = (gender or "").strip().upper()
    if g not in ("M", "F"):
        return None
    try:
        bw = float(bodyweight_kg)
    except (TypeError, ValueError):
        return None
    if bw <= 0:
        return None

    if g == "M":
        bounds = (61, 73, 89, 102, 109)
        labels = ("61 kg", "73 kg", "89 kg", "102 kg", "109 kg", "+109 kg")
    else:
        bounds = (49, 59, 71, 81, 87)
        labels = ("49 kg", "59 kg", "71 kg", "81 kg", "87 kg", "+87 kg")

    for upper, lab in zip(bounds, labels):
        if bw <= upper + 1e-9:
            return lab
    return labels[-1]


def normalize_bodyweight_for_storage(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        d = Decimal(str(value))
    except Exception:
        return None
    if d <= 0:
        return None
    return d.quantize(Decimal("0.01"))
