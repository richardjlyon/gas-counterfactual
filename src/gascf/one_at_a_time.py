"""Run-file block `one_at_a_time` (ticket 28, decision 0095): every option of the range registry
(`bills.switch_settings()`, ranked) and of the methods page (`bills.METHOD_SWITCHES`, never in the range),
each alone with the rest central, as its own per-year gap and the bill lines it moves.

The `sensitivities` block keeps only each switch's per-year lowest and highest change, so a 2002-24 total
under one option cannot be read from it (the per-year min can come from different options in different
years). This block keeps every option apart. `bills.build` is cached on Settings, so the builds are the
ones `ranges()` and the methods page already make."""
from __future__ import annotations

from dataclasses import fields

from gascf import bills as B


def _settings_diff(s) -> dict:
    return {f.name: getattr(s, f.name) for f in fields(s) if getattr(s, f.name) != getattr(B.CENTRAL, f.name)}


def _lines(b: dict) -> dict:
    out = {x["id"]: x["national_gbp_m_nominal"] for x in b["netzero"] + b["fossil"]}
    out["NZ1c"] = b["nz1c"]["national_gbp_m_nominal"]
    return out


def _option(s, run: dict, central: dict) -> dict:
    moved = {}
    for y in B.YEARS:
        a, c = _lines(run[y]), _lines(central[y])
        moved[str(y)] = {k: a.get(k, 0.0) - c.get(k, 0.0) for k in sorted(set(a) | set(c))
                         if abs(a.get(k, 0.0) - c.get(k, 0.0)) > 1e-9}
    return {"settings": _settings_diff(s),
            "gap_real_bn": {str(y): run[y]["totals"]["gap_real_bn"] for y in B.YEARS},
            "lines_moved_gbp_m_nominal": moved}


def block(built: dict, build=None, ranked=None, methods=None) -> dict:
    build = B.build if build is None else build
    ranked = B.switch_settings() if ranked is None else ranked
    methods = B.METHOD_SWITCHES if methods is None else methods
    return {name: {label: [_option(s, build(s), built) for s in sets] for label, sets in reg.items()}
            for name, reg in (("ranked", ranked), ("methods_page", methods))}


from gascf import export_v4 as _X  # noqa: E402

_X.register_block("one_at_a_time", block)
