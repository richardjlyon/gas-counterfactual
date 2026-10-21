"""Ticket 46 (EIC editorial ruling 17 Oct 2026, writer item 6): the figures key for the output of nuclear, imports
and pumped storage held at actual, net of exports and pumping, 2024 (engine volume.kept_twh / K(t), run-file field
years[y].nuclear_ic_ps_net_twh). Renames the never-built placeholder kept_output_twh_2024, whose name clashed with
the draft's bold term "kept output" (the extra output of the existing fleet). Reads the run field at full precision,
never GO1k's rounded years_note. PENDING until the release run (35) fixes the value."""
from __future__ import annotations


def _m(label: str, run_field: str, units: str, status: str) -> dict:
    return {"label": label, "basis": "modelled", "provisional": True, "ticket": "46",
            "run_field": run_field, "units": units, "status": status, "print": True}


DECLARED = {
    "nuclear_ic_ps_net_twh_2024": _m(
        "Output of nuclear, imports and pumped storage held at actual, net of exports and pumping, 2024 (TWh)",
        "years[2024].nuclear_ic_ps_net_twh", "TWh", "PENDING"),
}


def values(run: dict) -> dict:
    yrs = run.get("years")
    row = next((r for r in (yrs or []) if r.get("year") == 2024), None)
    if not row or "nuclear_ic_ps_net_twh" not in row:   # block or field absent: None (46-48 ruling), never the
        return {k: None for k in DECLARED}              # years_note; figures.assert_complete refuses it in release mode (any None, any status)
    return {"nuclear_ic_ps_net_twh_2024": row["nuclear_ic_ps_net_twh"]}
