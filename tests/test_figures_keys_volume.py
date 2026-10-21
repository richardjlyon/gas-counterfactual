"""Ticket 46: the figures key nuclear_ic_ps_net_twh_2024 reads the run-file years field (never GO1k's rounded
years_note), and the old placeholder kept_output_twh_2024 is gone (EIC editorial ruling 17 Oct 2026, writer item 6)."""
from __future__ import annotations

import copy

import pytest

from tools import figures as F
from tools.figures_keys import volume


def _run(v=70.9842024, note="kept 71.0 TWh", with_field=True):
    row = {"year": 2024, "volume_twh": 261.8258865}
    if with_field:
        row["nuclear_ic_ps_net_twh"] = v
    return {"meta": {"engine_version": "test"},
            "years": [{"year": 2002, "nuclear_ic_ps_net_twh": 50.0}, row],
            "gap": {"go1k": {"years_note": note}}}


def test_nuclear_ic_ps_net_twh_2024_reads_the_run_field():
    k = F.generate(_run(), modules=[volume])["keys"]["nuclear_ic_ps_net_twh_2024"]
    assert k["value"] == 70.9842024
    m = k["meta"]
    assert m["run_field"] == "years[2024].nuclear_ic_ps_net_twh"
    assert m["units"] == "TWh" and m["basis"] == "modelled" and m["ticket"] == "46"
    assert m["provisional"] is True and m["status"] == "PENDING"
    assert "kept" not in m["label"].lower()


def test_never_parses_the_years_note():
    k = F.generate(_run(v=70.9842024, note="kept 99.9 TWh"), modules=[volume])["keys"]
    assert k["nuclear_ic_ps_net_twh_2024"]["value"] == 70.9842024


def test_without_the_field_is_none_never_the_note():
    # 46-48 ruling: a run whose 2024 row lacks the field gives None (never GO1k's note); release check stops on it
    k = F.generate(_run(with_field=False, note="kept 99.9 TWh"), modules=[volume])["keys"]
    assert k["nuclear_ic_ps_net_twh_2024"]["value"] is None


def test_without_the_years_block_is_none():
    # ruling for 46-48: the key prints None when its block is absent; the 35 release check stops on it
    r = {"meta": {"engine_version": "test"}}
    assert F.generate(r, modules=[volume])["keys"]["nuclear_ic_ps_net_twh_2024"]["value"] is None


def test_old_kept_output_key_is_gone():
    import importlib
    from tools import figures_keys
    for name in ("kept_output_twh_2024", "kept_nuclear_ic_ps_twh_2024"):
        for mod in figures_keys.MODULES:
            m = importlib.import_module(f"tools.figures_keys.{mod}")
            assert name not in getattr(m, "DECLARED", {})
    # and no declared key reading nuclear_ic_ps_net_twh keeps "kept" in its name
    for name, meta in volume.DECLARED.items():
        if "nuclear_ic_ps_net_twh" in meta.get("run_field", ""):
            assert "kept" not in name
