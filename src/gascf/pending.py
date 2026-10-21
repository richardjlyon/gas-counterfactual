"""Source-status guard (ticket 02; 0089, 0091 PLACEHOLDER stops).

A staged input row carries `status` (SOURCED, PENDING or PLACEHOLDER), a value and a `source_id`.
`require_sourced` refuses to use rows that are not all SOURCED with a value and a source id;
`release_stops` lists every staged file still holding PLACEHOLDER or PENDING rows, and the release
run (ticket 35) refuses to go on while it is non-empty."""
from __future__ import annotations

import csv
from pathlib import Path

STAGED_DIR = Path(__file__).resolve().parents[2] / "data/raw/s36"
STOP_STATUSES = ("PLACEHOLDER", "PENDING")


class PendingSourceError(RuntimeError):
    """An input is not yet sourced; the figure it feeds cannot be built."""


def require_sourced(records, name: str) -> list[dict]:
    rows = list(records)
    bad = [r for r in rows if r.get("status") != "SOURCED"]
    if bad:
        raise PendingSourceError(f"{name}: {len(bad)} row(s) not SOURCED")
    if any(r.get("value") in (None, "") for r in rows):
        raise PendingSourceError(f"{name}: a SOURCED row has no value")
    if any(r.get("source_id") in (None, "") for r in rows):
        raise PendingSourceError(f"{name}: a SOURCED row has no source id")
    return rows


def release_stops(directory: Path = STAGED_DIR) -> dict[str, int]:
    """{file relative to directory: rows with status PLACEHOLDER or PENDING}, for every CSV with a
    `status` column. Empty means the release may go on."""
    out = {}
    for p in sorted(Path(directory).rglob("*.csv")):
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        n = sum(1 for r in rows if (r.get("status") or "").strip() in STOP_STATUSES)
        if n:
            out[str(p.relative_to(directory))] = n
    return out
