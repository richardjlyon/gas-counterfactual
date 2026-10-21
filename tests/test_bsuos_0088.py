"""s36 ticket 03 (0088, Richard, B10 option a): NZ6 for calendar years 2017-2024 is the sum of
the NESO daily BSUoS files by settlement day's calendar year, not FY totals put on calendar years
by 1/4 : 3/4. Years before 2017 and 2025 keep the 1/4 : 3/4 rule. The generators' share comes off
each day at the share of that day's financial year. Plus B11: the FY2006/07 fallback record.

Seams (from the ticket's test list): `balancing.nz6` (public NZ6 by calendar year) and
`fallbacks.recorded()` after `bills.build()`."""
import json
from pathlib import Path

import pytest

from gascf import balancing as b

FIX = json.loads((Path(__file__).parent / "fixtures/clock_bsuos_raw_annual_e5b4c0f1.json").read_text())
CLOCK_RAW = {int(y): v / 1e6 for y, v in FIX["raw_annual_gbp"].items()}     # £m, Clock e5b4c0f1


@pytest.mark.parametrize("year", range(2017, 2025))
def test_nz6_raw_2017_24_equals_clock_daily_calendar_total(year):
    """Red 1: NZ6 before the generators' share = the Clock's daily calendar-year total, to £0.01m."""
    assert b.nz6(gen_share="included")[year]["gbp_m"] == pytest.approx(CLOCK_RAW[year], abs=0.01)


S35 = json.loads((Path(__file__).parents[1] / "out/v4/2026-10-14-s35.json").read_text())
S35_NZ6 = {int(y): next(l for l in v["netzero"] if l["id"] == "NZ6")["national_gbp_m_nominal"]
           for y, v in S35["bills"].items()}
# section-b-results.md B10: Clock raw minus engine raw (v4-s35), £m cash
B10_GAP = {2017: 24.8, 2018: -41.7, 2019: -82.6, 2020: 64.7, 2021: -145.6, 2022: 279.5, 2023: -39.3,
           2024: -155.0}


@pytest.mark.parametrize("year", range(2017, 2025))
def test_b10_gap_closed(year):
    """Red 2: the engine's raw NZ6 moves by exactly the B10 gap, so Clock minus engine is 0."""
    fy, gs = b.bsuos_fy(), {k: v["share"] for k, v in b.bsuos_gen_share_fy().items()}
    s35_raw = 0.25 * fy[year - 1]["gbp_m"] + 0.75 * fy[year]["gbp_m"]      # the v4-s35 1/4 : 3/4 rule
    s35_net = 0.25 * fy[year - 1]["gbp_m"] * (1 - gs[year - 1]) + 0.75 * fy[year]["gbp_m"] * (1 - gs[year])
    assert s35_net == pytest.approx(S35_NZ6[year], abs=1e-6)          # anchors s35_raw to the run file
    assert b.nz6(gen_share="included")[year]["gbp_m"] - s35_raw == pytest.approx(B10_GAP[year], abs=0.05)
    assert CLOCK_RAW[year] - b.nz6(gen_share="included")[year]["gbp_m"] == pytest.approx(0, abs=0.01)


# Independent sum (plain csv read, each day x (1 - share of its FY), shares from the CMP308 anchors
# by hand: FY2016 0.492, FY2017 0.49, FY2018 0.48333, FY2019 0.47667, FY2020-22 0.47, FY2023+ 0).
REMOVED = {2017: 630.9228, 2018: 672.7066, 2019: 776.0450, 2020: 1059.1010, 2021: 1574.2471,
           2022: 2426.0982, 2023: 2768.3063, 2024: 3038.5291}


@pytest.mark.parametrize("year", range(2017, 2025))
def test_generators_share_taken_off_each_day_at_its_fy_share(year):
    """Red 3: central NZ6 2017-24 = sum of days x (1 - generators' share of that day's FY)."""
    assert b.nz6()[year]["gbp_m"] == pytest.approx(REMOVED[year], abs=0.01)


@pytest.mark.parametrize("year", list(range(2002, 2017)) + [2025])
def test_nz6_outside_2017_24_unchanged_from_v4_s35(year):
    """Guards: 2002-2016 keep the 1/4 : 3/4 rule (and the baseline); 2025 keeps the FY2025/26
    partial-year estimate path (0088 covers 2017-24 only). Equal to the v4-s35 run file."""
    assert b.nz6()[year]["gbp_m"] == pytest.approx(S35_NZ6[year], abs=1e-9)
    if year == 2025:
        assert b.bsuos_fy()[2025]["source_id"] == "neso-bsuos-2025-26-rf-partial-scaled"


def test_b11_fy2006_fallback_recorded_like_fy2010():
    """B11: FY2006/07 (NG 2010 Table 1 IBC x the 2007/08 internal ratio, £593.1m) is listed in the
    fallback register the same way as FY2010/11. No value moves."""
    from gascf import bills as B
    from gascf import fallbacks as fb
    B.build()
    rec = {f["name"]: f for f in fb.recorded()}
    assert rec["bsuos-fy2006-ibc-grossup"]["year"] == 2006
    assert rec["bsuos-fy2006-ibc-grossup"]["size"] == pytest.approx(593.1, abs=0.05)
    assert "bsuos-fy2010-cpih-interpolation" in rec
