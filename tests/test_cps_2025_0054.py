"""s36 ticket 21, decision 0054: 2025 Carbon Price Support about £428m (range £428-468m), provisional;
HMRC's printed £1,114.2m noted only."""
import pytest

from gascf import carbon


def test_cps_2025_three_figures_kept_apart():
    v, basis, src = carbon.cpf_receipts()[2025]
    assert v == 428.0 and basis == "estimated" and "provisional" in src
    rec = carbon.cps_2025_record()
    assert rec["status"] == "provisional" and rec["value"] == 428.0
    assert rec["cps_2025p_range_high_gbp_m"] == 468.0
    assert rec["cps_2025_hmrc_printed_gbp_m"] == pytest.approx(1114.248, abs=1e-3)
    assert "1,114.2" in rec["note"]


def _split():
    nz1c = {y: {"gbp_m": 5000.0, "basis": "modelled", "source_id": "toy-nz1c"} for y in range(2002, 2026)}
    return carbon.nz1c_split(nz1c)


def test_cps_2025_basis_note():
    t = _split()[2025]["carbon_price_receipts"]
    assert t["cps_gbp_m"] == 428.0 and t["cps_status"] == "provisional"
    assert t["cps_2025p_range_high_gbp_m"] == 468.0
    assert "HMRC's estimate" in t["cps_note"] and "note 5" in t["cps_note"] and "paid as one" in t["cps_note"]
    assert "cps_status" not in _split()[2024]["carbon_price_receipts"]


def test_ets_power_2025p_units_match_cps():
    t = _split()[2025]["carbon_price_receipts"]
    assert t["ets_money"] == t["cps_money"] == "cash"


def test_run_file_block_carries_the_2025_provisional_pair():
    import importlib

    from gascf import export_v4 as X
    importlib.import_module("gascf.carbon_blocks")
    b = X._BLOCKS["carbon_2025p"]({})
    assert b["cps_2025p_gbp_m"] == 428.0 and b["cps_2025p_range_high_gbp_m"] == 468.0
    assert b["ets_power_2025p_gbp_m"] == pytest.approx(900.03, abs=0.01)
    assert b["money"] == "cash" and b["status"] == "provisional"
    assert b["cps_2025_hmrc_printed_gbp_m"] == pytest.approx(1114.248, abs=1e-3)
    assert b["decisions"] == ["0054", "0079", "0078"]
