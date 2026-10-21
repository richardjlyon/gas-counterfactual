"""Decision 0108 item 1.7 (ticket 15 test 19, 0075): figures keys for "the net-zero change" in the Capacity Market
figures, contracted minus metered NZ5, read from the run file's `pos_cm` block."""
from __future__ import annotations

Y16_24 = [str(y) for y in range(2016, 2025)]

DECLARED = {
    "pos_cm_netzero_change_gbp_m": {
        "label": "Net-zero change in the Capacity Market line: NZ5 on contracted interconnectors less NZ5 on metered "
                 "flow (0057), by year 2016-24, cash £m",
        "mapped_name": "pos.cm.netzero_change_gbp_m", "basis": "modelled", "provisional": False, "ticket": "15",
        "units": "table, £m cash", "period": "2016-2024", "run_field": "pos_cm.netzero_change_gbp_m[2016..2024]"},
    "pos_cm_netzero_change_2002_24_gbp_bn": {
        "label": "Net-zero change in the Capacity Market line (contracted less metered NZ5), 2002-24 total "
                 "(0 before 2016), 2024 prices",
        "mapped_name": "pos.cm.netzero_change_gbp_m_2024prices", "basis": "modelled", "provisional": False,
        "ticket": "15", "units": "£bn, 2024 prices", "period": "2002-2024",
        "run_field": "Σ2002-24 pos_cm.netzero_change_gbp_m, cash to run base (CPIH), then 2024 prices"},
}


def values(run: dict) -> dict:
    from gascf import deflator_cpih
    from gascf.figures import to_2024
    b = run.get("pos_cm")
    if b is None:
        return {k: None for k in DECLARED}
    ch = b["netzero_change_gbp_m"]
    base = int(run["meta"]["price_base"])
    return {"pos_cm_netzero_change_gbp_m": {y: ch[y] for y in Y16_24},
            "pos_cm_netzero_change_2002_24_gbp_bn": to_2024(sum(deflator_cpih.to_real(ch[str(y)], y, base)
                                                                for y in range(2002, 2025)), run) / 1e3}
