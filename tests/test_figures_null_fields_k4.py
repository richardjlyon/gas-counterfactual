"""K4, card [internal ticket] (critic finding 4; sweep T6, sweep-technical R8b and 5.12): model-release step 4 says "no null
or empty anywhere in figures.json", but the release carries 44 nested null or empty fields (the same 44 in the frozen
v4-s39 and in the v4-s40 fresh export once its release record is filled). A check known to fail and passed over each
time is how a new null would get through. So the 44 are recorded as an exact expected set
(reference/figures_null_fields.json) and the cut passes only when the set is EQUAL: a 45th null fails, and so does
filling one of the 44 without updating the record.

Seam: `gascf.release.null_fields` (the walk the step-4 jq does: every scalar that is null or "") and `cut()`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gascf import release as rel

ROOT = Path(__file__).resolve().parents[1]


def test_null_fields_lists_every_nested_null_or_empty_scalar_like_the_step_4_jq():
    fig = {"keys": {"a": {"value": None, "meta": {"p": "", "q": "x", "z": 0, "f": False, "l": []}},
                    "t": {"value": [{"of_which": None}, {"of_which": 1.0}, ["", "y"]]}}}
    assert rel.null_fields(fig) == ["keys/a/meta/p", "keys/a/value", "keys/t/value/0/of_which", "keys/t/value/2/0"]


def test_the_expected_set_is_the_44_fields_of_released_v4_s39():
    """The sweep found the same 44 in v4-s39 (released) and in v4-s40: the record is those 44, by path, no more."""
    exp = rel.expected_null_fields(ROOT)
    assert len(exp) == 44 == len(set(exp))
    assert exp == rel.null_fields(json.loads((ROOT / "out/figures/v4-s39.json").read_text()))


def _git(root, *a):
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A light repo like test_release_cut's, whose figures writer is stubbed to write a chosen figures.json."""
    root = tmp_path / "eng"
    (root / "src").mkdir(parents=True)
    (root / "out/v4").mkdir(parents=True)
    (root / "reference").mkdir()
    (root / "src/x.py").write_text("x = 1\n")
    (root / "out/v4/run.json").write_text(json.dumps({"meta": {"engine_version": "v4-s99"}}))
    (root / "reference/figures_null_fields.json").write_text(json.dumps(
        {"_comment": "test", "paths": ["keys/a/meta/period", "keys/t/value/0/of_which"]}))
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c1")
    monkeypatch.setattr(rel.clock_export, "build", lambda *a, **k: {"meta": {"engine_version": "v4-s99"}})
    return root


def _figs(monkeypatch, fig: dict):
    def write(run, out, *, modules=None, root=None):
        op = Path(out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(fig))
        return op
    monkeypatch.setattr(rel, "write_figures", write)


def _runner(cmd, cwd):
    j = next(c.split("=", 1)[1] for c in cmd if c.startswith("--junitxml="))
    Path(j).write_text("<testsuites><testsuite name='pytest' tests='3' failures='0' errors='0' skipped='0'/>"
                       "</testsuites>")
    return "3 passed in 1.0s\n", 1.0


GOOD = {"meta": {"version": "v4-s99"},
        "keys": {"a": {"value": 1, "meta": {"period": None}}, "t": {"value": [{"of_which": None}]}}}


def test_cut_passes_when_the_null_set_is_exactly_the_expected_set(repo, monkeypatch):
    _figs(monkeypatch, GOOD)
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=_git(repo, "rev-parse", "HEAD"), root=repo,
                  runner=_runner)
    assert row["figures_null_fields"] == {"count": 2, "expected_file": "reference/figures_null_fields.json",
                                          "equal": True}


def test_a_45th_null_refuses_the_cut_and_rolls_it_back(repo, monkeypatch):
    bad = json.loads(json.dumps(GOOD))
    bad["keys"]["b"] = {"value": 2, "meta": {"ruling": ""}}
    _figs(monkeypatch, bad)
    before = (repo / "out/v4/run.json").read_bytes()
    with pytest.raises(SystemExit, match=r"REFUSED: figures.json null or empty fields.*keys/b/meta/ruling"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=_git(repo, "rev-parse", "HEAD"), root=repo,
                runner=_runner)
    assert (repo / "out/v4/run.json").read_bytes() == before
    assert not (repo / "releases.yaml").exists() and not (repo / "out/figures/v4-s99.json").exists()
    assert _git(repo, "status", "--porcelain") == ""


def test_filling_an_expected_null_without_updating_the_record_also_refuses(repo, monkeypatch):
    filled = json.loads(json.dumps(GOOD))
    filled["keys"]["a"]["meta"]["period"] = "2002-2024"
    _figs(monkeypatch, filled)
    with pytest.raises(SystemExit, match=r"REFUSED: figures.json null or empty fields.*keys/a/meta/period"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=_git(repo, "rev-parse", "HEAD"), root=repo,
                runner=_runner)
    assert not (repo / "releases.yaml").exists()


def test_a_missing_expected_set_refuses(repo, monkeypatch):
    (repo / "reference/figures_null_fields.json").unlink()
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-am", "rm")
    _figs(monkeypatch, GOOD)
    with pytest.raises(SystemExit, match=r"REFUSED: .*figures_null_fields.json"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=_git(repo, "rev-parse", "HEAD"), root=repo,
                runner=_runner)
