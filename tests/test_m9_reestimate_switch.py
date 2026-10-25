"""Card [internal ticket] (MEASURE ONLY): the 2021-23 wind/solar price effect from the M9 re-estimate, as a
switch, default OFF. Richard Lyon, 21 Oct 2026 (live, relayed on the card): "The number has to be accurate."
Two ways of applying it are measured; Richard chooses. Expected values are literals from the back-test's
own run log (branch modeller/[internal ticket]-m9-backtest at 4182bf7, run-20261021T160841Z.log, sha256 ed6ec398...f943e).

Rules (Settings.moe_crisis):
  'm9_ratio'        (A) the engine's 2021-23 Shao uplift x R, every month of 2021-23
  'm9_ratio_mayon'  (A) the same, but Jan-Apr 2021 (outside the test window) keeps Shao
  'm9_direct'       (B) the uplift's time-mean = 4.0853 x wind GW + 5.6857 x solar GW, every month of 2021-23
  'm9_direct_mayon' (B) the same, but Jan-Apr 2021 keeps Shao
"""
import pytest

from gascf import moe_crisis as MC


def test_window_figures_are_read_from_the_backtest_run_log():
    m = MC.m9_window()
    assert m["wind"] == -4.0853
    assert m["solar"] == -5.6857
    assert m["R"] == 2.8159
    assert (m["R_lo"], m["R_hi"]) == (2.2445, 3.3874)
    assert m["log_sha256"].startswith("ed6ec398") and m["log_sha256"].endswith("f943e")


def test_switch_is_m9_b_in_the_v4_s39_central_and_shao_is_an_explicit_setting():
    """v4-s39 (0164 addendum, "b"; card [internal ticket]): the central is M9 B; 'shao' (v4-s38) stays an explicit setting."""
    from gascf import bills as B
    assert B.CENTRAL.moe_crisis == "m9_direct_mayon"
    assert all(MC.k_months("shao", y, 15.0, 8.0, 1.5) == {m: 1.0 for m in range(1, 13)} for y in (2021, 2022, 2023))


def test_ratio_rule_multiplies_every_crisis_month_by_r():
    for y in (2021, 2022, 2023):
        assert MC.k_months("m9_ratio", y, 15.0, 8.0, 1.5) == {m: 2.8159 for m in range(1, 13)}
    for y in (2020, 2024):
        assert MC.k_months("m9_ratio", y, 15.0, 8.0, 1.5) == {m: 1.0 for m in range(1, 13)}


def test_direct_rule_reproduces_the_logs_window_uplift_ratio():
    # The log prints, on the window means (8.4188 GW wind, 1.4961 GW solar): re-estimated 42.90 £/MWh,
    # from Shao's 1.28/2.98 15.23 £/MWh. With the engine's mean set to Shao's, k must be 42.90 / 15.23.
    w, s = 8.4188, 1.4961
    k = MC.k_months("m9_direct", 2022, 1.28 * w + 2.98 * s, w, s)
    assert k[6] == pytest.approx(42.90 / 15.23, abs=2e-3)
    assert len(set(k.values())) == 1


@pytest.mark.parametrize("rule", ["m9_ratio_mayon", "m9_direct_mayon"])
def test_mayon_rules_leave_jan_to_apr_2021_on_shao(rule):
    k = MC.k_months(rule, 2021, 15.0, 8.0, 1.5)
    assert [k[m] for m in (1, 2, 3, 4)] == [1.0] * 4
    assert all(k[m] > 2.0 for m in range(5, 13))
    assert MC.k_months(rule, 2022, 15.0, 8.0, 1.5) == MC.k_months(rule.replace("_mayon", ""), 2022, 15.0, 8.0, 1.5)


def test_unknown_rule_raises():
    with pytest.raises(ValueError):
        MC.k_months("m9_typo", 2022, 15.0, 8.0, 1.5)
