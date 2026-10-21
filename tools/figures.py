"""Write figures.json from a v4 run file (ticket 02; 0006 and 0045: every printed figure from figures.json).

    python -m tools.figures <run.json> <figures.json>
"""
from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

BASES = ("measured", "modelled", "estimated")   # 0007: estimates labelled
STATUSES = ("SOURCED", "INTERIM_APPROVED", "PLACEHOLDER", "LOCATOR_TBC", "PENDING")   # ticket 29, 0100


def _modules():
    from tools import figures_keys
    return [importlib.import_module(f"tools.figures_keys.{m}") for m in figures_keys.MODULES]


def generate(run: dict, modules=None) -> dict:
    modules = _modules() if modules is None else modules
    keys = {}
    for m in modules:
        vals = m.values(run)
        undeclared = sorted(set(vals) - set(m.DECLARED))
        if undeclared:
            raise KeyError(f"{m.__name__}: undeclared key(s) {undeclared}")
        for name, meta in m.DECLARED.items():
            if name in keys:
                raise KeyError(f"{name}: declared twice ({m.__name__})")
            if meta.get("basis") not in BASES:
                raise ValueError(f"{name}: meta.basis must be one of {BASES}, got {meta.get('basis')!r}")
            if "status" in meta and meta["status"] not in STATUSES:
                raise ValueError(f"{name}: meta.status must be one of {STATUSES}, got {meta['status']!r}")
            keys[name] = {"value": vals[name], "meta": meta}
    from gascf.figures import PRICE_BASE_LABEL
    return {"meta": {"run_engine_version": run["meta"].get("engine_version"),
                     "release_tag": run["meta"].get("engine_version"), "price_base": PRICE_BASE_LABEL},
            "keys": keys}


def not_sourced(figures: dict) -> list[tuple[str, str]]:
    """(key, status) for every key whose status is not SOURCED, for the release record (ticket 29 item 6)."""
    return [(k, e["meta"].get("status", "UNSTATED")) for k, e in figures["keys"].items()
            if e["meta"].get("status") != "SOURCED"]


REGISTER_KEY = "annex_a_figure_register"
REGISTER_FIELDS = ("label", "units", "period", "price_base", "basis", "status", "provisional", "print")
REGISTER_META = {"label": "Annex A: figure register, one row per figures.json key (this row's own key excepted)",
                 "basis": "measured", "provisional": False, "ticket": "0122", "run_field": "figures.json keys[*].meta",
                 "units": "table", "period": "release", "status": "SOURCED", "print": True}


def figure_register(figures: dict) -> list[dict]:
    """Annex A (decision 0122, card item 2): every key in order with its label, units, period, price base, basis and
    status, read from the key metadata so the register and the figures can never disagree."""
    return [{"key": k, **{f: e["meta"][f] for f in REGISTER_FIELDS if e["meta"].get(f) not in (None, "")}}
            for k, e in figures["keys"].items() if k != REGISTER_KEY]


def assert_complete(figures: dict) -> None:
    """Release check (ticket 35, Richard 17 Oct 2026 21:00 BST): every figures.json key must carry a non-None value,
    whatever its status (SOURCED, PENDING, INTERIM_APPROVED or none). Raises ValueError naming every offending key,
    so the release build can refuse to write figures.json. A missing run-file block or field (whole or partial)
    prints None in the assembly; this is what stops the release."""
    none_keys = sorted(k for k, e in figures["keys"].items() if e.get("value") is None)
    if none_keys:
        raise ValueError("figures.json is incomplete: these keys are None (release refused): "
                         + ", ".join(none_keys))


def _commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], check=True,
                          capture_output=True, text=True).stdout.strip()


def write(run_path: Path, out_path: Path, modules=None, release: bool = False, commit: str | None = None) -> Path:
    """Write figures.json from a run file. In release mode (ticket 35) assert_complete refuses, before anything is
    written, if any key is None, so a missing run-file value stops the release; outside release mode None is kept.
    `commit`: the release commit, given by the rerun (gascf.rerun), whose source copy has no .git; else git HEAD."""
    raw = Path(run_path).read_bytes()
    out = generate(json.loads(raw), modules)
    if modules is None:          # the full figures file carries its own register (annex A, 0122)
        out["keys"][REGISTER_KEY] = {"value": figure_register(out), "meta": REGISTER_META}
    if release:
        assert_complete(out)
    out["meta"] |= {"run_file_sha256": hashlib.sha256(raw).hexdigest(), "commit": commit or _commit()}
    if release:
        # model-release first ticket 1: the release names the run file it read and its own version
        out["meta"] |= {"run_sha256": out["meta"]["run_file_sha256"], "version": out["meta"]["release_tag"]}
    Path(out_path).write_text(json.dumps(out, indent=1, allow_nan=False, ensure_ascii=False))
    return Path(out_path)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--release"]
    write(Path(args[0]), Path(args[1]), release="--release" in sys.argv)
