"""RB v1.1 M2: the closure test for the 'mixed' closures at the road's own load factor (card [internal ticket]).

Decision 0163 (Richard Lyon, 21 Oct 2026, as relayed by the chief-executive on card [internal ticket]; his words "Agree.
Next." to R1, R2 and R3 (a)):
- R1 (a): the closure test for Cottam and Fiddler's Ferry uses the road's load factor;
- R2 (a): repeat the test until the list of closures stops changing;
- R3 (a): the same test for all 9 mixed-cause closures.

Plain words. Spec §15.4 item 2 settles a 'mixed' closure (carbon costs and other causes together) by a margin test
without carbon: the station's margin in fossil Britain in the year before its real closure. Positive: carbon caused the
closure, so on the road it stays open; not positive: it closes on its real date. To v4-s38 the test ran in work scripts
(work/s24-closure-test, work/s28-fiddlers, work/s37-cottam) at each station's OWN load factor (NG's TNUoS ALF tables,
or LCPD running hours), and the register's dates were set by hand from the result. With `closure_test="road_lf"` the
engine runs the same margin formula at the ROAD's achieved coal load factor in that year
(`fossil_like_for_like.LfLYear.coal_lf_achieved`, the coal block's output over its nameplate), for every 'mixed' row,
and repeats until the list stops changing (`fixed_point`). A list that never settles stops the build
(`NoFixedPoint`); no list is picked silently.

The margin formula is the stored test's, unchanged (`work/s24-closure-test/margins.py`, loaded from the repository,
with Cottam's zone-15 setting from `work/s37-cottam/margins.py`, the highest of its three zone charges): output x
(price less carbon - fuel / efficiency - variable O&M) - (fixed O&M + insurance) - TNUoS wider tariff for its zone;
filters (FGD+SCR) shown separately. At the station's own load factor it reproduces the stored files exactly
(tests/test_v11_m2_closure_test.py). The load factor also sets the TNUoS ALF in the Transmit years (2016 on), as the
stored test does.

What a station that earns its keep does next is the register's own rule, recorded as data on each row
(`closure_test`: `if_kept_rule`, `if_kept_close`, `if_kept_source`), never chosen here:
- 'ied_tnp' (IED Transitional National Plan): it runs to the plan's end (30 June 2020) and closes, unless its margin
  after FGD+SCR is also positive, when it fits them and runs on (spec §15.4 item 3, §15.3 item 2; the Rugeley rule);
- 'lcpd_opt_out' (LCPD opted out): no filters were allowed; it closes on the register's LCPD date;
- 'ied_lld' (IED limited-life derogation): the register finds no datable close (hours only), so the real date is
  kept (the register's conservative rule for Ferrybridge C), and the test result is reported.

Carbon (cards [internal ticket], R12 (a)): the carbon rows put carbon into the same test as `extra_gbp_mwh`, £ per MWh of
the station's output (the carbon the price carries, less what is still deducted, less the station's own carbon), so
both groups run one loop.
"""
from __future__ import annotations

import calendar
import importlib.util
import statistics
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
S24 = ROOT / "work/s24-closure-test/margins.py"
RULES = ("register", "road_lf")
DEFAULT_RULE = "register"
IF_KEPT_RULES = ("lcpd_opt_out", "ied_tnp", "ied_lld")
FILTERS = "FGD+SCR"
# Cottam (work/s37-cottam/margins.py): zone 15 label, the highest of the three zone charges (conservative), and the
# Final ALFs 2021/22 paper for its 2015/16-2019/20 yearly load factors.
COTTAM = ("Cottam", "COTTAM", 2000, "2019-09-30", (2016, 2017, 2018, 2019))
COTTAM_ZONE = {"transmit": "South Lancashire, Yorkshire and Humber"}


class NoFixedPoint(RuntimeError):
    """The closure list did not settle: the loop revisited a list or ran out of rounds."""


@lru_cache(maxsize=1)
def _m():
    spec = importlib.util.spec_from_file_location("gascf_s24_margins", S24)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ZONES["Cottam"] = dict(COTTAM_ZONE)
    m.EXTRA_ALF["COTTAM"] = ((m.F_ALF2122, 2015),)
    return m


def stations() -> dict[str, dict]:
    """The tested stations (name -> alf name, MW, actual close, stored test years)."""
    out = {}
    for name, alf, mw, closed, years in [*_m().STATIONS, COTTAM]:
        out[name] = {"name": name, "alf_name": alf, "mw": float(mw), "actual_close": closed, "years": tuple(years)}
    return out


def station(name: str) -> dict:
    s = stations()
    if name not in s:
        raise KeyError(f"no closure test for {name!r}; tested: {sorted(s)}")
    return s[name]


@lru_cache(maxsize=None)
def _year_inputs(year: int, route: str | None = None) -> dict:
    from gascf import bills as B
    from gascf import fossil_fleet as ff
    from gascf import fossil_like_for_like as L
    P, C = B.p_elec(route or B.CENTRAL.route), B.c_marg()
    ed = L.edition(year)
    k, base = ed.coal, ed.price_base["coal"]
    return {"p": statistics.mean(P[(year, m)]["gbp_per_mwh"] for m in range(1, 13)),
            "c": statistics.mean(C[(year, m)]["gbp_per_mwh"] for m in range(1, 13)),
            "coal": statistics.mean(L.coal_price(year, m) for m in range(1, 13)),
            "eta": L._eta_dukes("coal", year),     # DUKES 5.10.C; 2025 the engine's recorded 2015-23 mean
            "vom": ff.restate(k.variable_om_gbp_mwh, base, year),
            "fix": ff.restate((k.fixed_om_gbp_mw_yr + k.insurance_gbp_mw_yr) / 1000, base, year),
            "fgdscr": ff.abatement_gbp_kw_yr(ed, FILTERS)}


@lru_cache(maxsize=None)
def station_margin(name: str, year: int, lf: float, extra_gbp_mwh: float = 0.0) -> dict:
    """The stored test's margin for `name` in `year` at load factor `lf`, £m year-y money (cash). `extra_gbp_mwh`
    is any further £ per MWh of output (the carbon rows' terms); 0 in the no-carbon test."""
    s = station(name)
    mw = s["mw"]
    x = _year_inputs(year)
    hours = (366 if calendar.isleap(year) else 365) * 24
    twh = mw * lf * hours / 1e6
    tn, tn_src = _m().tnuos(name, year, lf)
    spread = x["p"] - x["c"] - x["coal"] / x["eta"] - x["vom"]
    before = twh * (spread + extra_gbp_mwh) - mw * x["fix"] / 1000 - mw * tn / 1000
    f, v, _ = x["fgdscr"]
    filters = mw * f / 1000 + twh * v
    return {"station": name, "year": year, "lf": lf, "twh": twh, "spread_gbp_mwh": spread,
            "extra_gbp_mwh": extra_gbp_mwh, "fixed_gbp_m": mw * x["fix"] / 1000, "tnuos_gbp_kw": tn,
            "tnuos_src": tn_src, "margin_before_filters_gbp_m": before, "fgdscr_gbp_m": filters,
            "margin_after_fgdscr_gbp_m": before - filters}


def kept_coal_margin(year: int, coal_mw: float, lf: float, filter_vom_gbp_mwh: float, route: str | None = None) -> dict:
    """RB v1.1 M3 (decision 0163 R4 (a)): kept coal's market margin, £m year-y money: its output at the road's coal
    load factor x (price less carbon - fuel / efficiency - variable O&M - filters' running cost), annual means, the
    same margin as the closure test above (a working reading, stated in the card's results)."""
    x = _year_inputs(year, route)
    hours = (366 if calendar.isleap(year) else 365) * 24
    twh = coal_mw * lf * hours / 1e6
    spread = x["p"] - x["c"] - x["coal"] / x["eta"] - x["vom"] - filter_vom_gbp_mwh
    return {"twh": twh, "spread_gbp_mwh": spread, "margin_gbp_m": twh * spread, "lf": lf,
            "filter_vom_gbp_mwh": filter_vom_gbp_mwh}


def kept_coal_margin_road(year: int, share: float, block_twh_m: dict, price_less_carbon_gbp_m: dict,
                          uplift_gbp_m: dict, feedback_gbp_m: dict, filter_vom_gbp_mwh: float) -> dict:
    """v4-s40 item 2 (step-3 item 2 (a); decision 0175): kept coal's margin on the revenue the road assigns its output,
    £m year-y money. The `block_*` inputs are the coal block's own, by month, as the road charges them
    (`bills.coal_block_road_revenue`): price less carbon (MID-shaped under M8), the merit-order uplift on the coal
    block's own half-hours, the gas-price feedback. Kept coal is `share` of the block (kept coal MW / block MW, as
    v4-s39). Costs by month on the same output: fuel at the month's coal price / DUKES efficiency, variable O&M and the
    filters' running cost (as `kept_coal_margin`). The generators' net-zero charge (0167) comes off in `bills._build`
    (`bills.kept_coal_pay_after_charge`), where it is known."""
    x = _year_inputs(year)
    from gascf import fossil_like_for_like as L
    months = range(1, 13)
    twh = share * sum(block_twh_m[m] for m in months)
    plc = share * sum(price_less_carbon_gbp_m[m] for m in months)
    up = share * sum(uplift_gbp_m[m] for m in months)
    fb = share * sum(feedback_gbp_m[m] for m in months)
    fuel = share * sum(block_twh_m[m] * L.coal_price(year, m) / x["eta"] for m in months)
    vom = twh * (x["vom"] + filter_vom_gbp_mwh)
    margin = plc + up + fb - fuel - vom
    return {"twh": twh, "share": share, "block_twh_m": dict(block_twh_m), "price_less_carbon_gbp_m": plc,
            "uplift_gbp_m": up, "feedback_gbp_m": fb, "fuel_gbp_m": fuel, "vom_gbp_m": vom, "margin_gbp_m": margin,
            "spread_gbp_mwh": margin / twh if twh else 0.0, "filter_vom_gbp_mwh": filter_vom_gbp_mwh}


def deciding_year(row: dict) -> int:
    """The year the test decides on: the calendar year before the real closure (spec §15.4 item 2)."""
    return row["actual_close_d"].year - 1


def decide(row: dict, before: float, after: float) -> tuple[date | None, str | None, str]:
    """(fossil-Britain close, filters, why) for one 'mixed' row given its margins before and after FGD+SCR."""
    t = row["closure_test"]
    act = row["actual_close_d"]
    if before <= 0:
        return act, None, "margin not positive: closes on its real date"
    rule = t["if_kept_rule"]
    if rule not in IF_KEPT_RULES:
        raise ValueError(f"{row['station']}: if_kept_rule {rule!r} not in {IF_KEPT_RULES}")
    if rule == "ied_lld":
        return act, None, "margin positive, but the IED limited-life close is not datable: real date kept (register)"
    if rule == "ied_tnp" and after > 0:
        return None, FILTERS, "margin positive after FGD+SCR: fits them and runs on"
    close = date.fromisoformat(t["if_kept_close"])
    if close < act:
        raise ValueError(f"{row['station']}: if_kept_close {close} is before its real closure {act}")
    return close, None, ("margin positive, filters do not pay: runs to the TNP end and closes" if rule == "ied_tnp"
                         else "margin positive; LCPD opted out (no filters allowed): closes on the LCPD date")


def _key(row: dict) -> tuple[str, str]:
    return row["station"], row["unit"]


def register_state(rows: list[dict]) -> tuple:
    """The register's own list for these rows, as override tuples."""
    return tuple(sorted((r["station"], r["unit"],
                         r["fossil_britain_close_d"].isoformat() if r["fossil_britain_close_d"] else None,
                         r["abatement_needed"]) for r in rows))


def fixed_point(rows: list[dict], lf_of: Callable[[int, tuple], float],
                margin_of: Callable[[dict, int, float, tuple], tuple[float, float]], max_rounds: int = 20) -> dict:
    """R2 (a): start from the register's list; each round reads the road's coal load factor in each test year with
    the current list (`lf_of(year, overrides)`), re-tests every row (`margin_of(row, year, lf, overrides)` ->
    (before, after filters), £m) and sets each row's close by `decide`. Stops when a round changes nothing.
    Returns {"overrides": ((station, unit, close ISO or None, filters), ...), "rounds": [...], "converged": True}."""
    state = register_state(rows)
    seen = {state}
    rounds = []
    for _ in range(max_rounds):
        lfs = {y: lf_of(y, state) for y in sorted({deciding_year(r) for r in rows})}
        new, detail = [], []
        for r in rows:
            y = deciding_year(r)
            before, after = margin_of(r, y, lfs[y], state)
            close, ab, why = decide(r, before, after)
            new.append((r["station"], r["unit"], close.isoformat() if close else None, ab))
            detail.append({"station": r["station"], "unit": r["unit"], "test_year": y, "road_lf": lfs[y],
                           "margin_before_filters_gbp_m": before, "margin_after_fgdscr_gbp_m": after,
                           "fossil_britain_close": close.isoformat() if close else None, "abatement": ab, "why": why})
        new_state = tuple(sorted(new))
        rounds.append({"road_lf": lfs, "rows": detail, "changed": new_state != state})
        if new_state == state:
            return {"overrides": state, "rounds": rounds, "converged": True}
        if new_state in seen:
            raise NoFixedPoint(f"closure list cycles after {len(rounds)} rounds: {new_state}")
        seen.add(new_state)
        state = new_state
    raise NoFixedPoint(f"closure list not settled after {max_rounds} rounds")


def apply(rows: tuple[dict, ...], overrides: tuple) -> tuple[dict, ...]:
    """The register rows with the loop's closes and filters in place of the register's, for the rows named."""
    o = {(s, u): (c, a) for s, u, c, a in overrides}
    out = []
    for r in rows:
        if (r["station"], r["unit"]) in o:
            c, a = o[(r["station"], r["unit"])]
            r = {**r, "fossil_britain_close_d": date.fromisoformat(c) if c else None, "abatement_needed": a}
        out.append(r)
    return tuple(out)
