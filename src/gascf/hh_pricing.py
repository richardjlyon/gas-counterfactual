"""RB v1.1 M8 (decision 0163, R9 (a)): fossil output priced half-hourly from when a free half-hourly series
exists, monthly before. A switch, OFF by default, measure only: Richard rules which reading, if either.

The free half-hourly series is Elexon's market index price (MID, APX rows), from 12 Sep 2016 SP32, the first
row Elexon's public API returns (data/raw/elexon/MID_APX_YYYY.csv, `gascf.mid`; 2016-17 fetched 21 Oct 2026).
LCCC's IMRP from 30 Jun 2016 is hourly, not half-hourly, so it is not used (0163).

GASCF_M8_HH_PRICE:
- "monthly" (v4-s38): every MWh at the month's price (Ofgem's monthly series, `prices.elec_monthly`).
- "mid_level": from the break, each half-hour's MWh at that half-hour's MID price (MID's own level).
- "mid_shape" (v4-s39 central, 0167): from the break, the month's Ofgem price times MID's half-hour shape: the output-weighted MID
  over the month's time-mean MID (so the month's level stays Ofgem's; only the timing within it moves).
GASCF_M8_SCOPE:
- "fossil" (v4-s38): the road's market-priced fossil output (actual output, and extra running at the
  market under 0144 item 1A), as R9 is worded.
- "both" (v4-s39 central, 0167): also Reliable Britain's NZ1 volume (ND + embedded wind and solar) priced the same way.
Half-hours on or after the break with no MID row (Elexon's own gaps) are priced at the month's price and
counted (`gap_halfhours`, MWh and the £ size against the month's MID mean are not estimated: no MID to use).
Station load, contracted imports called and the carbon taken out stay monthly in every reading.
"""
from __future__ import annotations

import os
from datetime import date
from functools import lru_cache

ENV, SCOPE_ENV = "GASCF_M8_HH_PRICE", "GASCF_M8_SCOPE"
METHODS = ("monthly", "mid_level", "mid_shape")
SCOPES = ("fossil", "both")
# v4-s39 central (card [internal ticket]; decision 0167, Richard Lyon 22 Oct 2026: "Approve."): MID shape in both Britains.
# "monthly" / "fossil" = v4-s38.
DEFAULT, DEFAULT_SCOPE = "mid_shape", "both"
MID_YEARS = range(2016, 2027)


def method() -> str:
    m = os.environ.get(ENV, DEFAULT) or DEFAULT
    if m not in METHODS:
        raise ValueError(f"{ENV}={m!r}: one of {METHODS}")
    return m


def scope() -> str:
    s = os.environ.get(SCOPE_ENV, DEFAULT_SCOPE) or DEFAULT_SCOPE
    if s not in SCOPES:
        raise ValueError(f"{SCOPE_ENV}={s!r}: one of {SCOPES}")
    return s


@lru_cache(maxsize=None)
def _mid_all() -> dict:
    from gascf.mid import OUT, read_mid
    out = {}
    for y in MID_YEARS:
        if (OUT / f"MID_APX_{y}.csv").exists():
            out.update({k: p for k, (p, _v) in read_mid(y).items()})
    return out


@lru_cache(maxsize=None)
def _hh_from() -> tuple:
    return min(_mid_all())


HH_FROM = (date(2016, 9, 12), 32)     # checked against the held file by `_check_start`


def _check_start() -> None:
    if _hh_from() != HH_FROM:
        raise ValueError(f"M8: first held MID row is {_hh_from()}, not {HH_FROM}")


def mid_at(day: date, period: int) -> float | None:
    if (day, period) < HH_FROM:
        return None
    return _mid_all().get((day, period))


def is_gap(day: date, period: int) -> bool:
    """On or after the break and no MID row: priced at the month's price and counted."""
    return (day, period) >= HH_FROM and (day, period) not in _mid_all()


@lru_cache(maxsize=None)
def mid_month_mean(year: int, month: int) -> float | None:
    v = [p for (d, _), p in _mid_all().items() if d.year == year and d.month == month and (d, _) >= HH_FROM]
    return sum(v) / len(v) if v else None


class MonthSums:
    """Output in one month split into half-hours with a MID price and half-hours without one."""
    __slots__ = ("cov_w", "cov_wp", "unc_w", "gaps")

    def __init__(self):
        self.cov_w = self.cov_wp = self.unc_w = 0.0
        self.gaps = 0

    def add(self, mid: float | None, w: float, gap: bool = False) -> None:
        if w <= 0:
            return
        if mid is None:
            self.unc_w += w
            self.gaps += gap
        else:
            self.cov_w += w
            self.cov_wp += w * mid

    def price(self, p_month: float, meth: str, mid_mean: float | None) -> float:
        tot = self.cov_w + self.unc_w
        if meth == "monthly" or tot <= 0 or self.cov_w <= 0:
            return p_month
        if meth == "mid_level":
            return (self.cov_wp + self.unc_w * p_month) / tot
        if meth == "mid_shape":
            shape = (self.cov_wp / self.cov_w) / mid_mean
            return (self.cov_w * p_month * shape + self.unc_w * p_month) / tot
        raise ValueError(meth)

    def as_dict(self) -> dict:
        return {"covered_mw_hh": self.cov_w, "uncovered_mw_hh": self.unc_w, "gap_halfhours": self.gaps}


def effective(p_month: float, sums: "MonthSums | None", year: int, month: int, meth: str) -> float:
    if sums is None or meth == "monthly":
        return p_month
    return sums.price(p_month, meth, mid_month_mean(year, month))


@lru_cache(maxsize=None)
def demand_sums(year: int) -> dict:
    """Reliable Britain's NZ1 volume (ND + embedded wind + solar, as `residual_neso.volume_monthly`) by month."""
    from gascf import residual_neso as rn
    out = {m: MonthSums() for m in range(1, 13)}
    for r in rn.read_neso(year):
        out[r.day.month].add(mid_at(r.day, r.period), r.nd + r.embedded_wind + r.embedded_solar,
                             is_gap(r.day, r.period))
    return out


def active() -> bool:
    m = method()
    if m != "monthly":
        _check_start()
    return m != "monthly"


def run_meta() -> dict:
    return {"method": method(), "scope": scope(), "switch_env": [ENV, SCOPE_ENV], "default": [DEFAULT, DEFAULT_SCOPE],
            "halfhourly_from": f"{HH_FROM[0].isoformat()} SP{HH_FROM[1]}", "series": "Elexon BMRS MID, APX (APXMIDP)",
            "before": "monthly (Ofgem series)", "gaps": "priced at the month's price, counted",
            "status": "central in v4-s39, as ruled in decision 0167 (M8 'Approve.': MID shape, both Britains); 'monthly' / 'fossil' reproduce v4-s38"}
