"""Ticket 30 (0103): `gap_ucl_period`, Reliable Britain's gap on its own method over UCL's period
(calendar 2010-23), printed in §3 beside UCL's £104.3bn. No run on UCL's Europe-wide gas premise."""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, register_sha256, to_2024

PERIOD = range(2010, 2024)
UCL_PDF = "./s36/ucl-oshea/oshea-ucloe-preprint-290-v1.pdf"

DECLARED = {
    "gap_ucl_period": {
        "label": "Reliable Britain's gap on our method over UCL's period, 2010-23",
        "basis": "estimated", "provisional": False, "ticket": "30",
        "run_field": "Σ2010-23 gap[y].national_gbp_bn_real (= bills[y].totals.gap_gbp_m by CPIH)",
        "units": "£bn, 2024 prices", "period": "2010-2023", "price_base": PRICE_BASE_LABEL,
        "status": "SOURCED", "print": True,
        "period_start": PERIOD[0], "period_end": PERIOD[-1], "year_basis": "calendar",
        "compare_to": {
            "source": "O'Shea, Horne and Maslin (2025), UCL Open Environment Preprints, v1",
            "quote": "From 2010 to 2023, wind power delivered a net benefit of £104.3 billion",
            "locator": "abstract, PDF p.1, src/ucl-oshea/o.txt line 53",
            "pdf": UCL_PDF, "pdf_sha256": register_sha256(UCL_PDF),
        },
        "note": ("UCL's figure is wind-only, on a Europe-wide gas premise. There is no run on that premise; "
                 "this key is RB's gap on RB's method over UCL's period only."),
    },
}


def values(run: dict) -> dict:
    return {"gap_ucl_period": to_2024(sum(run["gap"][str(y)]["national_gbp_bn_real"] for y in PERIOD), run)}
