"""s30 (Richard, 12 Oct 2026): taxes are a cost to the payer, so no Treasury receipt is netted
off (the Electricity Generator Levy line is deleted) and VAT on households' share is counted;
GB costs over GB households throughout."""
import pytest

from gascf import bills as B
from gascf import households as hh
from gascf import system_costs as sc
from gascf import waterfall as W


@pytest.fixture(scope="module")
def central():
    return B.build()


def test_no_generator_levy_line(central):
    for y in (2023, 2024, 2025):
        ids = {l["id"] for l in central[y]["netzero"] + central[y]["fossil"]}
        assert "NZ9" not in ids
    assert "NZ9" not in B.NZ_IDS and not hasattr(B.CENTRAL, "egl_rule")


def test_vat_is_five_percent_of_household_share(central):
    d = sc.domestic_share_cy()
    for y in (2005, 2015, 2025):
        b = central[y]
        v = lambda i: B.val(b, i)                                     # noqa: E731
        nz = 0.05 * (d[y] * sum(v(i) for i in ("NZ1", "NZ2", "NZ3", "NZ4", "NZ4b", "NZ5", "NZ6", "NZ7")) + v("NZ10"))
        go = 0.05 * d[y] * sum(v(i) for i in ("GO1", "GO1k", "GO2", "GO3", "GO4", "GO5"))
        assert v("NZ11") == pytest.approx(nz) and v("GO7") == pytest.approx(go)
        st = {s["step"]: s for s in W.steps_for(b, y)}
        assert st[9]["value_gbp_m_nominal"] == pytest.approx(nz - go)
        assert abs(W.identity_error(W.steps_for(b, y))) < 0.01


def test_uk_only_lines_put_on_gb_basis(central):
    from gascf import subsidies as S
    for y in (2010, 2020):
        gb, _ = sc.gb_share_of_uk(y)
        o = central[y]["on_the_road"]
        # NZ2 (0097, ticket 26) and NZ8 (0044, ticket 12) are counted less their 2001 on-the-road parts;
        # the GB scaling (this test's subject) is unchanged, so add the netted-off parts back to check it.
        # v4-s39 (0169, card [internal ticket]): NZ2 also carries the GB RO mutualisation payments received (already GB).
        mut = S.ro_mutualisation_cy().get(y, 0.0)
        assert B.val(central[y], "NZ2") + o["nz2_on_the_road_gbp_m"] - mut == pytest.approx(S.ro()[y]["gbp_m"] * gb)
        assert B.val(central[y], "NZ8") + o["nz8_on_the_road_gbp_m"] + o["nz8_lec_exempt_gbp_m"] \
            == pytest.approx(S.ccl_electricity()[y]["gbp_m"] * gb)
        assert all(l["geo"] == "GB" for l in central[y]["netzero"] + central[y]["fossil"])


def test_one_household_count_everywhere(central):
    for y in (2002, 2014, 2015, 2024, 2025):
        assert central[y]["households"] == pytest.approx(hh.gb_households_count(y))
        assert central[y]["households"] == pytest.approx(sc.gb_households(y)[0])
