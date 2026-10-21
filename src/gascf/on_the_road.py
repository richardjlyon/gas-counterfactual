"""The shared "on the road at a 2001 level" component (0101; patterns 0044 and 0097).

A charge already on bills in 2001 is on the road Britain was on at its 2001 level, so only the part above that
level counts as extra. `net` takes the counted series by calendar year and the 2001 level, and returns the
counted-less-level series and the netted-off part by year.

Modes:
- `amount` (0097: the Fossil Fuel Levy, EESoP): level(y) = L x index(y)/index(2001) (`real_cpih`) or L (`cash`).
- `rate_x_volume` (0044, ticket 12: the CCL): level(y) = 2001 rate x volume(y), carried the same way.
No floor is ruled (0097, 0044: years below the level count as negative), so `floor` takes 'none' only.
`end_year` (inclusive): after it nothing is netted (0097: the levy to 2019)."""
from __future__ import annotations

from collections.abc import Mapping

BASE_YEAR = 2001
INDEXATIONS = ("real_cpih", "cash")


def net(counted: Mapping[int, float], level: float, *, mode: str = "amount", indexation: str = "real_cpih",
        year_basis: str = "calendar", floor: str = "none", end_year: int | None = None,
        volume: Mapping[int, float] | None = None, index: Mapping[int, float] | None = None,
        applies_to: str | None = None) -> dict:
    """Net `counted` (by calendar year) against its 2001 level. `level` is £m a year (`amount`) or the 2001 rate
    (`rate_x_volume`, with `volume` by year). `index` defaults to CPIH (ONS L522 annual)."""
    if floor != "none":
        raise ValueError(f"floor {floor!r}: no floor is ruled (0097, 0044); only 'none'")
    if year_basis != "calendar":
        raise ValueError(f"year_basis {year_basis!r}: only 'calendar'")
    if indexation not in INDEXATIONS:
        raise ValueError(f"indexation {indexation!r}: one of {INDEXATIONS}")
    if mode not in ("amount", "rate_x_volume"):
        raise ValueError(f"mode {mode!r}")
    if mode == "rate_x_volume" and volume is None:
        raise ValueError("rate_x_volume needs volume by year")
    if indexation == "real_cpih" and index is None:
        from gascf.deflator_cpih import cpih
        index = cpih()
    netted = {}
    for y in counted:
        if end_year is not None and y > end_year:
            netted[y] = 0.0
            continue
        carry = index[y] / index[BASE_YEAR] if indexation == "real_cpih" else 1.0
        netted[y] = level * carry * (volume[y] if mode == "rate_x_volume" else 1.0)
    return {"counted": {y: counted[y] - netted[y] for y in counted}, "netted": netted,
            "applies_to": applies_to, "mode": mode, "indexation": indexation, "end_year": end_year}
