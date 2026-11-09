"""Central path and parameter configuration for Vietnamese News Trend Analysis."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Canonical processed data directories
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_MULTISOURCE_DIR = (
    DATA_DIR / "processed_multisource"
    if (DATA_DIR / "processed_multisource").exists()
    else PROCESSED_DIR
)

# Core Phase 2-4 dataset paths
MULTISOURCE_ARTICLES_CLEAN_PARQUET = PROCESSED_MULTISOURCE_DIR / "articles_clean.parquet"
MULTISOURCE_ARTICLE_EVENTS_PARQUET = PROCESSED_MULTISOURCE_DIR / "article_events.parquet"
MULTISOURCE_EVENTS_PARQUET = PROCESSED_MULTISOURCE_DIR / "events.parquet"
MULTISOURCE_COVERAGE_DAILY_CSV = PROCESSED_MULTISOURCE_DIR / "coverage_daily.csv"
MULTISOURCE_ARTICLES_REPORT_JSON = PROCESSED_MULTISOURCE_DIR / "articles_clean_report.json"
MULTISOURCE_EVENTS_CONFIG_JSON = PROCESSED_MULTISOURCE_DIR / "events_config.json"
MULTISOURCE_EVENT_DAILY_PARQUET = PROCESSED_MULTISOURCE_DIR / "event_daily.parquet"

# Output directories for reports and figures
REPORTS_DIR = PROJECT_ROOT / "reports"
PHASE4_FIGURES_DIR = REPORTS_DIR / "figures" / "phase4"

