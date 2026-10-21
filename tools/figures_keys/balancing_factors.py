"""Ticket 48 (EIC ruling 17 Oct 2026 18:50, after pass 5): figures keys for the two balancing baseline factors the
engine computes. bsuos_basis_grossup_factor (1 + internal ÷ external balancing cost, FY2007/08) replaces the sourced
key CR-S048 (computed, so modelled; retired not reassigned), printed bare to 3 dp. Its sibling gb_over_ew_factor
(CR-S049, GB over E&W demand, 2002-05 mean) rides here on the lead builder's ruling, printed bare to 4 dp. Both read
the run-file balancing_factors block; block missing gives None (46-48 ruling). figures.assert_complete refuses any None key, whatever its status, when the release build writes figures.json (write(release=True)); a partly filled block is caught too.
Neither Table 22 input is a figures key: they are engine reference rows the fact-checker traces instead."""
from __future__ import annotations

_BSUOS_SOURCES = (
    "Ofgem, Transmission Annual Report for 2008-09 (TAR 2008-09, Ref 48/10), Table 22 - NGET Revenue Summary, PDF p.38",
    "engine reference rows tar_2008_09_t22_balancing_internal_2007_08 and tar_2008_09_t22_balancing_external_2007_08",
)
_GBEW_SOURCES = (
    "NESO Historic Demand Data 2002-05 (ND ÷ ENGLAND_WALES_DEMAND, each calendar year then the mean)",
)

DECLARED = {
    "rb.balancing.bsuos_basis_grossup_factor": {
        "label": "Gross-up of the incentivised balancing base to the BSUoS basis (system operator's internal "
                 "costs): 1 + internal ÷ external, 2007/08",
        "basis": "modelled", "provisional": True, "ticket": "48", "units": "ratio", "fy": "2007/08",
        "run_field": "balancing_factors.bsuos_basis_grossup.value", "was_claims_id": "CR-S048",
        "sources": list(_BSUOS_SOURCES), "status": "PENDING", "print": True, "print_dp": 3, "print_prefix": "",
        "notes": ["Not the GB gross-up (that is rb.balancing.gb_over_ew_factor)"]},
    "rb.balancing.gb_over_ew_factor": {
        "label": "England and Wales to GB gross-up: GB demand over England and Wales demand, mean of 2002-05",
        "basis": "modelled", "provisional": True, "ticket": "48", "units": "ratio", "period": "2002-2005",
        "year_basis": "calendar", "run_field": "balancing_factors.gb_over_ew.value", "was_claims_id": "CR-S049",
        "sources": list(_GBEW_SOURCES), "status": "PENDING", "print": True, "print_dp": 4, "print_prefix": "",
        "notes": ["Not the internal-cost gross-up (that is rb.balancing.bsuos_basis_grossup_factor)"]},
}


def values(run: dict) -> dict:
    out = {k: None for k in DECLARED}
    blk = run.get("balancing_factors")
    if not blk:          # block missing: None; figures.assert_complete refuses it in release mode (any None, any status)
        return out
    if blk.get("bsuos_basis_grossup"):
        out["rb.balancing.bsuos_basis_grossup_factor"] = blk["bsuos_basis_grossup"]["value"]
    if blk.get("gb_over_ew"):
        out["rb.balancing.gb_over_ew_factor"] = blk["gb_over_ew"]["value"]
    return out
