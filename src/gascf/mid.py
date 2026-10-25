"""Elexon BMRS MID: the Elexon market index price, APX (APXMIDP) half-hourly £/MWh and MWh. Elexon describes MID
as the price "in the short term markets"; it is not the day-ahead auction price (0163 R25 (a)).

N2EX (N2EXMIDP) is published with zero prices and volumes in most periods, so APX is
used. Stored one CSV per year: settlementDate, settlementPeriod, price, volume.

Usage: uv run python -m gascf.mid 2018 2026
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.request
from calendar import monthrange
from datetime import date
from pathlib import Path

URL = "https://data.elexon.co.uk/bmrs/api/v1/datasets/MID/stream?from={a}T00:00Z&to={b}T23:59Z"
OUT = Path(__file__).parents[2] / "data/raw/elexon"


def fetch_year(year: int) -> Path:
    rows = {}
    for m in range(1, 13):
        a, b = f"{year}-{m:02d}-01", f"{year}-{m:02d}-{monthrange(year, m)[1]:02d}"
        req = urllib.request.Request(URL.format(a=a, b=b), headers={"User-Agent": "gascf/0.1"})
        with urllib.request.urlopen(req, timeout=120) as r:
            for x in json.load(r):
                if x["dataProvider"] == "APXMIDP" and x["settlementDate"].startswith(str(year)):
                    rows[(x["settlementDate"], int(x["settlementPeriod"]))] = (x["price"], x["volume"])
    path = OUT / f"MID_APX_{year}.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["settlementDate", "settlementPeriod", "price", "volume"])
        for k in sorted(rows):
            w.writerow([*k, *rows[k]])
    return path


def read_mid(year: int) -> dict[tuple[date, int], tuple[float, float]]:
    with (OUT / f"MID_APX_{year}.csv").open(newline="") as f:
        return {(date.fromisoformat(r["settlementDate"]), int(r["settlementPeriod"])):
                (float(r["price"]), float(r["volume"])) for r in csv.DictReader(f)}


if __name__ == "__main__":
    for y in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
        p = fetch_year(y)
        print(p.name, sum(1 for _ in p.open()) - 1, "rows", flush=True)
