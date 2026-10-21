"""Carbon price on gas-fired power, £ per tonne CO2, by month (spec draft 3, §4 step 2).

Two parts, both GB-only:
- **Allowance price.** From May 2021, the UK ETS Authority's monthly average of the UKA
  December futures settlement price (gov.uk CCM full table). Before that, GB generators
  were in the EU ETS: EEX primary-auction clearing prices for EUAs (contract T3PA, aviation
  EUAAs and cancelled auctions excluded), averaged by month and converted at the Bank of
  England daily euro rate (XUDLERS) of each auction day. The Authority itself used EU ETS
  prices for its 2019-21 reference periods, which the test exploits as a check.
- **Carbon Price Support**, a per-kWh-of-gas levy set by financial year (HMRC).
"""
from __future__ import annotations

import csv
import html
import io
import re
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

CO2_T_PER_MWH_GAS_GCV = 0.18194   # DESNZ GHG conversion factors 2026, natural gas, kg CO2 per kWh gross CV

# HMRC / DESNZ environmental taxes bulletin, historical rates; frozen to 31 March 2028.
# £/kWh of gas burned (gross CV, as levied) -> £/MWh.
CPS_GBP_PER_MWH_GAS = [
    (date(2013, 4, 1), 0.91), (date(2014, 4, 1), 1.75),
    (date(2015, 4, 1), 3.34), (date(2016, 4, 1), 3.31),
]
CPS_FROZEN_UNTIL = date(2028, 3, 31)

Month = tuple[int, int]
_MON = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def cps_gbp_per_mwh_gas(d: date) -> float:
    if d > CPS_FROZEN_UNTIL:
        raise ValueError(f"CPS rate after {CPS_FROZEN_UNTIL} not yet legislated")
    rate = None
    for start, r in CPS_GBP_PER_MWH_GAS:
        if d >= start:
            rate = r
    if rate is None:
        raise ValueError(f"no CPS before April 2013: {d}")
    return rate


# ------------------------------------------------------------------ UK ETS

def _table_rows(page: str):
    for t in re.findall(r"<table.*?</table>", page, re.S):
        for r in re.findall(r"<tr.*?</tr>", t, re.S):
            yield [html.unescape(re.sub(r"<.*?>", "", c)).strip()
                   for c in re.findall(r"<t[hd].*?</t[hd]>", r, re.S)]


def read_ukets_ccm(path: Path) -> tuple[dict[Month, float], dict[Month, float]]:
    """(monthly UKA average £/t, CCM trigger price £/t) from the gov.uk full table.

    Each row names the month of assessment and lists the preceding months' averages;
    every monthly average therefore appears in several rows, and must agree each time.
    """
    page = path.read_text()
    avgs: dict[Month, float] = {}
    triggers: dict[Month, float] = {}
    for row in _table_rows(page):
        if not row or row[0] == "Month":
            continue
        mon, yy = row[0].split("-")
        m_assess = (2000 + int(yy), _MON[mon])
        triggers[m_assess] = float(row[2].lstrip("£"))
        names = [n.strip() for n in row[3].split(",")]
        prices = row[4:4 + len(names)]
        y, m = m_assess
        for k, (name, p) in enumerate(zip(names, prices)):
            back = len(names) - k                     # months before the assessment month
            mm = (m - back - 1) % 12 + 1
            yy_ = y - (1 if m - back < 1 else 0)
            if _MON[name[:3]] != mm:
                raise ValueError(f"CCM table: month {name} misaligned in row {row[0]}")
            if p.startswith("£"):
                v = float(p.lstrip("£"))
                if avgs.get((yy_, mm), v) != v:
                    raise ValueError(f"CCM table: {(yy_, mm)} printed as {avgs[(yy_, mm)]} and {v}")
                avgs[(yy_, mm)] = v
    return dict(sorted(avgs.items())), triggers


# ------------------------------------------------------------------ EU ETS (pre-UK ETS)

def read_boe_eur_per_gbp(path: Path) -> dict[date, float]:
    with path.open() as f:
        return {datetime.strptime(r["DATE"], "%d %b %Y").date(): float(r["XUDLERS"])
                for r in csv.DictReader(f)}


def _xl_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    return date(1899, 12, 30) + timedelta(days=int(v))


def read_eex_auctions(zip_path: Path, years: range) -> list[tuple[date, float]]:
    """EUA (T3PA) primary-auction clearing prices, €/t; aviation and cancelled excluded."""
    import openpyxl
    import xlrd
    out = []
    z = zipfile.ZipFile(zip_path)
    for name in z.namelist():
        m = re.search(r"report-(\d{4})-data\.xlsx?$", name)
        if not m or int(m.group(1)) not in years:
            continue
        data = z.read(name)
        if name.endswith(".xls"):
            s = xlrd.open_workbook(file_contents=data).sheet_by_index(0)
            rows = [s.row_values(i) for i in range(s.nrows)]
        else:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            rows = [list(r) for r in wb[wb.sheetnames[0]].iter_rows(values_only=True)]
        hi = next(i for i, r in enumerate(rows) if "Date" in r)
        h = rows[hi]
        col = {k: next(j for j, x in enumerate(h) if x and str(x).startswith(k))
               for k in ("Date", "Contract", "Auction Price")}
        st = next((j for j, x in enumerate(h) if x == "Status"), None)
        for r in rows[hi + 1:]:
            if not r[col["Date"]] or r[col["Contract"]] != "T3PA":
                continue
            if st is not None and r[st] != "successful":
                continue
            out.append((_xl_date(r[col["Date"]]), float(r[col["Auction Price"]])))
    return sorted(out)


def eua_monthly_gbp(auctions: list[tuple[date, float]], fx: dict[date, float]) -> dict[Month, float]:
    """Mean of each month's auction prices, each converted at that day's BoE rate
    (the latest earlier BoE day if the auction fell on a BoE holiday)."""
    days = sorted(fx)
    by_month: dict[Month, list[float]] = defaultdict(list)
    for d, eur in auctions:
        k = max(i for i, x in enumerate(days) if x <= d)
        if (d - days[k]).days > 4:
            raise ValueError(f"no BoE rate near {d}")
        by_month[(d.year, d.month)].append(eur / fx[days[k]])
    return {m: sum(v) / len(v) for m, v in sorted(by_month.items())}


# ------------------------------------------------------------------ combined

UKA_FROM: Month = (2021, 5)


def allowance_monthly_gbp(raw: Path) -> dict[Month, tuple[float, str]]:
    """£/t by month with its source tag: 'UKA' from May 2021, 'EUA' before."""
    uka, _ = read_ukets_ccm(raw / "UKETS_CCM_full_table.html")
    eua = eua_monthly_gbp(
        read_eex_auctions(raw / "eex/emission-spot-primary-market-auction-report-2012-2025-data.zip",
                          range(2014, 2022)),
        read_boe_eur_per_gbp(raw / "BoE_XUDLERS_2014-2021.csv"))
    out = {m: (v, "EUA") for m, v in eua.items() if m < UKA_FROM}
    out.update({m: (v, "UKA") for m, v in uka.items() if m >= UKA_FROM})
    return dict(sorted(out.items()))


def carbon_gbp_per_mwh_elec(allowance_gbp_t: float, d: date, efficiency_gcv: float) -> float:
    """Carbon cost of one MWh of gas-fired electricity: (allowance + CPS) on the CO2 burned."""
    co2 = CO2_T_PER_MWH_GAS_GCV / efficiency_gcv
    return allowance_gbp_t * co2 + cps_gbp_per_mwh_gas(d) / efficiency_gcv


# ================================================================== v4 additions (strand s20c)
# Carbon counted once (spec §6): the marginal carbon cost inside the wholesale price, NZ1c.
# New functions only; nothing above is changed.

ROOT_V4 = Path(__file__).parents[2] / "data/raw"
EEA_ZIP = ROOT_V4 / "eea/s18a-EUETS_emissions_allowances_surplus_prices_2005-2020_data-package.zip"
BOE_V4 = ROOT_V4 / "boe/s18a-XUDLERS_XUAAERS_2004-2026.csv"
EEX_ZIP = ROOT_V4 / "eex/emission-spot-primary-market-auction-report-2012-2025-data.zip"
UKETS_HTML = ROOT_V4 / "UKETS_CCM_full_table.html"
HMRC_RATES_HTML = ROOT_V4 / "hmrc/s18a-envtax_historical_rates.html"

SRC_EEA = "eea-euets-2005-2020-fig3-data"        # annual EUA, 2005–2011 of unstated origin (s18a C1)
SRC_EEX = "eex-primary-auction-t3pa-2012-2025"
SRC_UKA = "uk-ets-authority-ccm-full-table"
SRC_CPS = "hmrc-envtax-historical-rates-cps"
EEX_FROM: Month = (2013, 1)    # first full year of EEX T3PA auctions (2012 has Nov–Dec only)
CARBON_MARKET_FROM: Month = (2005, 1)
NO_MARKET_2021 = [(2021, m) for m in range(1, 5)]  # Jan–Apr 2021: out of EU ETS, no UKA yet (§15 dec. 3)


def read_boe_eur_per_gbp_v4(path: Path = BOE_V4) -> dict[date, float]:
    """BoE XUDLERS daily €/£, skipping blank rows (the s18a pull carries a blank XUAAERS column
    and a few blank XUDLERS days, which `read_boe_eur_per_gbp` does not tolerate)."""
    with path.open() as f:
        return {datetime.strptime(r["DATE"], "%d %b %Y").date(): float(r["XUDLERS"])
                for r in csv.DictReader(f) if r["XUDLERS"].strip()}


def boe_monthly_mean(fx: dict[date, float]) -> dict[Month, float]:
    by: dict[Month, list[float]] = defaultdict(list)
    for d, v in fx.items():
        by[(d.year, d.month)].append(v)
    return {m: sum(v) / len(v) for m, v in sorted(by.items())}


def read_eea_eua_annual(path: Path = EEA_ZIP) -> dict[int, float]:
    """EEA annual EUA price, €/t, row 'EUA price (EUR / t CO2-eq)', 2005–2020."""
    import openpyxl
    z = zipfile.ZipFile(path)
    wb = openpyxl.load_workbook(io.BytesIO(z.read("FIG3-142383-Emissions-allowances-Data.xlsx")),
                                read_only=True, data_only=True)
    rows = [r for r in wb["DATA"].iter_rows(values_only=True)]
    hdr = next(r for r in rows if 2005 in r and 2020 in r)
    row = next((r for r in rows if r[1] == "EUA price (EUR / t CO2-eq)"), None)
    if row is None:
        raise ValueError("EEA data package: EUA price row not found")
    return {int(y): float(row[j]) for j, y in enumerate(hdr) if isinstance(y, int)}


def read_cps_rates(path: Path = HMRC_RATES_HTML) -> list[dict]:
    """HMRC CPS rate table: one dict per 'Rate from' row with £/tCO2, gas £/kWh, coal £/gross GJ."""
    rows = list(_table_rows(path.read_text()))
    hi = next((i for i, r in enumerate(rows) if r[:3] == ["Rate from", "Carbon price equivalent", "Natural gas"]), None)
    if hi is None or "Coal and other taxable solid fuels" not in rows[hi]:
        raise ValueError("HMRC CPS table layout moved")
    jc = rows[hi].index("Coal and other taxable solid fuels")
    out = []
    for r in rows[hi + 2:]:
        if not r or not re.match(r"\d+ \w+ \d{4}$", r[0]):
            break
        out.append({"from": datetime.strptime(r[0], "%d %B %Y").date(),
                    "gbp_per_t": float(r[1].lstrip("£")),
                    "gas_gbp_per_kwh": float(r[2].lstrip("£")),
                    "coal_gbp_per_gj": float(r[jc].lstrip("£"))})
    return out


def co2_t_per_mwh_coal() -> float:
    """CO2 per MWh of coal burned (gross CV), implied by HMRC's own CPS table: the coal rate
    (£/gross GJ) over the carbon price equivalent (£/tCO2), × 3.6 GJ/MWh. Every CPS row gives
    the same factor to 3 s.f. (0.3226 t/MWh); the first row is used."""
    r = read_cps_rates()[0]
    return r["coal_gbp_per_gj"] / r["gbp_per_t"] * 3.6


def cps_gbp_per_mwh_coal(d: date) -> float:
    """CPS on coal, £ per MWh of coal burned (gross CV); zero before April 2013."""
    rate = 0.0
    for r in read_cps_rates():
        if d >= r["from"]:
            rate = r["coal_gbp_per_gj"] * 3.6
    if d > CPS_FROZEN_UNTIL:
        raise ValueError(f"CPS rate after {CPS_FROZEN_UNTIL} not yet legislated")
    return rate


def cps_gas_or_zero(d: date) -> float:
    """CPS on gas, £/MWh gas; zero before 1 April 2013 (CPS began then)."""
    return 0.0 if d < CPS_GBP_PER_MWH_GAS[0][0] else cps_gbp_per_mwh_gas(d)


def allowance_monthly_v4(years: range = range(2002, 2026)) -> dict[Month, tuple[float, str, str]]:
    """Allowance price £/t by month, 2002–2025, with (value, basis, source_id).

    - before 2005: 0 (no carbon market), measured;
    - 2005–2012: EEA annual EUA (€) at that month's mean BoE €/£, *estimated* (EEA's 2005–11
      figure has no stated primary origin, s18a C1; 2012 has only two EEX months);
    - 2013–2020: EEX T3PA primary-auction monthly mean at each auction day's BoE rate, measured;
    - Jan–Apr 2021: 0 (decision 3: GB out of the EU ETS, no UKA market until May), measured;
    - May 2021 on: UK ETS Authority monthly UKA average, measured.
    """
    fx = read_boe_eur_per_gbp_v4()
    fxm = boe_monthly_mean(fx)
    eea = read_eea_eua_annual()
    eex = eua_monthly_gbp(read_eex_auctions(EEX_ZIP, range(2013, 2021)), fx)
    uka, _ = read_ukets_ccm(UKETS_HTML)
    out: dict[Month, tuple[float, str, str]] = {}
    for y in years:
        for m in range(1, 13):
            k = (y, m)
            if k < CARBON_MARKET_FROM:
                out[k] = (0.0, "measured", "no-carbon-market")
            elif k < EEX_FROM:
                out[k] = (eea[y] / fxm[k], "estimated", SRC_EEA)
            elif k < (2021, 1):
                out[k] = (eex[k], "measured", SRC_EEX)
            elif k in NO_MARKET_2021:
                out[k] = (0.0, "measured", "no-carbon-market-jan-apr-2021")
            else:
                out[k] = (uka[k], "measured", SRC_UKA)
    return out


def c_marg_gbp_per_mwh_elec(allowance_gbp_t: float, d: date, eta_gcv: float) -> float:
    """Carbon in the wholesale price, £/MWh of electricity, with gas at the margin (spec §3.1
    NZ1c): (allowance × 0.18194 + CPS per MWh gas) ÷ efficiency. CPS is zero before Apr 2013."""
    return (allowance_gbp_t * CO2_T_PER_MWH_GAS_GCV + cps_gas_or_zero(d)) / eta_gcv


def c_marg_coal_gbp_per_mwh_elec(allowance_gbp_t: float, d: date, eta_gcv: float) -> float:
    """The same for a coal plant at the margin (used only by the pre-2010 price model)."""
    return (allowance_gbp_t * co2_t_per_mwh_coal() + cps_gbp_per_mwh_coal(d)) / eta_gcv


def c_marg_monthly(eta_ccgt: dict[int, float], years: range = range(2002, 2026)) -> dict[Month, dict]:
    """C_marg(m), £/MWh elec, by month with basis and source_id. `eta_ccgt` in per cent (DUKES 5.10.C)."""
    out = {}
    for k, (a, basis, src) in allowance_monthly_v4(years).items():
        d = date(k[0], k[1], 1)
        out[k] = {"gbp_per_mwh": c_marg_gbp_per_mwh_elec(a, d, eta_ccgt[k[0]] / 100),
                  "allowance_gbp_t": a, "basis": "modelled" if basis == "measured" else "estimated",
                  "source_id": f"{src}+{SRC_CPS}+dukes-5.10.C"}
    return out


def nz1c(volume_twh_monthly: dict[Month, float], eta_ccgt: dict[int, float]) -> dict[int, dict]:
    """NZ1c by calendar year, £m: Σ months C_marg(m) × V(m) (V in TWh from the residual strand).
    This is carved out of NZ1, never added to it."""
    cm = c_marg_monthly(eta_ccgt, range(min(k[0] for k in volume_twh_monthly),
                                        max(k[0] for k in volume_twh_monthly) + 1))
    out: dict[int, dict] = {}
    for k, v in volume_twh_monthly.items():
        row = out.setdefault(k[0], {"gbp_m": 0.0, "basis": "modelled", "source_id": "nz1c"})
        row["gbp_m"] += cm[k]["gbp_per_mwh"] * v          # £/MWh × TWh = £m
        if cm[k]["basis"] == "estimated":
            row["basis"] = "estimated"
    return out


def collected_carbon_on_power(year: int) -> float:
    """HMRC estimated CPF receipts, CY (Table 1b), £m: the 'tax collected' half of the §6
    cross-check (the ETS-auction share is the Clock's and is not computed here)."""
    from gascf.subsidies import read_ccl_table_1b
    return read_ccl_table_1b()[year]["cpf_receipts"]


# ------------------------------------------------------------------ s27b: NZ1c split
SRC_CPF_RECEIPTS = "hmrc-envtax-bulletin-2026-03-t1b"
SRC_ETS_POWER = "subsidy-clock-combined-annual-2026-10-10"
GB_SCALED_COMPONENTS = ("ets",)   # 0078: only the ETS part of tax collected is scaled to GB (CPS is GB already)
CARBON_SPLIT_OPTIONS = ("split", "single")   # 'split' = central (s27b); 'single' = pre-s27 one NZ1c line
CARBON_FALLBACKS = [
    {"name": "cpf-receipts-2013", "years": "2013",
     "what": "HMRC Table 1b has no CPF split for 2013 (CPS from 1 Apr 2013): total CCL+CPF receipts "
             "2013 less 2012"},
]


def ets_power_receipts() -> dict[int, tuple[float, str, str]]:
    """UK auction receipts for allowances attributable to power, CY £m, UK (GB scaling in `nz1c_split`).
    s36 (tickets 20, 21): revenue x power's share (0058), never the Subsidy Clock's 'ets' column.
    2002-07: none (no UK auctions in Phase I). 2008-12: traced auctions (`ets_power_phases`). 2013-20:
    registered revenue (`ets_auctions.uk_revenue_2013_20`) x the 0055 stand-in. 2021-24: calendar-year
    sums of the printed DESNZ auction rows (0012, 0055 as corrected) x DESNZ printed shares (2021: 0.428).
    2025 (0079): calendar-2025 auctions (ICE report 278) x the 2024 share, provisional."""
    from gascf import ets_auctions as E
    phases = ets_power_phases()
    out = {y: (0.0, "measured", "no-uk-auction-revenue-before-2008") for y in range(2002, 2008)}
    for y, p in phases.items():
        out[y] = (p["ets_phase2_gbp_m"] + p["ets_phase3_gbp_m"], "measured", p["source_id"])
    for y, r in E.uk_revenue_2013_20().items():
        sh = E.power_share(y)
        out[y] = (r["gbp_m"] * sh["value"], "estimated", f"{r['source_id']}+{sh['numerator_source_id']}+"
                  f"{sh['denominator_source_id']}")
    for y, r in E.ukets_revenue_cy().items():
        sh = E.power_share(y)
        out[y] = (r["gbp"] / 1e6 * sh["value"], "measured", f"{E.SRC_UKETS_2021_24}+{sh['source_id']}")
    r25, sh = E.ukets_revenue_2025(), E.power_share(2025)
    out[2025] = (r25["gbp"] / 1e6 * sh["value"], "estimated", f"{r25['source_id']}+{sh['source_id']}+provisional")
    return dict(sorted(out.items()))


def shortfall_rule_receipts() -> dict[int, dict]:
    """0058's shortfall-rule sensitivity (option (b), decision 0110 item 1.19), 2013-20, cash £m, GB: carbon tax
    collected on power = CPS + GB share x UK revenue x shortfall share, beside the central (0055) counterpart.
    Moves only the split of NZ1c between tax collected and carbon in the price; NZ1c, NZ8 and the gap never move."""
    from gascf import ets_auctions as E
    from gascf.system_costs import gb_share_of_uk
    cpf, rev, central = cpf_receipts(), E.uk_revenue_2013_20(), ets_power_receipts()
    out = {}
    for y in range(2013, 2021):
        gb, sh = gb_share_of_uk(y)[0], E.shortfall_share(y)
        out[y] = {"share": sh["value"], "uk_revenue_gbp_m": rev[y]["gbp_m"], "gb_share": gb, "cps_gbp_m": cpf[y][0],
                  "ets_gbp_m": gb * rev[y]["gbp_m"] * sh["value"],
                  "tax_collected_gbp_m": cpf[y][0] + gb * rev[y]["gbp_m"] * sh["value"],
                  "central_tax_collected_gbp_m": cpf[y][0] + gb * central[y][0]}
    return out


def ets_power_phases() -> dict[int, dict]:
    """s36 ticket 20, 2008-12: UK auction revenue as traced (Phase II, 0056; the 2012 Phase III row
    apart, 0067) x power's share of verified emissions (0058; 2008 entered under 0068, 2009-12 the
    0055 stand-in), UK cash £m, before GB scaling."""
    from gascf import ets_auctions as E
    p2, p3 = E.phase2_revenue_cy(), E.phase3_2012()
    out = {}
    for y, rev in p2.items():
        sh = E.power_share(y)
        rev3 = p3["gbp_m"] if y == p3["year"] else 0.0
        src = f"{E.SRC_PHASE2}+{sh['numerator_source_id']}+{sh['denominator_source_id']}"
        out[y] = {"uk_revenue_gbp_m": rev + rev3, "share": sh["value"], "ets_phase2_gbp_m": rev * sh["value"],
                  "ets_phase3_gbp_m": rev3 * sh["value"],
                  "source_id": src + (f"+{p3['source_id']}" if rev3 else "")}
    return out


def cpf_receipts() -> dict[int, tuple[float, str, str]]:
    """HMRC estimated CPF (Carbon Price Support) receipts, CY £m, Table 1b. CPS is levied only on
    fossil fuel used to generate electricity, so all of it is carbon tax collected on power.
    Before 2013: 0 (no CPS). 2013: total CCL+CPF receipts 2013 − 2012 (estimated, declared)."""
    from gascf.subsidies import HMRC_ENVTAX, read_ccl_table_1b, read_ods
    t = read_ccl_table_1b()
    out = {y: (0.0, "measured", "cps-not-yet-in-force") for y in range(2002, 2013)}
    for y in range(2014, 2026):
        out[y] = (t[y]["cpf_receipts"], "estimated" if t[y]["provisional"] else "measured", SRC_CPF_RECEIPTS)
    rows = read_ods(HMRC_ENVTAX)["CCL_and_CPF_statistics_tables"]
    i = next(k for k, r in enumerate(rows) if r and str(r[0]).startswith("Table 1b."))
    jt = rows[i].index("Total CCL and CPF receipts (£ million)")
    tot = {int(str(r[0])[:4]): r[jt] for r in rows[i + 1:i + 30] if r and str(r[0])[:4].isdigit()}
    out[2013] = (tot[2013] - tot[2012], "estimated", f"{SRC_CPF_RECEIPTS}+fallback:cpf-receipts-2013")
    r = cps_2025_record()                                 # s36 ticket 21 (0054): never HMRC's printed 2025 split
    out[2025] = (r["value"], "estimated", f"{r['source_id']}+provisional")
    return out


def _provisional_2025() -> dict:
    """2025 fields on tax collected: ETS (0079) and CPS (0054) both provisional, both cash £m."""
    from gascf import ets_auctions as E
    c = cps_2025_record()
    return {"ets_status": "provisional", "ets_note": E.NOTE_2025, "ets_money": "cash",
            "cps_status": c["status"], "cps_note": c["note"], "cps_money": c["money"],
            "cps_2025p_range_high_gbp_m": c["cps_2025p_range_high_gbp_m"]}


CPS_2025 = Path(__file__).resolve().parents[2] / "data/raw/s36/cps/cps-2025-provisional.csv"


def cps_2025_record(path: Path = CPS_2025) -> dict:
    """0054: 2025 CPS about £428m cash (range £428-468m), provisional; HMRC's printed Table 1b figure kept
    as a noted number only (its CCL/CPF split is an estimate, bulletin note 5: both are paid as one)."""
    import csv
    from gascf.subsidies import read_ccl_table_1b
    with Path(path).open(encoding="utf-8", newline="") as f:
        (r,) = list(csv.DictReader(f))
    hmrc = read_ccl_table_1b()[2025]["cpf_receipts"]
    return {"year": 2025, "value": float(r["value"]), "status": r["status"], "decision": r["decision"],
            "cps_2025p_range_low_gbp_m": float(r["range_low"]), "cps_2025p_range_high_gbp_m": float(r["range_high"]),
            "cps_2025_hmrc_printed_gbp_m": hmrc, "source_id": r["source_id"], "money": "cash",
            "note": (f"{r['note']} HMRC's printed {hmrc:,.1f} (Environmental Taxes Bulletin, 31 Mar 2026, "
                     "Table 1b, 2025 provisional) is not used: the CCL/CPF split is HMRC's estimate (bulletin "
                     "note 5: receipts for both are paid as one), so main-rate CCL may sit inside any "
                     "HMRC-based CPS figure; at GBP 18/t it implies about 61.9 Mt, over double GB power "
                     "station emissions (0054).")}


def nz1c_split(nz1c_by_year: dict[int, dict]) -> dict[int, dict]:
    """Split NZ1c (carbon in the wholesale price) into
    - carbon_price_receipts: CPS receipts (HMRC) + UK auction receipts attributable to power;
    - carbon_in_price: the rest of NZ1c (allowance value passed through the price but collected by
      nobody in GB: free allocation, Phase I, other states' auctions, and the marginal-plant
      pricing of all MWh).
    The two add to NZ1c exactly; carbon_in_price may be negative in a year if receipts exceed
    NZ1c (reported, not clipped)."""
    from gascf import ets_auctions as E
    from gascf.system_costs import gb_share_of_uk
    cpf, ets, phases = cpf_receipts(), ets_power_receipts(), ets_power_phases()
    rank = {"measured": 0, "modelled": 1, "estimated": 2}
    out = {}
    for y, row in nz1c_by_year.items():
        gb = gb_share_of_uk(y)[0]           # 0043 after 0078: the ETS part only is scaled to GB, every year
        tc = cpf[y][0] + gb * ets[y][0]
        b = max(cpf[y][1], ets[y][1], key=rank.get)
        by_phase = ({k: gb * phases[y][k] for k in ("ets_phase2_gbp_m", "ets_phase3_gbp_m")}
                    if y in phases else {})       # 0067: the 2012 Phase III row kept apart
        out[y] = {
            "carbon_price_receipts": {"gbp_m": tc, "cps_gbp_m": cpf[y][0], "ets_gbp_m": gb * ets[y][0],
                                     "ets_uk_gbp_m": ets[y][0], "cps_uk_gbp_m": cpf[y][0], "gb_share": gb,
                                     "gb_scaled_components": list(GB_SCALED_COMPONENTS), **by_phase,
                                     **(_provisional_2025() if y == 2025 else {}),
                                     "basis": b, "source_id": f"{cpf[y][2]};{ets[y][2]}"},
            "carbon_in_price": {"gbp_m": row["gbp_m"] - tc,
                                "basis": max(row["basis"], b, key=rank.get),
                                "source_id": f"{row['source_id']};{cpf[y][2]};{ets[y][2]}"},
        }
    return out


def ets_revenue_periods() -> dict[int, dict]:
    """s36 ticket 45: the period each year's UK auction revenue in `ets_power_receipts` covers, 2008-25.
    2008-12 and 2021-25: first to last auction date in the registered per-auction files; 2013-20: the stated
    period of `uk-auction-revenue-2013-20-calendar.csv` (every year calendar, decision 0110 item 1.19)."""
    from datetime import date, datetime

    from gascf import ets_auctions as E

    def span(ds, basis, **kw):
        return {"period_start": min(ds), "period_end": max(ds), "basis": basis, **kw}

    out: dict[int, list] = {}
    for r in E._rows(E.PHASE2):
        d = datetime.strptime(r["date"], "%d %B %Y").date()
        out.setdefault(d.year, []).append(d)
    for r in E._rows(E.PHASE3):
        d = datetime.strptime(r["date"], "%d %b %Y").date()
        out.setdefault(d.year, []).append(d)
    res = {y: span(ds, "auction_dates") for y, ds in out.items()}
    for y, r in E.uk_revenue_2013_20().items():
        res[y] = {"period_start": date.fromisoformat(r["period_start"]),
                  "period_end": date.fromisoformat(r["period_end"]), "basis": r["basis"]}
    for y in E.ukets_revenue_cy():
        res[y] = span([date.fromisoformat(r["date"]) for r in E.ukets_auction_rows() if r["date"][:4] == str(y)],
                      "auction_dates")
    res[2025] = span([date.fromisoformat(r["date"]) for r in E._rows(E.UKETS_2025)], "auction_dates",
                     provisional=True)
    return dict(sorted(res.items()))
