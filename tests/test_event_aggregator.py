#!/usr/bin/env python3
"""
Comprehensive Unit and Integration Test Suite for Event Aggregator (Milestone 3 / Tier 5).

Covers:
- TestEventAggregatorSchema: Exact 11 columns, non-nullability, physical dtypes, primary key uniqueness, ISO dates.
- TestEventAggregatorConservation: Source additivity on 100% of rows, daily source counts in {1, 2, 3},
  per-event and global article conservation, cumulative articles and sources monotonicity and saturation.
- TestEventAggregatorTemporalDynamics: is_first_day True iff event_age_days == 0, calendar elapsed days
  with multi-day gaps, 14-day boundary cap.
- TestEventAggregatorIdempotencyAndEdgeCases: Execution determinism, input non-mutation, routine filtering
  (drop_routine True vs False), all-routine input, unsorted input determinism, timestamp format flexibility,
  singleton events, DataFrame vs Parquet path equivalence.
- TestEventAggregatorTamperDetection: Missing required columns, injected count/schema corruptions reliably
  trigger AssertionError across all 10 conservation checks.
- TestEventAggregatorLiveDataset: Live verification against data/processed_multisource/event_daily.parquet
  (377,551 rows, 451,336 articles, 320,842 events converging with events.parquet).
"""

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.config as cfg
from src.analysis.event_aggregator import (
    aggregate_event_daily,
    compute_daily_aggregation,
    verify_conservation,
    SCHEMA_COLUMNS,
    SOURCE_THANHNIEN,
    SOURCE_TUOITRE,
    SOURCE_VIETNAMNET,
)


class TestEventAggregatorSchema(unittest.TestCase):
    """Verifies schema contracts, canonical columns, dtypes, and nullability."""

    def setUp(self):
        """Create sample multi-event, multi-source synthetic DataFrame."""
        self.df_sample = pd.DataFrame([
            {
                "article_id": "art_001",
                "event_id": "E1",
                "published_at": "2026-03-01T08:00:00+07:00",
                "source": SOURCE_THANHNIEN,
                "decision": "cluster",
            },
            {
                "article_id": "art_002",
                "event_id": "E1",
                "published_at": "2026-03-01T09:30:00+07:00",
                "source": SOURCE_TUOITRE,
                "decision": "cluster",
            },
            {
                "article_id": "art_003",
                "event_id": "E2",
                "published_at": "2026-03-02T10:00:00+07:00",
                "source": SOURCE_VIETNAMNET,
                "decision": "cluster",
            },
        ])

    def test_01_canonical_11_columns_exact_order(self):
        """Output DataFrame must contain exactly the 11 canonical columns in exact order."""
        out = aggregate_event_daily(self.df_sample)
        self.assertEqual(list(out.columns), SCHEMA_COLUMNS)
        self.assertEqual(len(out.columns), 11)
        expected_order = [
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
        self.assertEqual(list(out.columns), expected_order)

    def test_02_physical_dtypes_conformance(self):
        """Output columns must match expected physical dtypes (int64, bool, string/object)."""
        out = aggregate_event_daily(self.df_sample)
        self.assertTrue(
            pd.api.types.is_string_dtype(out["event_id"]) or out["event_id"].dtype == object,
            f"event_id expected string/object dtype, got {out['event_id'].dtype}",
        )
        self.assertTrue(
            pd.api.types.is_string_dtype(out["date"]) or out["date"].dtype == object,
            f"date expected string/object dtype, got {out['date'].dtype}",
        )
        self.assertTrue(
            pd.api.types.is_bool_dtype(out["is_first_day"]),
            f"is_first_day expected bool, got {out['is_first_day'].dtype}",
        )

        int_cols = [
            "article_count",
            "source_count",
            "count_thanhnien",
            "count_tuoitre",
            "count_vietnamnet",
            "cumulative_articles",
            "event_age_days",
            "cumulative_sources",
        ]
        for col in int_cols:
            self.assertEqual(
                out[col].dtype,
                np.dtype("int64"),
                f"Column {col} expected int64, got {out[col].dtype}",
            )

    def test_03_zero_null_contract_across_all_columns(self):
        """Zero NaN or null values across all 11 columns, including zero-count sources."""
        # E2 only has VietnamNet, so count_thanhnien and count_tuoitre must be 0, not NaN
        out = aggregate_event_daily(self.df_sample)
        total_nulls = int(out.isna().sum().sum())
        self.assertEqual(total_nulls, 0, "Null values detected in output DataFrame")
        e2_row = out[out["event_id"] == "E2"].iloc[0]
        self.assertEqual(e2_row["count_thanhnien"], 0)
        self.assertEqual(e2_row["count_tuoitre"], 0)
        self.assertEqual(e2_row["count_vietnamnet"], 1)

    def test_04_primary_key_uniqueness_event_date(self):
        """Composite key (event_id, date) must be strictly unique across all rows."""
        out = aggregate_event_daily(self.df_sample)
        dup_count = int(out.duplicated(subset=["event_id", "date"]).sum())
        self.assertEqual(dup_count, 0, f"Found {dup_count} duplicate (event_id, date) pairs")

    def test_05_date_format_conformance_iso_date(self):
        """All values in the 'date' column must conform to ISO 8601 YYYY-MM-DD format."""
        out = aggregate_event_daily(self.df_sample)
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for d in out["date"]:
            self.assertTrue(bool(pattern.match(str(d))), f"Invalid date format: {d}")

    def test_06_empty_input_schema_contract(self):
        """Empty input DataFrame or None must return 0 rows with all 11 canonical columns."""
        for empty_input in [pd.DataFrame(), None]:
            out = aggregate_event_daily(empty_input)
            self.assertEqual(len(out), 0)
            self.assertEqual(list(out.columns), SCHEMA_COLUMNS)
            self.assertEqual(out["article_count"].dtype, np.dtype("int64"))
            self.assertEqual(out["is_first_day"].dtype, bool)


class TestEventAggregatorConservation(unittest.TestCase):
    """Verifies mathematical conservation laws, additivity, concordance, and monotonicity."""

    def test_07_source_additivity_on_all_rows(self):
        """article_count == count_thanhnien + count_tuoitre + count_vietnamnet on 100% of rows."""
        df = pd.DataFrame([
            {"article_id": "a1", "event_id": "EV1", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a2", "event_id": "EV1", "published_at": "2026-03-01T09:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a3", "event_id": "EV1", "published_at": "2026-03-01T10:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "a4", "event_id": "EV1", "published_at": "2026-03-01T11:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
            {"article_id": "a5", "event_id": "EV1", "published_at": "2026-03-02T12:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)
        calc_sum = daily["count_thanhnien"] + daily["count_tuoitre"] + daily["count_vietnamnet"]
        self.assertTrue((daily["article_count"] == calc_sum).all())

    def test_08_daily_source_counts_concordance_and_bounds(self):
        """source_count equals active sources on that date and stays strictly in {1, 2, 3}."""
        df = pd.DataFrame([
            # Day 1: 3 sources active
            {"article_id": "a1", "event_id": "E_CONC", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a2", "event_id": "E_CONC", "published_at": "2026-03-01T09:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "a3", "event_id": "E_CONC", "published_at": "2026-03-01T10:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
            # Day 2: 2 sources active
            {"article_id": "a4", "event_id": "E_CONC", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a5", "event_id": "E_CONC", "published_at": "2026-03-02T09:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            # Day 3: 1 source active
            {"article_id": "a6", "event_id": "E_CONC", "published_at": "2026-03-03T11:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)
        calc_sources = (
            (daily["count_thanhnien"] > 0).astype(int)
            + (daily["count_tuoitre"] > 0).astype(int)
            + (daily["count_vietnamnet"] > 0).astype(int)
        )
        self.assertTrue((daily["source_count"] == calc_sources).all())
        self.assertTrue(daily["source_count"].between(1, 3).all())
        self.assertEqual(daily.iloc[0]["source_count"], 3)
        self.assertEqual(daily.iloc[1]["source_count"], 2)
        self.assertEqual(daily.iloc[2]["source_count"], 1)

    def test_09_per_event_and_global_article_conservation(self):
        """Sum of daily article_count per event equals event total, and global sum equals input total."""
        df = pd.DataFrame([
            # Event A: 4 articles across 2 days
            {"article_id": "ea_1", "event_id": "EA", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "ea_2", "event_id": "EA", "published_at": "2026-03-01T09:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "ea_3", "event_id": "EA", "published_at": "2026-03-02T10:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
            {"article_id": "ea_4", "event_id": "EA", "published_at": "2026-03-02T11:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            # Event B: 3 articles on 1 day
            {"article_id": "eb_1", "event_id": "EB", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "eb_2", "event_id": "EB", "published_at": "2026-03-02T09:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
            {"article_id": "eb_3", "event_id": "EB", "published_at": "2026-03-02T10:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
            # Event C: 5 articles across 3 days
            {"article_id": "ec_1", "event_id": "EC", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "ec_2", "event_id": "EC", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "ec_3", "event_id": "EC", "published_at": "2026-03-03T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "ec_4", "event_id": "EC", "published_at": "2026-03-03T09:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
            {"article_id": "ec_5", "event_id": "EC", "published_at": "2026-03-03T10:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)

        # Global sum conservation
        self.assertEqual(int(daily["article_count"].sum()), 12)

        # Per-event conservation
        event_sums = daily.groupby("event_id")["article_count"].sum()
        self.assertEqual(int(event_sums["EA"]), 4)
        self.assertEqual(int(event_sums["EB"]), 3)
        self.assertEqual(int(event_sums["EC"]), 5)

    def test_10_terminal_cumulative_articles_equals_event_total(self):
        """Final row's cumulative_articles per event exactly matches total articles for that event."""
        df = pd.DataFrame([
            {"article_id": "e1", "event_id": "EV_TERM", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "e2", "event_id": "EV_TERM", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "e3", "event_id": "EV_TERM", "published_at": "2026-03-02T09:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "e4", "event_id": "EV_TERM", "published_at": "2026-03-03T08:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)
        last_row = daily.groupby("event_id").last().iloc[0]
        self.assertEqual(int(last_row["cumulative_articles"]), 4)

    def test_11_cumulative_sources_monotonicity_and_saturation(self):
        """cumulative_sources is non-decreasing over time and saturates at total unique sources."""
        df = pd.DataFrame([
            # Day 0: Thanh Niên joins -> cum_sources = 1
            {"article_id": "s1", "event_id": "E_SAT", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            # Day 1: Tuổi Trẻ joins -> cum_sources = 2
            {"article_id": "s2", "event_id": "E_SAT", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            # Day 2: Thanh Niên publishes again -> cum_sources stays 2
            {"article_id": "s3", "event_id": "E_SAT", "published_at": "2026-03-03T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            # Day 3: VietnamNet joins -> cum_sources = 3
            {"article_id": "s4", "event_id": "E_SAT", "published_at": "2026-03-04T08:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
            # Day 4: All three publish -> cum_sources stays 3
            {"article_id": "s5", "event_id": "E_SAT", "published_at": "2026-03-05T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)
        cum_sources_seq = daily["cumulative_sources"].tolist()
        self.assertEqual(cum_sources_seq, [1, 2, 2, 3, 3])
        # Monotonicity check
        diffs = np.diff(cum_sources_seq)
        self.assertTrue((diffs >= 0).all(), "cumulative_sources decreased!")
        self.assertEqual(daily.iloc[-1]["cumulative_sources"], 3)


class TestEventAggregatorTemporalDynamics(unittest.TestCase):
    """Verifies calendar event age calculation, first-day flag uniqueness, and lifespan caps."""

    def test_12_is_first_day_true_iff_event_age_zero(self):
        """is_first_day is True if and only if event_age_days == 0, exactly once per event."""
        df = pd.DataFrame([
            {"article_id": "a1", "event_id": "E1", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a2", "event_id": "E1", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "a3", "event_id": "E2", "published_at": "2026-03-03T08:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)
        self.assertTrue((daily["is_first_day"] == (daily["event_age_days"] == 0)).all())
        self.assertEqual(int(daily["is_first_day"].sum()), 2)

    def test_13_calendar_elapsed_days_with_multiday_gaps(self):
        """event_age_days accurately reflects calendar differences across multi-day publishing gaps."""
        df = pd.DataFrame([
            # E_GAP1: Day 0 (2026-03-01) and Day 3 (2026-03-04) -> age = [0, 3]
            {"article_id": "g1_1", "event_id": "E_GAP1", "published_at": "2026-03-01T10:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "g1_2", "event_id": "E_GAP1", "published_at": "2026-03-04T15:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            # E_GAP2: Day 0 (2026-05-10), Day 2 (2026-05-12), Day 5 (2026-05-15) -> age = [0, 2, 5]
            {"article_id": "g2_1", "event_id": "E_GAP2", "published_at": "2026-05-10T08:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
            {"article_id": "g2_2", "event_id": "E_GAP2", "published_at": "2026-05-12T09:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "g2_3", "event_id": "E_GAP2", "published_at": "2026-05-15T12:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)

        gap1 = daily[daily["event_id"] == "E_GAP1"]
        self.assertEqual(gap1["event_age_days"].tolist(), [0, 3])

        gap2 = daily[daily["event_id"] == "E_GAP2"]
        self.assertEqual(gap2["event_age_days"].tolist(), [0, 2, 5])

    def test_14_fourteen_day_boundary_cap(self):
        """Event active on Day 0 and Day 14 satisfies the 14-day boundary cap."""
        df = pd.DataFrame([
            {"article_id": "b1", "event_id": "E_CAP14", "published_at": "2026-01-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "b2", "event_id": "E_CAP14", "published_at": "2026-01-15T22:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)
        self.assertEqual(daily.iloc[1]["event_age_days"], 14)
        self.assertTrue(daily["event_age_days"].between(0, 14).all())
        # verify_conservation must pass on this boundary
        v = verify_conservation(df, daily)
        self.assertEqual(v["status"], "PASS")

    def test_15_cumulative_articles_strictly_increasing(self):
        """cumulative_articles is strictly increasing across consecutive active dates for each event."""
        df = pd.DataFrame([
            {"article_id": "m1", "event_id": "E_MONO", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "m2", "event_id": "E_MONO", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "m3", "event_id": "E_MONO", "published_at": "2026-03-03T08:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)
        diffs = daily["cumulative_articles"].diff().dropna()
        self.assertTrue((diffs > 0).all(), "cumulative_articles not strictly increasing")


class TestEventAggregatorIdempotencyAndEdgeCases(unittest.TestCase):
    """Verifies execution determinism, routine filtering, singleton events, and edge cases."""

    def test_16_idempotency_deterministic_execution(self):
        """Running aggregate_event_daily twice on the same DataFrame yields identical DataFrames."""
        df = pd.DataFrame([
            {"article_id": "a1", "event_id": "E1", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a2", "event_id": "E1", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "a3", "event_id": "E2", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
        ])
        df_copy = df.copy()
        res1 = aggregate_event_daily(df)
        res2 = aggregate_event_daily(df)

        pd.testing.assert_frame_equal(res1, res2, check_exact=True)
        # Ensure input DataFrame was not mutated
        pd.testing.assert_frame_equal(df, df_copy, check_exact=True)

    def test_17_routine_article_filtering_exclusion(self):
        """Routine articles (decision=='routine', empty/null event_id) safely excluded when drop_routine=True."""
        df = pd.DataFrame([
            # Valid cluster articles
            {"article_id": "v1", "event_id": "E_REAL", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "v2", "event_id": "E_REAL", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            # Routine articles to exclude
            {"article_id": "r1", "event_id": "", "published_at": "2026-03-01T09:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "routine"},
            {"article_id": "r2", "event_id": None, "published_at": "2026-03-01T10:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "routine"},
            {"article_id": "r3", "event_id": "   ", "published_at": "2026-03-02T11:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "routine"},
            {"article_id": "r4", "event_id": "E_ROUTINE", "published_at": "2026-03-02T12:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "routine"},
        ])
        daily = aggregate_event_daily(df, drop_routine=True)
        self.assertEqual(len(daily), 2)
        self.assertEqual(daily["event_id"].unique().tolist(), ["E_REAL"])
        self.assertEqual(int(daily["article_count"].sum()), 2)

        # When drop_routine=False, routine articles are retained under event_id == ''
        daily_with_routine = aggregate_event_daily(df, drop_routine=False)
        self.assertIn("", daily_with_routine["event_id"].values)

    def test_18_all_routine_input_returns_empty(self):
        """Input consisting purely of routine articles returns empty 11-column DataFrame."""
        df = pd.DataFrame([
            {"article_id": "r1", "event_id": "", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "routine"},
            {"article_id": "r2", "event_id": None, "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "routine"},
        ])
        daily = aggregate_event_daily(df, drop_routine=True)
        self.assertEqual(len(daily), 0)
        self.assertEqual(list(daily.columns), SCHEMA_COLUMNS)

    def test_19_unsorted_input_determinism(self):
        """Input rows in shuffled / reverse order produce output identical to sorted input."""
        df_ordered = pd.DataFrame([
            {"article_id": "a1", "event_id": "E1", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a2", "event_id": "E1", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "a3", "event_id": "E2", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_VIETNAMNET, "decision": "cluster"},
        ])
        df_shuffled = df_ordered.iloc[::-1].reset_index(drop=True)

        res_ordered = aggregate_event_daily(df_ordered)
        res_shuffled = aggregate_event_daily(df_shuffled)

        pd.testing.assert_frame_equal(res_ordered, res_shuffled, check_exact=True)

    def test_20_timestamp_formats_flexibility(self):
        """Supports ISO 8601 with offset, space-separated string, and pd.Timestamp."""
        df = pd.DataFrame([
            {"article_id": "t1", "event_id": "E_TIME", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "t2", "event_id": "E_TIME", "published_at": "2026-03-01 14:30:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
            {"article_id": "t3", "event_id": "E_TIME", "published_at": pd.Timestamp("2026-03-01 20:00:00"), "source": SOURCE_VIETNAMNET, "decision": "cluster"},
        ])
        daily = aggregate_event_daily(df)
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily.iloc[0]["date"], "2026-03-01")
        self.assertEqual(daily.iloc[0]["article_count"], 3)
        self.assertEqual(daily.iloc[0]["source_count"], 3)

    def test_21_singleton_event_initial_state(self):
        """Singleton event (1 article) initializes Day 0 base state with exact metrics."""
        df = pd.DataFrame([
            {
                "article_id": "art_single",
                "event_id": "E_SINGLETON",
                "published_at": "2026-04-10T11:00:00+07:00",
                "source": SOURCE_THANHNIEN,
                "decision": "cluster",
            }
        ])
        daily = aggregate_event_daily(df)
        self.assertEqual(len(daily), 1)
        row = daily.iloc[0]
        self.assertEqual(row["event_id"], "E_SINGLETON")
        self.assertEqual(row["date"], "2026-04-10")
        self.assertEqual(row["article_count"], 1)
        self.assertEqual(row["source_count"], 1)
        self.assertEqual(row["count_thanhnien"], 1)
        self.assertEqual(row["count_tuoitre"], 0)
        self.assertEqual(row["count_vietnamnet"], 0)
        self.assertEqual(row["cumulative_articles"], 1)
        self.assertEqual(row["event_age_days"], 0)
        self.assertTrue(row["is_first_day"])
        self.assertEqual(row["cumulative_sources"], 1)

    def test_22_input_format_equivalence_dataframe_vs_parquet_path(self):
        """Calling aggregate_event_daily with DataFrame vs file path produces identical output."""
        df = pd.DataFrame([
            {"article_id": "a1", "event_id": "E1", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a2", "event_id": "E1", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
        ])
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            df.to_parquet(tmp_path, index=False)
            res_df = aggregate_event_daily(df)
            res_file = aggregate_event_daily(tmp_path)
            pd.testing.assert_frame_equal(res_df, res_file, check_exact=True)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_22b_compute_daily_aggregation_pipeline_flow(self):
        """compute_daily_aggregation reads parquet, aggregates, verifies, and writes output."""
        df_input = pd.DataFrame([
            {"article_id": "a1", "event_id": "E1", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a2", "event_id": "E1", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
        ])
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as in_tmp, \
             tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as out_tmp:
            in_path = Path(in_tmp.name)
            out_path = Path(out_tmp.name)
        try:
            df_input.to_parquet(in_path, index=False)
            df_res = compute_daily_aggregation(
                input_path=in_path,
                output_path=out_path,
                events_path=None,
                verify=True,
                drop_routine=True,
                quiet=True,
            )
            self.assertEqual(len(df_res), 2)
            self.assertTrue(out_path.exists())
            df_disk = pd.read_parquet(out_path)
            pd.testing.assert_frame_equal(df_res, df_disk, check_exact=True)
        finally:
            if in_path.exists():
                in_path.unlink()
            if out_path.exists():
                out_path.unlink()

    def test_22c_compute_daily_aggregation_missing_input_raises_filenotfound(self):
        """compute_daily_aggregation raises FileNotFoundError when input path does not exist."""
        non_existent = Path("non_existent_article_events_file.parquet")
        with self.assertRaises(FileNotFoundError):
            compute_daily_aggregation(input_path=non_existent, quiet=True)


class TestEventAggregatorTamperDetection(unittest.TestCase):
    """Verifies error handling, required columns validation, and tamper detection in verify_conservation."""

    def setUp(self):
        """Create valid baseline synthetic dataset and its aggregation."""
        self.df_valid = pd.DataFrame([
            {"article_id": "a1", "event_id": "E1", "published_at": "2026-03-01T08:00:00+07:00", "source": SOURCE_THANHNIEN, "decision": "cluster"},
            {"article_id": "a2", "event_id": "E1", "published_at": "2026-03-02T08:00:00+07:00", "source": SOURCE_TUOITRE, "decision": "cluster"},
        ])
        self.daily_valid = aggregate_event_daily(self.df_valid)

    def test_23_missing_required_columns_raises_value_error(self):
        """Missing mandatory columns ('event_id', 'published_at', 'source') raises ValueError."""
        # Missing published_at
        df_no_pub = pd.DataFrame([{"event_id": "E1", "source": SOURCE_THANHNIEN}])
        with self.assertRaises(ValueError) as ctx:
            aggregate_event_daily(df_no_pub)
        self.assertIn("published_at", str(ctx.exception))

        # Missing event_id
        df_no_eid = pd.DataFrame([{"published_at": "2026-03-01", "source": SOURCE_THANHNIEN}])
        with self.assertRaises(ValueError) as ctx:
            aggregate_event_daily(df_no_eid)
        self.assertIn("event_id", str(ctx.exception))

        # Missing source
        df_no_src = pd.DataFrame([{"event_id": "E1", "published_at": "2026-03-01"}])
        with self.assertRaises(ValueError) as ctx:
            aggregate_event_daily(df_no_src)
        self.assertIn("source", str(ctx.exception))

    def test_24_tamper_schema_columns_mismatch_raises_assertion(self):
        """Dropping a canonical column triggers AssertionError in verify_conservation."""
        tampered = self.daily_valid.drop(columns=["count_vietnamnet"])
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered)
        self.assertIn("Schema columns mismatch", str(ctx.exception))

    def test_25_tamper_null_value_raises_assertion(self):
        """Injecting a null value into output DataFrame triggers AssertionError."""
        tampered = self.daily_valid.copy()
        tampered.loc[0, "article_count"] = None
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered)
        self.assertIn("Null values detected", str(ctx.exception))

    def test_26_tamper_duplicate_pk_raises_assertion(self):
        """Injecting a duplicate (event_id, date) row triggers AssertionError."""
        tampered = pd.concat([self.daily_valid, self.daily_valid.iloc[[0]]], ignore_index=True)
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered)
        self.assertIn("Duplicate (event_id, date) pairs", str(ctx.exception))

    def test_27_tamper_source_additivity_violation_raises_assertion(self):
        """Mutating article_count so it does not equal sum(counts) triggers AssertionError."""
        tampered = self.daily_valid.copy()
        tampered.loc[0, "article_count"] = 99
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered)
        self.assertIn("Source additivity violation", str(ctx.exception))

    def test_28_tamper_source_count_violation_raises_assertion(self):
        """Mutating source_count out of concordance or out of [1, 3] triggers AssertionError."""
        tampered = self.daily_valid.copy()
        tampered.loc[0, "source_count"] = 0
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered)
        self.assertIn("Daily source_count mismatch", str(ctx.exception))

    def test_29_tamper_global_conservation_violation_raises_assertion(self):
        """Perturbing global article sum triggers AssertionError."""
        tampered = self.daily_valid.copy()
        tampered.loc[0, "article_count"] += 1
        tampered.loc[0, "count_thanhnien"] += 1
        # Now source additivity holds, but global conservation fails
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered)
        self.assertIn("Global article conservation violated", str(ctx.exception))

    def test_30_tamper_cumulative_monotonicity_violation_raises_assertion(self):
        """Decreasing cumulative_articles or cumulative_sources triggers AssertionError."""
        # Non-increasing cumulative_articles
        tampered_art = self.daily_valid.copy()
        tampered_art.loc[1, "cumulative_articles"] = 1  # was 2
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered_art)
        self.assertIn("cumulative_articles not strictly increasing", str(ctx.exception))

        # Decreasing cumulative_sources
        tampered_src = self.daily_valid.copy()
        tampered_src.loc[1, "cumulative_sources"] = 0
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered_src)
        self.assertIn("cumulative_sources decreased", str(ctx.exception))

    def test_31_tamper_event_age_exceeding_14_days_raises_assertion(self):
        """event_age_days exceeding 14 days triggers AssertionError."""
        tampered = self.daily_valid.copy()
        tampered.loc[1, "event_age_days"] = 15
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, tampered)
        self.assertIn("First day / age violation", str(ctx.exception))

    def test_32_tamper_events_convergence_mismatch_raises_assertion(self):
        """Mismatched ground truth in df_events triggers AssertionError."""
        df_events_tampered = pd.DataFrame([
            {"event_id": "E1", "n_articles": 999, "n_sources": 1}
        ])
        with self.assertRaises(AssertionError) as ctx:
            verify_conservation(self.df_valid, self.daily_valid, df_events=df_events_tampered)
        self.assertIn("Convergence against events.parquet failed", str(ctx.exception))


class TestEventAggregatorLiveDataset(unittest.TestCase):
    """Validates real production artifact data/processed_multisource/event_daily.parquet."""

    @classmethod
    def setUpClass(cls):
        """Skip live tests if production parquet files are not present."""
        if not cfg.MULTISOURCE_EVENT_DAILY_PARQUET.exists():
            raise unittest.SkipTest(
                f"Production artifact {cfg.MULTISOURCE_EVENT_DAILY_PARQUET} does not exist."
            )

    def test_33_live_event_daily_file_presence_and_shape(self):
        """event_daily.parquet exists, has 377,551 rows, 11 columns, and 0 nulls."""
        df = pd.read_parquet(cfg.MULTISOURCE_EVENT_DAILY_PARQUET)
        self.assertEqual(len(df), 377551)
        self.assertEqual(list(df.columns), SCHEMA_COLUMNS)
        self.assertEqual(int(df.isna().sum().sum()), 0)

    def test_34_live_global_article_sum_and_conservation(self):
        """Global sum of daily article_count equals 451,336 and matches source totals."""
        df = pd.read_parquet(cfg.MULTISOURCE_EVENT_DAILY_PARQUET)
        total_articles = int(df["article_count"].sum())
        self.assertEqual(total_articles, 451336)

        source_sum = int(
            df["count_thanhnien"].sum()
            + df["count_tuoitre"].sum()
            + df["count_vietnamnet"].sum()
        )
        self.assertEqual(source_sum, 451336)

    def test_35_live_unique_events_and_first_days(self):
        """Unique event_id count equals 320,842 and matches is_first_day count and age 0."""
        df = pd.read_parquet(cfg.MULTISOURCE_EVENT_DAILY_PARQUET)
        self.assertEqual(df["event_id"].nunique(), 320842)
        self.assertEqual(int(df["is_first_day"].sum()), 320842)
        self.assertTrue((df["is_first_day"] == (df["event_age_days"] == 0)).all())

    def test_36_live_event_age_bounds(self):
        """All event_age_days values are bounded in [0, 14]."""
        df = pd.read_parquet(cfg.MULTISOURCE_EVENT_DAILY_PARQUET)
        self.assertGreaterEqual(int(df["event_age_days"].min()), 0)
        self.assertLessEqual(int(df["event_age_days"].max()), 14)

    def test_37_live_events_convergence_against_ground_truth(self):
        """Terminal rows converge with events.parquet for all 320,842 events."""
        if not cfg.MULTISOURCE_EVENTS_PARQUET.exists():
            self.skipTest("events.parquet not present.")

        df_daily = pd.read_parquet(cfg.MULTISOURCE_EVENT_DAILY_PARQUET)
        df_events = pd.read_parquet(cfg.MULTISOURCE_EVENTS_PARQUET)

        last_daily = df_daily.groupby("event_id", sort=False).last()
        ev_idx = df_events.set_index("event_id")

        self.assertEqual(len(last_daily), 320842)
        self.assertTrue(
            (last_daily["cumulative_articles"] == ev_idx.loc[last_daily.index, "n_articles"]).all(),
            "Terminal cumulative_articles did not converge with events.parquet n_articles",
        )
        self.assertTrue(
            (last_daily["cumulative_sources"] == ev_idx.loc[last_daily.index, "n_sources"]).all(),
            "Terminal cumulative_sources did not converge with events.parquet n_sources",
        )

    def test_38_live_verify_conservation_passes_10_of_10(self):
        """Full verify_conservation passes 10/10 checks on live production dataset."""
        if not (
            cfg.MULTISOURCE_ARTICLE_EVENTS_PARQUET.exists()
            and cfg.MULTISOURCE_EVENTS_PARQUET.exists()
        ):
            self.skipTest("Required multisource parquet files not present.")

        metrics = verify_conservation(
            cfg.MULTISOURCE_ARTICLE_EVENTS_PARQUET,
            cfg.MULTISOURCE_EVENT_DAILY_PARQUET,
            cfg.MULTISOURCE_EVENTS_PARQUET,
        )
        self.assertEqual(metrics["status"], "PASS")
        self.assertTrue(metrics["valid"])
        self.assertEqual(len(metrics["errors"]), 0)
        self.assertEqual(metrics["total_articles"], 451336)
        self.assertEqual(metrics["unique_events"], 320842)
        self.assertEqual(metrics["converged_events"], 320842)


if __name__ == "__main__":
    unittest.main(verbosity=2)
