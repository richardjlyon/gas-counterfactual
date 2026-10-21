"""The rerun command (model-release step 5): rebuild a frozen release's run file and figures.json from a clean copy of
the source, offline, and compare them with the released files.

    UV_OFFLINE=1 UV_CACHE_DIR=<bundle>/uv-cache uv run --frozen --offline python -m gascf.rerun <version> \
        [--bundle <bundle dir>] [--scratch <dir>]

It reads the release row from releases.yaml (in the source copy), rebuilds the run file with the released run date
(export_v4.build_payload), carries over the released meta.test_suite record (the cut writes it after the export; it
is a record of the suite, not a computed figure), writes it byte-for-byte as the cut does, and compares its sha256
with the row. It then writes figures.json from the rebuilt run through the release gate and compares every key with
the released figures.json: same key set, equal values (numbers to REL_TOL), and the sha256 with the row. One line per
mismatch; the last line is `RERUN PASS <version>` or `RERUN FAIL <version> <n> mismatches`. Exit 0 on pass, 1 on fail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REL_TOL = 1e-9
ABS_TOL = 1e-12


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run_bytes(payload: dict, released_meta: dict) -> bytes:
    """The run file as the release wrote it: export_v4.write's dump, then (if the release was cut with its suite
    record) release.cut's reload, meta.test_suite added, and its dump."""
    text = json.dumps(payload, indent=1, default=str, allow_nan=False)
    if "test_suite" in released_meta:
        p = json.loads(text)
        p["meta"]["test_suite"] = released_meta["test_suite"]
        text = json.dumps(p, indent=1, allow_nan=False)
    return text.encode()


def _equal(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


def compare_figures(new: dict, old: dict) -> list[str]:
    out = []
    nk, ok = set(new["keys"]), set(old["keys"])
    out += [f"figures key missing from the rerun: {k}" for k in sorted(ok - nk)]
    out += [f"figures key not in the release: {k}" for k in sorted(nk - ok)]
    for k in sorted(nk & ok):
        if not _equal(new["keys"][k].get("value"), old["keys"][k].get("value")):
            out.append(f"figures key differs: {k}: released {old['keys'][k].get('value')!r}, "
                       f"rerun {new['keys'][k].get('value')!r}")
    return out


def _row(version: str, root: Path) -> dict:
    reg = json.loads((root / "releases.yaml").read_text())
    rows = [r for r in reg["releases"] if r["version"] == version]
    if len(rows) != 1:
        raise SystemExit(f"RERUN FAIL {version} 1 mismatches\nno single releases.yaml row for {version}")
    return rows[0]


def rerun(version: str, *, root: Path = ROOT, bundle: Path | None = None, scratch: Path,
          build=None, figures_write=None) -> list[str]:
    """Returns the mismatch lines (empty = pass). `build(run_date)` and `figures_write(run_path, out_path, commit)`
    default to the engine's own export and release figures writer."""
    if build is None:
        from gascf.export_v4 import build_payload as build
    if figures_write is None:
        from tools.figures import write as _w

        def figures_write(rp, op, commit):
            return _w(rp, op, release=True, commit=commit)
    row = _row(version, root)
    base = bundle if bundle is not None else root
    run_old = base / (Path(row["run_file"]).name if bundle is not None else row["run_file"])
    fig_old = base / ("figures.json" if bundle is not None else row["figures_file"])
    old_run = json.loads(run_old.read_bytes())
    mism = []
    if _sha(run_old.read_bytes()) != row["run_sha256"]:
        mism.append(f"released run file sha256 is not the releases.yaml row's: {run_old}")
    scratch.mkdir(parents=True, exist_ok=True)
    new_bytes = run_bytes(build(old_run["meta"]["run_date"]), old_run["meta"])
    rp = scratch / Path(row["run_file"]).name
    rp.write_bytes(new_bytes)
    if _sha(new_bytes) != row["run_sha256"]:
        mism.append(f"run file sha256 differs: release {row['run_sha256']}, rerun {_sha(new_bytes)}")
    fp = scratch / "figures.json"
    figures_write(rp, fp, row["commit"])
    mism += compare_figures(json.loads(fp.read_text()), json.loads(fig_old.read_text()))
    if _sha(fp.read_bytes()) != row.get("figures_sha256"):
        mism.append(f"figures.json sha256 differs: release {row.get('figures_sha256')}, rerun {_sha(fp.read_bytes())}")
    return mism


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m gascf.rerun", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("version")
    ap.add_argument("--bundle", type=Path, help="release bundle (read-only): its run file and figures.json")
    ap.add_argument("--scratch", type=Path, default=Path("rerun-out"))
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    mism = rerun(a.version, bundle=a.bundle, scratch=a.scratch)
    for m in mism:
        print(m)
    print(f"RERUN PASS {a.version}" if not mism else f"RERUN FAIL {a.version} {len(mism)} mismatches")
    return 0 if not mism else 1


if __name__ == "__main__":
    sys.exit(main())
