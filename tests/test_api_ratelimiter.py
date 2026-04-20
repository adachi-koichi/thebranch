#!/usr/bin/env python3
"""
test_api_ratelimiter.py — APIRateLimiter ユニットテスト

タスク #2245: APIレート制限・キャッシング最適化
"""

import pytest
import time
from scripts.api_ratelimiter import APIRateLimiter


class TestAPIRateLimiter:
    """APIRateLimiterクラスのユニットテスト"""

    def test_init_default_values(self):
        """デフォルト値で初期化できる"""
        limiter = APIRateLimiter()
        assert limiter.rpm_limit == 60
        assert limiter.tpm_limit == 100000
        assert limiter.initial_backoff_sec == 0.5
        assert limiter.max_backoff_sec == 60.0
        assert limiter.max_retries == 5

    def test_wait_if_needed_under_limit(self):
        """リミット以下なら待機なし"""
        limiter = APIRateLimiter(rpm_limit=10, tpm_limit=1000)
        wait_time = limiter.wait_if_needed(tokens_to_generate=100)
        assert wait_time == 0.0
        assert limiter.requests_in_window == 0

    def test_record_request_updates_state(self):
        """リクエスト記録でカウントが増える"""
        limiter = APIRateLimiter()
        limiter.record_request(input_tokens=100, output_tokens=50)
        assert limiter.requests_in_window == 1
        assert limiter.tokens_in_window == 150

    def test_exponential_backoff_calculation(self):
        """指数バックオフが正しく計算される"""
        limiter = APIRateLimiter(initial_backoff_sec=1.0, max_backoff_sec=60.0)

        assert limiter._exponential_backoff(0) == 1.0
        assert limiter._exponential_backoff(1) == 2.0
        assert limiter._exponential_backoff(2) == 4.0
        assert limiter._exponential_backoff(3) == 8.0
        assert limiter._exponential_backoff(4) == 16.0
        assert limiter._exponential_backoff(5) == 32.0
        assert limiter._exponential_backoff(6) == 60.0  # max_backoff_sec で制限

    def test_get_stats_returns_dict(self):
        """get_stats() が辞書を返す"""
        limiter = APIRateLimiter()
        limiter.record_request(input_tokens=100, output_tokens=50)
        stats = limiter.get_stats()

        assert isinstance(stats, dict)
        assert "rpm_limit" in stats
        assert "tpm_limit" in stats
        assert "requests_in_window" in stats
        assert "tokens_in_window" in stats
        assert "backoff_count" in stats
        assert "total_wait_time" in stats
        assert stats["requests_in_window"] == 1
        assert stats["tokens_in_window"] == 150

    def test_reset_clears_state(self):
        """reset() で統計がリセットされる"""
        limiter = APIRateLimiter()
        limiter.record_request(input_tokens=100, output_tokens=50)
        limiter.backoff_count = 3
        limiter.total_wait_time = 5.0

        limiter.reset()

        assert limiter.requests_in_window == 0
        assert limiter.tokens_in_window == 0
        assert limiter.backoff_count == 0
        assert limiter.total_wait_time == 0.0

    def test_multiple_requests_accumulate(self):
        """複数リクエストがカウントに反映される"""
        limiter = APIRateLimiter()
        limiter.record_request(input_tokens=100, output_tokens=50)
        limiter.record_request(input_tokens=200, output_tokens=100)
        limiter.record_request(input_tokens=150, output_tokens=75)

        assert limiter.requests_in_window == 3
        assert limiter.tokens_in_window == 675  # (100+50) + (200+100) + (150+75)

    def test_window_reset_after_60_seconds(self):
        """60秒経過後にウィンドウがリセットされる"""
        limiter = APIRateLimiter()
        limiter.record_request(input_tokens=100, output_tokens=50)

        # ウィンドウ開始時刻を60秒前に設定
        from datetime import datetime, timedelta
        limiter.window_start = datetime.utcnow() - timedelta(seconds=60)

        limiter._reset_window_if_needed()

        assert limiter.requests_in_window == 0
        assert limiter.tokens_in_window == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
