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
# `-p no:xdist` keeps it single even if a config ever adds -n.
SUITE_COMMAND = ["python", "-m", "pytest", "-p", "no:xdist", "-p", "no:cacheprovider", "-q", "-rfEs"]
# Failures Richard ruled to stay red, each disclosed in the paper, by pytest node id -> decision. The cut accepts a
# suite whose failures are exactly a subset of these (no errors, every failure named in the -rf report) and records
# them in the row; anything else is refused. Decision 0111 (Richard Lyon, 19 Oct 2026, item 1.3): ticket 13 test 7.
DISCLOSED_FAILURES = {
    "tests/test_fossil_like_for_like.py::test_early_years_gap_close_to_net_zero_extras_pooled": "0111",
}
# Tests that compare the engine with the LATEST releases.yaml row, so red by design until the new row exists. The cut
# accepts them in the full suite, writes the row, then re-runs POST_RELEASE_COMMAND, which must pass; otherwise every
# file the cut wrote is restored and the release is refused.
RELEASE_PENDING = {"tests/test_releases.py::test_latest_release_series_equal_engine_code"}
POST_RELEASE_COMMAND = [*SUITE_COMMAND, "tests/test_releases.py"]


def _failed_ids(out: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^FAILED (\S+)", out, flags=re.MULTILINE)]


def cut(version: str, run: Path, note: str, *, commit: str, root: Path = ROOT, runner=None) -> dict:
    """Cut a release with its own test-suite record (release-suite-run.md D1-D4): refuses a dirty tree or
    HEAD ≠ `commit`, runs the full suite in that checkout, refuses on any failure or error other than the disclosed
    (DISCLOSED_FAILURES) and release-pending (RELEASE_PENDING) ones, records the
    result in the releases.yaml row and the run file's meta.test_suite. It never tags: Richard tags the commit."""
    dirty = _git("status", "--porcelain", root=root)
    if dirty:
        raise SystemExit(f"REFUSED: working tree is dirty; commit or clean first:\n{dirty}")
    head = _git("rev-parse", "HEAD", root=root)
    if head != commit:
        raise SystemExit(f"REFUSED: HEAD {head} is not the release commit {commit}")
    runner = _run_suite if runner is None else runner
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    out, duration = runner(SUITE_COMMAND, root)
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
        row = release(version, run, note, root=root, tests=tests, figures=figs)
    except BaseException:
        restore()                       # a refused cut leaves the tree as it found it (code review, 19 Oct 2026)
        raise
    if tests.get("release_pending"):
        # the pending tests compare the engine with the latest release row: re-run them against the new row
        pout, pdur = runner(POST_RELEASE_COMMAND, root)
        post = {**parse_summary(pout), "duration_s": pdur, "command": " ".join(POST_RELEASE_COMMAND)}
        if post["failed"] + post["errors"] > 0:
            restore()
            raise SystemExit(f"REFUSED: post-release check (tests/test_releases.py against the new row): "
                             f"{post['failed']} failed, {post['errors']} errors; release rolled back")
        row["tests"] = dict(tests, post_release_check=post)
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
