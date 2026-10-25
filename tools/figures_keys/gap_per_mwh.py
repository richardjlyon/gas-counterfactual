"""RB v1.1 O4 (decision 0160, card [internal ticket]; ruled R19 (a), decision 0163, card [internal ticket]): the gap per MWh at
actual demand.

- billed: the gap over Britain's billed volume V (years[y].volume_twh: NESO demand plus embedded wind and solar, the
  volume both bills are charged on; station load is generated but billed in neither Britain, 0059). R19 (a), Richard
  Lyon, 21 Oct 2026: "the per-MWh gap at actual demand uses the billed volume the paper already uses for per-MWh
  figures". These keys print.
- with station load: the gap over V plus station load (years[y].station_load_twh), the volume generated. Kept in the
  file, never printed (R19 (a) chose the billed volume).

No model run: the gap and the volumes are in the run file. 2024 prices; £bn x 1,000 / TWh = £/MWh.
"""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

Y02_24 = [str(y) for y in range(2002, 2025)]
Y02_25 = Y02_24 + ["2025"]
BASES = {"billed": "billed volume V (years[y].volume_twh)",
         "with_station_load": "billed volume plus station load (years[y].volume_twh + station_load_twh)"}
PRINTED = "billed"          # R19 (a)


def _m(label: str, period: str, base: str, units: str = "£/MWh, 2024 prices", provisional: bool = False) -> dict:
    printed = base == PRINTED
    return {"label": label + ("" if printed else "; not printed (R19 (a) prints the billed volume)"),
            "basis": "modelled", "provisional": provisional, "ticket": "v1.1 O4 (0160)",
            "run_field": "gap[y].national_gbp_bn_real (to 2024 prices) x 1,000 / volume, TWh",
            "units": units, "period": period, "price_base": PRICE_BASE_LABEL, "status": "SOURCED",
            "print": printed, "ruling": "R19 (a)" if printed else "R19"}


DECLARED = {}
for _b, _w in BASES.items():
    DECLARED[f"gap_per_mwh_2002_24_{_b}_gbp"] = _m(f"Gap per MWh at actual demand, 2002-24 (Σ gap / Σ {_w})",
                                                   "2002-2024", _b)
    DECLARED[f"gap_per_mwh_2024_{_b}_gbp"] = _m(f"Gap per MWh at actual demand, 2024 ({_w})", "2024", _b)
    DECLARED[f"gap_per_mwh_2025p_{_b}_gbp"] = _m(f"Gap per MWh at actual demand, 2025 provisional ({_w})", "2025",
                                                 _b, provisional=True)
DECLARED["table_gap_per_mwh_by_year"] = _m("Gap per MWh at actual demand by year, 2002-25 (2025 provisional), over the "
                                           "billed volume, with the volume", "2002-2025", "billed",
                                           units="table, £/MWh, 2024 prices, TWh")
DECLARED["table_gap_per_mwh_by_year_with_station_load"] = _m(
    "Gap per MWh at actual demand by year, 2002-25 (2025 provisional), at both volumes, with the volumes",
    "2002-2025", "with_station_load", units="table, £/MWh, 2024 prices, TWh")


def values(run: dict) -> dict:
    if "years" not in run or "gap" not in run or any("station_load_twh" not in r for r in run["years"]):
        return {k: None for k in DECLARED}       # a run file before 0059 (v4-s35 and earlier) has no station load
    yr = {str(r["year"]): r for r in run["years"]}
    vol = {"billed": lambda y: yr[y]["volume_twh"],
           "with_station_load": lambda y: yr[y]["volume_twh"] + yr[y]["station_load_twh"]}
    gap = {y: to_2024(run["gap"][y]["national_gbp_bn_real"], run) for y in Y02_25}
    out = {}
    for b, f in vol.items():
        out[f"gap_per_mwh_2002_24_{b}_gbp"] = sum(gap[y] for y in Y02_24) * 1e3 / sum(f(y) for y in Y02_24)
        out[f"gap_per_mwh_2024_{b}_gbp"] = gap["2024"] * 1e3 / f("2024")
        out[f"gap_per_mwh_2025p_{b}_gbp"] = gap["2025"] * 1e3 / f("2025")
    prov = [str(p) for p in run["meta"]["provisional_years"]]
    both = [{"year": int(y), "provisional": y in prov, "gap_gbp_bn": gap[y], "volume_billed_twh": vol["billed"](y),
             "station_load_twh": yr[y]["station_load_twh"], "billed_gbp_mwh": gap[y] * 1e3 / vol["billed"](y),
             "with_station_load_gbp_mwh": gap[y] * 1e3 / vol["with_station_load"](y)} for y in Y02_25]
    out["table_gap_per_mwh_by_year_with_station_load"] = both
    out["table_gap_per_mwh_by_year"] = [{k: r[k] for k in ("year", "provisional", "gap_gbp_bn", "volume_billed_twh",
                                                            "billed_gbp_mwh")} for r in both]
    return out
