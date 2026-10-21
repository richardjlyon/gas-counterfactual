"""Spec §15.5 item 3: no silent fallbacks. Every fallback is declared in
`gascf.fallbacks.DECLARED` and recorded with its year and size when used (strand s27a)."""
import ast
import re
from pathlib import Path

import pytest

from gascf import fallbacks as fb
from gascf import fossil_like_for_like as L

SRC = Path(__file__).parents[1] / "src/gascf"
OWNED = ("fossil_like_for_like.py",)      # modules whose fallbacks s27a has declared
# patterns that pick a value for a year the source does not print
NEAREST = re.compile(r"min\(\w+\) if [\w.]*year\w* < min\(|max\(\w+ for \w+ in \w+ if \w+ <= \w+\)|"
                     r"\.get\(\s*year[^,]*,\s*[A-Z_]+\)")


def _record_names(texts: dict[str, str] | None = None) -> set[str]:
    """Fallback names the code uses: literal first arguments of fb.record and of
    require_recorded_carry_forward (keyed by file name for messages)."""
    if texts is None:
        texts = {p.name: p.read_text() for p in SRC.glob("*.py")}
    names = set()
    for pname, text in texts.items():
        for n in ast.walk(ast.parse(text)):
            if (isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "record"
                    and getattr(n.func, "value", None) is not None
                    and getattr(n.func.value, "id", None) in ("fb", "fallbacks")):
                a = n.args[0]
                assert isinstance(a, ast.Constant), f"{pname}:{n.lineno}: fallback name must be a literal"
                names.add(a.value)
            if isinstance(n, ast.Call) and "require_recorded_carry_forward" in (getattr(n.func, "attr", None),
                                                                    getattr(n.func, "id", None)):
                a = n.args[0]          # B-merge ruling (option a): naming it in the 0060 guard is a use
                assert isinstance(a, ast.Constant), f"{pname}:{n.lineno}: fallback name must be a literal"
                names.add(a.value)
    return names


def test_undeclared_fallback_is_refused():
    with pytest.raises(KeyError):
        fb.record("made_up_fallback", 2025, 1.0, "x")


def test_a_name_named_only_in_a_carry_forward_guard_counts_as_used_and_an_unused_name_does_not():
    """B-merge ruling (18 Oct 2026, option a): a declared fallback whose literal name is passed to
    require_recorded_carry_forward (ticket 24, 0060: the build refuses an unrecorded 2025 carry) is used,
    as is one passed to fb.record; a declared name that appears in neither is still reported unused."""
    texts = {"m.py": "from gascf import fallbacks as fb\n"
                     "fb.record(\"rec-name\", 2025, 1.0, \"x\")\n"
                     "_FB.require_recorded_carry_forward(\"guard-name\", {})\n"
                     "print(\"unused-name\")\n"}
    used = _record_names(texts)
    assert used == {"rec-name", "guard-name"}
    assert {"rec-name", "guard-name", "unused-name"} - used == {"unused-name"}


def test_every_recorded_name_is_declared_and_every_declared_name_is_used():
    names = _record_names()
    assert names <= set(fb.DECLARED), sorted(names - set(fb.DECLARED))
    assert set(fb.DECLARED) <= names, sorted(set(fb.DECLARED) - names)


@pytest.mark.parametrize("mod", OWNED)
def test_no_silent_nearest_year_fallback(mod):
    """Any nearest-year / default-value pick must have a fb.record within the next 6 lines."""
    lines = (SRC / mod).read_text().splitlines()
    bad = [f"{mod}:{i + 1}: {ln.strip()}" for i, ln in enumerate(lines) if NEAREST.search(ln)
           and not any("fb.record(" in x for x in lines[max(0, i - 2):i + 7])]
    assert not bad, "undeclared fallback(s):\n" + "\n".join(bad)
    assert sum(bool(NEAREST.search(ln)) for ln in lines) >= 3     # the scan is not vacuous


def test_coal_efficiency_2025_is_the_2015_2023_mean_and_recorded():
    from gascf import prices
    e = prices.dukes_efficiency()["coal"]
    assert 2025 not in e                                   # DUKES prints 0: no coal fleet
    mean = sum(e[y] for y in range(2015, 2024)) / 9
    assert L._eta_dukes("coal", 2025) == pytest.approx(mean / 100)
    assert L._eta_dukes("coal", 2024) == pytest.approx(e[2024] / 100)     # printed: no fallback
    rec = [f for f in fb.recorded() if f["name"] == "coal_efficiency_mean_2015_2023"]
    assert rec and rec[0]["year"] == 2025 and rec[0]["size"] == pytest.approx(mean)
    assert rec[0]["description"]


def test_recorded_entries_have_size_and_unit():
    L.lfl_year(2005)                                        # pre-NESO-mix year: several fallbacks
    rows = fb.recorded()
    assert rows
    for r in rows:
        assert r["name"] in fb.DECLARED and isinstance(r["year"], int) and r["unit"]
        assert r["size"] == r["size"]                     # not NaN
