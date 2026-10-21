"""The "today" panel (spec §5, output P3): four numbers for one day, in p/kWh, plus SAP.

1. **Day-ahead market price**: Elexon BMRS Market Index Data, APX (APXMIDP), volume-weighted
   over every settlement period of the settlement date. Periods that are absent, or present
   with zero volume, are listed in `missing_periods` and the panel is flagged incomplete.
   A settlement date normally has 48 half-hours; 46 on the spring clock change and 50 on
   the autumn one (computed, not assumed).
2. **Pure gas cost of power, fleet A**: the running cost of today's gas fleet at today's gas
   price, spec §12: SAP / eta + variable O&M + gas transport. eta is the DUKES Table 5.10.C
   CCGT fleet efficiency (gross CV) for the latest year printed; variable O&M is CEPA/GHD's
   medium figure for an H-class CCGT (Table 3.5, 2024 prices, read from the stored report);
   transport is National Gas's NTS exit capacity + General Non-Transmission Services charges
   (gastransport.py), on the full-utilisation convention. The spec's own spot check uses a
   rounded £1/MWh for transport; `fleet_a_running(..., transport_gbp_mwh_e=1.0)` reproduces it.
3. **Pure gas cost of power, fleet B**: the full cost per MWh of an all-new fleet sized to
   the 2025 residual-demand curve, at today's SAP (fleetb.py, via breakeven.fleet_cost_fn).
   This is a whole-year cost at today's gas price, not a cost for today's demand.
4. **Fleet A with carbon**: (2) plus UK ETS allowance and Carbon Price Support on the CO2
   burned (carbon.py). The UK ETS Authority publishes a monthly average only; the latest
   published month at or before the day is used and the lag is reported.

"Pure gas price" is kept for the bill-level step 1 only (spec §5); here the words are
"pure gas cost of power".

Day boundaries: SAP is for the gas day (05:00 to 05:00); MID is for the settlement date
(00:00 to 24:00). The panel pairs SAP for gas day D with MID for settlement date D, as the
spec's spot check does, and says so in `notes`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parents[2]
RAW = ROOT / "data/raw"
CEPA_TXT = ROOT / ("research/2026-10-10-methods/src/https_assets_publishing_service_gov_uk_media_"
                   "696616c68d599f4c09e1ffae_unabated_gas_electricity_generation_costs_2025_pdf.txt")

SRC_MID = "elexon-mid-apx"
SRC_SAP = "nationalgas-sap-pubob603"
SRC_DUKES = "desnz-dukes-5.10-2026"
SRC_CEPA = "cepa-ghd-unabated-gas-costs-2025"
SRC_TRANSPORT = "nationalgas-charges-oct-2026"
SRC_CARBON = "ukets-ccm-table+hmrc-cps"
SRC_FLEETB = "desnz-egc2025-annexA+fleetb"

UNSOURCED = "UNSOURCED"


@lru_cache(maxsize=1)
def cepa_vom_existing(case: str = "medium") -> float:
    """CEPA/GHD (2025) Table 3.5, Generation Option 1 (CCGT H class), variable fee £/MWh,
    current estimate in 2024 prices. Read from the stored text of the report; the anchor
    label and the six-number row must match or this fails."""
    t = CEPA_TXT.read_text()
    m = re.search(r"Table 3\.5: Generation Option 1 . O&M Costs.*?Variable fee \(£MWh\) "
                  r"([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)", t, re.S)
    if m is None:
        raise ValueError("CEPA Table 3.5 layout changed: variable fee row not found")
    vals = [float(x) for x in m.groups()]           # Leigh Fisher 2016 L/M/H, current L/M/H
    return {"low": vals[3], "medium": vals[4], "high": vals[5]}[case]


@lru_cache(maxsize=1)
def dukes_eta_latest() -> tuple[int, float]:
    from .official import read_dukes_510
    eff = read_dukes_510(RAW / "DUKES_5.10.xlsx").ccgt_efficiency
    y = max(eff)
    return y, eff[y] / 100


def transport_gbp_mwh_e(eta: float, gas_year: str = "2026/27") -> float:
    """National Gas exit capacity (booked at full-load burn, so per kWh of gas burned at full
    utilisation it equals the daily rate) + General Non-Transmission Services commodity,
    £/MWh of electricity at efficiency eta."""
    from .gastransport import read_transport
    t = read_transport()[gas_year]
    return (t.exit_capacity_p_kwh_day + t.commodity_p_kwh) * 10 / eta


def gas_year_of(d: date) -> str:
    y = d.year if d.month >= 10 else d.year - 1
    return f"{y}/{(y + 1) % 100:02d}"


def fleet_a_running(sap_gbp_mwh: float, eta: float, vom: float, transport_gbp_mwh_e: float) -> float:
    """Running cost of existing gas plant, £/MWh of electricity (no carbon)."""
    return sap_gbp_mwh / eta + vom + transport_gbp_mwh_e


def periods_in_day(d: date) -> int:
    """Settlement periods in a GB settlement date: 48, or 46/50 on clock-change days."""
    tz = ZoneInfo("Europe/London")
    a = datetime(d.year, d.month, d.day, tzinfo=tz)
    b = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    return int((b.timestamp() - a.timestamp()) // 1800)


@dataclass(frozen=True)
class DayAhead:
    gbp_mwh: float | None
    n_periods: int
    expected: int
    missing_periods: tuple[int, ...]
    volume_mwh: float

    @property
    def complete(self) -> bool:
        return not self.missing_periods


def day_ahead(d: date, mid: dict | None = None) -> DayAhead:
    """Volume-weighted APX day-ahead price over all settlement periods of date d."""
    if mid is None:
        from .mid import read_mid
        mid = read_mid(d.year)
    n = periods_in_day(d)
    have = {sp: pv for (day, sp), pv in mid.items() if day == d}
    missing = tuple(sp for sp in range(1, n + 1) if sp not in have or have[sp][1] <= 0)
    used = [(p, v) for sp, (p, v) in have.items() if v > 0]
    vol = sum(v for _, v in used)
    price = sum(p * v for p, v in used) / vol if vol > 0 else None
    return DayAhead(price, len(used), n, missing, vol)


@dataclass(frozen=True)
class Figure:
    key: str
    p_per_kwh: float | None
    gbp_per_mwh: float | None
    basis: str
    source_id: str
    note: str = ""


@dataclass(frozen=True)
class TodayPanel:
    day: date
    sap: Figure
    day_ahead: Figure
    fleet_a: Figure
    fleet_b: Figure
    fleet_a_with_carbon: Figure
    missing_periods: tuple[int, ...]
    flags: tuple[str, ...]
    notes: tuple[str, ...] = field(default=())

    def as_dict(self) -> dict:
        def f(x: Figure) -> dict:
            return {"p_per_kwh": x.p_per_kwh, "gbp_per_mwh": x.gbp_per_mwh, "basis": x.basis,
                    "source_id": x.source_id, "note": x.note}
        return {"date": self.day.isoformat(), "sap": f(self.sap), "day_ahead": f(self.day_ahead),
                "fleet_a_pure_gas_cost_of_power": f(self.fleet_a),
                "fleet_b_pure_gas_cost_of_power": f(self.fleet_b),
                "fleet_a_with_carbon": f(self.fleet_a_with_carbon),
                "missing_periods": list(self.missing_periods), "flags": list(self.flags),
                "notes": list(self.notes)}


def _fig(key: str, gbp: float | None, basis: str, src: str, note: str = "") -> Figure:
    return Figure(key, None if gbp is None else gbp / 10, gbp, basis, src, note)


def today(d: date, fleet_b_fn=None, sap: dict | None = None, mid: dict | None = None) -> TodayPanel:
    """Build the panel for day d. Raises if SAP for d is not stored (never guessed)."""
    from .carbon import allowance_monthly_gbp, carbon_gbp_per_mwh_elec
    from .sap import sap_gbp_per_mwh

    sap = sap if sap is not None else sap_gbp_per_mwh()
    if d not in sap:
        raise KeyError(f"{UNSOURCED}: no SAP stored for gas day {d}")
    s = sap[d]
    flags: list[str] = []
    notes = ["SAP is for gas day D (05:00-05:00); day-ahead is for settlement date D (00:00-24:00)"]

    da = day_ahead(d, mid)
    if da.missing_periods:
        flags.append(f"day-ahead: {len(da.missing_periods)} of {da.expected} settlement periods "
                     f"missing or zero-volume: {list(da.missing_periods)}")
    if da.gbp_mwh is None:
        flags.append(f"day-ahead: {UNSOURCED}, no APX data for {d}")

    y_eta, eta = dukes_eta_latest()
    vom = cepa_vom_existing()
    tr = transport_gbp_mwh_e(eta, gas_year_of(d)) if gas_year_of(d) >= "2026/27" else None
    if tr is None:
        flags.append(f"transport: {UNSOURCED} before gas year 2026/27 (only Oct 2026 charges stored); "
                     "fleet A shown without it")
    fa = fleet_a_running(s, eta, vom, tr or 0.0)
    fa_note = (f"SAP / {eta:.4f} (DUKES 5.10.C {y_eta}, gross CV) + VOM £{vom:.2f} (CEPA/GHD Table 3.5, "
               f"2024 prices, not rebased) + transport £{(tr or 0):.2f} (National Gas, full utilisation)")

    allow = allowance_monthly_gbp(RAW)
    months = [m for m in allow if m <= (d.year, d.month)]
    if not months:
        raise KeyError(f"{UNSOURCED}: no allowance price at or before {d}")
    m = max(months)
    a_price, a_src = allow[m]
    lag = (d.year - m[0]) * 12 + d.month - m[1]
    if lag:
        flags.append(f"carbon: latest published {a_src} monthly average is {m[0]}-{m[1]:02d} "
                     f"(£{a_price:.2f}/t), {lag} month(s) before {d}")
    c = carbon_gbp_per_mwh_elec(a_price, d, eta)

    if fleet_b_fn is None:
        from .breakeven import fleet_cost_fn
        fleet_b_fn = fleet_cost_fn("B", money_year=d.year)
    fb = fleet_b_fn(s)

    return TodayPanel(
        day=d,
        sap=_fig("sap", s, "measured", SRC_SAP, "System Average Price, actual day, gross CV"),
        day_ahead=_fig("day_ahead", da.gbp_mwh, "measured", SRC_MID,
                       f"APXMIDP volume-weighted over {da.n_periods}/{da.expected} periods"),
        fleet_a=_fig("fleet_a", fa, "modelled", f"{SRC_SAP}+{SRC_DUKES}+{SRC_CEPA}+{SRC_TRANSPORT}", fa_note),
        fleet_b=_fig("fleet_b", fb, "modelled", f"{SRC_SAP}+{SRC_FLEETB}",
                     "full cost of an all-new fleet on the 2025 residual-demand curve at today's SAP"),
        fleet_a_with_carbon=_fig("fleet_a_with_carbon", fa + c, "modelled",
                                 f"{SRC_SAP}+{SRC_DUKES}+{SRC_CEPA}+{SRC_TRANSPORT}+{SRC_CARBON}",
                                 f"+ carbon £{c:.2f}/MWh ({a_src} £{a_price:.2f}/t {m[0]}-{m[1]:02d} + CPS)"),
        missing_periods=da.missing_periods, flags=tuple(flags), notes=tuple(notes))
