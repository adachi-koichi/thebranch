#!/usr/bin/env python3
"""
test_response_cache.py — ResponseCache ユニットテスト

タスク #2245: APIレート制限・キャッシング最適化
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from scripts.response_cache import ResponseCache


class TestResponseCache:
    """ResponseCacheクラスのユニットテスト"""

    @pytest.fixture
    def temp_db(self):
        """テスト用の一時SQLiteデータベース"""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_cache_initialization(self, temp_db):
        """キャッシュが正しく初期化される"""
        cache = ResponseCache(db_path=temp_db, l1_capacity=100, l1_ttl_hours=1)
        assert cache.l1_capacity == 100
        assert cache.l1_ttl_hours == 1
        assert cache.l2_ttl_days == 7
        assert len(cache.l1_cache) == 0

    def test_cache_hit_l1_memory(self, temp_db):
        """L1メモリキャッシュヒット"""
        cache = ResponseCache(db_path=temp_db)
        cache.set("claude-haiku", "Hello", {}, "World response")

        result = cache.get("claude-haiku", "Hello", {})
        assert result == "World response"
        assert cache.l1_hits == 1
        assert cache.l1_misses == 0

    def test_cache_miss(self, temp_db):
        """キャッシュミス"""
        cache = ResponseCache(db_path=temp_db)
        result = cache.get("claude-haiku", "Hello", {})
        assert result is None
        assert cache.l1_misses == 1

    def test_cache_key_generation_consistent(self, temp_db):
        """キャッシュキー生成が一貫性を保つ"""
        cache = ResponseCache(db_path=temp_db)
        key1 = cache._make_cache_key("claude-haiku", "Hello", {"task_id": 1})
        key2 = cache._make_cache_key("claude-haiku", "Hello", {"task_id": 1})
        assert key1 == key2

    def test_cache_key_different_for_different_inputs(self, temp_db):
        """異なるプロンプトで異なるキーが生成される"""
        cache = ResponseCache(db_path=temp_db)
        key1 = cache._make_cache_key("claude-haiku", "Hello", {})
        key2 = cache._make_cache_key("claude-haiku", "World", {})
        assert key1 != key2

    def test_hit_rate_calculation(self, temp_db):
        """ヒット率が正しく計算される"""
        cache = ResponseCache(db_path=temp_db)
        cache.set("claude-haiku", "test", {}, "response")

        cache.get("claude-haiku", "test", {})  # hit
        cache.get("claude-haiku", "test2", {})  # miss
        cache.get("claude-haiku", "test", {})  # hit

        stats = cache.get_stats()
        assert stats["total_requests"] == 3
        assert stats["l1_hits"] == 2
        assert stats["l1_misses"] == 1
        assert stats["hit_rate_percent"] == pytest.approx(66.67, abs=0.1)

    def test_l1_lru_capacity_eviction(self, temp_db):
        """L1キャッシュが容量超過時に古いエントリを削除"""
        cache = ResponseCache(db_path=temp_db, l1_capacity=3)

        cache.set("model1", "prompt1", {}, "response1")
        cache.set("model1", "prompt2", {}, "response2")
        cache.set("model1", "prompt3", {}, "response3")

        assert len(cache.l1_cache) == 3

        cache.set("model1", "prompt4", {}, "response4")

        assert len(cache.l1_cache) == 3  # 容量制限
        assert cache.get("model1", "prompt1", {}) is None  # 最古のエントリが削除

    def test_l2_sqlite_persistence(self, temp_db):
        """L2 SQLiteに保存されたデータが永続化される"""
        cache1 = ResponseCache(db_path=temp_db)
        cache1.set("claude-haiku", "Hello", {}, "World response")

        cache2 = ResponseCache(db_path=temp_db)
        result = cache2.get("claude-haiku", "Hello", {})
        assert result == "World response"  # L1ミスでL2からリトリーブ

    def test_ttl_validation(self, temp_db):
        """TTL検証が機能する"""
        cache = ResponseCache(db_path=temp_db)

        past_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        assert cache._is_ttl_valid(past_time, 1) is False  # TTL 1時間で期限切れ

        current_time = datetime.utcnow().isoformat()
        assert cache._is_ttl_valid(current_time, 1) is True  # TTL 1時間で有効

    def test_cleanup_expired(self, temp_db):
        """期限切れキャッシュの削除が機能する"""
        cache = ResponseCache(db_path=temp_db, l2_ttl_days=7)
        cache.set("claude-haiku", "test", {}, "response")

        deleted_count = cache.cleanup_expired()
        # 直後なので削除されないはず
        assert deleted_count == 0

    def test_clear_all(self, temp_db):
        """全キャッシュをクリア"""
        cache = ResponseCache(db_path=temp_db)
        cache.set("model1", "prompt1", {}, "response1")
        cache.set("model1", "prompt2", {}, "response2")

        cache.clear_all()

        assert len(cache.l1_cache) == 0
        assert cache.get("model1", "prompt1", {}) is None

    def test_token_tracking(self, temp_db):
        """トークン数の追跡"""
        cache = ResponseCache(db_path=temp_db)
        cache.set(
            "claude-haiku",
            "test",
            {},
            "response",
            input_tokens=100,
            output_tokens=50,
        )

        stats = cache.get_stats()
        assert stats["l2_count"] == 1  # SQLiteに1エントリ


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
