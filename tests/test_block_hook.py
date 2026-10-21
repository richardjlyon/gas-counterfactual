"""Ticket 02: the run-file block hook in export_v4.build_payload (fast: the heavy builders are stubbed)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gascf import export_v4 as X

S35 = Path(__file__).resolve().parents[1] / "out/v4/2026-10-14-s35.json"
STUBBED = ["_meta", "_years", "_bills", "_gap", "_fleet", "_all_new", "_firm", "_carbon_check", "_cm", "_sens",
           "_methods_page", "_answers", "provenance", "_tests"]


@pytest.fixture
def stubbed(monkeypatch):
    """build_payload with every builder replaced by a cheap stub; no blocks registered."""
    monkeypatch.setattr(X.B, "build", lambda *a, **k: {"built": True})
    monkeypatch.setattr(X.B, "ranges", lambda *a, **k: {})
    monkeypatch.setattr(X.W, "waterfall", lambda *a, **k: {y: {} for y in X.B.YEARS})
    monkeypatch.setattr(X.R, "bridge", lambda *a, **k: {y: {} for y in X.B.YEARS})
    monkeypatch.setattr(X.R, "clock_cm_correction", lambda *a, **k: {})
    for name in STUBBED:
        monkeypatch.setattr(X, name, lambda *a, **k: {})
    monkeypatch.setattr(X, "_BLOCKS", {})
    # s36 tickets 18, 25 and 28: real block modules are listed; keep the stub block-free
    monkeypatch.setattr(X, "BLOCK_MODULES", [])
    return X


def test_registered_block_appears_in_the_payload_under_its_name(stubbed):
    stubbed.register_block("toy_block", lambda built: {"seen": built["built"]})
    p = stubbed.build_payload("2026-10-17")
    assert p["toy_block"] == {"seen": True}


def test_a_block_may_not_replace_an_existing_run_file_key(stubbed):
    stubbed.register_block("gap", lambda built: {"x": 1})
    with pytest.raises(ValueError, match="gap"):
        stubbed.build_payload("2026-10-17")


def test_no_blocks_registered_keeps_the_v4_s35_structure_key_for_key(stubbed):
    """Fast check; the full byte check of a real run is ticket 34's."""
    p = stubbed.build_payload("2026-10-17")
    assert list(p) == list(json.loads(S35.read_text()))


def test_block_modules_listed_are_imported_so_their_blocks_register(stubbed, monkeypatch, tmp_path):
    pkg = tmp_path / "gascf_blocks_toy"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "toy.py").write_text("from gascf import export_v4 as X\nX.register_block('toy_mod_block', lambda b: 7)\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(stubbed, "BLOCK_MODULES", ["gascf_blocks_toy.toy"])
    assert stubbed.build_payload("2026-10-17")["toy_mod_block"] == 7
