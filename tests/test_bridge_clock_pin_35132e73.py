"""Card [internal ticket] (Grok audit [internal ticket] / [internal ticket] item 1): the engine's stored Clock copy is the live Clock,
GitHub master 35132e73 (site/data files as served on 21 Oct 2026, equal to that commit's site/data by sha256,
current-online.md). The bridge table only: the headline does not read it (rows A and B cancel).
Expected hashes are the live files' own sha256, taken on 21 Oct 2026 ([internal ticket]), not the engine's output."""
import hashlib
from pathlib import Path

from gascf import bridge as BR

ROOT = Path(__file__).resolve().parents[1]
LIVE = {"combined": "ad2521ccc8c155405326be416d9ff8fb6fa51a50cb3b955b6074c10144f761e4",
        "timeseries": "648e8b5f5db0ba7aa408ad63c1047e63a353f52c41c20040056a60667eb1da8f"}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_bridge_reads_the_live_clock_copy():
    assert _sha(BR.CLOCK) == LIVE["combined"]
    assert _sha(BR.CLOCK_TIMESERIES) == LIVE["timeseries"]
    assert BR.SRC_CLOCK == "subsidy-clock-combined-annual-2026-10-21"
    assert BR.SRC_CLOCK_TS == "subsidy-clock-timeseries-2026-10-21"


def test_copies_are_registered():
    sums = (ROOT / "data/raw/SHA256SUMS").read_text()
    src = (ROOT / "data/raw/SOURCES.md").read_text()
    for p, h in ((BR.CLOCK, LIVE["combined"]), (BR.CLOCK_TIMESERIES, LIVE["timeseries"])):
        rel = "./" + str(Path(p).relative_to(ROOT / "data/raw"))
        assert f"{h}  {rel}" in sums
        assert f"| {rel[2:]} |" in src and "35132e73" in src
