"""model-release step 5: the rerun command (gascf.rerun). Light: the engine build and the figures writer are stubbed;
the comparison, the byte form of the run file, the row lookup and the PASS/FAIL line are real."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from gascf import rerun as R

PAYLOAD = {"meta": {"engine_version": "v4-s99", "run_date": "2026-10-19"}, "gap": {"2024": 1.5}}


def _figs(run: dict) -> dict:
    return {"meta": {"version": "v4-s99"}, "keys": {"headline": {"value": run["gap"]["2024"] * 100},
                                                     "label_only": {"value": "text"}}}


def _fw(rp, op, commit):
    Path(op).write_text(json.dumps(_figs(json.loads(Path(rp).read_text())) | {"commit": commit}, indent=1))


def _release(tmp_path: Path, payload=PAYLOAD, test_suite=True) -> tuple[Path, Path]:
    """A source root with releases.yaml and a bundle with the released run file and figures.json, written as the
    export and the cut write them."""
    root, bundle = tmp_path / "source", tmp_path / "bundle"
    root.mkdir(), bundle.mkdir()
    meta = dict(payload["meta"]) | ({"test_suite": {"passed": 3, "failed": 0}} if test_suite else {})
    run_b = R.run_bytes(payload, meta)
    (bundle / "2026-10-19-s99.json").write_bytes(run_b)
    _fw(bundle / "2026-10-19-s99.json", bundle / "figures.json", "c0ffee")
    row = {"version": "v4-s99", "commit": "c0ffee", "run_file": "out/v4/2026-10-19-s99.json",
           "run_sha256": hashlib.sha256(run_b).hexdigest(), "figures_file": "out/figures/v4-s99.json",
           "figures_sha256": hashlib.sha256((bundle / "figures.json").read_bytes()).hexdigest()}
    (root / "releases.yaml").write_text(json.dumps({"releases": [row]}))
    return root, bundle


def test_identical_rebuild_passes(tmp_path, capsys, monkeypatch):
    root, bundle = _release(tmp_path)
    assert R.rerun("v4-s99", root=root, bundle=bundle, scratch=tmp_path / "s", build=lambda d: PAYLOAD,
                   figures_write=_fw) == []


def test_run_bytes_match_the_cut_form_with_and_without_the_suite_record():
    plain = R.run_bytes(PAYLOAD, PAYLOAD["meta"])
    assert plain == json.dumps(PAYLOAD, indent=1, default=str, allow_nan=False).encode()
    cut = R.run_bytes(PAYLOAD, PAYLOAD["meta"] | {"test_suite": {"passed": 3}})
    want = json.loads(plain)
    want["meta"]["test_suite"] = {"passed": 3}
    assert cut == json.dumps(want, indent=1, allow_nan=False).encode()


def test_a_moved_figure_fails_and_is_named(tmp_path):
    root, bundle = _release(tmp_path)
    moved = json.loads(json.dumps(PAYLOAD))
    moved["gap"]["2024"] = 1.5000001
    m = R.rerun("v4-s99", root=root, bundle=bundle, scratch=tmp_path / "s", build=lambda d: moved, figures_write=_fw)
    assert any(x.startswith("run file sha256 differs") for x in m)
    assert any(x.startswith("figures key differs: headline") for x in m)
    assert any(x.startswith("figures.json sha256 differs") for x in m)


def test_tolerance_and_key_sets():
    old = {"keys": {"a": {"value": 1.0}, "b": {"value": [1, 2.0]}, "c": {"value": True}}}
    assert R.compare_figures({"keys": {"a": {"value": 1.0 + 1e-12}, "b": {"value": [1, 2.0]},
                                       "c": {"value": True}}}, old) == []
    m = R.compare_figures({"keys": {"a": {"value": 1.0}, "b": {"value": [1, 2.0]}, "d": {"value": 1}}}, old)
    assert m == ["figures key missing from the rerun: c", "figures key not in the release: d"]
    assert R.compare_figures({"keys": {**old["keys"], "c": {"value": 1}}}, old) == [
        "figures key differs: c: released True, rerun 1"]


def test_main_prints_one_line_per_mismatch_and_the_verdict(tmp_path, capsys, monkeypatch):
    root, bundle = _release(tmp_path)
    monkeypatch.setattr(R, "rerun", lambda v, **k: ["x differs", "y differs"])
    assert R.main(["v4-s99", "--bundle", str(bundle), "--scratch", str(tmp_path / "s")]) == 1
    assert capsys.readouterr().out.splitlines() == ["x differs", "y differs", "RERUN FAIL v4-s99 2 mismatches"]
    monkeypatch.setattr(R, "rerun", lambda v, **k: [])
    assert R.main(["v4-s99"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "RERUN PASS v4-s99"


def test_unknown_version_fails(tmp_path):
    root, bundle = _release(tmp_path)
    with pytest.raises(SystemExit, match="RERUN FAIL v4-s00"):
        R.rerun("v4-s00", root=root, bundle=bundle, scratch=tmp_path / "s", build=lambda d: PAYLOAD,
                figures_write=_fw)


def test_figures_writer_takes_the_release_commit(tmp_path, monkeypatch):
    """In the sealed box the source is a git archive with no .git: the figures writer must take the release commit
    from the row, never call git."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools import figures as F
    monkeypatch.setattr(F, "_commit", lambda: (_ for _ in ()).throw(AssertionError("git must not run")))
    monkeypatch.setattr(F, "generate", lambda run, modules=None: {"meta": {"release_tag": "v4-s99"}, "keys": {}})
    rp = tmp_path / "run.json"
    rp.write_text("{}")
    F.write(rp, tmp_path / "f.json", release=True, commit="c0ffee")
    assert json.loads((tmp_path / "f.json").read_text())["meta"]["commit"] == "c0ffee"
