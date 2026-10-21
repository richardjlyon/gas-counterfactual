# gas-counterfactual, release v4-s37

The engine behind *Reliable Britain: What Britain's electricity would have cost on gas* (Richard Lyon, technical
paper to Report No. 1, version 1.0, 2026). It models Great Britain's electricity system year by year from 2002,
twice: as it was, and as it would have been with net-zero policy taken out and the same demand met by gas and the
other fossil plant Britain had. The difference, in 2024 prices (CPIH), is the paper's headline.

This repository is the frozen release the paper prints, tag `v4-s37`. Every figure in the paper comes from
`figures.json` here.

## How it ties to the paper

| | |
|---|---|
| Paper | Lyon, R. (2026). *Reliable Britain: What Britain's electricity would have cost on gas.* Technical paper to Report No. 1, version 1.0 |
| Release | `v4-s37`, cut 20 October 2026 |
| Cut commit (named in `figures.json` `meta.commit` and in `releases.yaml`) | `d2692e204efc77b873a4722bd64071817f3716bb` |
| Tag commit in the author's working repository (printed in the paper) | `fee0640c32eadccd883ef7f53af88e830507809c` |
| Run file `2026-10-20-s37.json`, SHA-256 | `d22d2d3df0cf2aa0f60f336f1477fb4350978ec94013c3071477b9b0c46c1a8e` |
| `figures.json`, SHA-256 (printed in the paper) | `e85a473f736530839f51fa4dd609f302fde3e6448717f647e0e75c877e890fe3` |

This public repository is a clean copy of the code at that release, published as a single commit. The two commit
hashes above belong to the author's working repository and do not exist here. What ties this copy to the paper is
the two SHA-256 hashes: the rerun below rebuilds both files and checks them.

What the clean copy leaves out of the working repository: the author's working notes and research folders, and
earlier releases' outputs that this release does not read. Comments in a few test and tool files had internal
ticket references and file paths replaced with `[internal ticket]` or `<internal path>`; no code that runs was
changed, and the rerun proves it.

## Rerun it

You need [uv](https://docs.astral.sh/uv/) (tested with uv 0.12.23 and Python 3.14; the project needs Python 3.12
or later), internet access for the first two steps, about 1.2 GiB of memory and about 20 minutes.

```bash
sha256sum -c SHA256SUMS                    # the files in this repository are as released
python3 fetch_data.py                      # fetch what can still be fetched of the 87 inputs not in this repository
uv sync --frozen                           # the exact package versions in uv.lock
uv run --frozen python -m gascf.rerun v4-s37 --bundle . --scratch rerun-out
```

The last command rebuilds the run file from the code and data, compares its SHA-256 with `releases.yaml`, writes
`figures.json` from it, compares every figure with the released `figures.json` and its SHA-256, and ends with
`RERUN PASS v4-s37` or `RERUN FAIL v4-s37 <n> mismatches`. The rebuilt files are in `rerun-out/`.

`fetch_data.py` (Python standard library only) reads `data/FETCH.tsv`, the list of the 87 inputs not in this
repository. It does not download all of them. For the 38 with a public download address, it downloads the file from
its publisher and checks it against the release's SHA-256. A file the publisher has changed since 10 October 2026 is
kept beside its place as `<name>.fetched` and reported. The other 49 have no public download address and are
reported as missing. Tested on 21 Oct 2026, it got 32 of the 87 in the bytes the release used; the other 55 cannot
be fetched in those bytes (see "Files not in this repository" below). The rerun passes only when every input is the
release's own copy, so from public sources alone it ends in `RERUN FAIL`; with the full input set, which reviewers
can have on request, it ends in `RERUN PASS v4-s37`.

The release's test suite (`tests/`, `uv run --frozen python -m pytest`) is shipped as code but is not part of the
rerun. Many tests read the author's working files, which are not in this copy, so it is not expected to pass here.
The suite was run at the cut commit: 1,264 passed and 1 failed, the failure disclosed in the paper (§5.3) and in
`releases.yaml`.

## Data and its licences

The run reads 273 data files under `data/`. 186 are in this repository, under their publishers' open licences.
The other 87 are not republished here: for 9 the publisher's terms do not allow it, and for 78 the terms are
unclear. They are listed with their publishers under "Files not in this repository" below. `fetch_data.py` fetches 32
of them in the bytes the release used; the other 55 cannot be fetched in those bytes. `data/raw/SOURCES.md` gives
each file's source and the cells read; `data/raw/SHA256SUMS` the release's hash of every staged source.

Attribution for the data in this repository:

- Contains public sector information licensed under the Open Government Licence v3.0 (DESNZ, BEIS, HMRC, HM
  Treasury, CMA, Ofgem, ONS, National Records of Scotland, legislation.gov.uk, Low Carbon Contracts Company).
- Contains BMRS data © Elexon Limited copyright and database right 2026. Licence:
  https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/
- Contains data from the NESO Data Portal, licensed under the NESO Open Data Licence v1.0
  (https://www.neso.energy/data-portal/ngeso-open-licence).
- Contains data from the European Environment Agency, CC BY 4.0.

## Files not in this repository

87 input files are not republished here: for 9 the publisher's terms do not allow it, and for 78 the terms are unclear. `fetch_data.py` fetches 32 of them in the bytes the release used (tested 21 Oct 2026). The other 55 cannot be fetched in those bytes:

- 5: the publisher has changed the file since the release used it;
- 1: the download address no longer resolves;
- 19: there is no public download address;
- 30: the file is a text extract the engine reads in place of the publisher's document, so no download gives these bytes.

Without those 55 the rerun does not reach the released hashes.

Reviewers can have the full set of input files on request: corrections@richardlyon.net.

| File | Publisher | Source address | Fetched in the release's bytes |
|---|---|---|---|
| `data/raw/boe/s18a-XUDLERS_XUAAERS_2004-2026.csv` | Bank of England | https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2004&Dateto=10/Oct/2026&SeriesCodes=XUDLERS,XUAAERS&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N | no: the publisher's file has changed |
| `data/raw/desnz_cm/NESO_ECR_2026.pdf` | NESO (website documents) | https://emrdeliverybody.nationalenergyso.com/IG/s/article/CM-Auction-Guidelines-and-Parameters | no: the publisher's file has changed |
| `data/raw/desnz_cm/NESO_ECR_2026_Data_Workbook.xlsx` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/desnz_cm/NESO_T-1_T-4_Auction_Guidelines_2026_v1.pdf` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/eex/emission-spot-primary-market-auction-report-2012-2025-data.zip` | EEX (European Energy Exchange) | https://www.eex.com/fileadmin/EEX/Downloads/Markets/Environmentals/EUA_Emission_Spot_Primary_Market_Auction_Report/Archive_Reports/emission-spot-primary-market-auction-report-2012-2025-data.zip | yes |
| `data/raw/nao_s18b/Electricity-Balancing-Services.txt` | National Audit Office | https://www.nao.org.uk/wp-content/uploads/2014/05/Electricity-Balancing-Services.pdf | no: text extract made from the publisher's document |
| `data/raw/nationalgas/Notice_of_Final_NTS_Exit_Capacity_Charges_effective_1_October_2026.pdf` | National Gas Transmission | https://www.nationalgas.com/sites/default/files/documents/Notice%20of%20Final%20NTS%20Exit%20Capacity%20Charges%20effective%201%20October%202026.pdf | yes |
| `data/raw/nationalgas/Notice_of_General_Non-Transmission_Services_Charges_October_2026.pdf` | National Gas Transmission | https://www.nationalgas.com/sites/default/files/documents/Notice%20of%20General%20Non-Transmission%20Services%20Charges%20October%202026.pdf | yes |
| `data/raw/nationalgas/October_2026_Charging_Information_Provision.pdf` | National Gas Transmission | https://www.nationalgas.com/sites/default/files/documents/October%202026%20Charging%20Information%20Provision.pdf | yes |
| `data/raw/nationalgas/SAP_PUBOB603.csv` | National Gas Transmission | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso/CMP308_Second_Workgroup_Consultation_2021-04-01.pdf` | NESO (website documents) | https://www.nationalgrideso.com/codes/connection-and-use-system-code-cusc/modifications/removal-bsuos-charges-generation | no: the address no longer resolves |
| `data/raw/neso/NESO_2025_Annual_Balancing_Costs_Data_Workbook.xlsx` | NESO (website documents) | https://www.neso.energy/document/362561/download | no: the publisher's file has changed |
| `data/raw/neso/tnuos/Final_TNUoS_Tariffs_2022-23_Tables.xlsx` | NESO (website documents) | https://www.neso.energy/document/235026/download | yes |
| `data/raw/neso/tnuos/Final_TNUoS_Tariffs_2023-24_Tables.xlsx` | NESO (website documents) | https://www.neso.energy/document/275726/download | yes |
| `data/raw/neso/tnuos/Final_TNUoS_Tariffs_2024-25_Report.pdf` | NESO (website documents) | https://www.neso.energy/document/301741/download | yes |
| `data/raw/neso/tnuos/Final_TNUoS_Tariffs_2024-25_Tables.xlsx` | NESO (website documents) | https://www.neso.energy/document/301731/download | yes |
| `data/raw/neso/tnuos/Final_TNUoS_Tariffs_2025-26_Report.pdf` | NESO (website documents) | https://www.neso.energy/document/353086/download | yes |
| `data/raw/neso/tnuos/Final_TNUoS_Tariffs_2025-26_Tables.xlsx` | NESO (website documents) | https://www.neso.energy/document/353061/download | yes |
| `data/raw/neso/tnuos/Final_TNUoS_Tariffs_2026-27_Report.pdf` | NESO (website documents) | https://www.neso.energy/document/376336/download | yes |
| `data/raw/neso/tnuos/Final_TNUoS_Tariffs_2026-27_Tables.xlsx` | NESO (website documents) | https://www.neso.energy/document/376341/download | yes |
| `data/raw/neso_s18b/neso_doc_125636.pdf` | NESO (website documents) | https://www.neso.energy/document/125636/download | yes |
| `data/raw/neso_s18b/neso_doc_125636.txt` | NESO (website documents) | https://www.neso.energy/document/125636/download | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_163311.pdf` | NESO (website documents) | https://www.neso.energy/document/163311/download | yes |
| `data/raw/neso_s18b/neso_doc_163311.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_186176.pdf` | NESO (website documents) | https://www.neso.energy/document/186176/download | yes |
| `data/raw/neso_s18b/neso_doc_186176.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_46611.pdf` | NESO (website documents) | https://www.neso.energy/document/46611/download | yes |
| `data/raw/neso_s18b/neso_doc_46611.txt` | NESO (website documents) | https://www.neso.energy/document/46611/download | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_47901.pdf` | NESO (website documents) | https://www.neso.energy/document/47901/download | yes |
| `data/raw/neso_s18b/neso_doc_47901.txt` | NESO (website documents) | https://www.neso.energy/document/47901/download | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_50181.pdf` | NESO (website documents) | https://www.neso.energy/document/50181/download | yes |
| `data/raw/neso_s18b/neso_doc_50181.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_50211.pdf` | NESO (website documents) | https://www.neso.energy/document/50211/download | yes |
| `data/raw/neso_s18b/neso_doc_50211.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_50671.pdf` | NESO (website documents) | https://www.neso.energy/document/50671/download | yes |
| `data/raw/neso_s18b/neso_doc_50671.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_50676.pdf` | NESO (website documents) | https://www.neso.energy/document/50676/download | yes |
| `data/raw/neso_s18b/neso_doc_50676.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_50691.pdf` | NESO (website documents) | https://www.neso.energy/document/50691/download | yes |
| `data/raw/neso_s18b/neso_doc_50691.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_60556.pdf` | NESO (website documents) | https://www.neso.energy/document/60556/download | yes |
| `data/raw/neso_s18b/neso_doc_60556.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_60696.pdf` | NESO (website documents) | https://www.neso.energy/document/60696/download | yes |
| `data/raw/neso_s18b/neso_doc_60696.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_60761.pdf` | NESO (website documents) | https://www.neso.energy/document/60761/download | yes |
| `data/raw/neso_s18b/neso_doc_60761.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s18b/neso_doc_60821.pdf` | NESO (website documents) | https://www.neso.energy/document/60821/download | yes |
| `data/raw/neso_s18b/neso_doc_60821.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-Final_TNUoS_Tariffs_2024-25_Report.txt` | NESO (website documents) | https://www.neso.energy/document/301741/download | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-Final_TNUoS_Tariffs_2025-26_Report.txt` | NESO (website documents) | https://www.neso.energy/document/353086/download | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-Final_TNUoS_Tariffs_2026-27_Report.txt` | NESO (website documents) | https://www.neso.energy/document/376336/download | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-MBSS_0607_March_2007.pdf` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_0607_March_2007.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-MBSS_DATA_MAR13.xls` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_DATA_MAR14.xls` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_DATA_MAR15.xls` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_DATA_MAR16.xlsx` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_DATA_MAR17.xlsx` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_MARCH_2013.pdf` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_MARCH_2013.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-MBSS_MARCH_2014_V2.pdf` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_MARCH_2014_V2.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-MBSS_MARCH_2016v1.pdf` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_MARCH_2016v1.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-MBSS_March_2017.pdf` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-MBSS_March_2017.txt` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-mbss_pack_2006_07.zip` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-mbss_pack_2013_14.zip` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-mbss_pack_2014_15.zip` | NESO (website documents) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/neso_s20d/s20d-neso_doc_114041_TNUoS_in_10_minutes_extract.md` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-neso_doc_137351_Final_TNUoS_2019-20_extract.md` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/neso_s20d/s20d-neso_doc_50276_Final_TNUoS_2017-18_extract.md` | NESO (website documents) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/ofgem/s18a-WMI_elec_dayahead_monthly_n9WSDfgxc.js` | Ofgem chart data hosted by everviz | https://app.everviz.com/inject/n9WSDfgxc/ | yes |
| `data/raw/ons_households/statswales_household_estimates_mid2012-2024.csv` | Welsh Government (StatsWales) | https://stats.gov.wales/en-GB/ce1308bb-9afd-4107-ae5a-38d3022c7181 | no: the publisher's file has changed |
| `data/raw/papers/s22-Shao_etal_2022_RO_wind_merit_order.pdf` | academic paper (author/publisher) | https://cronfa.swan.ac.uk/Record/cronfa58360/Download/58360__21196__ea76b280adbe432798f860fcf8868851.pdf | yes |
| `data/raw/s24/s24-NG_ALFs_2017-18_doc50281.pdf` | NESO (website documents) | https://www.neso.energy/document/50281/download | yes |
| `data/raw/s24/s24-NG_ALFs_2017-18_doc50281.txt` | NESO (website documents) | https://www.neso.energy/document/50281/download | no: text extract made from the publisher's document |
| `data/raw/s24/s24-NG_ALFs_2017-18_doc50296.pdf` | NESO (website documents) | https://www.neso.energy/document/50296/download | yes |
| `data/raw/s24/s24-NG_ALFs_2017-18_doc50296.txt` | NESO (website documents) | https://www.neso.energy/document/50296/download | no: text extract made from the publisher's document |
| `data/raw/s24/s24-NG_Final_ALFs_2016-17_doc50216.pdf` | NESO (website documents) | https://www.neso.energy/document/50216/download | yes |
| `data/raw/s24/s24-NG_Final_ALFs_2016-17_doc50216.txt` | NESO (website documents) | https://www.neso.energy/document/50216/download | no: text extract made from the publisher's document |
| `data/raw/s26a/s26a-Neuhoff_2022_EPRG2212_gas_price_limits.pdf` | academic paper (author/publisher) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/s36/ets-2025/ice-report-278-2025.csv` | ICE (Intercontinental Exchange) | https://www.ice.com/report/278 | no: the publisher's file has changed |
| `data/raw/s36/s36-albrizio2022_imf_wp22-143.txt` | academic paper (author/publisher) | see `data/raw/SOURCES.md` | no: text extract made from the publisher's document |
| `data/raw/s36/s36-casoli_manera_valenti_FEEM_NDL2022-045.pdf` | academic paper (author/publisher) | see `data/raw/SOURCES.md` | no: no public download address |
| `data/raw/s36/s36-krichene2005_IMF_WP0532.pdf` | academic paper (author/publisher) | https://www.imf.org/external/pubs/ft/wp/2005/wp0532.pdf | yes |
| `data/raw/s36/ucl-oshea/oshea-ucloe-preprint-290-v1.pdf` | academic paper (author/publisher) | see `data/raw/SOURCES.md` | no: no public download address |

## Layout

- `src/gascf/`: the engine. `gascf.rerun` is the rerun command; `gascf.export_v4` builds the run file.
- `tools/`: `tools/figures.py` writes `figures.json` from a run file.
- `data/raw/`: inputs as published. `data/figures/sourced.yaml`: figures quoted from published sources.
- `reference/`: engine reference tables. `out/v4/`: the two earlier run files this release's bridge table reads.
  `work/s24-closure-test/margins.json`: the plant-closure margins the engine reads.
- `releases.yaml`: the release register (every engine release, its commit and hashes).

## Licence

- Code: MIT, copyright Richard Lyon, 2026 (`LICENSE`).
- Outputs (the run files, `figures.json`, `data/figures/sourced.yaml`): CC BY 4.0, copyright Richard Lyon, 2026
  (`LICENSE-outputs`).
- Third-party data stays under its publisher's licence, as listed above.

Corrections: corrections@richardlyon.net. Each accepted correction is logged and credited in the paper's version 1.1.
