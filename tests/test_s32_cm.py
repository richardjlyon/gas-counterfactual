"""s32: the Capacity Market rule (spec §5.4 rewritten). NZ5 = CM paid less Reliable Britain's
notional CM, priced only on the firm capacity whose fixed cost GO1 does NOT already carry: new
plant, the firm spare and kept-open coal are excluded (s32 roast, Finding 1)."""
import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from gascf import bills as B
from gascf import bridge as R
from gascf import household_bill as HB

CM_YEARS = range(2016, 2026)
ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def central():
    return B.build()


@pytest.fixture(scope="module")
def low():
    return B.build(B.replace(B.CENTRAL, cm_rule="extra_kept_coal"))


@pytest.fixture(scope="module")
def high():
    return B.build(B.replace(B.CENTRAL, cm_rule="full"))


def test_rule_excludes_new_spare_and_kept_coal(central):
    """The GW priced at Reliable Britain's CM = its whole firm capacity less new plant, the firm
    spare and kept coal; NZ5 = CM paid − price × that GW (floored at zero)."""
    for y in CM_YEARS:
        b = central[y]
        c, f, sp = b["cm"], b["fleet"], b["cm"]["split_gw"]
        assert sp["new_gw"] == pytest.approx(f["new_derated_gw"])
        assert sp["firm_spare_gw"] == pytest.approx(f["firm_spare_derated_gw"])
        assert sp["kept_coal_gw"] == pytest.approx(f["kept_derated_gw"])
        assert sp["go1_paid_gw"] == pytest.approx(sp["new_gw"] + sp["firm_spare_gw"] + sp["kept_coal_gw"])
        # the whole firm capacity (the old, double-counting base) less what GO1 pays for
        assert c["cm_gw"] == pytest.approx(c["fossil_firm_gw"] - sp["go1_paid_gw"])
        assert c["cm_gw"] == pytest.approx(sp["existing_unkept_gw"] + sp["unlisted_gw"] + sp["kept_at_peak_gw"])
        assert c["fossil_gbp_m"] == pytest.approx(c["price_gbp_kw_yr"] * c["cm_gw"])
        assert B.val(b, "NZ5") == pytest.approx(max(0.0, c["paid_gbp_m"] - c["fossil_gbp_m"]))
    # kept coal is real capacity in these years (else the exclusion is vacuous)
    assert central[2025]["cm"]["split_gw"]["kept_coal_gw"] > 1.0


def test_kept_coal_derated_with_the_engines_own_factor(central):
    from gascf import capacity
    der = capacity.read_derating()
    for y in CM_YEARS:
        k = central[y]["fleet"]["kept_gw"]
        want = (k.get("coal", 0) + k.get("ccgt", 0)) * der["ccgt"] + (k.get("other_gas", 0) + k.get("oil", 0)) * der["ocgt"]
        assert central[y]["fleet"]["kept_derated_gw"] == pytest.approx(want)


def test_unfloored_nz5_is_exported_and_floor_reported(central):
    for y in CM_YEARS:
        c = central[y]["cm"]
        assert c["nz5_unfloored_gbp_m"] == pytest.approx(c["paid_gbp_m"] - c["fossil_gbp_m"])
        assert B.val(central[y], "NZ5") == pytest.approx(max(0.0, c["nz5_unfloored_gbp_m"]))
        assert c["nz5_floored"] == (c["nz5_unfloored_gbp_m"] < 0)
        if c["nz5_floored"]:
            assert "floored at 0" in B.line(central[y], "NZ5")["note"]


def test_low_and_high_switches(central, low, high):
    """§11: low = kept coal needs CM too; high = the full CM. Both are in the range switches."""
    sw = B.SWITCHES["capacity market (kept coal in CM / full CM)"]
    assert [s.cm_rule for s in sw] == ["extra_kept_coal", "full"]
    for y in CM_YEARS:
        c, lo = central[y]["cm"], low[y]["cm"]
        assert lo["cm_gw"] == pytest.approx(c["cm_gw"] + c["split_gw"]["kept_coal_gw"])
        assert B.val(low[y], "NZ5") <= B.val(central[y], "NZ5") + 1e-9
        assert B.val(high[y], "NZ5") == pytest.approx(c["paid_gbp_m"])
        assert B.val(central[y], "NZ5") <= c["paid_gbp_m"] + 1e-9
    for y in range(2002, 2016):
        assert B.val(central[y], "NZ5") == 0 == central[y]["cm"]["paid_gbp_m"]


def test_2016_2017_price_is_the_main_auction_clearing_price(central):
    """Finding 7: in 2016-17 paid ÷ obligation (0.2 / 14.2 GW) is an artefact. The price is the
    T-1 Early Auction clearing price (£6.95/kW/yr, Ofgem CM AR 2025/26 Table 4) × months it
    delivered ÷ 12: none in 2016, Oct-Dec in 2017. From 2018 the average £/kW is used."""
    e = B.cm_early_price()
    assert e[2016]["gbp_kw_yr"] == 0.0 and e[2016]["auctions"] == [] and e[2016]["tr_auctions"] == ["TR-2016"]
    assert e[2017]["auctions"] == ["T-1-2017"] and e[2017]["months"] == [10, 11, 12]
    assert e[2017]["gbp_kw_yr"] == pytest.approx(6.95 * 3 / 12)
    for y in (2016, 2017):
        assert central[y]["cm"]["price_gbp_kw_yr"] == pytest.approx(e[y]["gbp_kw_yr"])
        assert B.SRC_CM_EARLY in B.line(central[y], "NZ5")["source_ids"]
    q = B.cm_obligation_mw_year()
    for y in range(2018, 2026):
        c = central[y]["cm"]
        assert c["price_gbp_kw_yr"] == pytest.approx(c["paid_gbp_m"] / q[y] * 1000)


def test_clock_correction_covers_engine_years_only():
    cc = R.clock_cm_correction()
    assert min(y for y in cc if cc[y]["nz5_gbp_m"] is not None) == 2016
    assert cc[2026]["nz5_gbp_m"] is None and cc[2026]["status"].startswith("not covered")
    assert cc[2026]["clock_cm_gbp_m"] == pytest.approx(1225.03, abs=0.01)
    for y in CM_YEARS:
        assert cc[y]["correction_gbp_m"] == pytest.approx(cc[y]["nz5_gbp_m"] - cc[y]["clock_cm_gbp_m"])
        assert cc[y]["nz5_low_gbp_m"] <= cc[y]["nz5_gbp_m"] <= cc[y]["nz5_high_gbp_m"] + 1e-9


def test_bridge_row_b_uses_the_new_nz5(central):
    br, clock = R.bridge(), R.read_clock()
    for y in CM_YEARS:
        rb = next(r for r in br[y]["rows"] if r["row"] == "B")
        assert rb["gbp_m_nominal"] == pytest.approx(B.val(central[y], "NZ5") - (clock[y]["capacity_market"] or 0.0))
        assert abs(br[y]["error"]) < 0.01


def test_household_cm_line_is_reliable_britains_notional_share(central):
    """The cap's CM line is no longer the same in both: Reliable Britain's = cap line × (notional
    RB CM / CM paid); Pot 1 gains the rest."""
    for y in range(2019, 2026):
        c = central[y]["cm"]
        rt = HB.ratios(y)
        assert rt["cm"] == pytest.approx(min(1.0, c["fossil_gbp_m"] / c["paid_gbp_m"]))
        assert rt["cm"] == pytest.approx(1 - B.val(central[y], "NZ5") / c["paid_gbp_m"])
    t = HB.typical_year(2025)
    row = next(r for r in t["rows"] if r["key"] == "capacity_market")
    p1 = {l["id"]: l["value"] for l in HB.pot1(t)}
    assert row["treatment"] == "cm"
    assert row["reliable"] == pytest.approx(row["netzero"] * HB.ratios(2025)["cm"])
    assert row["reliable"] < row["netzero"]
    assert p1["capacity_market"] == pytest.approx(row["netzero"] - row["reliable"])
    assert p1["capacity_market"] > 0


@lru_cache(maxsize=1)
def _real_register_2025() -> dict:
    """NZ5 2025 on the real closure register (the run behind out/v4), in a separate interpreter:
    this session runs on the conftest fixture register."""
    code = ("import json; from gascf import bills as B; "
            "b = B.build()[2025]; lo = B.build(B.replace(B.CENTRAL, cm_rule='extra_kept_coal'))[2025]; "
            "print(json.dumps({'nz5': B.val(b, 'NZ5'), 'low': B.val(lo, 'NZ5'), 'gw': b['cm']['cm_gw'], "
            "'kept': b['cm']['split_gw']['kept_coal_gw'], 'price': b['cm']['price_gbp_kw_yr']}))")
    env = {k: v for k, v in os.environ.items() if k != "GASCF_FOSSIL_CLOSURES"}
    r = subprocess.run([sys.executable, "-W", "ignore", "-c", code], env=env, cwd=ROOT, capture_output=True,
                       text=True, timeout=1800)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_nz5_2025_value_on_the_real_register():
    """Re-pinned for s36 (ticket 17, group B, 17 Oct 2026) from the build on wt/B (subprocess on the
    real register, this function's own code): contracted interconnectors (0057, ticket 15) and
    variant D contracted nuclear (0089, ticket 17) raise the GW priced at Reliable Britain's CM from
    38.21 to 46.21, so central NZ5 2025 moves £396.3m -> £179.6m and the low side (kept coal needs CM)
    £141.4m -> £0.0m (floored). Price £27.09/kW and kept coal 9.41 GW unchanged. v4-s35 values
    (roast Finding 1: £396m; low ≈ £0.14bn) are kept here for the record only.

    Re-pinned 19 Oct 2026 (card [internal ticket]) for decision 0110 item 1.8 (Richard Lyon: option (b), the actual system's
    own firm test on the same basis as RB's under contracted interconnectors). The unlisted firm plant falls, so the
    GW priced at RB's CM goes 46.21 -> 44.98 and central NZ5 2025 £179.6m -> £212.8m. The NZ5 value equals the
    prototype measurement behind 0110 (SIZES-2026-10-19.md, 212.775, a separate code path) to the last digit.
    Price, kept coal and the floored low side unchanged.

    Re-pinned 20 Oct 2026 (card [internal ticket]) for decision 0133 (Richard Lyon, "a": the margin over the 2027/28 peak,
    7.4% not 7.0%): RB sizes more spare plant, so the GW priced at RB's CM goes 44.98 -> 45.12 and central NZ5 2025
    £212.8m -> £209.1m (work/s36/repin_0133.py, this function). Price, kept coal and the low side unchanged; the
    0110 prototype figure (212.775) is the pre-0133 build, held in test_ic_contracted_0057 on the old margin.

    Re-pinned 20 Oct 2026 (card [internal ticket]) for decision 0144 item 6 (Richard Lyon, "Yes, take all the
    recommendations"; v4-s37): Cottam is `mixed` and closes on its real date, so RB keeps less coal open in 2025:
    kept coal 9.41 -> 7.60 GW, and the low side (kept coal needs CM) is no longer floored: £0.0m -> £3.16m
    (work/s37/repin_0144.py, this function's own code). Central NZ5 (£209.1m), the GW priced (45.12) and the price
    are unchanged: Reliable Britain's own firm capacity is met by new plant in Cottam's place."""
    d = _real_register_2025()
    assert d["price"] == pytest.approx(27.09, abs=0.01)
    assert d["gw"] == pytest.approx(45.12, abs=0.01)
    assert d["kept"] == pytest.approx(7.60, abs=0.01)                 # 9.41 before 0144 (Cottam)
    assert d["nz5"] == pytest.approx(209.095, abs=0.5)
    assert d["low"] == pytest.approx(3.164, abs=0.5)                  # 0.0 (floored) before 0144 (Cottam)
