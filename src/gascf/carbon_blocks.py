"""Run-file blocks for the carbon split (s36 tickets 20 onward), registered through export_v4's block hook.

ets_auctions (ticket 20): the traced 2008-12 UK auction revenue (0056; Phase II total and the 2012 Phase
III row apart, 0067), power's share by year (2008 entered under 0068 with its status), the components
scaled to GB (0078: ETS only) and the sha256 of every data file read. It stands in for the `meta` fields
named in the spec (D6), which the block hook keeps out of `meta`."""
from gascf import carbon
from gascf import ets_auctions as E
from gascf import export_v4 as X


def ets_auctions_block(built: dict) -> dict:
    phases = carbon.ets_power_phases()
    rec = E.share_2008_record()
    return {
        "phase2_total_uk_gbp_m": sum(E.phase2_revenue_cy().values()),
        "phase2_uk_gbp_m": {str(y): v for y, v in E.phase2_revenue_cy().items()},
        "phase3_2012_uk_gbp_m": E.phase3_2012()["gbp_m"],
        "ets_power_share": {str(y): p["share"] for y, p in phases.items()},
        "ets_power_share_2008": {k: rec[k] for k in ("value", "status", "numerator_mtco2", "denominator_mtco2",
                                                     "numerator_source_id", "denominator_source_id")},
        "ets_power_share_2008_status": rec["status"],
        "gb_scaled_components": list(carbon.GB_SCALED_COMPONENTS),
        "revenue_periods": {str(y): {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in p.items()}
                            for y, p in carbon.ets_revenue_periods().items()},   # s36 ticket 45
        "money": "cash £m, UK (before GB scaling)",
        "files": {f"s36/ets/{p.name}": E._sha(p) for p in (E.PHASE2, E.PHASE3, E.SHARE_2008)},
        "decisions": ["0056", "0067", "0068", "0043", "0078"],
    }


X.register_block("ets_auctions", ets_auctions_block)


def carbon_2025p_block(built: dict) -> dict:
    """s36 ticket 21: the 2025 provisional pair on tax collected, printed side by side (§14.2), both cash £m:
    ETS power (0079: calendar-2025 auctions x 2024 share, GB-scaled per 0078) and CPS (0054)."""
    from gascf.system_costs import gb_share_of_uk
    c = carbon.cps_2025_record()
    ets_uk = carbon.ets_power_receipts()[2025][0]
    return {"ets_power_2025p_gbp_m": gb_share_of_uk(2025)[0] * ets_uk, "ets_power_2025p_uk_gbp_m": ets_uk,
            "ets_note": E.NOTE_2025, "cps_2025p_gbp_m": c["value"],
            "cps_2025p_range_high_gbp_m": c["cps_2025p_range_high_gbp_m"],
            "cps_2025_hmrc_printed_gbp_m": c["cps_2025_hmrc_printed_gbp_m"], "cps_note": c["note"],
            "money": "cash", "status": "provisional", "decisions": ["0054", "0079", "0078"]}


X.register_block("carbon_2025p", carbon_2025p_block)


def carbon_shortfall_rule_block(built: dict) -> dict:
    """0058's shortfall-rule sensitivity, option (b) (decision 0110 item 1.19, Richard Lyon, 19 Oct 2026): carbon tax
    collected on power 2013-20 under that rule, GB, cash £m by year, with the central counterpart. Methods page only;
    it moves the split, never NZ1c, NZ8, the gap or the headline."""
    r = carbon.shortfall_rule_receipts()
    return {"rule": E.SHORTFALL_RULE, "in_headline": False, "money": "cash £m, GB",
            "share": {str(y): v["share"] for y, v in r.items()},
            "tax_collected_gbp_m": {str(y): v["tax_collected_gbp_m"] for y, v in r.items()},
            "central_tax_collected_gbp_m": {str(y): v["central_tax_collected_gbp_m"] for y, v in r.items()},
            "decisions": ["0058", "0110", "0055", "0078"]}


X.register_block("carbon_shortfall_rule", carbon_shortfall_rule_block)
