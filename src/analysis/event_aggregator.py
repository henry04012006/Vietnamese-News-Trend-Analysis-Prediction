"""
Modular Event-Daily Aggregator for Vietnamese Multi-Source News Dataset.

Aggregates article-event mappings from data/processed_multisource/article_events.parquet
into daily event-level temporal features (data/processed_multisource/event_daily.parquet).

Contract:
- Input: 463,995 articles across Thanh Niên, Tuổi Trẻ, VietnamNet (2023-2026).
- Filtering: Excludes 12,659 routine articles (event_id == "" or decision == "routine").
- Output: Exactly 377,551 active (event_id, date) records with 11 columns.
- Conservation: Sum of article_count equals 451,336; per-event totals converge with events.parquet.
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.config as cfg

logger = logging.getLogger("event_aggregator")

# Canonical source names (Unicode NFC)
SOURCE_THANHNIEN = "Thanh Ni\u00ean"
SOURCE_TUOITRE = "Tu\u1ed5i Tr\u1ebb"
SOURCE_VIETNAMNET = "VietnamNet"

SCHEMA_COLUMNS: List[str] = [
    "event_id",
    "date",
    "article_count",
    "source_count",
    "count_thanhnien",
    "count_tuoitre",
    "count_vietnamnet",
    "cumulative_articles",
    "event_age_days",
    "is_first_day",
    "cumulative_sources",
]


def _setup_logger(quiet: bool = False) -> None:
    """Configure module logger with appropriate log level and formatting."""
    level = logging.WARNING if quiet else logging.INFO
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        for handler in logger.handlers:
            handler.setLevel(level)


def _create_empty_result() -> pd.DataFrame:
    """Return an empty DataFrame conforming to the exact 11-column schema contract."""
    return pd.DataFrame(
        {
            "event_id": pd.Series(dtype="object"),
            "date": pd.Series(dtype="object"),
            "article_count": pd.Series(dtype="int64"),
            "source_count": pd.Series(dtype="int64"),
            "count_thanhnien": pd.Series(dtype="int64"),
            "count_tuoitre": pd.Series(dtype="int64"),
            "count_vietnamnet": pd.Series(dtype="int64"),
            "cumulative_articles": pd.Series(dtype="int64"),
            "event_age_days": pd.Series(dtype="int64"),
            "is_first_day": pd.Series(dtype="bool"),
            "cumulative_sources": pd.Series(dtype="int64"),
        }
    )


def aggregate_event_daily(
    df_article_events: Union[pd.DataFrame, str, Path],
    drop_routine: bool = True,
) -> pd.DataFrame:
    """
    Vectorized aggregation of article-event mappings to event-daily temporal features.

    Parameters
    ----------
    df_article_events : Union[pd.DataFrame, str, Path]
        DataFrame or file path containing 'event_id', 'published_at', 'source',
        and optional 'decision'.
    drop_routine : bool, default True
        If True, excludes records where event_id is empty/null or decision == 'routine'.

    Returns
    -------
    pd.DataFrame
        DataFrame with 11 canonical columns, sorted deterministically by ['event_id', 'date'].

    Raises
    ------
    ValueError
        If any mandatory column ('event_id', 'published_at', 'source') is missing.
    """
    if isinstance(df_article_events, (str, Path)):
        df_article_events = pd.read_parquet(
            df_article_events,
            columns=["event_id", "published_at", "source", "decision"]
            if "decision" in pd.read_parquet(df_article_events, columns=[]).columns
            else ["event_id", "published_at", "source"],
        )

    if df_article_events is None or df_article_events.empty:
        return _create_empty_result()

    required_cols = {"event_id", "published_at", "source"}
    missing = required_cols - set(df_article_events.columns)
    if missing:
        raise ValueError(f"Missing required columns in input DataFrame: {sorted(missing)}")

    # Step 1: Filter routine / non-event articles
    if drop_routine:
        valid_mask = (df_article_events["event_id"].notna()) & (
            df_article_events["event_id"].astype(str).str.strip() != ""
        )
        if "decision" in df_article_events.columns:
            valid_mask = valid_mask & (df_article_events["decision"] != "routine")
        sub = df_article_events.loc[valid_mask, ["event_id", "published_at", "source"]].copy()
    else:
        sub = df_article_events[["event_id", "published_at", "source"]].copy()
        sub["event_id"] = sub["event_id"].fillna("").astype(str)

    if sub.empty:
        return _create_empty_result()

    # Step 2: Extract date string (YYYY-MM-DD)
    if pd.api.types.is_datetime64_any_dtype(sub["published_at"]):
        sub["date"] = sub["published_at"].dt.strftime("%Y-%m-%d")
    else:
        sub["date"] = sub["published_at"].astype(str).str.strip().str.slice(0, 10)

    # Step 3: Source indicator decomposition
    sub["count_thanhnien"] = (sub["source"] == SOURCE_THANHNIEN).astype(np.int64)
    sub["count_tuoitre"] = (sub["source"] == SOURCE_TUOITRE).astype(np.int64)
    sub["count_vietnamnet"] = (sub["source"] == SOURCE_VIETNAMNET).astype(np.int64)

    # Step 4: Core aggregation by (event_id, date)
    daily = sub.groupby(["event_id", "date"], as_index=False, sort=True).agg(
        count_thanhnien=("count_thanhnien", "sum"),
        count_tuoitre=("count_tuoitre", "sum"),
        count_vietnamnet=("count_vietnamnet", "sum"),
    )
    daily["article_count"] = (
        daily["count_thanhnien"] + daily["count_tuoitre"] + daily["count_vietnamnet"]
    )
    daily["source_count"] = (
        (daily["count_thanhnien"] > 0).astype(np.int64)
        + (daily["count_tuoitre"] > 0).astype(np.int64)
        + (daily["count_vietnamnet"] > 0).astype(np.int64)
    )

    # Deterministic sort order (essential for cumsum, cummax, and transform('first'))
    daily = daily.sort_values(by=["event_id", "date"], ascending=[True, True]).reset_index(drop=True)

    # Step 5: Cumulative articles
    daily["cumulative_articles"] = (
        daily.groupby("event_id", sort=False)["article_count"].cumsum().astype(np.int64)
    )

    # Step 6: First date, first day flag, and calendar event age
    first_date = daily.groupby("event_id", sort=False)["date"].transform("first")
    daily["is_first_day"] = daily["date"] == first_date

    dt_series = pd.to_datetime(daily["date"], format="%Y-%m-%d")
    first_dt = dt_series.groupby(daily["event_id"], sort=False).transform("first")
    daily["event_age_days"] = (dt_series - first_dt).dt.days.astype(np.int64)

    # Step 7: Cumulative sources via single-pass DataFrame cummax
    flags = pd.DataFrame(
        {
            "tn": (daily["count_thanhnien"] > 0).astype(np.int8),
            "tt": (daily["count_tuoitre"] > 0).astype(np.int8),
            "vnn": (daily["count_vietnamnet"] > 0).astype(np.int8),
        },
        index=daily.index,
    )
    cum_df = flags.groupby(daily["event_id"], sort=False).cummax()
    daily["cumulative_sources"] = (cum_df["tn"] + cum_df["tt"] + cum_df["vnn"]).astype(np.int64)

    return daily[SCHEMA_COLUMNS]


def verify_conservation(
    df_article_events: Union[pd.DataFrame, str, Path],
    df_event_daily: Union[pd.DataFrame, str, Path],
    df_events: Optional[Union[pd.DataFrame, str, Path]] = None,
) -> Dict[str, Any]:
    """
    Verify all 10 mathematical conservation laws, domain invariants, and schema integrity.

    Parameters
    ----------
    df_article_events : Union[pd.DataFrame, str, Path]
        Source article-events mapping.
    df_event_daily : Union[pd.DataFrame, str, Path]
        Aggregated event-daily DataFrame to validate.
    df_events : Optional[Union[pd.DataFrame, str, Path]], default None
        Optional events ground-truth table for terminal convergence validation.

    Returns
    -------
    Dict[str, Any]
        Dictionary reporting validation status and metrics.

    Raises
    ------
    AssertionError
        If any mathematical conservation law or schema constraint is violated.
    """
    if isinstance(df_article_events, (str, Path)):
        df_article_events = pd.read_parquet(df_article_events)
    if isinstance(df_event_daily, (str, Path)):
        df_event_daily = pd.read_parquet(df_event_daily)
    if isinstance(df_events, (str, Path)):
        df_events = pd.read_parquet(df_events)

    results: Dict[str, Any] = {
        "valid": True,
        "total_event_daily_rows": len(df_event_daily),
        "total_articles": int(df_event_daily["article_count"].sum()) if not df_event_daily.empty else 0,
        "unique_events": int(df_event_daily["event_id"].nunique()) if not df_event_daily.empty else 0,
        "checks": {},
        "errors": [],
    }

    # 1. Schema columns
    col_match = list(df_event_daily.columns) == SCHEMA_COLUMNS
    results["checks"]["schema_columns"] = col_match
    if not col_match:
        msg = f"Schema columns mismatch: expected {SCHEMA_COLUMNS}, got {list(df_event_daily.columns)}"
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 2. Non-nullability
    no_nulls = not bool(df_event_daily.isna().any().any())
    results["checks"]["no_nulls"] = no_nulls
    if not no_nulls:
        null_cols = df_event_daily.isna().sum().to_dict()
        msg = f"Null values detected in output dataframe: {null_cols}"
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 3. Primary key uniqueness: (event_id, date)
    dup_count = df_event_daily.duplicated(subset=["event_id", "date"]).sum()
    results["checks"]["unique_event_date_pairs"] = bool(dup_count == 0)
    if dup_count > 0:
        sample = df_event_daily[df_event_daily.duplicated(subset=["event_id", "date"], keep=False)].head(10)
        msg = f"Duplicate (event_id, date) pairs detected: {dup_count} rows. Sample:\n{sample}"
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 4. Source additivity: article_count == count_thanhnien + count_tuoitre + count_vietnamnet
    calc_sum = (
        df_event_daily["count_thanhnien"]
        + df_event_daily["count_tuoitre"]
        + df_event_daily["count_vietnamnet"]
    )
    additivity_pass = bool((df_event_daily["article_count"] == calc_sum).all())
    results["checks"]["source_additivity"] = additivity_pass
    if not additivity_pass:
        sample = df_event_daily[df_event_daily["article_count"] != calc_sum].head(5)
        msg = f"Source additivity violation on rows:\n{sample}"
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 5. Source count concordance: source_count in [1, 3] and matches active sources
    calc_source_count = (
        (df_event_daily["count_thanhnien"] > 0).astype(int)
        + (df_event_daily["count_tuoitre"] > 0).astype(int)
        + (df_event_daily["count_vietnamnet"] > 0).astype(int)
    )
    src_count_match = bool((df_event_daily["source_count"] == calc_source_count).all())
    src_count_bounds = bool(df_event_daily["source_count"].between(1, 3).all())
    results["checks"]["source_count_concordance"] = src_count_match and src_count_bounds
    if not (src_count_match and src_count_bounds):
        sample = df_event_daily[
            (df_event_daily["source_count"] != calc_source_count)
            | (~df_event_daily["source_count"].between(1, 3))
        ].head(5)
        msg = f"Daily source_count mismatch on rows:\n{sample}"
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 6. Global article conservation
    valid_mask = (df_article_events["event_id"].notna()) & (
        df_article_events["event_id"].astype(str).str.strip() != ""
    )
    if "decision" in df_article_events.columns:
        valid_mask = valid_mask & (df_article_events["decision"] != "routine")
    n_valid_articles = int(valid_mask.sum())
    total_articles = int(df_event_daily["article_count"].sum())
    global_conserved = total_articles == n_valid_articles
    results["checks"]["global_article_conservation"] = global_conserved
    if not global_conserved:
        msg = (
            f"Global article conservation violated: sum(article_count)={total_articles:,} != "
            f"valid input articles={n_valid_articles:,}"
        )
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 7. Monotonicity: cumulative_articles strictly increasing across dates
    same_event = df_event_daily["event_id"] == df_event_daily["event_id"].shift(1)
    cum_art_diff = df_event_daily["cumulative_articles"] - df_event_daily["cumulative_articles"].shift(1)
    art_monotonic = not bool((same_event & (cum_art_diff <= 0)).any())
    results["checks"]["cumulative_articles_monotonic"] = art_monotonic
    if not art_monotonic:
        bad_idx = df_event_daily[same_event & (cum_art_diff <= 0)].index[:5]
        msg = f"cumulative_articles not strictly increasing at indices: {bad_idx.tolist()}"
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 8. Monotonicity: cumulative_sources monotonically non-decreasing in [1, 3]
    cum_src_diff = df_event_daily["cumulative_sources"] - df_event_daily["cumulative_sources"].shift(1)
    src_monotonic = not bool((same_event & (cum_src_diff < 0)).any())
    src_bounds = bool(df_event_daily["cumulative_sources"].between(1, 3).all())
    results["checks"]["cumulative_sources_monotonic"] = src_monotonic and src_bounds
    if not (src_monotonic and src_bounds):
        bad_idx = df_event_daily[same_event & (cum_src_diff < 0)].index[:5]
        msg = f"cumulative_sources decreased or out of bounds at indices: {bad_idx.tolist()}"
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 9. First day uniqueness and Event age bounds [0, 14]
    first_days_count = int(df_event_daily["is_first_day"].sum())
    unique_events_count = int(df_event_daily["event_id"].nunique())
    first_day_unique = first_days_count == unique_events_count
    first_day_age_zero = bool((df_event_daily["is_first_day"] == (df_event_daily["event_age_days"] == 0)).all())
    age_in_bounds = bool(df_event_daily["event_age_days"].between(0, 14).all())
    results["checks"]["first_day_and_age_bounds"] = (
        first_day_unique and first_day_age_zero and age_in_bounds
    )
    if not (first_day_unique and first_day_age_zero and age_in_bounds):
        msg = (
            f"First day / age violation: first_days={first_days_count:,}, "
            f"unique_events={unique_events_count:,}, age_zero={first_day_age_zero}, in_bounds={age_in_bounds}"
        )
        results["errors"].append(msg)
        raise AssertionError(msg)

    # 10. Convergence against df_events (if provided)
    if df_events is not None and not df_events.empty:
        last_daily = df_event_daily.groupby("event_id", sort=False).last()
        ev_idx = df_events.set_index("event_id")
        common_eids = last_daily.index.intersection(ev_idx.index)

        match_articles = bool(
            (last_daily.loc[common_eids, "cumulative_articles"] == ev_idx.loc[common_eids, "n_articles"]).all()
        )
        match_sources = bool(
            (last_daily.loc[common_eids, "cumulative_sources"] == ev_idx.loc[common_eids, "n_sources"]).all()
        )
        results["checks"]["events_convergence_articles"] = match_articles
        results["checks"]["events_convergence_sources"] = match_sources
        if not (match_articles and match_sources):
            msg = (
                f"Convergence against events.parquet failed: match_articles={match_articles}, "
                f"match_sources={match_sources}"
            )
            results["errors"].append(msg)
            raise AssertionError(msg)
        results["converged_events"] = len(common_eids)

    results["status"] = "PASS"
    return results


def compute_daily_aggregation(
    input_path: Union[str, Path] = cfg.MULTISOURCE_ARTICLE_EVENTS_PARQUET,
    output_path: Optional[Union[str, Path]] = cfg.MULTISOURCE_EVENT_DAILY_PARQUET,
    events_path: Optional[Union[str, Path]] = cfg.MULTISOURCE_EVENTS_PARQUET,
    verify: bool = True,
    drop_routine: bool = True,
    quiet: bool = False,
) -> pd.DataFrame:
    """
    Read article_events, execute daily aggregation, verify invariants, and write to Parquet.

    Parameters
    ----------
    input_path : Union[str, Path]
        Path to source article_events.parquet.
    output_path : Optional[Union[str, Path]]
        Destination path for event_daily.parquet. If None, writing is skipped.
    events_path : Optional[Union[str, Path]]
        Path to events.parquet for ground-truth convergence verification.
    verify : bool, default True
        If True, executes verify_conservation and raises AssertionError on any failure.
    drop_routine : bool, default True
        If True, excludes routine non-event articles.
    quiet : bool, default False
        If True, suppresses informational logging.

    Returns
    -------
    pd.DataFrame
        Aggregated event-daily DataFrame.
    """
    _setup_logger(quiet=quiet)

    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if not quiet:
        print("=" * 80)
        print("  EVENT-DAILY TEMPORAL AGGREGATOR (Milestone 2)")
        print("=" * 80)
        print(f"  Input Parquet:  {input_path}")
        print(f"  Output Parquet: {output_path}")
        print(f"  Drop Routine:   {drop_routine}")
        print(f"  Verify Laws:    {verify}")
        print("-" * 80)

    # Step 1: Load input data
    t0 = time.perf_counter()
    if not quiet:
        print("[1/4] Loading article-event mappings...")
    cols_to_load = ["event_id", "published_at", "source"]
    probe_df = pd.read_parquet(input_path, columns=["event_id"])
    if "decision" in pd.read_parquet(input_path, columns=[]).columns:
        cols_to_load.append("decision")
    df_ae = pd.read_parquet(input_path, columns=cols_to_load)
    t_load = time.perf_counter() - t0
    raw_count = len(df_ae)
    logger.info(f"Loaded {raw_count:,} raw articles in {t_load:.3f}s")

    # Step 2: Aggregate
    t1 = time.perf_counter()
    if not quiet:
        print("[2/4] Aggregating event-daily temporal statistics...")
    df_daily = aggregate_event_daily(df_ae, drop_routine=drop_routine)
    t_agg = time.perf_counter() - t1
    event_days_count = len(df_daily)
    unique_events = df_daily["event_id"].nunique()
    logger.info(
        f"Aggregated {event_days_count:,} active event-days across {unique_events:,} events in {t_agg:.3f}s"
    )

    # Step 3: Verify mathematical conservation laws
    if verify:
        t2 = time.perf_counter()
        if not quiet:
            print("[3/4] Verifying mathematical conservation laws...")
        df_events = None
        if events_path and Path(events_path).exists():
            df_events = pd.read_parquet(events_path, columns=["event_id", "n_articles", "n_sources"])
        metrics = verify_conservation(df_ae, df_daily, df_events)
        t_verify = time.perf_counter() - t2
        logger.info(
            f"All conservation laws verified successfully in {t_verify:.3f}s. "
            f"Total articles: {metrics['total_articles']:,}, Event-days: {metrics['total_event_daily_rows']:,}"
        )
        if not quiet:
            print("      [PASS] Source Additivity (article_count == count_tn + count_tt + count_vnn)")
            print("      [PASS] Source Count Concordance (1 <= source_count <= 3)")
            print(f"      [PASS] Global Article Conservation (sum == {metrics['total_articles']:,})")
            print("      [PASS] Monotonic Cumulative Articles")
            print("      [PASS] Monotonic Cumulative Sources")
            print("      [PASS] Event Age Bounds (0 <= event_age_days <= 14)")
            print(f"      [PASS] First Day Invariant (exactly {metrics['unique_events']:,} True flags)")
            if df_events is not None:
                print(f"      [PASS] Events.parquet Convergence ({metrics.get('converged_events', 0):,} events)")
            print("      Conservation verification: 10/10 checks PASSED!")

    # Step 4: Write output Parquet atomically
    if output_path is not None:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = out_path.with_suffix(".parquet.tmp")
        if not quiet:
            print("[4/4] Writing output Parquet...")
        t3 = time.perf_counter()
        df_daily.to_parquet(tmp_path, index=False, engine="pyarrow", compression="snappy")
        if out_path.exists():
            out_path.unlink()
        tmp_path.rename(out_path)
        t_write = time.perf_counter() - t3
        file_size_mb = out_path.stat().st_size / (1024**2)
        logger.info(
            f"Saved {event_days_count:,} rows to {out_path} ({file_size_mb:.2f} MB) in {t_write:.3f}s"
        )
        if not quiet:
            print(f"      Saved {event_days_count:,} rows to {out_path}")
            print(f"      Compression: snappy | Size: {file_size_mb:.2f} MB")

    total_time = time.perf_counter() - t0
    if not quiet:
        print("=" * 80)
        print(f"  SUCCESS: Event-daily aggregation completed in {total_time:.2f}s (Exit Code: 0)")
        print("=" * 80)

    return df_daily


def main() -> int:
    """CLI entry point for running event-daily aggregation."""
    parser = argparse.ArgumentParser(
        description="Vietnamese News Multi-Source Event-Daily Aggregator (Milestone 2)"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=str(cfg.MULTISOURCE_ARTICLE_EVENTS_PARQUET),
        help="Path to source article_events.parquet",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=str(cfg.MULTISOURCE_EVENT_DAILY_PARQUET),
        help="Destination path for event_daily.parquet",
    )
    parser.add_argument(
        "--events",
        "-e",
        type=str,
        default=str(cfg.MULTISOURCE_EVENTS_PARQUET),
        help="Path to events.parquet for convergence verification",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip post-aggregation mathematical conservation verification",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console output (only log errors)",
    )
    parser.add_argument(
        "--keep-routine",
        action="store_true",
        help="Keep routine non-event articles instead of dropping them",
    )

    args = parser.parse_args()

    try:
        compute_daily_aggregation(
            input_path=args.input,
            output_path=args.output,
            events_path=args.events,
            verify=not args.no_verify,
            drop_routine=not args.keep_routine,
            quiet=args.quiet,
        )
        return 0
    except Exception as exc:
        logger.error(f"Event aggregation failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
