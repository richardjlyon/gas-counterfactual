"""Repo-relative paths for run-file blocks (review ST1). A run file is published, so the paths it records must be
relative to the repo root, not the box checkout, or its sha256 would change between checkouts and a box path would
leak. Low-level by design (no gascf imports) so prices, balancing and the block modules can all use it; export_v4
cannot host it because it imports prices and balancing."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def rel_to_root(p, root: Path = None) -> str:
    """The path of a registered input, relative to the repo root, for writing into the run file. Falls back to the
    string path for anything outside the root (e.g. a tmp path in a test), matching export_v4's closures convention."""
    p = Path(p)
    root = ROOT if root is None else Path(root)
    return str(p.relative_to(root)) if p.is_relative_to(root) else str(p)
