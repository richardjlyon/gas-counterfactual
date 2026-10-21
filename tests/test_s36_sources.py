"""Ticket 01: every s36 source file is in data/raw/s36/, registered in SHA256SUMS and SOURCES.md."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
S36 = RAW / "s36"
SOURCES_COMMIT = "9aeb0dc"   # 0029: reuse the s36 sources commit, data/raw/s36/** only


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def test_sources_commit_tree_present_byte_identical():
    """Every data/raw/s36 file of 9aeb0dc is here, byte for byte (0029)."""
    names = [n for n in _git("ls-tree", "-r", "--name-only", SOURCES_COMMIT, "data/raw/s36/").splitlines() if n]
    assert len(names) == 23   # the 23 appended SHA256SUMS lines
    for n in names:
        blob = subprocess.run(["git", "show", f"{SOURCES_COMMIT}:{n}"], cwd=ROOT, capture_output=True, check=True).stdout
        p = ROOT / n
        assert p.is_file(), n
        assert p.read_bytes() == blob, n


def _sums() -> dict[str, str]:
    out = {}
    for line in (RAW / "SHA256SUMS").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            h, name = line.split(None, 1)
            out[name.strip().removeprefix("./")] = h
    return out


def _s36_files() -> list[str]:
    return sorted(str(p.relative_to(RAW)) for p in S36.rglob("*") if p.is_file())


def test_every_s36_file_has_a_matching_sha256sums_row():
    sums = _sums()
    files = _s36_files()
    assert files
    for n in files:
        assert n in sums, f"{n}: no SHA256SUMS row"
        assert _sha(RAW / n) == sums[n], f"{n}: checksum differs"
    assert not [n for n in sums if n.startswith("s36/") and not (RAW / n).is_file()], "SHA256SUMS row for a missing file"


def _sources_rows() -> set[str]:
    rows = set()
    for line in (RAW / "SOURCES.md").read_text().splitlines():
        if line.startswith("| "):
            rows.add(line.split("|")[1].strip())
    return rows


def test_every_s36_file_has_a_sources_md_row():
    rows = _sources_rows()
    missing = [n for n in _s36_files() if n not in rows]
    assert not missing, f"no SOURCES.md row: {missing}"


# Staged Route A files (ticket 01), copied byte for byte from reports-programme; path under data/raw/s36 -> sha256.
ROUTE_A = {
    "ic-src/EMR_T-4_2015_Final_Results.pdf": "e85a0bef0dcfd7725d43eca715fab095711ee8381e4eee0917dcde0cfbadbafb",
    "ic-src/EMR_Final_Results_Report_T-4_2016_v2017.pdf": "2176d9623ba631a69276e91e04db888352050c491da40a3f26588e7485829dda",
    "ic-src/EMR_T-1_2017_Final_Results_Report.pdf": "119a5a7a34c813a253c8855886bc2dab9b9e9116775304a9e00a50a5470ce102",
    "ic-src/EMR_T-1_DY20-21_Final_Results.pdf": "87231bc2f90a915c7873bed87e8b3eb0312c5f26e3de3cdae817be929d4b48f9",
    "ic-src/EA_2017_Final_Results_Report.pdf": "5572ba1963ea08485e9f5772a30033de9b10e9ca3b1a8b191f2059a2fbc16188",
    "ic-src/20180802_annual_report_on_the_operation_of_cm_2017-18_final.pdf": "e1ce9e2b8b169024c3bc507ec157b57ea1ccc5e19f4a128d15a40b04ab8709f1",
    "ic-src/cmu_20261014.csv": "3ecf866a4889fcce90d1d22ea16641f242d8ea4d30a1d11866a6223a5ca6df67",
    "ets/uk-ets-phase2-auctions.csv": "0ccf58033ab5c9e6a611ebf438f6cf3769dd063609e49a07221cf2faa1806cbf",
    "ets/uk-ets-phase3-2012-auctions.csv": "188c6f18d243c2654640dcbf46dd6f3b4eedd1bf89c3325ced235f1a165b31d3",
    "ets/decc-ara-2012-13.pdf": "6a8c888f0886471c9b87e134b09056dac837f72586b1f91e480859bc6aa3ca83",
    "ets/final-greenhouse-gas-emissions-tables-2024.xlsx": "39849813643d6ed812c10030fb4fdcba98e598d7f8a890a446450c74baba66fa",
    "ets/ETS_Database_September_2026.xlsx": "6eeb040e380072049823b8919e27503bf60b90573c1d918a6e1fd741d9a23e5a",
    "ets-2025/ice-report-278-2025.csv": "4aab8a4a85d3389ee7c00623a6bd926a002deb41d2824e6b815df3a1154c9806",
    "ucl-oshea/oshea-ucloe-preprint-290-v1.pdf": "d7fa85732a2b30a3f0fa3160401fa888b1d336a79f7d11a3b27655c3f9fd09a6",
    "gas-demand/gas_demand_production.csv": "1886225eb7f0766a5adb3bffd232deb2e7f189e4772e7ad0a39b6240c4a99125",
    "desnz/Electricity_since_1920.xlsx": "c95cc17e446f76cd4333421be3e2e537fbaf81073c5795385d70a9ae7bdde8de",
    "fit/ofgem-fit-annual-report-scheme-year-5.pdf": "030a2682b9857534e70483abcd5226bbaf0d54acb50a0e8f67264475c8b54af0",
    "lec/lecissued_mar01_apr05[2].xls": "561e614436f8671ec76504a4d113266fa3982f81ac6e3b4d35c0ceb9c8701208",
    "lec/lecissued_apr05_todate.xls": "b9ab3578b68ccc216d1d96a9648608e5060e638c1997b872af1507ac85ca3b4a",
    "lec/renewable-lecs-april-2008---jan-2011_summary.xls": "80687683da628f318b15270477c8f2cfd28e99908bdfe09b08dd6ce48835c7af",
    "lec/summary_of_renewable_levy_exemption_certificates_lecs_from_april_2009_to_march_2014_0.xlsx": "3613e6ab28ecdcbb5c91aafa3fe03bbdc8d8fa83ef4389df303b0b185a647dea",
    "lec/summary_of_renewable_levy_exemption_certificates_lecs_from_april_2014_to_march_2015.xlsx": "de80f284a58c11f66c476cfa897048ca0d076fc7b46f6fde2b18721921d54256",
}


def test_route_a_files_staged_byte_for_byte():
    for name, h in ROUTE_A.items():
        p = S36 / name
        assert p.is_file(), name
        assert _sha(p) == h, name
