"""Decision 0100 (sourced figures are filled from figures.json) and 0122 (Richard Lyon, 19 Oct 2026, card item 1): the
`sourced.*` section. Every entry of `data/figures/sourced.yaml`, checked by `gascf.figures.load_sourced`, becomes a
figures.json key carrying its value and, in its metadata, its units, source, locator, claims ID (or claims_id_tbc),
status and the file read. The run file is not read: a sourced figure is not an engine output."""
from __future__ import annotations

from pathlib import Path

from gascf.figures import load_sourced

PATH = Path(__file__).resolve().parents[2] / "data/figures/sourced.yaml"
META_FIELDS = ("units", "source", "locator", "file", "claims_id", "claims_id_tbc", "status", "derived", "derivation",
               "inputs", "note", "engine_check")


def _declared() -> dict:
    out = {}
    for name, e in load_sourced(PATH).items():
        out[name] = {"label": e.get("label") or f"{e['source']}: {e['locator']}", "basis": "measured",
                     "provisional": False, "ticket": "0122", "run_field": "none (data/figures/sourced.yaml)",
                     "section": "sourced", "paper_section": e["section"], "print": True,
                     **{f: e[f] for f in META_FIELDS if f in e}}
    return out


DECLARED = _declared()


def values(run: dict) -> dict:
    return {name: e["value"] for name, e in load_sourced(PATH).items()}
