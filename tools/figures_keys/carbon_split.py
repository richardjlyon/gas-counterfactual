"""s36 ticket 21: figures keys for the 2025 provisional pair on tax collected (0079 ETS, 0054 CPS),
read from the run file's `carbon_2025p` block; both cash £m, printed side by side in §14.2. And the 0058
shortfall-rule sensitivity, option (b) (decision 0110 item 1.19), from the `carbon_shortfall_rule` block."""
from __future__ import annotations

_COMMON = {"basis": "estimated", "provisional": True, "ticket": "21", "money": "cash"}
P2025 = ("ets_power_2025p_gbp_m", "cps_2025p_gbp_m", "cps_2025p_range_high_gbp_m")
SHORTFALL_KEY = "carbon_shortfall_rule_price_receipts_2013_20_gbp_bn"

DECLARED = {
    "ets_power_2025p_gbp_m": {
        "label": "2025 ETS power receipts, GB, provisional (0079: 2025 auctions x 2024 share)",
        "run_field": "carbon_2025p.ets_power_2025p_gbp_m", **_COMMON},
    "cps_2025p_gbp_m": {
        "label": "2025 Carbon Price Support, provisional (0054, about £428m; HMRC's next estimate of receipts from the "
                 "Carbon Price Floor for 2025, in the Environmental Taxes Bulletin tables due in March 2027)",
        "run_field": "carbon_2025p.cps_2025p_gbp_m", **_COMMON},
    "cps_2025p_range_high_gbp_m": {
        "label": "2025 Carbon Price Support, top of range (0054 Method B)",
        "run_field": "carbon_2025p.cps_2025p_range_high_gbp_m", **_COMMON},
    # Decision 0110 item 1.19 (Richard Lyon, 19 Oct 2026): the 0058 shortfall-rule sensitivity, option (b), 2013-20.
    SHORTFALL_KEY: {
        "label": ("Carbon prices collected as tax on power under the shortfall rule (0058 sensitivity, option (b), "
                  "0110), 2013-20; excludes the CCL at its main rates"),
        "basis": "estimated", "provisional": False, "ticket": "21", "money": "2024 prices",
        "units": "£bn, 2024 prices", "period": "2013-2020", "in_headline": False,
        "run_field": "Σ2013-20 carbon_shortfall_rule.tax_collected_gbp_m, cash to run base (CPIH), then 2024 prices"},
}


def values(run: dict) -> dict:
    from gascf import deflator_cpih
    from gascf.figures import to_2024
    b = run.get("carbon_2025p")      # s36 integration: absent from a pre-s36 run file -> None (as worked_hh)
    out = {k: (b[k] if b is not None else None) for k in P2025}
    s = run.get("carbon_shortfall_rule")
    base = int(run["meta"]["price_base"])
    out[SHORTFALL_KEY] = (None if s is None else to_2024(sum(
        deflator_cpih.to_real(s["tax_collected_gbp_m"][str(y)], y, base) for y in range(2013, 2021)), run) / 1e3)
    return out
