"""Decision 0102 (17 Oct 2026): the generators' 27% share stays on the whole stand-in GB base before
April 2005 (central, no engine change). The alternative, printed as a methods-page check and never in
the range: the 27% comes off NGC (England and Wales) only for FY2001/02-2004/05, nothing off SPT and
SHETL. Reference: reports-programme b-items-calc/b14_27pct_scot.py / .json, option (b), totals
`optb_cy2002_2005` on v4-s35 (2025 money): grid line +0.126 £m, NZ7 +270.07 £m, GO5 +269.94 £m."""
import pytest

from gascf import grid as g


def test_alternative_moves_the_gap_about_nil_over_2002_05():
    alt = g.scot_share_alt()
    assert alt["gap_effect_2002_05_gbp_m"] == pytest.approx(0.126, abs=0.01)


def test_alternative_shifts_nz7_and_go5_levels_about_270m_each():
    # 0102: "The levels of NZ7 and GO5 each move about £270m"; level_shift_gbp_m is NZ7's move
    alt = g.scot_share_alt()
    assert alt["level_shift_gbp_m"] == pytest.approx(270.07, abs=0.5)
    assert alt["level_shift_by_line_gbp_m"]["NZ7"] == alt["level_shift_gbp_m"]
    assert alt["level_shift_by_line_gbp_m"]["GO5"] == pytest.approx(269.94, abs=0.5)


def test_run_file_carries_the_check_as_its_own_block_not_in_the_range():
    import importlib

    from gascf import bills as B
    from gascf import export_v4 as X
    assert "gascf.grid_blocks" in X.BLOCK_MODULES
    importlib.import_module("gascf.grid_blocks")
    block = X._BLOCKS["scot_share_alt"]({})
    assert block["gap_effect_2002_05_gbp_m"] == pytest.approx(0.126, abs=0.01)
    assert block["level_shift_gbp_m"] == pytest.approx(270.07, abs=0.5)
    assert block["in_range"] is False and block["price_base"] == B.PRICE_BASE
    assert not any("scot" in n.lower() for n in list(B.SWITCHES) + list(B.METHOD_SWITCHES))
