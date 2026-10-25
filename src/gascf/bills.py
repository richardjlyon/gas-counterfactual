"""The two full bills, 2002-2025: net-zero Britain (actual) and fossil Britain (simulated).

Spec v4 §3.1 (NZ lines), §3.2 (GO lines), §5.4 (NZ5), §8, §9.3, §11; binding decisions
§15.1 and §15.2. Plain words:

- **Net-zero Britain** is what Britain's electricity actually cost each calendar year:
  wholesale power (NZ1, of which carbon NZ1c), the Renewables Obligation (NZ2), feed-in
  tariffs (NZ3), Contracts for Difference (NZ4), the part of the Capacity Market that buys
  more firm capacity than fossil Britain would need (NZ5), running the grid (NZ6, BSUoS),
  the high-voltage grid (NZ7, TNUoS), the Climate Change Levy on electricity (NZ8), and the
  energy-saving schemes (NZ10), plus the
  same-in-both block (S1: local wires, metering, supplier costs and margin, VAT).
- **Fossil Britain** has the same demand, the same nuclear stations, interconnectors and
  pumped storage, and replaces everything else with a coal-and-gas fleet priced as if
  built new (GO1; coal forced up to the coal capacity Britain actually had, §15.2 dec. 1),
  plus the kept plant's output priced as in the actual world less carbon (GO1k, §15 7a),
  running the grid (GO4) and the high-voltage grid (GO5) carried forward from 2002-05, and
  the same S1 block. No carbon price, no subsidies, no levies.

Every line is national £m, nominal (money of the day), then £m in 2025 money (ONS CPIH,
`deflator_cpih`), then £ per GB household (ONS LFS, year-matched). Each carries `basis`
(measured / modelled / estimated; a line is the weakest of its inputs) and `source_ids`.

**One residual method for every year (departure, flagged).** Spec §4.1 says the fleet runs
on the Elexon FUELHH residual from 2016. This module runs the fossil fleet on the NESO
demand-side residual (`residual_neso`) in *every* year, central case, because:
(1) the §3.2 volume identity (fleet output + kept output = V within 0.5%) holds exactly
with it and fails with FUELHH in 2016 (-1.4%), 2018, 2019 (-0.6%) and 2025 (+0.9%), the
FUELHH residual not being built from the same V that prices NZ1; (2) it now passes the
§15.2 calibration against FUELHH in all ten years 2016-2025; (3) the chart has no method
seam at 2016. The FUELHH residual is a switch (`residual="fuelhh"`, 2016-2025) in the range,
with the kept volume taken as the remainder of V so that the switch, too, covers V.
"""
from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, field, replace
from functools import lru_cache

from gascf import balancing, capacity, carbon, cm_contracted, grid, prices, subsidies
from gascf import moe_crisis as MC
from gascf import deflator_cpih as dfl
from gascf import fossil_fleet as ff
from gascf import households as hh
from gascf import residual_neso as rn
from gascf import same_in_both, schemes
from gascf import on_the_road as _otr
from gascf import ccl_baseline as _cclb
from gascf import lec as _lec
from gascf.gastransport import GasTransport, read_transport

YEARS = range(2002, 2026)
HEADLINE_YEAR = 2025                 # §15.1 decision 5: 2025, labelled provisional
LATEST_FULL_YEAR = 2024
PROVISIONAL_YEARS = (2025,)
PRICE_BASE = 2025                    # money of the headline year (§2)
# 0144 item 1A: how the extra running of the plant real Britain had is priced ('market' central, 'cost' = v4-s36)
EXTRA_RUNNING_RULES = ("market", "cost")
KEPT_FILTER_VOM_RULES = ("added", "in_price")      # RB v1.1 M4
KEPT_COAL_PAY_RULES = ("full", "fixed_less_margin", "cm_from_2014")   # RB v1.1 M3 (0163 R4)
# v4-s40 item 2 (step-3 item 2 (a); decision 0175, Richard Lyon 23 Oct 2026, "Yes." at 06:13:51 UTC, verified on card
# [internal ticket]): kept coal's M3 margin on the revenue the road assigns its output (uplift, gas-price feedback, M8 timing,
# the generators' net-zero charge), "road", central when unset; "observed" = v4-s39 (annual means of the observed price
# less carbon), explicit only. Set before the process starts (fleet_lfl is cached).
M3_MARGIN_ENV = "GASCF_M3_MARGIN"
M3_MARGIN_READINGS = ("road", "observed")


def m3_margin_reading() -> str:
    v = (os.environ.get(M3_MARGIN_ENV) or M3_MARGIN_READINGS[0]).strip()
    if v not in M3_MARGIN_READINGS:
        raise ValueError(f"${M3_MARGIN_ENV}={v!r}: one of {M3_MARGIN_READINGS}")
    return v
KEPT_COAL_CM_FROM = 2014                           # R4 (b): "the CM price from 2014, (a) before"
_RANK = {"measured": 0, "modelled": 1, "estimated": 2, "UNSOURCED": 3}

NZ_IDS = ("NZ1", "NZ2", "NZ3", "NZ4", "NZ5", "NZ6", "NZ7", "NZ8", "NZ10", "NZ11")
GO_IDS = ("GO1", "GO1k", "GO2", "GO3", "GO4", "GO5", "GO6", "GO7")
LABELS = {
    "NZ1": "Power: wholesale energy", "NZ1c": "of which carbon in the wholesale price",
    "NZ2": "Renewables Obligation", "NZ3": "Feed-in tariffs (levelisation cost)",
    "NZ4": "Contracts for Difference (wind, solar, other)", "NZ4b": "Contracts for Difference: biomass",
    "NZ1c_tax": "of which carbon tax collected (Carbon Price Support, UK carbon auctions on power)",
    "NZ1c_price": "of which carbon cost in the power price, not collected as tax in GB",
    "NZ5": "Backup: Capacity Market extra over fossil Britain's own backup",
    "NZ6": "Running the grid (balancing)", "NZ7": "High-voltage grid",
    "NZ8": "Climate Change Levy, electricity",
    "NZ10": "Energy-saving schemes (EEC, CERT, CESP, ECO, GBIS), electricity share",
    "NZ11": "VAT, 5%, on households' share of the lines above",
    "GO1": "Power: the fossil fleet (coal and gas, built new)",
    "GO1k": "Kept nuclear, imports and pumped storage, priced as actual less carbon",
    "GO2": "Backup payments (inside GO1)", "GO3": "Carbon", "GO4": "Running the grid (balancing)",
    "GO5": "High-voltage grid", "GO6": "CCL, subsidies, taxes",
    "GO7": "VAT, 5%, on households' share of the lines above",
}
GEO = {"NZ1": "GB", "NZ1c": "GB", "NZ1c_tax": "UK", "NZ1c_price": "GB", "NZ2": "GB", "NZ3": "GB", "NZ4": "GB",
       "NZ4b": "GB", "NZ5": "GB", "NZ6": "GB",
       "NZ7": "GB", "NZ8": "GB", "NZ10": "GB", "NZ11": "GB", "GO1": "GB", "GO1k": "GB", "GO2": "GB", "GO3": "GB",
       "GO4": "GB", "GO5": "GB", "GO6": "GB", "GO7": "GB"}


# Spec §15.3 item 3: the net-zero bill shown to readers in groups (layout only; totals unchanged).
# 'subsidies' = wind and solar subsidies (RO, FiT, CfD); 'backup' = backup, storage and standby
# (Capacity Market extra, balancing extra); 'wires' = long power lines (the high-voltage grid
# extra); 'carbon' = carbon tax (carbon in the wholesale price, CCL). 'power' = wholesale power before carbon (the base both bills
# pay for, not a net-zero group); fossil-side lines are 'fossil'; same-in-both 'same_in_both'.
# 'schemes' = the energy-saving obligations on suppliers (EEC, CERT, CESP, ECO, GBIS; spec §15.4
# item 1: net zero, fossil Britain pays nothing for them; the Warm Home Discount is not here).
# s27b (spec §15.5 item 3): with `Settings.carbon_split` (central) the 'carbon' group becomes two:
# 'carbon_price_receipts' (CPS + UK auction receipts on power) and 'carbon_in_price' (the rest
# of NZ1c). Total unchanged. `groups_for(s)` gives the tuple in force; GROUPS is the central one.
GROUPS_SINGLE_CARBON = ("subsidies", "backup", "wires", "carbon", "ccl", "schemes", "vat")
GROUPS = ("subsidies", "backup", "wires", "carbon_price_receipts", "ccl", "carbon_in_price", "schemes", "vat")
GROUP_LABELS = {"subsidies": "Wind, solar and biomass subsidies", "backup": "Backup, storage and standby",
                "wires": "Long power lines (high-voltage grid)", "carbon": "Carbon in the power price",
                "carbon_price_receipts": "Carbon prices collected as tax (Carbon Price Support, carbon auctions on power)",
                "ccl": "Climate Change Levy",
                "carbon_in_price": "Carbon cost in the power price, not collected as tax",
                "schemes": "Energy-saving schemes on bills",
                "vat": "VAT on households' share of the extra",
                "power": "Power, before carbon"}
GROUP = {"NZ1": "power", "NZ1c": "carbon", "NZ1c_tax": "carbon_price_receipts", "NZ1c_price": "carbon_in_price",
         "NZ2": "subsidies", "NZ3": "subsidies", "NZ4": "subsidies", "NZ4b": "subsidies",
         "NZ5": "backup", "NZ6": "backup", "NZ7": "wires", "NZ8": "ccl",
         "NZ10": "schemes", "NZ11": "vat",
         "GO1": "fossil", "GO1k": "fossil", "GO2": "fossil", "GO3": "fossil", "GO4": "fossil",
         "GO5": "fossil", "GO6": "fossil", "GO7": "fossil"}


def weakest(*b: str) -> str:
    return max(b, key=_RANK.get)


# ----------------------------------------------------------------------------- settings

@dataclass(frozen=True)
class Settings:
    """Every switch of §11 / §15.2 item 5. The defaults are the central case.

    route: pre-mid-2010 wholesale price ('ofgem_chart' central, §15.2 dec. 3; 'lower', 'model').
    kept_price: GO1k price (§15 7a): 'less_carbon' (i, central), 'actual' (ii), 'fleet_avg' (iii).
    margin: spare-plant margin 'low' / 'central' / 'high' (6.6 / 7.4 / 8.2% of the 2027/28 peak, §4.2, 0133).
    residual: 'neso' (central, every year) or 'fuelhh' (2016-2025 only; NESO before).
    coal_rule: 'forced' (§15.2 dec. 1, binding) or 'allowed' (report only).
    ic_basis: 0057 (option B): 'contracted' (central) counts interconnectors at their CM contracted
      de-rated GW from CY2016 in both fleet sizing and the CM split; 'metered' = v4-s35.
    nuclear_cm_column: 0089, the nuclear part of the CM split: 'post_trade_less_suspended' (variant D,
      central: post-trade, less agreements the NESO register flags suspended, whole DY), 'auction_acquired',
      'post_trade_tw', 'post_trade_ex_dungeness' (cm_contracted.NUCLEAR_COLUMNS).
    cm_rule: NZ5 'extra' (§5.4 s32 rule, central), 'extra_kept_coal' (low side: kept coal needs
      CM too) or 'full' (7c(ii), high side).
    bal_share / bal_option: GO4 energy share and baseline. None/None = the central rule
      `GO4_CENTRAL` ('ibc' + FY2018/19 share; Richard, 14 Oct 2026, spec §15.1 item 8); the other
      options are the range (the stacked 'nao_2005|max' is the low end).
    renewal: GO5 renewal allowance R 'low' / 'central' / 'high' (§7.3).
    transport: add gas transport to the fleet (§4.3).
    fleet: 'like_for_like' (s22 central: the actual system with net zero taken out, see
      `fossil_like_for_like`) or 'all_new' (the s21b method: the whole fleet built new).
    moe: merit-order uplift in the like-for-like fleet. Spec §15.5 item 1 (binding, overrides
      §15.3 item 1): 'shao' central (Shao et al. 2022 on the market-priced MWh); 'model' (the
      engine's own four-block stack estimate) is a methods-page row from v4-s37 (0144 item 4A; it was
      a range switch in SWITCHES to v4-s36); 'none' (the §15.3 rule), 'larger', 'smaller' are methods-page
      switches (METHOD_SWITCHES).
    extra_running: 0144 item 1A, the extra running of the plant real Britain had: 'market' (central, charged
      what its actual output is charged) or 'cost' (the v4-s36 mix, at fuel, running and transport cost;
      methods-page sensitivity row C).
    moe_crisis: 0069/0086, the 2021-23 uplift: 'shao' (central, every year) or 'ucl_stmoe' (methods page,
      not the range: O'Shea, Horne and Maslin 2025 is a preprint), which scales the hourly Shao uplift
      so its 2021-23 time-mean is UCL Table 4 (wind) + the engine's Shao solar part (`moe_crisis`); 'ucl_ltmoe'
      (RB v1.1 M10, held for ruling R10, bills.HELD_SWITCHES) the same with UCL Table 5 (long-run).
    gas_feedback: gas-price feedback, `fossil_like_for_like.gas_feedback` (spec §15.5 item 2, §15.6 item 2):
      'central' (0.06 + 0.169) / 'krichene_lr' (0.16 + 0.45, the range row) / 'high' (0.06 supply only, case B
      only) / 'none' (the s23b rule).
    coal_lf: kept coal capped at the DUKES 5.10.B load factor, `fossil_like_for_like.coal_lf_cap`
      (spec §15.5 item 3): 'dukes_max' central; 'none' = s23b rule.
    tnuos_gen: 'removed' (central, s27b) takes generators' TNUoS share out of NZ7 and GO5 per
      charging year; 'included' = pre-s27.
    bsuos_gen: 'removed' (central) takes generators' BSUoS share (before 1 April 2023) out of NZ6
      and GO4; 'included' = pre-s27.
    go5_index: 'rpi' (central) carries G0 by RPI over the price-control years; 'cpih' = pre-s27;
      'rpi_x' = the controls' own X values on top (0091, methods-page sensitivity).
    fit_basis: NZ3 at the FiT levelisation fund cost ('levelisation', central) or the pre-s27
      scheme value ('scheme_value').
    cfd_split: biomass CfD shown as its own line NZ4b (True, central); False = inside NZ4.
    carbon_split: NZ1c shown as carbon tax collected + carbon in the price (True, central);
      False = one 'carbon' group (pre-s27). Neither split changes the gap.
    closures: 'legitimate' (central, §15.3 items 2 and 5: stations closed by net-zero policy stay
      open, with the filters the law required) or 'actual' (every closure on its real date).
    newbuild: 'cheapest' (central, §15.3 item 4: cheapest of CCGT, OCGT, coal with FGD and NOx
      control, nuclear where the edition allows) or 'gas_only' (the s22 rule).
    """
    route: str = "ofgem_chart"
    kept_price: str = "less_carbon"
    margin: str = "central"
    residual: str = "neso"
    coal_rule: str = "forced"
    cm_rule: str = "extra"
    ic_basis: str = "contracted"     # 0057 option B; 'metered' = v4-s35 (named switch)
    nuclear_cm_column: str | None = "post_trade_less_suspended"   # 0089 variant D; None = metered at peak (v4-s35)
    # 0059 (ticket 11): station load is generated by RB's fleet but billed in neither Britain. P1 and P2 ruled by
    # decision 0108 (Richard Lyon, 19 Oct 2026): item 1.5 option (b), the all-new fleet deducts station load at price
    # less carbon, the central rule ('less_carbon'; 'fleet_avg' kept as a setting, not a sensitivity row); item 1.6
    # option (a), under the kept_price sensitivities the deduction stays at price less carbon ('less_carbon';
    # 'follow_kept' kept as a setting only).
    sl_all_new_price: str = "less_carbon"
    sl_kept_price: str = "less_carbon"
    # 0097 (ticket 26): charges already on bills in 2001 are on the road at their 2001 level (0101 shared component,
    # gascf.on_the_road). Defaults = Richard's package (17 Oct 2026): real-flat by CPIH (cash-flat is the named
    # sensitivity on_the_road_cash_flat); Fossil Fuel Levy FY2001/02 £92m as charged (ONS CIQY, GB) netted from
    # NZ2 to 2019 (NFFO contracts ended).
    otr_indexation: str = "real_cpih"
    otr_nz2_level_gbp_m: float = 92.0
    otr_nz2_end_year: int | None = 2019
    # EESoP 3 £110m over Apr 2000-Mar 2002 (Ofgem/EST 2003 Fig 3.1, indicative) = £55m a year, electricity share by
    # target 4,981 / 11,125 GWh (44.8%, unrounded here); both INTERIM_APPROVED. Netted from all of NZ10 every year.
    otr_nz10_level_gbp_m: float = 55.0 * 4981 / 11125
    otr_nz10_end_year: int | None = None
    # 0044 (ticket 12): NZ8 counted above the levy at its 2001 rate (0.43p/kWh) x the inferred volume, carried by
    # CPIH ('cpih_2001', central); 'cash_2001' is the named sensitivity ccl_2001_cash_frozen; 'none' counts the whole
    # levy (No. 2's basis, 0023; a comparison setting, not a switch).
    ccl_baseline: str = "cpih_2001"
    # 0044 cap ruling: the pre-August-2015 LEC exemption is capped each year at RB's own replaced renewables volume;
    # False is the uncapped note run only (not a switch, not in the range).
    ccl_lec_cap: bool = True
    bal_share: float | None = None          # None = central rule GO4_CENTRAL (see go4_central_choice)
    bal_option: str | None = None
    renewal: str = "central"
    transport: bool = True
    fleet: str = "like_for_like"
    moe: str = "shao"                # spec §15.5 item 1; 'model' engine's own stack estimate; 'none' methods page
    # 0069/0086: 'ucl_stmoe' scales the 2021-23 uplift to UCL target B (methods page). v4-s39 central (card
    # [internal ticket]): 'm9_direct_mayon' = M9 B, direct coefficients May 2021-Dec 2023; Jan-Apr 2021, 2002-20 and
    # 2024-25p keep Shao (decision 0164 addendum, Richard Lyon 21 Oct 2026: "b"). 'shao' reproduces v4-s38.
    moe_crisis: str = "m9_direct_mayon"
    closures: str = "legitimate"
    newbuild: str = "cheapest"
    gas_feedback: str = "central"    # spec §15.5 item 2; 'none' = s23b rule; 'krichene_lr' the 0144 sensitivity pair
    # 0144 item 1A (Richard Lyon, 20 Oct 2026): extra running of the plant real Britain had at the market price
    # ('market', central); 'cost' = the v4-s36 mix (at fuel, running and transport cost), sensitivity row C
    extra_running: str = "market"
    # RB v1.1 M2 (card [internal ticket]; decision 0163 R1-R3 (a), Richard Lyon 21 Oct 2026, relayed): 'road_lf' settles the 9
    # 'mixed' closures by the margin test at the road's own coal load factor, repeated until the list stops changing
    # (`gascf.closure_test`); 'register' = the register's dates as written (v4-s38). Ruled central; set in the
    # v4-s39 central by card [internal ticket] (V11_COAL_CENTRAL now equals CENTRAL).
    closure_test: str = "road_lf"
    # RB v1.1 M4 (card [internal ticket]; decision 0163 R5 (a)): kept coal's filter running cost on its extra output. 'added' =
    # v4-s38 (added on top of the market price, so counted twice under extra_running='market'); 'in_price' = the fix
    # (not added when the extra running is paid the market price; still charged once at cost). Ruled central.
    kept_filter_vom: str = "in_price"   # v4-s39 central ([internal ticket])
    # RB v1.1 M3 (card [internal ticket]; decision 0163 R4): what kept coal is paid for its fixed cost. 'full' = v4-s38 (the
    # whole keep-open cost and annualised filters); 'fixed_less_margin' = R4 (a), central: that less its market margin,
    # floored at zero, all years; 'cm_from_2014' = R4 (b), the sensitivity row: the road's CM rate on kept coal's
    # de-rated MW from 2014, (a) before. (a) and (b) apply under extra running at the market price only.
    kept_coal_pay: str = "fixed_less_margin"   # v4-s39 central ([internal ticket])
    # RB v1.1 M5 (card [internal ticket]; decision 0163 R6 (a)): a life-extension cost on kept coal, a SENSITIVITY ROW only (no
    # published coal figure): 'borrowed_gas' = CEPA/GHD 2025 CCGT £81/kW per 5 years (`gascf.life_extension`); 'none' central.
    kept_life_ext: str = "none"
    # RB v1.1 O1 (card [internal ticket]; decision 0163 R17 (a)): closures by class, methods-page rows only. A class named here
    # closes on its real dates (register `closure_class`; the net_zero_policy rows' classes are R34 (a), ruled in 0164).
    closures_real_date_class: str = "none"
    # spec §15.5 item 3; 'none' = s23b rule; 'dukes_max' = v4-s38. v4-s39 central (card [internal ticket]; decision 0166,
    # Richard Lyon 22 Oct 2026, "Approved."): reading (i), every coal station, kept and existing, on its real permit
    # hours, 2011-14 LCPD opt-outs included (kept LCPD stations held too: $GASCF_IED_LCPD_KEPT, on by default);
    # H2 2020 pro rata from 1 July 2020. SCR-instead ('+ex_scr') not used; reading (ii) is a check row (V11_COAL_ROWS).
    coal_lf: str = "dukes_max+ied_permits_1500+existing"
    # s27b (spec §15.5 item 3); each switch's old value reproduces the pre-s27 line
    tnuos_gen: str = "removed"       # 'included' = pre-s27
    bsuos_gen: str = "removed"       # 'included' = pre-s27
    go5_index: str = "rpi"           # 'cpih' = pre-s27
    fit_basis: str = "levelisation"  # 'scheme_value' = pre-s27
    cfd_split: bool = True           # False = pre-s27 (biomass inside NZ4)
    carbon_split: bool = True        # False = pre-s27 (one 'carbon' group)
    # RB v1.1 O2 (decision 0160): the plant-cost case (fossil_fleet.COST_CASES). 'medium' central (v4-s37); the two high
    # cases are held rows for ruling R13 (HELD_SWITCHES), never in the range or the methods page.
    cost_case: str = "medium"
    # Decision 0167 (generators' share, "a"; card [internal ticket]): the net-zero part of the generators' share of BSUoS and
    # TNUoS counted as a cost of real Britain, WAY 2 (`gascf.gen_nz_charge`): both bills unchanged, the charge taken out
    # of fossil Britain's market price. 'none' = v4-s38; 'fossil_price' = way 2, the v4-s39 central (card [internal ticket]).
    gen_nz_charge: str = "fossil_price"
    # Decision 0169 (RO mutualisation, "a"; cards [internal ticket], [internal ticket]): count it as part of the RO. 'off' = v4-s38;
    # 'received' is the v4-s39 central (card [internal ticket]): NZ2 is ROCs presented x Ofgem's worth, which leaves the
    # mutualisation recycle out. 'received' adds the GB mutualisation payments received
    # (subsidies.read_ro_mutualisation) to NZ2 in full, on calendar years by NZ2's scheme-year rule.
    ro_mutualisation: str = "received"


CENTRAL = Settings()
# RB v1.1 kept-coal group (card [internal ticket], decision 0163): the settings Richard ruled central. Set in CENTRAL itself
# by the v4-s39 release card ([internal ticket]), so this now equals CENTRAL; kept as a name for the group's scripts.
V11_COAL_CENTRAL = replace(CENTRAL, closure_test="road_lf", kept_coal_pay="fixed_less_margin", kept_filter_vom="in_price")
# M5 (R6 (a)) is a sensitivity row only: replace(V11_COAL_CENTRAL, kept_life_ext="borrowed_gas")
# The group's rows, measured against V11_COAL_CENTRAL and never in the range. Not yet in SWITCHES or METHOD_SWITCHES:
# the v4-s39 release card places them (and gives each its figures key and R-A6 choice).
V11_COAL_ROWS: dict[str, tuple[Settings, ...]] = {
    "kept coal paid the Capacity Market rate from 2014, fixed cost less margin before (R4 (b))":
        (replace(V11_COAL_CENTRAL, kept_coal_pay="cm_from_2014"),),
    "kept coal life extension: assumption borrowed from gas plant (CEPA/GHD 2025, £81/kW per 5 years; R6 (a), R33)":
        (replace(V11_COAL_CENTRAL, kept_life_ext="borrowed_gas"),),
    "closures by class: biomass conversions on their real dates (R17 (a); classes R34 (a), 0164)":
        (replace(V11_COAL_CENTRAL, closures_real_date_class="biomass_conversion"),),
    "closures by class: coal phase-out deadline closures on their real dates (R17 (a); classes R34 (a), 0164)":
        (replace(V11_COAL_CENTRAL, closures_real_date_class="coal_phase_out_deadline"),),
    "closures by class: mixed-cause closures on their real dates (R17 (a))":
        (replace(V11_COAL_CENTRAL, closures_real_date_class="mixed"),),
    # decision 0166 item 4: a check row only, never a range end
    "coal hours (ii): the 1,500-hour route also for Drax 1-4 and Lynemouth (check row, 0166)":
        (replace(V11_COAL_CENTRAL, coal_lf="dukes_max+ied_route_1500+existing"),),
}
# v4-s40 item 9 (step-3 sheet item 9 (a); decision 0175, Richard Lyon 23 Oct 2026, "Yes." at 06:13:51 UTC, verified on
# card [internal ticket]): the ruled rows above are exported as method checks outside the range, in their own
# `one_at_a_time.method_checks` group, each with a printed key (tools/figures_keys/method_checks.py). No range key reads
# the group. The same object, so a row added above is a method check by construction.
METHOD_CHECKS = V11_COAL_ROWS


# ----------------------------------------------------------------------------- inputs

@lru_cache(maxsize=None)
def households_count() -> dict[int, int]:
    return {y: v["households"] for y, v in hh.households(YEARS).items()}


def real(v: float, y: int) -> float:
    """Nominal £ of year y in PRICE_BASE money, CPIH (ONS L522)."""
    return dfl.to_real(v, y, PRICE_BASE)


@lru_cache(maxsize=None)
def v_monthly() -> dict[tuple[int, int], float]:
    """V(m), TWh: NESO ND + embedded wind + embedded solar (§4.1, §5.1)."""
    return {(y, m): v for y in YEARS for m, v in rn.volume_monthly(y).items()}


@lru_cache(maxsize=None)
def kept_monthly_neso() -> dict[tuple[int, int], float]:
    """Kept output net of pumping and exports, TWh by month, NESO method (§4.1)."""
    out: dict[tuple[int, int], float] = {}
    for y in YEARS:
        for r in rn.residual_neso_year(y):
            k = (y, r.day.month)
            out[k] = out.get(k, 0.0) + r.kept / 2e6
    return out


@lru_cache(maxsize=None)
def station_load_monthly() -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = {}
    for y in YEARS:
        for r in rn.residual_neso_year(y):
            k = (y, r.day.month)
            out[k] = out.get(k, 0.0) + r.station_load / 2e6
    return out


@lru_cache(maxsize=None)
def eta_ccgt() -> dict[int, float]:
    """DUKES 5.10.C CCGT fleet efficiency, per cent GCV: the marginal plant's η for NZ1c (§3.1)."""
    return prices.dukes_efficiency()["ccgt"]


@lru_cache(maxsize=None)
def c_marg() -> dict[tuple[int, int], dict]:
    # RB v1.1 M7 (0163 R8 (a)): marginal-plant carbon from Jan 2009 behind a switch, OFF ('gas') by default
    from gascf import marginal_carbon as M7
    return M7.c_marg_monthly(eta_ccgt(), YEARS)


def nz1_by_year(route: str) -> dict[int, dict]:
    """NZ1, Σ months P(m) x V(m); under the M8 switch with scope 'both' (OFF by default), from the first free
    MID row each month's price is weighted by Reliable Britain's own half-hourly volume the same way."""
    from gascf import hh_pricing as H8
    out = prices.nz1(dict(v_monthly()), route)
    if not H8.active() or H8.scope() != "both":
        return out
    P, V, meth = p_elec(route), v_monthly(), H8.method()
    for y in YEARS:
        if y < H8.HH_FROM[0].year:
            continue
        ds = H8.demand_sums(y)
        out[y] = {**out[y], "gbp_m": sum(H8.effective(P[(y, m)]["gbp_per_mwh"], ds[m], y, m, meth) * V[(y, m)]
                                         for m in range(1, 13)),
                  "source_id": out[y]["source_id"] + "+elexon-mid-apx", "basis": "modelled"}
    return out


def nz1c_by_year() -> dict[int, dict]:
    """NZ1c, the carbon inside Reliable Britain's price, at the same monthly carbon the road's price is taken
    less of (`c_marg`, so the M7 switch moves both together)."""
    return carbon.nz1c(dict(v_monthly()), eta_ccgt(), c_marg())


@lru_cache(maxsize=None)
def p_elec(route: str) -> dict[tuple[int, int], dict]:
    return prices.elec_monthly(route, YEARS)


@lru_cache(maxsize=None)
def transport_for(year: int) -> GasTransport:
    """National Gas 2026/27 exit capacity and GNTS charges, restated to year y with CPIH from
    2025 money (CY2026 CPIH not published; treating Oct 2026 charges as 2025 money slightly
    raises the fossil bill, the conservative side). Tagged estimated (§4.3).
    Calendar 2021-25 (input audit v4-s41 A3; v4-s42, decision 0195): the rates National Gas
    published for each gas year, mapped to calendar years (`gastransport.published_calendar`)."""
    from gascf.gastransport import published_calendar
    pub = published_calendar(year)
    if pub is not None:
        return pub
    t = read_transport()["2026/27"]
    k = dfl.cpih()[year] / dfl.cpih()[2025]
    return GasTransport(t.gas_year, t.exit_capacity_p_kwh_day * k, t.commodity_p_kwh * k)


def _ic_fields(year: int, sp: dict, mfrac: float, fr: dict, ic_basis: str, called: dict) -> dict:
    """D6 run-file fields on `fleet[y]` and the parts `cm_split` reads (one basis)."""
    return {"ic_basis": ic_basis, "sizing_peak_gross_gw": sp["gross_peak_mw"] / 1e3,
            "sizing_peak_residual_mw": sp["residual_mw"],
            "sizing_peak_halfhour": f"{sp['day'].isoformat()} SP{sp['period']}", "margin_fraction": mfrac,
            "firm_requirement_gw": fr["firm_requirement_gw"] if sp["contracted"] else sp["gross_peak_mw"] / 1e3 * (1 + mfrac),
            "margin_on_gross_extra_gw": fr["margin_on_gross_extra_gw"] if sp["contracted"] else 0.0,
            "nuclear_at_peak_gw": sp["nuclear_gw"], "ps_at_peak_gw": sp["ps_gw"],
            "imports_metered_at_peak_gw": sp["imports_metered_gw"],
            "imports_contracted_gw": sp["imports_contracted_gw"], "imports_counted_gw": sp["imports_counted_gw"],
            **(ic_peak_dy(sp["day"]) if year >= IC_FIRST_CM_YEAR else {}), **called}


@lru_cache(maxsize=None)
def fleet(year: int, margin: str = "central", residual: str = "neso", coal_rule: str = "forced",
          transport: bool = True, ic_basis: str = "metered") -> dict:
    """GO1 for one year: the fossil fleet sized and dispatched on the residual (§4)."""
    if residual == "fuelhh" and year >= 2016:
        from gascf.residual import residual_year
        rows = residual_year(year, replace_other=True)[0]
    else:
        rows = rn.residual_neso_year(year)
    der = capacity.read_derating()
    tr = transport_for(year) if transport else None
    sp = sizing_peak(year, rows, ic_basis, residual)
    mfrac = capacity.margin_fraction(margin)
    fr = firm_requirement(sp["gross_peak_mw"] / 1e3, mfrac, sp["imports_contracted_gw"] if sp["contracted"] else 0.0)
    f = ff.cost_fossil_year(year, rows, mfrac, der, transport=tr, coal_rule=coal_rule,
                            firm_requirement_mw=fr["firm_requirement_gw"] * 1e3 if sp["contracted"] else None)
    ed = ff.edition(year)
    eta = {k: getattr(ed, k).efficiency_gcv for k in ("coal", "ccgt", "ocgt")}
    gas_burn = f.gen_twh["ccgt"] / eta["ccgt"] + f.gen_twh["ocgt"] / eta["ocgt"]
    t_fixed = t_comm = 0.0
    if tr is not None:
        t_fixed = (tr.fixed_gbp_kw_e_yr(eta["ccgt"]) * f.ccgt_gw * 1e6
                   + tr.fixed_gbp_kw_e_yr(eta["ocgt"]) * (f.ocgt_gw + f.spare_gw) * 1e6) / 1e6
        t_comm = tr.commodity_gbp_mwh_gas * gas_burn          # £/MWh × TWh = £m
    mwh_m = {m: 0.0 for m in range(1, 13)}
    for r in rows:
        mwh_m[r.day.month] += max(0.0, r.residual) / 2e6
    dr = {"coal": der["ccgt"], "ccgt": der["ccgt"], "ocgt": der["ocgt"]}
    derated_gw = f.coal_gw * dr["coal"] + f.ccgt_gw * dr["ccgt"] + (f.ocgt_gw + f.spare_gw) * dr["ocgt"]
    basis = weakest(f.basis, "estimated" if transport else "modelled", "modelled")
    return {
        "total_gbp_m": f.total_gbp_m, "fixed_gbp_m": f.fixed_gbp_m - t_fixed,
        "fuel_gbp_m": sum(f.fuel_gbp_m.values()) - t_comm, "vom_gbp_m": f.vom_gbp_m,
        "transport_gbp_m": t_fixed + t_comm, "energy_twh": f.energy_twh, "energy_monthly_twh": mwh_m,
        "coal_gw": f.coal_gw, "coal_cap_gw": f.coal_cap_gw, "ccgt_gw": f.ccgt_gw, "ocgt_gw": f.ocgt_gw,
        "spare_gw": f.spare_gw, "derated_gw": derated_gw, "gen_twh": dict(f.gen_twh),
        "gas_burn_twh": gas_burn, "gbp_per_mwh": f.total_gbp_m / f.energy_twh,
        "cost_edition": f.source_id, "basis": basis,
        "source_id": f"{f.source_id};desnz-dukes-5.7;desnz-qep-321;ofgem-wmi-nbp;neso-ecr-2026"
                     + (";nationalgas-2026-27-charges" if transport else ""),
        **_ic_fields(year, sp, mfrac, fr, ic_basis, {"ic_called_twh": 0.0, "ic_called_halfhours": 0,
                                                       "ic_called_gbp_m": 0.0}),
    }


def _applied_moe_mean(r, mult: float, flat: float, km: dict) -> float:
    """The year's applied merit-order uplift, time-mean £/MWh. Outside the M9 rules km is 1 every month and this is
    the v4-s38 expression to the digit; under M9 (0164) each month's model mean is scaled by its km, weighted by the
    month's calendar half-hours (exact when km is the same every month, as in 2022 and 2023)."""
    if all(v == 1.0 for v in km.values()):
        return r.moe_model_mean * mult + flat
    import calendar
    h = {m: calendar.monthrange(r.year, m)[1] for m in r.moe_model_m}
    base = sum(r.moe_model_m[m] * h[m] for m in h)
    kbar = sum(km[m] * r.moe_model_m[m] * h[m] for m in h) / base if base else 1.0
    return r.moe_model_mean * mult * kbar + flat


@lru_cache(maxsize=None)
def fleet_lfl(year: int, margin: str = "central", residual: str = "neso", transport: bool = True,
              route: str = "ofgem_chart", moe: str = "shao", closures: str = "legitimate",
              newbuild: str = "cheapest", gas_feedback: str = "central", coal_lf: str = "dukes_max",
              ic_basis: str = "metered", moe_crisis: str = "shao", extra_running: str = "market",
              closure_test: str = "register", kept_filter_vom: str = "added", kept_coal_pay: str = "full",
              kept_life_ext: str = "none", closures_real_date_class: str = "none",
              cost_case: str = "medium") -> dict:
    """GO1 for one year, like for like (s22): the actual fossil output at the actual price less
    carbon, new CCGT/OCGT where existing plant runs out (priced new), extra firm capacity, and the
    merit-order uplift on the market-priced volume. Same keys as `fleet` plus the like-for-like parts.

    extra_running (decision 0144 item 1A, Richard Lyon, 20 Oct 2026): 'market' (central) charges the extra
    running of the plant real Britain had what its actual output is charged, each month: actual price less
    carbon, plus the uplift on the extra volume, plus the gas-price feedback, in place of its fuel, running and
    gas-transport cost (and the feedback on its gas fuel), which are no longer counted. 'cost' = the v4-s36 mix
    (spec §15.3 item 1 / §15.5 item 1: extra running at fuel, running and transport cost), sensitivity row C."""
    from gascf import fossil_like_for_like as LFL
    if extra_running not in EXTRA_RUNNING_RULES:
        raise ValueError(f"unknown extra_running rule {extra_running!r}; one of {EXTRA_RUNNING_RULES}")
    cf = str(LFL.closures_path()) if closures == "legitimate" else None
    r = LFL.lfl_year(year, residual, margin, transport, closures, newbuild, cf, coal_lf, ic_basis,
                     closure_test=closure_test, real_date_class=closures_real_date_class, cost_case=cost_case)
    P, C = p_elec(route), c_marg()
    months = [(year, m) for m in range(1, 13)]
    at_market = extra_running == "market"
    vol_m = {m: r.market_twh_m[m] + (r.extra_twh_m.get(m, 0.0) if at_market else 0.0) for m in range(1, 13)}
    # RB v1.1 M8 (0163 R9 (a)), OFF by default: the price the road's fossil output (f) and extra running (x)
    # is charged, half-hourly from the first free MID row; the month's P before it and when switched off
    from gascf import hh_pricing as H8
    m8, meth8 = r.m8_sums, H8.method()
    Pf = {k: H8.effective(P[k]["gbp_per_mwh"], m8[k[1]]["f"] if m8 else None, *k, meth8) for k in months}
    Px = {k: H8.effective(P[k]["gbp_per_mwh"], m8[k[1]]["x"] if m8 else None, *k, meth8) for k in months}
    if m8 is None:      # switched off: the v4-s38 expression, to the last digit
        market = sum((P[k]["gbp_per_mwh"] - C[k]["gbp_per_mwh"]) * vol_m[k[1]] for k in months)
    else:
        market = sum((Pf[k] - C[k]["gbp_per_mwh"]) * r.market_twh_m[k[1]]
                     + ((Px[k] - C[k]["gbp_per_mwh"]) * r.extra_twh_m.get(k[1], 0.0) if at_market else 0.0)
                     for k in months)
    market_extra = (sum((Px[k] - C[k]["gbp_per_mwh"]) * r.extra_twh_m.get(k[1], 0.0) for k in months)
                    if at_market else 0.0)
    mult, flat = LFL.moe_factor(r, moe)
    if moe_crisis in MC.SCALED_RULES:     # 0069/0086: 2021-23 time-mean uplift = the rule's UCL target; k = 1 otherwise
        mult *= MC.k(year, max(0.0, r.moe_shao_mean), r.solar_gw_mean, rule=moe_crisis)   # M10: 'ucl_ltmoe' (held)
    # [internal ticket]: M9 re-estimate, monthly scale (1 outside the M9 rules)
    km = MC.k_months(moe_crisis, year, max(0.0, r.moe_shao_mean), r.wind_gw_mean, r.solar_gw_mean)
    if moe_crisis in MC.M9_RULES and year in MC.CRISIS_YEARS and flat != 0.0:
        raise ValueError(f"{moe_crisis}: flat uplift in {year}; the monthly M9 scale is not defined for it")

    def _v(vm: dict) -> float:
        return sum(km[m] * v for m, v in vm.items())
    moe_x = (mult * _v(r.moe_vol_x_m) / 1e6 + flat * r.extra_twh) if at_market else 0.0
    moe_f = mult * _v(r.moe_vol_f_m) / 1e6 + flat * r.actual_fossil_twh + moe_x
    moe_k = mult * _v(r.moe_vol_k_m) / 1e6 + flat * sum(kept_monthly_neso()[k] for k in months)
    gfb = LFL.gas_feedback(r, gas_feedback)
    frac = gfb.get("price_rise_frac", 0.0)
    eta = LFL._eta_dukes("ccgt", year)
    gfb_x = (sum(frac * r.gas_marginal_share * LFL.gas_price(year, k[1]) / eta * r.extra_twh_m.get(k[1], 0.0)
                 for k in months) if at_market else 0.0)
    gfb_f = gfb["market_gbp_m"] + gfb_x  # feedback on the market-priced MWh (actual output, and extra running in 1A)
    gfb_at_cost = gfb["at_cost_gbp_m"] - (frac * r.extra_gas_fuel_gbp_m if at_market else 0.0)
    nw = r.new or {"ccgt_gw": 0.0, "ocgt_gw": 0.0, "spare_gw": 0.0, "energy_twh": 0.0, "fixed_gbp_m": 0.0,
                   "fuel_gbp_m": 0.0, "vom_gbp_m": 0.0, "total_gbp_m": 0.0, "gas_burn_twh": 0.0,
                   "gen_twh": {"coal": 0.0, "ccgt": 0.0, "ocgt": 0.0}, "source_id": ""}
    nw.setdefault("coal_gw", 0.0)
    tr = transport_for(year) if transport else None
    ed = ff.edition(year)
    t_fixed = t_comm = 0.0
    if tr is not None and r.new:
        t_fixed = (tr.fixed_gbp_kw_e_yr(ed.ccgt.efficiency_gcv) * nw["ccgt_gw"] * 1e6
                   + tr.fixed_gbp_kw_e_yr(ed.ocgt.efficiency_gcv) * (nw["ocgt_gw"] + nw["spare_gw"]) * 1e6) / 1e6
        t_comm = tr.commodity_gbp_mwh_gas * nw["gas_burn_twh"]
    t_spare = (tr.fixed_gbp_kw_e_yr(ed.ocgt.efficiency_gcv) * r.firm_spare_gw * 1e6 / 1e6) if tr else 0.0
    x_fuel, x_vom, x_tr = ((0.0, 0.0, 0.0) if at_market
                           else (r.extra_fuel_gbp_m, r.extra_vom_gbp_m, r.extra_transport_gbp_m))
    fixed = (nw["fixed_gbp_m"] - t_fixed + r.firm_spare_fixed_gbp_m - t_spare + r.kept_fixed_gbp_m
             + r.existing_scr_fixed_gbp_m)          # card [internal ticket] "+ex_scr" (0 unless that switch is on)
    # RB v1.1 M3 (decision 0163 R4): kept coal's fixed charge by the kept_coal_pay rule (the whole cost in v4-s38)
    # v4-s40 item 2 (0175): the margin on the revenue the road assigns the coal block's own output (unless "observed")
    road = (coal_block_road_revenue(r, P, C, Pf_of=lambda k: H8.effective(
                P[k]["gbp_per_mwh"], (r.coal_m8 or {}).get(k[1]) if m8 else None, *k, meth8),
                mult=mult, flat=flat, km=km, frac=frac)
            if m3_margin_reading() == "road" and r.coal_twh_m is not None else None)
    kcp = kept_coal_pay_year(year, r, route, kept_coal_pay, at_market, kept_life_ext, road=road)
    fixed += kcp["paid_gbp_m"] - kcp["coal_fixed_v4s38_gbp_m"]     # r.kept_fixed_gbp_m holds the v4-s38 charge
    fuel = nw["fuel_gbp_m"] - t_comm + x_fuel + gfb_at_cost
    # RB v1.1 M4 (decision 0163 R5 (a)): under the market rule kept coal's extra output is paid the market price, which
    # carries its running costs; 'in_price' stops the filters' running cost being added on top a second time
    if kept_filter_vom not in KEPT_FILTER_VOM_RULES:
        raise ValueError(f"unknown kept_filter_vom rule {kept_filter_vom!r}; one of {KEPT_FILTER_VOM_RULES}")
    k_ab_vom = 0.0 if (at_market and kept_filter_vom == "in_price") else r.kept_abatement_vom_gbp_m
    # card [internal ticket] "+ex_scr": existing coal's SCR running cost, added as that card built it (0 unless on)
    vom = nw["vom_gbp_m"] + x_vom + k_ab_vom + r.existing_scr_vom_gbp_m
    transport_m = t_fixed + t_comm + t_spare + x_tr
    total = market + moe_f + gfb_f + fixed + fuel + vom + transport_m
    der = capacity.read_derating()
    new_der = (nw["ccgt_gw"] + nw["coal_gw"]) * der["ccgt"] + (nw["ocgt_gw"] + nw["spare_gw"]) * der["ocgt"]
    ex = r.existing
    energy = r.energy_twh
    emon = dict(r.energy_twh_m)
    basis = weakest(r.basis, "estimated" if transport else "modelled", "modelled",
                    *(P[k]["basis"] for k in months), *(C[k]["basis"] for k in months))
    return {
        "total_gbp_m": total, "market_gbp_m": market, "moe_gbp_m": moe_f, "moe_kept_gbp_m": moe_k,
        "market_twh": sum(r.market_twh_m.values()),     # 0167 way 2: the actual fossil output paid the market price
        "gas_feedback_gbp_m": gfb_f, "gas_feedback_kept_gbp_m": gfb["kept_gbp_m"],
        "gas_feedback_at_cost_gbp_m": gfb_at_cost,
        # 0144 item 1A: the extra running's share of the market, uplift and feedback parts above, and the running
        # cost that is no longer counted (zero and the at-cost figures under extra_running='cost')
        "extra_running": extra_running, "extra_twh": r.extra_twh,
        "extra_market_gbp_m": market_extra, "extra_moe_gbp_m": moe_x, "extra_gas_feedback_gbp_m": gfb_x,
        "extra_cost_not_counted_gbp_m": ((r.extra_fuel_gbp_m + r.extra_vom_gbp_m + r.extra_transport_gbp_m
                                          + frac * r.extra_gas_fuel_gbp_m) if at_market else 0.0),
        "gas_feedback": {k: v for k, v in gfb.items()},
        "gas_marginal_share": r.gas_marginal_share,
        "worked_hh": r.worked_hh,
        **({"hh_pricing": {"method": meth8, "scope": H8.scope(),
                           "gap_halfhours": sum(m8[m]["f"].gaps for m in range(1, 13)),
                           "price_f_gbp_mwh": {k[1]: Pf[k] for k in months},
                           "price_x_gbp_mwh": {k[1]: Px[k] for k in months}}} if m8 else {}),
        "coal_lf": {"rule": r.coal_lf, "cap": r.coal_lf_cap, "avail_scale": r.coal_avail_scale,
                    "achieved": r.coal_lf_achieved},
        "fixed_gbp_m": fixed, "fuel_gbp_m": fuel, "vom_gbp_m": vom, "transport_gbp_m": transport_m,
        "energy_twh": energy, "energy_monthly_twh": emon,
        "coal_gw": ex.coal / 1e3, "coal_cap_gw": ff.coal_capacity_gb(year)[0] / 1e3,
        "ccgt_gw": nw["ccgt_gw"], "ocgt_gw": nw["ocgt_gw"], "spare_gw": nw["spare_gw"] + r.firm_spare_gw,
        "new_coal_gw": nw["coal_gw"],
        "kept_gw": {k: v / 1e3 for k, v in (r.kept or {}).get("mw", {}).items()},
        "kept_abated_gw": {k: v / 1e3 for k, v in (r.kept or {}).get("abated_mw", {}).items()},
        "kept_stations": list((r.kept or {}).get("stations", [])),
        "kept_fixed_gbp_m": r.kept_fixed_gbp_m, "kept_abatement_vom_gbp_m": k_ab_vom, "kept_filter_vom": kept_filter_vom,
        "kept_abatement_vom_in_price_gbp_m": r.kept_abatement_vom_gbp_m - k_ab_vom,
        "kept_coal_pay": kcp,
        "existing_scr_fixed_gbp_m": r.existing_scr_fixed_gbp_m, "existing_scr_vom_gbp_m": r.existing_scr_vom_gbp_m,
        "kept_detail": {k: v for k, v in (r.kept or {}).items() if k in ("keep_open_gbp_m", "abatement_fixed_gbp_m",
                                                                          "abatement_source_ids", "basis", "source_id")},
        "closures": r.closures, "newbuild": r.newbuild, "nuclear_note": r.nuclear_note,
        # RB v1.1 M2: the closure list the road-load-factor test settled on, and its rounds (absent under 'register')
        **({"closure_test": {"rule": r.closure_test["rule"], "converged": r.closure_test["converged"],
                             "overrides": [list(o) for o in r.closure_test["overrides"]],
                             "rounds": r.closure_test["rounds"]}} if r.closure_test else {}),
        "extra_gen_by_block_twh": dict(r.extra_gen_by_block_twh or {}),
        "existing_gw": {"coal": ex.coal / 1e3, "ccgt": ex.ccgt / 1e3, "other_gas": ex.other_gas / 1e3,
                        "oil": ex.oil / 1e3},
        "existing_derated_gw": r.existing_derated_mw / 1e3,
        # firm capacity for NZ5: listed plant + the unlisted firm plant the actual system met
        # its own peak with (fossil Britain keeps it) + new plant + extra firm, all de-rated
        "derated_gw": r.existing_derated_mw / 1e3 + r.unlisted_firm_gw + new_der + r.firm_spare_gw * der["ocgt"],
        "unlisted_firm_gw": r.unlisted_firm_gw,
        # s32: the parts of derated_gw whose fixed cost GO1 already carries (spec §5.4): new plant,
        # the firm spare, and kept-open plant (de-rated by the engine's own rule,
        # `fossil_like_for_like.Existing.derated`: coal and CCGT at the ECR CCGT factor)
        "new_derated_gw": new_der, "firm_spare_derated_gw": r.firm_spare_gw * der["ocgt"],
        "kept_derated_gw": sum(LFL.Existing(coal=(r.kept or {}).get("mw", {}).get("coal", 0.0),
                                            ccgt=(r.kept or {}).get("mw", {}).get("ccgt", 0.0),
                                            other_gas=(r.kept or {}).get("mw", {}).get("other_gas", 0.0),
                                            oil=(r.kept or {}).get("mw", {}).get("oil", 0.0),
                                            basis="").derated(der).values()) / 1e3,
        "new_gw": nw["ccgt_gw"] + nw["ocgt_gw"] + nw["spare_gw"] + nw["coal_gw"], "firm_extra_gw": r.firm_spare_gw,
        "gen_twh": {"actual_fossil": r.actual_fossil_twh, "extra_existing": r.extra_twh,
                    "new_ccgt": nw["gen_twh"]["ccgt"], "new_ocgt": nw["gen_twh"]["ocgt"],
                    "new_coal": nw["gen_twh"].get("coal", 0.0)},
        "renewables_replaced_twh": r.renew_twh, "new_total_gbp_m": nw["total_gbp_m"],
        # what the extra running is charged: at the market (0144 item 1A) or at its cost (extra_running='cost')
        "extra_running_gbp_m": ((market_extra + moe_x + gfb_x) if at_market
                                else r.extra_fuel_gbp_m + r.extra_vom_gbp_m + r.extra_transport_gbp_m),
        "gas_burn_twh": r.gas_burn_existing_twh + nw["gas_burn_twh"],
        "gbp_per_mwh": total / energy if energy else 0.0,
        "moe": {"rule": moe, "model_mean_gbp_mwh": r.moe_model_mean, "shao_mean_gbp_mwh": r.moe_shao_mean,
                "shao_note": r.shao_note, "applied_mean_gbp_mwh": _applied_moe_mean(r, mult, flat, km),
                "crisis_rule": moe_crisis if year in MC.CRISIS_YEARS else "shao",
                "applied_on_fossil_output_gbp_mwh": moe_f / r.actual_fossil_twh if r.actual_fossil_twh else 0.0,
                "wind_gw_mean": r.wind_gw_mean, "solar_gw_mean": r.solar_gw_mean},
        "cost_edition": nw["source_id"] or ";".join(sorted(set(ed.source_id.values()))),
        "basis": basis, "method": "like_for_like",
        "source_id": (f"{nz1_source(route, year)};{LFL.SRC_MIX};{LFL.SRC_57};{LFL.SRC_511};{LFL.SRC_SHAO};"
                      f"desnz-dukes-5.6;desnz-dukes-5.10;desnz-qep-321;ofgem-wmi-nbp;neso-ecr-2026;"
                      f"{LFL.SRC_NEUHOFF};{LFL.SRC_ET41};"
                      + ";".join(sorted(set(ed.source_id.values())))
                      + (";nationalgas-2026-27-charges" if transport else "")
                      + (f";{r.kept.get('source_id')}" if r.kept and r.kept.get("stations") else "")
                      + "".join(f";{x}" for x in (r.kept or {}).get("abatement_source_ids", []))),
        **_ic_fields(year, r.sizing, capacity.margin_fraction(margin), r.firm_req, ic_basis,
                     {"ic_called_twh": r.ic_called_twh, "ic_called_halfhours": r.ic_called_halfhours,
                      "ic_called_gbp_m": sum((P[k]["gbp_per_mwh"] - C[k]["gbp_per_mwh"]) * r.ic_called_twh_m[k[1]]
                                             for k in months)}),
    }


@lru_cache(maxsize=None)
def _nz1_all(route: str) -> dict:
    return prices.nz1(dict(v_monthly()), route)


def nz1_source(route: str, year: int) -> str:
    return f"{_nz1_all(route)[year]['source_id']};{c_marg()[(year, 1)]['source_id']}"


IC_BASES = ("contracted", "metered")
IC_FIRST_CM_YEAR = 2016          # 0062: contracted from CY2016 (0 MW); 2002-15 metered under either basis


def ic_contracted_applies(year: int, ic_basis: str) -> bool:
    if ic_basis not in IC_BASES:
        raise ValueError(f"ic_basis {ic_basis!r}: one of {IC_BASES}")
    return ic_basis == "contracted" and year >= IC_FIRST_CM_YEAR


@lru_cache(maxsize=None)
def kept_at_peak_parts(year: int, residual: str = "neso") -> dict[str, float]:
    """{'nuclear', 'ps', 'imports'}: GW, as metered, in the half-hour of the NESO residual peak."""
    r = max(rn.residual_neso_year(year), key=lambda h: h.residual)
    return {"nuclear": r.nuclear / 1e3, "ps": r.ps_gen / 1e3, "imports": r.imports / 1e3}


def imports_contracted_gw(year: int) -> float:
    """Interconnectors' CM contracted de-rated GW on calendar years (0057, 0066); 0 before 2016."""
    return cm_contracted.ic_contracted_cy_mw().get(year, 0.0) / 1e3


def imports_counted_gw(year: int, ic_basis: str = "contracted", residual: str = "neso") -> float:
    """The imports GW both fleet sizing and the CM split count (D3: one function, one basis)."""
    if ic_contracted_applies(year, ic_basis):
        return imports_contracted_gw(year)
    return kept_at_peak_parts(year, residual)["imports"]


def firm_requirement(gross_peak_gw: float, margin: float, contracted_gw: float) -> dict[str, float]:
    """0065: NESO's de-rated-margin definition. The margin is on the gross peak (demand) and
    contracted interconnectors count as supply: gross × (1 + m) − contracted."""
    return {"firm_requirement_gw": gross_peak_gw * (1 + margin) - contracted_gw,
            "margin_on_gross_extra_gw": margin * contracted_gw}


def ic_peak_dy(day) -> dict:
    """0066, printed only: the delivery year in force on the sizing-peak day and its contracted MW
    (Jan-Sep of y: DY (y-1)/y; Oct-Dec: DY y/(y+1)). Never used in sizing or the CM line."""
    start = day.year - 1 if day.month < 10 else day.year
    return {"ic_peak_dy": f"{start}/{str(start + 1)[2:]}",
            "ic_peak_dy_contracted_mw": cm_contracted.ic_contracted_dy_mw().get(start, 0.0)}


def ic_called(residual_mw, available_mw: float, p_less_c_gbp_mwh: float) -> dict:
    """0063: half-hours where the metered residual exceeds what the fleet can generate are met by
    contracted imports called, moved from fleet energy to kept and priced as kept output (P − C)."""
    called = [max(0.0, r - available_mw) for r in residual_mw]
    twh = sum(called) / 2e6
    return {"ic_called_twh": twh, "ic_called_halfhours": sum(1 for c in called if c > 0),
            "ic_called_gbp_m": twh * p_less_c_gbp_mwh}


def sizing_peak(year: int, rows, ic_basis: str, residual: str = "neso") -> dict:
    """D3/D4: the half-hour the fleet is sized on, and the parts at it, from one place.
    'metered' (and every year before 2016): the residual peak, as v4-s35. 'contracted' from 2016:
    the peak of the gross series residual(t) + metered imports(t) (imports matched from the NESO
    rows by day and period, so the FUELHH sensitivity uses the same imports)."""
    neso = rn.residual_neso_year(year)
    if not ic_contracted_applies(year, ic_basis):
        i = max(range(len(rows)), key=lambda k: rows[k].residual)
        r0 = rows[i]
        p = kept_at_peak_parts(year, residual)
        return {"gross_peak_mw": r0.residual, "residual_mw": r0.residual, "day": r0.day, "period": r0.period,
                "nuclear_gw": p["nuclear"], "ps_gw": p["ps"], "imports_metered_gw": p["imports"],
                "imports_contracted_gw": imports_contracted_gw(year), "imports_counted_gw": p["imports"],
                "contracted": False}
    imp = {(h.day, h.period): h for h in neso}
    g = [r.residual + (imp[(r.day, r.period)].imports if (r.day, r.period) in imp else 0.0) for r in rows]
    i = max(range(len(rows)), key=lambda k: g[k])
    h = imp.get((rows[i].day, rows[i].period))
    return {"gross_peak_mw": g[i], "residual_mw": rows[i].residual, "day": rows[i].day, "period": rows[i].period,
            "nuclear_gw": (h.nuclear if h else 0.0) / 1e3, "ps_gw": (h.ps_gen if h else 0.0) / 1e3,
            "imports_metered_gw": (h.imports if h else 0.0) / 1e3,
            "imports_contracted_gw": imports_contracted_gw(year),
            "imports_counted_gw": imports_contracted_gw(year), "contracted": True}


@lru_cache(maxsize=None)
def kept_at_peak_gw(year: int, residual: str = "neso") -> float:
    """Nuclear + pumped-storage output + imports, GW, in the half-hour of the NESO residual peak
    (gross of exports: exports are demand fossil Britain serves, not firm supply lost)."""
    p = kept_at_peak_parts(year, residual)
    return p["nuclear"] + p["ps"] + p["imports"]


@lru_cache(maxsize=None)
def cm_obligation_mw_year() -> dict[int, float]:
    """Mean monthly Capacity Market obligation in force, MW, by calendar year (LCCC)."""
    import csv
    months = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                          "August", "September", "October", "November", "December"], 1)}
    q: dict[tuple[int, int], float] = {}
    with subsidies.CM_CSV.open(newline="") as f:
        for r in csv.DictReader(f):
            k = (int(r["Calendar_Year"]), months[r["Calendar_Month"]])
            q[k] = q.get(k, 0.0) + float(r["Auction_Acquired_Capacity_Obligation_MW"] or 0)
    return {y: sum(v for k, v in q.items() if k[0] == y) / 12 for y in {k[0] for k in q}}


# s32 (Finding 7): in 2016 and 2017 the obligation in force was tiny (0.2 and 14.2 GW mean) because
# only the transitional (TR) auctions, a demand-side-response pilot, delivered until the T-1
# Early Auction started on 1 Oct 2017. Paid / obligation is then not a price at which ~50 GW could
# be bought. Rule: Reliable Britain's notional CM is priced only for the months a main (T-4 or T-1)
# auction delivered, at that auction's clearing price (Ofgem CM annual report 2025/26, Table 4:
# "2017/18 03-Feb-17 £6.95/kW/year"); TR months carry no notional CM (the TR pilot stays in NZ5).
CM_EARLY_YEARS = (2016, 2017)
CM_EARLY_AUCTION = {"T-1-2017": 6.95}        # £/kW/yr clearing price, Ofgem CM AR 2025/26 Table 4
CM_EARLY_QUOTE = "2017/18 03-Feb-17 £6.95/kW/year"
SRC_CM_EARLY = "ofgem-cm-annual-report-2025-26-table4"


@lru_cache(maxsize=None)
def cm_early_price() -> dict[int, dict]:
    """{year: {'gbp_kw_yr': annualised £/kW, 'months': [...], 'auctions': [...]}} for 2016-2017:
    clearing price × (months a main auction delivered)/12. Reads the LCCC file for the months and
    checks the price against the stored Ofgem report."""
    import csv
    from gascf import capacity_cm
    if CM_EARLY_QUOTE not in capacity_cm._text(capacity_cm.OFGEM_CM):
        raise ValueError("Ofgem CM AR 2025/26 Table 4: Early Auction clearing price moved")
    months = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                          "August", "September", "October", "November", "December"], 1)}
    seen: dict[int, dict[str, set]] = {y: {} for y in CM_EARLY_YEARS}
    with subsidies.CM_CSV.open(newline="") as f:
        for r in csv.DictReader(f):
            y = int(r["Calendar_Year"])
            if y in seen and float(r["Auction_Acquired_Capacity_Obligation_MW"] or 0) > 0:
                seen[y].setdefault(r["Auction_Identifier"], set()).add(months[r["Calendar_Month"]])
    out = {}
    for y, auc in seen.items():
        main = {a: ms for a, ms in auc.items() if not a.startswith("TR-")}
        unknown = set(main) - set(CM_EARLY_AUCTION)
        if unknown:
            raise ValueError(f"{y}: main auction(s) {unknown} delivering with no stored clearing price")
        p = sum(CM_EARLY_AUCTION[a] * len(ms) / 12 for a, ms in main.items())
        out[y] = {"gbp_kw_yr": p, "months": sorted(set().union(*main.values())) if main else [],
                  "auctions": sorted(main), "tr_auctions": sorted(a for a in auc if a.startswith("TR-"))}
    return out


@lru_cache(maxsize=None)
def rb_cm_price_kw(y: int) -> tuple[float, str]:
    """The road's notional CM rate, £/kW-yr, for calendar year y: the rule NZ5 prices the road's other existing plant
    at (`build`, s32 Finding 7): the main auction's clearing price x months delivered / 12 in 2016-17, else CM paid /
    mean obligation (LCCC); 0 where no CM delivered (before Oct 2016)."""
    q = cm_obligation_mw_year().get(y)
    if y in CM_EARLY_YEARS and q:
        return cm_early_price()[y]["gbp_kw_yr"], "main auction clearing price x months delivered/12"
    if q:
        return subsidies.CM_paid(YEARS)[y]["gbp_m"] / q * 1000, "CM paid / mean obligation (LCCC)"
    return 0.0, "no Capacity Market delivered this year"


def coal_block_road_revenue(r, P: dict, C: dict, Pf_of, mult: float, flat: float, km: dict, frac: float) -> dict:
    """v4-s40 item 2 (0175): what the road pays the coal block's own output, by month, £m year-y money, in the terms it
    charges every market-priced MWh (`fleet_lfl`): price less carbon (`Pf_of((year, m))`, the month's price, MID-shaped
    on the coal block's own half-hours under M8), the merit-order uplift on the coal block's own half-hours
    (`mult` x km(m) x Σ Δ x coal MW / 2, plus `flat` per MWh), and the gas-price feedback per MWh (`frac` x the share
    of half-hours gas is marginal x the month's gas price / CCGT efficiency, as `fossil_like_for_like.gas_feedback`).
    Used under the market rule only: under extra_running='cost' (row C) kept coal keeps its whole fixed cost, as in
    v4-s39 (`kept_coal_pay_year`), unchanged by item 2."""
    from gascf import fossil_like_for_like as LFL
    y = r.year
    eta = LFL._eta_dukes("ccgt", y)
    twh = r.coal_twh_m
    return {"block_twh_m": dict(twh),
            "price_less_carbon_gbp_m": {m: (Pf_of((y, m)) - C[(y, m)]["gbp_per_mwh"]) * twh[m] for m in range(1, 13)},
            "uplift_gbp_m": {m: mult * km[m] * r.coal_moe_vol_m[m] / 1e6 + flat * twh[m] for m in range(1, 13)},
            "feedback_gbp_m": {m: frac * r.gas_marginal_share * LFL.gas_price(y, m) / eta * twh[m]
                               for m in range(1, 13)}}


def kept_coal_pay_after_charge(k: dict, gen_nz_per_mwh: float, year: int) -> dict:
    """v4-s40 item 2 (0175): the generators' net-zero charge (0167 way 2, £/MWh off every MWh the road buys at the
    market price) also comes off kept coal's road margin. Applies where the pay is fixed cost less the road margin
    (rule (a), and R4 (b) before 2014); otherwise the pay is returned unchanged."""
    margin_rule = k.get("rule") == "fixed_less_margin" or (k.get("rule") == "cm_from_2014" and year < KEPT_COAL_CM_FROM)
    if k.get("margin_basis") != "road" or not margin_rule or "margin_gbp_m" not in k:
        return k
    charge = gen_nz_per_mwh * k["margin_twh"]
    margin = k["margin_gbp_m"] - charge
    return {**k, "charge_gbp_m": charge, "charge_gbp_mwh": gen_nz_per_mwh, "margin_gbp_m": margin,
            "margin_before_charge_gbp_m": k["margin_gbp_m"], "paid_gbp_m": max(0.0, k["coal_fixed_gbp_m"] - margin)}


def kept_coal_pay_year(year: int, r, route: str, rule: str, at_market: bool, life_ext: str = "none",
                       road: dict | None = None) -> dict:
    """RB v1.1 M3 (card [internal ticket]; decision 0163 R4): kept coal's fixed charge in GO1, £m year-y money.

    coal_fixed = the keep-open cost of kept coal (edition's fixed O&M, insurance, connection) plus its annualised
    filters (`fossil_like_for_like.kept_costs`), all v4-s38 charges. 'full' pays it all (v4-s38). 'fixed_less_margin'
    (R4 (a)) pays max(0, coal_fixed - margin), margin = `closure_test.kept_coal_margin` at the road's coal load factor.
    'cm_from_2014' (R4 (b)) pays the road's CM rate (`rb_cm_price_kw`) x kept coal's de-rated MW (the engine's coal
    de-rating, the ECR CCGT factor) from 2014, and (a) before. Under extra running at cost (row C) kept coal keeps its
    whole fixed cost: its output is then charged at cost, not paid the market price.

    life_ext (RB v1.1 M5, decision 0163 R6 (a), sensitivity row only): 'borrowed_gas' adds `life_extension.gbp_kw_yr`
    on each kept coal MW-year to coal_fixed (so under R4 (a) it is netted against the margin with the rest; a working
    reading stated in the card's results). The v4-s38 charge (kept_fixed_gbp_m) excludes it, so 'full' pays it on top."""
    from gascf import closure_test as CT
    from gascf import life_extension as LE
    if rule not in KEPT_COAL_PAY_RULES:
        raise ValueError(f"unknown kept_coal_pay rule {rule!r}; one of {KEPT_COAL_PAY_RULES}")
    kept = r.kept or {}
    coal_mw = kept.get("mw", {}).get("coal", 0.0)
    other_keep = sum(v for k, v in kept.get("keep_open_gbp_m", {}).items() if k != "coal")
    coal_fixed = kept.get("keep_open_gbp_m", {}).get("coal", 0.0) + kept.get("abatement_fixed_gbp_m", 0.0)
    if abs(r.kept_fixed_gbp_m - other_keep - coal_fixed) > 1e-6:
        raise ValueError(f"{year}: kept fixed cost does not split into coal and other plant")
    life = LE.gbp_kw_yr(life_ext, year) * coal_mw / 1e3
    coal_fixed_v438 = coal_fixed
    coal_fixed += life
    out = {"rule": rule, "coal_mw": coal_mw, "coal_fixed_gbp_m": coal_fixed, "paid_gbp_m": coal_fixed,
           "life_ext": life_ext, "life_ext_gbp_m": life, "coal_fixed_v4s38_gbp_m": coal_fixed_v438}
    if coal_mw <= 0 or rule == "full" or not at_market:
        return out
    ed = ff.edition(year)
    fv = sum(ff.abatement_gbp_kw_yr(ed, k)[1] * mw for k, mw in kept.get("abated_mw", {}).items() if mw > 0) / coal_mw
    m = CT.kept_coal_margin(year, coal_mw, r.coal_lf_achieved, fv, route)
    out.update({"margin_gbp_m": m["margin_gbp_m"], "margin_twh": m["twh"], "spread_gbp_mwh": m["spread_gbp_mwh"],
                "filter_vom_gbp_mwh": fv, "lf": m["lf"], "paid_gbp_m": max(0.0, coal_fixed - m["margin_gbp_m"])})
    if road is not None:
        # v4-s40 item 2 (0175): the road's own revenue on kept coal's share of the coal block, by month
        share = coal_mw / r.existing.coal
        g = CT.kept_coal_margin_road(year, share, road["block_twh_m"], road["price_less_carbon_gbp_m"],
                                     road["uplift_gbp_m"], road["feedback_gbp_m"], fv)
        out.update({"margin_basis": "road", "margin_observed_gbp_m": m["margin_gbp_m"],
                    **{k: g[k] for k in ("share", "block_twh_m", "price_less_carbon_gbp_m", "uplift_gbp_m",
                                         "feedback_gbp_m", "fuel_gbp_m", "vom_gbp_m")},
                    "margin_gbp_m": g["margin_gbp_m"], "margin_twh": g["twh"], "spread_gbp_mwh": g["spread_gbp_mwh"],
                    "paid_gbp_m": max(0.0, coal_fixed - g["margin_gbp_m"])})
    if rule == "cm_from_2014" and year >= KEPT_COAL_CM_FROM:
        price, basis = rb_cm_price_kw(year)
        der = capacity.read_derating()["ccgt"]
        out.update({"cm_price_gbp_kw_yr": price, "cm_price_basis": basis, "derating": der,
                    "paid_gbp_m": price * coal_mw / 1e3 * der})
    return out


def cm_worked_example(f: dict) -> dict:
    """B16: the CM worked-example fields, from the half-hour the fleet is sized on (R-A1 option A:
    §7 names the sizing peak; §4.3's residual peak is ticket 44's export). `margin` is the fraction."""
    day, sp = f["sizing_peak_halfhour"].split(" SP")
    return {"peak_settlement_date": day, "peak_settlement_period": int(sp),
            "residual_peak_mw": f["sizing_peak_residual_mw"], "margin": f["margin_fraction"]}


def cm_split(f: dict, year: int, residual: str = "neso", nuclear_column: str | None = None) -> dict:
    """Spec §5.4 (s32): Reliable Britain's firm capacity (de-rated GW) split into the part whose
    fixed cost GO1 does NOT carry (it would hold CM agreements: existing unkept listed plant,
    the unlisted firm plant, and nuclear / pumped storage / imports at its residual peak) and
    the part GO1 already pays in full (new plant, the firm spare, kept-open plant)."""
    kept = f.get("kept_derated_gw", 0.0)
    existing = f.get("existing_derated_gw", 0.0) - kept          # existing_derated includes kept
    unlisted = f.get("unlisted_firm_gw", 0.0)
    if "new_derated_gw" in f:
        new, spare = f["new_derated_gw"], f["firm_spare_derated_gw"]
    else:                        # all_new fleet: every listed MW is built, and paid, by GO1
        new, spare = f["derated_gw"], 0.0
    if "imports_counted_gw" in f:       # D3: the same parts the fleet was sized with (one basis)
        parts = {"nuclear_at_peak_gw": f["nuclear_at_peak_gw"], "ps_at_peak_gw": f["ps_at_peak_gw"],
                 "imports_metered_at_peak_gw": f["imports_metered_at_peak_gw"],
                 "imports_contracted_gw": f["imports_contracted_gw"], "imports_counted_gw": f["imports_counted_gw"],
                 "ic_basis": f["ic_basis"]}
        at_peak = parts["nuclear_at_peak_gw"] + parts["ps_at_peak_gw"] + parts["imports_counted_gw"]
        if f["ic_basis"] == "metered" or year < IC_FIRST_CM_YEAR:
            at_peak = kept_at_peak_gw(year, residual)     # v4-s35 exactly (same half-hour)
            parts["nuclear_at_peak_gw"] = kept_at_peak_parts(year, residual)["nuclear"]
    else:
        parts = {"nuclear_at_peak_gw": kept_at_peak_parts(year, residual)["nuclear"]}
        at_peak = kept_at_peak_gw(year, residual)
    # 0089 (variant D default): from the first CM year nuclear counts at its CM obligation on calendar
    # years (cm_contracted), not its output at the peak half-hour; PS and imports as above.
    nuc_contracted = None
    if nuclear_column is not None and year >= IC_FIRST_CM_YEAR:
        cy = cm_contracted.nuclear_contracted_cy_mw(nuclear_column)
        if year in cy:
            nuc_contracted = cy[year] / 1e3
            at_peak = at_peak - parts["nuclear_at_peak_gw"] + nuc_contracted
    return {**parts, "nuclear_contracted_gw": nuc_contracted,
            "existing_unkept_gw": existing, "unlisted_gw": unlisted, "kept_at_peak_gw": at_peak,
            "non_go1_gw": existing + unlisted + at_peak,
            "new_gw": new, "firm_spare_gw": spare, "kept_coal_gw": kept,
            "go1_paid_gw": new + spare + kept, "total_gw": f["derated_gw"] + at_peak}


@lru_cache(maxsize=None)
def go4_options(gen_share: str = "removed", years=YEARS) -> dict[str, dict[int, dict]]:
    """GO4 under each well-sourced balancing choice (§15.2 item 5).

    Baseline: 'ibc' (Ofgem IBC grossed up, modelled) or 'nao_2005' (NAO's measured £642m for
    2005/06 carried back with CPIH). Energy share: NESO's own workbook shares (FY2018/19, the
    spec's first year, 0.548; and the lowest and highest FY shares in the same workbook)."""
    shares = balancing_workbook_shares()
    out = {}
    for opt in ("ibc", "nao_2005"):
        for name, s in (("first", shares[2018]), ("min", min(shares.values())), ("max", max(shares.values()))):
            out[f"{opt}|{name}"] = balancing.go4(PRICE_BASE, s, opt, years, gen_share=gen_share)
    return out


@lru_cache(maxsize=None)
def balancing_workbook_shares() -> dict[int, float]:
    """(Constraints + Energy Imbalance) ÷ total by FY, NESO 2025 Annual Balancing Costs workbook."""
    import openpyxl
    ws = openpyxl.load_workbook(balancing.WORKBOOK, read_only=True, data_only=True)["Total outturn"]
    rows = list(ws.iter_rows(values_only=True))
    h = next(r for r in rows if r and r[0] == "FY")
    cats = [c for c in h[1:] if c and str(c).endswith("(£)")]
    if not {"Constraints (£)", "Energy Imbalance (£)"} <= set(cats):
        raise ValueError("NESO workbook headers moved")
    out = {}
    for r in rows:
        if r and isinstance(r[0], str) and r[0][:2] == "20" and "/" in r[0]:
            d = dict(zip(h, r))
            out[int(r[0][:4])] = (d["Constraints (£)"] + d["Energy Imbalance (£)"]) / sum(d[c] for c in cats)
    return out


# Central GO4 (Richard, 14 Oct 2026, spec §15.1 item 8): B0 option 'ibc' with the NESO
# workbook's FY2018/19 energy share (`balancing.energy_share_2018()`, the spec's first year).
# A stated exception to standing decision 7 (conservative rule): the stacked choice below put
# net zero's balancing cost below zero in 16 of 23 years, including 2002-05 themselves.
GO4_CENTRAL = "ibc|first"


@lru_cache(maxsize=None)
def go4_stacked_choice(gen_share: str = "removed") -> str:
    """The stacked cautious choice (the s27-s32 central, §15.2 item 5): of the well-sourced
    options, the one rule giving the largest GO4 (so the smallest net-zero cost) summed over
    2002-2025 in 2025 money. Since v4-s33 the LOW end of the balancing range, not the central."""
    opts = go4_options(gen_share)
    tot = {k: sum(real(v[y]["gbp_m"], y) for y in YEARS) for k, v in opts.items()}
    return max(tot, key=tot.get)


@lru_cache(maxsize=None)
def go4_high_choice(gen_share: str = "removed") -> str:
    """The option giving the smallest GO4 (largest net-zero cost): the HIGH end of the range."""
    opts = go4_options(gen_share)
    tot = {k: sum(real(v[y]["gbp_m"], y) for y in YEARS) for k, v in opts.items()}
    return min(tot, key=tot.get)


def go4_central_choice(gen_share: str = "removed") -> str:
    """The central GO4 rule (Richard, 14 Oct 2026; spec §15.1 item 8): 'ibc|first', one rule for
    every year. `gen_share` is accepted for call compatibility; the rule does not depend on it."""
    if gen_share not in balancing.BSUOS_GEN_OPTIONS:
        raise ValueError(gen_share)
    return GO4_CENTRAL


def _lfl_args(s: Settings, y: int) -> tuple:
    """The one constructor of `fleet_lfl`'s arguments after the year (s36 F1-10): used by `build`
    and `go4_line`, so GO4's gas uplift is always the build's own. 0069/0086 (ticket 18): the
    moe_crisis rule applies in the crisis years only; other years take 'shao' so they share the cache."""
    return (s.margin, s.residual, s.transport, s.route, s.moe, s.closures, s.newbuild,
            s.gas_feedback, s.coal_lf, s.ic_basis, s.moe_crisis if y in MC.CRISIS_YEARS else "shao",
            s.extra_running, s.closure_test, s.kept_filter_vom, s.kept_coal_pay, s.kept_life_ext,
            s.closures_real_date_class, s.cost_case)


def go4_line(s: Settings) -> dict[int, dict]:
    """GO4 for settings `s`. s36 F1 (ticket 10): in the like-for-like fleet the energy part is
    carried at Reliable Britain's own feedback-raised gas price, u(y) = the build's
    `gas_feedback.price_rise_frac` (`_lfl_args`); the all-new fleet has no feedback (u = None)."""
    if s.bal_share is None and s.bal_option is None:
        opt, which = go4_central_choice(s.bsuos_gen).split("|")
        shares = balancing_workbook_shares()
        share = {"first": shares[2018], "min": min(shares.values()), "max": max(shares.values())}[which]
    else:
        opt = s.bal_option or go4_central_choice(s.bsuos_gen).split("|")[0]
        share = s.bal_share if s.bal_share is not None else balancing.energy_share_2018()
    u = ({y: fleet_lfl(y, *_lfl_args(s, y))["gas_feedback"].get("price_rise_frac", 0.0) for y in YEARS}
         if s.fleet == "like_for_like" else None)
    return balancing.go4(PRICE_BASE, share, opt, YEARS, gen_share=s.bsuos_gen, gas_uplift=u)


# ----------------------------------------------------------------------------- the build

def _line(lid: str, y: int, nominal: float | None, basis: str, src: str, note: str = "",
          label: str | None = None, geo: str | None = None) -> dict:
    H = households_count()[y]
    grp = GROUP.get(lid, "same_in_both" if lid.startswith("S1.") else None)
    if grp is None:
        raise KeyError(f"line {lid!r} has no reader group (spec §15.3 item 3)")
    if nominal is None:
        return {"id": lid, "group": grp, "label": label or LABELS.get(lid, lid), "national_gbp_m_nominal": None,
                "national_gbp_m_real": None, "per_household_real": None, "per_household_nominal": None,
                "basis": "UNSOURCED", "geo": geo or GEO.get(lid, "GB"), "source_ids": ["UNSOURCED"],
                "years_note": note}
    return {"id": lid, "group": grp, "label": label or LABELS.get(lid, lid), "national_gbp_m_nominal": nominal,
            "national_gbp_m_real": real(nominal, y), "per_household_real": real(nominal, y) * 1e6 / H,
            "per_household_nominal": nominal * 1e6 / H, "basis": basis, "geo": geo or GEO.get(lid, "GB"),
            "source_ids": [x for x in src.replace("|", ";").replace("+", ";").split(";") if x],
            "years_note": note}


def _carbon_split_lines(y: int, sp: dict) -> dict:
    t, p = sp["carbon_price_receipts"], sp["carbon_in_price"]
    p3 = (f" (of which 2012 Phase III auctions {t['ets_phase3_gbp_m']:.0f})"
          if t.get("ets_phase3_gbp_m") else "")
    return {
        "carbon_price_receipts": _line("NZ1c_tax", y, t["gbp_m"], t["basis"], t["source_id"],
                                      f"CPS {t['cps_gbp_m']:.0f} + UK auction receipts on power, GB part "
                                      f"{t['ets_gbp_m']:.0f}{p3}; inside NZ1, never added"),
        "carbon_in_price": _line("NZ1c_price", y, p["gbp_m"], p["basis"], p["source_id"],
                                 # 0144 item 5a: relabelled (v4-s36 said nobody in GB collected it)
                                 "rest of carbon in the wholesale price: "
                                 "carbon in the power price not collected as UK carbon tax (the rest)"
                                 "; inside NZ1, never added"),
    }


def record_netzero_fallbacks(s: Settings) -> None:
    """Register s27b's declared fallbacks (subsidies.FIT_FALLBACKS, carbon.CARBON_FALLBACKS, the
    BSUoS interpolations) in the `fallbacks` registry when the setting that uses them is on, each
    with its size, so `meta.fallbacks` lists them (spec §15.5 item 3: no silent fallbacks)."""
    from gascf import fallbacks as fb
    # C-008: no FiT fallback left (SY1-5 are Ofgem's published levelisation funds)
    if s.carbon_split:
        cpf = carbon.cpf_receipts()
        fb.record("cpf-receipts-2013", 2013, cpf[2013][0], "£m nominal",
                  "HMRC Table 1b: total CCL+CPF 2013 less 2012")
    if s.bsuos_gen == "removed":
        for y, v in balancing.bsuos_gen_share_fy().items():
            if v["basis"] == "estimated":
                fb.record("bsuos-gen-share-interpolated", y, v["share"], "share of BSUoS (FY)",
                          "straight line between CMP308 anchors (50:50 to FY2012/13, 49:51 2017, 47:53 2020)"
                          if y < 2020 else "CMP308 'expected 47:53 by 2020' carried to FY2022/23")
    fb.record("bsuos-fy2006-ibc-grossup", 2006, balancing.bsuos_fy()[2006]["gbp_m"], "£m nominal (FY)",
              "NZ6 FY2006/07: NG 2010 Table 1 IBC x (1 + FY2007/08 internal ratio)")
    fb.record("bsuos-fy2010-internal-cpih-interpolation", 2010, balancing.fy2010_internal(), "£m nominal (FY)",
              "NZ6 FY2010/11 internal part: real-terms (CPIH) mean of the FY2009/10 and FY2011/12 internal costs")


def s1_lines(y: int) -> list[dict]:
    """The same-in-both block, read through `same_in_both.block()` (s21a improves it in
    parallel; whatever items it carries flow through). Per-household nominal → national."""
    b = same_in_both.block()[y]
    H = households_count()[y]
    out = []
    for item, v in b.items():
        if item == "total" or item.endswith("_gbp_m") or not isinstance(v, dict) or "value" not in v:
            continue
        nom = None if v["value"] is None else v["value"] * H / 1e6
        out.append(_line(f"S1.{item}", y, nom, v["basis"], v["source_id"], v.get("note", ""),
                         label=f"Same in both: {item}", geo="GB"))
    return out


def _gen_nz_charge_series(s: Settings, nz6: dict, nz7: dict, go4: dict, go5: dict, V: dict) -> dict | None:
    """0167 way 2 (`gascf.gen_nz_charge`): per year the net-zero part of the generators' BSUoS and TNUoS, £m, and
    that part per MWh of real Britain's billed power. None when the switch is OFF. A component whose generators'
    share is 'included' in both bills is already counted there, so it is zero here."""
    from gascf import gen_nz_charge as GNC
    if GNC.check(s.gen_nz_charge) == "none":
        return None
    zero = {y: 0.0 for y in YEARS}
    if s.bsuos_gen == "removed":
        nz6w, go4w = balancing.nz6(YEARS, "included"), go4_line(replace(s, bsuos_gen="included"))
        b = GNC.net_zero_part({y: nz6w[y]["gbp_m"] for y in YEARS}, {y: nz6[y]["gbp_m"] for y in YEARS},
                              {y: go4w[y]["gbp_m"] for y in YEARS}, {y: go4[y]["gbp_m"] for y in YEARS}, YEARS)
    else:
        b = zero
    if s.tnuos_gen == "removed":
        fld = "gbp_m" if s.renewal == "central" else s.renewal          # the field the GO5 line reads
        nz7w, go5w = grid.nz7(YEARS, "included"), grid.go5(PRICE_BASE, YEARS, s.go5_index, "included")
        t = GNC.net_zero_part({y: nz7w[y]["gbp_m"] for y in YEARS}, {y: nz7[y]["gbp_m"] for y in YEARS},
                              {y: go5w[y][fld] for y in YEARS}, {y: go5[y][fld] for y in YEARS}, YEARS)
    else:
        t = zero
    v = {y: sum(V[(y, m)] for m in range(1, 13)) for y in YEARS}
    return GNC.series(b, t, v, YEARS)


def sl_unbilled_gbp_m(y: int, f: dict, s: Settings, gen_nz_per_mwh: float = 0.0) -> float:
    """0059 D1/D4: the station load RB's fleet generates but does not bill, £m nominal, at the price it is
    billed at today: Σ months (P(m) − C(m)) × SL(m) on the market-priced part (like for like); the all-new
    fleet at P − C too (0108 item 1.5 (b); "fleet_avg" is a setting only); the kept-price sensitivities at P − C
    (0108 item 1.6 (a)). 0167 way 2 (`gen_nz_per_mwh`, 0 when OFF): the market price less the generators' net-zero
    charge per MWh; the fleet-average paths already carry it through f['gbp_per_mwh']."""
    P, C, SL = p_elec(s.route), c_marg(), station_load_monthly()
    months = [(y, m) for m in range(1, 13)]
    if s.sl_all_new_price not in ("fleet_avg", "less_carbon") or s.sl_kept_price not in ("less_carbon", "follow_kept"):
        raise ValueError((s.sl_all_new_price, s.sl_kept_price))
    less_carbon = sum((P[k]["gbp_per_mwh"] - C[k]["gbp_per_mwh"] - gen_nz_per_mwh) * SL[k] for k in months)
    if s.fleet == "all_new":
        return f["gbp_per_mwh"] * sum(SL[k] for k in months) if s.sl_all_new_price == "fleet_avg" else less_carbon
    if s.sl_kept_price == "follow_kept" and s.kept_price == "actual":
        return sum((P[k]["gbp_per_mwh"] - gen_nz_per_mwh) * SL[k] for k in months)
    if s.sl_kept_price == "follow_kept" and s.kept_price == "fleet_avg":
        return f["gbp_per_mwh"] * sum(SL[k] for k in months)
    return less_carbon


def build(s: Settings = CENTRAL) -> dict[int, dict]:
    """Both bills for every year 2002-2025 under settings `s` (see `_build`). The input guards run on every
    call, outside the Settings cache: s36 B-merge cause 4, a guard inside the cached body was skipped for any
    Settings already built in the process."""
    if s.residual not in ("neso", "fuelhh"):
        raise ValueError(s.residual)
    if s.moe_crisis not in MC.RULES:
        raise ValueError(f"moe_crisis {s.moe_crisis!r}: one of {MC.RULES}")
    if s.moe_crisis in MC.SCALED_RULES:
        MC.require_sourced()          # 0069 test 1: before any output (M10's held rule too)
    if s.cost_case != "medium" and s.fleet != "like_for_like":
        # O2 is threaded through the like-for-like fleet only; the all-new comparison fleet would silently ignore it
        raise NotImplementedError(f"cost_case {s.cost_case!r} is built for the like-for-like fleet only")
    from gascf import fallbacks as _FB
    from gascf.system_costs import domestic_share_cy as _dsh
    _FB.require_recorded_carry_forward("domestic-share-2025-carried", _dsh())   # 0060: no silent 2025 carry
    return _build(s)


build.cache_clear = lambda: _build.cache_clear()     # the cache lives on _build


@lru_cache(maxsize=None)
def _build(s: Settings = CENTRAL) -> dict[int, dict]:
    """Both bills for every year 2002-2025 under settings `s`.

    Returns {year: {"netzero": [lines], "fossil": [lines], "nz1c": line, "totals": {...},
    "fleet": {...}, "volume": {...}, "cm": {...}}}. Totals are nominal £m.
    """
    V, K, SL = v_monthly(), kept_monthly_neso(), station_load_monthly()
    P, C = p_elec(s.route), c_marg()
    nz1 = nz1_by_year(s.route)
    nz1c = nz1c_by_year()
    ro, cm = subsidies.ro(YEARS), subsidies.CM_paid(YEARS)
    if s.ro_mutualisation == "received":
        ro_mut = subsidies.ro_mutualisation_cy(YEARS)
    elif s.ro_mutualisation == "off":
        ro_mut = {y: 0.0 for y in YEARS}
    else:
        raise ValueError(s.ro_mutualisation)
    fit = subsidies.fit(YEARS, s.fit_basis)
    cfd = subsidies.cfd(YEARS, "other" if s.cfd_split else "all")
    cfd_bio = subsidies.cfd(YEARS, "biomass") if s.cfd_split else None
    nz6 = balancing.nz6(YEARS, s.bsuos_gen)
    nz7 = grid.nz7(YEARS, s.tnuos_gen)
    ccl = subsidies.ccl_electricity(YEARS)
    from gascf.system_costs import domestic_share_cy, gb_share_of_uk, SRC_SUBNAT
    dsh = domestic_share_cy()
    vat_rate = same_in_both.domestic_vat_rate()["rate"]
    sch = schemes.schemes()
    go4 = go4_line(s)
    go5 = grid.go5(PRICE_BASE, YEARS, s.go5_index, s.tnuos_gen)
    nz1c_sp = carbon.nz1c_split(nz1c) if s.carbon_split else None
    gnc = _gen_nz_charge_series(s, nz6, nz7, go4, go5, V)     # 0167 way 2; None when OFF
    record_netzero_fallbacks(s)
    q_cm = cm_obligation_mw_year()
    out = {}
    for y in YEARS:
        if s.fleet == "all_new":
            f = fleet(y, s.margin, s.residual, s.coal_rule, s.transport, s.ic_basis)
        elif s.fleet == "like_for_like":
            f = fleet_lfl(y, *_lfl_args(s, y))
        else:
            raise ValueError(s.fleet)
        if f["ic_called_twh"] > 0:
            # 0063: the move from fleet energy to kept, priced in GO1k, is not wired: in both fleet
            # paths the dispatched fleet is built to the metered residual peak, so called is 0
            raise NotImplementedError(f"{y}: contracted imports called {f['ic_called_twh']} TWh (0063 move)")
        months = [(y, m) for m in range(1, 13)]
        # ---- 0167 way 2: the generators' net-zero charge off every MWh fossil Britain buys at the market price
        dlt = gnc[y]["gbp_per_mwh"] if gnc is not None else 0.0
        if gnc is not None:
            mkt_twh = f.get("market_twh", 0.0) + (f.get("extra_twh", 0.0) if f.get("extra_running") == "market" else 0.0)
            cut_f = dlt * mkt_twh
            tot_f = f["total_gbp_m"] - cut_f
            f = {**f, "total_gbp_m": tot_f, "gbp_per_mwh": tot_f / f["energy_twh"] if f["energy_twh"] else 0.0,
                 **({"market_gbp_m": f["market_gbp_m"] - cut_f} if "market_gbp_m" in f else {}),
                 "gen_nz_charge": {**gnc[y], "fleet_twh": mkt_twh, "fleet_gbp_m": cut_f}}
            # v4-s40 item 2 (0175): the same charge comes off kept coal's road margin, so its top-up can rise
            k0 = f.get("kept_coal_pay")
            if k0 is not None:
                k1 = kept_coal_pay_after_charge(k0, dlt, y)
                dk = k1["paid_gbp_m"] - k0["paid_gbp_m"]
                if k1 is not k0:
                    tot_f = f["total_gbp_m"] + dk
                    f = {**f, "kept_coal_pay": k1, "total_gbp_m": tot_f, "fixed_gbp_m": f["fixed_gbp_m"] + dk,
                         "gbp_per_mwh": tot_f / f["energy_twh"] if f["energy_twh"] else 0.0}
        # ---- 0059: station load stays in the fleet's generation (sizing, dispatch unchanged), not in the bill
        sl_unbilled = (sl_unbilled_gbp_m(y, f, s, gen_nz_per_mwh=dlt) if gnc is not None
                       else sl_unbilled_gbp_m(y, f, s))     # OFF: the v4-s38 call, unchanged
        sl_cut = (sl_unbilled_gbp_m(y, f, s) - sl_unbilled) if gnc is not None else 0.0   # 0167: delta x SL at market
        f = {**f, "sl_unbilled_gbp_m": sl_unbilled, "total_gbp_m": f["total_gbp_m"] - sl_unbilled,
             **({"market_gbp_m": f["market_gbp_m"] - sl_unbilled} if "market_gbp_m" in f else {})}
        v_y = sum(V[k] for k in months)
        if s.residual == "fuelhh" and y >= 2016:
            kept = {k: V[k] + SL[k] - f["energy_monthly_twh"][k[1]] for k in months}  # remainder of V
        else:
            kept = {k: K[k] for k in months}
        kept_y = sum(kept.values())
        # ---- GO1k: kept output at the actual price less carbon (§15 7a (i))
        # like for like: merit-order uplift and gas-price feedback on the kept (market-priced) output
        uplift_k = f.get("moe_kept_gbp_m", 0.0)
        gfb_k = f.get("gas_feedback_kept_gbp_m", 0.0)
        moe_k = uplift_k + gfb_k
        if s.kept_price == "less_carbon":
            go1k = sum((P[k]["gbp_per_mwh"] - C[k]["gbp_per_mwh"]) * kept[k] for k in months) + moe_k
            go1k_basis = weakest("modelled", *(P[k]["basis"] for k in months), *(C[k]["basis"] for k in months))
            go1k_src = f"{nz1[y]['source_id']};{nz1c[y]['source_id']};neso-hdd;dukes-5.6;et-5.4"
        elif s.kept_price == "actual":
            go1k = sum(P[k]["gbp_per_mwh"] * kept[k] for k in months) + moe_k
            go1k_basis, go1k_src = "modelled", f"{nz1[y]['source_id']};neso-hdd;dukes-5.6"
        elif s.kept_price == "fleet_avg":
            go1k = f["gbp_per_mwh"] * kept_y
            go1k_basis, go1k_src = "modelled", "GO1-average-cost;neso-hdd;dukes-5.6"
        else:
            raise ValueError(s.kept_price)
        if gnc is not None:
            # 0167 way 2: kept output bought at the market price (less carbon, or actual) carries delta too; at the
            # fleet's average cost (fleet_avg) it already follows the fleet's cut price per MWh
            cut_k = dlt * kept_y if s.kept_price in ("less_carbon", "actual") else 0.0
            go1k -= cut_k
            sl_twh = sum(SL[k] for k in months)
            g = f["gen_nz_charge"]
            f = {**f, "gen_nz_charge": {**g, "kept_twh": kept_y if cut_k else 0.0, "kept_gbp_m": cut_k,
                                        "station_load_twh": sl_twh, "station_load_gbp_m": sl_cut,
                                        # GO1 + GO1k fall by this (before VAT; GO7 follows them)
                                        "fossil_cut_gbp_m": g["fleet_gbp_m"] + cut_k - sl_cut}}
        # ---- NZ5 (§5.4, s32): the actual CM less what Reliable Britain would have paid anyway:
        # its notional CM = that year's £/kW × the de-rated firm capacity whose fixed cost GO1
        # does NOT already carry (existing unkept plant, unlisted firm plant, nuclear / pumped
        # storage / imports at its residual peak). New plant, the firm spare and kept-open coal
        # are excluded: GO1 pays their capital / keep-open cost in full, so a CM on them would
        # count Reliable Britain's backup twice. cm_rule 'extra_kept_coal' (low side, §11)
        # counts kept coal as needing CM too; 'full' (high side, 7c(ii)) the whole CM.
        cm_paid = cm[y]["gbp_m"]
        split = cm_split(f, y, s.residual, nuclear_column=s.nuclear_cm_column)
        firm_gw = split["total_gw"]
        if y in CM_EARLY_YEARS and q_cm.get(y):
            price_kw = cm_early_price()[y]["gbp_kw_yr"]
            price_basis = (f"clearing price of the main auction(s) {cm_early_price()[y]['auctions'] or 'none'} "
                           f"x months delivered/12 (Finding 7 rule, Ofgem CM AR 2025/26 Table 4)")
        else:
            price_kw = cm_paid / q_cm[y] * 1000 if q_cm.get(y) else 0.0      # £/kW-yr
            price_basis = "CM paid / mean obligation (LCCC)"
        cm_gw = split["non_go1_gw"] + (split["kept_coal_gw"] if s.cm_rule == "extra_kept_coal" else 0.0)
        cm_rb = price_kw * cm_gw                                               # £m (£/kW × GW)
        nz5_unfloored = cm_paid - cm_rb
        if s.cm_rule == "full":
            nz5, nz5_note, cm_fossil = cm_paid, "§15 7c(ii): full Capacity Market (high side)", cm_rb
        elif s.cm_rule in ("extra", "extra_kept_coal"):
            cm_fossil = cm_rb
            nz5 = max(0.0, nz5_unfloored)
            nz5_note = (f"CM paid {cm_paid:.1f} less Reliable Britain's notional CM {cm_rb:.1f} = "
                        f"£{price_kw:.2f}/kW ({price_basis}) x {cm_gw:.1f} GW de-rated not paid by GO1 "
                        f"(existing unkept {split['existing_unkept_gw']:.1f} + unlisted {split['unlisted_gw']:.1f}"
                        f" + nuclear/PS/imports at peak {split['kept_at_peak_gw']:.1f}"
                        + (f" + kept coal {split['kept_coal_gw']:.1f}" if s.cm_rule == "extra_kept_coal" else "")
                        + f"); excluded as GO1-paid: new {split['new_gw']:.1f}, spare {split['firm_spare_gw']:.1f}"
                        + ("" if s.cm_rule == "extra_kept_coal" else f", kept coal {split['kept_coal_gw']:.1f}")
                        + (f"; unfloored {nz5_unfloored:.1f}, floored at 0" if nz5_unfloored < 0 else ""))
        else:
            raise ValueError(s.cm_rule)
        H = households_count()[y]
        gb, gb_basis = gb_share_of_uk(y)
        gb_note = f"UK total x GB share of consumption {gb:.4f} (DESNZ subnational 7.1{'' if gb_basis == 'modelled' else ', nearest year'})"
        # ---- 0097: the Fossil Fuel Levy (the NFFO part of NZ2) is on the road at its 2001 level to 2019
        otr2 = _otr.net({y: ro[y]["gbp_m"] * gb}, s.otr_nz2_level_gbp_m, indexation=s.otr_indexation,
                        end_year=s.otr_nz2_end_year, applies_to="NZ2")
        otr_nz2 = otr2["netted"][y]
        # ---- 0097: EESoP (NZ10's predecessor) is on the road at its 2001 level, every year
        otr10 = _otr.net({y: sch[y]["gbp_m"]}, s.otr_nz10_level_gbp_m, indexation=s.otr_indexation,
                         end_year=s.otr_nz10_end_year, applies_to="NZ10")
        otr_nz10 = otr10["netted"][y]
        # ---- 0044: the CCL at its 2001 rate x the inferred taxable volume is on the road (0101 component)
        nz8_paid = ccl[y]["gbp_m"] * gb
        if s.ccl_baseline not in ("cpih_2001", "cash_2001", "none"):
            raise ValueError(s.ccl_baseline)
        otr8 = (_otr.net({y: nz8_paid}, _cclb.RATE_2001, mode="rate_x_volume",
                         indexation="real_cpih" if s.ccl_baseline == "cpih_2001" else "cash",
                         volume={y: _cclb.inferred_volume_gwh(nz8_paid, y)}, applies_to="NZ8")
                if s.ccl_baseline != "none" else {"counted": {y: nz8_paid}, "netted": {y: 0.0}})
        otr_nz8 = otr8["netted"][y]
        # ---- 0044 D5: the levy the counterfactual pays on RB-technology output exempt through LECs (2002 to Mar 2015),
        # capped at RB's own replaced renewables volume, at the 2001 rate carried as in D3, x the GB share
        lec_cy = _lec.gb_rbtech_mwh_by_cy()
        nz8_lec, lec_capped = 0.0, None
        if s.ccl_baseline != "none" and y in lec_cy:
            rep_twh = f.get("renewables_replaced_twh")
            if rep_twh is None:
                rep_twh = fleet_lfl(y, *_lfl_args(s, y))["renewables_replaced_twh"]
            mwh = lec_cy[y]["gb_rbtech_mwh"]
            lec_capped = mwh > rep_twh * 1e6
            if s.ccl_lec_cap:
                mwh = min(mwh, rep_twh * 1e6)
            rate = _cclb.RATE_2001 * (dfl.cpih()[y] / dfl.cpih()[2001] if s.ccl_baseline == "cpih_2001" else 1.0)
            nz8_lec = mwh * 1e3 * rate * gb / 1e6
        nzl = [
            _line("NZ1", y, nz1[y]["gbp_m"], nz1[y]["basis"], nz1[y]["source_id"] + ";neso-hdd"),
            _line("NZ2", y, otr2["counted"][y] + ro_mut[y], weakest(ro[y]["basis"], gb_basis),
                  f"{ro[y]['source_id']};{SRC_SUBNAT};ons-ciqy-ffl"
                  + (f";{subsidies.SRC_RO_MUT}" if ro_mut[y] else ""),
                  gb_note + (f"; Fossil Fuel Levy on the road at its 2001 level (0097) -{otr_nz2:.0f}" if otr_nz2 else "")
                  + (f"; GB RO mutualisation received +{ro_mut[y]:.1f} (decision 0169)" if ro_mut[y] else "")),
            _line("NZ3", y, fit[y]["gbp_m"], fit[y]["basis"], fit[y]["source_id"],
                  label=None if s.fit_basis == "levelisation" else "Feed-in tariffs (scheme value)"),
            _line("NZ4", y, cfd[y]["gbp_m"], cfd[y]["basis"], cfd[y]["source_id"],
                  label=None if s.cfd_split else "Contracts for Difference"),
            *([_line("NZ4b", y, cfd_bio[y]["gbp_m"], cfd_bio[y]["basis"], cfd_bio[y]["source_id"],
                     "CfD paid to Biomass Conversion (Drax) and Dedicated Biomass units, LCCC")]
              if s.cfd_split else []),
            _line("NZ5", y, nz5, "modelled" if cm_paid else "measured",
                  f"{cm[y]['source_id']};lccc-cm-obligation-mw;GO1"
                  + (f";{SRC_CM_EARLY}" if y in CM_EARLY_YEARS else ""), nz5_note),
            _line("NZ6", y, nz6[y]["gbp_m"], nz6[y]["basis"], nz6[y]["source_id"],
                  f"generators' share {nz6[y].get('gen_share', 0):.1%} removed"),
            _line("NZ7", y, nz7[y]["gbp_m"], nz7[y]["basis"], nz7[y]["source_id"],
                  f"generators' share {nz7[y].get('gen_share', 0):.1%} removed"),
            _line("NZ8", y, otr8["counted"][y] - nz8_lec, weakest(ccl[y]["basis"], gb_basis),
                  f"{ccl[y]['source_id']};{SRC_SUBNAT}" + (";hmrc-envtax-historical-rates" if otr_nz8 else ""),
                  gb_note + (f"; levy at its 2001 rate on the road (0044) -{otr_nz8:.0f}" if otr_nz8 else "")
                  + (f"; LEC-exempt output at the 2001 rate (0044, "
                        + ("capped at RB's replaced renewables" if s.ccl_lec_cap else "uncapped, note run") + f") -{nz8_lec:.0f}"
                     if nz8_lec else "")),
            _line("NZ10", y, otr10["counted"][y], sch[y]["basis"], sch[y]["source_id"] + ";ofgem-est-2003-eesop",
                  ((sch[y]["note"] + f"; range {sch[y]['low']:.0f}-{sch[y]['high']:.0f}") if sch[y]["gbp_m"]
                   else "no scheme in force")
                  + (f"; EESoP on the road at its 2001 level (0097) -{otr_nz10:.0f}" if otr_nz10 else "")),
        ]
        if s.fleet == "like_for_like":
            go1_note = (f"actual fossil {f['gen_twh']['actual_fossil']:.1f} TWh at actual price less carbon "
                        f"{f['market_gbp_m'] - f.get('extra_market_gbp_m', 0.0):.0f}; renewables replaced "
                        f"{f['renewables_replaced_twh']:.1f} TWh: extra running of existing plant "
                        f"{f['gen_twh']['extra_existing']:.1f} TWh {f['extra_running_gbp_m']:.0f} "
                        f"({'at the market price, 0144' if s.extra_running == 'market' else 'at cost'}), new CCGT {f['ccgt_gw']:.1f} / OCGT {f['ocgt_gw']:.1f} GW "
                        f"{f['new_total_gbp_m']:.0f}, extra firm {f['firm_extra_gw']:.1f} GW; merit-order uplift "
                        f"{f['moe']['applied_mean_gbp_mwh']:.2f} £/MWh ({s.moe}"
                        f"{'; 2021-23 rule ' + f['moe']['crisis_rule'] if f['moe'].get('crisis_rule', 'shao') != 'shao' else ''}) "
                        f"{f['moe_gbp_m']:.0f}; "
                        f"gas-price feedback ({s.gas_feedback}) {f.get('gas_feedback_gbp_m', 0.0):.0f} on market MWh "
                        f"+ {f.get('gas_feedback_at_cost_gbp_m', 0.0):.0f} at-cost fuel; coal LF rule {s.coal_lf}")
            go1_label = "Power: the actual plant less carbon, renewables' output replaced by fossil"
            go1_note += f"; station load generated, not billed (0059) −{sl_unbilled:.0f} on market MWh"
        else:
            go1_note = (f"coal {f['coal_gw']:.1f} GW (cap {f['coal_cap_gw']:.1f}), CCGT {f['ccgt_gw']:.1f}, "
                        f"OCGT {f['ocgt_gw']:.1f}, spare {f['spare_gw']:.1f} GW; edition {f['cost_edition']}")
            go1_label = None
            go1_note += f"; station load generated, not billed (0059) −{sl_unbilled:.0f} at average cost"
        go4_note = (f"energy share {go4[y]['energy_share']:.3f}; generators' share "
                    f"{go4[y].get('gen_share', 0) if s.bsuos_gen == 'removed' else 0:.1%} removed"
                    + (f"; energy part at RB's own gas price (+{go4[y]['gas_uplift_frac']:.1%}, "
                       f"{go4[y]['gas_feedback_gbp_m']:.0f})" if go4[y]["gas_uplift_frac"] else ""))
        go_l = [
            _line("GO1", y, f["total_gbp_m"], f["basis"], f["source_id"], go1_note, label=go1_label),
            _line("GO1k", y, go1k, go1k_basis, go1k_src, f"kept {kept_y:.1f} TWh, price option {s.kept_price}"
                  + (f"; merit-order uplift {uplift_k:.0f}" if uplift_k else "")
                  + (f"; gas-price feedback {gfb_k:.0f}" if gfb_k else "")),
            _line("GO2", y, 0.0, "modelled", "inside-GO1", "spare plant inside GO1"),
            _line("GO3", y, 0.0, "modelled", "brief-3.1-no-carbon"),
            {**_line("GO4", y, go4[y]["gbp_m"], go4[y]["basis"], go4[y]["source_id"], go4_note),
             "gas_feedback_gbp_m": go4[y]["gas_feedback_gbp_m"]},     # s36 F1: dGO4 from the feedback
            {**_line("GO5", y, go5[y]["gbp_m"] if s.renewal == "central" else go5[y][s.renewal],
                  weakest(go5[y]["basis"], "estimated"), go5[y]["source_id"],
                  f"carried {go5[y]['carried_gbp_m']:.0f} by {s.go5_index.upper()} + renewal allowance "
                  f"({s.renewal}); generators' share "
                  f"{go5[y].get('gen_share', 0) if s.tnuos_gen == 'removed' else 0:.1%} removed"),
             "carried_gbp_m": go5[y]["carried_gbp_m"]},   # ticket 29 note 3 (0117): renewal R = GO5 - carried
            _line("GO6", y, 0.0, "modelled", "brief-3-no-levies"),
        ]
        # ---- NZ11 / GO7 (s30): VAT, a tax that exists only on what households pay. 5% on the
        # domestic share of each Britain's wholesale, subsidy, backup and grid lines, and on the
        # energy-saving schemes in full (recovered from households only). CCL is not charged on
        # domestic supply, so it carries no domestic VAT. Business VAT is recovered: not a cost.
        d = dsh.get(y, dsh[max(dsh)])
        nv = {l["id"]: l["national_gbp_m_nominal"] for l in nzl}
        gv = {l["id"]: l["national_gbp_m_nominal"] for l in go_l}
        nz_base = d * sum(nv.get(i, 0.0) for i in ("NZ1", "NZ2", "NZ3", "NZ4", "NZ4b", "NZ5", "NZ6", "NZ7")) + nv["NZ10"]
        go_base = d * sum(gv[i] for i in ("GO1", "GO1k", "GO2", "GO3", "GO4", "GO5"))
        vat_src = "hmrc-vfup1000;dukes-5.2;dukes-5.5D"
        vat_basis = "modelled" if y in dsh else "estimated"
        nzl.append(_line("NZ11", y, vat_rate * nz_base, vat_basis, vat_src,
                         f"5% x (domestic share {d:.3f} x NZ1-NZ7 + NZ10)"))
        go_l.append(_line("GO7", y, vat_rate * go_base, vat_basis, vat_src,
                          f"5% x domestic share {d:.3f} x (GO1 + GO1k + GO2 + GO3 + GO4 + GO5)"))
        go_l[-1]["domestic_share"] = d          # s36 F1: the break-even's VAT on the feedback reads it
        for l in nzl:
            l["group"] = group_of(l["id"], s)
        s1 = s1_lines(y)
        s1_tot = sum(l["national_gbp_m_nominal"] for l in s1 if l["national_gbp_m_nominal"] is not None)
        s1_complete = all(l["national_gbp_m_nominal"] is not None for l in s1)
        nz_tot = sum(l["national_gbp_m_nominal"] for l in nzl) + s1_tot
        go_tot = sum(l["national_gbp_m_nominal"] for l in go_l) + s1_tot
        out[y] = {
            "netzero": nzl, "fossil": go_l, "same_in_both": s1,
            "on_the_road": {"nz2_on_the_road_gbp_m": otr_nz2, "nz10_on_the_road_gbp_m": otr_nz10,
                            # VAT the build removed with each netting (0097, ticket 26 option a): NZ11 is
                            # vat_rate * (d * sum(NZ1..NZ7) + NZ10), so netting NZ2 (domestic share d) and NZ10
                            # (full) lowers it by exactly these. Exported so the figures keys read what the engine
                            # charged, never re-derive it.
                            "nz2_on_the_road_vat_gbp_m": vat_rate * d * otr_nz2,
                            "nz10_on_the_road_vat_gbp_m": vat_rate * otr_nz10,
                            "nz8_on_the_road_gbp_m": otr_nz8,
                            "nz8_lec_exempt_gbp_m": nz8_lec, "nz8_lec_capped": lec_capped},
            "nz1c": _line("NZ1c", y, nz1c[y]["gbp_m"], nz1c[y]["basis"],
                          f"{nz1c[y]['source_id']};{C[(y, 1)]['source_id']}", "inside NZ1, never added"),
            **({"carbon_split": _carbon_split_lines(y, nz1c_sp[y])} if s.carbon_split else {}),
            "totals": {"nz_gbp_m": nz_tot, "go_gbp_m": go_tot, "gap_gbp_m": nz_tot - go_tot,
                       "s1_gbp_m": s1_tot, "s1_complete": s1_complete,
                       "nz_real": real(nz_tot, y), "go_real": real(go_tot, y),
                       "gap_real_bn": real(nz_tot - go_tot, y) / 1e3,
                       "nz_per_hh_real": real(nz_tot, y) * 1e6 / H, "go_per_hh_real": real(go_tot, y) * 1e6 / H,
                       "gap_per_hh_real": real(nz_tot - go_tot, y) * 1e6 / H},
            "fleet": f,
            "volume": {"v_twh": v_y, "kept_twh": kept_y, "fleet_twh": f["energy_twh"],
                       "station_load_twh": sum(SL[k] for k in months),
                       # 0059 D3: the billing identity, fleet + kept − station load = V, by month
                       "billed_monthly_twh": {k[1]: f["energy_monthly_twh"][k[1]] + kept[k] - SL[k] for k in months},
                       "billed_twh": f["energy_twh"] + kept_y - sum(SL[k] for k in months),
                       "station_load_unbilled_gbp_m": sl_unbilled,
                       "basis": rn.volume_annual()[y]["basis"]},
            "cm": {"paid_gbp_m": cm_paid, "fossil_gbp_m": cm_fossil, "obligation_mw": q_cm.get(y, 0.0),
                   "fossil_firm_gw": firm_gw, "price_gbp_kw_yr": price_kw, "price_basis": price_basis,
                   "cm_gw": cm_gw, "split_gw": split, "nz5_unfloored_gbp_m": nz5_unfloored,
                   "worked_example": cm_worked_example(f),
                   "nz5_floored": nz5_unfloored < 0 and s.cm_rule != "full", "rule": s.cm_rule},
            "households": H,
        }
    return out


def line(b: dict, lid: str) -> dict:
    for side in ("netzero", "fossil"):
        for l in b[side]:
            if l["id"] == lid:
                return l
    if lid == "NZ1c":
        return b["nz1c"]
    for l in b.get("carbon_split", {}).values():
        if l["id"] == lid:
            return l
    raise KeyError(lid)


def groups_for(s: Settings) -> tuple[str, ...]:
    """The net-zero groups in force: the carbon group split in two when `s.carbon_split`."""
    return GROUPS if s.carbon_split else GROUPS_SINGLE_CARBON


def group_of(lid: str, s: Settings) -> str | None:
    """Group of a line under settings `s` (NZ8, CCL, is carbon tax collected when split)."""
    if lid == "NZ8":
        return "ccl"                 # CCL its own group under both settings (0090)
    if not s.carbon_split and lid in ("NZ1c_tax", "NZ1c_price"):
        return "carbon"
    return GROUP.get(lid)


def val(b: dict, lid: str) -> float:
    return line(b, lid)["national_gbp_m_nominal"]


# ----------------------------------------------------------------------------- ranges

# Decision 0144 (Richard Lyon, 20 Oct 2026): row names used by the switch registries and the sensitivity rows.
FEEDBACK_KRICHENE = "gas-price feedback (Krichene world long-run pair, 0.16 + 0.45 = 0.61)"   # item 2, row B
MOE_STACK = "merit-order uplift (engine's own stack estimate)"                                 # item 4A
EXTRA_AT_COST = "extra running at fuel, running and transport cost (the v4-s36 mix)"            # item 1, row C
MOE_UCL = "merit-order uplift 2021-23: UCL short-run (preprint)"                                # item 3, row B

SWITCHES: dict[str, tuple[Settings, ...]] = {
    "wholesale_pre2010 (lower / model)": (replace(CENTRAL, route="lower"), replace(CENTRAL, route="model")),
    "kept_price (actual / fleet avg)": (replace(CENTRAL, kept_price="actual"), replace(CENTRAL, kept_price="fleet_avg")),
    "spare margin (6.6% / 8.2%)": (replace(CENTRAL, margin="low"), replace(CENTRAL, margin="high")),
    "residual method 2016+ (FUELHH)": (replace(CENTRAL, residual="fuelhh"),),
    "interconnectors at peak (metered flow, v4-s35)": (replace(CENTRAL, ic_basis="metered"),),
    # s32: low side = kept coal needs CM too (smaller NZ5); high side = the full CM (7c(ii))
    "capacity market (kept coal in CM / full CM)": (replace(CENTRAL, cm_rule="extra_kept_coal"),
                                                    replace(CENTRAL, cm_rule="full")),
    "balancing (other sourced share / baseline)": (),            # filled in switch_settings()
    "grid renewal R (low / high)": (replace(CENTRAL, renewal="low"), replace(CENTRAL, renewal="high")),
    "gas transport (none)": (replace(CENTRAL, transport=False),),
    # Decision 0144 item 4A (Richard Lyon, 20 Oct 2026): the engine's own four-block stack estimate moved to the
    # methods page (kept as a sensitivity row, METHOD_SWITCHES); the feedback row rebuilt with a paired
    # elasticity: Krichene's own world long-run pair (0144 item 2, sensitivity row B). v4-s36's supply-only rows
    # (0.34 / 0.06) are gone with the supply-only formula.
    FEEDBACK_KRICHENE: (replace(CENTRAL, gas_feedback="krichene_lr"),),
}
# 0097 (ticket 26): the named sensitivity on_the_road_cash_flat, the 2001 levels of NZ2 and NZ10 held in cash.
# Separate from ticket 12's CCL cash-frozen switch (the paper prints the two apart).
OTR_CASH_FLAT = "2001 on-the-road levels held cash-flat (on_the_road_cash_flat, 0097)"
# 0044 (ticket 12): the 2001 CCL rate held cash-frozen (`a_cash`), its own named sensitivity.
CCL_CASH_FROZEN = "2001 CCL rate held cash-frozen (ccl_2001_cash_frozen, 0044)"
# 0091 (ticket 25): grid index at the price controls' own X values; printed as it falls.
RPI_X = "grid index at the controls' own X (RPI-X, 0091)"
# 0097 inputs update and 0108 item 1.20 (Richard Lyon, 19 Oct 2026: a named sensitivity, not central): the 2001 Fossil
# Fuel Levy level at the GBP 85.5m NFFO and SRO payments estimate for FY2001/02 (HC Deb 18 Apr 2002 vol 383 c1139W).
NFFO_85_5 = ("£85.5m NFFO payments estimate as the 2001 Fossil Fuel Levy level "
             "(on_the_road_nz2_nffo_payments, 0097)")
# Decision 0112 (Richard Lyon, 19 Oct 2026, item 1.4 option (a)): the printed range is set by the rows above plus the
# s36 alternative central choices: metered interconnectors (above), rpi_x, CCL cash-frozen, 2001 levels cash-flat and
# GBP 85.5m. Methods-page rows and case B stay out of the range.
SWITCHES |= {
    RPI_X: (replace(CENTRAL, go5_index="rpi_x"),),
    CCL_CASH_FROZEN: (replace(CENTRAL, ccl_baseline="cash_2001"),),
    OTR_CASH_FLAT: (replace(CENTRAL, otr_indexation="cash"),),
    NFFO_85_5: (replace(CENTRAL, otr_nz2_level_gbp_m=85.5),),
}
# Spec §15.5 item 1: Shao central, the engine's own stack estimate in SWITCHES; no uplift at all,
# and the s22 rules, are methods-page sensitivities, never in the range. 0112 / 2.4: the UCL row (M8) too.
METHOD_SWITCHES: dict[str, tuple[Settings, ...]] = {
    "no merit-order uplift (§15.3 rule)": (replace(CENTRAL, moe="none"),),
    "merit-order uplift (s22 rule: larger of model / Shao)": (replace(CENTRAL, moe="larger"),),
    "merit-order uplift (smaller of model / Shao)": (replace(CENTRAL, moe="smaller"),),
    MOE_UCL: (replace(CENTRAL, moe_crisis="ucl_stmoe"),),   # 0069; 0144 item 3 row B
    "no gas-price feedback": (replace(CENTRAL, gas_feedback="none"),),
    "no coal load-factor cap (s23b rule)": (replace(CENTRAL, coal_lf="none"),),
    "closures as they actually happened": (replace(CENTRAL, closures="actual"),),
    "new build gas only (no new coal, s22 rule)": (replace(CENTRAL, newbuild="gas_only"),),
    # rpi_x, CCL cash-frozen and the 2001 levels cash-flat moved to SWITCHES (the range) by decision 0112
    # Decision 0144 (Richard Lyon, 20 Oct 2026): item 4A, the four-block stack estimate, out of the range and kept
    # as a sensitivity row (each block has one efficiency, so taking wind out moves the price only when a block
    # runs out); item 1 row C, the v4-s36 mix (extra running at cost).
    MOE_STACK: (replace(CENTRAL, moe="model"),),
    EXTRA_AT_COST: (replace(CENTRAL, extra_running="cost"),),
}
# RB v1.1 (decision 0160, card [internal ticket]): switches built OFF by default and run as named rows so their value is
# measured, but held out of the range, the methods page and the headline until Richard rules where each is printed
# (rulings sheet R10, R13, R18; O5a is the 0044 "note run only"). Read by `one_at_a_time` into its `held` block,
# which no range or table key reads. A ruling moves a row into SWITCHES or METHOD_SWITCHES; nothing here is central.
HELD_O3 = "nuclear in the Capacity Market at its auction obligation (O3; held for ruling R18)"
# 0044 cap ruling: the uncapped LEC exemption is "the uncapped note run only (not a switch, not in the range)"; held here
# so its value is measured (O5a). Its key keeps the register's name, headline_lec_uncapped_2002_24_gbp_bn.
HELD_O5A = "LEC exemption uncapped before August 2015 (O5a; the 0044 note run)"
# M10: the 2021-23 uplift scaled to UCL's long-run (Table 5) estimate, beside the short-run row MOE_UCL (paper line 728
# "run in v1.1"); R10 asks whether it is a sensitivity row or central for 2021-23.
HELD_M10 = "merit-order uplift 2021-23: UCL long-run (preprint; M10, held for ruling R10)"
# O2: the high plant-cost case, two ways (R13): DESNZ's published high case as it stands (capital and hurdle; only
# EGC 2025 prints a high hurdle, so the two rows differ only in 2025) and high capital cost only.
HELD_O2_CAP_HURDLE = "plant costs at the editions' high case: capital and hurdle (O2; held for ruling R13)"
HELD_O2_CAP = "plant costs at the editions' high case: capital only (O2; held for ruling R13)"
HELD_SWITCHES: dict[str, tuple[Settings, ...]] = {
    HELD_O3: (replace(CENTRAL, nuclear_cm_column="auction_acquired"),),
    HELD_O5A: (replace(CENTRAL, ccl_lec_cap=False),),
    HELD_M10: (replace(CENTRAL, moe_crisis="ucl_ltmoe"),),
    HELD_O2_CAP_HURDLE: (replace(CENTRAL, cost_case="high_capital_hurdle"),),
    HELD_O2_CAP: (replace(CENTRAL, cost_case="high_capital"),),
}
# A5 (J3): Krichene's 1974-2004 long-run pair (0.21 + 0.06 = 0.27) beside the 0.61 range row; R14 asks key or run.
# Run here as a held row so its value is measured; FEEDBACK_KRICHENE (0.61) stays the range row.
HELD_A5 = "gas-price feedback (Krichene world long-run pair 1974-2004, 0.21 + 0.06 = 0.27; A5, held for ruling R14)"
HELD_SWITCHES[HELD_A5] = (replace(CENTRAL, gas_feedback="krichene_lr_1974"),)
# The "what moved" walk (s27c): the s23b central (£795 in 2025) and each spec §15.5 fix switched
# on in turn, in this order. Coal efficiency has no switch in the engine (s27a: always on), so
# its step is computed by `what_moved()` through `fossil_like_for_like.COAL_ETA_RULE` if present.
OLD_CENTRAL = replace(CENTRAL, moe="none", gas_feedback="none", coal_lf="none", tnuos_gen="included",
                      bsuos_gen="included", go5_index="cpih", fit_basis="scheme_value", cfd_split=False,
                      carbon_split=False)
WHAT_MOVED_STEPS: tuple[tuple[str, dict], ...] = (
    ("merit-order uplift (Shao)", {"moe": "shao"}),
    ("gas-price feedback", {"gas_feedback": "central"}),
    ("coal capped at DUKES load factor", {"coal_lf": "dukes_max"}),
    ("coal efficiency 2015-2023 mean", {}),
    ("TNUoS generators' share removed", {"tnuos_gen": "removed"}),
    ("BSUoS generators' share removed", {"bsuos_gen": "removed"}),
    ("grid carried by RPI", {"go5_index": "rpi"}),
    ("FiT at levelisation cost", {"fit_basis": "levelisation"}),
    ("biomass CfD split, carbon split (relabel only)", {"cfd_split": True, "carbon_split": True}),
)
# The s21b method, kept as a switch for comparison; not in the range (a different question:
# what if fossil Britain had bought every plant new).
ALL_NEW = replace(CENTRAL, fleet="all_new")


def switch_settings() -> dict[str, tuple[Settings, ...]]:
    sw = dict(SWITCHES)
    shares = balancing_workbook_shares()
    central = go4_central_choice()
    alts = []
    for k in go4_options():
        if k == central:
            continue
        opt, which = k.split("|")
        share = {"first": shares[2018], "min": min(shares.values()), "max": max(shares.values())}[which]
        alts.append(replace(CENTRAL, bal_option=opt, bal_share=share))
    sw["balancing (other sourced share / baseline)"] = tuple(alts)
    return sw


@lru_cache(maxsize=None)
def ranges() -> dict:
    """Per year: each switch's lowest and highest gap (£m nominal, one at a time from central),
    and the combined low / high (all downward swings together, all upward together)."""
    c = build(CENTRAL)
    out: dict[int, dict] = {y: {"central": c[y]["totals"]["gap_gbp_m"], "switches": {}} for y in YEARS}
    for name, sets in switch_settings().items():
        runs = [build(st) for st in sets]
        for y in YEARS:
            g = [r[y]["totals"]["gap_gbp_m"] for r in runs]
            d = [x - out[y]["central"] for x in g]
            out[y]["switches"][name] = {"low": min(d + [0.0]), "high": max(d + [0.0])}
    for y in YEARS:
        sw = out[y]["switches"].values()
        out[y]["low"] = out[y]["central"] + sum(v["low"] for v in sw)
        out[y]["high"] = out[y]["central"] + sum(v["high"] for v in sw)
    return out


# ----------------------------------------------------------------------------- §9.3

def on_household_bill(b: dict, y: int, steps: list[dict]) -> dict:
    """£ per household (2025 money) of the net-zero cost that reaches household bills
    directly: Σ domestic share × step, CCL zero (not charged on domestic supply), schemes and VAT
    in full. The EPG green-levy transfer is NOT yet deducted: its amounts are not sourced (GAP).
    For households not on prepayment the EPG discount ended on 30 June 2023 (gov.uk, "Energy
    Price Guarantee up to 30 June 2023"), so only 2022 and 2023 overstate the on-bill part;
    tagged estimated in those years."""
    from gascf.system_costs import domestic_share_cy
    share = domestic_share_cy()
    d = share.get(y, share[max(share)])
    tot = sum(st["value_gbp_m_nominal"] for st in steps if st["step"] in range(1, 8) and st["step"] != 7)
    # step 8 (energy-saving schemes) is recovered from domestic customers only, and step 9 (VAT)
    # is charged on domestic supply only: both added in full
    dom = sum(st["value_gbp_m_nominal"] for st in steps if st["step"] in (8, 9))
    H = b["households"]
    # B6: each step's part (domestic share for 1-6, nil for 7, in full for 8 and 9); adds to `value`
    part = {n: 0.0 for n in range(1, 10)}
    for st in steps:
        n = st["step"]
        if n not in part:              # step 0 and '=' are the two bills, not steps
            continue
        part[n] += st["value_gbp_m_nominal"] * (d if n in range(1, 7) else 0.0 if n == 7 else 1.0)
    by_step = {n: {"nominal_gbp_m": v, "real_gbp_m": real(v, y), "per_household_real": real(v, y) * 1e6 / H}
               for n, v in part.items()}
    epg = y in (2022, 2023)            # EPG discount Oct 2022 - Jun 2023 (s30 fix)
    return {"value": real(tot * d + dom, y) * 1e6 / H, "domestic_share": d, "by_step": by_step,
            "basis": "estimated" if (epg or y not in share) else "modelled",
            "source_id": "dukes-5.2;dukes-5.5D;waterfall",
            "note": "EPG transfer not deducted (UNSOURCED amounts)" if epg else ""}
