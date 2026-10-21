"""The All-gas Britain column of the household receipt, and the staircase (spec §2, §6).

For every Ofgem cap period (32, April 2015 to October-December 2026) and for fleet A or
fleet B, this module builds the receipt's second column, **All-gas Britain**, line for line
beside the actual column (`receipt_actual`), and splits the difference into the spec's steps:

    step 1   pure gas price      the whole all-gas Britain bill, no carbon, no policy levies
    step 2   carbon taxes        the carbon an all-gas Britain would pay (UK ETS/EU ETS + CPS);
                                 all-gas Britain itself pays no carbon price (Richard, 11 Oct 2026)
    step 3   other net-zero policy  ECO, Sizewell C (WHD, AAHEDC, EII levy: held equal, not net zero)
    step 4a  renewables subsidies  CfD, RO bill share, FiT, RO paid by the Treasury (Layer 2)
    step 4b  renewables grid     constraint cost above the 2017/18 baseline (current year: the
                                 trailing 12 months), offshore transmission, and the RIIO-3
                                 transmission step-up Ofgem attributes to net zero (low/high)
    step 4c  wholesale difference  the rest of the wholesale gap, net of carbon (and CM, fleet B)
    =        what you pay

**Identity (tested):** actual total = step 1 + 2 + 3 + 4a + 4b + 4c, every period, both fleets,
and for every line actual − all-gas = the sum of its step pieces.

How it is built (terms: *nil* = Ofgem's cap at zero consumption, the standing-charge part;
*typical* = the cap at Ofgem's benchmark consumption Q):

1. Everything is computed at Ofgem's own Q, typical and nil, then restated to any size by
   Ofgem's own linear rule, nil + (typical − nil) × c / Q (Annex 9 tab 1c). Each line carries
   `fixed_gbp` (the nil part) and `gbp_per_kwh` (the slope) so the site can restate it.
2. The staircase walks from the all-gas bill to the actual bill through sequential states,
   carbon first (§7.3): pure gas → +carbon → +other policy → +subsidies → +grid → +rest of
   wholesale = actual. A driver line (wholesale, a levy) changes in exactly one transition
   (wholesale in two: carbon → 2, the rest → 4c). The percentage lines (payment-method
   percentage, debt-related costs, EBIT, headroom) and VAT are recomputed with **Ofgem's own
   formulas**, read from the cap model's formula cells, at every state; what they change in a
   transition is that step's "pro rata" share. Because the states telescope, the identity is
   exact by construction, and the test checks it anyway.
3. Percentage lines are written as actual + f(state) − f(actual): f reproduces Ofgem's lines
   (tested to a few pence), and this delta form makes the actual state equal Ofgem's
   published figures exactly.

Wholesale, all-gas (spec §3, §5): fleet A or B cost per MWh at transmission, on Ofgem's gas
index for the period (Annex 2 tab 1b), → Ofgem's own uplift and GB-mean losses (the ratio of
Ofgem's GB-mean £/MWh supplied to its electricity index) → × consumption. Plant costs are DESNZ
2024 money: the gas index is rebased to 2024 with the HMT GDP deflator, the result back to the
period's year. Residual demand: the calendar year the period mostly falls in (ties go to the
start year); 2015 → 2016 and 2026 → 2025 (2026 is incomplete), flagged.

Carbon an all-gas Britain would pay (step 2): fleet(gas + carbon per MWh of gas) − fleet(gas),
so carbon goes through the same merit order and screening curve as fuel. Carbon per MWh of gas
= allowance £/t × 0.18194 t/MWh (gross CV) + CPS £/MWh, monthly, averaged over the period's
months (EU ETS before May 2021, UK ETS after: carbon.py). Months not yet published use the
latest published month, flagged.

Reversed order (P6): renewables first, then carbon. The carbon then added is the carbon inside
today's bill, on a cost basis: actual GB gas generation × carbon per MWh gas / DUKES η ÷ demand
(NESO national demand + embedded wind and solar). Coal carbon is not counted (no CO2 factor
for coal is stored), which lowers it in 2015-17 and makes the reversed renewables step larger.

Replaced generation = the subsidised set (spec §12): residual demand with wind, biomass,
hydro, embedded wind and solar replaced, coal and oil **kept** (`REPLACE_COAL_OIL = False`;
residual.py's default replaces them).

Fleet A: existing GB CCGT at the DUKES fleet efficiency for the year, variable O&M £5/MWh (the
figure the §8 validation margin was measured against, so the pair reproduces the market
price), plus the §8 gas-market margin (volume-weighted mean, `margin_stats`) for the matching year (nearest year for
2015-17, flagged). Capacity Market held equal (spec §3.3). Fleet B: all new, DESNZ EGC 2025
Annex A, no margin. Fleet B's Capacity Market: the gas share of DY 2026/27 agreements (Ofgem's
printed auction results, `cm_gas_share`) is removed; the rest is kept (spec §3.3). Both fleets: ECR 2026 central spare margin and de-rating, National Gas
2026/27 gas transport (rebased; earlier years have no stored charges, flagged).

Step 3 holds only ECO and Sizewell C, each tied to decarbonisation by a primary source (STEP3).
Warm Home Discount, AAHEDC and the EII levy are not net zero: held equal in both columns
(NOT_NET_ZERO; Richard, 11 Oct 2026).

Gas power cost is the reader's choice (Richard, 11 Oct 2026): fleet A, fleet B, or "D", DESNZ's
own estimate (EGC 2025 Annex A, CCGT 93% column, 2030, total less carbon, 2024 money).

Lines held equal (sit in step 1 on both sides and cancel), assigned explicitly in `HELD_EQUAL`:
backwardation, adjustment allowance (Ofgem Annex 8 true-up; no basis to change it in all-gas
Britain), levelisation (a transfer between suppliers' customers by payment method, net zero
across GB), Capacity Market (fleet A rule; fleet B see below), networks other than the two 4b
lines, operating costs, smart metering, industry charges, payment-method additional cost.

Basis: every line read from receipt_actual is an **Ofgem ex-ante allowance**, not outturn. The
staircase tags it `allowance` (BASIS_ALLOWANCE) whatever receipt_actual calls it, and never
`measured`; lines the staircase computes are `modelled` or `estimated`. The 4b lines are carved out of BSUoS (constraint
cost above baseline) and TNUoS (offshore transmission demand share), so nothing is counted twice;
where NESO data does not cover the financial year the line is null with its reason and the
cost stays inside BSUoS/TNUoS, held equal.

Layer 3 (goods) is attached beside the staircase (`layer3`), never inside its total.
The Energy Price Guarantee (Oct 2022 - Jun 2023) is not netted: the cap level is the all-in cost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

from . import receipt_actual as ra

ROOT = Path(__file__).parents[2]
RAW = ROOT / "data/raw"
ANNEX2 = ROOT / ("research/2026-10-10-methods/src/"
                 "Annex-2-wholesale-cost-allowance-methodology-v1.30_data_removed-2.xlsx")
CAP_MODEL = ra.CAP_MODEL

SRC_A2 = "ofgem-annex2-v1.30"
SRC_CAP = ra.SRC_CAP
SRC_FLEET = {"A": "desnz-egc2025-annexA; dukes-5.10; dukes-5.11; elexon-fuelhh+neso (residual); "
                  "elexon-mid-apx+nationalgas-sap (§8 margin); neso-ecr-2026; nationalgas-charges-oct-2026; "
                  "hmt-gdp-deflator-sep-2026",
             "B": "desnz-egc2025-annexA; elexon-fuelhh+neso (residual); neso-ecr-2026; "
                  "nationalgas-charges-oct-2026; hmt-gdp-deflator-sep-2026",
             "D": "desnz-egc2025-annexA; hmt-gdp-deflator-sep-2026"}
SRC_CARBON = "ukets-ccm-table / eex-eua-auctions+boe-fx; hmrc-cps; desnz-ghg-factors-2026"
UNSOURCED = "UNSOURCED"

REPLACE_COAL_OIL = False      # spec §12: replaced set = subsidised set; coal and oil are kept
REPLACE_HYDRO = True          # residual.py default (bracket there)
VOM_EXISTING = None           # filled lazily from validate.VOM_GBP_MWH (£5, 2024 prices)
RESIDUAL_YEARS = range(2016, 2026)   # complete years of FUELHH + NESO; 2026 is partial
MARGIN_YEARS = range(2018, 2027)     # §8 validation needs daily SAP (2018 on)

STEPS = ("1", "2", "3", "4a", "4b", "4c")
STEP_NAMES = {"1": "Pure gas price", "2": "Carbon taxes (UK ETS, Carbon Price Support; EU ETS before 2021)",
              "3": "Other net-zero policy charges (ECO, Sizewell C)", "4a": "Renewables: subsidies (bill and taxes)",
              "4b": "Renewables: grid costs", "4c": "Renewables: wholesale difference, net of "
                                                    "the carbon renewables avoid"}

# cap model rows 15-28 (Eastern), component codes in order
CODE_ROWS = ("DF", "CM", "AA", "PC", "NC", "OC", "SMNCC", "IC", "PAAC", "PAP", "CO", "DRC", "E", "H")
PCT = {"PAP": "payment_adjustment_pct", "DRC": "debt_related_costs", "E": "ebit", "H": "headroom"}
LINE_CODE = {
    "direct_fuel": "DF", "backwardation": "DF", "cfd": "DF", "capacity_market": "CM",
    "adjustment_allowance": "AA", "ro": "PC", "fit": "PC", "eco": "PC", "whd": "PC",
    "aahedc": "PC", "eii_levy": "PC", "sizewell_c": "PC", "tnuos": "NC", "duos": "NC",
    "bsuos": "NC", "constraint_difference": "NC", "ofto": "NC", "operating_costs": "OC",
    "core_operating_costs": "CO", "smart_meter": "SMNCC", "industry_charges": "IC",
    "payment_adjustment_cost": "PAAC", "payment_adjustment_pct": "PAP",
    "debt_related_costs": "DRC", "ebit": "E", "headroom": "H", "levelisation": None,
    "vat": None, "ro_treasury": None,
}
EXTRA_LINES = {
    "constraint_difference": ("Constraint payments above the 2017/18 baseline (inside BSUoS)", "network"),
    "ofto": ("Offshore transmission owners, demand share (inside TNUoS)", "network"),
    "grid_netzero": ("Transmission build-out Ofgem attributes to net zero (inside TNUoS)", "network"),
    "ro_treasury": ("Renewables Obligation paid by the Treasury (Layer 2, taxes)", "tax"),
}
# Step 3 keeps only policy charges a primary source ties to decarbonisation (Richard, 11 Oct 2026,
# decision 3; quotes in spec §6 and work/s15-richard-decisions/notes.md):
#   eco         DESNZ ECO4 guidance §1.2: "contribute to carbon reduction targets in the domestic sector"
#   sizewell_c  DESNZ SZC FID value-for-money assessment para 4: "required for a low cost, net zero
#               compliant energy system"
STEP3 = ("eco", "sizewell_c")
# Not net zero: you pay these either way. Held equal in both columns (step 1), shown as their own block.
#   whd       Warm Home Discount, a rebate for poorer households (Richard, 11 Oct 2026)
#   aahedc    help with grid costs in the north of Scotland (Richard, 11 Oct 2026)
#   eii_levy  DESNZ impact assessment 2024/62 para 52: proceeds "compensate eligible EIIs for a
#             proportion of the network charging costs element in their energy bills"
NOT_NET_ZERO = ("whd", "aahedc", "eii_levy")
HELD_EQUAL = ("backwardation", "capacity_market", "adjustment_allowance", "levelisation", "tnuos",
              "duos", "bsuos", "operating_costs", "core_operating_costs", "smart_meter",
              "industry_charges", "payment_adjustment_cost") + NOT_NET_ZERO   # step 1, equal in both
HELD_EQUAL_NOTE = {
    "adjustment_allowance": "step 1, held equal: Ofgem Annex 8 adjustment allowance (ex-ante true-up); "
                            "no basis for a different value in all-gas Britain",
    "levelisation": "step 1, held equal: payment-method levelisation nets to zero across GB",
    "backwardation": "step 1, held equal (spec §6)",
    "whd": "not net zero: held equal in both columns (Richard, 11 Oct 2026)",
    "aahedc": "not net zero: held equal in both columns (Richard, 11 Oct 2026)",
    "eii_levy": "not net zero: held equal; DESNZ IA 2024/62 para 52, proceeds compensate energy-intensive "
                "industry for network charges",
}
# Gas power cost, the reader's choice (Richard, 11 Oct 2026, decision 1):
#   "A" today's gas price, today's plants; "B" all-new fleet; "D" DESNZ's own estimate (EGC 2025
#   Annex A, CCGT 93% column, 2030, total less carbon, 2024 money, restated by the GDP deflator).
FLEET_IDS = ("A", "B", "D")
ETA_CASES = ("dukes", "new")              # fleet A existing-plant efficiency: DUKES year, or new-plant
CAPEX_CASES = ("low", "medium", "high")   # DESNZ EGC 2025 Annex A
HURDLE_CASES = ("low", "medium", "high")  # DESNZ EGC 2025 Table 7 (7.3% / 8.9% / 10.6%)
SRC_CM = "ofgem-cm-annual-report-2022-23; ofgem-cm-annual-report-2025-26"
CM_REPORTS = {"T-4": RAW / "ofgem_cm/Ofgem_CM_annual_report_2022-23.pdf",
              "T-1": RAW / "ofgem_cm/Ofgem_CM_annual_report_2025-26.pdf"}
BASIS_ALLOWANCE = "allowance"   # Ofgem ex-ante cap allowance, not outturn (wave-1 review B2)
STEP4A = ("cfd", "ro", "fit", "ro_treasury")
STEP4B = ("constraint_difference", "ofto", "grid_netzero")
GRID_CASES = ("low", "high")   # network_netzero bracket; low (= £0) is the cautious default
SUBSIDY_LINES = ("cfd", "ro", "fit", "ro_treasury")   # zero in all-gas Britain


# --------------------------------------------------------------------------- Ofgem's percentage formulas

@dataclass(frozen=True)
class PctRule:
    """value = sum(base components) x rate + const; or, for EBIT at nil consumption,
    sum(base) x (typical EBIT / typical EBIT base) (`ratio`)."""
    base: tuple[str, ...]
    rate: float = 0.0
    const: float = 0.0
    ratio: bool = False
    formula: str = ""


def _rows_to_codes(spec: str) -> tuple[str, ...]:
    out = []
    for a, b in re.findall(r"@(\d+):@(\d+)", spec):
        out += [CODE_ROWS[r - 15] for r in range(int(a), int(b) + 1)]
    return tuple(out)


def _parse(f, col: str, cell) -> PctRule | None:
    s = str(f).strip()
    if s in ("-", "None", ""):
        return None
    ext: list[float] = []

    def sub(m):
        ext.append(cell(m.group(1), m.group(2), int(m.group(3))))
        return "#"
    s = re.sub(r"'([^']+)'!\$?([A-Z]+)\$?(\d+)", sub, s).replace(" ", "")
    s = s.replace(f"ElecSingle_Other_Benchmark!{col}", "B@")
    s = re.sub(rf"(?<![A-Z$!@]){col}(\d+)", r"@\1", s)
    guard = r'IF\(@\d+="-","-",'
    if m := re.fullmatch(rf'={guard}SUM\(((?:@\d+:@\d+,?)+)\)\*#\)', s):
        return PctRule(_rows_to_codes(m.group(1)), rate=ext[0], formula=str(f))
    if m := re.fullmatch(rf'=\({guard}\(SUM\((@\d+:@\d+)\)\*#\)\+\(SUM\(\1\)\*#\)\+#\)\)', s):
        return PctRule(_rows_to_codes(m.group(1)), rate=ext[0] + ext[1], const=ext[2], formula=str(f))
    if m := re.fullmatch(rf'={guard}\(SUM\((@\d+:@\d+)\)\*#\)\+\(#/2\)\)', s):
        return PctRule(_rows_to_codes(m.group(1)), rate=ext[0], const=ext[1] / 2, formula=str(f))
    if m := re.fullmatch(rf'={guard}SUM\((@\d+:@\d+)\)\*\(B@27/SUM\(B@(\d+:@\d+)\)\)\)', s):
        if "@" + m.group(2) != m.group(1):
            raise ValueError(f"cap model EBIT nil formula moved: {f}")
        return PctRule(_rows_to_codes(m.group(1)), ratio=True, formula=str(f))
    raise ValueError(f"cap model percentage formula not recognised (column {col}): {f}")


@lru_cache(maxsize=1)
def percentage_rules() -> dict[tuple, dict[str, dict[str, PctRule | None]]]:
    """{period: {'typical'|'nil': {'PAP'|'DRC'|'E'|'H': PctRule}}} from the cap model's
    Eastern rows 24, 26, 27, 28 (every region carries the same formula; rates are uniform)."""
    wf = openpyxl.load_workbook(CAP_MODEL, read_only=True)
    wv = openpyxl.load_workbook(CAP_MODEL, read_only=True, data_only=True)
    cache: dict[str, list] = {}

    def cell(tab, colname, row):
        if tab not in cache:
            cache[tab] = list(wv[tab].iter_rows(max_row=80, max_col=60, values_only=True))
        v = cache[tab][row - 1][column_index_from_string(colname) - 1]
        if not isinstance(v, (int, float)):
            raise ValueError(f"cap model {tab}!{colname}{row} is {v!r}, expected a number")
        return float(v)

    out: dict = {}
    for tab, side in (("ElecSingle_Other_Benchmark", "typical"), ("ElecSingle_Other_Nil", "nil")):
        R = list(wf[tab].iter_rows(min_row=12, max_row=28, max_col=50, values_only=True))
        codes = [str(R[r - 12][2]).strip() for r in range(15, 29)]
        if codes != list(CODE_ROWS) or str(R[3][3]).strip() != "Eastern":
            raise ValueError(f"{tab} rows 15-28 moved: {codes}")
        last = max(r.period for r in ra.receipts())
        for k, j in ra._cols(R[0], 6).items():
            if k > last:
                continue          # future columns hold '-' inputs; not needed
            col = get_column_letter(j + 1)
            out.setdefault(k, {})[side] = {
                code: _parse(R[row - 12][j], col, cell)
                for code, row in (("PAP", 24), ("DRC", 26), ("E", 27), ("H", 28))}
    return out


def _rules_for(period) -> dict:
    rules = percentage_rules()
    if period in rules:
        return rules[period]
    raise KeyError(f"cap model has no column for {ra.label_of(period)}")


def apply_pct(vec: dict[str, tuple[float, float]], rules: dict) -> dict[str, tuple[float, float]]:
    """Ofgem's percentage lines for a bill vector {line: (typical, nil)}; returns {code: (t, n)}."""
    tot = {s: {c: 0.0 for c in CODE_ROWS} for s in (0, 1)}
    for key, tn in vec.items():
        c = LINE_CODE.get(key)
        if c and c not in PCT:
            for s in (0, 1):
                tot[s][c] += tn[s]
    out = {}
    for code in ("PAP", "DRC", "E", "H"):
        vals = [0.0, 0.0]
        for s, side in ((0, "typical"), (1, "nil")):
            r = rules[side][code]
            if r is None:
                continue
            base = sum(tot[s][c] for c in r.base)
            if r.ratio:
                rt = rules["typical"][code]
                tbase = sum(tot[0][c] for c in rt.base)
                vals[s] = base * (tot[0][code] / tbase) if tbase else 0.0
            else:
                vals[s] = base * r.rate + r.const
            tot[s][code] = vals[s]
        out[code] = (vals[0], vals[1])
    return out


# --------------------------------------------------------------------------- inputs per period

@lru_cache(maxsize=1)
def annex2_periods() -> dict[tuple, object]:
    from .ofgem import read_annex2, unique_periods
    return {ra.period_key(p.name): p for p in unique_periods(read_annex2(ANNEX2))}


def months_of(k: tuple) -> list[tuple[int, int]]:
    y, m = k[0], k[1]
    out = []
    while (y, m) <= (k[2], k[3]):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def price_year(k: tuple) -> int:
    """Calendar year the period mostly falls in; ties go to the start year."""
    ms = months_of(k)
    counts = {y: sum(1 for (yy, _) in ms if yy == y) for y in {y for y, _ in ms}}
    best = max(counts.values())
    return min(y for y, c in counts.items() if c == best)


def fy_of(k: tuple) -> int:
    """Financial year (April start) the period starts in."""
    return k[0] if k[1] >= 4 else k[0] - 1


def nearest(year: int, years) -> tuple[int, bool]:
    ys = list(years)
    if year in ys:
        return year, False
    return min(ys, key=lambda y: (abs(y - year), -y)), True


@lru_cache(maxsize=None)
def _ldc(year: int) -> tuple[float, ...]:
    from .residual import load_duration, residual_year
    rows, _ = residual_year(year, replace_coal_oil=REPLACE_COAL_OIL, replace_hydro=REPLACE_HYDRO)
    return tuple(load_duration(rows))


@lru_cache(maxsize=None)
def _actual_gas_share(year: int) -> float:
    """Actual gas generation / (NESO national demand + embedded wind and solar), the year."""
    from .residual import residual_year
    rows, _ = residual_year(year, replace_coal_oil=REPLACE_COAL_OIL, replace_hydro=REPLACE_HYDRO)
    return sum(r.gas_actual for r in rows) / sum(r.nd + r.embedded for r in rows)


@lru_cache(maxsize=None)
def margin_stats(year: int) -> dict[str, float]:
    """Spec §8 spread (day-ahead price − gas running cost, £/MWh) for one year, on the half-hours
    `validate.validate_year` keeps: median, mean and **volume-weighted mean** (weights = Elexon
    MID volume). Same loop and filters as validate_year (tested equal on the median)."""
    import statistics as stt
    from .carbon import CO2_T_PER_MWH_GAS_GCV, allowance_monthly_gbp, cps_gbp_per_mwh_gas
    from .mid import read_mid
    from .residual import read_fuelhh
    from .sap import sap_gbp_per_mwh
    from .validate import VOM_GBP_MWH, gas_day
    sap, allow = sap_gbp_per_mwh(), allowance_monthly_gbp(RAW)
    d = _dukes_eta()
    eta = d.get(year, d[max(d)])
    mid, fuel = read_mid(year), read_fuelhh(year)
    sp, w = [], []
    for kk, g in fuel.items():
        if kk not in mid:
            continue
        price, vol = mid[kk]
        if vol <= 0 or g.get("CCGT", 0) < 10_000 or g.get("COAL", 0) >= 1_000:
            continue
        gd = gas_day(*kk)
        a = allow.get((kk[0].year, kk[0].month))
        if gd not in sap or a is None:
            continue
        cost = (sap[gd] + a[0] * CO2_T_PER_MWH_GAS_GCV + cps_gbp_per_mwh_gas(kk[0])) / eta + VOM_GBP_MWH
        sp.append(price - cost)
        w.append(vol)
    return {"n": len(sp), "median": stt.median(sp), "mean": stt.mean(sp),
            "vw_mean": sum(a * b for a, b in zip(sp, w)) / sum(w)}


# Gas-market margin statistic (spec §3 "the average gap"; decided 11 Oct 2026): the volume-weighted
# mean. It is the highest of median / mean / volume-weighted mean, so it gives fleet A the dearest
# all-gas column and the smallest gap: the conservative choice. The others are sensitivities.
MARGIN_STAT = "vw_mean"
PLANT_MONEY_YEAR = 2024         # DESNZ EGC 2025 Annex A costs are in 2024 prices
CACHE_DP = 9                    # round float cache keys to 9 dp so equal inputs share one entry
BREAK_EVEN_CEILING_GBP_MWH = 300.0   # spec §9: highest gas price searched (breakeven default)
FEEDBACK_CEILING = 3.0          # spec §7.4: gas-price rises searched, up to +300%
MARGIN_CASES = ("vw_mean", "mean", "median")


@lru_cache(maxsize=None)
def _margin(year: int, stat: str = MARGIN_STAT) -> float:
    return margin_stats(year)[stat]


@lru_cache(maxsize=1)
def cm_gas_share() -> dict:
    """Share of Capacity Market agreements for delivery year 2026/27 held by gas, from the two
    auctions for that year, as printed by Ofgem (T-4 held 2022/23; T-1 held 2025/26). Capacity
    share and payment share (de-rated GW × clearing price; CPI indexation ignored). Agreements
    from earlier auctions that run into 2026/27 (multi-year new-build terms) are not printed by
    technology in these reports and are left out."""
    import pymupdf
    pats = {"T-4": (r"2022/23 T-4 Auction cleared at a price of £(\d+\.\d+)/kW/year and a total of "
                    r"approximately (\d+\.\d+) ?GW.{0,400}?Gas CMUs gained the.{0,400}?most De-rated "
                    r"Capacity in the Auction at approximately (\d+\.\d+) ?GW"),
            "T-1": (r"2026/27 T-1 Auction cleared at a price of £(\d+\.\d+)/kW/year and a total of "
                    r"(\d+\.\d+) ?GW.{0,300}?followed by Gas CMUs, which secured (\d+\.\d+) ?GW")}
    rows = {}
    for auction, path in CM_REPORTS.items():
        text = " ".join(" ".join(pg.get_text() for pg in pymupdf.open(path)).split())
        m = re.search(pats[auction], text)
        if not m:
            raise ValueError(f"CM report {path.name}: {auction} result for DY 2026/27 not found")
        rows[auction] = {"price_gbp_kw_yr": float(m.group(1)), "total_gw": float(m.group(2)),
                         "gas_gw": float(m.group(3))}
    cap = sum(r["gas_gw"] for r in rows.values()) / sum(r["total_gw"] for r in rows.values())
    pay = (sum(r["gas_gw"] * r["price_gbp_kw_yr"] for r in rows.values())
           / sum(r["total_gw"] * r["price_gbp_kw_yr"] for r in rows.values()))
    return {"delivery_year": "2026/27", "auctions": rows, "capacity_share": cap, "payment_share": pay,
            "used": min(cap, pay), "source_id": SRC_CM,
            "note": "lower of capacity and payment share (be conservative); agreements from earlier "
                    "auctions running into 2026/27 are not split by technology in these reports"}


def _plant_case(p, capex: str):
    """The same DESNZ plant with its 'medium' capital costs set to the `capex` case, so the
    fleet models (which read the medium case) cost the chosen case."""
    from dataclasses import replace
    if capex == "medium":
        return p
    return replace(p, predev_gbp_kw={**p.predev_gbp_kw, "medium": p.predev_gbp_kw[capex]},
                   construction_gbp_kw={**p.construction_gbp_kw, "medium": p.construction_gbp_kw[capex]},
                   infrastructure_gbp_k={**p.infrastructure_gbp_k, "medium": p.infrastructure_gbp_k[capex]})


@lru_cache(maxsize=1)
def _dukes_eta() -> dict[int, float]:
    from .official import read_dukes_510
    return {y: v / 100 for y, v in read_dukes_510(RAW / "DUKES_5.10.xlsx").ccgt_efficiency.items()}


@lru_cache(maxsize=1)
def _fleet_kit():
    from .capacity import margin_fraction, read_derating
    from .deflator import rebase
    from .fleeta import read_existing_gb_gas
    from .gastransport import GasTransport, read_transport
    from .official import read_desnz_plants
    from .validate import VOM_GBP_MWH
    pl = read_desnz_plants(RAW / "DESNZ_EGC2025_AnnexA.xlsx")
    t = read_transport()["2026/27"]
    k = rebase(1.0, 2026, 2024)
    return dict(ccgt=pl[("Gas CCGT 93% Load Factor", 2030)], ocgt=pl[("Gas OCGT 760MW 30% Load Factor", 2030)],
                margin=margin_fraction("central"), derating=read_derating(), existing=read_existing_gb_gas(),
                transport=GasTransport(t.gas_year, t.exit_capacity_p_kwh_day * k, t.commodity_p_kwh * k),
                vom=VOM_GBP_MWH)


@lru_cache(maxsize=None)
def fleet_gbp_mwh(fleet: str, ldc_year: int, gas24: float, margin24: float = 0.0, eta: float = 0.0,
                  capex: str = "medium", hurdle: str = "medium") -> float:
    """Fleet cost per MWh at transmission, 2024 money, no carbon unless it is inside gas24.
    `capex` and `hurdle` pick DESNZ's low / medium / high case for every new plant."""
    from .fleeta import cost_fleet_a
    from .fleetb import cost_fleet_b
    kit = _fleet_kit()
    ldc = list(_ldc(ldc_year))
    ccgt, ocgt = _plant_case(kit["ccgt"], capex), _plant_case(kit["ocgt"], capex)
    if fleet == "A":
        return cost_fleet_a(ldc, gas24, eta, kit["vom"], margin24, kit["existing"], ccgt,
                            ocgt, kit["margin"], kit["derating"],
                            transport=kit["transport"], hurdle=hurdle).gbp_per_mwh
    if fleet == "B":
        return cost_fleet_b(ldc, gas24, ccgt, ocgt, kit["margin"], hurdle=hurdle,
                            derating=kit["derating"], transport=kit["transport"]).gbp_per_mwh
    raise ValueError(f"fleet must be 'A' or 'B', not {fleet!r}")


@lru_cache(maxsize=1)
def desnz_gas_power_2024() -> dict:
    """Decision 1(a): DESNZ's own cost of gas power, EGC 2025 Annex A, 'Gas CCGT 93% Load
    Factor', 2030, total less carbon, £/MWh 2024 money (no gas transport line: DESNZ has none)."""
    from .sensitivity import DESNZ_COLUMN, DESNZ_YEAR, desnz_printed
    pr = desnz_printed()
    return {"gbp_mwh_2024": pr["Total"] - pr["Carbon costs"], "total": pr["Total"],
            "carbon": pr["Carbon costs"], "fuel": pr["Fuel costs"], "column": DESNZ_COLUMN,
            "year": DESNZ_YEAR, "source_id": "desnz-egc2025-annexA"}


@lru_cache(maxsize=1)
def _allowances():
    from .carbon import allowance_monthly_gbp
    return allowance_monthly_gbp(RAW)


def carbon_per_mwh_gas(k: tuple) -> tuple[float, str, list[str]]:
    """Mean over the period's months of allowance £/t x CO2 factor + CPS, £ per MWh of gas
    burned (gross CV), nominal; plus the allowance tag(s) and notes."""
    from .carbon import CO2_T_PER_MWH_GAS_GCV, cps_gbp_per_mwh_gas
    allow = _allowances()
    latest = max(allow)
    vals, tags, notes, lagged = [], set(), [], []
    for (y, m) in months_of(k):
        if (y, m) in allow:
            a, tag = allow[(y, m)]
        else:
            if (y, m) < min(allow):
                raise KeyError(f"no allowance price for {y}-{m:02d}")
            a, tag = allow[latest]
            lagged.append(f"{y}-{m:02d}")
        tags.add(tag)
        vals.append(a * CO2_T_PER_MWH_GAS_GCV + cps_gbp_per_mwh_gas(date(y, m, 1)))
    if lagged:
        notes.append(f"carbon: allowance price not yet published for {', '.join(lagged)}; latest "
                     f"published month {latest[0]}-{latest[1]:02d} used (estimated)")
    return sum(vals) / len(vals), "+".join(sorted(tags)), notes


# --------------------------------------------------------------------------- output types

@dataclass(frozen=True)
class StairLine:
    key: str
    label: str
    group: str
    step: str                      # '1', '2', '3', '4a', '4b', '4c', '2+4c' or 'pro rata'
    actual: float                  # £/household/yr at the staircase's consumption
    all_gas: float
    actual_fixed_gbp: float        # nil (standing-charge) part, £/yr
    actual_gbp_per_kwh: float      # slope, £/kWh
    all_gas_fixed_gbp: float
    all_gas_gbp_per_kwh: float
    by_step: dict[str, float]      # actual − all_gas, split by step (£/yr)
    by_step_fixed_gbp: dict[str, float]
    by_step_gbp_per_kwh: dict[str, float]
    basis_actual: str
    basis_all_gas: str
    source_id: str
    note: str = ""


@dataclass(frozen=True)
class Staircase:
    period: tuple[int, int, int, int]
    label: str
    fleet: str
    order: str                     # 'carbon_first' (headline) or 'renewables_first' (reversed)
    kwh: float
    ofgem_kwh: float
    vat_rate: float
    lines: tuple[StairLine, ...]
    steps: dict[str, float]        # '1' = all-gas bill; others the increments; sum = actual
    actual_total: float
    all_gas_total: float
    inputs: dict
    nulls: tuple[tuple[str, str], ...]      # lines that could not be sourced, with the reason
    layer3: dict                   # goods, beside the headline, never inside it
    notes: tuple[str, ...] = field(default=())

    def line(self, key: str) -> StairLine:
        for ln in self.lines:
            if ln.key == key:
                return ln
        raise KeyError(key)

    @property
    def identity_residual(self) -> float:
        return self.actual_total - sum(self.steps.values())

    @property
    def renewables(self) -> float:
        return self.steps["4a"] + self.steps["4b"] + self.steps["4c"]


# --------------------------------------------------------------------------- the build

@lru_cache(maxsize=None)
def _core(k: tuple, fleet: str, order: str, grid: str = "low", eta_case: str = "dukes",
          capex: str = "medium", hurdle: str = "medium", gas_mult: float = 1.0,
          margin_stat: str = MARGIN_STAT):
    """Everything at Ofgem's own consumption: vectors {line: (typical, nil)} per state.
    `gas_mult` raises the gas price on the all-gas side only (spec §7.4 feedback threshold)."""
    from .deflator import rebase
    if fleet not in FLEET_IDS:
        raise ValueError(f"fleet must be one of {FLEET_IDS}, not {fleet!r}")
    if (eta_case not in ETA_CASES or capex not in CAPEX_CASES or hurdle not in HURDLE_CASES
            or margin_stat not in MARGIN_CASES):
        raise ValueError(f"switch out of range: eta {eta_case}, capex {capex}, hurdle {hurdle}, "
                         f"margin {margin_stat}")
    r = ra.receipt(k)
    p = annex2_periods()[k]
    Q, py, fy = r.consumption_mwh, price_year(k), fy_of(k)
    notes: list[str] = list(r.notes)
    nulls: list[tuple[str, str]] = []
    if r.epg_in_force:
        notes.append("Energy Price Guarantee in force: the cap level is kept as the all-in cost; "
                     "what the Treasury paid is a note only (taxes.epg_note), not in the staircase")
    act = {ln.key: (ln.typical, ln.nil) for ln in r.lines if ln.key != "vat"}
    meta = {ln.key: ln for ln in r.lines}

    # ---- 4b carve-outs from BSUoS / TNUoS
    from .system_costs import constraint_per_household_current, ofto_demand_share
    from .network_netzero import grid_netzero_per_household
    constraint_basis = None
    try:
        c = constraint_per_household_current(fy, price_year=py)
        c_mwh = c["difference_per_2500kwh"].value / 2.5
        constraint_basis = c["difference_per_2500kwh"].basis
        act["constraint_difference"] = (c_mwh * Q, 0.0)
        act["bsuos"] = (act["bsuos"][0] - c_mwh * Q, act["bsuos"][1])
        if act["bsuos"][0] < 0:
            notes.append("constraint difference exceeds Ofgem's BSUoS allowance (generators paid half "
                         "of BSUoS before April 2023; part of the cost sat in wholesale)")
        when = (f"trailing 12 months {c['window'].note}" if "window" in c
                else f"NESO FY {fy}/{(fy + 1) % 100:02d}")
        notes.append(f"constraint difference: {when}, in {py} prices, "
                     f"£{c_mwh:.3f}/MWh of final consumption")
    except (KeyError, ValueError) as e:
        nulls.append(("constraint_difference", f"{e}; cost stays inside BSUoS, held equal"))
    try:
        o = ofto_demand_share(fy)["per_household"].value
        act["ofto"] = (o, o)
        act["tnuos"] = (act["tnuos"][0] - o, act["tnuos"][1] - o)
        if act["tnuos"][1] < 0:
            notes.append("OFTO demand share exceeds Ofgem's TNUoS standing charge")
        notes.append(f"offshore transmission: NESO TNUoS {fy}/{(fy + 1) % 100:02d} demand share, "
                     "per domestic site, estimated, nominal")
    except (KeyError, ValueError) as e:
        nulls.append(("ofto", f"{e}; cost stays inside TNUoS, held equal"))
    if grid not in GRID_CASES:
        raise ValueError(f"grid must be one of {GRID_CASES}")
    grid_bracket = None
    try:
        g = grid_netzero_per_household(fy, price_year=py)
        grid_bracket = (g.low, g.high)
        if g.low is None:
            nulls.append(("grid_netzero", f"{g.note}"))
        else:
            gv = g.pick(grid)
            act["grid_netzero"] = (gv, gv)          # a standing-charge (per household) amount
            act["tnuos"] = (act["tnuos"][0] - gv, act["tnuos"][1] - gv)
            if act["tnuos"][1] < 0:
                notes.append("net-zero transmission step-up exceeds Ofgem's TNUoS standing charge")
            notes.append(f"grid build-out ({grid} case): £{gv:.2f}/household/yr in {py} prices; "
                         f"bracket £{g.low:.2f} to £{g.high:.2f} (Ofgem RIIO-3 FD IA Table 3; "
                         "estimated)")
    except (KeyError, ValueError) as e:
        nulls.append(("grid_netzero", f"{e}; cost stays inside TNUoS, held equal"))

    # ---- Layer 2: RO paid by the Treasury (from April 2026)
    if (k[0], k[1]) >= (2026, 4):
        from .taxes import ro_treasury
        t = ro_treasury(p.name)["ro_treasury_mwh"].value
        act["ro_treasury"] = (t * Q, 0.0)

    # ---- wholesale: all-gas Britain
    ul = sum(p.supplied.values()) / len(p.supplied) / p.elec_index
    D = act["direct_fuel"][0]
    to24, back = rebase(1.0, py, 2024), rebase(1.0, 2024, py)
    ldc_year, ldc_flag = nearest(py, RESIDUAL_YEARS)
    if ldc_flag:
        notes.append(f"residual demand: {py} not available, {ldc_year} used (flagged)")
    eta_year, eta_flag = nearest(py, _dukes_eta())
    eta = _dukes_eta()[eta_year]
    if eta_flag:
        notes.append(f"DUKES CCGT efficiency: {py} not printed, {eta_year} used")
    eta_fleet = _fleet_kit()["ccgt"].efficiency_gcv if eta_case == "new" else eta
    margin = 0.0
    margin_year = None
    if fleet == "A":
        margin_year, mflag = nearest(py, MARGIN_YEARS)
        margin = _margin(margin_year, margin_stat)
        if mflag:
            notes.append(f"gas-market margin: no §8 validation for {py} (daily SAP from 2018); "
                         f"{margin_year} {margin_stat} used (flagged)")
        elif margin_year == 2026:
            notes.append("gas-market margin: 2026 validation covers a part year")
    cpm, ctag, cnotes = carbon_per_mwh_gas(k)
    notes += cnotes
    g24 = p.gas_index * to24 * gas_mult
    m24 = rebase(margin, py, 2024) if fleet == "A" else 0.0
    eta_arg = eta_fleet if fleet == "A" else 0.0
    if fleet == "D":
        # DESNZ's own figure in place of the fleet cost: no merit order, no transport line, its
        # own 2030 gas price. Carbon (step 2) at the same plant's efficiency, today's carbon price.
        dz = desnz_gas_power_2024()
        F = (dz["gbp_mwh_2024"] + dz["fuel"] * (gas_mult - 1)) * back
        Fc = F + cpm / _fleet_kit()["ccgt"].efficiency_gcv
        notes.append(f"gas power cost: DESNZ EGC 2025 Annex A, {dz['column']} {dz['year']}, total "
                     f"£{dz['total']:.0f} less carbon £{dz['carbon']:.0f} = £{dz['gbp_mwh_2024']:.0f}/MWh "
                     f"(2024 money), restated to {py} money; DESNZ's figure has no gas pipeline "
                     "charges and its own 2030 gas price")
    else:
        F = fleet_gbp_mwh(fleet, ldc_year, round(g24, 9), round(m24, 9), eta_arg, capex, hurdle) * back
        Fc = fleet_gbp_mwh(fleet, ldc_year, round(g24 + cpm * to24, 9), round(m24, 9), eta_arg,
                           capex, hurdle) * back
    W_pure, C_ag = F * ul * Q, (Fc - F) * ul * Q
    C_act = cpm / eta * _actual_gas_share(ldc_year) * ul * Q
    if fleet != "D" and (py >= 2026 or py < 2018):
        notes.append("gas transport: National Gas 2026/27 charges rebased by the GDP deflator "
                     "(no stored charges for other gas years)")

    # ---- all-gas drivers and the transitions
    pct_keys = set(PCT.values())
    drivers = [kk for kk in act if kk not in pct_keys]
    ag = dict(act)
    ag["direct_fuel"] = (W_pure, 0.0)
    step3 = STEP3
    for kk in step3 + STEP4A + STEP4B:
        if kk in ag:
            ag[kk] = (0.0, 0.0)
    # Capacity Market, spec §3.3. Fleet A: held equal (it pays the existing fleet). Fleet B: its
    # £/MWh already pays the full fixed cost of the gas plant, spare included, so the CM paid to
    # gas plant is removed; CM paid to everything else (nuclear, interconnectors, storage, demand
    # response) is kept. Gas share: Ofgem's printed DY 2026/27 auction results (cm_gas_share);
    # the removed part falls in 4(c) with wholesale. DESNZ's figure ("D") is one plant with no
    # spare capacity, so the CM, which pays for spare capacity, is held equal (be conservative).
    cm_in_4c = fleet == "B" and "capacity_market" in ag
    cm_share = None
    if cm_in_4c:
        cm_share = cm_gas_share()
        keep = 1.0 - cm_share["used"]
        ag["capacity_market"] = (act["capacity_market"][0] * keep, act["capacity_market"][1] * keep)
        if (k[0], k[1]) < (2026, 10) or (k[2], k[3]) > (2027, 9):
            notes.append(f"Capacity Market gas share: delivery year 2026/27 share "
                         f"({cm_share['used']:.1%}) used for this period (other years not read)")
    restore = lambda keys: {kk: act[kk] for kk in keys if kk in act}
    wholesale_keys = ["direct_fuel"] + (["capacity_market"] if cm_in_4c else [])
    if order == "carbon_first":
        trans = [("2", {"direct_fuel": (W_pure + C_ag, 0.0)}), ("3", restore(step3)),
                 ("4a", restore(STEP4A)), ("4b", restore(STEP4B)), ("4c", restore(wholesale_keys))]
    elif order == "renewables_first":
        trans = [("3", restore(step3)), ("4a", restore(STEP4A)), ("4b", restore(STEP4B)),
                 ("4c", {"direct_fuel": (D - C_act, 0.0), **restore(wholesale_keys[1:])}),
                 ("2", restore(["direct_fuel"]))]
    else:
        raise ValueError(order)

    rules = _rules_for(k)
    f_act = apply_pct(act, rules)

    def full(state: dict) -> dict:
        v = {kk: state[kk] for kk in drivers}
        fs = apply_pct(v, rules)
        for code, key in PCT.items():
            v[key] = tuple(act[key][s] + fs[code][s] - f_act[code][s] for s in (0, 1))
        bill = [kk for kk in v if kk != "ro_treasury"]
        v["vat"] = tuple(r.vat_rate * sum(v[kk][s] for kk in bill) for s in (0, 1))
        return v

    states = [full(ag)]
    cur = dict(ag)
    for step, change in trans:
        cur.update(change)
        states.append(full(cur))
    final = states[-1]
    vat_act = meta["vat"]
    if abs(final["vat"][0] - vat_act.typical) > 1e-6:
        raise ValueError(f"{r.label}: recomputed VAT {final['vat'][0]} != receipt {vat_act.typical}")
    inputs = dict(
        gas_index_gbp_mwh=p.gas_index, elec_index_gbp_mwh=p.elec_index, uplift_losses=ul,
        price_year=py, ldc_year=ldc_year, fleet_gbp_mwh=F, fleet_with_carbon_gbp_mwh=Fc,
        carbon_per_mwh_gas=cpm, carbon_tag=ctag, carbon_all_gas_gbp_mwh=Fc - F,
        carbon_in_actual_bill_gbp_mwh=cpm / eta * _actual_gas_share(ldc_year),
        actual_gas_share=_actual_gas_share(ldc_year), eta_existing=eta,
        gas_market_margin_gbp_mwh=margin if fleet == "A" else None, margin_year=margin_year,
        consumption_mwh=Q, financial_year=fy,
        all_gas_wholesale_at_q=W_pure, carbon_all_gas_at_q=C_ag, carbon_actual_at_q=C_act,
        actual_wholesale_at_q=D, grid_case=grid,
        grid_netzero_low=grid_bracket[0] if grid_bracket else None,
        grid_netzero_high=grid_bracket[1] if grid_bracket else None,
        constraint_basis=constraint_basis,
        eta_case=eta_case, eta_used=eta_fleet if fleet == "A" else None, capex_case=capex,
        hurdle_case=hurdle, gas_mult=gas_mult, margin_stat=margin_stat if fleet == "A" else None,
        cm_gas_share=cm_share["used"] if cm_share else None,
        desnz_gbp_mwh_2024=desnz_gas_power_2024()["gbp_mwh_2024"] if fleet == "D" else None,
    )
    return dict(r=r, Q=Q, act=act, states=states, trans=trans, meta=meta, notes=notes,
                nulls=nulls, inputs=inputs, ag=ag, cm_in_4c=cm_in_4c)


def staircase(period, fleet: str = "A", kwh: float | None = 2500.0, order: str = "carbon_first",
              grid: str = "low", eta: str = "dukes", capex: str = "medium", hurdle: str = "medium",
              gas_mult: float = 1.0, margin: str = MARGIN_STAT) -> Staircase:
    """The receipt's two columns and the staircase for one cap period.

    kwh=None gives Ofgem's own benchmark consumption for the period. ``grid`` picks the end of
    the network_netzero bracket counted in 4(b): "low" (default, cautious) or "high". ``fleet``
    is the gas power cost: "A", "B" or "D" (DESNZ's own estimate). ``eta`` (fleet A existing
    plant: "dukes" or "new"), ``capex`` and ``hurdle`` (DESNZ low/medium/high) are the P6
    switches; ``margin`` (fleet A: "vw_mean" default, "mean", "median") picks the §8 statistic;
    ``gas_mult`` raises the gas price on the all-gas side only (spec §7.4)."""
    k = period if isinstance(period, tuple) else ra.period_key(period)
    c = _core(k, fleet, order, grid, eta, capex, hurdle, round(float(gas_mult), 9), margin)
    r, Q, states, trans = c["r"], c["Q"], c["states"], c["trans"]
    kwh_ = Q * 1000 if kwh is None else float(kwh)
    fq = (kwh_ / 1000) / Q

    def at(tn):
        return tn[1] + (tn[0] - tn[1]) * fq

    def slope(tn):
        return (tn[0] - tn[1]) / (Q * 1000)

    keys = list(states[0])
    order_keys = list(ra.LINES) + [kk for kk in EXTRA_LINES]
    keys.sort(key=lambda kk: order_keys.index(kk) if kk in order_keys else 999)
    pct_keys = set(PCT.values()) | {"vat"}
    lines = []
    for kk in keys:
        pieces = {s: (0.0, 0.0) for s in STEPS[1:]}
        for i, (step, _) in enumerate(trans):
            a, b = states[i][kk], states[i + 1][kk]
            pieces[step] = (pieces[step][0] + b[0] - a[0], pieces[step][1] + b[1] - a[1])
        nz = [s for s, tn in pieces.items() if abs(tn[0]) > 1e-12 or abs(tn[1]) > 1e-12]
        if kk in pct_keys:
            step = "pro rata"
        elif kk == "direct_fuel":
            step = "2+4c"
        else:
            declared = ("3" if kk in STEP3 else "4a" if kk in STEP4A else "4b" if kk in STEP4B
                        else "4c" if (kk == "capacity_market" and c.get("cm_in_4c")) else "1")
            # a zero line (e.g. ECO from Apr 2026) keeps the step it is assigned to
            step = nz[0] if len(nz) == 1 else (declared if not nz else "+".join(nz))
            if nz and step != declared:
                raise ValueError(f"{r.label}: {kk} moved in step {step}, assigned to {declared}")
        actual, allg = states[-1][kk], states[0][kk]
        if kk in ra.LINES:
            label, group = ra.LINES[kk]
            m = c["meta"].get(kk)
            # Ofgem's cap components are ex-ante allowances, never outturn: never 'measured'
            basis_a, src = BASIS_ALLOWANCE, (m.source_id if m else SRC_CAP)
            if (kk == "bsuos" and "constraint_difference" in states[-1]) or (
                    kk == "tnuos" and ("ofto" in states[-1] or "grid_netzero" in states[-1])):
                basis_a = "modelled"      # allowance less a modelled 4b carve-out
        else:
            label, group = EXTRA_LINES[kk]
            basis_a = {"constraint_difference": c["inputs"].get("constraint_basis") or "modelled",
                       "ofto": "estimated", "grid_netzero": "estimated",
                       "ro_treasury": "modelled"}[kk]
            src = {"constraint_difference": "neso_constraint_breakdown; dukes-5.1",
                   "ofto": "neso_final_tnuos_tables",
                   "grid_netzero": "ofgem_riio3_fd_impact_assessment_t3",
                   "ro_treasury": "ofgem-annex4-v1.25 (taxes.py)"}[kk]
        if kk == "direct_fuel":
            basis_g, src = "modelled", f"{src}; {SRC_A2}; {SRC_FLEET[fleet]}; {SRC_CARBON}"
        elif kk in pct_keys:
            basis_g = "modelled"
            src = f"{src}; {SRC_CAP} formula cells (recomputed)"
        elif step == "1":
            basis_g = basis_a
        else:
            basis_g = "modelled"
        if kk in HELD_EQUAL and kk != "capacity_market" and step != "1":
            raise ValueError(f"{r.label}: {kk} should be held equal (step 1), got step {step}")
        note = ""
        if kk == "capacity_market":
            note = ("held equal (fleet A rule, spec §3.3)" if fleet == "A" else
                    "held equal: DESNZ's figure is one plant with no spare capacity, which the "
                    "Capacity Market still pays for" if fleet == "D" else
                    f"all-gas Britain: the CM paid to gas plant ({c['inputs']['cm_gas_share']:.1%} of "
                    "DY 2026/27 agreements, Ofgem) is removed because the gas cost already pays for "
                    "the plant; CM to everything else kept; difference in 4(c)")
        elif kk in HELD_EQUAL_NOTE:
            note = HELD_EQUAL_NOTE[kk]
        elif kk == "eco":
            note = ("step 3: DESNZ ECO4 guidance §1.2, 'contribute to carbon reduction targets'; "
                    "zero in all-gas Britain")
        elif kk == "sizewell_c":
            note = ("step 3: DESNZ SZC value-for-money assessment para 4, new nuclear 'required for a "
                    "low cost, net zero compliant energy system'; zero in all-gas Britain")
        elif kk == "constraint_difference":
            note = ("all-gas Britain: NESO 2017/18 volume at this year's £/MWh; carved out of BSUoS"
                    + ("; current year: trailing 12 months" if c["inputs"]["financial_year"] >= 2026
                       and any("trailing 12 months" in n for n in c["notes"]) else ""))
        elif kk == "grid_netzero":
            lo, hi = c["inputs"]["grid_netzero_low"], c["inputs"]["grid_netzero_high"]
            note = (f"{c['inputs']['grid_case']} case of £{lo:.2f}-£{hi:.2f}: Ofgem gives no £ split "
                    "to renewables alone (low); high = whole RIIO-3 transmission step-up; carved out "
                    "of TNUoS")
        lines.append(StairLine(
            key=kk, label=label, group=group, step=step,
            actual=at(actual), all_gas=at(allg),
            actual_fixed_gbp=actual[1], actual_gbp_per_kwh=slope(actual),
            all_gas_fixed_gbp=allg[1], all_gas_gbp_per_kwh=slope(allg),
            by_step={s: at(tn) for s, tn in pieces.items()},
            by_step_fixed_gbp={s: tn[1] for s, tn in pieces.items()},
            by_step_gbp_per_kwh={s: slope(tn) for s, tn in pieces.items()},
            basis_actual=basis_a, basis_all_gas=basis_g, source_id=src, note=note))
    steps = {"1": sum(ln.all_gas for ln in lines)}
    for s in STEPS[1:]:
        steps[s] = sum(ln.by_step[s] for ln in lines)
    return Staircase(
        period=k, label=r.label, fleet=fleet, order=order, kwh=kwh_, ofgem_kwh=Q * 1000,
        vat_rate=r.vat_rate, lines=tuple(lines), steps=steps,
        actual_total=sum(ln.actual for ln in lines), all_gas_total=steps["1"],
        inputs=dict(c["inputs"]), nulls=tuple(c["nulls"]), layer3=layer3_beside(k),
        notes=tuple(c["notes"]) + ((f"restated at {kwh_:,.0f} kWh by Ofgem's linear rule",)
                                   if abs(fq - 1) > 1e-12 else ()))


@lru_cache(maxsize=1)
def _layer3_rows():
    from .goods import layer3
    return tuple(layer3())


def layer3_beside(k: tuple) -> dict:
    fy = fy_of(k)
    for row in _layer3_rows():
        if row.get("scheme") == "total" and row.get("fy") == fy:
            return {"fy": row["period"], "per_household": row["passed_through"],
                    "label": row["pass_through_label"], "basis": row["basis"],
                    "source_id": row["source_id"], "note": "beside the headline, never inside it"}
    return {"fy": f"{fy}-{(fy + 1) % 100:02d}", "per_household": None,
            "reason": f"{UNSOURCED}: no Layer 3 total for FY {fy}-{(fy + 1) % 100:02d}"}


def staircases(fleet: str = "A", kwh: float | None = 2500.0, order: str = "carbon_first") -> list[Staircase]:
    return [staircase(r.period, fleet, kwh, order) for r in ra.receipts()]


def table(s: Staircase) -> str:
    out = [f"{s.label}  fleet {s.fleet}  {s.order}  {s.kwh:,.0f} kWh  (£/household/yr)",
           f"{'line':58s} {'actual':>9s} {'all-gas':>9s}  step"]
    for ln in s.lines:
        out.append(f"{ln.label[:58]:58s} {ln.actual:9.2f} {ln.all_gas:9.2f}  {ln.step}")
    out.append(f"{'TOTAL':58s} {s.actual_total:9.2f} {s.all_gas_total:9.2f}")
    for st in STEPS:
        out.append(f"  step {st:3s} {STEP_NAMES[st]:62s} {s.steps[st]:9.2f}")
    return "\n".join(out)


if __name__ == "__main__":
    for lab in ("October 2026 - December 2026", "October 2022 - December 2022",
                "January 2023 - March 2023", "April 2023 - June 2023"):
        for fl in ("A", "B"):
            print(table(staircase(lab, fl)))
            print()
