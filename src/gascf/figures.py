"""figures.json support for Report No. 1 (ticket 29; 0006, 0045: every printed figure from figures.json).

The run file is in its own money (`meta.price_base`, 2025 for v4-s35/s36); every £ key printed in
the report is in 2024 prices (`PRICE_BASE_LABEL`). `to_2024` is the one conversion, with the engine's
CPIH series (ONS L522, `gascf.deflator_cpih`), the deflator the run names in `meta.deflator`.
"""
from __future__ import annotations

from gascf import deflator_cpih

PRICE_BASE_YEAR = 2024
PRICE_BASE_LABEL = "2024 £ (CPIH L522)"
RUN_DEFLATOR = "ONS CPIH L522"


def register_sha256(rel: str) -> str:
    """sha256 of a staged source from the source register `data/raw/SHA256SUMS` (ticket 01), by its
    register path (e.g. "./s36/desnz/Electricity_since_1920.xlsx")."""
    from pathlib import Path
    sums = Path(__file__).resolve().parents[2] / "data/raw/SHA256SUMS"
    hits = [ln.split()[0] for ln in sums.read_text().splitlines() if ln.strip().endswith("  " + rel)]
    if len(hits) != 1:
        raise KeyError(f"{rel}: {len(hits)} rows in {sums.name}")
    return hits[0]


def to_2024(value: float, run: dict) -> float:
    """Restate `value` from the run's price base (meta.price_base) in 2024 prices, CPIH."""
    if run["meta"].get("deflator") != RUN_DEFLATOR:
        raise ValueError(f"run deflator {run['meta'].get('deflator')!r}, expected {RUN_DEFLATOR!r}")
    c = deflator_cpih.cpih()
    return value * c[PRICE_BASE_YEAR] / c[int(run["meta"]["price_base"])]


# ----------------------------------------------------------------------------- sourced section (0100)

SOURCED_REQUIRED = ("value", "units", "source", "locator", "claims_id")
TBC_MAY_LACK = ("locator", "claims_id")
# EiC, 17 Oct 2026: IDs are never renumbered or reassigned; CR-S039 deleted, CR-S041 and CR-S044 retired, unused.
# Ticket 47 (EIC ruling 17 Oct 2026 pass-4 point 3): CR-S008, CR-S050, CR-S051 moved to the modelled rb.pricing.*
# keys (QEP to day-ahead ratio), retired not reassigned. CR-S048 moves to modelled under ticket 48.
RETIRED_CLAIMS_IDS = ("CR-S039", "CR-S041", "CR-S044", "CR-S008", "CR-S050", "CR-S051", "CR-S048")


def load_sourced(path) -> dict:
    """The sourced section: {key: entry}. `data/figures/sourced.yaml` is JSON (valid YAML; the engine
    carries no YAML parser). Refuses an entry without a locator or a claims ID unless it carries
    `status: LOCATOR_TBC` (printed in the release record; does not block a preprint)."""
    import json
    from pathlib import Path
    keys = json.loads(Path(path).read_text())["keys"]
    for name, e in keys.items():
        tbc = e.get("status") == "LOCATOR_TBC"
        # 0122: a key the writer's claims register has not numbered yet carries claims_id_tbc instead of an ID; it is
        # listed in the release notes and never carries an invented ID.
        cid_tbc = e.get("claims_id_tbc") is True
        if cid_tbc and e.get("claims_id"):
            raise ValueError(f"{name}: claims_id_tbc and a claims_id together")
        for f in SOURCED_REQUIRED:
            if f == "claims_id" and cid_tbc:
                continue
            if not e.get(f) and e.get(f) != 0 and not (tbc and f in TBC_MAY_LACK):
                raise ValueError(f"{name}: no {f} (and status is not LOCATOR_TBC)")
        if e.get("claims_id") in RETIRED_CLAIMS_IDS:
            raise ValueError(f"{name}: claims ID {e['claims_id']} is retired and never reassigned")
        if name.startswith("sourced.qep_dayahead_ratio"):
            raise ValueError(f"{name}: moved to modelled rb.pricing.* (ticket 47); not a sourced key")
        if name.startswith("sourced.balancing_bsuos_basis_grossup"):
            raise ValueError(f"{name}: moved to modelled rb.balancing.* (ticket 48); not a sourced key")
    seen: dict = {}
    for name, e in keys.items():
        cid = e.get("claims_id")
        if cid and cid in seen:
            raise ValueError(f"{cid} carried by two keys: {seen[cid]} and {name}")
        seen[cid] = name
    return keys
