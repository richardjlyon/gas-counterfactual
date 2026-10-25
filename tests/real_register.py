"""The real-register builds the suite checks, made once per session in one fresh interpreter
([internal ticket], item 2).

The suite runs on the conftest fixture register, and the engine caches by register, so a check on the
real closure register (`reference/fossil_closures.yaml`, the register behind out/v4) has to build in a
separate interpreter. Three test files used to start one each and build the central case three times
over: `test_export_v4` (central 2025 gap), `test_household_by_step` (steps by window, v4-s35 settings
and the s36 central case) and `test_s32_cm` (NZ5 2025, central and kept-coal-needs-CM). This module
builds all of them in one interpreter and hands each test its part. The code each part runs is the
code its test ran before; only the interpreter is shared.

Not a test module (no `test_` prefix): pytest puts `tests/` on the path, so tests import it by name.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).parents[1]
WINDOWS = {"2006-2023": (2006, 2023), "2006-2024": (2006, 2024), "2006-2025": (2006, 2025), "2002-2025": (2002, 2025)}

_CODE = (
    "import json; from gascf import bills as B; from gascf import waterfall as W\n"
    "out = {}\n"
    # test_export_v4: the central 2025 gap (was `repr(...)` of the float; json keeps every digit too)
    "out['gap_2025'] = B.build()[2025]['totals']['gap_per_hh_real']\n"
    # test_household_by_step: steps by window for v4-s35 settings and the s36 central case
    "by_step = {}\n"
    "for name, s in (('s35', B.replace(B.CENTRAL, ic_basis='metered', nuclear_cm_column=None)), ('s36', B.CENTRAL)):\n"
    "    b, wf = B.build(s), W.waterfall(s)\n"
    f"    win = {WINDOWS!r}\n"
    "    hb = {y: B.on_household_bill(b[y], y, wf[y]) for y in B.YEARS}\n"
    "    by_step[name] = {'windows': {w: {n: sum(hb[y]['by_step'][n]['real_gbp_m'] for y in range(a, z + 1)) / 1e3\n"
    "                                     for n in range(1, 10)} for w, (a, z) in win.items()},\n"
    "                     'max_err': max(abs(sum(p['per_household_real'] for p in hb[y]['by_step'].values()) - hb[y]['value'])\n"
    "                                    for y in B.YEARS)}\n"
    "out['by_step'] = by_step\n"
    # test_s32_cm: NZ5 2025, central and the low side (kept coal needs CM)
    "b = B.build()[2025]; lo = B.build(B.replace(B.CENTRAL, cm_rule='extra_kept_coal'))[2025]\n"
    "out['cm_2025'] = {'nz5': B.val(b, 'NZ5'), 'low': B.val(lo, 'NZ5'), 'gw': b['cm']['cm_gw'],\n"
    "                  'kept': b['cm']['split_gw']['kept_coal_gw'], 'price': b['cm']['price_gbp_kw_yr']}\n"
    "print(json.dumps(out))"
)


def default_register() -> Path:
    from gascf.fossil_like_for_like import CLOSURES_FILE
    return Path(CLOSURES_FILE)


@lru_cache(maxsize=None)
def _built(register: str) -> dict:
    env = os.environ | {"GASCF_FOSSIL_CLOSURES": register}
    r = subprocess.run([sys.executable, "-W", "ignore", "-c", _CODE], env=env, cwd=ROOT, capture_output=True,
                       text=True, timeout=3000)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def real_register(register: Path | None = None) -> dict:
    """{'gap_2025': float, 'by_step': {'s35': ..., 's36': ...}, 'cm_2025': {...}} on `register`
    (default: the real closure register), built once per register per session."""
    return _built(str(Path(register or default_register()).resolve()))
