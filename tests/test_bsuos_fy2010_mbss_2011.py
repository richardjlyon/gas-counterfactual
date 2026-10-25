"""NZ6 FY2010/11 from National Grid's March 2011 MBSS (input audit part D, card [internal ticket]; fix prepared on [internal ticket]).

Until v4-s41 the engine had no source for FY2010/11 and took the real-terms (CPIH) mean of FY2009/10 and FY2011/12
for the whole year: £851.41m nominal. The March 2011 MBSS (v2), section 9 "Summary of BSIS Costs", PDF p.27, column
"Year to Date Total Cost" (1 Apr 2010 to 31 Mar 2011), prints NIA -£273.3m and TOTAL (excl TLIC) £310.9m, so the
external cost before the Net Imbalance Adjustment is £584.2m. The issue prints no SO internal cost; that part alone
stays a CPIH interpolation of the neighbours' internal costs (FY2009/10 £99.6m, Ofgem TAR 2009-10; FY2011/12
£105.0m, MBSS March 2013 s10.3), labelled estimated and listed as a fallback.

Decision 0195 (Richard Lyon, 24 Oct 2026, "yes to all three"): basis (i), before NIA (£584.2m external, not £310.9m); the
internal cost interpolated, FY2010/11 £685.78m in all. The values below pin that option.

Expected values are literals from the printed source, not the engine's own output.
"""
import pytest

from gascf import balancing as b
from gascf import deflator_cpih as dfl

YTD_NIA = -273.3                      # MBSS March 2011 s9, 'NIA', Year to Date Total Cost
YTD_TOTAL_EXCL_TLIC = 310.9           # same column, 'TOTAL (excl TLIC)'
EXTERNAL_BEFORE_NIA = 584.2           # 310.9 - (-273.3)
INTERNAL_FY2009, INTERNAL_FY2011 = 99.6, 105.0   # TAR 2009-10; MBSS March 2013 s10.3 'Estimated Internal BSUoS'


def _internal_2010():
    c = dfl.cpih()
    return (INTERNAL_FY2009 / c[2009] + INTERNAL_FY2011 / c[2011]) / 2 * c[2010]


def test_mbss_march_2011_section9_read_from_the_saved_source():
    r = b.mbss_march_2011()
    assert r["nia"] == pytest.approx(YTD_NIA, abs=1e-9)
    assert r["total_excl_tlic"] == pytest.approx(YTD_TOTAL_EXCL_TLIC, abs=1e-9)
    assert r["external_before_nia"] == pytest.approx(EXTERNAL_BEFORE_NIA, abs=1e-9)


def test_fy2010_is_mbss_external_plus_interpolated_internal():
    row = b.bsuos_fy()[2010]
    assert row["gbp_m"] == pytest.approx(EXTERNAL_BEFORE_NIA + _internal_2010(), abs=1e-6)
    assert row["gbp_m"] == pytest.approx(685.8, abs=0.05)          # was 851.41 (interpolation of the whole year)
    assert row["basis"] == "estimated"                            # the internal part is still estimated
    assert row["source_id"] == "ng-mbss-march-2011-s9+internal-cpih-interpolation"


def test_fy2010_fallback_names_the_internal_part_only():
    from gascf import bills as B
    from gascf import fallbacks as fb
    B.build()
    rec = {f["name"]: f for f in fb.recorded()}
    assert "bsuos-fy2010-cpih-interpolation" not in rec
    assert rec["bsuos-fy2010-internal-cpih-interpolation"]["year"] == 2010
    assert rec["bsuos-fy2010-internal-cpih-interpolation"]["size"] == pytest.approx(_internal_2010(), abs=1e-6)
