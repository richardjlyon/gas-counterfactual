"""Ticket 32 (release-suite-run.md D1-D4, B16): the release records its own test-suite run and refuses a
dirty or failing tree. Seam: `gascf.release.cut` in a temporary git repo, with pytest and the clock export
stubbed (light; no suite is run here)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gascf import release as rel


def _git(root, *a):
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "eng"
    (root / "src").mkdir(parents=True)
    (root / "out/v4").mkdir(parents=True)
    (root / "src/x.py").write_text("x = 1\n")
    (root / "out/v4/run.json").write_text(json.dumps({"meta": {"engine_version": "v4-s99"}}))
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c1")
    monkeypatch.setattr(rel.clock_export, "build", lambda *a, **k: {"meta": {"engine_version": "v4-s99"}})
    # cut() writes figures.json through the release gate (write_figures, release=True; db97b77). The gate and the
    # write stay real; only the key modules are narrowed to release_record, the one this seam fills (from the
    # meta.test_suite block cut itself writes). The other modules need a full s36 run file, which no light test
    # has; their gate is tested in test_release_check.py.
    from tools import figures as F
    from tools.figures_keys import release_record
    monkeypatch.setattr(F, "_modules", lambda: [release_record])
    return root


def _never(*a, **k):
    raise AssertionError("pytest must not run")


def test_dirty_tree_refused_before_pytest_runs(repo):
    (repo / "notes.txt").write_text("uncommitted\n")
    with pytest.raises(SystemExit, match="dirty"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=_git(repo, "rev-parse", "HEAD"), root=repo,
                runner=_never)


def test_commit_mismatch_refused(repo):
    with pytest.raises(SystemExit, match="HEAD"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit="0" * 40, root=repo, runner=_never)


def test_suite_command_is_single_process():
    """Richard, 18 Oct 2026 (AGENTS.md 'Running it'): never `pytest -n`; parallel runs once crashed the VM.
    The release's own suite run is one process, with xdist switched off even if a config ever adds -n."""
    cmd = rel.SUITE_COMMAND
    assert "-n" not in cmd and not any(a.startswith(("-n", "--numprocesses", "--dist")) for a in cmd)
    plugins_off = [cmd[i + 1] for i, a in enumerate(cmd[:-1]) if a == "-p"]
    assert "no:xdist" in plugins_off


def test_cut_does_not_tag(repo):
    """Tags are Richard's (AGENTS.md 'Running it', Richard, 18 Oct 2026). cut records the commit to tag and stops."""
    head = _git(repo, "rev-parse", "HEAD")
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=lambda c, d: ("3 passed in 1.0s\n", 1.0))
    assert _git(repo, "tag", "--list") == ""
    assert row["commit"] == head


def test_result_recorded_in_row_and_run_meta(repo):
    head = _git(repo, "rev-parse", "HEAD")
    seen = {}

    def runner(cmd, cwd):
        seen["cmd"], seen["cwd"] = cmd, cwd
        return "....\n3 passed, 1 warning in 2.01s\n", 2.01

    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo, runner=runner)
    t = row["tests"]
    assert (t["passed"], t["failed"], t["skipped"], t["errors"], t["warnings"]) == (3, 0, 0, 0, 1)
    assert t["commit"] == head and t["duration_s"] == 2.01 and t["command"] == " ".join(rel.SUITE_COMMAND)
    assert seen["cwd"] == repo
    run = json.loads((repo / "out/v4/run.json").read_text())
    assert run["meta"]["test_suite"] == t
    reg = json.loads((repo / "releases.yaml").read_text())
    assert reg["releases"][-1]["tests"] == t
    figs = json.loads((repo / "out/figures/v4-s99.json").read_text())   # written by cut, through the gate
    assert figs["keys"]["test_suite_pass_count"]["value"] == 3
    assert figs["keys"]["release.test_suite.commit"]["value"] == head


def _sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_row_carries_figures_file_and_sha256(repo):
    """model-release first ticket 2 (Richard's release rules): every new releases.yaml row pins the figures file
    by sha256, so a report's pin checker can refuse a changed figures.json."""
    head = _git(repo, "rev-parse", "HEAD")
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=lambda c, d: ("3 passed in 1.0s\n", 1.0))
    assert row["figures_file"] == "out/figures/v4-s99.json"
    assert row["figures_sha256"] == _sha(repo / "out/figures/v4-s99.json")
    reg = json.loads((repo / "releases.yaml").read_text())
    assert reg["releases"][-1]["figures_sha256"] == row["figures_sha256"]


def test_figures_meta_names_run_sha256_and_version(repo):
    """model-release first ticket 1: figures.json meta carries run_sha256 (equal to the row's, i.e. the run file as
    released) and the version, written by the release tool, never by hand."""
    head = _git(repo, "rev-parse", "HEAD")
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=lambda c, d: ("3 passed in 1.0s\n", 1.0))
    meta = json.loads((repo / "out/figures/v4-s99.json").read_text())["meta"]
    assert meta["run_sha256"] == row["run_sha256"] == _sha(repo / "out/v4/run.json")
    assert meta["version"] == "v4-s99"
    assert "commit" in meta


def test_failing_suite_refused(repo):
    head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(SystemExit, match="failed"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                runner=lambda c, d: ("1 failed, 2 passed in 1.0s\n", 1.0))
    assert not (repo / "releases.yaml").exists()


T7 = "tests/test_fossil_like_for_like.py::test_early_years_gap_close_to_net_zero_extras_pooled"


def test_disclosed_0111_failure_alone_is_recorded_not_refused(repo):
    """Decision 0111 (Richard Lyon, 19 Oct 2026): ticket 13 test 7 stays red and is an expected, disclosed failure.
    The cut accepts a suite whose only failures are the disclosed ones, by node id, and records each with its
    decision in the row; the failed count is kept as it is."""
    head = _git(repo, "rev-parse", "HEAD")
    out = f"FAILED {T7} - assert False is True\n1 failed, 2 passed in 1.0s\n"
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo, runner=lambda c, d: (out, 1.0))
    assert row["tests"]["failed"] == 1
    assert row["tests"]["disclosed_failures"] == [{"test": T7, "decision": "0111"}]
    assert rel.DISCLOSED_FAILURES == {T7: "0111"}


def test_any_other_failure_still_refused(repo):
    head = _git(repo, "rev-parse", "HEAD")
    for out in (f"FAILED {T7} - x\nFAILED tests/test_x.py::test_y - y\n2 failed, 2 passed in 1.0s\n",
                "FAILED tests/test_x.py::test_y - y\n1 failed, 2 passed in 1.0s\n",
                "1 failed, 2 passed in 1.0s\n",                         # a failure not named: refused
                f"FAILED {T7} - x\n1 failed, 1 error in 1.0s\n"):
        with pytest.raises(SystemExit, match="REFUSED"):
            rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo, runner=lambda c, d, o=out: (o, 1.0))
    assert not (repo / "releases.yaml").exists()


PENDING = "tests/test_releases.py::test_latest_release_series_equal_engine_code"


def _two_phase(first: str, post: str, seen: list):
    def runner(cmd, cwd):
        seen.append(cmd)
        return (post if cmd == rel.POST_RELEASE_COMMAND else first), 1.0
    return runner


def test_release_pending_test_is_checked_after_the_row_is_written(repo):
    """The drift test compares the engine with the LATEST release row, so it is red by design until the new row
    exists. The cut accepts it in the full suite, writes the row, then re-runs tests/test_releases.py, which must pass
    against the new row; both runs are recorded."""
    head = _git(repo, "rev-parse", "HEAD")
    seen = []
    first = f"FAILED {PENDING} - balancing series moved\nFAILED {T7} - x\n2 failed, 9 passed in 1.0s\n"
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=_two_phase(first, "5 passed in 0.5s\n", seen))
    assert seen == [rel.SUITE_COMMAND, rel.POST_RELEASE_COMMAND]
    assert rel.RELEASE_PENDING == {PENDING} and rel.POST_RELEASE_COMMAND[-1] == "tests/test_releases.py"
    assert row["tests"]["release_pending"] == [PENDING]
    assert row["tests"]["post_release_check"]["passed"] == 5 and row["tests"]["post_release_check"]["failed"] == 0
    assert json.loads((repo / "releases.yaml").read_text())["releases"][-1]["tests"] == row["tests"]


def test_failing_post_release_check_rolls_the_release_back(repo):
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()
    with pytest.raises(SystemExit, match="REFUSED: post-release check"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                runner=_two_phase(f"FAILED {PENDING} - x\n1 failed, 9 passed in 1.0s\n",
                                  f"FAILED {PENDING} - x\n1 failed, 4 passed in 0.5s\n", []))
    assert not (repo / "releases.yaml").exists()
    assert not (repo / "out/clock/v4-s99.json").exists() and not (repo / "out/figures/v4-s99.json").exists()
    assert (repo / "out/v4/run.json").read_bytes() == before
    assert _git(repo, "status", "--porcelain") == ""


def test_figures_json_reads_the_release_record(repo):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools import figures as F
    head = _git(repo, "rev-parse", "HEAD")
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=lambda c, d: ("2 passed, 1 skipped in 1.0s\n", 1.0))
    run = json.loads((repo / "out/v4/run.json").read_text())
    from tools.figures_keys import release_record as RR
    k = F.generate(run, modules=[RR])["keys"]
    assert k["release.test_suite.commit"]["value"] == row["commit"] == row["tests"]["commit"]
    assert k["test_suite_pass_count"]["value"] == 2
    assert k["test_suite_total"]["value"] == 3
    assert k["release.test_suite.started_utc"]["value"] == row["tests"]["started_utc"]
    assert F.generate({"meta": {"engine_version": "v4-s35"}}, modules=[RR])["keys"]["test_suite_pass_count"]["value"] is None


def test_v4_s35_row_present_with_its_pinned_hashes():
    """B21: the v4-s35 row (added before s36) so test_releases.py covers the release No. 2 and RB pin to."""
    reg = rel.load(Path(__file__).resolve().parents[1] / "releases.yaml")
    r = next(x for x in reg["releases"] if x["version"] == "v4-s35")
    assert r["run_sha256"] == "f902a6140d22672dd94e5130ff5b91cf2026e46ea87392af55384b604b7d7b49"
    assert r["clock_export_sha256"] == "6838a93ca701baef90c9f469821d426ee0d9470c550922eccdfaded6f73029ba"


def test_cli_with_commit_runs_cut(monkeypatch):
    seen = {}
    monkeypatch.setattr(rel, "cut", lambda v, run, note, commit: seen.update(v=v, commit=commit) or {"version": v})
    assert rel.main(["v4-s36", "--run", "out/v4/x.json", "--note", "n", "--commit", "abc"]) == 0
    assert seen == {"v": "v4-s36", "commit": "abc"}


def test_figures_gate_refusal_leaves_the_tree_as_it_was(repo, monkeypatch):
    """Code review (19 Oct 2026): the figures gate refuses after the cut has written meta.test_suite into the run file;
    the cut must restore every file it wrote before it re-raises, so a refused cut leaves a clean tree."""
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()

    def refuse(*a, **k):
        raise ValueError("figures.json is incomplete: these keys are None (release refused): x")
    monkeypatch.setattr(rel, "write_figures", refuse)
    with pytest.raises(ValueError, match="incomplete"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                runner=lambda c, d: ("3 passed in 1.0s\n", 1.0))
    assert (repo / "out/v4/run.json").read_bytes() == before
    assert not (repo / "releases.yaml").exists()
    assert _git(repo, "status", "--porcelain") == ""
