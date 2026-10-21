"""Run-file block for the 0097 on-the-road netting (ticket 26), registered through export_v4's block hook (02).

on_the_road: by year, the parts of NZ2 (Fossil Fuel Levy, to 2019) and NZ10 (EESoP) netted off in Reliable Britain
at their 2001 levels, and the parts of NZ8 (CCL, 0044, ticket 12) at its 2001 rate (D3) and on LEC-exempt
output (D5, capped), nominal and in 2024 £ (CPIH L522), for No. 2's bridge rows (27; No. 2 does not net, 0097),
and the inputs with their source status (01, 29)."""
from gascf import bills as B
from gascf import export_v4 as X
from gascf.deflator_cpih import to_real

KEYS = ("nz2_on_the_road_gbp_m", "nz10_on_the_road_gbp_m",
        "nz2_on_the_road_vat_gbp_m", "nz10_on_the_road_vat_gbp_m",  # 0097 (ticket 26 opt a): VAT the build removed
        "nz8_on_the_road_gbp_m", "nz8_lec_exempt_gbp_m")          # 0044 (ticket 12): D3 and D5 parts of NZ8
INPUTS = (
    {"name": "ffl_level_fy2001_02_gbp_m", "value": 92.0, "status": "SOURCED",
     "note": "Fossil Fuel Levy as charged to bills, FY2001/02 = 23+23+23+23, ONS CIQY (EDP 22-09-2026)"},
    {"name": "ffl_geography_gb", "value": "GB", "status": "SOURCED",
     "note": "CIQY is England and Wales FFL plus FFL (Scotland), Northern Ireland not included (ONS Economic "
             "Trends 609, p.4): no GB scaling"},
    {"name": "eesop_spend_gbp_m", "value": 110.0, "status": "INTERIM_APPROVED",
     "note": "indicative supplier cost, not outturn (Ofgem/EST 2003, Fig 3.1; Apr 2000-Mar 2002, both fuels)"},
    {"name": "eesop_electricity_share", "value": 4981 / 11125, "status": "INTERIM_APPROVED",
     "note": "split by energy saved, not by spend (EESoP 3 targets 4,981 / 11,125 GWh)"},
)


def on_the_road_block(built: dict) -> dict:
    years = {}
    for y in B.YEARS:
        o = built[y]["on_the_road"]
        years[str(y)] = {**{k: o[k] for k in KEYS},
                         **{k.replace("_gbp_m", "_gbp_m_2024"): to_real(o[k], y, 2024) for k in KEYS},
                         "nz8_lec_capped": o["nz8_lec_capped"]}
    return {"decision": "0097, 0044", "component": "0101 (gascf.on_the_road)", "in_range": False,
            "inputs": [dict(i) for i in INPUTS], "years": years}


X.register_block("on_the_road", on_the_road_block)
