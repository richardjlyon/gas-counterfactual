"""Decision 0110 item 1.19 (Richard Lyon, 19 Oct 2026): the 0058 shortfall-rule sensitivity is computed by option (b),
the narrowest: power's share of UK auction revenue 2013-20 = the 0055 power proxy (DESNZ GHG Table 1.2 power stations
less MSW) / UK verified emissions less free allocation (EEA Union Registry v82, the UK parts). A methods-page
sensitivity on the carbon split only: it never moves NZ1c, NZ8, the gap or the headline (0058)."""
import pytest

from gascf import carbon
from gascf import ets_auctions as E

# Option (b) shares measured for 0110 by the never-merged prototype (SIZES-2026-10-19.md, measure log
# 20261019T095203Z, prototype/[internal ticket]-size-options), a separate code path, 4 dp.
SIZES_B = {2013: 0.9085, 2014: 0.9047, 2015: 0.8616, 2016: 0.8211, 2017: 0.7768, 2018: 0.7785, 2019: 0.7529,
           2020: 0.7687}


def test_shortfall_share_option_b_matches_the_measured_shares():
    for y, v in SIZES_B.items():
        s = E.shortfall_share(y)
        assert s["value"] == pytest.approx(v, abs=5e-5), y
        assert s["rule"] == "0058 shortfall rule, option (b) (0110)"
        assert s["value"] > E.stand_in_share(y)["value"], y          # roughly doubles power's share (0058)
        assert s["numerator_mtco2"] == E.stand_in_share(y)["numerator_mtco2"], y
    with pytest.raises(ValueError):
        E.shortfall_share(2021)                                       # 2013-20 only


def test_shortfall_receipts_split_only_and_built_from_parts():
    from gascf.system_costs import gb_share_of_uk
    r, cpf, rev = carbon.shortfall_rule_receipts(), carbon.cpf_receipts(), E.uk_revenue_2013_20()
    central = carbon.ets_power_receipts()
    assert set(r) == set(range(2013, 2021))
    for y, row in r.items():
        want = cpf[y][0] + gb_share_of_uk(y)[0] * rev[y]["gbp_m"] * E.shortfall_share(y)["value"]
        assert row["tax_collected_gbp_m"] == pytest.approx(want, abs=1e-9), y
        central_tc = cpf[y][0] + gb_share_of_uk(y)[0] * central[y][0]
        assert row["central_tax_collected_gbp_m"] == pytest.approx(central_tc, abs=1e-9), y
        assert row["tax_collected_gbp_m"] >= central_tc - 1e-9, y   # 2019: no auctions, equal
    assert r[2019]["tax_collected_gbp_m"] == pytest.approx(r[2019]["central_tax_collected_gbp_m"], abs=1e-9)


def test_run_file_block_and_figures_key():
    import importlib
    import sys
    from pathlib import Path

    from gascf import deflator_cpih
    from gascf import export_v4 as X
    importlib.import_module("gascf.carbon_blocks")
    blk = X._BLOCKS["carbon_shortfall_rule"]({})
    assert blk["rule"] == "0058 shortfall rule, option (b) (0110)" and blk["in_headline"] is False
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.figures_keys import carbon_split as K
    run = {"meta": {"price_base": 2025, "deflator": "ONS CPIH L522"}, "carbon_shortfall_rule": blk}
    c = deflator_cpih.cpih()
    want = sum(deflator_cpih.to_real(blk["tax_collected_gbp_m"][str(y)], y, 2025) for y in range(2013, 2021))
    v = K.values(run)
    assert v["carbon_shortfall_rule_price_receipts_2013_20_gbp_bn"] == pytest.approx(want * c[2024] / c[2025] / 1e3,
                                                                                     rel=1e-12)
    lab = K.DECLARED["carbon_shortfall_rule_price_receipts_2013_20_gbp_bn"]["label"]
    assert "excludes the CCL at its main rates" in lab
    assert v["carbon_shortfall_rule_price_receipts_2013_20_gbp_bn"] > 0
    assert K.values({"meta": run["meta"]})["carbon_shortfall_rule_price_receipts_2013_20_gbp_bn"] is None
