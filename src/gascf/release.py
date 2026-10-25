"""Cut an engine release for the Subsidy Clock: `out/clock/<version>.json` + a row in releases.yaml.

    uv run python -m gascf.release v4-s32 --run out/v4/2026-10-13.json --note "..."

Rules (Richard, 14 Oct 2026): a release is pinned by version and sha256; drift is detected,
never applied automatically. So this command:

- refuses a version already listed in releases.yaml, or an out/clock/<version>.json that exists
  (once listed, files are immutable: a new run is a new version);
- refuses if <version> differs from the run file's meta.engine_version;
- refuses if the working tree's src/ differs from HEAD (the baselines are computed by the
  engine code at the recorded commit, so that code must be committed);
- writes nothing outside out/clock/ and releases.yaml.

releases.yaml is written as JSON (valid YAML), like reference/cost_editions.yaml: the engine
carries no YAML parser.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from gascf import clock_export

ROOT = Path(__file__).parents[2]
RELEASES = ROOT / "releases.yaml"
CLOCK_DIR = ROOT / "out/clock"
FIGURES_DIR = ROOT / "out/figures"
HEADER = ("Engine releases. One row per version; once listed, the run file and the clock export are "
          "immutable (tests/test_releases.py checks every sha256). Cut with `python -m gascf.release`.")


def _git(*args: str, root: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()


def write_figures(run, out, *, modules=None, root: Path = ROOT) -> Path:
    """The release path's figures.json step, gated by the non-None release check (ticket 35, review R2-SP1a):
    tools.figures.write(..., release=True) refuses, before writing anything, if any figures key is None whatever
    its status, naming each offending key, so a missing run-file value stops the release. modules=None uses every
    registered key module. Run on an s36 run file by `cut`; ticket 35 runs the real release."""
    from tools.figures import write as _figwrite
    rp = Path(run) if Path(run).is_absolute() else root / run
    op = Path(out) if Path(out).is_absolute() else root / out
    op.parent.mkdir(parents=True, exist_ok=True)
    return _figwrite(rp, op, modules=modules, release=True)


def load(path: Path = RELEASES) -> dict:
    if not path.exists():
        return {"_comment": HEADER, "releases": []}
    return json.loads(path.read_text())


def release(version: str, run: Path, note: str, *, root: Path = ROOT, tests: dict | None = None,
            figures: Path | None = None) -> dict:
    run = (root / run) if not Path(run).is_absolute() else Path(run)
    if not run.exists():
        raise SystemExit(f"run file not found: {run}")
    reg = load(root / "releases.yaml")
    if any(r["version"] == version for r in reg["releases"]):
        raise SystemExit(f"REFUSED: version {version} is already in releases.yaml (releases are immutable)")
    out = root / "out/clock" / f"{version}.json"
    if out.exists():
        raise SystemExit(f"REFUSED: {out.relative_to(root)} exists (releases are immutable)")
    meta_v = json.loads(run.read_text())["meta"]["engine_version"]
    if meta_v != version:
        raise SystemExit(f"REFUSED: version {version} != run file meta.engine_version {meta_v}")
    dirty = _git("status", "--porcelain", "--", "src", root=root)
    if dirty:
        raise SystemExit(f"REFUSED: src/ has uncommitted changes; commit first:\n{dirty}")
    commit = _git("rev-parse", "HEAD", root=root)
    run_rel = str(run.resolve().relative_to(root.resolve()))
    run_commit = _git("log", "-1", "--format=%H", "--", run_rel, root=root) or None
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = clock_export.build(run, commit=commit, created=created, run_commit=run_commit)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, allow_nan=False) + "\n")
    row = {
        "version": version,
        "date": date.today().isoformat(),
        "commit": commit,
        "run_commit": run_commit,
        "run_file": run_rel,
        "run_sha256": clock_export.sha256_file(run),
        "clock_export_file": str(out.relative_to(root)),
        "clock_export_sha256": clock_export.sha256_file(out),
        "note": note,
    }
    if tests is not None:
        row["tests"] = tests
    if figures is not None:
        # model-release first ticket 2: the figures file is pinned by sha256 like the run file
        fp = Path(figures) if Path(figures).is_absolute() else root / figures
        row["figures_file"] = str(fp.resolve().relative_to(root.resolve()))
        row["figures_sha256"] = clock_export.sha256_file(fp)
    reg["releases"].append(row)
    (root / "releases.yaml").write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    return row


# ----------------------------------------------------------------------------- ticket 32 (B16)

# release-suite-run.md D1, one process: Richard, 18 Oct 2026, never `pytest -n` (parallel runs crashed the VM).
# `-p no:xdist` keeps it single even if a config ever adds -n. K7 (card [internal ticket]): -rfEsxX, the command the 0-failed
# suite was proved with (M4 job [internal ticket]-jS3), so an xfail or an xpass is named in the kept log.
SUITE_COMMAND = ["python", "-m", "pytest", "-p", "no:xdist", "-p", "no:cacheprovider", "-q", "-rfEsxX"]
# Failures Richard ruled to stay red, each disclosed in the paper, by pytest node id -> decision. The cut accepts a
# suite whose failures are exactly a subset of these (no errors, every failure named in the -rf report) and records
# them in the row; anything else is refused. Empty since card [internal ticket] (sweep 5.11): decision 0111's ticket 13 test 7
# (tests/test_fossil_like_for_like.py::test_early_years_gap_close_to_net_zero_extras_pooled) has passed since RB v1.1
# M6 (0163 R7 (a)); a passing test left here could go red at a gate unnoticed.
DISCLOSED_FAILURES: dict[str, str] = {}
# Tests that compare the engine with the LATEST releases.yaml row, so red by design until the new row exists. The cut
# accepts them in the full suite, writes the row, then re-runs POST_RELEASE_COMMAND, which must pass; otherwise every
# file the cut wrote is restored and the release is refused.
RELEASE_PENDING = {"tests/test_releases.py::test_latest_release_series_equal_engine_code"}
POST_RELEASE_COMMAND = [*SUITE_COMMAND, "tests/test_releases.py"]


def _failed_ids(out: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^FAILED (\S+)", out, flags=re.MULTILINE)]


# Card [internal ticket] (sweep 5.1): the gate keeps its full suite output. Each run's output and junit go to
# .release-logs/<version>/ (kept whether the cut is refused or not; the folder ignores itself, so a refused cut still
# leaves `git status` clean), and on a cut that is written, to out/tests/<version>-<phase>.log and -junit.xml, pinned
# by sha256 in the row's suite_output and carried into the bundle.
LOG_DIR = ".release-logs"


def _logged_run(runner, cmd: list[str], root: Path, version: str, phase: str) -> tuple[str, float, Path, Path]:
    d = root / LOG_DIR / version
    d.mkdir(parents=True, exist_ok=True)
    (root / LOG_DIR / ".gitignore").write_text("*\n")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log, junit = d / f"{stamp}-{phase}.log", d / f"{stamp}-{phase}-junit.xml"
    out, dur = runner([*cmd, f"--junitxml={junit}"], root)
    log.write_text(out)
    return out, dur, log, junit


def junit_counts(junit: Path) -> dict:
    """Counts from the junit file pytest wrote: tests, failures, errors, skipped (pytest counts an xfail as a skip
    here), and passed = tests - failures - errors - skipped, summed over every <testsuite>."""
    import xml.etree.ElementTree as ET
    root_el = ET.parse(junit).getroot()
    suites = [root_el] if root_el.tag == "testsuite" else list(root_el.iter("testsuite"))
    n = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    n["passed"] = n["tests"] - n["failures"] - n["errors"] - n["skipped"]
    return n


def run_in_full(summary: dict, junit: Path) -> str | None:
    """K1 (card [internal ticket]; critic finding 1; the CE's rule for the v4-s40 cut: 0 skipped, 0 failed in the saved
    junit; the paper says the suite "ran in full"). None if the run skipped nothing and its junit agrees with its
    summary line; otherwise the reason it did not run in full. Read by the code, so no person has to read the junit."""
    if summary["skipped"] > 0:
        return f"{summary['skipped']} skipped (a release suite must run in full)"
    if not junit.exists():
        return f"no junit file at {junit.name}: the run cannot be checked for skips"
    try:
        j = junit_counts(junit)
    except Exception as e:  # noqa: BLE001 - any unreadable junit refuses
        return f"junit file {junit.name} unreadable: {e}"
    if j["skipped"] > 0:
        return f"junit records {j['skipped']} skipped (an xfail counts as a skip; a release suite must run in full)"
    got = {"passed": j["passed"], "failed": j["failures"], "errors": j["errors"]}
    want = {k: summary[k] for k in got}
    if got != want:
        return f"junit counts {got} differ from the summary line {want}"
    return None


# K4, card [internal ticket] (critic finding 4; sweep T6, sweep-technical R8b): figures.json carries 44 nested null or empty
# fields (the same in v4-s39 and v4-s40). They are recorded by path in this file, and the cut passes only when the
# figures it writes have EXACTLY that set: a new null fails, and so does filling one without updating the record.
NULL_FIELDS_FILE = "reference/figures_null_fields.json"


def null_fields(fig) -> list[str]:
    """Every scalar in `fig` that is null or "" (model-release step 4's jq: paths(scalars) == null or ""), as
    '/'-joined paths, sorted."""
    found: list[str] = []

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, path + [str(k)])
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, path + [str(i)])
        elif x is None or x == "":
            found.append("/".join(path))
    walk(fig, [])
    return sorted(found)


def expected_null_fields(root: Path = ROOT) -> list[str]:
    p = root / NULL_FIELDS_FILE
    if not p.exists():
        raise SystemExit(f"REFUSED: no expected null set {NULL_FIELDS_FILE}: the figures cannot be checked")
    return sorted(json.loads(p.read_text())["paths"])


def check_null_fields(fig_path: Path, root: Path = ROOT) -> dict:
    exp = expected_null_fields(root)
    got = null_fields(json.loads(Path(fig_path).read_text()))
    if got != exp:
        new, gone = sorted(set(got) - set(exp)), sorted(set(exp) - set(got))
        raise SystemExit(f"REFUSED: figures.json null or empty fields differ from {NULL_FIELDS_FILE} "
                         f"({len(got)} found, {len(exp)} expected): new {new}; no longer null {gone}")
    return {"count": len(got), "expected_file": NULL_FIELDS_FILE, "equal": True}


def cut(version: str, run: Path, note: str, *, commit: str, root: Path = ROOT, runner=None) -> dict:
    """Cut a release with its own test-suite record (release-suite-run.md D1-D4): refuses a dirty tree or
    HEAD ≠ `commit`, runs the full suite in that checkout, refuses on any failure or error other than the disclosed
    (DISCLOSED_FAILURES) and release-pending (RELEASE_PENDING) ones, and on any skip (K1, card [internal ticket]: the summary
    line and the junit must both show 0 skipped and agree), records the
    result in the releases.yaml row and the run file's meta.test_suite. It never tags: Richard tags the commit."""
    dirty = _git("status", "--porcelain", root=root)
    if dirty:
        raise SystemExit(f"REFUSED: working tree is dirty; commit or clean first:\n{dirty}")
    head = _git("rev-parse", "HEAD", root=root)
    if head != commit:
        raise SystemExit(f"REFUSED: HEAD {head} is not the release commit {commit}")
    runner = _run_suite if runner is None else runner
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    out, duration, s_log, s_junit = _logged_run(runner, SUITE_COMMAND, root, version, "suite")
    tests = {"commit": head, **parse_summary(out), "duration_s": duration, "started_utc": started,
             "command": " ".join(SUITE_COMMAND)}
    if tests["failed"] + tests["errors"] > 0:
        ids = _failed_ids(out)
        allowed = set(DISCLOSED_FAILURES) | RELEASE_PENDING
        ok = tests["errors"] == 0 and len(ids) == tests["failed"] and all(i in allowed for i in ids)
        if not ok:
            raise SystemExit(f"REFUSED: suite at {head}: {tests['failed']} failed, {tests['errors']} errors"
                             f" (failures not all disclosed: {[i for i in ids if i not in allowed]})")
        disclosed = [i for i in ids if i in DISCLOSED_FAILURES]
        pending = [i for i in ids if i in RELEASE_PENDING]
        if disclosed:
            tests["disclosed_failures"] = [{"test": i, "decision": DISCLOSED_FAILURES[i]} for i in disclosed]
        if pending:
            tests["release_pending"] = pending
    why = run_in_full(tests, s_junit)
    if why:
        raise SystemExit(f"REFUSED: suite at {head}: {why}; nothing written (output kept in {s_log.parent})")
    run_path = (root / run) if not Path(run).is_absolute() else Path(run)
    reg_path, clock_path = root / "releases.yaml", root / "out/clock" / f"{version}.json"
    fig_path = root / "out/figures" / f"{version}.json"
    saved = {p: (p.read_bytes() if p.exists() else None) for p in (run_path, reg_path, clock_path, fig_path)}

    def restore():
        for p, b in saved.items():
            if b is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(b)
    try:
        payload = json.loads(run_path.read_text())
        payload["meta"]["test_suite"] = tests
        run_path.write_text(json.dumps(payload, indent=1, allow_nan=False))
        figs = write_figures(run_path, fig_path, root=root)  # ticket 35 / R2-SP1a: non-None gate
        nulls = check_null_fields(figs, root)                 # K4 ([internal ticket]): the exact expected null set
        row = release(version, run, note, root=root, tests=tests, figures=figs)
    except BaseException:
        restore()                       # a refused cut leaves the tree as it found it (code review, 19 Oct 2026)
        raise
    # Card [internal ticket] (sweep 5.2): EVERY cut re-runs tests/test_releases.py against the new row, not only when a
    # release-pending test failed (at v4-s40 none was pending, so the row's own CM case would have shipped red).
    # A failure other than a disclosed one (DISCLOSED_FAILURES), or any error, rolls the release back.
    pout, pdur, p_log, p_junit = _logged_run(runner, POST_RELEASE_COMMAND, root, version, "post-release")
    post = {**parse_summary(pout), "duration_s": pdur, "command": " ".join(POST_RELEASE_COMMAND)}
    if post["failed"] + post["errors"] > 0:
        pids = _failed_ids(pout)
        if post["errors"] or len(pids) != post["failed"] or any(i not in DISCLOSED_FAILURES for i in pids):
            restore()
            raise SystemExit(f"REFUSED: post-release check (tests/test_releases.py against the new row): "
                             f"{post['failed']} failed, {post['errors']} errors; release rolled back: "
                             f"{[i for i in pids if i not in DISCLOSED_FAILURES]}")
    why = run_in_full(post, p_junit)
    if why:
        restore()
        raise SystemExit(f"REFUSED: post-release check (tests/test_releases.py against the new row): {why}; "
                         f"release rolled back")
    row["post_release_check"] = post       # beside the suite record, which stays equal to meta.test_suite
    row["figures_null_fields"] = nulls
    kept = {}
    for src, name in ((s_log, "suite.log"), (s_junit, "suite-junit.xml"), (p_log, "post-release.log"),
                      (p_junit, "post-release-junit.xml")):
        if src.exists():                  # pytest writes the junit; a missing one is visible by its absence here
            dst = root / "out/tests" / f"{version}-{name}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            kept[str(dst.relative_to(root))] = clock_export.sha256_file(dst)
    row["suite_output"] = kept
    reg = load(reg_path)
    reg["releases"][-1] = row
    reg_path.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    # No tag here: tags are Richard's (AGENTS.md, Richard, 18 Oct 2026; overrides release-suite-run.md D3).
    # The row names the commit he tags as `version`.
    return row


def parse_summary(out: str) -> dict:
    """Counts from pytest's last summary line ("3 passed, 1 warning in 2.01s")."""
    line = [ln for ln in out.strip().splitlines() if re.search(r"\d+ (passed|failed|error)", ln)][-1]
    n = lambda word: sum(int(x) for x in re.findall(rf"(\d+) {word}", line))  # noqa: E731
    return {"passed": n("passed"), "failed": n("failed"), "skipped": n("skipped"),
            "errors": n("errors?"), "warnings": n("warnings?")}


def _run_suite(cmd: list[str], cwd: Path) -> tuple[str, float]:
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, *cmd[1:]], cwd=cwd, capture_output=True, text=True)
    return p.stdout + p.stderr, round(time.monotonic() - t0, 2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gascf.release", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("version", help="must equal the run file's meta.engine_version, e.g. v4-s32")
    ap.add_argument("--run", required=True, type=Path, help="out/v4/<date>.json")
    ap.add_argument("--note", required=True)
    ap.add_argument("--commit", help="release commit: refuse unless HEAD equals it and the tree is clean; run "
                                     "and record the full suite (ticket 32); Richard tags the commit")
    a = ap.parse_args(argv)
    row = cut(a.version, a.run, a.note, commit=a.commit) if a.commit else release(a.version, a.run, a.note)
    print(json.dumps(row, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
