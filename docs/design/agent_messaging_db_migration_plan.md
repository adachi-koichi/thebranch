# AIエージェント間メッセージング・通知システム
## DB マイグレーション計画（MVP フェーズ 1）

**Document Version:** 1.0  
**Date:** 2026-04-30  
**Status:** Ready for Implementation  

---

## 1. マイグレーション概要

### 対象：3つのテーブル追加
1. `task_completion_events` — タスク完了イベント履歴・監査ログ
2. `webhook_subscriptions` — Webhook 登録管理
3. `webhook_delivery_logs` — Webhook 配信ログ・リトライ制御

### 実装方針
- **ファイル名規則:** `migrations/0XXX_add_agent_messaging_tables.py` (Flask-Alembic)
- **ロールバック対応:** DOWN() メソッドで完全削除
- **既存テーブルへの依存:** tasks テーブル、users テーブル（既存）

---

## 2. マイグレーション SQL スクリプト

### 2.1 task_completion_events テーブル作成

```sql
-- Migration: 0001_create_task_completion_events
CREATE TABLE task_completion_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- イベント基本情報
    task_id INTEGER NOT NULL,
    workflow_id TEXT NOT NULL,
    team_name TEXT NOT NULL,
    
    -- 実行者情報
    executor_user_id TEXT NOT NULL,
    executor_username TEXT NOT NULL,
    executor_role TEXT NOT NULL,
    
    -- タスク完了情報
    status TEXT NOT NULL DEFAULT 'completed',
    priority INTEGER NOT NULL DEFAULT 3,
    completion_time_ms INTEGER,
    
    -- メタデータ
    tag_ids TEXT,  -- JSON: ["urgent", "mvp"]
    category TEXT,
    phase TEXT,
    
    -- イベント配信状態
    event_status TEXT NOT NULL DEFAULT 'triggered',
    
    -- タイムスタンプ
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triggered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_webhook_attempt_at DATETIME,
    
    CONSTRAINT chk_executor_role CHECK(executor_role IN ('ai-engineer', 'pm', 'em', 'admin')),
    CONSTRAINT chk_status CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    CONSTRAINT chk_priority CHECK(priority BETWEEN 1 AND 5),
    CONSTRAINT chk_event_status CHECK(event_status IN ('triggered', 'dispatched', 'acked', 'failed')),
    CONSTRAINT chk_category CHECK(category IN ('infra', 'feature', 'design', 'test')),
    CONSTRAINT chk_phase CHECK(phase IN ('design', 'implementation', 'test', 'review')),
    
    UNIQUE(task_id, triggered_at),
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX idx_task_completion_events_task_id ON task_completion_events(task_id);
CREATE INDEX idx_task_completion_events_workflow_id ON task_completion_events(workflow_id);
CREATE INDEX idx_task_completion_events_team_name ON task_completion_events(team_name);
CREATE INDEX idx_task_completion_events_created_at ON task_completion_events(created_at);
CREATE INDEX idx_task_completion_events_event_status ON task_completion_events(event_status);
```

### 2.2 webhook_subscriptions テーブル作成

```sql
-- Migration: 0002_create_webhook_subscriptions
CREATE TABLE webhook_subscriptions (
    webhook_id TEXT PRIMARY KEY,  -- UUID: "wh_abc123xyz..."
    
    -- ユーザー情報
    user_id TEXT NOT NULL,
    
    -- Webhook 基本設定
    name TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'task.completed',
    target_url TEXT NOT NULL,
    
    -- 認証情報
    auth_type TEXT NOT NULL,
    secret_key_hash TEXT NOT NULL,  -- bcrypt hash
    
    -- 状態
    is_active BOOLEAN NOT NULL DEFAULT 1,
    
    -- リトライポリシー（JSON）
    retry_policy TEXT NOT NULL DEFAULT '{"max_retries": 3, "retry_backoff_ms": 1000, "timeout_ms": 5000}',
    
    -- カスタムヘッダ（JSON）
    custom_headers TEXT,  -- {"X-Custom-Header": "value"}
    
    -- 統計情報
    trigger_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_triggered_at DATETIME,
    last_status_code INTEGER,
    
    -- 作成・更新情報
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_auth_type CHECK(auth_type IN ('bearer', 'hmac-sha256')),
    CONSTRAINT chk_event_type CHECK(event_type IN ('task.completed')),
    
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX idx_webhook_subscriptions_user_id ON webhook_subscriptions(user_id);
CREATE INDEX idx_webhook_subscriptions_event_type ON webhook_subscriptions(event_type);
CREATE INDEX idx_webhook_subscriptions_is_active ON webhook_subscriptions(is_active);
CREATE INDEX idx_webhook_subscriptions_created_at ON webhook_subscriptions(created_at);
```

### 2.3 webhook_delivery_logs テーブル作成

```sql
-- Migration: 0003_create_webhook_delivery_logs
CREATE TABLE webhook_delivery_logs (
    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 関連ID
    webhook_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    
    -- 配信情報
    attempt_number INTEGER NOT NULL DEFAULT 1,
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    
    -- HTTP レスポンス情報
    http_status_code INTEGER,
    response_body TEXT,
    
    -- リトライ情報
    next_retry_at DATETIME,
    last_error_message TEXT,
    
    -- タイムスタンプ
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME,
    
    CONSTRAINT chk_delivery_status CHECK(delivery_status IN ('pending', 'sent', 'acked', 'failed', 'permanent_failure')),
    CONSTRAINT chk_attempt_number CHECK(attempt_number >= 1),
    
    FOREIGN KEY(webhook_id) REFERENCES webhook_subscriptions(webhook_id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES task_completion_events(event_id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX idx_webhook_delivery_logs_webhook_id ON webhook_delivery_logs(webhook_id);
CREATE INDEX idx_webhook_delivery_logs_event_id ON webhook_delivery_logs(event_id);
CREATE INDEX idx_webhook_delivery_logs_delivery_status ON webhook_delivery_logs(delivery_status);
CREATE INDEX idx_webhook_delivery_logs_next_retry_at ON webhook_delivery_logs(next_retry_at);
CREATE INDEX idx_webhook_delivery_logs_created_at ON webhook_delivery_logs(created_at);
```

---

## 3. Flask Alembic マイグレーションスクリプト実装

### ファイルパス
```
dashboard/migrations/versions/0001_add_agent_messaging_tables.py
```

### 実装例（Flask-SQLAlchemy + Alembic）

```python
"""Add agent messaging notification tables

Revision ID: 0001
Revises: <PREVIOUS_MIGRATION_ID>
Create Date: 2026-04-30 06:57:03.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = '<PREVIOUS_MIGRATION_ID>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create task_completion_events, webhook_subscriptions, webhook_delivery_logs tables"""
    
    # 1. task_completion_events テーブル
    op.create_table(
        'task_completion_events',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Text(), nullable=False),
        sa.Column('team_name', sa.Text(), nullable=False),
        sa.Column('executor_user_id', sa.Text(), nullable=False),
        sa.Column('executor_username', sa.Text(), nullable=False),
        sa.Column('executor_role', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='completed'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('completion_time_ms', sa.Integer(), nullable=True),
        sa.Column('tag_ids', sa.Text(), nullable=True),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('phase', sa.Text(), nullable=True),
        sa.Column('event_status', sa.Text(), nullable=False, server_default='triggered'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('triggered_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('last_webhook_attempt_at', sa.DateTime(), nullable=True),
        
        sa.CheckConstraint("executor_role IN ('ai-engineer', 'pm', 'em', 'admin')", name='chk_executor_role'),
        sa.CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'failed')", name='chk_status'),
        sa.CheckConstraint("priority BETWEEN 1 AND 5", name='chk_priority'),
        sa.CheckConstraint("event_status IN ('triggered', 'dispatched', 'acked', 'failed')", name='chk_event_status'),
        sa.CheckConstraint("category IN ('infra', 'feature', 'design', 'test')", name='chk_category'),
        sa.CheckConstraint("phase IN ('design', 'implementation', 'test', 'review')", name='chk_phase'),
        
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id'),
        sa.UniqueConstraint('task_id', 'triggered_at', name='uq_task_triggered')
    )
    
    # インデックス
    op.create_index('idx_task_completion_events_task_id', 'task_completion_events', ['task_id'])
    op.create_index('idx_task_completion_events_workflow_id', 'task_completion_events', ['workflow_id'])
    op.create_index('idx_task_completion_events_team_name', 'task_completion_events', ['team_name'])
    op.create_index('idx_task_completion_events_created_at', 'task_completion_events', ['created_at'])
    op.create_index('idx_task_completion_events_event_status', 'task_completion_events', ['event_status'])
    
    # 2. webhook_subscriptions テーブル
    op.create_table(
        'webhook_subscriptions',
        sa.Column('webhook_id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False, server_default='task.completed'),
        sa.Column('target_url', sa.Text(), nullable=False),
        sa.Column('auth_type', sa.Text(), nullable=False),
        sa.Column('secret_key_hash', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('retry_policy', sa.Text(), nullable=False, 
                  server_default='{"max_retries": 3, "retry_backoff_ms": 1000, "timeout_ms": 5000}'),
        sa.Column('custom_headers', sa.Text(), nullable=True),
        sa.Column('trigger_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('last_status_code', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        
        sa.CheckConstraint("auth_type IN ('bearer', 'hmac-sha256')", name='chk_auth_type'),
        sa.CheckConstraint("event_type IN ('task.completed')", name='chk_event_type'),
        
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('webhook_id')
    )
    
    # インデックス
    op.create_index('idx_webhook_subscriptions_user_id', 'webhook_subscriptions', ['user_id'])
    op.create_index('idx_webhook_subscriptions_event_type', 'webhook_subscriptions', ['event_type'])
    op.create_index('idx_webhook_subscriptions_is_active', 'webhook_subscriptions', ['is_active'])
    op.create_index('idx_webhook_subscriptions_created_at', 'webhook_subscriptions', ['created_at'])
    
    # 3. webhook_delivery_logs テーブル
    op.create_table(
        'webhook_delivery_logs',
        sa.Column('delivery_id', sa.Integer(), nullable=False),
        sa.Column('webhook_id', sa.Text(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('delivery_status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('http_status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('last_error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        
        sa.CheckConstraint("delivery_status IN ('pending', 'sent', 'acked', 'failed', 'permanent_failure')", 
                          name='chk_delivery_status'),
        sa.CheckConstraint("attempt_number >= 1", name='chk_attempt_number'),
        
        sa.ForeignKeyConstraint(['webhook_id'], ['webhook_subscriptions.webhook_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['task_completion_events.event_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('delivery_id')
    )
    
    # インデックス
    op.create_index('idx_webhook_delivery_logs_webhook_id', 'webhook_delivery_logs', ['webhook_id'])
    op.create_index('idx_webhook_delivery_logs_event_id', 'webhook_delivery_logs', ['event_id'])
    op.create_index('idx_webhook_delivery_logs_delivery_status', 'webhook_delivery_logs', ['delivery_status'])
    op.create_index('idx_webhook_delivery_logs_next_retry_at', 'webhook_delivery_logs', ['next_retry_at'])
    op.create_index('idx_webhook_delivery_logs_created_at', 'webhook_delivery_logs', ['created_at'])


def downgrade() -> None:
    """Drop all agent messaging tables"""
    
    # テーブル削除（逆順）
    op.drop_table('webhook_delivery_logs')
    op.drop_table('webhook_subscriptions')
    op.drop_table('task_completion_events')
```

---

## 4. 実装ステップ（Engineer チーム向け）

### Step 1: マイグレーションファイル作成
```bash
# Alembic 初期化（未実施の場合）
cd /Users/delightone/dev/github.com/adachi-koichi/thebranch/dashboard
flask db init migrations

# マイグレーション作成
flask db migrate -m "Add agent messaging notification tables"
```

### Step 2: マイグレーションファイルの確認・手動調整
```bash
# 生成されたマイグレーション確認
ls -la dashboard/migrations/versions/
cat dashboard/migrations/versions/<LATEST>.py
```

### Step 3: マイグレーション実行
```bash
# ローカル DB に適用
flask db upgrade

# または既存 DB に対して直接実行
sqlite3 ~/.claude/skills/task-manager-sqlite/data/tasks.sqlite < migration_sql.sql
```

### Step 4: 検証
```bash
# テーブル確認
sqlite3 ~/.claude/skills/task-manager-sqlite/data/tasks.sqlite ".tables"
sqlite3 ~/.claude/skills/task-manager-sqlite/data/tasks.sqlite ".schema task_completion_events"

# インデックス確認
sqlite3 ~/.claude/skills/task-manager-sqlite/data/tasks.sqlite ".indices task_completion_events"
```

---

## 5. ロールバック手順

### テスト環境での失敗時
```bash
# 直前のマイグレーション状態に戻す
flask db downgrade -1

# または完全にリセット
rm ~/.claude/skills/task-manager-sqlite/data/tasks.sqlite
flask db upgrade  # 最新状態から再構築
```

---

## 6. チェックリスト

- [ ] マイグレーションファイル生成
- [ ] SQL 仕様との一貫性確認
- [ ] インデックス戦略の確認（特に event_status, webhook_id）
- [ ] FOREIGN KEY 制約の動作確認
- [ ] CHECK 制約の値の検証
- [ ] 本番環境へのマイグレーション予定確認
- [ ] バックアップ取得

---

## 参考リンク

- **インターフェース仕様:** `docs/design/agent_messaging_interface_spec.md`
- **既存 Flask 設定:** `dashboard/app.py`
- **既存 DB スキーマ:** `dashboard/models.py`

---

**Next Step:** Engineer による実装開始
