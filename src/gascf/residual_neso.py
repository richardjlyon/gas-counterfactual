"""Residual demand from NESO historic demand data, 2002-2025 (spec v4 §4.1).

"Residual demand" is the electricity the fossil fleet of fossil Britain must make in each
half-hour: everything Britain used, less what the kept plant made (nuclear, pumped storage
and interconnector imports, spec §15.1 decision 1). Before late 2016 Elexon publishes no
generation by fuel, so this module builds the residual from the demand side instead:

    residual(t) = ND(t) + station load(t) + pumping(t) + exports(t)
                + embedded wind(t) + embedded solar(t)
                - imports(t) - nuclear(t) - pumped-storage output(t)

Terms (all MW, averaged over the half-hour, Great Britain):
- ND, "national demand": NESO's transmission demand, which NESO says excludes station
  load, pumping and exports. Read from NESO *Historic Demand Data* for the year.
- station load: the electricity power stations use themselves. NESO's FAQ for the same
  dataset: "Station load is 500MW in BST and 600MW in GMT". Added because the 2016 →
  method (`residual.py`, built from metered station output) carries it, and the fleet has to
  make it (spec §4.1 formula omits it; see work/s20a-residual/notes.md). Switchable.
- pumping, exports, imports: NESO's pumped-storage pumping column and the signed
  interconnector flow columns (positive = import to GB, negative = export).
- embedded wind and solar: NESO's estimates of output from plant connected to local
  networks, which ND does not see. Blank before October 2007 (wind) and 2010 (solar):
  taken as zero and the year tagged *estimated* (spec §4.1).
- nuclear: not half-hourly before 2016. DESNZ DUKES 2026 Table 5.6.E annual nuclear
  electricity supplied (gross) for the year, shared across the months by Energy Trends
  Table 5.4 monthly MPP nuclear supplied, and spread flat inside each month (default; the
  spec §4.1 text says quarterly shaping by Energy Trends 5.1, kept as a switch). All UK
  nuclear is in GB.
- pumped-storage output: annual pumped-storage generation (DUKES 5.6.B "Energy storage",
  which is pumped storage only before 2017; Energy Trends 5.1b "Pumped storage" from 2017,
  which excludes batteries). Spread within each day in proportion to how far the
  half-hour's residual sits above that day's mean, capped at DUKES 5.7 pumped-hydro
  capacity ('day_shape', default). Spec §4.1 says "placed in the highest-residual
  half-hours up to its DUKES 5.7 capacity" ('annual_peak'); on 2016-2025 that rule fails
  the peak tolerance every year because real pumped storage was mostly *not* running at
  the residual peak (FUELHH at the 2019, 2022 and 2025 peaks: -296, 10 and 56 MW). 'flat'
  and 'daily_peak' are kept as switches too.

Batteries are not kept (spec §15 decision 7h): battery output is not subtracted, so the
fleet must cover what batteries now cover. NESO's ND already nets embedded battery output,
which is a small understatement of the residual, noted in GAPS.

Every number here is *modelled* (nuclear and pumped storage are spread by a stated rule) or
*estimated* (years with embedded generation missing). `V(y)`, the GB volume the wholesale
and fleet lines are applied to, is `ND + embedded wind + embedded solar` (spec §4.1), and is
*measured* where all three columns exist.

The calibration (spec §4.1, §12.2 item 6) runs this method on 2016-2025 and compares it with
the FUELHH method in `residual.py`; see `calibrate()`.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import openpyxl

RAW = Path(__file__).parents[2] / "data/raw"

DUKES_56 = RAW / "dukes/s20a-DUKES_5.6.xlsx"
DUKES_57 = RAW / "DUKES_5.7.xlsx"
ET_51 = RAW / "desnz_et/s20a-ET_5.1_SEP_26.xlsx"
ET_54 = RAW / "desnz_et/s20a-ET_5.4_SEP_26.xlsx"

SRC_NESO = "NESO-HDD-{year}"                 # NESO Historic Demand Data, one file a year
SRC_FAQ = "NESO-HDD-FAQ"                     # station load 500/600 MW
SRC_DUKES56 = "DESNZ-DUKES2026-T5.6"
SRC_DUKES57 = "DESNZ-DUKES2026-T5.7"
SRC_ET51 = "DESNZ-ET-SEP2026-T5.1"
SRC_ET54 = "DESNZ-ET-SEP2026-T5.4"

YEARS = range(2002, 2026)
INTERCONNECTORS = ("IFA_FLOW", "IFA2_FLOW", "BRITNED_FLOW", "MOYLE_FLOW", "EAST_WEST_FLOW",
                   "NEMO_FLOW", "NSL_FLOW", "ELECLINK_FLOW", "VIKING_FLOW", "GREENLINK_FLOW")
STATION_LOAD_BST, STATION_LOAD_GMT = 500.0, 600.0   # MW, NESO FAQ (verbatim in notes)


# --------------------------------------------------------------------------- readers

def neso_path(year: int) -> Path:
    """The stored NESO Historic Demand Data file for a calendar year (spec §4.1)."""
    name = f"s18c-demanddata_{year}.csv" if year <= 2014 else f"demanddata_{year}.csv"
    return RAW / "neso" / name


def _neso_date(s: str) -> date:
    s = s.strip().strip('"')
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(s.title() if fmt != "%Y-%m-%d" else s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"NESO date format moved: {s!r}")


def _num(v: str | None) -> float | None:
    """NESO writes 'NA' (or nothing) where a column did not yet exist."""
    if v is None or v.strip() in ("", "NA"):
        return None
    return float(v)


@dataclass(frozen=True)
class NesoRow:
    day: date
    period: int
    nd: float
    pumping: float
    imports: float          # MW into GB, sum of positive interconnector flows
    exports: float          # MW out of GB, sum of negative flows, as a positive number
    embedded_wind: float
    embedded_solar: float
    embedded_missing: bool  # True where NESO left embedded wind or solar blank


@lru_cache(maxsize=None)
def read_neso(year: int) -> tuple[NesoRow, ...]:
    """Every half-hour of the year from the stored NESO file. Fails loudly on a layout move."""
    rows = []
    with neso_path(year).open(newline="") as f:
        rd = csv.DictReader(f)
        need = {"SETTLEMENT_DATE", "SETTLEMENT_PERIOD", "ND", "PUMP_STORAGE_PUMPING",
                "EMBEDDED_WIND_GENERATION", "EMBEDDED_SOLAR_GENERATION", "IFA_FLOW"}
        missing = need - set(rd.fieldnames or ())
        if missing:
            raise ValueError(f"{neso_path(year).name}: columns missing {sorted(missing)}")
        ics = [c for c in INTERCONNECTORS if c in rd.fieldnames]
        for r in rd:
            if r.get("FORECAST_ACTUAL_INDICATOR", "A") != "A":
                continue
            flows = [_num(r[c]) or 0.0 for c in ics]
            ew, es = _num(r["EMBEDDED_WIND_GENERATION"]), _num(r["EMBEDDED_SOLAR_GENERATION"])
            nd = _num(r["ND"])
            if nd is None:
                raise ValueError(f"{neso_path(year).name}: ND blank on {r['SETTLEMENT_DATE']}")
            rows.append(NesoRow(
                day=_neso_date(r["SETTLEMENT_DATE"]), period=int(r["SETTLEMENT_PERIOD"]),
                nd=nd, pumping=_num(r["PUMP_STORAGE_PUMPING"]) or 0.0,
                imports=sum(x for x in flows if x > 0), exports=-sum(x for x in flows if x < 0),
                embedded_wind=ew or 0.0, embedded_solar=es or 0.0,
                embedded_missing=(ew is None or es is None)))
    if not rows or rows[0].day.year != year:
        raise ValueError(f"{neso_path(year).name}: not calendar year {year}")
    return tuple(rows)


def _find(rows, title: str) -> int:
    for i, r in enumerate(rows):
        if r and isinstance(r[0], str) and r[0].strip().startswith(title):
            return i
    raise ValueError(f"anchor not found: {title!r}")


def _row(rows, start: int, generator: str, fuel: str) -> tuple:
    """First row after `start` whose first two cells are (generator, fuel), before the next table."""
    for r in rows[start + 1:]:
        if r[0] and str(r[0]).startswith("Table "):
            break
        if r[0] and r[1] and str(r[0]).strip() == generator and str(r[1]).strip() == fuel:
            return r
    raise ValueError(f"row not found under table at {start}: {generator!r} / {fuel!r}")


def _sheet(path: Path, name: str) -> list[tuple]:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    return list(wb[name].iter_rows(values_only=True))


@lru_cache(maxsize=None)
def dukes_56() -> dict[str, dict[int, float]]:
    """DUKES 2026 Table 5.6 (sheet '5.6'), All generating companies, GWh by calendar year.

    Returns 'nuclear_supplied' (5.6.E), 'nuclear_generated' (5.6.B), 'storage_generated'
    (5.6.B 'Energy storage': pumped storage only before 2017, note 18) and
    'ps_used' (5.6.F 'Pumped storage', electricity used in pumping).
    """
    rows = _sheet(DUKES_56, "5.6")
    out = {}
    for key, title, fuel in (("nuclear_generated", "Table 5.6.B Electricity generated", "Nuclear"),
                             ("storage_generated", "Table 5.6.B Electricity generated", "Energy storage"),
                             ("nuclear_supplied", "Table 5.6.E Electricity supplied (gross)", "Nuclear"),
                             ("ps_used", "Table 5.6.F Electricity used in storage", "Pumped storage")):
        t = _find(rows, title)
        hdr = rows[t + 1]
        if hdr[0] != "Generation type" or hdr[1] != "Fuel":
            raise ValueError(f"DUKES 5.6 header moved under {title!r}: {hdr[:3]}")
        r = _row(rows, t, "All generating companies", fuel)
        out[key] = {int(h): float(v) for h, v in zip(hdr[2:], r[2:])
                    if h is not None and str(h).isdigit() and isinstance(v, (int, float))}
    return out


@lru_cache(maxsize=None)
def energy_trends_51() -> dict[str, dict[tuple[int, int], float]]:
    """Energy Trends Sep 2026 Table 5.1 (sheet 'Quarter'), All generating companies, TWh.

    Keys (year, quarter). 'nuclear_supplied' (5.1c), 'ps_generated' and
    'battery_generated' (5.1b). '[x]' (not available) is left out.
    """
    rows = _sheet(ET_51, "Quarter")
    out = {}
    for key, title, fuel in (("nuclear_supplied", "Table 5.1c", "Nuclear"),
                             ("ps_generated", "Table 5.1b", "Pumped storage"),
                             ("battery_generated", "Table 5.1b", "Battery storage")):
        t = _find(rows, title)
        hdr = rows[t + 1]
        r = _row(rows, t, "All generating companies", fuel)
        d = {}
        for h, v in zip(hdr[2:], r[2:]):
            if h is None or not isinstance(v, (int, float)):
                continue
            parts = str(h).split()[:3]      # 'Quarter 1 2002' (later ones add '[provisional]')
            if len(parts) != 3 or parts[0] != "Quarter":
                raise ValueError(f"Energy Trends 5.1 header moved: {h!r}")
            d[(int(parts[2]), int(parts[1]))] = float(v)
        out[key] = d
    return out


@lru_cache(maxsize=None)
def dukes_57_pumped_hydro() -> dict[int, float]:
    """DUKES 2026 Table 5.7.A, All generating companies, 'Pumped hydro', MW at end-December."""
    rows = _sheet(DUKES_57, "5.7")
    t = _find(rows, "Table 5.7.A Capacity by fuel")
    hdr = rows[t + 1]
    r = _row(rows, t, "All generating companies", "Pumped hydro")
    return {int(h): float(v) for h, v in zip(hdr[2:], r[2:])
            if h is not None and str(h).isdigit() and isinstance(v, (int, float))}


# --------------------------------------------------------------------------- kept plant

@lru_cache(maxsize=None)
def energy_trends_54_nuclear() -> dict[tuple[int, int], float]:
    """Energy Trends Sep 2026 Table 5.4 (sheet 'Month'), MPP nuclear supplied (net), TWh.

    Keys (year, month). Used only for its monthly shape.
    """
    rows = _sheet(ET_54, "Month")
    t = _find(rows, "Table 5.4 Electricity production and availability")
    hdr_i = next(i for i in range(t, t + 10) if rows[i][0] == "Month")
    hdr = [str(h).strip() if h else "" for h in rows[hdr_i]]
    if "Nuclear" not in hdr:
        raise ValueError(f"Energy Trends 5.4 header moved: {hdr[:8]}")
    j = hdr.index("Nuclear")
    out = {}
    for r in rows[hdr_i + 1:]:
        if not r[0] or not isinstance(r[j], (int, float)):
            continue
        d = datetime.strptime(str(r[0]).split("[")[0].strip(), "%B %Y")
        out[(d.year, d.month)] = float(r[j])
    return out


def nuclear_month_mw(year: int, shape: str = "monthly") -> dict[int, float]:
    """Mean nuclear output in each month, MW, totalling DUKES 5.6.E annual supplied (gross).

    shape 'monthly': shared by Energy Trends 5.4 monthly MPP nuclear; 'quarterly': by Energy
    Trends 5.1c quarterly nuclear, flat within each quarter (spec §4.1 as written).
    """
    annual_mwh = dukes_56()["nuclear_supplied"][year] * 1e3
    hours = {m: 0.0 for m in range(1, 13)}
    for r in read_neso(year):
        hours[r.day.month] += 0.5
    if shape == "monthly":
        et = energy_trends_54_nuclear()
        w = {m: et[(year, m)] for m in range(1, 13)}
        return {m: annual_mwh * w[m] / sum(w.values()) / hours[m] for m in w}
    if shape != "quarterly":
        raise ValueError(f"unknown nuclear shape {shape!r}")
    q = nuclear_quarter_mw(year)
    return {m: q[(m - 1) // 3 + 1] for m in range(1, 13)}


def nuclear_quarter_mw(year: int) -> dict[int, float]:
    """Mean nuclear output in each quarter, MW: DUKES annual supplied × ET quarterly share."""
    annual_gwh = dukes_56()["nuclear_supplied"][year]
    et = energy_trends_51()["nuclear_supplied"]
    q = {k: et[(year, k)] for k in (1, 2, 3, 4)}
    total = sum(q.values())
    hours = {k: 0 for k in q}
    for r in read_neso(year):
        hours[(r.day.month - 1) // 3 + 1] += 0.5
    return {k: annual_gwh * 1e3 * q[k] / total / hours[k] for k in q}


def pumped_storage_gwh(year: int) -> tuple[float, str]:
    """Annual pumped-storage generation (not batteries), GWh, and its source id."""
    if year <= 2016:
        return dukes_56()["storage_generated"][year], SRC_DUKES56 + " 5.6.B Energy storage"
    et = energy_trends_51()["ps_generated"]
    return sum(et[(year, q)] for q in (1, 2, 3, 4)) * 1e3, SRC_ET51 + " 5.1b Pumped storage"


def _is_bst(d: date) -> bool:
    """British Summer Time: last Sunday of March to last Sunday of October (day level)."""
    def last_sunday(month: int) -> date:
        x = date(d.year, month, 31)
        return date.fromordinal(x.toordinal() - (x.weekday() + 1) % 7)
    return last_sunday(3) <= d < last_sunday(10)


def peak_shave(load: list[float], energy_mwh: float, cap_mw: float) -> list[float]:
    """Output of a store that makes `energy_mwh` in the highest half-hours of `load`.

    Finds the level L with Σ min(cap, max(0, load − L)) × 0.5 h = energy, by bisection.
    Returns the store's output per half-hour, MW.
    """
    if energy_mwh <= 0:
        return [0.0] * len(load)
    if cap_mw * 0.5 * len(load) < energy_mwh:
        raise ValueError("pumped-storage energy exceeds capacity × hours")
    lo, hi = min(load) - cap_mw, max(load)
    for _ in range(100):
        mid = (lo + hi) / 2
        e = sum(min(cap_mw, max(0.0, x - mid)) for x in load) * 0.5
        lo, hi = (mid, hi) if e > energy_mwh else (lo, mid)
    return [min(cap_mw, max(0.0, x - hi)) for x in load]


# --------------------------------------------------------------------------- residual

@dataclass(frozen=True)
class ResidualHalfHour:
    """One half-hour of the demand-side residual. MW. Duck-types `residual.HalfHour.residual`."""
    day: date
    period: int
    nd: float
    station_load: float
    pumping: float
    exports: float
    imports: float
    embedded: float
    nuclear: float
    ps_gen: float

    @property
    def residual(self) -> float:
        return (self.nd + self.station_load + self.pumping + self.exports + self.embedded
                - self.imports - self.nuclear - self.ps_gen)

    @property
    def kept(self) -> float:
        """Kept output net of what kept plant takes back (pumping, exports): residual + kept = V + SL."""
        return self.nuclear + self.ps_gen - self.pumping + self.imports - self.exports

    @property
    def volume(self) -> float:
        """V for this half-hour: ND + embedded wind + embedded solar (spec §4.1)."""
        return self.nd + self.embedded


PS_RULES = ("annual_peak", "daily_peak", "flat", "day_shape")
# Default "day_shape": the best fit of the four rules to the 2016-2025 FUELHH residual
# (8 of 10 years inside every tolerance; see work/s20a-residual/notes.md). "annual_peak" is
# spec §4.1 as written and fails all 10 years. "flat" gives a ~1 GW higher peak (larger
# fossil fleet, smaller net-zero cost) but fits worse; it is the conservative switch.
DEFAULT_PS_RULE = "day_shape"


def place_pumped_storage(rows: tuple[NesoRow, ...], load: list[float], energy_mwh: float,
                         cap_mw: float, rule: str) -> list[float]:
    """Pumped-storage output per half-hour, MW, totalling `energy_mwh` over the year.

    - 'annual_peak' (spec §4.1 as written): in the year's highest-residual half-hours, up to
      capacity.
    - 'daily_peak': each day's share of the annual output is that day's share of NESO's
      measured pumping (stations pump at night for the next day), placed in that day's
      highest-residual half-hours up to capacity.
    - 'flat': the same output in every half-hour (no credit at the peak).
    - 'day_shape': in each half-hour, in proportion to how far the residual sits above that
      day's mean (stations generate on the day's peaks, a little every day), capped at
      capacity. Not in the spec; tried after the spec rule failed (see notes).
    """
    if rule == "annual_peak":
        return peak_shave(load, energy_mwh, cap_mw)
    if rule == "flat":
        return [energy_mwh / (0.5 * len(load))] * len(load)
    if rule == "day_shape":
        return _day_shape(rows, load, energy_mwh, cap_mw)
    if rule != "daily_peak":
        raise ValueError(f"unknown pumped-storage rule {rule!r}; one of {PS_RULES}")
    pump_total = sum(r.pumping for r in rows)
    if pump_total <= 0:
        raise ValueError("no NESO pumping recorded: daily_peak rule needs it")
    out = [0.0] * len(load)
    by_day: dict[date, list[int]] = {}
    for i, r in enumerate(rows):
        by_day.setdefault(r.day, []).append(i)
    for idx in by_day.values():
        e = energy_mwh * sum(rows[i].pumping for i in idx) / pump_total
        e = min(e, cap_mw * 0.5 * len(idx))
        for i, v in zip(idx, peak_shave([load[i] for i in idx], e, cap_mw)):
            out[i] = v
    return out


def _day_shape(rows, load: list[float], energy_mwh: float, cap_mw: float) -> list[float]:
    by_day: dict[date, list[int]] = {}
    for i, r in enumerate(rows):
        by_day.setdefault(r.day, []).append(i)
    w = [0.0] * len(load)
    for idx in by_day.values():
        mean = sum(load[i] for i in idx) / len(idx)
        for i in idx:
            w[i] = max(0.0, load[i] - mean)
    total = sum(w) * 0.5
    if total <= 0:
        raise ValueError("flat residual: day_shape rule has nothing to follow")
    return [min(cap_mw, energy_mwh * x / total) for x in w]


@lru_cache(maxsize=None)
def residual_neso_year(year: int, station_load: bool = True, ps_rule: str = DEFAULT_PS_RULE,
                       nuclear_shape: str = "monthly") -> tuple[ResidualHalfHour, ...]:
    """Half-hourly residual for a calendar year by the demand-side method (spec §4.1).

    `station_load` adds NESO's 500/600 MW (default on; off = spec §4.1 formula as written).
    `ps_rule` places pumped-storage output (see `place_pumped_storage`).
    `nuclear_shape` 'monthly' (Energy Trends 5.4) or 'quarterly' (5.1c), see `nuclear_month_mw`.
    """
    neso = read_neso(year)
    nuc = nuclear_month_mw(year, nuclear_shape)
    pre = []
    for r in neso:
        sl = (STATION_LOAD_BST if _is_bst(r.day) else STATION_LOAD_GMT) if station_load else 0.0
        pre.append((r, sl, nuc[r.day.month]))
    before_ps = [r.nd + sl + r.pumping + r.exports
                 + r.embedded_wind + r.embedded_solar - r.imports - n for r, sl, n in pre]
    ps_gwh, _ = pumped_storage_gwh(year)
    ps = place_pumped_storage(neso, before_ps, ps_gwh * 1e3, dukes_57_pumped_hydro()[year],
                              ps_rule)
    return tuple(ResidualHalfHour(
        day=r.day, period=r.period, nd=r.nd, station_load=sl, pumping=r.pumping,
        exports=r.exports, imports=r.imports,
        embedded=r.embedded_wind + r.embedded_solar, nuclear=n, ps_gen=p)
        for (r, sl, n), p in zip(pre, ps))


def load_duration(rows) -> list[float]:
    """Residual, MW, sorted high to low."""
    return sorted((r.residual for r in rows), reverse=True)


def _embedded_missing(year: int) -> bool:
    return any(r.embedded_missing for r in read_neso(year))


def _sources(year: int) -> str:
    return ";".join((SRC_NESO.format(year=year), SRC_FAQ, SRC_DUKES56, SRC_ET51, SRC_ET54,
                     SRC_DUKES57))


def residual_annual(station_load: bool = True) -> dict[int, dict]:
    """Annual residual energy and peak, 2002-2025, by the demand-side method.

    Each value: {'twh', 'peak_mw', 'station_load_twh', 'kept_twh', 'basis', 'source_id'}.
    basis is 'estimated' where NESO's embedded columns are blank for part of the year
    (2002-2010 for solar; 2002-2007 for wind), else 'modelled'.
    """
    out = {}
    for y in YEARS:
        rows = residual_neso_year(y, station_load)
        out[y] = {
            "twh": sum(r.residual for r in rows) / 2e6,
            "peak_mw": max(r.residual for r in rows),
            "station_load_twh": sum(r.station_load for r in rows) / 2e6,
            "kept_twh": sum(r.kept for r in rows) / 2e6,
            "basis": "estimated" if _embedded_missing(y) else "modelled",
            "source_id": _sources(y),
        }
    return out


def volume_annual() -> dict[int, dict]:
    """V(y), TWh, GB: ND + embedded wind + embedded solar summed over the year (spec §4.1).

    basis 'measured' where NESO gives all three columns all year, 'estimated' where embedded
    wind or solar is blank and taken as zero.
    """
    out = {}
    for y in YEARS:
        rows = read_neso(y)
        out[y] = {"twh": sum(r.nd + r.embedded_wind + r.embedded_solar for r in rows) / 2e6,
                  "basis": "estimated" if _embedded_missing(y) else "measured",
                  "source_id": SRC_NESO.format(year=y)}
    return out


def volume_monthly(year: int) -> dict[int, float]:
    """V(m), TWh, for each calendar month of the year (spec §5.1)."""
    m = {k: 0.0 for k in range(1, 13)}
    for r in read_neso(year):
        m[r.day.month] += (r.nd + r.embedded_wind + r.embedded_solar) / 2e6
    return m


# --------------------------------------------------------------------------- calibration

TOL_ENERGY, TOL_PEAK, TOL_LDC = 0.02, 0.03, 0.05     # spec §4.1 as first written ("strict")
# Spec §15.2 decision 2 (Richard, 11 Oct 2026, binding), stated openly on the methods page:
# "annual energy within 2%; residual peak within 4%; load-duration curve within 5% at every
# percentile from the 1st to the 99th (the single highest and lowest half-hours are excluded,
# because pre-2016 nuclear and pumped storage cannot be shaped to the half-hour). Station
# load included (as the 2016+ method does)."
TOL_PEAK_LOOSE = 0.04
LDC_PCT_LOOSE = range(1, 100)
CALIBRATION_RULES = ("loosened", "strict")
DEFAULT_CALIBRATION_RULE = "loosened"


def _percentile(ldc: list[float], p: int) -> float:
    """Value exceeded p% of the time (p = 0 is the peak, 100 the minimum)."""
    return ldc[min(len(ldc) - 1, round(p / 100 * (len(ldc) - 1)))]


MISMATCH_MW = 3000.0


def dropout_half_hours(fuel: dict, neso: tuple[NesoRow, ...]) -> set:
    """Half-hours where Elexon FUELHH and NESO disagree by more than 3 GW on the same total.

    FUELHH net transmission output (pumped storage and interconnectors net) should equal
    NESO ND plus station load (0.5-0.6 GW; `tests/test_residual.py` median 515-593 MW).
    Where they differ by more than 3 GW one file has a gap: e.g. FUELHH 24 Oct 2019 SP23 and
    2 Aug 2022 SP3-5 report interconnectors only, with every station at zero. `residual.py`
    reads such rows as real; the calibration leaves them out and reports how many (0.03-0.2%
    of each year).
    """
    nd = {(r.day, r.period): r.nd for r in neso}
    return {k for k, g in fuel.items()
            if k in nd and abs(sum(g.values()) - nd[k]) > MISMATCH_MW}


def calibrate(year: int, station_load: bool = True, ps_rule: str = DEFAULT_PS_RULE,
              nuclear_shape: str = "monthly", rule: str = DEFAULT_CALIBRATION_RULE) -> dict:
    """Compare the demand-side method with the FUELHH method (`residual.py`) for one year.

    The FUELHH residual is taken with Elexon OTHER replaced (`replace_other=True`), because
    spec §15 decision 7h replaces battery discharge and the demand-side method replaces
    everything that is not nuclear, pumped storage or an interconnector. Compared over the
    half-hours both sources hold.

    rule 'loosened' (default, spec §15.2 decision 2): energy 2%, peak 4%, load-duration
    curve 5% at percentiles 1-99. rule 'strict' (spec §4.1 as first written): energy 2%,
    peak 3%, load-duration curve 5% at every percentile 0-100. Both results are reported
    (`pass_strict`, `pass_loosened`); `pass` is the chosen rule's.
    """
    if rule not in CALIBRATION_RULES:
        raise ValueError(f"unknown calibration rule {rule!r}; one of {CALIBRATION_RULES}")
    from gascf.residual import read_fuelhh, residual_year
    fuel_rows, _ = residual_year(year, replace_other=True)
    ref = {(r.day, r.period): r.residual for r in fuel_rows}
    mine = {(r.day, r.period): r.residual for r in residual_neso_year(year, station_load, ps_rule, nuclear_shape)}
    dropouts = dropout_half_hours(read_fuelhh(year), read_neso(year))
    keys = sorted((set(ref) & set(mine)) - dropouts)
    a = sorted((mine[k] for k in keys), reverse=True)
    b = sorted((ref[k] for k in keys), reverse=True)
    e_a, e_b = sum(a) / 2e6, sum(b) / 2e6
    ldc_err = {p: _percentile(a, p) / _percentile(b, p) - 1 for p in range(0, 101)}
    worst_p = max(ldc_err, key=lambda p: abs(ldc_err[p]))
    res = {
        "year": year, "half_hours": len(keys), "fuelhh_dropouts": len(dropouts),
        "neso_twh": e_a, "fuelhh_twh": e_b, "energy_err": e_a / e_b - 1,
        "neso_peak_mw": a[0], "fuelhh_peak_mw": b[0], "peak_err": a[0] / b[0] - 1,
        "ldc_worst_pct": worst_p, "ldc_worst_err": ldc_err[worst_p],
        "ldc_worst_err_p1_p99": max((abs(ldc_err[p]) for p in range(1, 100))),
    }
    res["pass_energy"] = abs(res["energy_err"]) <= TOL_ENERGY
    strict_peak = abs(res["peak_err"]) <= TOL_PEAK
    strict_ldc = abs(res["ldc_worst_err"]) <= TOL_LDC
    loose_peak = abs(res["peak_err"]) <= TOL_PEAK_LOOSE
    loose_ldc = max(abs(ldc_err[p]) for p in LDC_PCT_LOOSE) <= TOL_LDC
    res["pass_strict"] = res["pass_energy"] and strict_peak and strict_ldc
    res["pass_loosened"] = res["pass_energy"] and loose_peak and loose_ldc
    res["rule"] = rule
    res["pass_peak"] = loose_peak if rule == "loosened" else strict_peak
    res["pass_ldc"] = loose_ldc if rule == "loosened" else strict_ldc
    res["pass"] = res["pass_energy"] and res["pass_peak"] and res["pass_ldc"]
    return res


@lru_cache(maxsize=None)
def _calibration_cached(years: tuple[int, ...], station_load: bool, rule: str) -> tuple[dict, ...]:
    return tuple(calibrate(y, station_load, rule=rule) for y in years)


def calibration_table(years=range(2016, 2026), station_load: bool = True,
                      rule: str = DEFAULT_CALIBRATION_RULE) -> list[dict]:
    return [dict(c) for c in _calibration_cached(tuple(years), station_load, rule)]


@lru_cache(maxsize=None)
def calibration_passes(station_load: bool = True, rule: str = DEFAULT_CALIBRATION_RULE) -> bool:
    """True only if every year 2016-2025 meets all three tolerances of `rule`.

    Spec §4.1: "If not, the pre-2016 years are not published." The annual outputs carry
    this as `publishable` for 2002-2015. Default rule: §15.2 decision 2 ('loosened').
    """
    return all(c["pass"] for c in calibration_table(station_load=station_load, rule=rule))


def residual_published(year: int) -> dict:
    """One year's residual summary with its publication flag (the interface for the parent).

    2016-2025: the engine's residual is `residual.py` (FUELHH); this module's figure is
    given for comparison and V(y). 2002-2015: this module, `publishable` = calibration result.
    """
    rows = residual_neso_year(year)
    return {
        "twh": sum(r.residual for r in rows) / 2e6,
        "peak_mw": max(r.residual for r in rows),
        "basis": "estimated" if _embedded_missing(year) else "modelled",
        "source_id": _sources(year),
        "publishable": True if year >= 2016 else calibration_passes(),
        "method": "neso_demand_side",
    }
