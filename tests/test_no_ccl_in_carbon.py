"""Ticket 37 (0090): the standing fact-checker guard. No printed 'carbon' figure may include the CCL (NZ8), and
no figure named for the CCL may include a carbon line (NZ1c / NZ1c_tax / NZ1c_price). Checked from the declared
lines of every figures.json key and of the rows and columns of the five tables."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402

S35 = ROOT / "out/v4/2026-10-14-s35.json"


def _fig():
    return F.generate(json.loads(S35.read_text()))


def test_real_figures_pass_the_guard():
    from tools.checks import no_ccl_in_carbon as G
    assert G.audit(_fig()) == []


def test_carbon_named_key_including_nz8_is_flagged():
    from tools.checks import no_ccl_in_carbon as G
    bad = {"keys": {"carbon_x_gbp_bn": {"value": 1.0, "meta": {"label": "Carbon thing", "lines": ["NZ1c", "NZ8"]}}}}
    assert G.audit(bad)
    ok = {"keys": {"carbon_x_gbp_bn": {"value": 1.0, "meta": {"label": "Carbon thing", "lines": ["NZ1c"]}}}}
    assert G.audit(ok) == []


def test_ccl_named_key_including_a_carbon_line_is_flagged():
    from tools.checks import no_ccl_in_carbon as G
    bad = {"keys": {"ccl_x_gbp_bn": {"value": 1.0, "meta": {"label": "Climate Change Levy", "lines": ["NZ1c_tax"]}}}}
    assert G.audit(bad)
    ok = {"keys": {"ccl_x_gbp_bn": {"value": 1.0, "meta": {"label": "Climate Change Levy", "lines": ["NZ8"]}}}}
    assert G.audit(ok) == []


def test_waterfall_table_row_from_the_old_grouped_name_is_flagged():
    from tools.checks import no_ccl_in_carbon as G
    bad = {"keys": {"table_waterfall_2002_24": {"value": [
        {"key": "carbon_tax_collected", "label": "Carbon tax collected", "lines": ["NZ1c_tax", "NZ8"], "value": 1.0}]}}}
    assert G.audit(bad)


def test_carbon_rest_worked_out_with_nz8_is_flagged():
    # computing the rest as carbon_line less (receipts + NZ8) drags NZ8 into a carbon-named key
    from tools.checks import no_ccl_in_carbon as G
    bad = {"keys": {"carbon_rest_in_price_2002_24_gbp_bn": {
        "value": 32.017, "meta": {"label": "Carbon in the power price, the rest", "lines": ["NZ1c", "NZ1c_tax", "NZ8"]}}}}
    assert G.audit(bad)


def test_main_raises_on_a_bad_figures_file(tmp_path):
    from tools.checks import no_ccl_in_carbon as G
    p = tmp_path / "figures.json"
    p.write_text(json.dumps({"keys": {"carbon_x": {"value": 1.0, "meta": {"label": "Carbon", "lines": ["NZ8"]}}}}))
    with pytest.raises(SystemExit):
        G.main([str(p)])
