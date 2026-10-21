"""Run-file block `release_step_effects` (decision 0117, Richard Lyon, 19 Oct 2026): the release-step differences the
register names (figures-keys.md, tickets 09, 10 and 17), each as its effect on the gap by year (positive = more cost of
net zero), so figures keys read them from the run file alone.

- 09 B4 (0030): GO4's gas index on NBP before October 2009 (and its 2002-05 base mean g0 with it), against v4-s35's
  QEP join. Measured as the v4-s35 to s36 difference in GO4 (0108 item 1.10 option (a): not a QEP run, 0072), with
  F1's part taken out (F1 = u x the B4-scaled energy part, so the cross-term sits in F1, as the ticket 09 integrator
  split it), and GO7's VAT on it (5% x the domestic share). Nothing else in s36 moves GO4.
- 10 F1: Reliable Britain's balancing energy at its own feedback-raised gas price, on against off: GO4's own
  `gas_feedback_gbp_m` with GO7's VAT on it. Read, not rebuilt: F1 is central and GO4 is linear in it.
- 17 (0089): NZ5 with the nuclear CM column (variant D, central) less NZ5 with nuclear at peak (the v4-s35 rule,
  `nuclear_cm_column=None`), cash £m. One extra build.

The prior release is read from `releases.yaml` and its run file's sha256 is checked."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from gascf import bills as B
from gascf import same_in_both

ROOT = Path(__file__).resolve().parents[2]
PRIOR = "v4-s35"


def prior_release_run(version: str = PRIOR, releases: Path | None = None, root: Path = ROOT) -> dict:
    rows = json.loads(Path(releases or root / "releases.yaml").read_text())["releases"]
    hit = [r for r in rows if r["version"] == version]
    if len(hit) != 1:
        raise KeyError(f"{version}: {len(hit)} rows in releases.yaml")
    raw = (root / hit[0]["run_file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != hit[0]["run_sha256"]:
        raise ValueError(f"{version} run file {hit[0]['run_file']}: sha256 does not match releases.yaml")
    return json.loads(raw)


def _l(lines: list, ident: str) -> dict:
    hits = [x for x in lines if x["id"] == ident]
    if len(hits) != 1:
        raise KeyError(f"{len(hits)} lines {ident}")
    return hits[0]


def block(built: dict, prior: dict | None = None, build=None) -> dict:
    prior = prior_release_run() if prior is None else prior
    build = B.build if build is None else build
    peak_s = replace(B.CENTRAL, nuclear_cm_column=None)
    peak = build(peak_s)
    # Decision 0122 (card item 2, cm_nuclear_suspended_effect_2017_24_gbp_m): variant D less the same post-trade
    # column with no suspended agreement taken out, one more build.
    tw_s = replace(B.CENTRAL, nuclear_cm_column="post_trade_tw")
    tw = build(tw_s)
    vat = same_in_both.domestic_vat_rate()["rate"]
    years = {}
    for y in B.YEARS:
        go4, go7 = _l(built[y]["fossil"], "GO4"), _l(built[y]["fossil"], "GO7")
        go4_prior_real = _l(prior["bills"][str(y)]["gasonly"], "GO4")["national_gbp_m_real"]
        k = 1 + vat * go7["domestic_share"]
        f1 = -B.real(go4.get("gas_feedback_gbp_m", 0.0), y) * k
        total = -(B.real(go4["national_gbp_m_nominal"], y) - go4_prior_real) * k
        nz5 = _l(built[y]["netzero"], "NZ5")["national_gbp_m_nominal"] - \
            _l(peak[y]["netzero"], "NZ5")["national_gbp_m_nominal"]
        nz5_sus = _l(built[y]["netzero"], "NZ5")["national_gbp_m_nominal"] - \
            _l(tw[y]["netzero"], "NZ5")["national_gbp_m_nominal"]
        years[str(y)] = {"b4_gap_effect_gbp_m_real": total - f1, "f1_gap_effect_gbp_m_real": f1,
                         "release_difference_go4_gap_effect_gbp_m_real": total,
                         "cm_nuclear_nz5_change_gbp_m_nominal": nz5,
                         "cm_nuclear_suspended_nz5_change_gbp_m_nominal": nz5_sus}
    return {"years": years, "prior_release": prior["meta"].get("engine_version"),
            "nuclear_at_peak_settings": {"nuclear_cm_column": peak_s.nuclear_cm_column},
            "suspended_off_settings": {"nuclear_cm_column": tw_s.nuclear_cm_column},
            "money": "b4/f1: run price base £m (gap effect, VAT included); cm: cash £m (NZ5)",
            "note": "B4 = v4-s35 to s36 GO4 difference less F1's part; F1 = GO4.gas_feedback_gbp_m; both with GO7's "
                    "VAT. Positive = more cost of net zero.",
            "decisions": ["0030", "0072", "0089", "0108 item 1.10", "0117", "0122"]}


from gascf import export_v4 as _X  # noqa: E402

_X.register_block("release_step_effects", block)
