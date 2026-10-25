"""s36 ticket 08 (0033, 0048; rulings of 17 Oct, R1): the gas-feedback range re-sourced to supply
studies, under v4-s35's names. Light tests (constants, comments, labels, registers); the 1/e scaling
and the central-gap guard are in tests/test_fossil_like_for_like.py (heavy).

Seams: `fossil_like_for_like` constants and source text, `bills.SWITCHES`, `data/raw/SOURCES.md`."""
import re

import pytest
from pathlib import Path

from gascf import fossil_like_for_like as L

ROOT = Path(__file__).parents[1]
SRC = (ROOT / "src/gascf/fossil_like_for_like.py").read_text()


def test_gas_elasticity_names_inverse_of_keys():
    """v4-s37, decision 0144 item 2A (Richard Lyon, 20 Oct 2026): e = supply + demand, by pair. Central Albrizio's
    0.06 + 0.169; the range row Krichene's world long-run 0.16 + 0.45; 'high' (0.06, supply only) kept for case B
    only (0048, open). v4-s36 pinned {central 0.16, low 0.34, high 0.06}, supply only."""
    # RB v1.1 A5 (0160): the held 1974-2004 pair (Krichene Table 2, VECM), never in the range
    assert L.GAS_ELASTICITY_PAIRS == {"central": (0.06, 0.169), "krichene_lr": (0.16, 0.45), "high": (0.06, 0.0),
                                      "krichene_lr_1974": (0.21, 0.06)}
    assert L.GAS_ELASTICITY == pytest.approx({"central": 0.229, "krichene_lr": 0.61, "high": 0.06, "krichene_lr_1974": 0.27})
    line = next(ln for ln in SRC.splitlines() if ln.startswith("GAS_ELASTICITY ="))
    assert "#" in line and "supply + demand" in line.split("#", 1)[1]


def test_switch_label_by_value():
    """The SWITCHES label names its pair (0144 item 4A: feedback rows rebuilt with paired elasticities)."""
    from gascf import bills as B
    lab = next(k for k in B.SWITCHES if k.startswith("gas-price feedback"))
    assert lab == "gas-price feedback (Krichene world long-run pair, 0.16 + 0.45 = 0.61)" == B.FEEDBACK_KRICHENE
    assert [s.gas_feedback for s in B.SWITCHES[lab]] == ["krichene_lr"]


def _block_above_gas_elasticity() -> str:
    lines = SRC.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("GAS_ELASTICITY ="))
    j = max(k for k in range(i) if lines[k].startswith("# s27a, spec §15.5 item 2"))
    return "\n".join(lines[j:i + 1])


def _docstring(fn) -> str:
    return fn.__doc__ or ""


def _no_table1_for_006(text: str) -> None:
    for ln in text.splitlines():
        if "0.06" in ln or "0.05" in ln:
            assert "Table 1" not in ln, ln
    assert "Neuhoff Table 1" not in text and "Andersen" not in text


def test_engine_comment_cites_krichene_2005_table5():
    """Rulings (b-items/ccl-key-mapping.md §5): the comment above GAS_ELASTICITY and the gas-feedback
    docstring cite Krichene (2005) Table 5 (printed p.20, PDF p.21) for 0.06; no "Table 1" next to
    0.06 or 0.05; no Neuhoff Table 1 or Andersen et al. as the source of 0.06."""
    for text in (_block_above_gas_elasticity(), _docstring(L.gas_feedback)):
        flat = re.sub(r"\s+", " ", text.replace("#", " "))
        assert re.search(r"Krichene \(?2005\)?,? .{0,60}Table 5 \(printed p\.20, PDF p\.21\)", flat), flat[:400]
        _no_table1_for_006(text)


def test_006_comment_reads_short_run_worst_case_word_for_word():
    """0.06 line says "the short-run worst case (12 months, no new investment)", as 22's rejection text."""
    flat = re.sub(r"\s+", " ", _block_above_gas_elasticity().replace("#", " "))
    assert "0.06" in flat and "the short-run worst case (12 months, no new investment)" in flat


def test_sources_md_krichene_table5():
    """The SOURCES.md Krichene (2005) row cites Table 5 (printed p.20, PDF p.21: natural gas supply,
    short-run price elasticity 0.06, SEM with the NEER, 1974-2004) for 0.06, and does not say Table 1
    corroborates it (Table 1 gives 0.05 for 1974-2004, t = 1.49)."""
    row = next(ln for ln in (ROOT / "data/raw/SOURCES.md").read_text().splitlines()
               if ln.startswith("| s36/s36-krichene2005_IMF_WP0532.pdf "))
    assert "Table 5" in row and "printed p.20, PDF p.21" in row and "0.06" in row and "NEER" in row
    assert "Table 1" not in row and "corroborates e0.06" not in row


def test_gas_option_names_not_renamed():
    """Ruled 17 Oct (R1): engine names kept; report keys map by value only. 0144 (v4-s37) removed 'low' (0.34,
    supply only) and added 'krichene_lr' (the paired range row); 'central', 'high' and 'none' keep their names."""
    assert L.GAS_FEEDBACK_RULES == ("central", "krichene_lr", "high", "none", "krichene_lr_1974")   # A5 held (0160)
    assert not hasattr(L, "RENAMED_GAS_FEEDBACK")
    assert not re.search(r"""["']e0\.\d+["']""", SRC)


def test_every_elasticity_source_cited_in_the_module_is_registered():
    """Each elasticity source file the module names exists and has a SOURCES.md row."""
    rows = (ROOT / "data/raw/SOURCES.md").read_text()
    for p in (L.KRICHENE_2005_PDF, L.CASOLI_2023_PDF, L.ALBRIZIO_2022_TXT, L.NEUHOFF_PDF):
        rel = p.relative_to(ROOT / "data/raw").as_posix()
        assert p.exists() and f"| {rel} |" in rows, rel


def test_every_gas_feedback_setting_has_a_range_option_name():
    """Found at the s36 release run (19 Oct 2026): the methods-page row M4 'no gas-price feedback' carries
    gas_feedback='none', which has no elasticity, and range.option_name raised KeyError. Every engine setting gets a
    name; 'none' is named as the feedback switched off, never as an elasticity."""
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.figures_keys import range as R
    names = {r: R.option_name("x", {"gas_feedback": r}) for r in L.GAS_FEEDBACK_RULES}
    assert names["none"] == "gas-price feedback off"
    assert names["central"] == "gas-price feedback, elasticity 0.229 (supply 0.06 + demand 0.169)"
    assert len(set(names.values())) == len(names)
