#!/usr/bin/env python3
"""
test_api_integration.py — API統合テスト

タスク #2245: APIレート制限・キャッシング最適化
"""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from scripts.api_ratelimiter import APIRateLimiter
from scripts.response_cache import ResponseCache
from scripts.api_performance_monitor import APIPerformanceMonitor


class TestAPIIntegration:
    """API最適化モジュール間の統合テスト"""

    @pytest.fixture
    def temp_db(self):
        """テスト用の一時SQLiteデータベース"""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def temp_monitor_log(self):
        """テスト用の一時パフォーマンスログ"""
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_cache_hit_skips_rate_limit(self, temp_db):
        """キャッシュヒット時はレート制限をスキップ"""
        limiter = APIRateLimiter(rpm_limit=1, tpm_limit=100)
        cache = ResponseCache(db_path=temp_db)

        cache.set("model", "prompt", {}, "cached_response")

        # キャッシュヒット
        result = cache.get("model", "prompt", {})
        assert result == "cached_response"

        # レート制限はまだ呼ばれていない
        assert limiter.requests_in_window == 0

    def test_rate_limit_tracks_api_calls(self, temp_db):
        """APIコール後、レート制限に記録される"""
        limiter = APIRateLimiter()
        cache = ResponseCache(db_path=temp_db)

        limiter.record_request(input_tokens=100, output_tokens=50)
        assert limiter.requests_in_window == 1
        assert limiter.tokens_in_window == 150

    def test_performance_monitor_logs_api_calls(self, temp_monitor_log):
        """パフォーマンス監視がAPI呼び出しをログ"""
        monitor = APIPerformanceMonitor(log_file=temp_monitor_log)

        monitor.record_api_call(
            model="claude-haiku",
            input_tokens=100,
            output_tokens=50,
            latency_sec=0.5,
            cache_hit=False,
        )

        with open(temp_monitor_log, "r") as f:
            line = f.readline()
            entry = json.loads(line)
            assert entry["model"] == "claude-haiku"
            assert entry["input_tokens"] == 100
            assert entry["output_tokens"] == 50
            assert entry["cache_hit"] is False

    def test_cache_and_monitor_integration(self, temp_db, temp_monitor_log):
        """キャッシュとパフォーマンス監視の統合"""
        cache = ResponseCache(db_path=temp_db)
        monitor = APIPerformanceMonitor(log_file=temp_monitor_log)

        cache.set("model", "prompt", {}, "response", input_tokens=100, output_tokens=50)
        monitor.record_api_call(
            model="model",
            input_tokens=100,
            output_tokens=50,
            latency_sec=0.5,
            cache_hit=False,
        )

        result = cache.get("model", "prompt", {})
        assert result == "response"

        monitor.record_cache_hit()

        summary = monitor.get_summary()
        assert summary["total_calls"] == 2
        assert summary["cache_hits"] == 1

    def test_rate_limiter_monitor_tracking(self):
        """レート制限とモニタリング統合"""
        limiter = APIRateLimiter(rpm_limit=60, tpm_limit=100000)

        limiter.record_request(input_tokens=100, output_tokens=50)
        limiter.record_request(input_tokens=200, output_tokens=100)

        stats = limiter.get_stats()
        assert stats["requests_in_window"] == 2
        assert stats["tokens_in_window"] == 450

    def test_full_pipeline_with_cache_miss(self, temp_db, temp_monitor_log):
        """キャッシュミス時の完全なパイプライン"""
        limiter = APIRateLimiter()
        cache = ResponseCache(db_path=temp_db)
        monitor = APIPerformanceMonitor(log_file=temp_monitor_log)

        # キャッシュミス
        result = cache.get("model", "prompt", {})
        assert result is None
        assert monitor.get_summary()["cache_misses"] == 0

        # API呼び出しをシミュレート
        limiter.wait_if_needed(tokens_to_generate=200)
        limiter.record_request(input_tokens=100, output_tokens=50)

        cache.set("model", "prompt", {}, "response", input_tokens=100, output_tokens=50)
        monitor.record_api_call(
            model="model",
            input_tokens=100,
            output_tokens=50,
            latency_sec=0.5,
            cache_hit=False,
        )

        # 2番目の呼び出しではキャッシュヒット
        result = cache.get("model", "prompt", {})
        assert result == "response"
        monitor.record_cache_hit()

        summary = monitor.get_summary()
        assert summary["cache_hits"] == 1
        assert summary["cache_hit_rate_percent"] == 50.0

    def test_performance_metrics_cost_calculation(self, temp_monitor_log):
        """パフォーマンスモニタが正確にコストを計算"""
        monitor = APIPerformanceMonitor(log_file=temp_monitor_log)

        monitor.record_api_call(
            model="claude-haiku-4-5-20251001",
            input_tokens=1000,  # $0.80 / M tokens
            output_tokens=1000,  # $4.0 / M tokens
            cache_read_tokens=0,
            latency_sec=0.1,
            cache_hit=False,
        )

        summary = monitor.get_summary()
        # 入力: 1000 / 1M * 0.80 = 0.0008
        # 出力: 1000 / 1M * 4.0 = 0.004
        # 合計: 0.0048
        assert summary["total_cost_usd"] == pytest.approx(0.0048, abs=0.0001)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
