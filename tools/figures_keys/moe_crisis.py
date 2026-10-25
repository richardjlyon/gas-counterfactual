"""Ticket 18 (0069, 0086): the 2021-23 gap under the central uplift, under Shao's uplift in every month, and under
UCL's short-run merit-order effect (methods-page sensitivity, preprint), and UCL's uplift over Shao's. Read from
the run file's `moe_crisis` block (gascf.moe_crisis_block). Gap keys: £bn, 2024 prices (CPIH).

v4-s39 (card [internal ticket]): decision 0164 and its addendum (Richard Lyon, 21 Oct 2026: "The number has to be
accurate."; "b") make the central 2021-23 uplift the re-estimate on outturn, May 2021-Dec 2023 (M9 B); Jan-Apr
2021 keeps Shao. The block's `central` column is that; `shao` is Shao in every month (the v4-s38 central). The UCL
row is measured against the central (0164 addendum: the UCL row "is re-based on the new central")."""
from __future__ import annotations

SOURCE = ("O'Shea, Horne and Maslin (2025), UCL Open: Environment Preprints 290 v1 (not peer reviewed), "
          "Table 4 Total MOE, printed p.22 (PDF p.24); engine Shao uplift (Shao et al. 2022)")
YEARS = ("2021", "2022", "2023")


def _meta(label: str, field: str, ticket: str = "18") -> dict:
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": ticket,
            "run_field": f"moe_crisis.{field}", "source": SOURCE}


DECLARED = {
    "gap_2021_23_central_gbp_bn": _meta(
        "Gap 2021-23, central (Shao Jan-Apr 2021; price effect re-estimated on outturn May 2021-Dec 2023, 0164), "
        "£bn 2024 prices", "years[2021-23].central.national_gbp_m_nominal", "t_a6fd25b7"),
    "gap_2021_23_shao_gbp_bn": _meta("Gap 2021-23, Shao uplift in every month (the v4-s38 central), £bn 2024 prices",
                                     "years[2021-23].shao.national_gbp_m_nominal"),
    "gap_2021_23_ucl_gbp_bn": _meta("Gap 2021-23, UCL short-run uplift (sensitivity), £bn 2024 prices",
                                    "years[2021-23].ucl_stmoe.national_gbp_m_nominal"),
    "gap_2021_23_ucl_difference_gbp_bn": _meta("Gap 2021-23, UCL less central, £bn 2024 prices",
                                               "years[2021-23].{ucl_stmoe - central}"),
    "ucl_over_shao_total_low": _meta("UCL Table 4 over Shao's total uplift, lowest of 2021-23", "ucl_over_shao.total"),
    "ucl_over_shao_total_high": _meta("UCL Table 4 over Shao's total uplift, highest of 2021-23", "ucl_over_shao.total"),
    "ucl_over_shao_wind_low": _meta("UCL Table 4 over Shao's wind part, lowest of 2021-23", "ucl_over_shao.wind"),
    "ucl_over_shao_wind_high": _meta("UCL Table 4 over Shao's wind part, highest of 2021-23", "ucl_over_shao.wind"),
}


def values(run: dict) -> dict:
    from gascf import deflator_cpih as dfl
    b = run.get("moe_crisis")
    if b is None:      # ruling 17 Oct 2026 (a): a run file without the s36 block gives None; 35's check stops the release
        return {k: None for k in DECLARED}

    run_rule = (run.get("meta", {}).get("central_settings") or {}).get("moe_crisis", "shao")

    def gap(case: str) -> float:
        # A pre-v4-s39 block has no `central` column: its run's central WAS Shao (central_settings.moe_crisis 'shao'),
        # so Shao is that run's central. A run whose central is not Shao must carry `central` (KeyError otherwise):
        # never read Shao as the central of an M9 run (card [internal ticket]).
        if case == "central" and any("central" not in b["years"][y] for y in YEARS):
            if run_rule != "shao":
                raise KeyError(f"moe_crisis block has no 'central' column but the run's central rule is {run_rule!r}")
            case = "shao"
        return sum(dfl.to_real(b["years"][y][case]["national_gbp_m_nominal"], int(y), 2024) for y in YEARS) / 1e3

    central, shao, ucl = gap("central"), gap("shao"), gap("ucl_stmoe")
    tot = [b["ucl_over_shao"]["total"][y] for y in YEARS]
    wind = [b["ucl_over_shao"]["wind"][y] for y in YEARS]
    return {"gap_2021_23_central_gbp_bn": central, "gap_2021_23_shao_gbp_bn": shao, "gap_2021_23_ucl_gbp_bn": ucl,
            "gap_2021_23_ucl_difference_gbp_bn": ucl - central,
            "ucl_over_shao_total_low": min(tot), "ucl_over_shao_total_high": max(tot),
            "ucl_over_shao_wind_low": min(wind), "ucl_over_shao_wind_high": max(wind)}
