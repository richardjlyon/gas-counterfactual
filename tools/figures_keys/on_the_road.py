"""Ticket 26 (0097): figures keys for the pre-2002 netting of the Fossil Fuel Levy (NZ2, to 2019) and EESoP
(NZ10, every year), each including the VAT the engine removed (figures-keys.md rows pre2002_netting_nz2/nz10/total).

Option (a): the on_the_road run-file block carries both the netted-off line part and its VAT (bills.py exports
vat_rate * d * nz2 and vat_rate * nz10, exactly what NZ11 lost), in 2024 prices. These keys read that part, never
re-derive it, so the printed figure equals what the build actually charged. The key is -(line + its VAT): the
netting lowers bills, so the figure is negative (-3.005, -1.059, -4.064 on s35).

Flags: NZ10's level and electricity share are INTERIM_APPROVED (0097 inputs update), so the NZ10 key and the
total carry both interim notes; NZ2's FFL level is SOURCED (CIQY, GB)."""
from __future__ import annotations

from gascf.bills import Settings as _S
from gascf.figures import PRICE_BASE_LABEL
from gascf.otr_blocks import INPUTS as _OTR_INPUTS

Y02_24 = [str(y) for y in range(2002, 2025)]          # NZ10 netting runs 2002-24 (2025 apart, 0093/0098)

# EESoP numbers derived from the engine's own on-the-road inputs, not re-typed (review ST5)
_EESOP_SPEND_GBP_M = next(i["value"] for i in _OTR_INPUTS if i["name"] == "eesop_spend_gbp_m")
_EESOP_ELEC_SHARE = next(i["value"] for i in _OTR_INPUTS if i["name"] == "eesop_electricity_share")
_INTERIM = (
    f"EESoP spend £{_EESOP_SPEND_GBP_M:g}m is an indicative supplier cost, not outturn (INTERIM_APPROVED)",
    f"EESoP electricity share {_EESOP_ELEC_SHARE * 100:.1f}% is split by energy saved, not by spend (INTERIM_APPROVED)",
)


def _m(label: str, run_field: str, period: str, status: str, notes=()) -> dict:
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": "26", "run_field": run_field,
            "units": "£bn, 2024 prices", "period": period, "price_base": PRICE_BASE_LABEL, "status": status,
            "notes": list(notes), "print": True}


DECLARED = {
    "pre2002_netting_nz2_2002_19_gbp_bn": _m(
        "Fossil Fuel Levy netted at its 2001 level, -(line + VAT), Σ2002-19 (0097)",
        "-Σ2002-19 on_the_road.years[y].(nz2_on_the_road_gbp_m_2024 + nz2_on_the_road_vat_gbp_m_2024)",
        "2002-2019", "SOURCED"),
    "pre2002_netting_nz10_2002_24_gbp_bn": _m(
        "EESoP netted at its 2001 level, -(line + VAT), Σ2002-24 (0097)",
        "-Σ2002-24 on_the_road.years[y].(nz10_on_the_road_gbp_m_2024 + nz10_on_the_road_vat_gbp_m_2024)",
        "2002-2024", "INTERIM_APPROVED", _INTERIM),
    "pre2002_netting_total_2002_24_gbp_bn": _m(
        "Pre-2002 netting, NZ2 + NZ10 incl. VAT, Σ2002-24 (0097)",
        "sum of pre2002_netting_nz2_2002_19_gbp_bn and pre2002_netting_nz10_2002_24_gbp_bn",
        "2002-2024", "INTERIM_APPROVED", _INTERIM),
    # Decision 0111 states the size of 0097's netting over 2002-04 (about £647.2m, 2025 prices); the paper's §5 prints it.
    "pre2002_netting_2002_04_gbp_m": _m(
        "0097 netting over 2002-04, NZ2 + NZ10 incl. VAT, amount removed from the net-zero-only lines (0111)",
        "Σ2002-04 on_the_road.years[y].(nz2 + nz2_vat + nz10 + nz10_vat)_gbp_m_2024, restated in 2025 prices (CPIH)",
        "2002-2004", "INTERIM_APPROVED", _INTERIM) | {"units": "£m, 2025 prices", "price_base": "2025 prices"},
}


def _incl(yrs: dict, y: str, line: str) -> float:
    return yrs[y][f"{line}_on_the_road_gbp_m_2024"] + yrs[y][f"{line}_on_the_road_vat_gbp_m_2024"]


def values(run: dict) -> dict:
    otr = run.get("on_the_road")
    if otr is None:          # without the block: None; figures.assert_complete refuses it in release mode (any None, any status)
        return {k: None for k in DECLARED}
    yrs = otr["years"]
    end = _S.otr_nz2_end_year                          # NZ2 nets only to the engine's end year (review ST5)
    if end != 2019:                                    # key name/label/period are fixed at 2002-19 (R2-ST5a): don't let value and label part
        raise ValueError(f"nz2 key is labelled 2002-19 but Settings.otr_nz2_end_year is {end}; "
                         "update the key name, label and period together with the end year")
    nz2_years = [y for y in Y02_24 if int(y) <= end]
    nz2 = -sum(_incl(yrs, y, "nz2") for y in nz2_years) / 1e3
    nz10 = -sum(_incl(yrs, y, "nz10") for y in Y02_24) / 1e3
    from gascf import deflator_cpih
    c = deflator_cpih.cpih()
    early = sum(_incl(yrs, y, "nz2") + _incl(yrs, y, "nz10") for y in ("2002", "2003", "2004")) * c[2025] / c[2024]
    return {
        "pre2002_netting_2002_04_gbp_m": early,
        "pre2002_netting_nz2_2002_19_gbp_bn": nz2,
        "pre2002_netting_nz10_2002_24_gbp_bn": nz10,
        "pre2002_netting_total_2002_24_gbp_bn": nz2 + nz10,
    }
