"""The shared cost register this engine reads (decision 0168: one number, one source), pinned by sha256.

Every covered subsidy and system-cost series the bills use is read from here at run time: RO, RO mutualisation,
FiT (levelisation; scheme value for the sensitivity), CfD (all, biomass, other), Capacity Market paid, CCL on
electricity, CPS, ETS on power, BSUoS and TNUoS (whole charge, and Reliable Britain's generators'-share input),
and the energy-saving schemes. The engine's source parsers in `subsidies`, `balancing`, `grid`, `schemes` and
`carbon` are the register's builder (shared-cost-register/build, run at a release commit); the run never calls
them for those series. tests/test_cost_register_0168.py fails if a covered series is read from anywhere else.

Register home: <internal path> (README names the release it was built from).
A new register is never picked up automatically: copy the new file here, change REGISTER and REGISTER_SHA256,
rebuild, and record it, on purpose.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from gascf import cost_register as CR

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "data/register/shared-cost-register-v4-s43.csv"
REGISTER_SHA256 = "e38ae577d255e3cb6e350d8b4c4483d58c7903766d65ad879c49b7b6c3adf5b8"
PRODUCT = "rb"


@lru_cache(maxsize=None)
def register() -> CR.Register:
    return CR.load(REGISTER, REGISTER_SHA256)


def fy_rows(line: str, product: str | None = None) -> dict[int, tuple[float, str, str]]:
    """{year: (GBP m, basis, source_id)}: the series (or the product's line) with each row's basis and source."""
    reg = register()
    vals = reg.line(line, product) if product else reg.series(line)
    return {y: (v, reg.row(line, y)["basis"], reg.row(line, y)["source_id"]) for y, v in vals.items()}


def clear_caches() -> None:
    """Forget the loaded register and every cache that holds a register value (tests re-point REGISTER)."""
    from gascf import schemes
    register.cache_clear()
    schemes.schemes.cache_clear()
