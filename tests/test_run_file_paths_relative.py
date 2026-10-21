"""Review ST1: the pricing and balancing_factors run-file blocks must write repo-relative paths, so the run-file
sha256 does not depend on the checkout and no box path leaks into a published file."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_SNIPPET = (
    "import json;from gascf import prices,balancing;"
    "from gascf import pricing_block as pb, balancing_factors_block as bfb;"
    "print(json.dumps({'p':prices.qep_dayahead_ratio_2010_25()['inputs'],"
    "'g':balancing.gb_over_ew_inputs(),'pb':pb.block({}),'bb':bfb.block({})},sort_keys=True))"
)

_NEEDED = [
    "data/raw/desnz_qep/s18a-QEP_table_321.xlsx",
    "data/raw/ofgem/s18a-WMI_gas_dayahead_monthly_YFsS4g98P.js",
    "data/raw/neso/s18c-demanddata_2002.csv",
    "data/raw/neso/s18c-demanddata_2003.csv",
    "data/raw/neso/s18c-demanddata_2004.csv",
    "data/raw/neso/s18c-demanddata_2005.csv",
    "reference/balancing_tar_2008_09_table22.json",
]


def _all_paths():
    from gascf import balancing, prices
    from gascf import balancing_factors_block, pricing_block
    out = [i["path"] for i in prices.qep_dayahead_ratio_2010_25()["inputs"]]
    out += [i["path"] for i in balancing.gb_over_ew_inputs()]
    out += [i["path"] for i in pricing_block.block({})["qep_dayahead_ratio"]["inputs"]]
    bb = balancing_factors_block.block({})
    out.append(bb["bsuos_basis_grossup"]["reference_file"]["path"])
    out += [i["path"] for i in bb["gb_over_ew"]["inputs"]]
    return out


def test_no_run_file_block_path_is_absolute():
    paths = _all_paths()
    for p in paths:
        assert not p.startswith("/"), p
    assert any(p.startswith("data/raw/") for p in paths)


def _run(root: Path) -> str:
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    return subprocess.run([sys.executable, "-c", _SNIPPET], cwd=root, env=env,
                          check=True, capture_output=True, text=True).stdout


def test_blocks_identical_bytes_from_two_checkout_roots(tmp_path):
    rootb = tmp_path / "checkout_b"
    shutil.copytree(REPO / "src", rootb / "src")
    for rel in _NEEDED:
        src = REPO / rel
        if src.exists():
            dst = rootb / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    assert _run(REPO) == _run(rootb)
