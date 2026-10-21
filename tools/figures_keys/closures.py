"""Ticket 44 (key half): §6.2 closure margins before carbon, last full year (2015), R-A4 option A.

Read from `work/s24-closure-test/margins.json`, a work-script output (margins.py), not a run-file field: the
release step (35) reruns margins.py on the release code and the file's sha256 is pinned in each key's
metadata at generation. The build stops if a sign no longer matches the §6.2 words (no auto-rewording).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

MARGINS = Path(__file__).resolve().parents[2] / "work/s24-closure-test/margins.json"
STATIONS = {"rugeley_margin_ex_carbon_last_year_gbp_m": "Rugeley",
            "longannet_margin_ex_carbon_last_year_gbp_m": "Longannet"}


def _m(station):
    return {"label": f"{station}'s modelled margin before carbon in its last full year of operation (2015), "
                     "before the abatement filters", "basis": "modelled", "provisional": True, "ticket": "44",
            "run_field": f"margins.json[{station}].years[-1].margin_before_filters_gbp_m (work script, not a "
                         "run field; 0045 note)", "units": "£m, cash", "period": "2015", "year": 2015,
            "status": "PENDING", "print": True, "file": "work/s24-closure-test/margins.json",
            "file_sha256": None}


DECLARED = {k: _m(s) for k, s in STATIONS.items()}


def check_signs(m: dict) -> None:
    """§6.2 words: Rugeley positive in each of its three years (though thin), Longannet negative in 2015."""
    rug = [y["margin_before_filters_gbp_m"] for y in m["Rugeley"]["years"]]
    lng = m["Longannet"]["years"][-1]["margin_before_filters_gbp_m"]
    if any(v <= 0 for v in rug):
        raise ValueError(f"Rugeley margin not positive in every year {rug}: §6.2 wording needs the Editor")
    if lng >= 0:
        raise ValueError(f"Longannet 2015 margin {lng} is not negative: §6.2 wording needs the Editor")


def values(run: dict) -> dict:
    raw = Path(MARGINS).read_bytes()
    m = json.loads(raw)
    check_signs(m)
    sha = hashlib.sha256(raw).hexdigest()
    out = {}
    for k, st in STATIONS.items():
        last = m[st]["years"][-1]
        if last.get("year", 2015) != 2015:
            raise ValueError(f"{st}: last year is {last.get('year')}, not 2015")
        DECLARED[k]["file_sha256"] = sha        # pinned at generation (R-A4 option A)
        out[k] = last["margin_before_filters_gbp_m"]
    return out
