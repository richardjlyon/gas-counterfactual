"""Ticket 48: the rb.balancing.* figures keys read the run-file balancing_factors block. bsuos_basis_grossup_factor
(1 + internal ÷ external, 2007/08) prints bare to 3 dp (1.198); its sibling gb_over_ew_factor (GB over E&W demand,
2002-05 mean) prints bare to 4 dp (1.1086). Both modelled, PENDING; block missing gives None (46-48 ruling)."""
from __future__ import annotations

import pytest

from tools import figures as F
from tools.figures_keys import balancing_factors

BSUOS, GBEW = 1.1981574098, 1.108625924


def _run(with_block=True):
    r = {"meta": {"engine_version": "t"}}
    if with_block:
        r["balancing_factors"] = {"bsuos_basis_grossup": {"value": BSUOS},
                                  "gb_over_ew": {"value": GBEW, "by_year": {}, "inputs": []}}
    return r


def _keys(run=None):
    return F.generate(run or _run(), modules=[balancing_factors])["keys"]


def test_rb_balancing_bsuos_basis_grossup_factor_reads_the_run_block():
    k = _keys()
    e = k["rb.balancing.bsuos_basis_grossup_factor"]
    assert e["value"] == BSUOS
    m = e["meta"]
    assert m["basis"] == "modelled" and m["ticket"] == "48" and m["units"] == "ratio" and m["fy"] == "2007/08"
    assert m["run_field"] == "balancing_factors.bsuos_basis_grossup.value"
    assert m["was_claims_id"] == "CR-S048" and m["print_dp"] == 3 and m["print_prefix"] == ""
    assert m["provisional"] is True and m["status"] == "PENDING"
    assert "1 + internal" in m["label"] and "internal ÷ external" in m["label"]
    assert any("Not the GB gross-up" in n for n in m["notes"])
    assert any("TAR 2008-09" in s and "Table 22" in s and "p.38" in s for s in m["sources"])
    assert any("tar_2008_09_t22_balancing_internal_2007_08" in s for s in m["sources"])


def test_no_figures_key_for_either_table22_input():
    for name in balancing_factors.DECLARED:
        assert "balancing_external" not in name and "balancing_internal" not in name


def test_block_missing_gives_none():
    k = _keys(_run(with_block=False))
    for name in balancing_factors.DECLARED:
        assert k[name]["value"] is None


def test_rb_balancing_gb_over_ew_factor_reads_the_run_block():
    k = _keys()
    e = k["rb.balancing.gb_over_ew_factor"]
    assert e["value"] == GBEW
    m = e["meta"]
    assert m["basis"] == "modelled" and m["ticket"] == "48" and m["units"] == "ratio"
    assert m["period"] == "2002-2005" and m["year_basis"] == "calendar"
    assert m["run_field"] == "balancing_factors.gb_over_ew.value" and m["was_claims_id"] == "CR-S049"
    assert "GB demand over England and Wales demand" in m["label"]
    assert any("Not the internal-cost gross-up" in n for n in m["notes"])
    assert any("Historic Demand Data" in s for s in m["sources"])


def test_bsuos_prints_bare_to_3_dp_and_gb_over_ew_to_4_dp():
    k = _keys()
    b = k["rb.balancing.bsuos_basis_grossup_factor"]
    g = k["rb.balancing.gb_over_ew_factor"]
    assert b["meta"]["print_dp"] == 3 and g["meta"]["print_dp"] == 4      # the two siblings differ
    assert b["value"] != round(b["value"], 3) and g["value"] != round(g["value"], 4)
    bfill = f"{b['meta']['print_prefix']}{round(b['value'], 3):.3f}"
    gfill = f"{g['meta']['print_prefix']}{round(g['value'], 4):.4f}"
    assert bfill == "1.198" and gfill == "1.1086"
    for e in (b, g):
        assert "about" not in e["meta"]["label"].lower()
        assert all("about" not in n.lower() for n in e["meta"].get("notes", []))
