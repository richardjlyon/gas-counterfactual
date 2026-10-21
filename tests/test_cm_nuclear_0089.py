"""Decision 0089 (B13 option b) with Richard's variant D ruling (17 Oct 2026): nuclear counts in the
CM split at its CM obligation, post-trade, less any agreement the NESO CM register flags as suspended
for that whole delivery year. Reference: reports-programme b-items-calc/b13_nuclear_columns.py/.json."""
import hashlib

import pytest

from gascf import cm_contracted as cmc

FLAGS_SHA = "1247d8e8575caced62c15b03b5c732e791b4daf1860226c495fee059872d141e"
COLUMNS_SHA = "5cd7148cf16d61717b92541393255c4d6f2c886599133e1fb61d7c5e5b5cfcbd"


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_register_flags_extract_pinned_by_sha256():
    assert cmc.NUCLEAR_FLAGS_SHA256 == FLAGS_SHA
    assert _sha(cmc.NUCLEAR_FLAGS_CSV) == FLAGS_SHA


def test_nuclear_columns_file_pinned_by_sha256():
    assert cmc.NUCLEAR_DY_SHA256 == COLUMNS_SHA
    assert _sha(cmc.NUCLEAR_DY_CSV) == COLUMNS_SHA


def test_loaders_refuse_a_file_whose_checksum_does_not_match(tmp_path, monkeypatch):
    bad = tmp_path / "flags.csv"
    bad.write_bytes(cmc.NUCLEAR_FLAGS_CSV.read_bytes() + b"\n")
    monkeypatch.setattr(cmc, "NUCLEAR_FLAGS_CSV", bad)
    cmc.suspended_mw_by_dy.cache_clear(); cmc._suspended.cache_clear()
    with pytest.raises(ValueError, match="sha256"):
        cmc.suspended_mw_by_dy()
    cmc.suspended_mw_by_dy.cache_clear(); cmc._suspended.cache_clear()


def test_suspended_mw_by_delivery_year_from_the_register():
    # b13 suspended_mw_by_dy; whole DY; DNB kept (no flag) in DY2017/18 and DY2019/20
    s = cmc.suspended_mw_by_dy()
    assert s == pytest.approx({2018: 1385.257, 2020: 928.079, 2021: 940.995, 2022: 895.31, 2023: 426.671}, abs=1e-3)
    assert 2017 not in s and 2019 not in s


def test_hunterston_b_unit_7_dropped_in_dy2018_19():
    rows = cmc.suspended_agreements()
    assert ("HU7-14", 2018) in {(r["cmu"], r["dy"]) for r in rows}
    assert not any(r["dy"] in (2017, 2019) and r["unit"].startswith("Dungeness B") for r in rows)


def test_variant_d_is_the_default_column():
    from gascf import bills as B
    assert B.CENTRAL.nuclear_cm_column == "post_trade_less_suspended"
    assert set(cmc.NUCLEAR_COLUMNS) == {"auction_acquired", "post_trade_tw", "post_trade_ex_dungeness",
                                        "post_trade_less_suspended"}


def test_variant_d_calendar_mw_matches_b13():
    # b13 calendar_mw D_post_trade_less_suspended_mw; CY y = 0.75 DY(y-1) + 0.25 DY(y)
    want = {2017: 1969.591, 2018: 7531.487, 2019: 6507.426, 2020: 6655.436, 2021: 6741.499,
            2022: 5842.409, 2023: 5007.246, 2024: 4918.825, 2025: 4761.347}
    got = cmc.nuclear_contracted_cy_mw("post_trade_less_suspended")
    for y, v in want.items():
        assert got[y] == pytest.approx(v, abs=1e-3), y


def test_calendar_rule_is_three_quarters_previous_delivery_year():
    assert cmc.dy_to_cy({2023: 4000.0, 2024: 5000.0})[2024] == pytest.approx(4250.0)


def test_no_placeholder_rows_left_so_no_release_stop():
    assert cmc.nuclear_release_stops() == []


def test_cm_split_counts_contracted_nuclear_not_metered():
    from gascf import bills as B
    f = {"kept_derated_gw": 0.0, "existing_derated_gw": 10.0, "unlisted_firm_gw": 1.0,
         "new_derated_gw": 5.0, "firm_spare_derated_gw": 1.0, "derated_gw": 16.0}
    parts = B.kept_at_peak_parts(2024)
    metered = B.cm_split(f, 2024)
    d = B.cm_split(f, 2024, nuclear_column="post_trade_less_suspended")
    assert metered["kept_at_peak_gw"] == pytest.approx(parts["nuclear"] + parts["ps"] + parts["imports"])
    assert d["nuclear_contracted_gw"] == pytest.approx(4918.825 / 1e3, abs=1e-6)
    assert d["nuclear_at_peak_gw"] == pytest.approx(parts["nuclear"])
    assert d["kept_at_peak_gw"] == pytest.approx(4.918825 + parts["ps"] + parts["imports"], abs=1e-6)


def test_years_with_no_cm_delivery_year_unchanged():
    from gascf import bills as B
    f = {"existing_derated_gw": 10.0, "unlisted_firm_gw": 1.0, "derated_gw": 10.0}
    for y in (2005, 2010, 2015):
        assert B.cm_split(f, y, nuclear_column="post_trade_less_suspended") == B.cm_split(f, y) | {
            "nuclear_contracted_gw": None, "nuclear_at_peak_gw": B.kept_at_peak_parts(y)["nuclear"]}


# ---- heavy: full builds (one heavy job at a time; run after the baseline) ----
def _to_2024(v_nominal, y):
    from gascf import deflator_cpih as dfl
    cp = dfl.cpih()
    return v_nominal * cp[2024] / cp[y]


@pytest.fixture(scope="module")
def builds():
    from gascf import bills as B
    from dataclasses import replace
    return {c: B.build(replace(B.CENTRAL, nuclear_cm_column=c))
            for c in ("post_trade_less_suspended", "auction_acquired", "post_trade_ex_dungeness")}


def _nz5(b, y):
    return next(l["national_gbp_m_nominal"] for l in b[y]["netzero"] if l["id"] == "NZ5")


def test_variant_d_vs_auction_acquired_nz5_and_headline_2017_24(builds):
    # b13 totals D_post_trade_less_suspended_mw: dNZ5 127.528, dGap 129.956 (£m, 2024 prices)
    d, a = builds["post_trade_less_suspended"], builds["auction_acquired"]
    yrs = range(2017, 2025)
    dnz5 = sum(_to_2024(_nz5(d, y) - _nz5(a, y), y) for y in yrs)
    dgap = sum(_to_2024(d[y]["totals"]["gap_gbp_m"] - a[y]["totals"]["gap_gbp_m"], y) for y in yrs)
    assert dnz5 == pytest.approx(127.5, abs=0.5)
    assert dgap == pytest.approx(130.0, abs=0.5)


def test_variant_d_vs_ex_dungeness_headline_by_year(builds):
    # b13 D_vs_ex_dungeness per_year_d_gap_gbp_m_2024p
    d, x = builds["post_trade_less_suspended"], builds["post_trade_ex_dungeness"]
    want = {2017: -0.5, 2018: -7.6, 2019: 5.9, 2020: -5.3, 2021: 0.0, 2022: 0.0, 2023: 0.0, 2024: 0.0}
    for y, v in want.items():
        got = _to_2024(d[y]["totals"]["gap_gbp_m"] - x[y]["totals"]["gap_gbp_m"], y)
        assert got == pytest.approx(v, abs=0.05), y
