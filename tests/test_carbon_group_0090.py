"""Ticket 37 (0090, option C): the carbon tax group renamed and split. CCL (NZ8) becomes its own group `ccl`;
the carbon tax collected on power (NZ1c_tax) becomes `carbon_price_receipts`; `carbon_in_price` is unchanged. The
old name `carbon_tax_collected` is removed everywhere (no alias). Layout only: no total or line value moves.
Tests first, b09 tests 1-3 and the CCL key-mapping rows."""
from __future__ import annotations

from dataclasses import replace

import pytest

from gascf import bills as B
from gascf import waterfall as W
from gascf import export_v4 as X


@pytest.fixture(scope="module")
def built():
    return B.build(B.CENTRAL)


def test_groups_split_ccl_out_of_carbon_price_receipts():
    assert "carbon_price_receipts" in B.GROUPS and "ccl" in B.GROUPS
    assert "carbon_tax_collected" not in B.GROUPS and "carbon_tax_collected" not in B.GROUPS_SINGLE_CARBON
    assert B.group_of("NZ8", B.CENTRAL) == "ccl"
    assert B.group_of("NZ1c_tax", B.CENTRAL) == "carbon_price_receipts"
    assert B.group_of("NZ1c_price", B.CENTRAL) == "carbon_in_price"
    # NZ8 is its own ccl group under both settings (0090); NZ1c_tax collapses into 'carbon' when not split
    single = replace(B.CENTRAL, carbon_split=False)
    assert B.group_of("NZ8", single) == "ccl"
    assert B.group_of("NZ1c_tax", single) == "carbon"


def test_labels_name_ccl_and_no_label_mixes_carbon_and_ccl():
    assert B.GROUP_LABELS["ccl"] == "Climate Change Levy"
    assert "carbon_tax_collected" not in B.GROUP_LABELS
    assert B.GROUP_LABELS["carbon_price_receipts"] == (
        "Carbon prices collected as tax (Carbon Price Support, carbon auctions on power)")
    assert B.GROUP_LABELS["carbon"] == "Carbon in the power price"
    for lab in B.GROUP_LABELS.values():
        low = lab.lower()
        assert not (("carbon" in low) and ("ccl" in low or "climate change levy" in low)), lab


def test_split_is_layout_only_no_total_or_line_moves(built):
    single = B.build(replace(B.CENTRAL, carbon_split=False))
    for y in B.YEARS:
        assert built[y]["totals"] == pytest.approx(single[y]["totals"], abs=1e-9), y
        a = {l["id"]: l["national_gbp_m_nominal"] for l in built[y]["netzero"] + built[y]["fossil"]}
        s = {l["id"]: l["national_gbp_m_nominal"] for l in single[y]["netzero"] + single[y]["fossil"]}
        assert a == pytest.approx(s, abs=1e-9), y


def test_line_groups_and_run_file_have_no_old_name(built):
    import json
    for y in B.YEARS:
        assert B.line(built[y], "NZ8")["group"] == "ccl", y
        assert B.line(built[y], "NZ1c_tax")["group"] == "carbon_price_receipts", y
        grp = X._groups(built[y], y)
        assert "carbon_tax_collected" not in json.dumps(grp), y
        assert grp["carbon_price_receipts"]["lines"] == ["NZ1c_tax"], y
        assert grp["ccl"]["lines"] == ["NZ8"], y
        # receipts + ccl equals the old combined group (NZ1c_tax + NZ8) every year, to the penny
        got = grp["carbon_price_receipts"]["national_gbp_m_nominal"] + grp["ccl"]["national_gbp_m_nominal"]
        assert got == pytest.approx(B.val(built[y], "NZ1c_tax") + B.val(built[y], "NZ8"), abs=1e-6), y


def test_step7_ccl_is_its_own_group(built):
    assert "ccl" in W.GROUP_ORDER_SPLIT and "ccl" in W.GROUP_ORDER
    assert "carbon_tax_collected" not in W.GROUP_ORDER_SPLIT
    for y in B.YEARS:
        g = W.grouped(W.steps_for(built[y], y))
        rows = {r["group"]: r for r in g}
        assert rows["carbon_price_receipts"]["lines"] == ["NZ1c_tax"], y
        assert rows["ccl"]["lines"] == ["NZ8"], y
        assert W.steps_for(built[y], y)
    # step 7's group is ccl, not the old combined name
    s7 = next(r for r in W.steps_for(built[2025], 2025) if r["step"] == 7)
    assert s7["group"] == "ccl"


def test_cps_stays_inside_carbon_price_receipts_not_ccl(built):
    # CPS is in law a CCL rate but stays in carbon_price_receipts (0022 split); no CPS amount moves to ccl
    for y in B.YEARS:
        cs = built[y]["carbon_split"]
        assert "carbon_price_receipts" in cs and "carbon_tax_collected" not in cs
        assert cs["carbon_price_receipts"]["id"] == "NZ1c_tax", y
