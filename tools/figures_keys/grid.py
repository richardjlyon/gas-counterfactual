"""Figures keys for the grid switches (ticket 25), read from the run file and restated in 2024 prices (CPIH), the
price base of every headline key (`gascf.figures.to_2024`).

sens_grid_rpi_x_2002_24_gbp_bn: the headline under go5_index = 'rpi_x' (0091), from the run's one-at-a-time range row
(0112), summed over 2002-24. rpi_x_effect_2002_24_gbp_bn: that less the central headline (negative = the gap falls).
Decision 0122 (Richard Lyon, 19 Oct 2026), card item 3: until the re-cut these keys stayed in the run's own money
(2025 £), so `sens_grid_rpi_x` read 162.71 beside a 161.28 central in 2024 £, as if RPI-X raised the gap. In one price
base it is 156.70, 4.58 below central, the same as the one-at-a-time table row."""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

RPI_X_ROW = "grid index at the controls' own X (RPI-X, 0091)"   # bills.SWITCHES name (range row, 0112)
Y02_24 = [str(y) for y in range(2002, 2025)]


def _m(label, run_field, units, period, ticket="25", **extra):
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": ticket, "run_field": run_field,
            "units": units, "period": period, "price_base": PRICE_BASE_LABEL, **extra}


DECLARED = {
    "sens_grid_rpi_x_2002_24_gbp_bn": _m(
        "Headline 2002-24 with the grid index at the price controls' own X values (RPI-X, 0091)",
        f"one_at_a_time.ranked[{RPI_X_ROW}][0].gap_real_bn[y], summed 2002-24, CPIH to 2024 £",
        "£bn, 2024 prices", "2002-2024"),
    "rpi_x_effect_2002_24_gbp_bn": _m(
        "Change in the 2002-24 headline with the grid index at the price controls' own X values (RPI-X, 0091), "
        "against central; negative = the gap falls",
        "sens_grid_rpi_x_2002_24_gbp_bn less Σ2002-24 gap[y].national_gbp_bn_real, both CPIH to 2024 £",
        "£bn, 2024 prices", "2002-2024", ticket="44 (0122)", signed=True),
    "scot_share_alt_gap_effect_2002_05_gbp_m": _m(
        "Gap effect 2002-05 of the alternative Scottish treatment before April 2005 (0102); not in the range",
        "scot_share_alt.gap_effect_2002_05_gbp_m, CPIH to 2024 £", "£m, 2024 prices", "2002-2005"),
    "scot_share_alt_level_shift_gbp_m": _m(
        "Shift in the NZ7 level 2002-05 under the alternative Scottish treatment (0102); GO5 moves about the same",
        "scot_share_alt.level_shift_gbp_m, CPIH to 2024 £", "£m, 2024 prices", "2002-2005"),
}


def values(run: dict) -> dict:
    # s36 integration (C onto D): a run file without the s36 row or block (e.g. frozen v4-s35, which group D's
    # figures tests read) gives None, as worked_hh does, instead of stopping figures.json for every module.
    out = {k: None for k in DECLARED}
    row = run.get("one_at_a_time", {}).get("ranked", {}).get(RPI_X_ROW)
    if row is not None:
        # decision 0112: rpi_x is a range row, read from the one-at-a-time block (national real gap, run price base)
        sens = to_2024(sum(row[0]["gap_real_bn"][y] for y in Y02_24), run)
        central = to_2024(sum(run["gap"][y]["national_gbp_bn_real"] for y in Y02_24), run)
        out["sens_grid_rpi_x_2002_24_gbp_bn"] = sens
        out["rpi_x_effect_2002_24_gbp_bn"] = sens - central
    if "scot_share_alt" in run:
        out["scot_share_alt_gap_effect_2002_05_gbp_m"] = to_2024(run["scot_share_alt"]["gap_effect_2002_05_gbp_m"], run)
        out["scot_share_alt_level_shift_gbp_m"] = to_2024(run["scot_share_alt"]["level_shift_gbp_m"], run)
    return out
