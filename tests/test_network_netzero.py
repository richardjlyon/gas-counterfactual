"""network_netzero: the RIIO-3 transmission step-up Ofgem attributes to net zero (s11).

Spot values are Ofgem RIIO-3 Final Determinations Impact Assessment, Table 3 "Profiling
effects", read by eye from the stored PDF when written.
"""
import pytest

from gascf import network_netzero as nn
from gascf.deflator import read_deflator


def test_table3_spot_values():
    et = nn.read_et_charges()
    assert et.years == (2025, 2026, 2027, 2028, 2029, 2030)
    assert et.pre_profiling == {2025: 44, 2026: 68, 2027: 83, 2028: 95, 2029: 100, 2030: 104}
    assert et.profiling == {2025: 0, 2026: -3, 2027: 0, 2028: 1, 2029: 1, 2030: 1}


def test_table3_reconciles_with_table2():
    """Table 2 (2030/31, pre-profiling): ET today 44, under RIIO-3 104, total network 222 -> 330."""
    t = nn._text(nn.IA)
    assert "Today's charges (using average 25/26 price cap prices) 44 165 13 222" in t
    assert "2030/31 charges under RIIO-3 recommendations 104 209 16 330" in t
    et = nn.read_et_charges()
    assert et.pre_profiling[2025] == 44 and et.pre_profiling[2030] == 104


def test_quotes_present_in_stored_documents():
    assert all(nn.check_quotes().values()), nn.check_quotes()


def test_bracket_2026_27():
    g = nn.grid_netzero_per_household(2026)
    assert g.low == 0
    assert g.high == pytest.approx(65 - 44)            # 2025/26 prices, after profiling
    assert g.basis == "estimated" and g.source_id == nn.SRC_IA
    idx = read_deflator()[0]
    g26 = nn.grid_netzero_per_household(2026, price_year=2026)
    assert g26.high == pytest.approx(21 * idx[2026] / (0.75 * idx[2025] + 0.25 * idx[2026]))
    assert g.pick("low") == 0 and g.pick("high") == g.high
    with pytest.raises(ValueError):
        g.pick("mid")


def test_before_riio3_is_null_with_reason():
    g = nn.grid_netzero_per_household(2025)
    assert g.low is None and g.high is None
    assert g.basis == "UNSOURCED" and "UNSOURCED" in g.note


def test_after_table_raises():
    with pytest.raises(KeyError):
        nn.grid_netzero_per_household(2031)
