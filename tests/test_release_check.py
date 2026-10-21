"""Ticket 35 release check (written now in the serial tail, Richard 17 Oct 21:00 BST): on an s36 run file every
figures.json key must be non-None whatever its status; the release build refuses to write figures.json otherwise and
names each offending key. Outside release mode the assembly may still print None (the s35 run file, as now)."""
from __future__ import annotations

import json

import pytest

from tools import figures as F


def test_assert_complete_raises_and_names_every_none_key_whatever_its_status():
    figs = {"keys": {
        "ok_sourced": {"value": 1.0, "meta": {"status": "SOURCED"}},
        "none_pending": {"value": None, "meta": {"status": "PENDING"}},
        "none_nostatus": {"value": None, "meta": {}},
        "none_interim": {"value": None, "meta": {"status": "INTERIM_APPROVED"}},
    }}
    with pytest.raises(ValueError) as ei:
        F.assert_complete(figs)
    msg = str(ei.value)
    assert "none_pending" in msg and "none_nostatus" in msg and "none_interim" in msg
    assert "ok_sourced" not in msg


def test_release_write_refuses_a_none_key_and_writes_nothing(tmp_path):
    from tools.figures_keys import volume
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"meta": {"engine_version": "t"}}))          # no years block -> key is None
    out = tmp_path / "figs.json"
    with pytest.raises(ValueError, match="nuclear_ic_ps_net_twh_2024"):
        F.write(run, out, modules=[volume], release=True)
    assert not out.exists()
    # outside release mode the assembly still writes None, as now
    F.write(run, out, modules=[volume], release=False)
    assert json.loads(out.read_text())["keys"]["nuclear_ic_ps_net_twh_2024"]["value"] is None


def test_release_check_catches_a_partly_filled_block(tmp_path):
    from tools.figures_keys import balancing_factors
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"meta": {"engine_version": "t"},
                               "balancing_factors": {"bsuos_basis_grossup": {"value": 1.2}}}))
    out = tmp_path / "figs.json"
    with pytest.raises(ValueError, match="gb_over_ew_factor"):
        F.write(run, out, modules=[balancing_factors], release=True)
    assert not out.exists()


def test_release_build_refuses_a_none_key_and_names_it(tmp_path):
    """Condition 2 (R2-SP1a): the release path's figures step (gascf.release.write_figures) is gated with
    release=True, so a made-up run file with one None key is refused and the key is named; nothing is written."""
    from gascf import release as R
    from tools.figures_keys import volume
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"meta": {"engine_version": "t"}}))            # no years block -> key is None
    out = tmp_path / "figures.json"
    with pytest.raises(ValueError, match="nuclear_ic_ps_net_twh_2024"):
        R.write_figures(run, out, modules=[volume])
    assert not out.exists()


def test_release_build_writes_a_complete_file(tmp_path):
    """Condition 2 (R2-SP1a): on a complete made-up run file the release path writes figures.json."""
    from gascf import release as R
    from tools.figures_keys import volume
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"meta": {"engine_version": "t"},
                               "years": [{"year": 2024, "nuclear_ic_ps_net_twh": 123.0}]}))
    out = tmp_path / "figures.json"
    R.write_figures(run, out, modules=[volume])
    assert json.loads(out.read_text())["keys"]["nuclear_ic_ps_net_twh_2024"]["value"] == 123.0
