"""Ticket 18 (0069, 0086): the 2021-23 gap under Shao (central) and under UCL's short-run merit-order
effect (methods-page sensitivity, preprint), and UCL's uplift over Shao's. Read from the run file's
`moe_crisis` block (gascf.moe_crisis_block). Gap keys: £bn, 2024 prices (CPIH)."""
from __future__ import annotations

SOURCE = ("O'Shea, Horne and Maslin (2025), UCL Open: Environment Preprints 290 v1 (not peer reviewed), "
          "Table 4 Total MOE, printed p.22 (PDF p.24); engine Shao uplift (Shao et al. 2022)")
YEARS = ("2021", "2022", "2023")


def _meta(label: str, field: str) -> dict:
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": "18",
            "run_field": f"moe_crisis.{field}", "source": SOURCE}


DECLARED = {
    "gap_2021_23_shao_gbp_bn": _meta("Gap 2021-23, Shao uplift (central), £bn 2024 prices",
                                     "years[2021-23].shao.national_gbp_m_nominal"),
    "gap_2021_23_ucl_gbp_bn": _meta("Gap 2021-23, UCL short-run uplift (sensitivity), £bn 2024 prices",
                                    "years[2021-23].ucl_stmoe.national_gbp_m_nominal"),
    "gap_2021_23_ucl_difference_gbp_bn": _meta("Gap 2021-23, UCL less Shao, £bn 2024 prices",
                                               "years[2021-23].{ucl_stmoe - shao}"),
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

    def gap(case: str) -> float:
        return sum(dfl.to_real(b["years"][y][case]["national_gbp_m_nominal"], int(y), 2024) for y in YEARS) / 1e3

    shao, ucl = gap("shao"), gap("ucl_stmoe")
    tot = [b["ucl_over_shao"]["total"][y] for y in YEARS]
    wind = [b["ucl_over_shao"]["wind"][y] for y in YEARS]
    return {"gap_2021_23_shao_gbp_bn": shao, "gap_2021_23_ucl_gbp_bn": ucl,
            "gap_2021_23_ucl_difference_gbp_bn": ucl - shao,
            "ucl_over_shao_total_low": min(tot), "ucl_over_shao_total_high": max(tot),
            "ucl_over_shao_wind_low": min(wind), "ucl_over_shao_wind_high": max(wind)}
