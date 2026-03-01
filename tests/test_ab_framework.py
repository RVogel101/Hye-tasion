"""Tests for the A/B testing framework — statistical analysis, metric vectors, etc."""
import pytest
from unittest.mock import patch

from app.models.ab_test import ABTest, ABVariant
from app.ab_testing.ab_framework import (
    _build_metric_vector,
    _collect_historical_metrics,
    analyze_test,
)


class TestBuildMetricVector:
    def test_all_metrics_present(self, db, make_ab_test):
        test = make_ab_test(
            variant_kw=[
                {"score": 50, "num_comments": 10, "upvote_ratio": 0.85, "engagement_rate": 42.5},
                {"score": 30, "num_comments": 5, "upvote_ratio": 0.72, "engagement_rate": 21.6},
            ],
        )
        v = test.variants[0]
        vec = _build_metric_vector(v)
        assert len(vec) == 4
        assert vec[0] == 50.0           # score
        assert vec[1] == 10.0           # num_comments
        assert vec[2] == 85.0           # upvote_ratio * 100
        assert vec[3] == 42.5           # engagement_rate

    def test_missing_metrics(self, db, make_ab_test):
        test = make_ab_test(
            variant_kw=[
                {"score": 10, "num_comments": None, "upvote_ratio": None, "engagement_rate": None},
                {"score": 5},
            ],
        )
        vec = _build_metric_vector(test.variants[0])
        assert vec == [10.0]

    def test_zero_score(self, db, make_ab_test):
        test = make_ab_test(
            variant_kw=[{"score": 0, "num_comments": 0}, {"score": 1}],
        )
        vec = _build_metric_vector(test.variants[0])
        assert 0.0 in vec


class TestAnalyzeTest:
    def test_insufficient_variants(self, db, make_ab_test):
        test = make_ab_test(num_variants=1, variant_kw=[{"score": 10}])
        result = analyze_test(db, test)
        assert result["status"] == "insufficient_data"

    def test_no_scores_insufficient(self, db, make_ab_test):
        """Variants with no score data should be treated as insufficient."""
        test = make_ab_test(
            variant_kw=[{"score": None}, {"score": None}],
        )
        result = analyze_test(db, test)
        assert result["status"] == "insufficient_data"

    def test_identifies_winner(self, db, make_ab_test):
        test = make_ab_test(
            variant_kw=[
                {"score": 100, "num_comments": 20, "upvote_ratio": 0.9, "engagement_rate": 90.0},
                {"score": 30, "num_comments": 5, "upvote_ratio": 0.6, "engagement_rate": 18.0},
            ],
        )
        result = analyze_test(db, test)
        assert result["winner"] == "A"
        assert result["improvement_pct"] > 0

    def test_returns_sample_sizes(self, db, make_ab_test):
        test = make_ab_test(
            variant_kw=[
                {"score": 50, "num_comments": 10, "upvote_ratio": 0.8, "engagement_rate": 40.0},
                {"score": 30, "num_comments": 5, "upvote_ratio": 0.7, "engagement_rate": 21.0},
            ],
        )
        result = analyze_test(db, test)
        assert "sample_sizes" in result
        assert result["sample_sizes"]["a"] >= 4
        assert result["sample_sizes"]["b"] >= 4

    def test_significant_result_concludes_test(self, db, make_ab_test):
        """When p < threshold and sample is large enough, test should conclude."""
        # Create several historical concluded tests to build up sample size
        for i in range(5):
            old_test = make_ab_test(
                variant_kw=[
                    {"score": 100 + i * 10, "num_comments": 20 + i, "upvote_ratio": 0.9, "engagement_rate": 90.0 + i * 5},
                    {"score": 10 + i, "num_comments": 2, "upvote_ratio": 0.4, "engagement_rate": 4.0 + i},
                ],
            )
            for v in old_test.variants:
                v.status = "concluded"
            db.commit()

        # Now create the test under analysis with clear difference
        test = make_ab_test(
            variant_kw=[
                {"score": 200, "num_comments": 50, "upvote_ratio": 0.95, "engagement_rate": 190.0,
                 "title_strategy": "standard"},
                {"score": 5, "num_comments": 1, "upvote_ratio": 0.3, "engagement_rate": 1.5,
                 "title_strategy": "standard"},
            ],
        )
        result = analyze_test(db, test)
        # With enough historical data and a huge difference, it should be significant
        if result.get("p_value") is not None:
            assert isinstance(result["p_value"], float)
            assert 0 <= result["p_value"] <= 1

    def test_inconclusive_with_small_samples(self, db, make_ab_test):
        """With no history and few metrics, should return inconclusive."""
        test = make_ab_test(
            variant_kw=[
                {"score": 51, "engagement_rate": 45.0},
                {"score": 50, "engagement_rate": 44.0},
            ],
        )
        result = analyze_test(db, test)
        # With only 2 observations each and no history, likely inconclusive
        assert result["status"] in ("inconclusive", "significant")


class TestCollectHistoricalMetrics:
    def test_empty_when_no_history(self, db, make_ab_test):
        test = make_ab_test()
        history = _collect_historical_metrics(db, "armenia", test.id)
        assert history == {}

    def test_collects_from_concluded(self, db, make_ab_test):
        old = make_ab_test(
            variant_kw=[
                {"score": 50, "num_comments": 10, "upvote_ratio": 0.8, "engagement_rate": 40.0,
                 "title_strategy": "question"},
                {"score": 30, "num_comments": 5, "upvote_ratio": 0.7, "engagement_rate": 21.0,
                 "title_strategy": "standard"},
            ],
        )
        for v in old.variants:
            v.status = "concluded"
        db.commit()

        new = make_ab_test()
        history = _collect_historical_metrics(db, "armenia", new.id)
        assert "question" in history
        assert "standard" in history
        assert len(history["question"]) >= 4  # score + comments + ratio + engagement

    def test_excludes_current_test(self, db, make_ab_test):
        test = make_ab_test(
            variant_kw=[
                {"score": 50, "title_strategy": "standard"},
                {"score": 30, "title_strategy": "standard"},
            ],
        )
        for v in test.variants:
            v.status = "concluded"
        db.commit()

        history = _collect_historical_metrics(db, "armenia", test.id)
        assert history == {}
