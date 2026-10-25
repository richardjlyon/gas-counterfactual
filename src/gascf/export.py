"""Write the site's data file (output for `renewables-cost/site/data/latest.json`, schema 0.3).

The question the page answers: what would a household's electricity cost in a Britain without
net zero, against what it costs in Britain with net zero?

- **With net zero** = what you pay: the bill at Ofgem's cap allowance plus the Renewables
  Obligation now paid through taxes (the staircase's actual column).
- **Without net zero** = step 1 of the staircase, all-gas Britain at the pure gas price: no
  carbon tax, no renewables subsidy, no other policy levy (spec line 30).
- **The headline** = with minus without, for fleet A and fleet B, reported as a range. The
  carbon tax is one of the costs of net zero: it is inside the gap, never set against it.
  Steps 2 to 4c are only the breakdown of the gap; their renewables subtotal is not the answer.
- **Goods** (business levies passed into prices, `goods.layer3`) sit beside the headline,
  never inside it.

This module computes nothing the engine does not. It calls the engine's public functions,
renames and groups their output for the page, and adds plain words. The only arithmetic here:
a step's fixed and per-kWh parts are the sums of its lines' parts (checked against the
engine's own step total to 1p), and "pence of net zero in every £1" is gap / what you pay.
No figure is typed in: if a line, a source or a preset cannot be read, the export raises.

Schema 0.3 adds three sections, each built from engine calls:
- `p5_history`: the headline for every Ofgem cap period, both fleets, both grid cases,
  restated to the receipt's money year with the GDP deflator.
- `p6_switches`: every setting of the page's switches (gas price, fleet, grid build-out),
  precomputed by the engine; the page only picks one.
- `p9_opposing_case`: "isn't renewable power cheaper?", the opposing case with its primary
  sources (DESNZ AR7 results, DESNZ generation costs, LCCC), each answered with engine numbers.
  Its words carry {placeholders} filled from `figures`, and the claims they make are checked
  against those figures at build time.

Usage: uv run python -m gascf.export [--site PATH]   (writes out/YYYY-MM-DD.json)
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from contextlib import nullcontext

import pymupdf

from . import breakeven, goods, receipt_actual, staircase, today
from . import sensitivity as sens
from .deflator import rebase
from .official import read_desnz_levelised
from .sap import sap_gbp_per_mwh

ROOT = Path(__file__).parents[2]
OUT = ROOT / "out"
SITE_JSON = ROOT.parent / "renewables-cost/site/data/latest.json"
TDCV_TXT = ROOT / "work/s4-site-prototype/src/Ofgem_TDCV_review_decision_2026.txt"
SCHEMA_VERSION = "0.4"   # 0.4 (s15): gas-power choice A/B/D, carbon and not-net-zero blocks, plant switches
KWH = 2500.0              # spec §5 reference household
ORDER = "carbon_first"    # headline order (spec §4)
FLEETS = staircase.FLEET_IDS   # the gas power cost, the reader's choice (Richard, 11 Oct 2026): A, B, D
BUILT = ("A", "B")              # the two fleets the engine builds itself (D is DESNZ's own figure)
DEFAULT_FLEET = "D"             # the headline: the Government's own cost of gas power (Richard, 11 Oct)
RETRIEVED = "2026-10-10"  # date the stored source files were downloaded (data/raw/SOURCES.md)
GRIDS = staircase.GRID_CASES        # grid build-out switch: ("low", "high"); low (£0) is the default
SWITCH_GAS = (sens.TRIAL_PRICES[2], sens.TRIAL_PRICES[-1])   # £60 and £100 /MWh gas (brief s13)
AR7_PDF = ROOT / "data/raw/desnz_cfd/contracts-for-difference-allocation-round-7-results.pdf"
EGC_PDF = ROOT / "data/raw/desnz_ffpa/electricity-generation-costs-report-2025.pdf"
MILLION = 1000 * 1000      # £ to £m, MWh to TWh (unit change only)
FY_START_MONTH = list(calendar.month_name).index("April")   # UK financial year starts 1 April
LCOE_TECHS = ("Large Scale Solar", "Onshore Wind", "Fixed Offshore Wind5")   # Annex A column heads

# --------------------------------------------------------------------------- plain words

FLEET_WORDS = {
    "A": {"label": "Today's gas price, today's plants",
          "short": "today's gas power stations at today's gas price, with new ones added where they run short",
          "description": "Britain's existing gas power stations at today's gas price, with new gas "
                         "plant built where they run short."},
    "B": {"label": "An all-new gas fleet",
          "short": "an all-new gas fleet",
          "description": "A fleet of brand-new gas power stations, costed from the government's "
                         "own figures for building and running them."},
    "D": {"label": "The Government's own cost of gas power",
          "short": "gas power at the Government's own cost estimate",
          "description": "DESNZ's own figure for a new gas power station running most of the time "
                         "(Electricity Generation Costs 2025), with its carbon cost taken out. It "
                         "uses DESNZ's own gas price for 2030, not today's, and has no gas pipeline "
                         "charges, because DESNZ leaves them out."},
}

SECTIONS = (  # id, receipt heading, keys in order
    ("power", "The electricity", ("direct_fuel", "backwardation", "capacity_market")),
    ("subsidy", "Subsidies for wind, solar and other low-carbon power",
     ("cfd", "ro", "fit", "ro_treasury")),
    ("levies", "Other net-zero policy charges", staircase.STEP3),
    ("not_net_zero", "Not net zero: you pay these either way", staircase.NOT_NET_ZERO),
    ("grid", "The grid", ("tnuos", "ofto", "grid_netzero", "duos", "bsuos", "constraint_difference")),
    ("supplier", "Your supplier", ("operating_costs", "core_operating_costs", "smart_meter",
                                   "industry_charges", "payment_adjustment_cost",
                                   "payment_adjustment_pct", "debt_related_costs", "ebit",
                                   "headroom", "levelisation", "adjustment_allowance")),
    ("vat", "Tax on the bill", ("vat",)),
)

# key -> (receipt label, one-sentence explanation). Words only; every figure comes from the engine.
WORDS = {
    "direct_fuel": ("Electricity itself (wholesale)",
                    "What your supplier pays for the electricity you use, bought months ahead on "
                    "the wholesale market. Without net zero: what gas power stations would charge, "
                    "with no carbon tax."),
    "backwardation": ("Cost of buying ahead",
                      "An Ofgem allowance for the extra cost of buying power months in advance. "
                      "Kept the same in both columns."),
    "capacity_market": ("Standby power stations (Capacity Market)",
                        "Payments to power stations to be ready when demand peaks."),
    "cfd": ("Contracts for Difference",
            "Top-up payments to wind, solar and biomass plants that hold a Contract for "
            "Difference: a government deal that guarantees them a fixed price for each unit."),
    "ro": ("Renewables Obligation, on your bill",
           "The older subsidy for wind, solar and biomass: suppliers must buy certificates from "
           "renewable generators and pass the cost on."),
    "fit": ("Feed-in Tariffs",
            "Payments to owners of small solar panels and wind turbines for the power they make."),
    "ro_treasury": ("Renewables Obligation, through your taxes",
                    "From April 2026 the government moved most of the Renewables Obligation off "
                    "bills and onto general taxes. You still pay it, as a taxpayer."),
    "eco": ("Energy Company Obligation",
            "Insulation and heating for poorer homes, paid for through bills; the government "
            "says one of its aims is to cut carbon. Removed from electricity bills in April 2026."),
    "whd": ("Warm Home Discount",
            "A yearly rebate for poorer households, paid for by everyone else's bills. Not a "
            "net-zero cost, so it is the same in both columns."),
    "aahedc": ("North of Scotland network help",
               "Keeps grid charges down in the north of Scotland, where wires cost more to run. "
               "Not a net-zero cost, so it is the same in both columns."),
    "eii_levy": ("Heavy industry discount",
                 "Pays for a discount on grid charges given to steel and other energy-hungry "
                 "industries. The government says the money pays for part of their network "
                 "charges, so it is not counted as a net-zero cost: the same in both columns."),
    "sizewell_c": ("Sizewell C nuclear levy",
                   "Pays towards building the Sizewell C nuclear power station, which the "
                   "government says is needed for net zero."),
    "tnuos": ("High-voltage grid",
              "The long-distance pylons and cables (transmission)."),
    "ofto": ("Cables to offshore wind farms",
             "The households' share of the cables that bring offshore wind ashore, carved out of "
             "the high-voltage grid charge so it is not counted twice."),
    "grid_netzero": ("Grid build-out the regulator puts down to net zero",
                     "The rise in high-voltage grid charges from April 2026 that Ofgem says supports "
                     "its clean-power plans; carved out of the high-voltage grid charge. Counted as "
                     "nil by default because Ofgem does not split it between renewables and demand "
                     "growth."),
    "duos": ("Local wires",
             "The local network that brings power to your street (distribution)."),
    "bsuos": ("Running the grid minute by minute",
              "What the grid operator spends keeping supply and demand matched (balancing)."),
    "constraint_difference": ("Paying wind farms to switch off",
                              "Payments to generators to stop when the grid cannot carry their "
                              "power, above the 2017/18 level."),
    "operating_costs": ("Supplier running costs (old allowance)",
                        "Staff, billing and call centres, under Ofgem's allowance before July 2025."),
    "core_operating_costs": ("Supplier running costs",
                             "Staff, billing and call centres."),
    "smart_meter": ("Smart meters",
                    "The net cost of installing and running smart meters."),
    "industry_charges": ("Industry fees",
                         "Fees suppliers pay for industry bodies and data systems."),
    "payment_adjustment_cost": ("Payment method adjustment",
                                "Ofgem's adjustment for the extra cost of some ways of paying."),
    "payment_adjustment_pct": ("Payment method adjustment (share of bill)",
                               "The same adjustment, set as a share of the bill."),
    "debt_related_costs": ("Unpaid bills",
                           "Customers who do not pay. Set as a share of the bill, so it is "
                           "smaller when the bill is smaller."),
    "ebit": ("Supplier profit",
             "The profit Ofgem allows suppliers, set as a share of the bill."),
    "headroom": ("Safety margin",
                 "An allowance for costs Ofgem cannot predict, set as a share of the bill."),
    "levelisation": ("Payment-type balancing",
                     "Evens out costs between customers who pay in different ways. Adds up to "
                     "nothing across Britain."),
    "adjustment_allowance": ("Ofgem adjustment allowance",
                             "A correction Ofgem makes for past periods (Ofgem's licence Annex 8)."),
    "vat": ("VAT",
            "Value Added Tax. The government cut it to nothing on electricity from 1 October "
            "2026 to 31 March 2027."),
}

CARBON_LABEL = "Carbon taxes (UK ETS, Carbon Price Support; EU ETS before 2021)"

STEP_WORDS = {
    "1": ("Without net zero",
          "Gas power stations make the electricity now made by subsidised wind, solar, biomass "
          "and other plants. No carbon tax, no subsidy, no other policy levy."),
    "2": (CARBON_LABEL,
          "The carbon taxes gas power stations pay today. All-gas Britain has no carbon price of "
          "any kind, so they are a cost of net zero and part of the gap."),
    "3": ("Other net-zero policy charges",
          "Sizewell C and the Energy Company Obligation."),
    "4a": ("Subsidies for wind, solar and other low-carbon power",
           "Contracts for Difference, Renewables Obligation (bill and taxes) and Feed-in Tariffs."),
    "4b": ("Extra grid costs of wind",
           "Cables to offshore wind farms, and paying wind farms to switch off."),
    "4c": ("Wholesale price difference",
           "What wind and solar do to the wholesale price, compared with gas power stations "
           "that pay the carbon taxes. A minus figure means the wholesale price is lower."),
}

SOURCE_TOKEN = re.compile(r"\s*(?:;|\+|/)\s*")


# --------------------------------------------------------------------------- sources

def _src(publisher, title, edition, url, locator, file=None, retrieved=RETRIEVED) -> dict:
    return {"publisher": publisher, "title": title, "edition": edition, "url": url,
            "retrieved": retrieved, "locator": locator, "file": file}


OFGEM_CAP_PAGE = ("https://www.ofgem.gov.uk/energy-regulation/domestic-and-non-domestic/"
                  "energy-pricing-rules/energy-price-cap/energy-price-cap-default-tariff-levels")
ENGINE = "gas-counterfactual engine"

SOURCES = {
    # Ofgem cap documents (data/raw/SOURCES.md rows 32-36; research/2026-10-10-methods/src)
    "ofgem-annex9-v1.11": _src("Ofgem", "Annex 9: levelisation allowance methodology and levelised "
                               "cap levels", "v1.11, cap period 1 October to 31 December 2026",
                               "https://www.ofgem.gov.uk/sites/default/files/2026-08/Annex-9-"
                               "Levelisation-allowance-methodology-and-levelised-cap-levels-v1.11.xlsx",
                               "Tab '1b Historical level tables', Other Payment Method, single rate, "
                               "GB average rows (nil and typical consumption)",
                               "data/raw/ofgem/Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-v1.11.xlsx"),
    "ofgem-cap-model-v1.31": _src("Ofgem", "Default tariff cap level model", "v1.31",
                                  "https://www.ofgem.gov.uk/sites/default/files/2026-08/"
                                  "Default-tariff-cap-level-v1.31.xlsx",
                                  "Tab '3a DF' rows 11-24 (direct fuel), 48-61 (backwardation), "
                                  "85-98 (CfD); percentage-line formula cells",
                                  "data/raw/ofgem/Default-tariff-cap-level-v1.31.xlsx"),
    "ofgem-annex4-v1.25": _src("Ofgem", "Annex 4: policy cost allowance methodology", "v1.25",
                               "https://www.ofgem.gov.uk/sites/default/files/2026-08/Annex-4-"
                               "policy-cost-allowance-methodology-v1.25.xlsx",
                               "Tab '1a Policy Cost Allowance' rows 53-60, scheme by scheme",
                               "data/raw/ofgem/Annex-4-policy-cost-allowance-methodology-v1.25.xlsx"),
    "ofgem-annex3-elec-v1.25": _src("Ofgem", "Annex 3: network cost allowance methodology "
                                    "(electricity)", "v1.25",
                                    "https://www.ofgem.gov.uk/sites/default/files/2026-08/Annex-3-"
                                    "network-cost-allowance-methodology-electricity-v1.25.xlsx",
                                    "Tabs '2a TNUoS', '2b DUoS', '2c BSUoS', GB mean of 14 regions",
                                    "data/raw/ofgem/Annex-3-network-cost-allowance-methodology-electricity-v1.25.xlsx"),
    "ofgem-annex2-v1.30": _src("Ofgem", "Annex 2: wholesale cost allowance methodology",
                               "v1.30 (data removed)", OFGEM_CAP_PAGE,
                               "Tab '1b', hard-coded electricity and gas indices by cap period",
                               "research/2026-10-10-methods/src/Annex-2-wholesale-cost-allowance-methodology-v1.30_data_removed-2.xlsx"),
    "ofgem_tdcv_2026": _src("Ofgem", "Review of typical domestic consumption values: decision",
                            "27 May 2026, in force from 1 July 2026",
                            "https://www.ofgem.gov.uk/sites/default/files/2026-05/Review%20of%20"
                            "typical%20domestic%20consumption%20values%20decision.pdf",
                            "Table 1, Electricity, Profile Class 1 (standard single-rate meters), "
                            "column '2026 TDCV'",
                            "work/s4-site-prototype/src/Ofgem_TDCV_review_decision_2026.pdf"),
    # fleets and carbon
    "desnz-egc2025-annexA": _src("DESNZ", "Electricity Generation Costs 2025, Annex A",
                                 "2024 prices",
                                 "https://www.gov.uk/government/publications/electricity-generation-costs-2025",
                                 "Gas CCGT and OCGT technology rows (capital, fixed and variable costs); "
                                 "levelised cost, 'Gas CCGT 93% Load Factor', 2030 (total, carbon)",
                                 "data/raw/DESNZ_EGC2025_AnnexA.xlsx"),
    "dukes-5.10": _src("DESNZ", "Digest of UK Energy Statistics 2026, Table 5.10", "30 July 2026",
                       "https://assets.publishing.service.gov.uk/media/6a6a364b0ddb7e4831c629f2/DUKES_5.10.xlsx",
                       "CCGT efficiency (gross calorific value) by year", "data/raw/DUKES_5.10.xlsx"),
    "dukes-5.11": _src("DESNZ", "Digest of UK Energy Statistics 2026, Table 5.11", "30 July 2026",
                       "https://assets.publishing.service.gov.uk/media/6a6a365b0ddb7e4831c629f3/DUKES_5.11.xlsx",
                       "Power stations operational end May 2026, GB natural-gas plant",
                       "data/raw/DUKES_5.11.xlsx"),
    "elexon-fuelhh": _src("Elexon", "BMRS FUELHH, generation by fuel type, half-hourly",
                          "2016-2026", "https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream",
                          "Residual demand left for gas when subsidised generators are removed",
                          "data/raw/elexon/FUELHH_YYYY.csv"),
    "neso": _src("NESO", "Historic Demand Data", "2015-2026",
                 "https://api.neso.energy/dataset/historic-demand-data",
                 "National demand and embedded generation, half-hourly",
                 "data/raw/neso/demanddata_YYYY.csv"),
    "neso-ecr-2026": _src("NESO", "Electricity Capacity Report 2026 and data workbook", "2026",
                          "https://emrdeliverybody.nationalenergyso.com/IG/s/article/"
                          "CM-Auction-Guidelines-and-Parameters",
                          "Recommendations p.5 (T-1 2027/28 de-rated margin); data workbook Fig B1 "
                          "(2027/28 Base Case peak, 0133), Fig A10 (de-rating factors)",
                          "data/raw/desnz_cm/NESO_ECR_2026.pdf"),
    "nationalgas-charges-oct-2026": _src("National Gas", "NTS charges effective from 1 October 2026",
                                         "29 May and 31 July 2026",
                                         "https://www.nationalgas.com/sites/default/files/documents/"
                                         "October%202026%20Charging%20Information%20Provision.pdf",
                                         "Exit capacity and general non-transmission services charges",
                                         "data/raw/nationalgas/October_2026_Charging_Information_Provision.pdf"),
    "nationalgas-sap": _src("National Gas", "System Average Price of gas, actual day (PUBOB603)",
                            "daily", "https://api.nationalgas.com/operationaldata/v1/publications/gasday",
                            "SAP by gas day, used for the gas-market margin check",
                            "data/raw/nationalgas/SAP_PUBOB603.csv"),
    "nationalgas-sap-pubob603": _src("National Gas", "System Average Price of gas, actual day "
                                     "(PUBOB603)", "daily",
                                     "https://api.nationalgas.com/operationaldata/v1/publications/gasday",
                                     "SAP for the gas day shown", "data/raw/nationalgas/SAP_PUBOB603.csv"),
    "elexon-mid-apx": _src("Elexon", "BMRS Market Index Data (MID), APX rows: Elexon market index price "
                           "(short-term markets; not the day-ahead auction price, 0163 R25)", "daily",
                           "https://data.elexon.co.uk/bmrs/api/v1/datasets/MID/stream",
                           "APXMIDP price and volume, all settlement periods of the day",
                           "data/raw/elexon/MID_APX_YYYY.csv"),
    "ukets-ccm-table": _src("UK ETS Authority", "CCM trigger prices and average monthly prices: "
                            "full table", "monthly",
                            "https://www.gov.uk/government/publications/taking-part-in-the-uk-"
                            "emissions-trading-scheme-markets/cost-containment-mechanism-ccm-"
                            "trigger-prices-and-average-monthly-prices-full-table",
                            "Monthly average UK allowance price", "data/raw/UKETS_CCM_full_table.html"),
    "eex-eua-auctions": _src("EEX", "EUA primary market auction reports", "2012-2025",
                             "https://www.eex.com/fileadmin/EEX/Downloads/Markets/Environmentals/"
                             "EUA_Emission_Spot_Primary_Market_Auction_Report/Archive_Reports/"
                             "emission-spot-primary-market-auction-report-2012-2025-data.zip",
                             "Auction clearing prices before the UK scheme began (May 2021)",
                             "data/raw/eex/emission-spot-primary-market-auction-report-2012-2025-data.zip"),
    "boe-fx": _src("Bank of England", "Spot euro per pound (XUDLERS)", "2014-2021",
                   "https://www.bankofengland.co.uk/boeapps/database/", "Daily rate on each "
                   "auction day", "data/raw/BoE_XUDLERS_2014-2021.csv"),
    "hmrc-cps": _src("HMRC", "Carbon Price Support rates (carbon price floor)",
                     "rates by financial year; frozen to 31 March 2028",
                     "https://www.gov.uk/government/publications/excise-notice-ccl16-a-guide-to-carbon-price-floor",
                     "Rate per kWh of gas burned in power stations (src/gascf/carbon.py)"),
    "desnz-ghg-factors-2026": _src("DESNZ", "Greenhouse gas reporting: conversion factors 2026",
                                   "flat format, revised",
                                   "https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026",
                                   "Natural gas, kg CO2 per kWh, gross calorific value",
                                   "research/2026-10-10-methods/src/ghg2026flat.xlsx"),
    "hmt-gdp-deflator-sep-2026": _src("HM Treasury", "GDP deflators at market prices, and money GDP",
                                      "September 2026",
                                      "https://assets.publishing.service.gov.uk/media/6abe277f26660e5f62a7f1e9/"
                                      "GDP_Deflators_Qtrly_National_Accounts_September_2026.xlsx",
                                      "Calendar-year deflator, used to restate money in one year's prices",
                                      "data/raw/hmt/GDP_Deflators_Qtrly_National_Accounts_September_2026.xlsx"),
    "desnz-dukes-5.10-2026": _src("DESNZ", "Digest of UK Energy Statistics 2026, Table 5.10",
                                  "30 July 2026",
                                  "https://assets.publishing.service.gov.uk/media/6a6a364b0ddb7e4831c629f2/DUKES_5.10.xlsx",
                                  "CCGT efficiency, latest year printed", "data/raw/DUKES_5.10.xlsx"),
    "cepa-ghd-unabated-gas-costs-2025": _src("CEPA and GHD for DESNZ", "Unabated gas electricity "
                                             "generation costs", "2025",
                                             "https://assets.publishing.service.gov.uk/media/696616c68d599f4c09e1ffae/"
                                             "unabated-gas-electricity-generation-costs-2025.pdf",
                                             "Table 3.5, Generation Option 1, variable fee, medium "
                                             "current estimate (2024 prices)"),
    # grid lines (system_costs.py; data/raw/SOURCES.md rows 41-50)
    "neso_final_tnuos_tables": _src("NESO", "Final TNUoS tariffs 2026/27, tables and report",
                                    "January 2026", "https://www.neso.energy/document/376341/download",
                                    "Offshore transmission (OFTO) demand share, per domestic site",
                                    "data/raw/neso/tnuos/Final_TNUoS_Tariffs_2026-27_Tables.xlsx"),
    "neso_constraint_breakdown": _src("NESO", "Constraint breakdown costs and volume",
                                      "FY 2017/18 to 2026/27",
                                      "https://api.neso.energy/dataset/fb56b46e-cef3-4eb8-9294-0ca19769b7eb",
                                      "Daily constraint costs by financial year",
                                      "data/raw/neso/constraint_breakdown/"),
    "ofgem_riio3_fd_impact_assessment_t3": _src(
        "Ofgem", "RIIO-3 Final Determinations: Impact Assessment", "December 2025",
        "https://www.ofgem.gov.uk/sites/default/files/2025-12/RIIO-3-Final-Determinations-impact-assessment.pdf",
        "Table 3 'Profiling effects', ET charges (pre-profiling) and ET profiling effect, £ per "
        "dual-fuel household, 2025/26 prices; para 5.39: 'These bill increases will support the "
        "electrification of the power system, in line with government’s CP2030 plans and the wider "
        "transition to net zero'",
        "data/raw/ofgem_networks/RIIO-3-Final-Determinations-impact-assessment.pdf"),
    "dukes-5.1": _src("DESNZ", "Digest of UK Energy Statistics 2026, Table 5.1", "30 July 2026",
                      "https://assets.publishing.service.gov.uk/media/6a6a35d80ddb7e4831c629ef/DUKES_5.1.xlsx",
                      "Electricity supplied, by year", "data/raw/dukes/DUKES_5.1.xlsx"),
    # goods layer (goods.py; data/raw/SOURCES.md rows 63-84, 93-104)
    "LCCC-RDLR": _src("Low Carbon Contracts Company", "Reconciled Daily Levy Rates", "data portal",
                      "https://dp.lowcarboncontracts.uk/dataset/reconciled-daily-levy-rates",
                      "Levy rate and eligible demand, by day", "data/raw/lccc/reconciled_daily_levy_rates.csv"),
    "OFGEM-RO-AR-2024-25": _src("Ofgem", "Renewables Obligation Annual Report, scheme year 23 (2024-25)",
                                "27 March 2026",
                                "https://www.ofgem.gov.uk/sites/default/files/2026-03/RO_24-25_SY23_Annual_Report-20260327121336.pdf",
                                "Total obligation and buy-out price", "data/raw/ofgem_ro_fit/RO_annual_report_SY23.pdf"),
    "OFGEM-FIT-AR-2024-25": _src("Ofgem", "Feed-in Tariffs Annual Report, scheme year 15 (2024-25)",
                                 "10 December 2025",
                                 "https://www.ofgem.gov.uk/sites/default/files/2025-12/feed_in_tariff_annual_report_sy15_20251210120852.pdf",
                                 "Levelisation fund and relevant electricity supplied",
                                 "data/raw/ofgem_ro_fit/FIT_annual_report_SY15.pdf"),
    "DUKES26-5.2": _src("DESNZ", "Digest of UK Energy Statistics 2026, Table 5.2", "30 July 2026",
                        "https://assets.publishing.service.gov.uk/media/6a6a35e4bf4a7aca8f8976c2/DUKES_5.2.xlsx",
                        "Row 'Domestic', public distribution system: the households' share of sales",
                        "data/raw/dukes/DUKES_5.2.xlsx"),
    "DUKES26-5.5": _src("DESNZ", "Digest of UK Energy Statistics 2026, Table 5.5", "30 July 2026",
                        "https://assets.publishing.service.gov.uk/media/6a6a36088319ab05f7caa1da/DUKES_5.5.xlsx",
                        "Section 5.5.D, row 'Gives UK electricity sales'", "data/raw/dukes/DUKES_5.5.xlsx"),
    "ONS-LFS": _src("ONS", "Households by household size, regions of England and GB countries",
                    "2025", "https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/families",
                    "Households, England", "data/raw/ons_households/householdsizebyregionscountries2025.xlsx"),
    "bank-underground-2023": _src("Bank of England (Bank Underground blog)", "How do firms pass "
                                  "energy and food costs through the supply chain", "24 August 2023",
                                  "https://bankunderground.co.uk/2023/08/24/how-do-firms-pass-energy-and-food-costs-through-the-supply-chain/",
                                  "'long-run coefficients ranging from 0.4 (for services industries) to "
                                  "0.8 (for most manufacturing industries)'",
                                  "data/raw/papers/BankUnderground_2023_energy_food_costs_supply_chain.html"),
    "ccc-2017": _src("Committee on Climate Change", "Energy prices and bills: impacts of meeting "
                     "carbon budgets", "March 2017",
                     "https://www.theccc.org.uk/wp-content/uploads/2017/03/Energy-Prices-and-Bills-Committee-on-Climate-Change-March-2017.pdf",
                     "Box 2.4, share of UK output exported", "data/raw/papers/CCC_2017_Energy_Prices_and_Bills.pdf"),
    # break-even (breakeven.py)
    "lccc-actual-cfd-generation": _src("Low Carbon Contracts Company", "Actual CfD generation and "
                                       "avoided GHG emissions", "data portal",
                                       "https://dp.lowcarboncontracts.uk/dataset/actual-cfd-generation-and-avoided-ghg-emissions",
                                       "CfD generation, latest 12 months", "data/raw/lccc/actual_cfd_generation.csv"),
    "lccc-actual-ilr-income": _src("Low Carbon Contracts Company", "Actual ILR income", "data portal",
                                   "https://dp.lowcarboncontracts.uk/dataset/actual-ilr-income",
                                   "Eligible demand", "data/raw/lccc/actual_ilr_income.csv"),
    # the opposing case (brief s13)
    "desnz-cfd-ar7-results": _src("DESNZ", "Contracts for Difference Allocation Round 7 results",
                                  "14 January 2026",
                                  "https://assets.publishing.service.gov.uk/media/6966861de8c04eb2919f773a/"
                                  "contracts-for-difference-allocation-round-7-results-.pdf",
                                  "Table (E), clearing strike price by technology, 2012 and 2024 prices; "
                                  "table (F), total capacity (MW)",
                                  "data/raw/desnz_cfd/contracts-for-difference-allocation-round-7-results.pdf"),
    "desnz-egc-2025-report": _src("DESNZ", "Electricity Generation Costs 2025", "report, 2026",
                                  "https://www.gov.uk/government/publications/electricity-generation-costs-2025",
                                  "'Scope of the report', p.8: wider system costs are out of scope",
                                  "data/raw/desnz_ffpa/electricity-generation-costs-report-2025.pdf"),
    "desnz-ffpa-2025": _src("DESNZ", "Fossil Fuel Price Assumptions 2025", "January 2026",
                            "https://assets.publishing.service.gov.uk/media/69693a291c8a70fc0a3b0434/"
                            "Fossil_Fuel_Price_Assumptions_2025_publication.xlsx",
                            "Sheet 'Gas' (Table 1), p/therm, real 2024 prices, Assumption B (central), 2030",
                            "data/raw/desnz_ffpa/Fossil_Fuel_Price_Assumptions_2025_publication.xlsx"),
    "desnz_epg_up_to_30_june_2023": _src("DESNZ", "Energy Price Guarantee up to 30 June 2023",
                                         "policy paper (withdrawn 10 April 2024, still hosted)",
                                         "https://www.gov.uk/government/publications/energy-bills-support/"
                                         "energy-price-guarantee-up-until-30-june-2023",
                                         "Unit-rate discounts by quarter, Great Britain",
                                         "data/raw/govuk/EPG_up_to_30_June_2023.html"),
    # Richard's decisions of 11 Oct 2026 (brief s15; data/raw/s15/)
    "ofgem-cm-annual-report-2022-23": _src("Ofgem", "Annual Report on the Operation of the Capacity "
                                           "Market in 2022-23", "August 2023",
                                           "https://www.ofgem.gov.uk/sites/default/files/2023-08/Final%20Annual%20"
                                           "Report%20on%20the%20Operation%20of%20the%20Capacity%20Market%20in%202022-23.pdf",
                                           "2022/23 T-4 auction (delivery year 2026/27): clearing price, total "
                                           "and gas de-rated capacity",
                                           "data/raw/ofgem_cm/Ofgem_CM_annual_report_2022-23.pdf"),
    "ofgem-cm-annual-report-2025-26": _src("Ofgem", "Annual Report on the Operation of the Capacity "
                                           "Market in 2025-26", "September 2026",
                                           "https://www.ofgem.gov.uk/sites/default/files/2026-09/Annual-report-"
                                           "on-the-operation-of-the-capacity-market-in-2025-26.pdf",
                                           "2026/27 T-1 auction: clearing price, total and gas capacity",
                                           "data/raw/ofgem_cm/Ofgem_CM_annual_report_2025-26.pdf"),
    "desnz-eco4-guidance": _src("DESNZ", "Energy Company Obligation guidance 2022 to 2026", "2023",
                                "https://assets.publishing.service.gov.uk/media/64787c1cb32b9e0012a96038/"
                                "energy-company-obligation-eco-guidance-2022-2026.pdf",
                                "§1.2: objectives include to 'contribute to carbon reduction targets in "
                                "the domestic sector'",
                                "data/raw/s15/energy-company-obligation-eco-guidance-2022-2026.pdf"),
    "desnz-szc-fid-vfm": _src("DESNZ", "Sizewell C Final Investment Decision: Value for Money "
                              "assessment", "July 2025",
                              "https://assets.publishing.service.gov.uk/media/687f951dfdc190fb6b84689d/"
                              "szc-fid-vfm-assessment.pdf",
                              "para 4: new nuclear beyond Hinkley Point C 'is required for a low cost, "
                              "net zero compliant energy system'", "data/raw/s15/szc-fid-vfm-assessment.pdf"),
    "desnz-eii-levy-ia-2024": _src("DESNZ", "The Energy-Intensive Industry Electricity Support Payments "
                                   "and Levy Regulations 2024: impact assessment", "UKIA 2024/62",
                                   "https://www.legislation.gov.uk/ukia/2024/62/pdfs/ukia_20240062_en.pdf",
                                   "para 52: levy proceeds 'compensate eligible EIIs for a proportion of "
                                   "the network charging costs element in their energy bills'",
                                   "data/raw/s15/ukia_20240062_en.pdf"),
    # the engine itself
    "gascf-sensitivity": _src(ENGINE, "Gas-price sensitivity and DESNZ reconciliation "
                              "(src/gascf/sensitivity.py)", None, None,
                              "Staircase re-run at trial gas prices; walk from DESNZ's £/MWh to the fleets'"),
    "fleetb": _src(ENGINE, "Fleet B: an all-new gas fleet (src/gascf/fleetb.py)", None, None,
                   "Cost of power on the 2025 residual-demand curve at the day's gas price"),
    "gascf-staircase": _src(ENGINE, "Staircase: with net zero against without (src/gascf/staircase.py)",
                            None, None, "Both columns of the receipt and the steps between them"),
    "gascf-goods": _src(ENGINE, "Goods: business levies passed into prices (src/gascf/goods.py)",
                        None, None, "CfD, RO and FiT paid by businesses, share passed on, per household"),
}


def source_tokens(source_id: str) -> list[str]:
    """Split an engine source_id ('a; b+c / d (note)') into keys of SOURCES. Raises if unknown."""
    out = []
    for part in SOURCE_TOKEN.split(source_id):
        tok = part.strip().split(" ")[0].strip()
        if not tok:
            continue
        if tok not in SOURCES:
            raise KeyError(f"export: engine source_id {tok!r} (from {source_id!r}) has no entry in "
                           "export.SOURCES; add its publisher, title, URL and locator")
        if tok not in out:
            out.append(tok)
    return out


# --------------------------------------------------------------------------- helpers

def money(gbp, fixed=None, per_kwh=None) -> dict:
    return {"gbp": gbp, "fixed_gbp": fixed, "gbp_per_kwh": per_kwh}


def presets_from_tdcv(path: Path = TDCV_TXT) -> list[dict]:
    """Low / Medium / High single-rate electricity TDCVs, read from Ofgem's decision (Table 1).

    The text layer prints the table one cell per line: heading, the four column names, then
    rows of four cells (level, 2023 TDCV, 2026 TDCV, change). Raises if the layout moves."""
    header = ["Usage Level", "2023 TDCV", "2026 TDCV", "Change"]
    lines = iter(ln.strip() for ln in path.read_text().splitlines())
    for ln in lines:
        if ln.startswith("Electricity") and "Profile Class 1" in ln:
            break
    else:
        raise ValueError("TDCV decision: 'Electricity - Profile Class 1' heading not found")
    head = [next(lines, None) for _ in header]
    if head != header:
        raise ValueError(f"TDCV decision: Table 1 layout changed: {head!r}")
    col = header.index("2026 TDCV")
    out = []
    for level, pid, label in (("Low", "small", "Small flat"), ("Medium", "typical", "Typical home"),
                              ("High", "large", "Large house")):
        row = [next(lines, None) for _ in header]
        if row[0] != level:
            raise ValueError(f"TDCV decision: expected {level!r}, found {row[0]!r}")
        out.append({"id": pid, "label": label, "ofgem_level": level,
                    "kwh": int(row[col].replace(",", "")), "source_id": "ofgem_tdcv_2026"})
    return out


def engine_meta() -> dict:
    """Engine name and commit, and any engine files changed since that commit (work in progress)."""
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True,
                                  check=True).stdout
        except Exception:
            return None
    dirty = git("status", "--porcelain", "--", "src/gascf") or ""
    commit = git("rev-parse", "--short", "HEAD")
    return {"name": "gas-counterfactual", "version": None, "commit": commit.strip() if commit else None,
            "uncommitted_engine_files": sorted(ln[3:].strip() for ln in dirty.splitlines() if ln.strip())}


def latest_period() -> tuple:
    return receipt_actual.receipts()[-1].period


def period_meta(k: tuple, label: str) -> dict:
    """Ofgem cap period (y1, m1, y2, m2) as an id ('2026-Q4') and plain dates."""
    y1, m1, y2, m2 = k
    last = calendar.monthrange(y2, m2)[1]
    quarter = (m1 - 1) // 3 + 1 if (m1 - 1) % 3 == 0 and (y2, m2) == (y1, m1 + 2) else None
    a = f"1 {calendar.month_name[m1]}" + ("" if y1 == y2 else f" {y1}")
    return {"id": f"{y1}-Q{quarter}" if quarter else f"{y1}-{m1:02d}",
            "label": f"{a} to {last} {calendar.month_name[m2]} {y2}", "engine_label": label}


def _steps_of(step: str) -> list[str]:
    return ["pro_rata"] if step == "pro rata" else step.split("+")


# --------------------------------------------------------------------------- the receipt

def receipt(s) -> dict:
    """One fleet's receipt: sections of lines, totals, and the steps the gap is made of."""
    by_key = {ln.key: ln for ln in s.lines}
    placed = [k for _, _, keys in SECTIONS for k in keys]
    missing = set(by_key) - set(placed)
    if missing:
        raise KeyError(f"export: staircase lines with no receipt section: {sorted(missing)}")
    nulls = dict(s.nulls)
    sections = []
    for sid, slabel, keys in SECTIONS:
        lines = []
        for k in keys:
            if k in nulls and k not in by_key:
                lines.append({"id": k, "label": WORDS[k][0], "engine_label": staircase.EXTRA_LINES.get(k, (k,))[0],
                              "explain": WORDS[k][1], "actual": money(None), "all_gas": money(None),
                              "gap": money(None), "step": [], "basis": None, "status": "not_built",
                              "source_id": None, "source_ids": [], "note": nulls[k], "net_zero": False})
                continue
            if k not in by_key:
                continue
            ln = by_key[k]
            if k not in WORDS:
                raise KeyError(f"export: no plain words for line {k!r}")
            gap_fixed = sum(ln.by_step_fixed_gbp.values())
            gap_slope = sum(ln.by_step_gbp_per_kwh.values())
            ids = source_tokens(ln.source_id)
            lines.append({
                "id": k, "label": WORDS[k][0], "engine_label": ln.label, "explain": WORDS[k][1],
                "actual": money(ln.actual, ln.actual_fixed_gbp, ln.actual_gbp_per_kwh),
                "all_gas": money(ln.all_gas, ln.all_gas_fixed_gbp, ln.all_gas_gbp_per_kwh),
                "gap": money(ln.actual - ln.all_gas, gap_fixed, gap_slope),
                "by_step": {st: money(v, ln.by_step_fixed_gbp[st], ln.by_step_gbp_per_kwh[st])
                            for st, v in ln.by_step.items() if abs(v) > 1e-9},
                "step": _steps_of(ln.step),
                "basis": {"actual": ln.basis_actual, "all_gas": ln.basis_all_gas},
                "status": "verified",
                "source_id": ids[0], "source_ids": ids, "engine_source_id": ln.source_id,
                "note": ln.note, "net_zero": abs(ln.actual - ln.all_gas) > 0.005,
                "policy": sid in ("subsidy", "levies"), "not_net_zero": sid == "not_net_zero",
            })
        sections.append({"id": sid, "label": slabel, "lines": lines})

    # steps: engine totals, with their fixed / per-kWh parts summed from the lines
    steps = []
    for st in staircase.STEPS:
        if st == "1":
            fixed = sum(ln.all_gas_fixed_gbp for ln in s.lines)
            slope = sum(ln.all_gas_gbp_per_kwh for ln in s.lines)
        else:
            fixed = sum(ln.by_step_fixed_gbp[st] for ln in s.lines)
            slope = sum(ln.by_step_gbp_per_kwh[st] for ln in s.lines)
        gbp = s.steps[st]
        if abs(fixed + slope * s.kwh - gbp) > 0.01:
            raise ValueError(f"step {st}: fixed + per-kWh x {s.kwh} != engine total {gbp}")
        steps.append({"id": st, "label": STEP_WORDS[st][0], "explain": STEP_WORDS[st][1],
                      "engine_label": staircase.STEP_NAMES[st], "money": money(gbp, fixed, slope),
                      "basis": "modelled", "source_id": "gascf-staircase"})
    a_fixed = sum(ln.actual_fixed_gbp for ln in s.lines)
    a_slope = sum(ln.actual_gbp_per_kwh for ln in s.lines)
    g = steps[0]["money"]
    c = steps[1]["money"]
    gap = money(s.actual_total - s.all_gas_total, a_fixed - g["fixed_gbp"], a_slope - g["gbp_per_kwh"])
    totals = {
        "with_net_zero": money(s.actual_total, a_fixed, a_slope),
        "without_net_zero": g,
        "gap": gap,
        "gap_without_carbon": money(gap["gbp"] - c["gbp"], gap["fixed_gbp"] - c["fixed_gbp"],
                                    gap["gbp_per_kwh"] - c["gbp_per_kwh"]),
    }
    return {"fleet": s.fleet, "sections": sections, "totals": totals, "steps": steps,
            "carbon_block": carbon_block(s, c), "not_net_zero_block": not_net_zero_block(s),
            "nulls": [{"id": k, "reason": r} for k, r in s.nulls], "notes": list(s.notes),
            "inputs": {k: v for k, v in s.inputs.items() if isinstance(v, (int, float, str))}}


def carbon_block(s, m: dict) -> dict:
    """Decision 2: carbon shown as its own block. All-gas Britain pays no carbon price; the
    carbon taxes are inside 'Electricity itself' in what you pay, and are step 2 of the gap."""
    return {"label": CARBON_LABEL, "money": m, "in_line": "direct_fuel",
            "explain": "All-gas Britain pays no carbon price of any kind. What you pay today includes "
                       "carbon taxes on the gas burned in power stations, inside the wholesale line. "
                       "This is that carbon, counted as a cost of net zero.",
            "basis": "modelled", "source_id": "gascf-staircase",
            "source_ids": ["gascf-staircase", "ukets-ccm-table", "hmrc-cps"]}


def not_net_zero_block(s) -> dict:
    """Decision 3: charges that are not net zero, held equal in both columns, as their own block."""
    lines = [s.line(k) for k in staircase.NOT_NET_ZERO if any(ln.key == k for ln in s.lines)]
    for ln in lines:
        if abs(ln.actual - ln.all_gas) > 1e-9:
            raise ValueError(f"{ln.key}: not net zero, so it must be equal in both columns")
    return {"label": "Not net zero: you pay these either way",
            "ids": [ln.key for ln in lines], "labels": [WORDS[ln.key][0] for ln in lines],
            "money": money(sum(ln.actual for ln in lines), sum(ln.actual_fixed_gbp for ln in lines),
                           sum(ln.actual_gbp_per_kwh for ln in lines)),
            "explain": "Warm Home Discount, help with grid costs in the north of Scotland, and the "
                       "heavy industry discount are not costs of net zero, so they are the same in "
                       "both columns and are not in the gap.",
            "basis": "allowance", "source_id": "ofgem-annex4-v1.25",
            "source_ids": ["ofgem-annex4-v1.25", "desnz-eii-levy-ia-2024"]}


# --------------------------------------------------------------------------- goods, today, break-even

def goods_beside() -> dict:
    """The latest financial year with all three schemes (CfD, RO, FiT), from goods.layer3()."""
    rows = goods.layer3()
    totals = [r for r in rows if r.get("scheme") == "total"]
    if not totals:
        return {"low": None, "central": None, "high": None, "status": "not_built",
                "reason": "UNSOURCED: no complete goods year"}
    t = max(totals, key=lambda r: r["fy"])
    parts = [r for r in rows if r.get("fy") == t["fy"] and r.get("scheme") in ("CfD", "RO", "FiT")]
    ids = []
    for r in parts:
        for tok in source_tokens(r["source_id"]):
            if tok not in ids:
                ids.append(tok)
    ids += ["bank-underground-2023", "ccc-2017", "gascf-goods"]
    pt = t["passed_through"]
    return {"low": pt["low"], "central": pt["central"], "high": pt["high"],
            "period": t["period"], "fy": t["fy"], "basis": t["basis"], "status": "verified",
            "money_note": f"money of financial year {t['period']}, not restated",
            "label": "Subsidies paid by businesses and passed on in the price of what you buy",
            "explain": "Businesses pay the same subsidies on their own electricity bills (Contracts "
                       "for Difference, Renewables Obligation, Feed-in Tariffs) and pass part of the "
                       "cost on in prices. This is an estimate, it is for a past year, and it is "
                       "not added into the figures above.",
            "pass_through_label": t["pass_through_label"],
            "source_id": ids[0], "source_ids": ids}


def p3_today(d: date) -> dict:
    t = today.today(d).as_dict()
    def fig(key, label, caption):
        f = t[key]
        ids = source_tokens(f["source_id"])
        return {"p_per_kwh": f["p_per_kwh"], "gbp_per_mwh": f["gbp_per_mwh"], "label": label,
                "caption": caption, "note": f["note"], "as_of": t["date"], "basis": f["basis"],
                "status": "verified" if f["gbp_per_mwh"] is not None else "not_built",
                "source_id": ids[0], "source_ids": ids}
    return {
        "date": t["date"],
        "market_price": fig("day_ahead", "Market price of power",
                            "Day-ahead wholesale price, average over the day (Elexon)."),
        "fleet_a_pure_gas": fig("fleet_a_pure_gas_cost_of_power", "Today's gas fleet",
                                "Cost of power from today's gas plant at today's gas price, no carbon tax."),
        "fleet_b_pure_gas": fig("fleet_b_pure_gas_cost_of_power", "All-new gas fleet",
                                "Full cost of power from an all-new gas fleet at today's gas price, no carbon tax."),
        "fleet_a_with_carbon": fig("fleet_a_with_carbon", "Today's gas fleet with carbon tax",
                                   "The same, plus the carbon tax."),
        "sap": fig("sap", "Gas price", "Wholesale gas, per kWh of gas (National Gas)."),
        "flags": t["flags"], "notes": t["notes"], "missing_periods": t["missing_periods"],
    }


def p4_break_even(k: tuple) -> dict:
    """Break-even gas price, built on breakeven.py's fits and solver but with this page's rules:
    the not-net-zero lines (staircase.NOT_NET_ZERO) left out of the gap, fleet B's Capacity
    Market rule (staircase, spec §3.3) put in, and each fleet's cost from staircase.fleet_gbp_mwh
    with the same margin and efficiency as the headline. DESNZ's figure ("D"): its fuel part
    moves in proportion to the gas price (DESNZ's own 2030 gas price at £45 of fuel)."""
    from dataclasses import replace
    names = [q.name for q in breakeven.cap_periods() if receipt_actual.period_key(q.name) == k]
    if len(names) != 1:
        raise KeyError(f"export: no single Annex 2 cap period for {k}: {names}")
    ceiling = staircase.BREAK_EVEN_CEILING_GBP_MWH
    fits = {"all": breakeven.fit_cap_periods(False), "ex_epg": breakeven.fit_cap_periods(True)}
    out = {"ceiling_gbp_mwh": ceiling, "fleets": {}, "source_id": "ofgem-annex2-v1.30",
           "source_ids": source_tokens("ofgem-annex2-v1.30; lccc-actual-cfd-generation; lccc-actual-ilr-income"),
           "basis": "modelled", "status": "verified",
           "rule": "not-net-zero lines left out; same fleet costs as the headline"}
    for f in FLEETS:
        s = staircase.staircase(k, f, KWH, ORDER)
        model = breakeven.gap_model(names[0], "A")
        fixed = [ln for ln in model.fixed if ln.key not in staircase.NOT_NET_ZERO]
        if s.inputs.get("cm_gas_share"):
            cm = s.line("capacity_market")
            fixed.append(breakeven.GapLine("capacity_market", (cm.actual - cm.all_gas) / (KWH / 1000),
                                           "4c", "modelled", staircase.SRC_CM,
                                           "gas plant's share of the CM removed in all-gas Britain"))
        model = replace(model, fixed=tuple(fixed),
                        excluded=tuple(x for x in model.excluded if not x.startswith("capacity_market")))
        fc = fleet_cost_of_gas(s)
        res, roots = {}, []
        g0, e0 = model.gas_observed, model.elec_observed
        for kk, fit in fits.items():
            for anchored in (False, True):
                r = breakeven.break_even(fc, model, fit, ceiling, anchored=anchored)
                res[f"{kk}_{'anchored' if anchored else 'fitted'}"] = breakeven.summarise(r, ceiling)
                roots += [x.gas_gbp_mwh for x in r.values() if x.gas_gbp_mwh is not None]
        out["fleets"][f] = {"range": ({"low": min(roots), "high": max(roots)} if roots else None),
                            "text": (f"£{min(roots):.0f}-£{max(roots):.0f}/MWh gas" if roots
                                     else f"none below £{ceiling:.0f}/MWh gas"),
                            "variants": res, "excluded": list(model.excluded),
                            "left_out": list(staircase.NOT_NET_ZERO)}
    return out


def fleet_cost_of_gas(s):
    """The all-gas cost of power (£/MWh at transmission, period money, no carbon) as a function
    of the gas price (£/MWh, period money), on the same inputs as staircase `s`."""
    py = int(s.inputs["price_year"])
    y24 = staircase.PLANT_MONEY_YEAR
    to24, back = rebase(1, py, y24), rebase(1, y24, py)
    if s.fleet == "D":
        dz = staircase.desnz_gas_power_2024()
        g_dz = sens.desnz_gas()["gbp_mwh_2024"].value
        return lambda g: (dz["gbp_mwh_2024"] + dz["fuel"] * (g * to24 / g_dz - 1)) * back
    m24 = rebase(s.inputs["gas_market_margin_gbp_mwh"], py, y24) if s.fleet == "A" else 0
    eta = s.inputs["eta_used"] if s.fleet == "A" else 0
    ly = int(s.inputs["ldc_year"])
    dp = staircase.CACHE_DP
    return lambda g: staircase.fleet_gbp_mwh(s.fleet, ly, round(g * to24, dp), round(m24, dp), eta,
                                             s.inputs["capex_case"], s.inputs["hurdle_case"]) * back


def feedback_threshold(k: tuple, fleet: str, ceiling: float = staircase.FEEDBACK_CEILING) -> dict:
    """Spec §7.4 threshold, on the engine's own staircase: by what share would the gas price in
    all-gas Britain have to rise (from the extra gas it burns) before (a) the whole gap and (b)
    the gap without carbon taxes falls to zero? What you pay is held at Ofgem's allowance."""
    def gaps(mult):
        s = staircase.staircase(k, fleet, KWH, ORDER, gas_mult=mult)
        g = s.actual_total - s.steps["1"]
        return g, g - s.steps["2"]

    def solve(i):
        # Illinois false position on a bracketing pair: the gap falls almost in a straight line as
        # the gas price rises, so this converges in a few staircase runs (bisection needed 24).
        a, b = 0, ceiling
        fa, fb = gaps(1 + a)[i], gaps(1 + b)[i]
        if fb > 0:
            return None
        if fa <= 0:
            return 0
        side = 0
        for _ in range(100):
            c = b - fb * (b - a) / (fb - fa)
            fc = gaps(1 + c)[i]
            if abs(fc) < 0.005 or b - a < 1e-9:     # within half a penny a year
                return c
            if fc > 0:
                a, fa = c, fc
                if side == -1:
                    fb /= 2
                side = -1
            else:
                b, fb = c, fc
                if side == 1:
                    fa /= 2
                side = 1
        raise ValueError(f"feedback threshold for fleet {fleet} did not converge")
    return {"whole_gap": solve(0), "without_carbon": solve(1), "ceiling": ceiling,
            "basis": "modelled", "source_id": "gascf-staircase",
            "note": "the gas price rises in all-gas Britain only; what you pay stays at Ofgem's "
                    "allowance; household gas bills, which would also rise, are not counted"}


# --------------------------------------------------------------------------- shared money helpers

def scaled(m: dict, f: float) -> dict:
    """A Money restated by a factor (a change of money year). Nulls stay null."""
    return money(*(None if v is None else v * f for v in (m["gbp"], m["fixed_gbp"], m["gbp_per_kwh"])))


def stair_totals(s) -> dict:
    """With, without and gap as Money, from one engine staircase; each split checked to 1p."""
    a = money(s.actual_total, sum(ln.actual_fixed_gbp for ln in s.lines),
              sum(ln.actual_gbp_per_kwh for ln in s.lines))
    w = money(s.steps["1"], sum(ln.all_gas_fixed_gbp for ln in s.lines),
              sum(ln.all_gas_gbp_per_kwh for ln in s.lines))
    for m in (a, w):
        if abs(m["fixed_gbp"] + m["gbp_per_kwh"] * s.kwh - m["gbp"]) > 0.01:
            raise ValueError(f"{s.label}: fixed + per-kWh does not rebuild the engine total")
    return {"with_net_zero": a, "without_net_zero": w,
            "gap": money(a["gbp"] - w["gbp"], a["fixed_gbp"] - w["fixed_gbp"],
                         a["gbp_per_kwh"] - w["gbp_per_kwh"])}


def step_monies(s) -> list[dict]:
    out = []
    for st in staircase.STEPS:
        if st == "1":
            fixed = sum(ln.all_gas_fixed_gbp for ln in s.lines)
            slope = sum(ln.all_gas_gbp_per_kwh for ln in s.lines)
        else:
            fixed = sum(ln.by_step_fixed_gbp[st] for ln in s.lines)
            slope = sum(ln.by_step_gbp_per_kwh[st] for ln in s.lines)
        if abs(fixed + slope * s.kwh - s.steps[st]) > 0.01:
            raise ValueError(f"step {st}: fixed + per-kWh x {s.kwh} != engine total {s.steps[st]}")
        out.append({"id": st, "money": money(s.steps[st], fixed, slope)})
    return out


def line_money(s, key: str) -> dict:
    try:
        ln = s.line(key)
    except KeyError:
        return money(None)
    return money(ln.actual, ln.actual_fixed_gbp, ln.actual_gbp_per_kwh)


# --------------------------------------------------------------------------- P5 history

HISTORY_WORDS = {
    "title": "What net zero has added to your bill, each price-cap period",
    "explain": "Each point is one Ofgem price-cap period: what you paid with net zero, minus what the same "
               "electricity would have cost from gas power stations at the pure gas price, in {money_year} "
               "money, at {kwh} kWh a year. The two lines are the two ways of building the gas fleet.",
    "early": "Before January 2019 there was no price cap: Ofgem's figures for 2015 to 2018 are its own "
             "illustration of what the cap would have been.",
    "epg": "October 2022 to June 2023: the Energy Price Guarantee. The government paid part of every "
           "bill, but the figures here are Ofgem's cap, the full cost before that help. Ofgem set its "
           "wholesale allowance from prices it watched months before each period began (for "
           "{window_period}, from {window_first} to {window_last}), so in the crisis the cap lagged the "
           "market, and Ofgem's allowance for Contracts for Difference was a refund. The all-gas "
           "column uses the same Ofgem gas price, so both sides share the lag.",
    "nulls": "Where a line could not be counted for a period it is left out of that period's gap (held "
             "the same in both columns), and listed. Where a whole figure is missing it is shown as a gap "
             "in the line, never filled in.",
}


ANNEX2_ELEC_TAB = "2a(iii) Elec 3-1.5-12"


def annex2_lag_quote() -> str:
    """Ofgem's own words on how the electricity index is observed (Annex 2, Notes tab)."""
    import openpyxl
    ws = openpyxl.load_workbook(staircase.ANNEX2, read_only=True, data_only=True)["Notes"]
    for row in ws.iter_rows(values_only=True):
        for c in row:
            if isinstance(c, str) and c.startswith("This tab calculates the value of the \"3-1.5-12 \" index "
                                                   "for electricity"):
                return " ".join(c.split())
    raise ValueError("Annex 2 Notes: the 3-1.5-12 electricity index description has moved")


def annex2_window(period: tuple) -> dict:
    """First and last day Ofgem watched electricity prices for a cap period (Annex 2 v1.30, tab
    2a(iii), columns A 'Date of price observation' and C 'Charge restriction period'). Raises
    if the period is not in the tab or the header has moved."""
    import openpyxl
    ws = openpyxl.load_workbook(staircase.ANNEX2, read_only=True, data_only=True)[ANNEX2_ELEC_TAB]
    rows = ws.iter_rows(values_only=True)
    for row in rows:
        if row and row[0] == "Date of price observation":
            if row[2] != "Charge restriction period":
                raise ValueError(f"Annex 2 {ANNEX2_ELEC_TAB}: header moved: {row[:3]}")
            break
    else:
        raise ValueError(f"Annex 2 {ANNEX2_ELEC_TAB}: 'Date of price observation' header not found")
    y1, m1, y2, m2 = period
    want = f"Q{(m1 - 1) // 3 + 1} {y1}"
    days = [r[0].date() for r in rows if r and r[2] == want and isinstance(r[0], datetime)]
    if not days:
        raise KeyError(f"Annex 2 {ANNEX2_ELEC_TAB}: no observation dates for {want}")
    return {"period": want, "first": min(days).isoformat(), "last": max(days).isoformat(),
            "source_id": "ofgem-annex2-v1.30"}


def p5_history(money_year: int) -> dict:
    """The headline for every cap period, both fleets, both grid cases, restated to money_year.

    Per period and variant: with, without and gap straight from staircase.staircase (period
    money), then times the GDP deflator factor. The gap is actual minus step 1, never refilled:
    if the staircase raises for a period, that variant is null with the reason."""
    periods = []
    for r in receipt_actual.receipts():
        k = r.period
        py = staircase.price_year(k)
        f = rebase(1, py, money_year)
        d0, d1 = receipt_actual.period_dates(k)
        row = {**period_meta(k, r.label), "start": d0.isoformat(), "end": d1.isoformat(),
               "price_year": py, "to_money_year": f, "cap_in_force": r.cap_in_force,
               "epg": r.epg_in_force, "variants": {}}
        for grid in GRIDS:
            for fl in BUILT:   # DESNZ's figure is for 2030: not used for past periods
                key = f"{fl}|{grid}"
                try:
                    s = staircase.staircase(k, fl, KWH, ORDER, grid=grid)
                except (KeyError, ValueError) as e:
                    row["variants"][key] = {"with_net_zero": money(None), "without_net_zero": money(None),
                                            "gap": money(None), "status": "not_built", "reason": str(e)}
                    continue
                t = stair_totals(s)
                row["variants"][key] = {
                    **{kk: scaled(v, f) for kk, v in t.items()},
                    "gap_period_money": t["gap"],
                    "cfd_on_bill": scaled(line_money(s, "cfd"), f),
                    "not_counted": [{"id": kk, "label": WORDS[kk][0] if kk in WORDS else kk, "reason": why}
                                    for kk, why in s.nulls],
                    "status": "verified", "basis": "modelled",
                }
        periods.append(row)
    epg_last = [pr for pr in periods if pr["epg"]][-1]
    win = annex2_window(receipt_actual.period_key(epg_last["engine_label"]))
    day = lambda iso: f"{date.fromisoformat(iso).day} {date.fromisoformat(iso):%B %Y}"   # noqa: E731
    w = {kk: v.format(money_year=money_year, kwh=f"{int(KWH):,}", window_first=day(win["first"]),
                      window_period=f"{date.fromisoformat(epg_last['start']):%B} to "
                                    f"{date.fromisoformat(epg_last['end']):%B %Y}",
                      window_last=day(win["last"])) for kk, v in HISTORY_WORDS.items()}
    return {**w, "money_year": money_year, "kwh": int(KWH), "default_variant": f"{FLEETS[0]}|{GRIDS[0]}",
            "rule": "gap = with net zero minus step 1 (pure gas price), per period, then restated",
            "ofgem_lag_quote": annex2_lag_quote(), "ofgem_window": win, "periods": periods, "basis": "modelled",
            "status": "verified", "source_id": "gascf-staircase",
            "source_ids": ["gascf-staircase", "hmt-gdp-deflator-sep-2026", "ofgem-annex9-v1.11",
                           "ofgem-annex2-v1.30", "desnz_epg_up_to_30_june_2023"]}


# --------------------------------------------------------------------------- P6 switches

def gas_options(k: tuple) -> list[dict]:
    """The gas-price switch: DESNZ central, today's (Ofgem's index for the period), £60, £100."""
    p = staircase.annex2_periods()[k]
    py = staircase.price_year(k)
    d = sens.desnz_gas(money_year=py)
    th = sens.therm_factor()
    opts = [
        {"id": "desnz", "label": "DESNZ central", "gbp_mwh": d["gbp_mwh"].value,
         "explain": f"The government's own central gas price for 2030 (Fossil Fuel Price Assumptions "
                    f"2025, Assumption B), restated to {py} money. The figure DESNZ uses for its "
                    "generation costs.",
         "basis": "modelled", "source_ids": ["desnz-ffpa-2025", "ofgem-annex2-v1.30", "hmt-gdp-deflator-sep-2026"]},
        {"id": "today", "label": "Today", "gbp_mwh": p.gas_index,
         "explain": "Ofgem's gas price for this cap period, the one in the bill you pay now.",
         "basis": "allowance", "source_ids": ["ofgem-annex2-v1.30"]},
    ] + [{"id": f"{int(g)}", "label": f"£{int(g)}", "gbp_mwh": g,
          "explain": "A higher gas price, for comparison.", "basis": "estimated",
          "source_ids": ["gascf-sensitivity"]} for g in SWITCH_GAS]
    for o in opts:
        o["p_per_therm"] = o["gbp_mwh"] * th
        o["p_per_kwh_gas"] = o["gbp_mwh"] * 100 / 1000      # £/MWh -> p/kWh
        o["source_id"] = o["source_ids"][0]
    return opts


PLANT_APPLIES = {"A": ("eta", "capex", "hurdle", "margin"), "B": ("capex", "hurdle"), "D": ()}
SENS_CASES = {"eta": staircase.ETA_CASES, "capex": staircase.CAPEX_CASES,
              "hurdle": staircase.HURDLE_CASES, "margin": staircase.MARGIN_CASES}
SWITCH_DEFAULT = {"eta": staircase.ETA_CASES[0], "capex": "medium", "hurdle": "medium",
                  "margin": staircase.MARGIN_STAT}
# A fourth gas-price option, "normal years" (Richard, 11 Oct 2026): a named slot, NOT built. It
# needs a sourced definition of a normal year's gas price before any figure goes in it.
GAS_SLOTS_UNBUILT = ({"id": "normal_years", "label": "Normal years", "built": False,
                      "note": "Slot reserved for a gas price from normal (pre-crisis) years. Not "
                              "built: no figure until its definition and source are agreed."},)


def variant(k: tuple, gas_id: str, gas: float, fleet: str, grid: str, eta: str = "dukes",
            capex: str = "medium", hurdle: str = "medium", margin: str = staircase.MARGIN_STAT) -> dict:
    """One precomputed switch setting: the engine staircase with the gas price, grid case and
    plant cases set. 'today' is the plain staircase, so it equals the receipt exactly; other
    prices use the engine's own override (sensitivity._gas_override), which also moves what you
    pay. DESNZ's figure ("D") carries its own 2030 gas price: at 'today' it is DESNZ's figure as
    printed; at another price its fuel part is scaled by that price over DESNZ's."""
    py = staircase.price_year(k)
    mult = 1
    if fleet == "D" and gas_id != "today":
        mult = gas / sens.desnz_gas(money_year=py)["gbp_mwh"].value
    ctx = nullcontext() if gas_id == "today" else sens._gas_override(k, gas, "all", True)
    with ctx:
        s = staircase.staircase(k, fleet, KWH, ORDER, grid=grid, eta=eta, capex=capex, hurdle=hurdle,
                                gas_mult=mult, margin=margin)
    t = stair_totals(s)
    st = step_monies(s)
    c = st[1]["money"]
    t["gap_without_carbon"] = money(t["gap"]["gbp"] - c["gbp"], t["gap"]["fixed_gbp"] - c["fixed_gbp"],
                                    t["gap"]["gbp_per_kwh"] - c["gbp_per_kwh"])
    sm = {x["id"]: x["money"]["gbp"] for x in st}
    return {**t, "steps": st,
            "net_zero_pence_per_pound": 100 * t["gap"]["gbp"] / t["with_net_zero"]["gbp"],
            "at_least_test_gbp": sm["4a"] + sm["4b"] + min(0, sm["4c"]),
            "fleet_gbp_mwh": s.inputs["fleet_gbp_mwh"], "identity_residual": s.identity_residual,
            "basis": "modelled", "source_id": "gascf-staircase" if gas_id == "today" else "gascf-sensitivity"}


def sensitivity_rows(k: tuple, base: dict) -> list[dict]:
    """Efficiency, build cost, hurdle rate and gas-market margin: one at a time from the default
    (today's gas price, grid counted as nil), for each gas-power choice they apply to. `base` is
    the full-grid variants, so each row also carries its change from the default."""
    rows = []
    for fl in FLEETS:
        b = base[f"today|{fl}|{GRIDS[0]}"]
        for sw in PLANT_APPLIES[fl]:
            for case in SENS_CASES[sw]:
                if case == SWITCH_DEFAULT[sw]:
                    continue
                v = variant(k, "today", 0, fl, GRIDS[0], **{**SWITCH_DEFAULT, sw: case})
                rows.append({"fleet": fl, "switch": sw, "case": case,
                             "gap": v["gap"], "gap_without_carbon": v["gap_without_carbon"],
                             "change_gbp": v["gap"]["gbp"] - b["gap"]["gbp"],
                             "at_least_test_gbp": v["at_least_test_gbp"],
                             "fleet_gbp_mwh": v["fleet_gbp_mwh"], "identity_residual": v["identity_residual"],
                             "basis": "modelled", "source_id": "gascf-staircase"})
    return rows


def p6_switches(k: tuple) -> dict:
    """The page's switches (Richard, 11 Oct 2026). Full grid ONLY for gas-power choice (A, B, D)
    x gas price (today, DESNZ central, £60, £100) x grid build-out (nil, Ofgem's whole step-up):
    24 settings. Efficiency, build cost, hurdle rate and margin: one at a time from the default,
    as a sensitivity table. Spec §7.2's "at least" test and the range run over both."""
    gas = gas_options(k)
    variants = {f"{o['id']}|{fl}|{grid}": variant(k, o["id"], o["gbp_mwh"], fl, grid)
                for o in gas for fl in FLEETS for grid in GRIDS}
    sens_rows = sensitivity_rows(k, variants)
    g = staircase.staircase(k, "A", KWH, ORDER).inputs   # plant/margin settings describe fleet A
    kit = staircase._fleet_kit()
    pool = {**{x: (v["gap"]["gbp"], v["at_least_test_gbp"]) for x, v in variants.items()},
            **{f"sens|{r['fleet']}|{r['switch']}={r['case']}": (r["gap"]["gbp"], r["at_least_test_gbp"])
               for r in sens_rows}}
    lo_w = min(pool, key=lambda x: pool[x][1])
    gaps = {x: v[0] for x, v in pool.items()}
    ms = {y: staircase.margin_stats(y) for y in (int(g["margin_year"]),)}
    return {
        "default": {"gas": "today", "fleet": DEFAULT_FLEET, "grid": GRIDS[0]},
        "key": "gas|fleet|grid",
        "gas": gas,
        "gas_slots_unbuilt": list(GAS_SLOTS_UNBUILT),
        "fleet": [{"id": f, "label": FLEET_WORDS[f]["label"], "explain": FLEET_WORDS[f]["description"]}
                  for f in FLEETS],
        "grid": [
            {"id": GRIDS[0], "label": "Counted as nil", "gbp": g["grid_netzero_low"],
             "explain": "Ofgem does not say how much of the grid build-out is for wind and solar rather "
                        "than for rising demand, so by default none of it is counted."},
            {"id": GRIDS[-1], "label": "Ofgem's whole step-up", "gbp": g["grid_netzero_high"],
             "explain": "The whole rise in high-voltage grid charges from April 2026 that Ofgem says "
                        "supports its clean-power plans, per household."},
        ],
        "sensitivity": {
            "default": dict(SWITCH_DEFAULT),
            "applies": {f: list(v) for f, v in PLANT_APPLIES.items()},
            "from": {"gas": "today", "grid": GRIDS[0]},
            "rows": sens_rows,
            "cases": {
                "eta": [
                    {"id": "dukes", "label": "As measured", "value": g["eta_existing"],
                     "explain": "Today's gas power stations at the efficiency DESNZ measured for the "
                                "fleet (DUKES Table 5.10)."},
                    {"id": "new", "label": "As good as new", "value": kit["ccgt"].efficiency_gcv,
                     "explain": "Today's gas power stations as efficient as a new one (DESNZ "
                                "Generation Costs 2025)."}],
                "capex": [{"id": c, "label": c.capitalize(),
                           "explain": f"DESNZ's {c} estimate of what a new gas power station costs to build."}
                          for c in staircase.CAPEX_CASES],
                "hurdle": [{"id": h, "label": f"{100 * kit['ccgt'].hurdle[h]:.1f}%",
                            "value": kit["ccgt"].hurdle[h],
                            "explain": f"DESNZ's {h} return on the money borrowed to build new gas plant."}
                           for h in staircase.HURDLE_CASES],
                "margin": [{"id": m, "label": {"vw_mean": "Average, weighted by volume", "mean": "Average",
                                               "median": "Middle value"}[m],
                            "value": ms[int(g["margin_year"])][m],
                            "explain": "The gap between the market price of power and the cost of the "
                                       "gas, in half-hours when gas sets the price."}
                           for m in staircase.MARGIN_CASES],
            },
        },
        "gas_note": "Changing the gas price moves both columns. Without net zero, the gas fleet's cost "
                    "follows the gas price. With net zero, what you pay follows the link between gas and "
                    "wholesale electricity prices in Ofgem's own cap periods since 2015; the subsidy for "
                    "Contracts for Difference moves the other way.",
        "variants": variants,
        "range": {"low": min(gaps.values()), "high": max(gaps.values()),
                  "low_key": min(gaps, key=gaps.get), "high_key": max(gaps, key=gaps.get),
                  "n": len(gaps), "over": "the 24-setting grid and every sensitivity row"},
        "at_least": {"rule": "spec §7.2: X = min over every switch of [4(a) + 4(b) + min(0, 4(c))]",
                     "x_gbp": pool[lo_w][1], "at_key": lo_w, "passed": pool[lo_w][1] > 0},
        "source_id": "gascf-sensitivity",
        "source_ids": ["gascf-sensitivity", "gascf-staircase", "ofgem_riio3_fd_impact_assessment_t3",
                       "lccc-actual-cfd-generation", "desnz-egc2025-annexA", "dukes-5.10"],
    }


# --------------------------------------------------------------------------- P9 "isn't renewable power cheaper?"

def _pdf_text(path: Path) -> str:
    return " ".join(" ".join(pg.get_text() for pg in pymupdf.open(path)).split())


def ar7_results(path: Path = AR7_PDF) -> dict:
    """DESNZ AR7 results, table (E) clearing strike prices and table (F) total MW. Raises if the
    layout moves."""
    lines = [ln.strip() for pg in pymupdf.open(path) for ln in pg.get_text().splitlines() if ln.strip()]
    flat = " ".join(lines)
    m = re.search(r"published today (\d+ [A-Z]+ \d{4}) published the outcome|today (\d+ [A-Z]+ \d{4})", flat)
    if not m:
        raise ValueError("AR7 results: publication date not found")
    published = next(x for x in m.groups() if x).title()
    try:
        e0 = next(i for i, ln in enumerate(lines) if ln.startswith("(E) Maximum % saving"))
        f0 = next(i for i, ln in enumerate(lines) if ln.startswith("(F) Breakdown"))
    except StopIteration:
        raise ValueError("AR7 results: tables (E)/(F) not found") from None
    block = lines[e0:f0]
    if "saving" not in block or not any("Clearing Strike" in b for b in block):
        raise ValueError("AR7 results: table (E) header moved")
    bases = re.findall(r"\((\d{4}) prices\)", " ".join(block))
    if len(set(bases)) != len(("old", "new")):
        raise ValueError(f"AR7 results: table (E) price bases {bases}")
    old_base, new_base = sorted(set(bases), key=int)
    body = block[block.index("saving") + 1:]
    num = re.compile(r"^[\d.]+%?$")
    techs = {}
    i = 0
    cols = ("asp_old", "asp_new", "strike_old", "strike_new", "saving_pct")
    n = len(cols)
    while i < len(body):
        cells = body[i + 1:i + 1 + n]
        if not num.match(body[i]) and len(cells) == n and all(num.match(x) for x in cells):
            techs[body[i]] = {c: float(v.rstrip("%")) for c, v in zip(cols, cells)}
            i += n + 1
        else:
            i += 1
    if "Offshore Wind" not in techs:
        raise ValueError(f"AR7 results: no 'Offshore Wind' row in table (E): {list(techs)}")
    tail = lines[f0:]
    try:
        t = tail.index("Total %")
    except ValueError:
        raise ValueError("AR7 results: table (F) total row moved") from None
    mw = float([x for x in tail[t + 1:] if num.match(x) and "%" not in x][0])
    try:
        d0 = next(i for i, ln in enumerate(lines) if ln.startswith("(D) Breakdown"))
        d1 = lines.index("Total", d0)
    except (StopIteration, ValueError):
        raise ValueError("AR7 results: table (D) header moved") from None
    years = [ln for ln in lines[d0:d1] if re.fullmatch(r"\d{4}/\d{2}", ln)]
    if not years:
        raise ValueError("AR7 results: no delivery years in table (D)")
    return {"published": published, "techs": techs, "total_mw": mw, "delivery_years": years,
            "price_base": int(new_base), "old_price_base": int(old_base)}


EGC_SCOPE_QUOTE = ("Wider system costs beyond those faced by the developer, and wider system benefits of "
                   "deploying generation assets. These cannot be assessed without whole power system modelling.")


def egc_scope_quote(path: Path = EGC_PDF) -> str:
    if EGC_SCOPE_QUOTE not in _pdf_text(path):
        raise ValueError("DESNZ EGC 2025: the 'out of scope' sentence is not in the stored report")
    return EGC_SCOPE_QUOTE


def p9_opposing_case(k: tuple, hist: dict, sw: dict, money_year: int) -> dict:
    """The opposing case at its strongest, each point with its primary source, each answered with
    the engine's own numbers. Words carry {placeholders}; `figures` holds every value."""
    figs = {}

    def fig(key, value, fmt, basis, source_ids, note=""):
        figs[key] = {"value": value, "fmt": fmt, "basis": basis, "source_id": source_ids[0],
                     "source_ids": source_ids, "note": note}

    # --- point 1: CfD strike prices below wholesale
    ar7 = ar7_results()
    off = ar7["techs"]["Offshore Wind"]
    p = staircase.annex2_periods()[k]
    rec = sens.reconcile(k)
    rows = sens.sweep(k, KWH, fleets=FLEETS, slopes=("all",))
    d_gas = sw["gas"][0]["gbp_mwh"]
    e_desnz = next(r.elec_index for r in rows if abs(r.gas_gbp_mwh - d_gas) < 1e-9)
    vol = breakeven.cfd_volume()
    fig("ar7_strike", off["strike_new"], "gbp2", "measured", ["desnz-cfd-ar7-results"],
        f"clearing strike price, offshore wind, {ar7['price_base']} prices")
    fig("ar7_price_base", ar7["price_base"], "year", "measured", ["desnz-cfd-ar7-results"])
    fig("ar7_mw", ar7["total_mw"], "mw0", "measured", ["desnz-cfd-ar7-results"])
    fig("ar7_published", ar7["published"], "text", "measured", ["desnz-cfd-ar7-results"])
    fig("ar7_first_year", ar7["delivery_years"][0], "text", "measured", ["desnz-cfd-ar7-results"])
    fig("ar7_last_year", ar7["delivery_years"][-1], "text", "measured", ["desnz-cfd-ar7-results"])
    fig("ar7_strike_now", rebase(off["strike_new"], ar7["price_base"], money_year), "gbp2", "modelled",
        ["desnz-cfd-ar7-results", "hmt-gdp-deflator-sep-2026"], f"restated to {money_year} money")
    fig("elec_index_now", p.elec_index, "gbp2", "allowance", ["ofgem-annex2-v1.30"],
        f"Ofgem's wholesale electricity index for {period_meta(k, '')['label']}, {staircase.price_year(k)} money")
    fig("elec_index_at_desnz_gas", e_desnz, "gbp2", "modelled", ["gascf-sensitivity", "desnz-ffpa-2025"],
        "Ofgem's index moved along its own 2015-2026 link to the gas price")
    fig("desnz_gas_gbp_mwh", d_gas, "gbp2", "modelled", ["desnz-ffpa-2025"])
    fig("lccc_topup_gbp_mwh", vol.payments_gbp / vol.generation_mwh, "gbp2", "measured",
        ["lccc-actual-cfd-generation"], "CfD payments / CfD generation")
    fig("lccc_payments_gbpm", vol.payments_gbp / MILLION, "gbpm", "measured", ["lccc-actual-cfd-generation"])
    fig("lccc_generation_twh", vol.generation_mwh / MILLION, "twh1", "measured", ["lccc-actual-cfd-generation"])
    fig("lccc_start", vol.start.isoformat(), "date", "measured", ["lccc-actual-cfd-generation"])
    fig("lccc_end", vol.end.isoformat(), "date", "measured", ["lccc-actual-cfd-generation"])

    # --- the sensitivity table (all-period slope), at the reference size
    sweep_rows = [{"label": r.label, "gas_gbp_mwh": r.gas_gbp_mwh, "fleet": r.fleet,
                   "with_net_zero_gbp": r.actual_total, "without_net_zero_gbp": r.step1,
                   "gap_gbp": r.headline} for r in rows]
    gaps = [r["gap_gbp"] for r in sweep_rows]
    fig("sweep_min_gap", min(gaps), "gbp0", "modelled", ["gascf-sensitivity"])
    fig("sweep_max_gap", max(gaps), "gbp0", "modelled", ["gascf-sensitivity"])
    fig("sweep_min_gas", min(r["gas_gbp_mwh"] for r in sweep_rows), "gbp0", "estimated", ["gascf-sensitivity"])
    fig("sweep_max_gas", max(r["gas_gbp_mwh"] for r in sweep_rows), "gbp0", "estimated", ["gascf-sensitivity"])

    # --- point 2: DESNZ levelised costs
    lc = read_desnz_levelised(sens.ANNEX_A, sens.DESNZ_YEAR)
    lcoe = []
    for t in LCOE_TECHS + (sens.DESNZ_COLUMN,):
        if t not in lc:
            raise KeyError(f"DESNZ Annex A {sens.DESNZ_YEAR}: no column {t!r}")
        tot, carb = lc[t]["Total"], lc[t].get("Carbon costs") or 0
        lcoe.append({"tech": re.sub(r"\d+$", "", t).strip(), "total": tot, "carbon": carb,
                     "without_carbon": tot - carb, "basis": "measured", "source_id": "desnz-egc2025-annexA"})
    gas_lcoe = lcoe[-1]
    fig("desnz_gas_total", gas_lcoe["total"], "gbp0", "measured", ["desnz-egc2025-annexA"])
    fig("desnz_gas_carbon", gas_lcoe["carbon"], "gbp0", "measured", ["desnz-egc2025-annexA"])
    fig("desnz_gas_ex_carbon", gas_lcoe["without_carbon"], "gbp0", "measured", ["desnz-egc2025-annexA"])
    for i, t in enumerate(LCOE_TECHS):
        fig(f"desnz_lcoe_{i}", lcoe[i]["total"], "gbp0", "measured", ["desnz-egc2025-annexA"], lcoe[i]["tech"])
    fa, fb = (sw["variants"][f"today|{f}|{GRIDS[0]}"]["fleet_gbp_mwh"] for f in BUILT)
    fig("fleet_a_now", fa, "gbp2", "modelled", ["gascf-staircase"], f"{money_year} money")
    fig("fleet_b_now", fb, "gbp2", "modelled", ["gascf-staircase"], f"{money_year} money")
    walk = {f: [{"name": st.name, "delta": st.delta, "level": st.level, "money": st.money,
                 "basis": st.basis, "source_ids": source_tokens(re.sub(r"\([^)]*\)", "", st.source_id)),
                 "note": st.note} for st in rec[f]] for f in BUILT}
    for f in BUILT:
        for st in walk[f]:
            st["source_id"] = st["source_ids"][0]
    step_gas = next(st for st in walk["B"] if st["name"].startswith("Gas price"))
    step_part = next(st for st in walk["B"] if st["name"].startswith("Running part-time"))
    fig("walk_gas_delta", step_gas["delta"], "gbp2", "modelled", ["gascf-sensitivity"])
    fig("walk_parttime_delta", step_part["delta"], "gbp2", "modelled", ["gascf-sensitivity"])
    fig("egc_quote", egc_scope_quote(), "text", "measured", ["desnz-egc-2025-report"])

    # --- point 3: CfD refunds in 2022
    cfd = goods.read_cfd()
    epg = [pr for pr in hist["periods"] if pr["epg"]]
    if not epg:
        raise ValueError("p5_history: no Energy Price Guarantee periods found")
    e0 = date.fromisoformat(epg[0]["start"])
    low = e0.year if e0.month >= FY_START_MONTH else e0.year - 1   # financial year of the first EPG period
    if low not in cfd or low - 2 not in cfd:
        raise KeyError(f"LCCC levy rates: no financial year {low} or {low - 2}")
    fy_rows = [{"fy": goods.fy_label(fy), "cost_gbpm": cfd[fy].cost_gbp / MILLION, "basis": cfd[fy].basis,
                "source_id": cfd[fy].source_id} for fy in sorted(cfd) if low - 2 <= fy <= low + 1]   # two years before to one after
    fig("cfd_low_fy", goods.fy_label(low), "text", "measured", ["LCCC-RDLR"])
    fig("cfd_low_fy_gbpm", cfd[low].cost_gbp / MILLION, "gbpm", "measured", ["LCCC-RDLR"])
    fig("cfd_before_gbpm", cfd[low - 2].cost_gbp / MILLION, "gbpm", "measured", ["LCCC-RDLR"],
        goods.fy_label(low - 2))
    dv = hist["default_variant"]
    refund = [pr["variants"][dv]["cfd_on_bill"]["gbp"] for pr in epg]
    fig("epg_cfd_refund_max", -min(refund), "gbp2", "allowance", ["ofgem-cap-model-v1.31"],
        f"largest CfD refund in Ofgem's cap, Energy Price Guarantee periods, {money_year} money")
    epg_gaps = [pr["variants"][f"{f}|{GRIDS[0]}"]["gap"]["gbp"] for pr in epg for f in BUILT]
    fig("epg_gap_min", min(epg_gaps), "gbp0", "modelled", ["gascf-staircase"])
    fig("epg_gap_max", max(epg_gaps), "gbp0", "modelled", ["gascf-staircase"])
    all_gaps = [v["gap"]["gbp"] for pr in hist["periods"] for v in pr["variants"].values()
                if v["gap"]["gbp"] is not None]
    fig("history_min_gap", min(all_gaps), "gbp0", "modelled", ["gascf-staircase"], f"{money_year} money")
    fig("history_n_periods", len(hist["periods"]), "int", "modelled", ["gascf-staircase"])

    points = [
        {"id": "strike",
         "claim": "New wind power is now cheaper than the market price.",
         "case": "In the government's latest auction, published {ar7_published}, offshore wind won "
                 "Contracts for Difference for {ar7_mw} at a strike price of {ar7_strike} a MWh in "
                 "{ar7_price_base} money, about {ar7_strike_now} in {money_year} money. That is below Ofgem's "
                 "wholesale electricity price for this quarter, {elec_index_now} a MWh, and below what "
                 "our own gas fleets would cost at today's gas price, {fleet_a_now} to {fleet_b_now} a "
                 "MWh. When the market price is above the strike price, the wind farm pays the "
                 "difference back.",
         "answer": "On these figures the point stands for new contracts, and we say so. But they are not "
                   "on your bill yet: these wind farms start delivering between {ar7_first_year} and "
                   "{ar7_last_year}. What you pay now "
                   "carries the contracts already signed. In the 12 months from {lccc_start} to "
                   "{lccc_end}, Contract for Difference generators were paid {lccc_topup_gbp_mwh} a MWh "
                   "on top of the market price, {lccc_payments_gbpm} in all for {lccc_generation_twh}. "
                   "And the wholesale price they are compared with is set by gas: at DESNZ's own central "
                   "gas price ({desnz_gas_gbp_mwh} a MWh of gas), Ofgem's wholesale index would be about "
                   "{elec_index_at_desnz_gas}, and these contracts would be paid a top-up, not pay one "
                   "back. Across gas prices from {sweep_min_gas} to {sweep_max_gas} a MWh, our engine "
                   "finds net zero adds {sweep_min_gap} to {sweep_max_gap} a year to a {kwh} kWh bill "
                   "(table below).",
         "source_ids": ["desnz-cfd-ar7-results", "ofgem-annex2-v1.30", "lccc-actual-cfd-generation",
                        "desnz-ffpa-2025", "gascf-sensitivity"]},
        {"id": "lcoe",
         "claim": "The government's own figures say wind and solar are the cheapest power.",
         "case": "DESNZ's Electricity Generation Costs 2025 puts new plants starting in {lcoe_year} at "
                 "{desnz_lcoe_0} a MWh for large solar, {desnz_lcoe_1} for onshore wind and "
                 "{desnz_lcoe_2} for offshore wind, against {desnz_gas_total} for a new gas power "
                 "station (2024 money).",
         "answer": "Two things sit inside DESNZ's gas figure. First, {desnz_gas_carbon} of it is carbon "
                   "tax, which is itself a cost of net zero; without it the gas plant costs "
                   "{desnz_gas_ex_carbon}. Second, it is one plant running most of the year at DESNZ's "
                   "central gas price. We rebuild DESNZ's figure from its own inputs and walk it to our "
                   "fleets (table below). In DESNZ's 2024 money, today's gas price adds {walk_gas_delta} a "
                   "MWh, and a fleet that follows demand, running part-time, adds a further "
                   "{walk_parttime_delta}. With pipeline charges, spare plant and the change to "
                   "{money_year} money, our fleets cost {fleet_a_now} to {fleet_b_now} a MWh. Our gas fleets carry "
                   "their own spare plant and pipeline charges. DESNZ's wind and solar figures leave out "
                   "the cost of backing them up and connecting them; DESNZ says so itself: "
                   "\u201c{egc_quote}\u201d",
         "source_ids": ["desnz-egc2025-annexA", "desnz-egc-2025-report", "gascf-sensitivity"]},
        {"id": "refunds",
         "claim": "In the 2022 gas crisis, renewables paid money back to bill payers.",
         "case": "When wholesale prices soared, many Contract for Difference generators paid back more "
                 "than they were paid. LCCC's figures show the scheme's net cost fell to "
                 "{cfd_low_fy_gbpm} in financial year {cfd_low_fy}, from {cfd_before_gbpm} two years "
                 "before.",
         "answer": "True, and it is already in our figures. What you pay (the with-net-zero column) uses "
                   "Ofgem's own allowance for Contracts for Difference, which in the Energy Price "
                   "Guarantee periods was a refund of up to {epg_cfd_refund_max} a year at {kwh} kWh ({money_year} money). "
                   "Even with the refund netted off, net zero added {epg_gap_min} to {epg_gap_max} a "
                   "year in those periods. Across all {history_n_periods} cap periods since April 2015 "
                   "(chart above), the smallest gap on the chart is {history_min_gap}. The refunds were "
                   "real, but much smaller than the subsidies, carbon tax and levies around them.",
         "source_ids": ["LCCC-RDLR", "ofgem-cap-model-v1.31", "gascf-staircase"]},
    ]
    fig("lcoe_year", sens.DESNZ_YEAR, "year", "measured", ["desnz-egc2025-annexA"])
    fig("kwh", int(KWH), "int", "estimated", ["ofgem_tdcv_2026"])
    fig("money_year", money_year, "year", "modelled", ["hmt-gdp-deflator-sep-2026"])
    # the words make claims; check each still holds on the engine's numbers, or stop
    v = {kk: x["value"] for kk, x in figs.items()}
    checks = {
        "strike below today's wholesale": v["ar7_strike_now"] < v["elec_index_now"],
        "strike below both fleets today": v["ar7_strike_now"] < min(v["fleet_a_now"], v["fleet_b_now"]),
        "top-up at DESNZ gas": v["elec_index_at_desnz_gas"] < v["ar7_strike_now"],
        "LCCC top-up paid": v["lccc_topup_gbp_mwh"] > 0,
        "refund smaller than the EPG gap": v["epg_cfd_refund_max"] < v["epg_gap_min"],
        "refund was a refund": v["epg_cfd_refund_max"] > 0,
        "net zero adds in every period": v["history_min_gap"] > 0,
        "gas cheaper than offshore without carbon": v["desnz_gas_ex_carbon"] < v["desnz_lcoe_2"],
        "CfD cost fell": v["cfd_low_fy_gbpm"] < v["cfd_before_gbpm"],
    }
    bad = [kk for kk, ok in checks.items() if not ok]
    if bad:
        raise ValueError(f"p9: the words no longer match the numbers: {bad}")
    for pt in points:
        for part in ("case", "answer"):
            for name in re.findall(r"\{(\w+)\}", pt[part]):
                if name not in figs:
                    raise KeyError(f"p9: placeholder {{{name}}} in point {pt['id']} has no figure")
    return {"title": "\u201cIsn't renewable power cheaper?\u201d",
            "intro": "The case against our answer, at its strongest, with its sources. Each point is "
                     "answered with the engine's own numbers.",
            "points": points, "figures": figs,
            "sensitivity": {"rows": sweep_rows, "kwh": int(KWH), "slope": "all",
                            "note": "What you pay, without net zero and the gap at each gas price, at "
                                    f"{int(KWH):,} kWh, {staircase.price_year(k)} money, carbon first.",
                            "source_id": "gascf-sensitivity", "source_ids": ["gascf-sensitivity"]},
            "lcoe": {"year": sens.DESNZ_YEAR, "money": "2024", "rows": lcoe,
                     "source_id": "desnz-egc2025-annexA", "source_ids": ["desnz-egc2025-annexA"]},
            "reconciliation": walk,
            "cfd_years": fy_rows,
            "source_id": "gascf-sensitivity",
            "source_ids": sorted({sid for pt in points for sid in pt["source_ids"]})}


# --------------------------------------------------------------------------- the file

def build(d: date | None = None, period: tuple | None = None) -> dict:
    k = period or latest_period()
    st = {f: staircase.staircase(k, f, KWH, ORDER) for f in FLEETS}
    sa = st[DEFAULT_FLEET]
    for f, s in st.items():
        if abs(sa.actual_total - s.actual_total) > 0.005:
            raise ValueError("what you pay differs between fleets: the actual column must not depend on the fleet")
    rec = {f: receipt(s) for f, s in st.items()}
    gap = {f: rec[f]["totals"]["gap"] for f in FLEETS}
    by_gap = sorted(FLEETS, key=lambda f: gap[f]["gbp"])
    lo, hi = by_gap[0], by_gap[-1]
    money_year = int(sa.inputs["price_year"])
    if d is None:
        d = max(sap_gbp_per_mwh())
    sources_used = set()

    def collect(o):
        if isinstance(o, dict):
            for kk, v in o.items():
                if kk in ("source_ids",) and isinstance(v, list):
                    sources_used.update(v)
                elif kk == "source_id" and isinstance(v, str):
                    sources_used.add(v)
                else:
                    collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)

    with_nz = rec[DEFAULT_FLEET]["totals"]["with_net_zero"]
    dflt = rec[DEFAULT_FLEET]["totals"]
    data = {
        "schema_version": SCHEMA_VERSION,
        "status": "draft",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine": engine_meta(),
        "period": period_meta(k, sa.label),
        "money_year": money_year,
        "household": {
            "reference_kwh": int(KWH),
            "description": "One household for one year, Great Britain average, single-rate meter, "
                           "paying by Direct Debit, on Ofgem's price cap.",
            "presets": presets_from_tdcv(),
            "slider": {"min_kwh": 1000, "max_kwh": 6000, "step_kwh": 100},
            "note": "Ofgem's 'typical' household is a yardstick for comparing bills, not the "
                    "average household.",
        },
        "fleets": {f: {**FLEET_WORDS[f]} for f in FLEETS},
        "headline": {
            "rule": "net zero costs = with net zero (what you pay) minus without net zero (step 1, "
                    "all-gas Britain, no carbon price). Carbon taxes are a cost of net zero, inside "
                    "the gap, shown as their own block. Charges that are not net zero are the same in "
                    "both columns, so they are not in the gap.",
            "default_fleet": DEFAULT_FLEET,
            "with_net_zero_gbp": with_nz,
            "without_net_zero_gbp": {f: rec[f]["totals"]["without_net_zero"] for f in FLEETS},
            "net_zero_costs_gbp": {f: gap[f] for f in FLEETS},
            "net_zero_costs_without_carbon_gbp": {f: rec[f]["totals"]["gap_without_carbon"] for f in FLEETS},
            "carbon_gbp": {f: rec[f]["carbon_block"]["money"] for f in FLEETS},
            "range_across_fleets": {"low": gap[lo], "low_fleet": lo, "high": gap[hi], "high_fleet": hi},
            "default": {"gap": dflt["gap"], "gap_without_carbon": dflt["gap_without_carbon"],
                        "pence_per_pound": 100 * dflt["gap"]["gbp"] / with_nz["gbp"]},
            "desnz_beside": {"fleet": "D", "gap": gap["D"],
                             "label": "On the Government's own cost of gas power"},
            "net_zero_pence_per_pound": {f: 100 * gap[f]["gbp"] / with_nz["gbp"] for f in FLEETS},
            "no_carbon_statement": "A Britain without net zero has no carbon price: carbon taxes exist "
                                   "to drive net zero, so they are a cost of it.",
            "not_net_zero": rec[DEFAULT_FLEET]["not_net_zero_block"],
            "goods_beside_gbp": goods_beside(),
            "basis": "modelled", "status": "verified", "source_id": "gascf-staircase",
            "source_ids": ["gascf-staircase"],
        },
        "p2_receipt": {"fleets": rec},
        "p3_today": p3_today(d),
        "p4_break_even": p4_break_even(k),
        "p5_history": None, "p6_switches": None, "p7_provenance": None, "p8_forward": None,
        "p9_opposing_case": None,
        "sources": {},
    }
    data["p5_history"] = p5_history(money_year)
    data["p6_switches"] = p6_switches(k)
    sw = data["p6_switches"]
    data["headline"]["at_least"] = sw["at_least"]
    data["headline"]["range_across_switches"] = {**sw["range"],
        "note": "the range covers every setting of the page's switches, including the gas price, "
                "and every row of the sensitivity table"}
    data["methods"] = {
        "feedback": {**{f: feedback_threshold(k, f) for f in FLEETS},
                     "explain": "All-gas Britain would burn far more gas, which could push up the gas "
                                "price. These are the rises in the gas price, in all-gas Britain only, "
                                "at which the gap would fall to nothing. Nobody has published how much "
                                "the price would actually rise.",
                     "source_id": "gascf-staircase", "source_ids": ["gascf-staircase"]},
        "margin": {"stat": staircase.MARGIN_STAT,
                   "year": st["A"].inputs["margin_year"],
                   "stats_gbp_mwh": staircase.margin_stats(int(st["A"].inputs["margin_year"])),
                   "explain": "Today's gas power stations sell power for more than their gas costs. We "
                              "add the average gap between the market price of power and the cost of "
                              "the gas, each half-hour weighted by how much power was sold "
                              "(volume-weighted mean). It is the highest of the three ways of "
                              "averaging, so it makes all-gas Britain dearest and the gap smallest.",
                   "decided": "11 Oct 2026",
                   "source_id": "gascf-staircase", "source_ids": ["gascf-staircase", "elexon-mid-apx", "nationalgas-sap"]},
        "capacity_market": {"gas_share": {**staircase.cm_gas_share(),
                                          "source_id": "ofgem-cm-annual-report-2022-23",
                                          "source_ids": source_tokens(staircase.SRC_CM)},
                            "source_id": "ofgem-cm-annual-report-2022-23",
                            "source_ids": ["ofgem-cm-annual-report-2022-23", "ofgem-cm-annual-report-2025-26"]},
        "decision_sources": {
            "eco": {"keep": True, "source_id": "desnz-eco4-guidance",
                    "quote": "contribute to carbon reduction targets in the domestic sector"},
            "sizewell_c": {"keep": True, "source_id": "desnz-szc-fid-vfm",
                           "quote": "required for a low cost, net zero compliant energy system"},
            "eii_levy": {"keep": False, "source_id": "desnz-eii-levy-ia-2024",
                         "quote": "compensate eligible EIIs for a proportion of the network charging "
                                  "costs element in their energy bills"},
            "whd": {"keep": False, "why": "a rebate for poorer households (Richard, 11 Oct 2026)"},
            "aahedc": {"keep": False, "why": "help with grid costs in the north of Scotland (Richard, 11 Oct 2026)"},
        },
    }
    data["p9_opposing_case"] = p9_opposing_case(k, data["p5_history"], data["p6_switches"], money_year)
    collect(data)
    data["sources"] = {sid: SOURCES[sid] for sid in sorted(sources_used)}
    return data


def write(data: dict, out_dir: Path = OUT, site: Path | None = SITE_JSON) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{data['generated_at'][:10]}.json"
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    if site is not None:
        site.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, site)
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=str(SITE_JSON), help="where to copy latest.json ('' to skip)")
    ap.add_argument("--out", default=str(OUT), help="directory for the dated file")
    a = ap.parse_args()
    data = build()
    path = write(data, out_dir=Path(a.out), site=Path(a.site) if a.site else None)
    h = data["headline"]
    print(f"wrote {path}")
    print(f"with net zero £{h['with_net_zero_gbp']['gbp']:.2f}")
    for f in FLEETS:
        print(f"  {f}: without £{h['without_net_zero_gbp'][f]['gbp']:.2f}; gap £{h['net_zero_costs_gbp'][f]['gbp']:.2f}; "
              f"without carbon £{h['net_zero_costs_without_carbon_gbp'][f]['gbp']:.2f}")
    print(f"range across switches £{h['range_across_switches']['low']:.2f} to £{h['range_across_switches']['high']:.2f}; "
          f"at-least test X £{h['at_least']['x_gbp']:.2f} passed={h['at_least']['passed']}")
