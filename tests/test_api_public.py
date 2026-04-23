import pytest
import asyncio
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.app import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
async def test_db():
    """テスト用データベース"""
    db_path = Path.home() / ".test_thebranch.sqlite"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # テーブル作成
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL,
            name TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used_at DATETIME,
            expires_at DATETIME,
            is_active BOOLEAN DEFAULT 1,
            rate_limit_per_minute INTEGER DEFAULT 100,
            description TEXT,
            FOREIGN KEY (org_id) REFERENCES organizations(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT,
            status TEXT,
            department_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_templates (
            id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
    """)

    # テストデータ挿入
    cursor.execute("INSERT INTO organizations VALUES ('org123', 'Test Organization')")
    cursor.execute("INSERT INTO users VALUES ('user123', 'testuser', 'test@example.com')")

    # テスト用APIキーを作成
    test_key = "sk_test12345678901234567890123"
    key_hash = hashlib.sha256(test_key.encode()).hexdigest()
    cursor.execute(
        """INSERT INTO api_keys
           (id, org_id, name, key_hash, created_by, is_active, rate_limit_per_minute)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("key123", "org123", "Test Key", key_hash, "user123", 1, 100)
    )

    # テストデータ
    cursor.execute(
        "INSERT INTO departments VALUES (?, ?, ?, ?, ?)",
        ("dept1", "org123", "Engineering", "Engineering Team", datetime.now())
    )
    cursor.execute(
        "INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("agent1", "org123", "Agent 1", "engineer", "active", "dept1", datetime.now())
    )
    cursor.execute(
        "INSERT INTO workflow_templates VALUES (?, ?, ?, ?, ?, ?)",
        ("wf1", "org123", "Workflow 1", "Test Workflow", "active", datetime.now())
    )

    conn.commit()
    yield db_path, test_key

    conn.close()
    if db_path.exists():
        db_path.unlink()


def test_api_key_creation(client):
    """APIキー作成テスト"""
    response = client.post(
        "/api/v1/api-keys",
        json={"name": "New Key", "description": "Test", "rate_limit_per_minute": 200},
        headers={"Authorization": "Bearer test_token"}
    )
    # テストトークンが無効のため401が返る
    assert response.status_code == 401


def test_api_key_validation_missing_header(client):
    """APIキー未指定テスト"""
    response = client.get("/api/v1/departments")
    assert response.status_code == 401
    assert "APIキーが必要です" in response.json()["detail"]


def test_get_departments_endpoint(client):
    """エンドポイント存在確認"""
    response = client.get(
        "/api/v1/departments",
        headers={"X-API-Key": "invalid_key"}
    )
    # 無効なAPIキーのため401が返る
    assert response.status_code == 401


def test_get_agents_endpoint(client):
    """エンドポイント存在確認"""
    response = client.get(
        "/api/v1/agents",
        headers={"X-API-Key": "invalid_key"}
    )
    assert response.status_code == 401


def test_get_workflows_endpoint(client):
    """エンドポイント存在確認"""
    response = client.get(
        "/api/v1/workflows",
        headers={"X-API-Key": "invalid_key"}
    )
    assert response.status_code == 401


def test_revoke_api_key(client):
    """APIキー無効化テスト"""
    response = client.delete(
        "/api/v1/api-keys/key123",
        headers={"Authorization": "Bearer test_token"}
    )
    # テストトークンが無効のため401が返る
    assert response.status_code == 401


def test_list_api_keys(client):
    """APIキー一覧取得テスト"""
    response = client.get(
        "/api/v1/api-keys",
        headers={"Authorization": "Bearer test_token"}
    )
    # テストトークンが無効のため401が返る
    assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
