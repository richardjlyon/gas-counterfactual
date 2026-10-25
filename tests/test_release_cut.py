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
    # K4 (card [internal ticket]): cut() checks the figures' null set against the recorded one; the release_record keys this
    # seam fills have none
    (root / "reference").mkdir()
    (root / "reference/figures_null_fields.json").write_text(json.dumps({"paths": []}))
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


def _write_junit(cmd: list[str], out: str, skipped_extra: int = 0) -> None:
    """Like pytest: write the junit file the cut asks for, with the counts of the summary line `out` (plus
    `skipped_extra` skips the summary line does not show: pytest's junit counts an xfail as a skip)."""
    j = next((c.split("=", 1)[1] for c in cmd if c.startswith("--junitxml=")), None)
    assert j, cmd
    n = rel.parse_summary(out) if out.strip() else {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    sk = n["skipped"] + skipped_extra
    tests = n["passed"] + n["failed"] + sk + n["errors"]
    Path(j).write_text(f"<testsuites name='{'post' if 'tests/test_releases.py' in cmd else 'suite'}'>"
                       f"<testsuite name='pytest' tests='{tests}' failures='{n['failed']}' errors='{n['errors']}' "
                       f"skipped='{sk}'/></testsuites>")


def _runner(suite: str, post: str | None = None, *, junit: bool = True, post_skipped_extra: int = 0,
            suite_skipped_extra: int = 0):
    """A stub runner that returns `suite` for the full suite and `post` (default: the same) for the post-release
    check, writing a junit file that agrees with each, as pytest does (unless told otherwise)."""
    def runner(cmd, cwd):
        is_post = "tests/test_releases.py" in cmd
        out = (suite if post is None else post) if is_post else suite
        if junit:
            _write_junit(cmd, out, post_skipped_extra if is_post else suite_skipped_extra)
        return out, 1.0
    return runner


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


def test_suite_command_is_the_proven_jS3_command():
    """K7 (card [internal ticket]; critic finding 7): the gate must run the command the 0-failed suite was proved with (M4 job
    [internal ticket]-jS3): single process, no disk cache, -q, the f/E/s report plus x and X (so an xfail or an xpass is
    named in the kept log), and a junit file (added by the cut)."""
    assert rel.SUITE_COMMAND == ["python", "-m", "pytest", "-p", "no:xdist", "-p", "no:cacheprovider", "-q",
                                 "-rfEsxX"]


def test_cut_does_not_tag(repo):
    """Tags are Richard's (AGENTS.md 'Running it', Richard, 18 Oct 2026). cut records the commit to tag and stops."""
    head = _git(repo, "rev-parse", "HEAD")
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=_runner("3 passed in 1.0s\n"))
    assert _git(repo, "tag", "--list") == ""
    assert row["commit"] == head


def test_result_recorded_in_row_and_run_meta(repo):
    head = _git(repo, "rev-parse", "HEAD")
    seen = {}

    def runner(cmd, cwd):
        seen["cmd"], seen["cwd"] = cmd, cwd
        _write_junit(cmd, "....\n3 passed, 1 warning in 2.01s\n")
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
                  runner=_runner("3 passed in 1.0s\n"))
    assert row["figures_file"] == "out/figures/v4-s99.json"
    assert row["figures_sha256"] == _sha(repo / "out/figures/v4-s99.json")
    reg = json.loads((repo / "releases.yaml").read_text())
    assert reg["releases"][-1]["figures_sha256"] == row["figures_sha256"]


def test_figures_meta_names_run_sha256_and_version(repo):
    """model-release first ticket 1: figures.json meta carries run_sha256 (equal to the row's, i.e. the run file as
    released) and the version, written by the release tool, never by hand."""
    head = _git(repo, "rev-parse", "HEAD")
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=_runner("3 passed in 1.0s\n"))
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


@pytest.fixture
def t7_disclosed(monkeypatch):
    """The disclosure mechanism, tested with ticket 13 test 7 as it stood under 0111 (it passes now; see below)."""
    monkeypatch.setattr(rel, "DISCLOSED_FAILURES", {T7: "0111"})


def test_live_disclosed_failures_name_only_tests_that_still_fail():
    """Card [internal ticket] (sweep 5.11): DISCLOSED_FAILURES lets a named test fail at the gate. Test 7 (0111) has passed
    since RB v1.1 M6 (0163 R7 (a), feedback both ways; it asserts passed is True): 0 failures in the v4-s39 row and
    PASSED in the v4-s40 cut suite (junit-cut.xml, M4 job [internal ticket]-jW, 23 Oct 2026). A passing test left on the list
    would let it go red again at a gate unnoticed, so the live list is empty; 0111's disclosure text stays in the
    paper's record of v4-s37."""
    assert rel.DISCLOSED_FAILURES == {}


def test_disclosed_0111_failure_alone_is_recorded_not_refused(repo, t7_disclosed):
    """Decision 0111 (Richard Lyon, 19 Oct 2026): ticket 13 test 7 stays red and is an expected, disclosed failure.
    The cut accepts a suite whose only failures are the disclosed ones, by node id, and records each with its
    decision in the row; the failed count is kept as it is."""
    head = _git(repo, "rev-parse", "HEAD")
    out = f"FAILED {T7} - assert False is True\n1 failed, 2 passed in 1.0s\n"
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo, runner=_runner(out))
    assert row["tests"]["failed"] == 1
    assert row["tests"]["disclosed_failures"] == [{"test": T7, "decision": "0111"}]


def test_any_other_failure_still_refused(repo, t7_disclosed):
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
        seen.append(cmd[:-1] if cmd[-1].startswith("--junitxml=") else cmd)   # 5.1: the cut adds its junit file
        out = post if "tests/test_releases.py" in cmd else first
        _write_junit(cmd, out)
        return out, 1.0
    return runner


def test_release_pending_test_is_checked_after_the_row_is_written(repo, t7_disclosed):
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
    # card [internal ticket] (sweep 5.2): the post-release check is a row field of its own, so the suite record stays equal
    # to the run file's meta.test_suite
    assert row["post_release_check"]["passed"] == 5 and row["post_release_check"]["failed"] == 0
    assert json.loads((repo / "releases.yaml").read_text())["releases"][-1] == row


def test_post_release_check_runs_even_when_nothing_is_pending(repo):
    """Card [internal ticket] (sweep 5.2): cut() runs tests/test_releases.py against the new row on EVERY cut, not only when
    a release-pending test failed. At v4-s40 nothing was pending, so the row's own CM case would have shipped red."""
    head = _git(repo, "rev-parse", "HEAD")
    seen = []
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=_two_phase("9 passed in 1.0s\n", "4 passed in 0.5s\n", seen))
    assert seen == [rel.SUITE_COMMAND, rel.POST_RELEASE_COMMAND]
    assert row["post_release_check"]["passed"] == 4 and "release_pending" not in row["tests"]
    assert json.loads((repo / "out/v4/run.json").read_text())["meta"]["test_suite"] == row["tests"]


def test_post_release_failure_after_a_clean_suite_rolls_the_release_back(repo):
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()
    bad = "FAILED tests/test_releases.py::test_clock_export_cm_block_equals_run_file[v4-s99] - x\n1 failed, 4 passed\n"
    with pytest.raises(SystemExit, match="REFUSED: post-release check"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                runner=_two_phase("9 passed in 1.0s\n", bad, []))
    assert not (repo / "releases.yaml").exists() and not (repo / "out/clock/v4-s99.json").exists()
    assert (repo / "out/v4/run.json").read_bytes() == before
    assert _git(repo, "status", "--porcelain") == ""


def _junit_runner(suite: str, post: str):
    """A stub runner that, like pytest, writes the junit file the cut asks for."""
    return _runner(suite, post)


def test_gate_keeps_its_full_suite_output_and_junit(repo):
    """Card [internal ticket] (sweep 5.1): the gate kept only a REFUSED line and counts, so a skip or a wrong-file pass could
    not be audited. The cut now keeps the full output and the junit of both runs: under out/tests/ (release files,
    pinned by sha256 in the row, carried into the bundle) and, refused or not, under .release-logs/ (git-ignored)."""
    head = _git(repo, "rev-parse", "HEAD")
    suite = ".....\n5 passed in 2.0s\n"   # K1 ([internal ticket]): a skip is now refused, so the kept output has none
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=_junit_runner(suite, "6 passed in 0.5s\n"))
    files = row["suite_output"]
    assert sorted(files) == ["out/tests/v4-s99-post-release-junit.xml", "out/tests/v4-s99-post-release.log",
                             "out/tests/v4-s99-suite-junit.xml", "out/tests/v4-s99-suite.log"]
    assert (repo / "out/tests/v4-s99-suite.log").read_text() == suite
    assert "name='suite'" in (repo / "out/tests/v4-s99-suite-junit.xml").read_text()
    for f, sha in files.items():
        assert _sha(repo / f) == sha, f
    assert json.loads((repo / "releases.yaml").read_text())["releases"][-1]["suite_output"] == files
    kept = sorted(p.name for p in (repo / ".release-logs/v4-s99").iterdir())
    assert any(n.endswith("-suite.log") for n in kept) and any(n.endswith("-post-release.log") for n in kept)


def test_refused_gate_keeps_its_output_and_leaves_git_clean(repo):
    head = _git(repo, "rev-parse", "HEAD")
    out = "FAILED tests/test_x.py::test_y - assert 8.632 == 8.674\n1 failed, 2 passed in 1.0s\n"
    with pytest.raises(SystemExit, match="REFUSED"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo, runner=_junit_runner(out, ""))
    logs = sorted((repo / ".release-logs/v4-s99").glob("*-suite.log"))
    assert logs and logs[-1].read_text() == out
    assert sorted((repo / ".release-logs/v4-s99").glob("*-suite-junit.xml"))
    assert not (repo / "out/tests").exists()
    assert _git(repo, "status", "--porcelain") == ""


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
                  runner=_runner("2 passed in 1.0s\n"))
    run = json.loads((repo / "out/v4/run.json").read_text())
    from tools.figures_keys import release_record as RR
    k = F.generate(run, modules=[RR])["keys"]
    assert k["release.test_suite.commit"]["value"] == row["commit"] == row["tests"]["commit"]
    assert k["test_suite_pass_count"]["value"] == 2
    assert k["test_suite_total"]["value"] == 2
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
                runner=_runner("3 passed in 1.0s\n"))
    assert (repo / "out/v4/run.json").read_bytes() == before
    assert not (repo / "releases.yaml").exists()
    assert _git(repo, "status", "--porcelain") == ""


# ---------------------------------------------------------------------------- K1, card [internal ticket] (critic finding 1)
# The CE's rule for the v4-s40 cut: the gate's saved junit must show 0 skipped and 0 failed, and the paper says the
# suite "ran in full". So a skip refuses the cut, in the suite and in the post-release check, read from the summary
# line AND the junit file pytest writes (which also counts an xfail as a skip). No person has to read the junit.

SKIP_OUT = "..s\nSKIPPED [1] tests/test_cost_register_0168.py:118: register home not reachable from here\n" \
           "2 passed, 1 skipped in 1.0s\n"


def _untouched(repo, before: bytes) -> None:
    assert (repo / "out/v4/run.json").read_bytes() == before
    assert not (repo / "releases.yaml").exists()
    assert not (repo / "out/clock/v4-s99.json").exists() and not (repo / "out/figures/v4-s99.json").exists()
    assert not (repo / "out/tests").exists()
    assert _git(repo, "status", "--porcelain") == ""


def test_a_skipped_test_in_the_suite_refuses_the_cut(repo):
    """'2 passed, 1 skipped' (the register-home test that cannot reach its path) is REFUSED, before anything is
    written; the refused gate's output is still kept under .release-logs/."""
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()
    with pytest.raises(SystemExit, match=r"REFUSED: suite .*1 skipped"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo, runner=_runner(SKIP_OUT))
    _untouched(repo, before)
    assert sorted((repo / ".release-logs/v4-s99").glob("*-suite.log"))[-1].read_text() == SKIP_OUT


def test_a_skip_the_summary_line_hides_is_caught_from_the_junit(repo):
    """pytest's junit counts an xfail as a skip; the summary line does not say 'skipped'. The junit decides."""
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()
    with pytest.raises(SystemExit, match=r"REFUSED: suite .*junit"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                runner=_runner("3 passed, 1 xfailed in 1.0s\n", suite_skipped_extra=1))
    _untouched(repo, before)


def test_a_suite_with_no_junit_file_is_refused(repo):
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()
    with pytest.raises(SystemExit, match=r"REFUSED: suite .*junit"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                runner=_runner("3 passed in 1.0s\n", junit=False))
    _untouched(repo, before)


def test_a_junit_that_disagrees_with_the_summary_line_is_refused(repo):
    """A summary read wrongly (critic finding 3) must not pass: the counts in the junit and in the summary line agree
    or the cut is refused."""
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()

    def runner(cmd, cwd):
        _write_junit(cmd, "4 passed in 1.0s\n")
        return "3 passed in 1.0s\n", 1.0
    with pytest.raises(SystemExit, match=r"REFUSED: suite .*junit"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo, runner=runner)
    _untouched(repo, before)


def test_a_skip_in_the_post_release_check_rolls_the_release_back(repo):
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()
    with pytest.raises(SystemExit, match=r"REFUSED: post-release check.*1 skipped"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                runner=_runner("9 passed in 1.0s\n", "3 passed, 1 skipped in 0.5s\n"))
    _untouched(repo, before)


def test_a_post_release_skip_seen_only_in_the_junit_rolls_the_release_back(repo):
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()
    with pytest.raises(SystemExit, match=r"REFUSED: post-release check.*junit"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                runner=_runner("9 passed in 1.0s\n", "4 passed in 0.5s\n", post_skipped_extra=1))
    _untouched(repo, before)


def test_a_post_release_check_with_no_junit_rolls_the_release_back(repo):
    head = _git(repo, "rev-parse", "HEAD")
    before = (repo / "out/v4/run.json").read_bytes()

    def runner(cmd, cwd):
        if "tests/test_releases.py" not in cmd:
            _write_junit(cmd, "9 passed in 1.0s\n")
        return ("4 passed in 0.5s\n" if "tests/test_releases.py" in cmd else "9 passed in 1.0s\n"), 1.0
    with pytest.raises(SystemExit, match=r"REFUSED: post-release check.*junit"):
        rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo, runner=runner)
    _untouched(repo, before)


def test_a_clean_cut_records_zero_skipped_in_both_runs(repo):
    head = _git(repo, "rev-parse", "HEAD")
    row = rel.cut("v4-s99", Path("out/v4/run.json"), "n", commit=head, root=repo,
                  runner=_runner("9 passed in 1.0s\n", "4 passed in 0.5s\n"))
    assert row["tests"]["skipped"] == 0 and row["post_release_check"]["skipped"] == 0
    assert row["post_release_check"]["failed"] == 0 and row["post_release_check"]["errors"] == 0
