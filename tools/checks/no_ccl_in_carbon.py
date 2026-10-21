"""Ticket 37 (0090, option C): the standing fact-checker guard. No printed figure named or labelled for 'carbon'
may include the CCL (NZ8), and no figure named or labelled for the CCL may include a carbon line (NZ1c, NZ1c_tax,
NZ1c_price). The check reads the declared lines of every figures.json key and of the rows and columns of the five
tables (table_lines_2024, table_results_by_year, table_waterfall_2002_24, table_choice8, table_one_at_a_time).

Run by the release suite. `main(argv)` loads a figures.json, prints any violation and exits non-zero."""
from __future__ import annotations

import json
import sys

CARBON_LINES = ("NZ1c", "NZ1c_tax", "NZ1c_price")
CCL_LINE = "NZ8"
TABLE_KEYS = ("table_lines_2024", "table_results_by_year", "table_waterfall_2002_24",
              "table_choice8", "table_one_at_a_time")


def _is_carbon(name: str, label: str) -> bool:
    return "carbon" in f"{name} {label}".lower()


def _is_ccl(name: str, label: str) -> bool:
    # the key/row name carries the abbreviation (ccl_*); the label carries the full phrase. The bare word
    # "ccl" is NOT matched inside a descriptive label such as "excludes the CCL at its main rates".
    return "ccl" in name.lower() or "climate change levy" in f"{name} {label}".lower()


def _check(name: str, label: str, lines) -> str | None:
    s = set(lines or ())
    ident = f"{name} {label}".strip()
    if _is_carbon(name, label) and CCL_LINE in s:
        return f"{ident!r} is named/labelled carbon but includes the CCL ({CCL_LINE})"
    if _is_ccl(name, label) and (set(CARBON_LINES) & s):
        return f"{ident!r} is named/labelled CCL but includes a carbon line ({sorted(set(CARBON_LINES) & s)})"
    return None


def _source_lines(source: str) -> list[str]:
    s = (source or "").lower()
    if "nz8" in s:
        return ["NZ8"]
    if "nz1c" in s:
        return ["NZ1c"]
    return []


def _table_rows(key: str, entry: dict):
    """Yield (identifier, lines) for the rows/columns of a table key."""
    val = entry.get("value")
    meta = entry.get("meta", {})
    if key == "table_waterfall_2002_24" and isinstance(val, list):
        for r in val:
            yield r.get("key", ""), r.get("label", ""), r.get("lines")
    elif key == "table_lines_2024" and isinstance(val, list):
        for r in val:
            yield r.get("id", ""), r.get("label", ""), [r.get("id")]
    elif key == "table_results_by_year":
        for c in meta.get("columns", []):
            yield c.get("name", ""), "", _source_lines(c.get("source", ""))
    elif key in ("table_choice8", "table_one_at_a_time") and isinstance(val, list):
        for r in val:
            yield r.get("switch", r.get("label", "")), "", r.get("lines_moved")


def audit(figures: dict) -> list[str]:
    """Every violation (empty list = clean). Accepts the generate() payload or a bare {name: entry} keys map."""
    keys = figures.get("keys", figures)
    problems: list[str] = []
    for name, entry in keys.items():
        meta = entry.get("meta", {}) if isinstance(entry, dict) else {}
        p = _check(name, meta.get("label", ""), meta.get("lines"))
        if p:
            problems.append(p)
        if name in TABLE_KEYS:
            for rname, rlabel, lines in _table_rows(name, entry):
                p = _check(rname, rlabel, lines)
                if p:
                    problems.append(f"{name}: {p}")
    return problems


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: no_ccl_in_carbon.py <figures.json>")
        raise SystemExit(2)
    figures = json.loads(open(argv[0]).read())
    problems = audit(figures)
    for p in problems:
        print(f"CCL-IN-CARBON: {p}")
    if problems:
        raise SystemExit(1)
    print("no_ccl_in_carbon: clean")


if __name__ == "__main__":
    main()
