"""Ticket 02: tools/figures.py writes figures.json from declared key modules (tools/figures_keys/)."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402

RUN = {"meta": {"engine_version": "toy"}, "gap": {"2024": {"real_bn": 12.5}}}
META = {"label": "toy gap", "basis": "modelled", "provisional": False, "ticket": "02", "run_field": "gap.2024.real_bn"}


def _module(declared, values):
    m = types.ModuleType("toy_keys")
    m.DECLARED = declared
    m.values = values
    return m


def test_writes_the_declared_keys_with_their_meta(tmp_path):
    run = tmp_path / "run.json"
    run.write_text(json.dumps(RUN))
    out = tmp_path / "figures.json"
    mod = _module({"toy_gap_2024_gbp_bn": META}, lambda r: {"toy_gap_2024_gbp_bn": r["gap"]["2024"]["real_bn"]})
    F.write(run, out, modules=[mod])
    d = json.loads(out.read_text())
    assert d["keys"]["toy_gap_2024_gbp_bn"] == {"value": 12.5, "meta": META}
    assert d["meta"]["run_engine_version"] == "toy"


def test_refuses_a_value_for_an_undeclared_key():
    mod = _module({"toy_gap_2024_gbp_bn": META}, lambda r: {"toy_gap_2024_gbp_bn": 1.0, "stray_key": 2.0})
    with pytest.raises(KeyError, match="stray_key"):
        F.generate(RUN, modules=[mod])


@pytest.mark.parametrize("basis", [None, "guessed"])
def test_refuses_a_key_without_a_valid_meta_basis(basis):
    meta = {k: v for k, v in META.items() if k != "basis"} | ({"basis": basis} if basis else {})
    mod = _module({"toy_gap_2024_gbp_bn": meta}, lambda r: {"toy_gap_2024_gbp_bn": 1.0})
    with pytest.raises(ValueError, match="basis"):
        F.generate(RUN, modules=[mod])


def test_refuses_two_modules_declaring_the_same_key():
    a = _module({"toy_gap_2024_gbp_bn": META}, lambda r: {"toy_gap_2024_gbp_bn": 1.0})
    b = _module({"toy_gap_2024_gbp_bn": META}, lambda r: {"toy_gap_2024_gbp_bn": 2.0})
    with pytest.raises(KeyError, match="declared twice"):
        F.generate(RUN, modules=[a, b])
