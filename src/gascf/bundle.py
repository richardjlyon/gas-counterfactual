"""Build a release bundle in the layout the fact-checker's review-report script reads (model-release step 7):

    <releases_root>/gas-counterfactual/<version>/
        source/        git archive of the release ref (the tag Richard makes), unpacked
        uv-cache/      a warmed uv cache, so `uv sync --frozen --offline` works with no network
        figures.json   the released figures file
        <run file>     the released run file (name as in the releases.yaml row)
        tests/         the gate's full suite output and junit, when the row pins them (suite_output; 5.1)
        RERUN.md       the rerun command and what it checks
        rerun.sh       the rerun command as a script (review-report runs `bash /bundle/rerun.sh` in a sealed box)
        SHA256SUMS     every file except itself, paths relative to the bundle, written last

    uv run --frozen python -m gascf.bundle <version> <ref> --uv-cache <dir> [--releases-root <dir>]

It never creates or moves a tag: <ref> is the tag Richard made (or, for a dry run, a commit).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = "gas-counterfactual"
RELEASES_ROOT = Path(os.environ.get("RELEASES_ROOT", "releases"))

RERUN_SH = """#!/bin/bash
# Rerun of {model} {version} (model-release step 5). review-report runs this in a sealed box (image
# a sealed container, no network) from a writable copy of source/, with BUNDLE set to this read-only bundle
# and UV_CACHE_DIR to a writable copy of uv-cache/. Ends with RERUN PASS {version} or RERUN FAIL {version} <n> mismatches.
set -euo pipefail
: "${{BUNDLE:?BUNDLE must point at the release bundle}}"
export UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never
unset GASCF_FOSSIL_CLOSURES          # the release reads the real closure register
uv sync --frozen --offline
exec uv run --frozen --offline python -m gascf.rerun {version} --bundle "$BUNDLE" --scratch "${{TMPDIR:-/tmp}}/rerun-{version}"
"""

RERUN_MD = """# Rerun {model} {version}

From a clean copy of `source/` (the git archive of the release tag), offline:

```bash
BUNDLE=<this folder> UV_CACHE_DIR=<a writable copy of uv-cache/> bash <this folder>/rerun.sh
```

which runs

```bash
UV_OFFLINE=1 uv sync --frozen --offline
UV_OFFLINE=1 uv run --frozen --offline python -m gascf.rerun {version} --bundle "$BUNDLE" --scratch <dir>
```

It rebuilds the run file (released run date, released suite record) and figures.json into the scratch folder,
compares the run file's sha256 with the releases.yaml row, compares every figures key with `figures.json` (same key
set, numbers to a relative 1e-9) and its sha256 with the row, prints one line per mismatch, and ends with
`RERUN PASS {version}` or `RERUN FAIL {version} <n> mismatches`. An export takes about 20 minutes and 1.2 GiB.

Check the bundle itself first: `sha256sum --quiet -c SHA256SUMS` in this folder.
"""

PROVENANCE_MD = """
## Provenance

The release was cut at commit {cut}: figures.json `meta.commit`, the releases.yaml row's `commit` and its suite
record (`tests.commit`) all name it, and the rerun writes figures.json with it. source/ is commit {src} (`{ref}`), the
commit the tag is to name. It adds only release files to the cut commit, checked when this bundle was built:

{between}
"""


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git_text(root: Path, *a) -> str:
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def release_only_diff(row: dict, ref: str, root: Path) -> list[str]:
    """Decision 0122 item 5: the release records (figures meta.commit, the releases.yaml row, the suite record) name the
    commit the cut ran at; the bundle's source/ is the commit that adds the release files to it. Refuse unless the cut
    commit is an ancestor of `ref` and every path changed between them is a release file (the row's run, clock and
    figures files, releases.yaml, CHANGELOG.md, RERUN.md, or the pull-request notes under work/). Returns those paths."""
    cut = row["commit"]
    ok = subprocess.run(["git", "merge-base", "--is-ancestor", cut, ref], cwd=root, capture_output=True)
    if ok.returncode != 0:
        raise SystemExit(f"REFUSED: the row's cut commit {cut} is not an ancestor of {ref}")
    changed = [p for p in _git_text(root, "diff", "--name-only", cut, ref).splitlines() if p]
    allowed = {"releases.yaml", "CHANGELOG.md", "RERUN.md", row.get("run_file"), row.get("clock_export_file"),
               row.get("figures_file"), *(row.get("suite_output") or {})}
    code = [p for p in changed if p not in allowed and not p.startswith("work/")]
    if code:
        raise SystemExit(f"REFUSED: {ref} changes more than release files after the cut commit {cut}: {code}")
    return changed


def _git_bytes(root: Path, *a) -> bytes:
    return subprocess.run(["git", *a], cwd=root, check=True, capture_output=True).stdout


def build(version: str, ref: str, *, uv_cache: Path, releases_root: Path = RELEASES_ROOT, root: Path = ROOT) -> Path:
    out = Path(releases_root) / MODEL / version
    if out.exists():
        raise SystemExit(f"REFUSED: {out} exists (a bundle is built once)")
    reg = json.loads(_git_bytes(root, "show", f"{ref}:releases.yaml"))
    (row,) = [r for r in reg["releases"] if r["version"] == version]
    between = release_only_diff(row, ref, root)
    src_commit = _git_text(root, "rev-parse", ref)
    out.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(_git_bytes(root, "archive", "--format=tar", ref))) as t:
        t.extractall(out / "source", filter="data")
    shutil.copytree(uv_cache, out / "uv-cache", symlinks=False)
    (out / Path(row["run_file"]).name).write_bytes(_git_bytes(root, "show", f"{ref}:{row['run_file']}"))
    (out / "figures.json").write_bytes(_git_bytes(root, "show", f"{ref}:{row['figures_file']}"))
    # card [internal ticket] (sweep 5.1): the gate's full suite output and junit, as pinned in the row
    for f, sha in (row.get("suite_output") or {}).items():
        b = _git_bytes(root, "show", f"{ref}:{f}")
        if hashlib.sha256(b).hexdigest() != sha:
            raise SystemExit(f"REFUSED: {f} at {ref} does not match its sha256 in the row")
        (out / "tests").mkdir(exist_ok=True)
        (out / "tests" / Path(f).name).write_bytes(b)
    (out / "RERUN.md").write_text(RERUN_MD.format(model=MODEL, version=version) + PROVENANCE_MD.format(
        cut=row["commit"], src=src_commit, ref=ref,
        between="\n".join(f"- `{p}`" for p in between) or "- nothing (the same commit)"))
    sh = out / "rerun.sh"
    sh.write_text(RERUN_SH.format(model=MODEL, version=version))
    sh.chmod(0o755)
    files = sorted(p for p in out.rglob("*") if p.is_file())
    (out / "SHA256SUMS").write_text("".join(f"{_sha(p)}  ./{p.relative_to(out)}\n" for p in files))
    return out


def check_layout(out: Path) -> list[str]:
    """The checks review-report makes before it runs anything, plus the bundle's named parts."""
    faults = []
    for p in ("source", "uv-cache"):
        if not (out / p).is_dir():
            faults.append(f"no {p}/")
    for p in ("figures.json", "RERUN.md", "rerun.sh", "SHA256SUMS"):
        if not (out / p).is_file():
            faults.append(f"no {p}")
    if (out / "rerun.sh").is_file() and not os.access(out / "rerun.sh", os.X_OK):
        faults.append("rerun.sh is not executable")
    if (out / "SHA256SUMS").is_file():
        r = subprocess.run(["sha256sum", "--quiet", "-c", "SHA256SUMS"], cwd=out, capture_output=True, text=True)
        if r.returncode != 0:
            faults.append(f"SHA256SUMS does not verify: {(r.stdout + r.stderr).strip()[:300]}")
    return faults


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gascf.bundle", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("version")
    ap.add_argument("ref", help="the release tag (Richard's), or a commit for a dry run")
    ap.add_argument("--uv-cache", type=Path, required=True)
    ap.add_argument("--releases-root", type=Path, default=RELEASES_ROOT)
    a = ap.parse_args(argv)
    out = build(a.version, a.ref, uv_cache=a.uv_cache, releases_root=a.releases_root)
    faults = check_layout(out)
    print(out)
    for f in faults:
        print(f)
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
