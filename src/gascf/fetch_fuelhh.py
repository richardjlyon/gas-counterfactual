"""Download Elexon BMRS FUELHH (transmission generation by fuel type, half-hourly, MW)
and store one pivoted CSV per year: date, period, then one column per fuel type.

Usage: uv run python -m gascf.fetch_fuelhh 2016 2026
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.request
from calendar import monthrange
from collections import defaultdict
from pathlib import Path

URL = ("https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream"
       "?settlementDateFrom={a}&settlementDateTo={b}")
OUT = Path(__file__).parents[2] / "data/raw/elexon"


def fetch_year(year: int) -> Path:
    rows: dict[tuple[str, int], dict[str, int]] = defaultdict(dict)
    for m in range(1, 13):
        a = f"{year}-{m:02d}-01"
        b = f"{year}-{m:02d}-{monthrange(year, m)[1]:02d}"
        with urllib.request.urlopen(URL.format(a=a, b=b), timeout=120) as r:
            for x in json.load(r):
                rows[(x["settlementDate"], int(x["settlementPeriod"]))][x["fuelType"]] = int(x["generation"])
    fuels = sorted({f for v in rows.values() for f in v})
    path = OUT / f"FUELHH_{year}.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["settlementDate", "settlementPeriod", *fuels])
        for k in sorted(rows):
            w.writerow([*k, *(rows[k].get(fu, "") for fu in fuels)])
    return path


if __name__ == "__main__":
    a, b = int(sys.argv[1]), int(sys.argv[2])
    for y in range(a, b + 1):
        p = fetch_year(y)
        print(p.name, sum(1 for _ in p.open()) - 1, "rows", flush=True)
