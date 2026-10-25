"""s24 closure test (spec §15.4 item 2): each tested coal station's margin in fossil Britain,
three calendar years before its actual closure, WITHOUT carbon costs.

margin (£m) = output × (wholesale price − carbon in it)            [engine's P − C, bills.py]
            − output × fuel (QEP 3.2.1 coal £/MWh ÷ DUKES 5.10.C coal-fleet efficiency)
            − output × variable O&M (cost edition in force)
            − MW × (fixed O&M + insurance) (cost edition in force; its 'connection/UoS' line is
              replaced by the station's own TNUoS zone tariff, so not counted twice)
            − MW × TNUoS wider generation tariff for its zone (NG/NESO Final tariff papers)
            − MW × annualised pollution filters (fossil_fleet.abatement_gbp_kw_yr), shown
              separately: 'before filters' and 'after filters'.
output = MW × load factor × hours. Load factor: the station's own TNUoS Annual Load Factor
(charging year starting in that calendar year) where printed; else DUKES 5.10.B coal-fleet
load factor for the calendar year.

Writes work/s24-closure-test/margins.json (read by margins.md and the register update).
Run: uv run python work/s24-closure-test/margins.py (with GASCF_FOSSIL_CLOSURES unset).
"""
from __future__ import annotations

import calendar
import json
import re
import statistics
from pathlib import Path

import openpyxl

from gascf import bills as B
from gascf import fossil_fleet as ff
from gascf import fossil_like_for_like as L
from gascf import prices

ROOT = Path(__file__).parents[2]
RAW = ROOT / "data/raw"
OUT = Path(__file__).parent / "margins.json"
# s28: Fiddler's Ferry results go to the s28 strand file; margins.json keeps the s24 stations only
# (tests/test_fossil_closures.py reads it keyed by register station name).
OUT_S28 = ROOT / "work/s28-fiddlers/margins.json"
S28 = ("Fiddler's Ferry unit 1", "Fiddler's Ferry units 2-4")

# ----------------------------------------------------------------- TNUoS wider generation tariffs
# £/kW, conventional generator, by charging year (Apr-Mar) starting in the key year.
# Pre-2016/17: one wider tariff per zone. 2016/17 on (Project Transmit): peak + ALF × year-round
# shared + year-round not shared + residual, components as printed.
F_1011 = "data/raw/neso_s18b/neso_doc_50691.txt"     # TNUoS tariffs 2010/11 (cols 2009/10, 2010/11)
F_1213 = "data/raw/neso_s18b/neso_doc_50676.txt"     # TNUoS 2012/13 (cols 2011/12, 2012/13)
F_1314 = "data/raw/neso_s18b/neso_doc_50671.txt"     # TNUoS statement 2013/14
F_1516 = "data/raw/neso_s18b/neso_doc_50181.txt"     # Final TNUoS 2015/16 (cols 2014/15, 2015/16)
F_1617 = "data/raw/neso_s18b/neso_doc_50211.txt"     # Final TNUoS 2016/17 (components)
F_1718 = "data/raw/neso_s20d/s20d-neso_doc_50276_Final_TNUoS_2017-18_extract.md"
F_1920 = "data/raw/neso_s20d/s20d-neso_doc_137351_Final_TNUoS_2019-20_extract.md"


def _num(s):
    return float(s.replace(" ", ""))


def _flat(path, zone_label, year_cols):
    """Rows like '17 South East 0.25 0.81 ...': return {year: tariff} for the first two numbers.
    `zone_label` carries the generation-zone number ('21 South Wales') so the demand tables,
    which reuse some names, never match."""
    t = (ROOT / path).read_text()
    num, name = zone_label.split(" ", 1)
    m = re.search(r"(?m)^\s*" + num + r"\s+" + re.escape(name) + r"\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)", t)
    if not m:
        raise ValueError(f"{path}: zone {zone_label!r} not found")
    return {year_cols[0]: float(m.group(1)), year_cols[1]: float(m.group(2))}


def _single(path, zone_label):
    t = (ROOT / path).read_text()
    num, name = zone_label.split(" ", 1)
    m = re.search(r"(?m)^\s*" + num + r"\s+" + re.escape(name) + r"\s+(-?\d+\.\d+)", t)
    if not m:
        raise ValueError(f"{path}: zone {zone_label!r} not found")
    return float(m.group(1))


def _components(path, zone_label):
    """(peak, year-round shared, year-round not shared, residual)."""
    t = re.sub(r"\s+", " ", (ROOT / path).read_text())
    m = re.search(re.escape(zone_label) + r" (-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+) (-?\d+\.\d+)", t)
    if not m:
        raise ValueError(f"{path}: zone {zone_label!r} components not found")
    return tuple(float(g) for g in m.groups())


# zone labels per tariff paper (20-zone to 2012/13; 27-zone from 2013/14)
ZONES = {
    "Tilbury B": {"old": "17 South East", "new": "24 Essex and Kent"},
    "Ironbridge": {"old": "14 Midlands", "new": "18 Mid Wales and The Midlands"},
    "Ferrybridge C": {"new": "15 South Lancashire, Yorkshire and Humber", "new1516": "15 South Lancs, Yorks and Humber"},
    "Longannet": {"new": "9 Stirlingshire and Fife", "new1516": "9 Stirlingshire and Fife"},
    # Rugeley: zone 18 (C-007, Richard Lyon 21 Oct 2026). NG 'TNUoS tariffs for 2013/14' (doc 50671)
    # p.27 old-to-new zone table: 'Rugeley B' old zone 14 -> new zone 18, with Ironbridge and
    # Ratcliffe-on-Soar. Releases to v4-s37 used the higher of zones 16 and 18 (zone 16).
    "Rugeley": {"new": "18 Mid Wales and The Midlands", "new1516": "18 Mid Wales and The Midlands"},
    "Uskmouth": {"new": "21 South Wales", "new1516": "21 South Wales", "transmit": "South Wales & Gloucester"},
    "Eggborough": {"new": "15 South Lancashire, Yorkshire and Humber", "new1516": "15 South Lancs, Yorks and Humber",
                   "transmit": "South Lancashire, Yorkshire and Humber"},
    "Aberthaw B": {"transmit": "South Wales & Gloucester"},
    # s28: Fiddler's Ferry (Warrington, North West England) is in generation zone 15: NG Final
    # TNUoS 2015/16 (doc 50181) Table 16 'Fiddlers Ferry 15 1987 1953'; NG TNUoS 2013/14 (doc
    # 50671) zone map lists it with Drax, Eggborough and Ferrybridge in zone 15. Test years
    # 2016-2019 all fall in the Transmit (component) papers.
    "Fiddler's Ferry unit 1": {"transmit": "South Lancashire, Yorkshire and Humber"},
    "Fiddler's Ferry units 2-4": {"transmit": "South Lancashire, Yorkshire and Humber"},
}

# LCPD opted-out stations (Tilbury B, Ironbridge): station-specific hours from DECC 'LCPD running
# hours 2012/13' Table 1 (hours remaining of 20,000 allowed 1 Jan 2008 - 31 Dec 2015, at end of
# March 2013). Hours run ÷ 5.25 years ÷ 8,760 = share of hours on load: an UPPER bound on the
# load factor (a unit on load at part output counts a full hour).
LCPD_TXT = "data/raw/s23a/s23a-DECC_LCPD_running_hours_2012_13.txt"
LCPD_ROWS = {"Tilbury B": ("Tilbury (7 & 8)", "Tilbury (9 &10)"), "Ironbridge": ("Ironbridge",)}


def lcpd_lf(name: str) -> tuple[float, str] | None:
    if name not in LCPD_ROWS:
        return None
    t = (ROOT / LCPD_TXT).read_text()
    rem = []
    for lab in LCPD_ROWS[name]:
        m = re.search(r"(?m)^\s*" + re.escape(lab) + r"\s+[\d,]+\s+[\d,]+\s+([\d,]+)\s+\d+%", t)
        if not m:
            raise ValueError(f"LCPD table row {lab!r} not found")
        rem.append(int(m.group(1).replace(",", "")))
    run = statistics.mean(20000 - x for x in rem)
    return run / 5.25 / 8760, (f"DECC LCPD running hours 2012/13 Table 1: {', '.join(LCPD_ROWS[name])} hours "
                               f"remaining {rem} of 20,000 -> {run:,.0f} h run Jan 2008-Mar 2013 / 5.25 yr / 8,760 h "
                               f"(upper bound on load factor)")


def tnuos(station: str, year: int, alf: float) -> tuple[float, str]:
    z = ZONES[station]
    pick = lambda labels, f: max(f(l) for l in (labels if isinstance(labels, tuple) else (labels,)))  # noqa: E731
    if year <= 2010:
        v = _flat(F_1011, z["old"], (2009, 2010))
        return v[max(year, 2009)], f"{F_1011} zone '{z['old']}' {max(year, 2009)}/{max(year, 2009) + 1 - 2000:02d}" + (
            " (2008/09 not stored: 2009/10 used)" if year < 2009 else "")
    if year <= 2012:
        v = _flat(F_1213, z["old"], (2011, 2012))
        return v[year], f"{F_1213} zone '{z['old']}' {year}/{year - 1999:02d}"
    if year == 2013:
        return pick(z["new"], lambda l: _single(F_1314, l)), f"{F_1314} zone {z['new']} 2013/14"
    if year in (2014, 2015):
        return (pick(z["new1516"], lambda l: _flat(F_1516, l, (2014, 2015))[year]),
                f"{F_1516} zone {z['new1516']} {year}/{year - 1999:02d}")
    lab = z.get("transmit") or z["new"]
    if year == 2016:
        f = F_1617
    elif year == 2017:
        f = F_1718
    elif year == 2019:
        f = F_1920
    else:      # 2018/19 paper not stored: higher of 2017/18 and 2019/20 (conservative)
        a = tnuos(station, 2017, alf)[0]
        b = tnuos(station, 2019, alf)[0]
        return max(a, b), "2018/19 paper not stored: higher of 2017/18 and 2019/20 at this ALF"
    pk, yrs, yrns, res = _components(f, lab)
    return pk + alf * yrs + yrns + res, f"{f} zone '{lab}' peak+ALF×YRS+YRNS+residual ({pk:.2f}, {yrs:.2f}, {yrns:.2f}, {res:.2f})"


# ----------------------------------------------------------------- load factors
F_ALF1617 = "data/raw/s24/s24-NG_Final_ALFs_2016-17_doc50216.txt"   # Final ALFs 2016/17 (yearly LFs 2010/11-2014/15)
# Draft ALFs 2017/18 (doc 50296): the only stored paper printing 2015/16 yearly LFs for
# Longannet, Rugeley B and Ferrybridge B (the Final ALFs, doc 50281, drop the closed stations).
F_ALF1718D = "data/raw/s24/s24-NG_ALFs_2017-18_doc50296.txt"
ALF_SRC = {"2016/17": F_ALF1617, "2017/18d": F_ALF1718D, "2019/20": F_1920, "2017/18": F_1718}


def station_alf(name: str) -> dict[int, float]:
    """Station-specific yearly load factors printed in the TNUoS ALF tables, keyed by the
    calendar year the charging year starts in. The later paper wins where both print a year."""
    out = {}
    for paper, first in (("2016/17", 2010), ("2017/18d", 2011), ("2017/18", 2011), ("2019/20", 2013)):
        t = re.sub(r"\s+", " ", (ROOT / ALF_SRC[paper]).read_text())
        m = re.search(re.escape(name) + r" (?:Coal|COAL) (?:Yes )?(?:(?:Actual|Partial|Generic) ){5}"
                      r"((?:\d+\.\d+% ){5})", t, re.I)
        if m:
            vals = [float(v.rstrip("%")) / 100 for v in m.group(1).split()]
            for i, v in enumerate(vals):
                out[first + i] = (v, f"{ALF_SRC[paper]} '{name}' yearly LF {first + i}/{first + i - 1999:02d}")
    # s28: later ALF papers, used ONLY for the stations named here (so the s24 stations' inputs
    # are unchanged). Stored in the strand folder pending registration in data/raw/.
    for path, first in EXTRA_ALF.get(name, ()):
        t = re.sub(r"\s+", " ", (ROOT / path).read_text())
        m = re.search(re.escape(name) + r" (?:Coal|COAL) (?:Yes )?(?:(?:Actual|Partial|Generic) ){5}"
                      r"((?:\d+\.\d+% ){5})", t, re.I)
        if not m:
            raise ValueError(f"{path}: {name!r} yearly load factors not found")
        for i, v in enumerate(m.group(1).split()):
            out[first + i] = (float(v.rstrip("%")) / 100, f"{path} '{name}' yearly LF {first + i}/{first + i - 1999:02d}")
    return out


# s28: NG ESO Final ALFs for 2020/21 (doc 157476, yearly LFs 2014/15-2018/19) and 2021/22
# (doc 186166, 2015/16-2019/20): the only papers printing Fiddler's Ferry's 2018/19 and 2019/20.
F_ALF2021 = "data/raw/s28/NG_Final_ALFs_2020-21_doc157476.txt"
F_ALF2122 = "data/raw/s28/NG_Final_ALFs_2021-22_doc186166.txt"
EXTRA_ALF = {"FIDDLERS FERRY": ((F_ALF2021, 2014), (F_ALF2122, 2015))}


def dukes_coal_lf() -> dict[int, float]:
    ws = openpyxl.load_workbook(RAW / "DUKES_5.10.xlsx", read_only=True, data_only=True)["5.10.B and 5.10.C"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[6]
    row = rows[11]
    if not str(row[0]).startswith("of which coal-fired stations"):
        raise ValueError("DUKES 5.10.B coal row moved")
    return {int(str(h)[:4]): float(v) / 100 for h, v in zip(hdr[1:], row[1:]) if h and isinstance(v, (int, float))}


# ----------------------------------------------------------------- stations
STATIONS = [  # name in register, ALF name, MW, actual close, three test years
    ("Tilbury B", None, 1063, "2011-06-30", (2008, 2009, 2010)),
    ("Ironbridge", None, 1000, "2013-06-30", (2010, 2011, 2012)),
    # NG's ALF list names the Ferrybridge coal station 'Ferrybridge B' (its BM unit naming; the
    # only coal station at Ferrybridge after 1992 is C): used for Ferrybridge C.
    ("Ferrybridge C", "Ferrybridge B", 980, "2016-03-31", (2013, 2014, 2015)),
    ("Longannet", "Longannet", 2260, "2016-03-31", (2013, 2014, 2015)),
    # Decision 0159 (Richard Lyon, 21 Oct 2026): 1,006 MW, DUKES 2004-16 edition sheets (was 448, the 2016
    # changed-stations row). Must equal reference/fossil_closures.yaml (tests/test_fossil_closures.py).
    ("Rugeley", "Rugeley B", 1006, "2016-06-30", (2013, 2014, 2015)),
    ("Uskmouth", "USKMOUTH", 220, "2017-06-30", (2014, 2015, 2016)),
    ("Eggborough", "EGGBOROUGH", 1960, "2018-09-30", (2015, 2016, 2017)),
    ("Aberthaw B", "ABERTHAW", 1559, "2020-03-31", (2017, 2018, 2019)),
    # s28 (spec §15.4 item 4): Fiddler's Ferry, two register entries; NG's yearly LF is for the
    # whole station (metered output ÷ station TEC), applied to each entry's MW.
    ("Fiddler's Ferry unit 1", "FIDDLERS FERRY", 485, "2019-03-31", (2016, 2017, 2018)),
    ("Fiddler's Ferry units 2-4", "FIDDLERS FERRY", 1510, "2020-03-31", (2017, 2018, 2019)),
]


def run() -> dict:
    P, C = B.p_elec(B.CENTRAL.route), B.c_marg()
    eta = prices.dukes_efficiency()["coal"]
    dlf = dukes_coal_lf()
    out = {}
    for name, alfname, mw, closed, years in STATIONS:
        mw = L.switched_mw(name, mw)      # card [internal ticket]: edition-MW switch ($GASCF_EDITION_MW), off by default
        salf = station_alf(alfname) if alfname else {}
        rows = []
        for y in years:
            hours = (366 if calendar.isleap(y) else 365) * 24
            if y in salf:
                lf, lf_src = salf[y]
            elif lcpd_lf(name):
                lf, lf_src = lcpd_lf(name)
            else:
                lf, lf_src = dlf[y], f"DUKES 5.10.B coal-fired stations {y}"
            twh = mw * lf * hours / 1e6
            p = statistics.mean(P[(y, m)]["gbp_per_mwh"] for m in range(1, 13))
            c = statistics.mean(C[(y, m)]["gbp_per_mwh"] for m in range(1, 13))
            coal = statistics.mean(L.coal_price(y, m) for m in range(1, 13))
            e = eta[y] / 100
            ed = L.edition(y)
            k = ed.coal
            base = ed.price_base["coal"]
            vom = ff.restate(k.variable_om_gbp_mwh, base, y)
            fix = ff.restate((k.fixed_om_gbp_mw_yr + k.insurance_gbp_mw_yr) / 1000, base, y)   # £/kW/yr
            conn_edition = ff.restate(k.connection_uos_gbp_mw_yr / 1000, base, y)
            tn, tn_src = tnuos(name, y, lf)
            scr = ff.abatement_gbp_kw_yr(ed, "SCR")
            fgdscr = ff.abatement_gbp_kw_yr(ed, "FGD+SCR")
            rev = twh * (p - c)
            fuel = twh * coal / e
            var = twh * vom
            fixed = mw * fix / 1000
            trans = mw * tn / 1000
            before = rev - fuel - var - fixed - trans
            r = {"year": y, "lf": lf, "lf_src": lf_src, "twh": twh, "p": p, "c": c, "p_less_c": p - c,
                 "coal_gbp_mwh_fuel": coal, "eta": e, "fuel_gbp_mwh_e": coal / e, "vom": vom,
                 "fixed_gbp_kw": fix, "edition_conn_gbp_kw_not_used": conn_edition, "edition": ed.source_id["coal"],
                 "tnuos_gbp_kw": tn, "tnuos_src": tn_src,
                 "rev_gbp_m": rev, "fuel_gbp_m": fuel, "vom_gbp_m": var, "fixed_gbp_m": fixed, "tnuos_gbp_m": trans,
                 "margin_before_filters_gbp_m": before,
                 "scr_gbp_m": mw * scr[0] / 1000 + twh * scr[1],
                 "fgdscr_gbp_m": mw * fgdscr[0] / 1000 + twh * fgdscr[1],
                 "filter_src": fgdscr[2],
                 "spread_gbp_mwh": p - c - coal / e - vom}
            r["margin_after_scr_gbp_m"] = before - r["scr_gbp_m"]
            r["margin_after_fgdscr_gbp_m"] = before - r["fgdscr_gbp_m"]
            r["margin_fleet_lf_gbp_m"] = (mw * dlf[y] * hours / 1e6 * r["spread_gbp_mwh"] - fixed - trans)
            r["breakeven_lf"] = (fixed + trans) / (mw * hours / 1e6 * r["spread_gbp_mwh"]) if r["spread_gbp_mwh"] > 0 else None
            rows.append(r)
        out[name] = {"mw": mw, "actual_close": closed, "years": rows}
    return out


if __name__ == "__main__":
    res = run()
    OUT.write_text(json.dumps({k: v for k, v in res.items() if k not in S28}, indent=1))
    OUT_S28.write_text(json.dumps({k: v for k, v in res.items() if k in S28}, indent=1))
    for n, v in res.items():
        print(n, v["mw"], v["actual_close"])
        for r in v["years"]:
            print(f"  {r['year']} LF {r['lf']:.3f} TWh {r['twh']:.2f} P-C {r['p_less_c']:.2f} fuel {r['fuel_gbp_mwh_e']:.2f} "
                  f"vom {r['vom']:.2f} spread {r['spread_gbp_mwh']:.2f} | rev {r['rev_gbp_m']:.0f} fuel {r['fuel_gbp_m']:.0f} "
                  f"vom {r['vom_gbp_m']:.0f} fix {r['fixed_gbp_m']:.0f} tnuos {r['tnuos_gbp_m']:.1f} ({r['tnuos_gbp_kw']:.2f}) "
                  f"=> before {r['margin_before_filters_gbp_m']:.0f} afterSCR {r['margin_after_scr_gbp_m']:.0f} "
                  f"afterFGD+SCR {r['margin_after_fgdscr_gbp_m']:.0f}")
