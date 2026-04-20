# エージェント間タスク委譲API - DBスキーマ・API I/F設計書

**タスク ID**: #2404  
**フェーズ**: 設計フェーズ  
**作成日**: 2026-04-20  
**バージョン**: v1.0

---

## 目次

1. [概要](#概要)
2. [DBスキーマ設計](#dbスキーマ設計)
3. [REST API 設計](#rest-api-設計)
4. [委譲チェーン管理](#委譲チェーン管理)
5. [エラーハンドリング](#エラーハンドリング)
6. [ステータス遷移](#ステータス遷移)

---

## 概要

### 背景

マルチエージェント環境（Orchestrator → EM → Engineer）において、タスク委譲を **監視可能・監査可能** に実装する。委譲チェーン全体をログに記録し、どのエージェントがどのタスクを委譲・承認したのかを追跡可能にする。

### 委譲フロー

```
Orchestrator
    ↓ 委譲（ワークフロー全体）
Engineering Manager (EM)
    ↓ 委譲（フェーズごと）
Engineer × N
    ↓ 確認応答（acknowledgement）
EM（確認状態を記録）
    ↓ 状態反映
Orchestrator（全体監視）
```

### 主な要件

- ✓ 委譲チェーン全体をトレーサブルに記録
- ✓ 各ステップで タイムスタンプ・アクター・アクション を記録
- ✓ タスク単位で「誰から誰へ委譲されたか」を把握
- ✓ 委譲待機・確認応答の状態管理
- ✓ 再委譲（retry）メカニズムのサポート

---

## DBスキーマ設計

### テーブル 1: task_delegations（委譲トランザクション管理）

タスク委譲の基本ユニット。委譲元エージェントから委譲先エージェントへの委譲を記録。

```sql
CREATE TABLE IF NOT EXISTS task_delegations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 委譲の基本情報
    delegation_key        TEXT NOT NULL UNIQUE,  -- "deleg-{timestamp}-{uuid}"
    task_id               INTEGER NOT NULL REFERENCES dev_tasks(id) ON DELETE CASCADE,
    
    -- 委譲関係
    from_agent_id         TEXT NOT NULL,  -- 委譲元エージェント ID
    to_agent_id           TEXT NOT NULL,  -- 委譲先エージェント ID
    from_agent_type       TEXT NOT NULL CHECK(from_agent_type IN ('orchestrator', 'em', 'engineer')),
    to_agent_type         TEXT NOT NULL CHECK(to_agent_type IN ('em', 'engineer')),
    
    -- 委譲コンテキスト
    delegation_scope      TEXT NOT NULL CHECK(delegation_scope IN ('workflow', 'phase', 'task')),
    scope_reference_id    INTEGER,  -- workflow_id / phase_id の参照
    scope_reference_key   TEXT,     -- 'workflow-001' / 'phase-02' など
    
    -- 委譲メッセージ
    delegation_message    TEXT,     -- 委譲時のメッセージ（期待される完了期限など）
    
    -- ステータス管理
    status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK(status IN (
                            'pending',           -- 委譲待機（受信側未確認）
                            'acknowledged',      -- 受信側が確認応答
                            'in_progress',       -- 実行中
                            'completed',         -- 完了
                            'rejected',          -- 委譲拒否
                            'reassigned'         -- 再委譲（他のエージェントへ）
                          )),
    
    -- タイムスタンプ
    delegated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    acknowledged_at       TEXT,  -- 受信側が確認した時刻
    started_at            TEXT,  -- 実作業開始時刻
    completed_at          TEXT,
    
    -- トレーサビリティ
    parent_delegation_id  INTEGER REFERENCES task_delegations(id),  -- 再委譲元
    retry_attempt         INTEGER DEFAULT 0,  -- リトライ回数
    
    -- メタデータ
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    
    FOREIGN KEY (task_id) REFERENCES dev_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_delegation_id) REFERENCES task_delegations(id) ON DELETE SET NULL
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_task_delegations_task_id ON task_delegations(task_id);
CREATE INDEX IF NOT EXISTS idx_task_delegations_from_agent ON task_delegations(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_task_delegations_to_agent ON task_delegations(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_task_delegations_status ON task_delegations(status);
CREATE INDEX IF NOT EXISTS idx_task_delegations_delegation_key ON task_delegations(delegation_key);
CREATE INDEX IF NOT EXISTS idx_task_delegations_scope_reference ON task_delegations(scope_reference_id);
```

### テーブル 2: delegation_events（委譲イベントログ）

委譲チェーンの各ステップを詳細に記録。

```sql
CREATE TABLE IF NOT EXISTS delegation_events (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- イベントの関連付け
    delegation_id         INTEGER NOT NULL REFERENCES task_delegations(id) ON DELETE CASCADE,
    task_id               INTEGER NOT NULL REFERENCES dev_tasks(id) ON DELETE CASCADE,
    
    -- イベント情報
    event_type            TEXT NOT NULL CHECK(event_type IN (
                            'delegated',        -- タスク委譲実行
                            'acknowledged',     -- 受信側が確認応答
                            'rejected',         -- 委譲拒否
                            'started',          -- 実作業開始
                            'completed',        -- 完了
                            'error',            -- エラー発生
                            'reassigned',       -- 再委譲
                            'commented'         -- コメント追加
                          )),
    
    -- アクター情報
    actor_id              TEXT NOT NULL,
    actor_type            TEXT NOT NULL CHECK(actor_type IN ('orchestrator', 'em', 'engineer')),
    actor_name            TEXT,
    
    -- イベント詳細
    message               TEXT,
    metadata              TEXT,  -- JSON: 詳細情報（エラー詳細など）
    
    -- タイムスタンプ
    event_timestamp       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    
    FOREIGN KEY (delegation_id) REFERENCES task_delegations(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES dev_tasks(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_delegation_events_delegation_id ON delegation_events(delegation_id);
CREATE INDEX IF NOT EXISTS idx_delegation_events_task_id ON delegation_events(task_id);
CREATE INDEX IF NOT EXISTS idx_delegation_events_event_type ON delegation_events(event_type);
CREATE INDEX IF NOT EXISTS idx_delegation_events_actor_id ON delegation_events(actor_id);
CREATE INDEX IF NOT EXISTS idx_delegation_events_timestamp ON delegation_events(event_timestamp);
```

### テーブル 3: delegation_comments（委譲に関するコメント・メモ）

委譲過程でのやり取り。進捗報告、質問、リスク等を記録。

```sql
CREATE TABLE IF NOT EXISTS delegation_comments (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- コメント対象
    delegation_id         INTEGER NOT NULL REFERENCES task_delegations(id) ON DELETE CASCADE,
    task_id               INTEGER NOT NULL REFERENCES dev_tasks(id) ON DELETE CASCADE,
    
    -- コメント情報
    author_id             TEXT NOT NULL,
    author_type           TEXT NOT NULL CHECK(author_type IN ('orchestrator', 'em', 'engineer')),
    content               TEXT NOT NULL,
    
    -- メタデータ
    comment_type          TEXT DEFAULT 'note'  -- 'note', 'risk', 'blocker', 'update'
                          CHECK(comment_type IN ('note', 'risk', 'blocker', 'update')),
    
    -- タイムスタンプ
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    
    FOREIGN KEY (delegation_id) REFERENCES task_delegations(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES dev_tasks(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_delegation_comments_delegation_id ON delegation_comments(delegation_id);
CREATE INDEX IF NOT EXISTS idx_delegation_comments_task_id ON delegation_comments(task_id);
CREATE INDEX IF NOT EXISTS idx_delegation_comments_author_id ON delegation_comments(author_id);
```

### テーブル 4: dev_tasks 拡張（既存テーブルへのカラム追加）

既存の `dev_tasks` テーブルに委譲追跡用フィールドを追加：

```sql
ALTER TABLE dev_tasks ADD COLUMN IF NOT EXISTS current_delegation_id INTEGER REFERENCES task_delegations(id);
ALTER TABLE dev_tasks ADD COLUMN IF NOT EXISTS delegation_chain_depth INTEGER DEFAULT 0;
ALTER TABLE dev_tasks ADD COLUMN IF NOT EXISTS last_delegated_at TEXT;

-- インデックス追加
CREATE INDEX IF NOT EXISTS idx_dev_tasks_current_delegation ON dev_tasks(current_delegation_id);
```

### スキーマの関連図

```
dev_tasks
  ├─ id (PK)
  ├─ title
  ├─ current_delegation_id (FK → task_delegations.id)
  └─ delegation_chain_depth (委譲の深さ)
       ↓ (1:N)
task_delegations
  ├─ id (PK)
  ├─ task_id (FK)
  ├─ from_agent_id / to_agent_id
  ├─ status
  ├─ parent_delegation_id (self-reference, 再委譲の場合)
  └─ delegated_at
       ├─ (1:N)
       │  └─ delegation_events
       │      ├─ event_type
       │      ├─ actor_id
       │      └─ event_timestamp
       │
       └─ (1:N)
          └─ delegation_comments
              ├─ author_id
              ├─ content
              └─ comment_type
```

---

## REST API 設計

### API エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|---------|----------------|------|
| **POST** | `/api/v1/tasks/{id}/delegate` | タスク委譲を実行 |
| **GET** | `/api/v1/tasks/{id}/delegations` | タスクの委譲チェーン取得 |
| **GET** | `/api/v1/delegations/{delegation_id}` | 委譲詳細取得 |
| **PUT** | `/api/v1/delegations/{delegation_id}/acknowledge` | 委譲を確認応答 |
| **POST** | `/api/v1/delegations/{delegation_id}/reject` | 委譲を拒否 |
| **POST** | `/api/v1/delegations/{delegation_id}/comments` | コメント追加 |
| **GET** | `/api/v1/delegations?status={status}` | 条件検索（待機中など） |

---

### 1. タスク委譲実行

```http
POST /api/v1/tasks/{task_id}/delegate
Content-Type: application/json
Authorization: Bearer {token}

Request Body:
{
  "to_agent_id": "em-1",
  "to_agent_type": "em",
  "delegation_scope": "task",  -- 'workflow' | 'phase' | 'task'
  "scope_reference_id": 5,     -- workflow_id など
  "delegation_message": "フェーズ2の実装をお願いします。期限は2026-05-15です。",
  "expected_completion": "2026-05-15"
}
```

**レスポンス** (201 Created):

```json
{
  "success": true,
  "data": {
    "delegation_id": 1001,
    "delegation_key": "deleg-2026-04-20T18:30:45-uuid-xxxx",
    "task_id": 2404,
    "task_title": "【設計】エージェント間タスク委譲API",
    "from_agent_id": "orchestrator",
    "from_agent_type": "orchestrator",
    "to_agent_id": "em-1",
    "to_agent_type": "em",
    "delegation_scope": "task",
    "status": "pending",
    "delegated_at": "2026-04-20T18:30:45Z",
    "delegation_message": "フェーズ2の実装をお願いします。期限は2026-05-15です。",
    "expected_completion": "2026-05-15",
    "_links": {
      "self": "/api/v1/delegations/1001",
      "acknowledge": "/api/v1/delegations/1001/acknowledge",
      "reject": "/api/v1/delegations/1001/reject",
      "comments": "/api/v1/delegations/1001/comments"
    }
  }
}
```

**エラーレスポンス** (400 Bad Request):

```json
{
  "success": false,
  "error": {
    "code": "INVALID_DELEGATION",
    "message": "Cannot delegate to same agent",
    "details": {
      "task_id": 2404,
      "from_agent_id": "em-1",
      "to_agent_id": "em-1"
    }
  }
}
```

---

### 2. タスク委譲チェーン取得

```http
GET /api/v1/tasks/{task_id}/delegations
Authorization: Bearer {token}

Query Parameters:
  - include_events: true|false (イベントログを含むか)
  - include_comments: true|false (コメントを含むか)
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "task_id": 2404,
    "task_title": "【設計】エージェント間タスク委譲API",
    "current_status": "in_progress",
    "delegation_chain": [
      {
        "sequence": 1,
        "delegation_id": 1000,
        "from_agent": {
          "id": "orchestrator",
          "type": "orchestrator",
          "name": "AI Orchestrator"
        },
        "to_agent": {
          "id": "em-1",
          "type": "em",
          "name": "Engineering Manager #1"
        },
        "scope": "workflow",
        "status": "acknowledged",
        "delegated_at": "2026-04-20T10:00:00Z",
        "acknowledged_at": "2026-04-20T10:05:00Z",
        "duration_minutes": 5
      },
      {
        "sequence": 2,
        "delegation_id": 1001,
        "from_agent": {
          "id": "em-1",
          "type": "em",
          "name": "Engineering Manager #1"
        },
        "to_agent": {
          "id": "eng-3",
          "type": "engineer",
          "name": "Engineer Bob"
        },
        "scope": "task",
        "status": "in_progress",
        "delegated_at": "2026-04-20T10:30:00Z",
        "acknowledged_at": "2026-04-20T10:35:00Z",
        "started_at": "2026-04-20T11:00:00Z",
        "duration_minutes": 30
      }
    ],
    "total_depth": 2,
    "timeline": {
      "first_delegated": "2026-04-20T10:00:00Z",
      "last_delegated": "2026-04-20T10:30:00Z",
      "total_elapsed_hours": 0.5
    }
  }
}
```

---

### 3. 委譲詳細取得

```http
GET /api/v1/delegations/{delegation_id}
Authorization: Bearer {token}

Query Parameters:
  - include_events: true
  - include_comments: true
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "delegation_id": 1001,
    "delegation_key": "deleg-2026-04-20T18:30:45-uuid-xxxx",
    "task": {
      "id": 2404,
      "title": "【設計】エージェント間タスク委譲API"
    },
    "from_agent": {
      "id": "em-1",
      "type": "em",
      "name": "Engineering Manager #1"
    },
    "to_agent": {
      "id": "eng-3",
      "type": "engineer",
      "name": "Engineer Bob"
    },
    "delegation_scope": "task",
    "status": "in_progress",
    "delegated_at": "2026-04-20T10:30:00Z",
    "acknowledged_at": "2026-04-20T10:35:00Z",
    "started_at": "2026-04-20T11:00:00Z",
    "delegation_message": "フェーズ2の実装をお願いします。期限は2026-05-15です。",
    "expected_completion": "2026-05-15",
    
    "events": [
      {
        "event_id": 5001,
        "event_type": "delegated",
        "actor": {
          "id": "em-1",
          "type": "em"
        },
        "message": "Task delegated to Engineer Bob",
        "timestamp": "2026-04-20T10:30:00Z"
      },
      {
        "event_id": 5002,
        "event_type": "acknowledged",
        "actor": {
          "id": "eng-3",
          "type": "engineer"
        },
        "message": "Assignment acknowledged",
        "timestamp": "2026-04-20T10:35:00Z"
      },
      {
        "event_id": 5003,
        "event_type": "started",
        "actor": {
          "id": "eng-3",
          "type": "engineer"
        },
        "message": "Work started",
        "timestamp": "2026-04-20T11:00:00Z"
      }
    ],
    
    "comments": [
      {
        "comment_id": 7001,
        "author": {
          "id": "eng-3",
          "type": "engineer",
          "name": "Engineer Bob"
        },
        "content": "Backend implementation started. On track for deadline.",
        "comment_type": "update",
        "created_at": "2026-04-20T11:30:00Z"
      }
    ]
  }
}
```

---

### 4. 委譲を確認応答

```http
PUT /api/v1/delegations/{delegation_id}/acknowledge
Content-Type: application/json
Authorization: Bearer {token}

Request Body:
{
  "message": "タスク受け取りました。実装を開始します。",
  "expected_start": "2026-04-20T11:00:00Z"
}
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "delegation_id": 1001,
    "status": "acknowledged",
    "acknowledged_at": "2026-04-20T10:35:00Z",
    "acknowledged_by": "eng-3",
    "acknowledgement_message": "タスク受け取りました。実装を開始します。"
  }
}
```

---

### 5. 委譲を拒否

```http
POST /api/v1/delegations/{delegation_id}/reject
Content-Type: application/json
Authorization: Bearer {token}

Request Body:
{
  "reason": "現在のプロジェクト負荷が高く、期限までに実装できません。",
  "suggested_reassign_to": "eng-4"  -- 他のエージェントへの再委譲提案
}
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "delegation_id": 1001,
    "status": "rejected",
    "rejected_at": "2026-04-20T10:40:00Z",
    "rejected_by": "eng-3",
    "rejection_reason": "現在のプロジェクト負荷が高く、期限までに実装できません。",
    "suggested_reassign_to": "eng-4",
    "next_action": "Delegation returned to em-1 for re-delegation"
  }
}
```

---

### 6. コメント追加

```http
POST /api/v1/delegations/{delegation_id}/comments
Content-Type: application/json
Authorization: Bearer {token}

Request Body:
{
  "content": "APIスキーマ設計が完了しました。実装フェーズに進める準備ができています。",
  "comment_type": "update"  -- 'note' | 'update' | 'risk' | 'blocker'
}
```

**レスポンス** (201 Created):

```json
{
  "success": true,
  "data": {
    "comment_id": 7002,
    "delegation_id": 1001,
    "author": {
      "id": "eng-3",
      "type": "engineer",
      "name": "Engineer Bob"
    },
    "content": "APIスキーマ設計が完了しました。実装フェーズに進める準備ができています。",
    "comment_type": "update",
    "created_at": "2026-04-20T15:00:00Z"
  }
}
```

---

### 7. 委譲条件検索

```http
GET /api/v1/delegations?status=pending&agent_id=em-1
Authorization: Bearer {token}

Query Parameters:
  - status: pending|acknowledged|in_progress|completed|rejected
  - agent_id: {agent_id} (委譲先エージェント)
  - from_agent_id: {agent_id} (委譲元エージェント)
  - task_id: {task_id}
  - scope: workflow|phase|task
  - created_after: {ISO8601_datetime}
  - created_before: {ISO8601_datetime}
  - limit: 50 (default), max: 200
  - offset: 0
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "delegations": [
      {
        "delegation_id": 1001,
        "task_id": 2404,
        "task_title": "【設計】エージェント間タスク委譲API",
        "from_agent_id": "em-1",
        "to_agent_id": "eng-3",
        "status": "acknowledged",
        "delegated_at": "2026-04-20T10:30:00Z",
        "acknowledged_at": "2026-04-20T10:35:00Z"
      },
      {
        "delegation_id": 1002,
        "task_id": 2405,
        "task_title": "【実装】タスク委譲API エンドポイント",
        "from_agent_id": "em-1",
        "to_agent_id": "eng-4",
        "status": "pending",
        "delegated_at": "2026-04-20T10:45:00Z",
        "acknowledged_at": null
      }
    ],
    "total": 42,
    "pending_count": 15,
    "limit": 50,
    "offset": 0
  }
}
```

---

## 委譲チェーン管理

### 委譲フロー（正常系）

```
[orchestrator] delegated_at=2026-04-20T10:00:00Z
    ↓
[em-1] status=pending (受信待機)
    ↓ acknowledged_at=2026-04-20T10:05:00Z
[em-1] status=acknowledged (受け入れ）
    ↓ (EM が engineer へ再委譲)
[em-1] delegated_at=2026-04-20T10:30:00Z
    ↓
[eng-3] status=pending (受信待機)
    ↓ acknowledged_at=2026-04-20T10:35:00Z
[eng-3] status=acknowledged
    ↓ started_at=2026-04-20T11:00:00Z
[eng-3] status=in_progress (実行中)
    ↓ completed_at=2026-04-20T16:00:00Z
[eng-3] status=completed (完了)
```

### 再委譲フロー（リジェクト発生時）

```
[em-1] →(delegate)→ [eng-3]
                      ↓ status=rejected
                      ↓ parent_delegation_id=1001
[em-1] →(delegate)→ [eng-4]  (新しいエンジニアに再委譲)
                      ↓
                   acknowledged
```

### チェーン深さの制限

```
max_delegation_depth = 3

❌ 許可されない:
orchestrator → em-1 → eng-1 → ? (深さ3超過)

✓ 許可される:
orchestrator → em-1 → eng-1 (深さ2)
orchestrator → em-1 → eng-2 (eng-1 の再委譲)
```

---

## エラーハンドリング

### エラーコード定義

| コード | HTTP | 説明 |
|-------|------|------|
| `TASK_NOT_FOUND` | 404 | タスクが存在しない |
| `AGENT_NOT_FOUND` | 404 | エージェントが存在しない |
| `INVALID_DELEGATION` | 400 | 無効な委譲（同じエージェントなど） |
| `DELEGATION_NOT_FOUND` | 404 | 委譲が存在しない |
| `INVALID_STATUS_TRANSITION` | 400 | 無効なステータス遷移 |
| `MAX_DELEGATION_DEPTH_EXCEEDED` | 400 | 委譲チェーン深さ超過 |
| `PERMISSION_DENIED` | 403 | 権限不足 |
| `CONCURRENT_MODIFICATION` | 409 | 同時更新エラー |

### エラーレスポンス例

```json
{
  "success": false,
  "error": {
    "code": "MAX_DELEGATION_DEPTH_EXCEEDED",
    "message": "Cannot delegate: maximum delegation chain depth (3) exceeded",
    "details": {
      "current_depth": 3,
      "max_allowed": 3,
      "delegation_chain": [
        {"from": "orchestrator", "to": "em-1"},
        {"from": "em-1", "to": "eng-1"},
        {"from": "eng-1", "to": "?"}
      ]
    }
  }
}
```

---

## ステータス遷移

### タスク委譲のステータスマシン

```
pending (初期状態)
  ├→ acknowledged (受け入れ)
  │   ├→ in_progress (実作業開始)
  │   │   └→ completed (完了)
  │   └→ reassigned (再委譲)
  │
  ├→ rejected (拒否)
  │   └→ pending (再委譲可)
  │
  └→ (タイムアウト) → error (期限超過エラー)
```

### 遷移ルール

| 現在のステータス | 可能な遷移 | トリガー | 条件 |
|-----------------|----------|--------|------|
| `pending` | → `acknowledged` | `PUT /acknowledge` | 委譲先エージェントのみ |
| `pending` | → `rejected` | `POST /reject` | 委譲先エージェントのみ |
| `acknowledged` | → `in_progress` | `PUT /start` | 委譲先エージェントのみ |
| `acknowledged` | → `reassigned` | `POST /reassign` | 委譲元エージェントのみ |
| `in_progress` | → `completed` | `PUT /complete` | 委譲先エージェントのみ |
| `in_progress` | → `rejected` | `POST /reject` | 委譲先エージェントのみ |
| `rejected` | → `pending` (新しいdeleg_id) | `POST /re-delegate` | 委譲元エージェントのみ |

---

## 実装チェックリスト

### DBスキーマ
- [ ] `task_delegations` テーブル作成
- [ ] `delegation_events` テーブル作成
- [ ] `delegation_comments` テーブル作成
- [ ] `dev_tasks` テーブル拡張（3カラム追加）
- [ ] インデックス作成（10個）
- [ ] マイグレーション SQL スクリプト作成

### REST API
- [ ] POST `/api/v1/tasks/{id}/delegate` 実装
- [ ] GET `/api/v1/tasks/{id}/delegations` 実装
- [ ] GET `/api/v1/delegations/{id}` 実装
- [ ] PUT `/api/v1/delegations/{id}/acknowledge` 実装
- [ ] POST `/api/v1/delegations/{id}/reject` 実装
- [ ] POST `/api/v1/delegations/{id}/comments` 実装
- [ ] GET `/api/v1/delegations?status=...` 実装

### ビジネスロジック
- [ ] ステータス遷移バリデーション
- [ ] 委譲チェーン深さチェック
- [ ] タイムアウト検出ロジック
- [ ] イベントログ記録
- [ ] 再委譲メカニズム

### テスト
- [ ] unit テスト（API エンドポイント）
- [ ] integration テスト（ワークフロー全体）
- [ ] BDD テスト (`features/task_delegation.feature`)
- [ ] UAT テスト（委譲チェーン検証）

---

## 関連ドキュメント

- [DATA-MODEL.md](design/DATA-MODEL.md) - 全体データモデル
- [WORKFLOW-TEMPLATE-DESIGN.md](design/WORKFLOW-TEMPLATE-DESIGN.md) - ワークフロー管理 API
- [test_delegation_chain.py](test_uat/test_delegation_chain.py) - UAT テスト
- [mission_tables.sql](dashboard/migrations/007_create_missions_tables.sql) - ミッション テーブル定義

---

## バージョン履歴

| バージョン | 日時 | 変更内容 |
|-----------|------|--------|
| v1.0 | 2026-04-20 | 初版作成 |

---

*このドキュメントは タスク #2404 の設計フェーズにおける API・DBスキーマ仕様です。*
