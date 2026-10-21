"""Run-file block `balancing_factors` (s36 ticket 48; EIC ruling 17 Oct 2026 18:50, after pass 5): the two
balancing baseline factors the engine computes, through the ticket 02 hook (export_v4.register_block).
bsuos_basis_grossup is 1 + internal / external balancing cost (FY2007/08), from two Table 22 reference rows;
gb_over_ew is GB over England and Wales demand, mean of 2002-05. Both unrounded; a block of its own."""
from __future__ import annotations

import hashlib

from gascf.pathutil import rel_to_root
from gascf import balancing as B
from gascf import export_v4 as X


def block(built: dict) -> dict:
    g = B.bsuos_basis_grossup()
    rows = B.table22_rows()
    fys = {rows[rid]["period"].removeprefix("FY") for rid in g["inputs"]}   # from the reference rows, not a literal (ST5)
    if len(fys) != 1:
        raise ValueError(f"Table 22 reference rows span different periods: {sorted(fys)}")
    return {
        "bsuos_basis_grossup": {
            "value": g["value"],
            "inputs": [{"id": rid, "value": rows[rid]["value"]} for rid in g["inputs"]],
            "fy": fys.pop(),
            "reference_file": {"path": rel_to_root(B.TABLE22_REF),
                               "sha256": hashlib.sha256(B.TABLE22_REF.read_bytes()).hexdigest()}},
        "gb_over_ew": {
            "value": B.gb_over_ew(),
            "by_year": {str(y): v for y, v in B.gb_over_ew_by_year().items()},
            "inputs": B.gb_over_ew_inputs()},
    }


X.register_block("balancing_factors", block)
