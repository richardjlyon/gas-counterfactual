"""Ticket 24 (0060): the household share counts supplier sales only (DUKES 2026 Table 5.2 domestic public
supply over Table 5.5.D UK electricity sales; self-used generation excluded), each year with its own
value and source id, and a guard on silent 2025 carry-forwards."""
import pytest

from gascf import fallbacks as FB
from gascf import system_costs as SC

SENTINEL = ("domestic-share-2025-carried", 1999)   # s36 B-merge fix 3: proves this module leaves the registry as found


@pytest.fixture
def fb_isolated():
    """s36 B-merge fix 3: an empty fallback registry for the test, the earlier records put back after it
    (FB.clear() alone wiped records that lru_cached recorders never make again, e.g. coal efficiency 2025)."""
    saved = dict(FB._REG)
    FB._REG.clear()
    yield
    FB._REG.clear()
    FB._REG.update(saved)


def test_00_a_record_made_before_this_module():
    FB.record(*SENTINEL, 0.0, "share", "isolation sentinel (removed by test_zz)")


def test_2024_and_2025_shares_are_each_years_own_dukes_2026_value_with_a_source_id():
    r = SC.domestic_share_records()
    assert r[2025]["value"] == pytest.approx(0.365458, abs=1e-6)
    assert r[2024]["value"] == pytest.approx(0.365434, abs=1e-6)
    for y in (2024, 2025):
        assert "dukes-2026-5.2" in r[y]["source_id"] and "dukes-2026-5.5D" in r[y]["source_id"]
        assert str(y) in r[y]["source_id"]
    assert {y: v["value"] for y, v in r.items()} == SC.domestic_share_cy()


NAME = "domestic-share-2025-carried"


def test_a_2025_copy_of_2024_without_a_fallback_record_raises(fb_isolated):
    with pytest.raises(FB.CarryForwardError, match=NAME):
        FB.require_recorded_carry_forward(NAME, {2024: 0.365434, 2025: 0.365434})
    with pytest.raises(FB.CarryForwardError, match=NAME):          # missing 2025 is a silent carry too
        FB.require_recorded_carry_forward(NAME, {2024: 0.365434})
    FB.require_recorded_carry_forward(NAME, {2024: 0.365434, 2025: 0.365458})   # own value: passes


def test_with_a_record_it_passes_and_is_listed_in_the_fallbacks(fb_isolated):
    FB.record(NAME, 2025, 0.365434, "share", "fixture")
    FB.require_recorded_carry_forward(NAME, {2024: 0.365434, 2025: 0.365434})
    assert (NAME, 2025) in {(f["name"], f["year"]) for f in FB.recorded()}


def test_build_refuses_a_silently_carried_2025_share_before_any_output(monkeypatch, fb_isolated):
    from gascf import bills as B
    carried = {**SC.domestic_share_cy(), 2025: SC.domestic_share_cy()[2024]}   # real series, 2025 silently = 2024
    monkeypatch.setattr(SC, "domestic_share_cy", lambda: carried)
    with pytest.raises(FB.CarryForwardError, match=NAME):
        B.build(B.replace(B.CENTRAL, margin="high"))     # a setting not built elsewhere in this session


def test_guards_run_on_every_build_call_even_for_a_setting_already_built(monkeypatch):
    """s36 B-merge cause 4: `bills.build` is lru_cached on Settings, so an input guard inside the cached body is
    skipped for any Settings built earlier in the process. The 0060 guard (and the 0069 one) must run every call."""
    from gascf import bills as B
    B.build(B.CENTRAL)                                     # built (or already cached) with the real share
    carried = {**SC.domestic_share_cy(), 2025: SC.domestic_share_cy()[2024]}
    monkeypatch.setattr(SC, "domestic_share_cy", lambda: carried)
    with pytest.raises(FB.CarryForwardError, match=NAME):
        B.build(B.CENTRAL)


def test_zz_the_record_made_before_this_module_survives_it():
    try:
        assert SENTINEL in {(f["name"], f["year"]) for f in FB.recorded()}
    finally:
        FB._REG.pop(SENTINEL, None)
