"""RO mutualisation as a switch (cards [internal ticket], [internal ticket]). Richard ruled to count it (decision 0169, "a");
the switch stays OFF by default here because the release card [internal ticket] sets central defaults.

When suppliers fail and leave part of their RO obligation unpaid, Ofgem bills the shortfall to the
solvent suppliers in quarterly "mutualisation" payments and recycles it to the suppliers that presented
ROCs. Ofgem's "worth" of a ROC (buy-out price + recycle of the buy-out and late payment funds), which NZ2
uses, leaves the mutualisation recycle out ("Suppliers will receive a further mutualisation recycle value
once the mutualisation process for this compliance period is complete", RO annual reports 2017-18 to SY20).
So NZ2 counts what was paid in through ROCs, buy-out and late payments, and the mutualisation cash is
not inside it. The switch `ro_mutualisation` adds the GB mutualisation payments received, by the
scheme year they make good, to NZ2. 'off' is the default (v4-s39-rc unchanged).

Expected values are Ofgem's printed "Total received" cells (Appendix tables of the RO annual reports
2020-21, SY20, SY21, SY22, SY23), typed here from the reports, not from the engine.
"""
import hashlib
from dataclasses import replace

import pytest

from gascf import bills as B
from gascf import subsidies as s
from gascf.system_costs import domestic_share_cy

# {scheme start year: (RO England & Wales received £, ROS Scotland received £)}; NI is not mutualised.
RECEIVED = {
    2017: (53_344_913.39, 4_410_525.61),     # 2017-18 (SY16): 2020-21 report, Tables A2.1, A2.2
    2018: (87_900_731.62, 9_381_816.21),     # 2018-19 (SY17): 2020-21 report A2.3-A2.4; SY20 report A2.1-A2.2
    2019: (30_801_226.40, 1_745_150.56),     # 2019-20 (SY18): SY20 report A2.3-A2.4; SY21 report A2.1-A2.2
    2020: (204_771_724.69, 13_513_163.76),   # 2020-21 (SY19): SY21 report A2.3-A2.4; SY22 report A3.1-A3.2
    2021: (111_789_971.84, 7_878_317.75),    # 2021-22 (SY20): SY22 report A3.3-A3.4; SY23 report A3.1-A3.2
}


def test_reader_gives_ofgem_received_totals_by_scheme_year():
    m = s.read_ro_mutualisation()
    assert sorted(m) == sorted(RECEIVED)
    for y, (ro, ros) in RECEIVED.items():
        assert m[y]["ro_gbp"] == pytest.approx(ro, abs=0.005)
        assert m[y]["ros_gbp"] == pytest.approx(ros, abs=0.005)
        assert m[y]["gbp_m"] == pytest.approx((ro + ros) / 1e6, abs=1e-8)
    assert sum(v["gbp_m"] for v in m.values()) == pytest.approx(525.53754183, abs=1e-6)


# sha256 of each report as saved by the analyst's source check (card [internal ticket], 22 Oct 2026; SHA256SUMS in
# reports-programme-sources/reliable-britain/solr-ro-mutualisation/), typed here: the reader must use those files.
SAVED_SHA256 = {
    "2020-21": "aca93531796bafa72372d82ebcdaf2a7a7b5fd1d14281f1301f4d4191108be54",
    "SY20": "a82ac69bcd5a983dedbe7b664753bcb792c6baecc631b64bebd62f78066d234d",
    "SY21": "0041a34f8d6bfcd5cbbeea00a3c1dbb0d8d583fa4dd9a309435cb29b57093fa1",
    "SY22": "2c65d5388bcc0c0a665268a6467452ccedbede5bc1548ca8dd912936e145507a",
    "SY23": "2043fe4ab9dcac2102715f861325c3c386f92d767ef71e1bb9f02a86bd26e2ef",
}


def test_reader_reads_the_reports_saved_by_t_2eed4f2e():
    assert [p.name for p in s.RO_MUT_REPORTS] == [f"RO_annual_report_{n}.pdf" for n in SAVED_SHA256]
    for p, want in zip(s.RO_MUT_REPORTS, SAVED_SHA256.values()):
        assert hashlib.sha256(p.read_bytes()).hexdigest() == want


def test_ofgem_worth_used_by_nz2_is_the_pre_mutualisation_worth():
    # Guard against double counting: if Ofgem ever restates Figure A4.1 to include the mutualisation
    # recycle, these pins (each year's own report, before mutualisation) go red and the switch must go.
    a = s.read_ro_sy9_23()
    for y, worth in {2017: 51.43, 2018: 55.04, 2019: 54.43, 2020: 54.47, 2021: 58.24}.items():
        assert a[y]["worth"] == worth


def test_calendar_years_by_the_nz2_rule():
    cy = s.ro_mutualisation_cy()
    gb = {y: (ro + ros) / 1e6 for y, (ro, ros) in RECEIVED.items()}
    assert cy[2016] == 0.0 and cy[2023] == 0.0 and cy[2024] == 0.0 and cy[2025] == 0.0
    assert cy[2017] == pytest.approx(0.75 * gb[2017])
    assert cy[2020] == pytest.approx(0.25 * gb[2019] + 0.75 * gb[2020])
    assert cy[2022] == pytest.approx(0.25 * gb[2021])
    assert sum(cy.values()) == pytest.approx(525.53754183, abs=1e-6)


def test_switch_is_received_in_the_v4_s39_central():
    """0169 "a", set central by the release card [internal ticket]; 'off' (v4-s38) stays an explicit setting."""
    assert B.Settings().ro_mutualisation == "received"
    assert B.CENTRAL.ro_mutualisation == "received"


def test_switch_on_adds_the_payments_to_nz2_in_full_and_vat_on_the_domestic_share(monkeypatch, request):
    from pathlib import Path
    from gascf import fossil_like_for_like as L
    # the v4-s39 central (M2 closure test) needs the real register's closure_test data
    monkeypatch.setenv(L.CLOSURES_ENV, str(Path(__file__).resolve().parents[1] / "reference/fossil_closures.yaml"))
    # build/fleet_lfl caches are keyed on settings, not on the register: in the full suite B.build(CENTRAL) was
    # already cached on the fixture register, so clear them either side (card [internal ticket])
    from _pre_0133 import s39_caches
    for f in s39_caches():
        f.cache_clear()
    request.addfinalizer(lambda: [f.cache_clear() for f in s39_caches()])
    off = B.build(replace(B.CENTRAL, ro_mutualisation="off"))   # v4-s38 = explicit setting
    on = B.build(B.CENTRAL)
    cy = s.ro_mutualisation_cy()

    def line(run, y, i):
        return next(l for l in run[y]["netzero"] if l["id"] == i)["national_gbp_m_nominal"]

    dsh = domestic_share_cy()
    for y in B.YEARS:
        assert line(on, y, "NZ2") - line(off, y, "NZ2") == pytest.approx(cy[y], abs=1e-9)
        d = dsh.get(y, dsh[max(dsh)])
        dvat = line(on, y, "NZ11") - line(off, y, "NZ11")
        assert dvat == pytest.approx(0.05 * d * cy[y], abs=1e-9)
        assert on[y]["fossil"] == off[y]["fossil"]
        assert on[y]["totals"]["gap_gbp_m"] - off[y]["totals"]["gap_gbp_m"] == pytest.approx(
            cy[y] * (1 + 0.05 * d), abs=1e-9)
