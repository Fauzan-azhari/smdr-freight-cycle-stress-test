"""Satu pintu untuk jalur data. Semua modul membaca dan menulis tabel lewat nama, bukan jalur tertulis.

Lapisan (data/README.md memuat diagram dan aturan tiap lapisan):
  00_registry   registri sumber, kamus, daftar celah data
  01_raw        teks apa adanya dari penyedia (CSV UTF-8)
  02_curated    tabel kurasi tangan beralamat sumber (asumsi, skenario, bukti, pembiayaan, keputusan)
  03_canonical  tabel analitik bentukan kode dan hasil kontrol mutu
  04_marts      keluaran model yang dikonsumsi deck, Excel, dan naskah
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
MARTS = os.path.join(DATA, "04_marts")
BASELINE = os.path.join(MARTS, "baseline")
RESULTS = os.path.join(MARTS, "results")

LAYOUT = {   # nama berkas -> folder (relatif terhadap data/)
    "scenario_results.csv": "04_marts/results",
    "cash_paths_monthly.csv": "04_marts/results",
    "covenant_quarterly.csv": "04_marts/results",
    "mitigation_tests.csv": "04_marts/results",
    "backtest.csv": "04_marts/results",
    "historical_test.csv": "04_marts/results",
    "cash_tornado.csv": "04_marts/results",
    "severity.csv": "04_marts/results",
    "baseline_quarters.csv": "04_marts/baseline",
    "baseline_ttm.csv": "04_marts/baseline",
    "baseline_bridge.csv": "04_marts/baseline",
    "opening_balance_2026-09-30.csv": "04_marts/baseline",
    "DCOILBRENTEU.csv": "01_raw/fred",
    "deck_dependencies.csv": "00_registry",
    "sources.csv": "00_registry",
    "lineage.csv": "00_registry",
    "dictionary.csv": "00_registry",
    "schemas.csv": "00_registry",
    "idx_line_items.csv": "01_raw/idx",
    "usdidr_monthly_provider.csv": "01_raw/fx",
    "brent_daily_fred.csv": "01_raw/fred",
    "capex_milestones.csv": "02_curated/financing",
    "cash_assumptions.csv": "02_curated/assumptions",
    "covenant_suite.csv": "02_curated/financing",
    "data_gaps.csv": "00_registry",
    "decisions.csv": "02_curated/decisions",
    "emerging_risk_evidence.csv": "03_canonical",
    "emerging_risk_evidence_src.csv": "02_curated/evidence",
    "emerging_risks.csv": "02_curated/evidence",
    "entities.csv": "02_curated/financing",
    "evidence.csv": "02_curated/evidence",
    "financing_events.csv": "03_canonical",
    "financing_facilities.csv": "02_curated/financing",
    "fs_checks.csv": "03_canonical/quality",
    "fs_known_exceptions.csv": "02_curated/quality",
    "fs_line_dictionary.csv": "00_registry",
    "fs_long.csv": "03_canonical",
    "fs_source_manifest.csv": "00_registry",
    "industry_narratives.csv": "02_curated/scenarios",
    "known_exceptions.csv": "02_curated/quality",
    "legacy_benchmark.csv": "02_curated/decisions",
    "legacy_decisions.csv": "02_curated/decisions",
    "macro_anchors.csv": "02_curated/scenarios",
    "macro_checks.csv": "03_canonical/quality",
    "macro_daily.csv": "03_canonical",
    "macro_forecast_vintages.csv": "02_curated/scenarios",
    "macro_ifrs9_vintage.csv": "02_curated/scenarios",
    "macro_known_exceptions.csv": "02_curated/quality",
    "macro_monthly.csv": "03_canonical",
    "macro_monthly_wide.csv": "03_canonical",
    "macro_scenario_definitions.csv": "02_curated/scenarios",
    "macro_source_manifest.csv": "00_registry",
    "mitigations.csv": "02_curated/assumptions",
    "network_exposure.csv": "03_canonical",
    "operating_assumptions.csv": "02_curated/assumptions",
    "operating_checks.csv": "03_canonical/quality",
    "operating_dictionary.csv": "00_registry",
    "operating_long.csv": "02_curated/evidence",
    "project_aliases.csv": "02_curated/financing",
    "project_status.csv": "02_curated/financing",
    "projects.csv": "02_curated/financing",
    "source_manifest.csv": "00_registry",
    "usdidr_monthly_fred.csv": "01_raw/fred",
    "wci_composite_weekly.csv": "01_raw/drewry",
    "zero_fill_rules.csv": "02_curated/assumptions",
}


def table(name):
    """Jalur lengkap tabel menurut namanya, mis. table("fs_long.csv")."""
    if name not in LAYOUT:
        raise KeyError("tabel tidak terdaftar di paths.LAYOUT: " + name)
    return os.path.join(DATA, LAYOUT[name], name)


def layer_of(name):
    return LAYOUT[name].split("/")[0]
