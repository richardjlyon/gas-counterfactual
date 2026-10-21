"""Run-file block `pos_cm` (decision 0108 item 1.7, Richard Lyon, 19 Oct 2026, option (a); ticket 15 test 19, 0075):
"the net-zero change" in the Capacity Market figures = NZ5 under contracted interconnectors (the central build) minus
NZ5 under the range registry's metered-interconnector row, cash £m by year. 0 before 2016 (0062)."""
from __future__ import annotations

from gascf import bills as B

METERED_ROW = "interconnectors at peak (metered flow, v4-s35)"


def _nz5(b: dict) -> float:
    return next(l["national_gbp_m_nominal"] for l in b["netzero"] if l["id"] == "NZ5")


def block(built: dict, build=None) -> dict:
    build = B.build if build is None else build
    (s,) = B.SWITCHES[METERED_ROW]
    metered = build(s)
    return {"netzero_change_gbp_m": {str(y): _nz5(built[y]) - _nz5(metered[y]) for y in B.YEARS},
            "metered_settings": {"ic_basis": s.ic_basis}, "metered_row": METERED_ROW, "money": "cash £m",
            "decision": "0108 item 1.7", "decisions": ["0057", "0062", "0075", "0108"]}


from gascf import export_v4 as _X  # noqa: E402

_X.register_block("pos_cm", block)
