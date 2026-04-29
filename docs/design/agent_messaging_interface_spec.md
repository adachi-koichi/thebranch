# AIエージェント間メッセージング・通知システム（MVP フェーズ 1）
## 技術仕様書

**Document Version:** 1.0  
**Date:** 2026-04-30  
**Tech Lead:** AI-Engineer (Task #2547)  
**Status:** Design Phase  

---

## 1. システム概要

### スコープ（MVP フェーズ 1）
- **対象イベント**: タスク完了通知のみ
- **配信チャネル**: WebSocket + Webhook（POST）
- **認証**: Bearer Token（既存 API 認証基盤を流用）
- **対象**: orchestrator, workflow execution team 間のイベント通知

### 非対象（将来実装）
- エスカレーション通知
- 高度なフィルター・ルーティング
- メッセージキュー（Rabbit MQ 等）
- リトライロジック（フェーズ 2）

---

## 2. WebSocket イベント仕様

### 2.1 エンドポイント

```
ws://localhost:8000/ws
```

**認証:**
- クエリパラメータ: `?token=<jwt_token>`
- または ヘッダ: `Authorization: Bearer <jwt_token>`

### 2.2 イベント: task.completed

**説明:** タスク完了時に発火するイベント

**ペイロード（JSON）:**

```json
{
  "type": "task.completed",
  "timestamp": "2026-04-30T06:57:03Z",
  "task_id": 2547,
  "task_title": "AIエージェント間メッセージング・通知システム実装",
  "workflow_id": "2547",
  "team_name": "agent-messaging",
  "executor": {
    "user_id": "usr_001",
    "username": "adachi-koichi",
    "role": "ai-engineer"
  },
  "status": "completed",
  "priority": 1,
  "completion_time_ms": 1800000,
  "metadata": {
    "tag_ids": ["urgent", "mvp"],
    "category": "infra",
    "phase": "design"
  }
}
```

**フィールド定義:**

| フィールド | 型 | 説明 | 例 |
|---|---|---|---|
| `type` | string | イベントタイプ（固定） | "task.completed" |
| `timestamp` | ISO 8601 | イベント発生時刻（UTC） | "2026-04-30T06:57:03Z" |
| `task_id` | integer | タスク ID | 2547 |
| `task_title` | string | タスクタイトル | "..." |
| `workflow_id` | string | ワークフロー ID | "2547" |
| `team_name` | string | チーム名 | "agent-messaging" |
| `executor.user_id` | string | 実行者ユーザー ID | "usr_001" |
| `executor.username` | string | 実行者ユーザー名 | "adachi-koichi" |
| `executor.role` | string | 実行者ロール | "ai-engineer" \| "pm" \| "em" |
| `status` | string | 最終ステータス | "completed" |
| `priority` | integer | タスク優先度 | 1-5 |
| `completion_time_ms` | integer | 完了までの時間（ミリ秒） | 1800000 |
| `metadata.tag_ids` | array | タスクタグ | ["urgent"] |
| `metadata.category` | string | カテゴリ | "infra" \| "feature" \| "design" |
| `metadata.phase` | string | フェーズ | "design" \| "implementation" \| "test" |

### 2.3 WebSocket クライアント実装例（Python）

```python
import asyncio
import websockets
import json
from typing import Callable

class TaskCompletionListener:
    def __init__(self, token: str, on_message: Callable):
        self.token = token
        self.on_message = on_message
        self.uri = f"ws://localhost:8000/ws?token={token}"
    
    async def connect(self):
        async with websockets.connect(self.uri) as ws:
            async for message in ws:
                event = json.loads(message)
                if event.get("type") == "task.completed":
                    await self.on_message(event)

# 使用例
async def handle_task_completion(event):
    print(f"Task {event['task_id']} completed: {event['task_title']}")
    # orchestrator が依存タスクのアンブロック等を実行

listener = TaskCompletionListener(
    token="your_jwt_token",
    on_message=handle_task_completion
)
asyncio.run(listener.connect())
```

---

## 3. Webhook API 仕様

### 3.1 Webhook 登録エンドポイント

**Endpoint:** `POST /api/webhooks/register`

**リクエストヘッダ:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**リクエストボディ:**

```json
{
  "name": "orchestrator-completion-notifier",
  "event_type": "task.completed",
  "target_url": "https://external-system.example.com/webhooks/tasks",
  "auth_type": "bearer",
  "secret_key": "whsec_abc123xyz...",
  "is_active": true,
  "retry_policy": {
    "max_retries": 3,
    "retry_backoff_ms": 1000,
    "timeout_ms": 5000
  },
  "headers": {
    "X-Custom-Header": "custom-value"
  }
}
```

**フィールド定義:**

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `name` | string | ✓ | Webhook 識別名 |
| `event_type` | string | ✓ | イベントタイプ（"task.completed"） |
| `target_url` | string (URL) | ✓ | Webhook ターゲット URL |
| `auth_type` | string | ✓ | 認証タイプ（"bearer" \| "hmac-sha256"） |
| `secret_key` | string | ✓ | Bearer token または HMAC シークレット |
| `is_active` | boolean | - | 有効/無効（デフォルト: true） |
| `retry_policy.max_retries` | integer | - | 最大リトライ回数（デフォルト: 3） |
| `retry_policy.retry_backoff_ms` | integer | - | リトライ間隔（ms）（デフォルト: 1000） |
| `retry_policy.timeout_ms` | integer | - | リクエスト Timeout（ms）（デフォルト: 5000） |
| `headers` | object | - | カスタムリクエストヘッダ |

**レスポンス（201 Created）:**

```json
{
  "webhook_id": "wh_abc123xyz...",
  "name": "orchestrator-completion-notifier",
  "event_type": "task.completed",
  "target_url": "https://external-system.example.com/webhooks/tasks",
  "is_active": true,
  "created_at": "2026-04-30T06:57:03Z",
  "last_triggered_at": null
}
```

### 3.2 Webhook 削除エンドポイント

**Endpoint:** `DELETE /api/webhooks/{webhook_id}`

**認証:** Bearer Token

**レスポンス（204 No Content）**

### 3.3 Webhook 一覧取得

**Endpoint:** `GET /api/webhooks?event_type=task.completed`

**認証:** Bearer Token

**レスポンス（200 OK）:**

```json
{
  "webhooks": [
    {
      "webhook_id": "wh_abc123xyz...",
      "name": "orchestrator-completion-notifier",
      "event_type": "task.completed",
      "target_url": "https://external-system.example.com/webhooks/tasks",
      "is_active": true,
      "created_at": "2026-04-30T06:57:03Z",
      "last_triggered_at": "2026-04-30T06:50:00Z",
      "trigger_count": 42
    }
  ],
  "total": 1
}
```

### 3.4 Webhook ペイロード

**HTTP POST リクエスト:**

```
POST https://external-system.example.com/webhooks/tasks HTTP/1.1
Host: external-system.example.com
Authorization: Bearer <secret_key>
X-Custom-Header: custom-value
X-Webhook-ID: wh_abc123xyz...
X-Webhook-Timestamp: 2026-04-30T06:57:03Z
X-Webhook-Signature: sha256=<hmac_signature>
Content-Type: application/json

{
  "type": "task.completed",
  "timestamp": "2026-04-30T06:57:03Z",
  "task_id": 2547,
  "task_title": "AIエージェント間メッセージング・通知システム実装",
  "workflow_id": "2547",
  "team_name": "agent-messaging",
  "executor": {
    "user_id": "usr_001",
    "username": "adachi-koichi",
    "role": "ai-engineer"
  },
  "status": "completed",
  "priority": 1,
  "completion_time_ms": 1800000,
  "metadata": {
    "tag_ids": ["urgent", "mvp"],
    "category": "infra",
    "phase": "design"
  }
}
```

**署名検証（HMAC-SHA256）:**

```python
import hmac
import hashlib

def verify_webhook_signature(payload_body: bytes, secret: str, signature: str) -> bool:
    expected_signature = "sha256=" + hmac.new(
        secret.encode(),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)
```

---

## 4. データベーススキーマ

### 4.1 task_completion_events テーブル

**目的:** タスク完了イベントの履歴管理・監査・リトライ制御

```sql
CREATE TABLE task_completion_events (
    -- 主キー・ID管理
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- イベント基本情報
    task_id INTEGER NOT NULL,
    workflow_id TEXT NOT NULL,
    team_name TEXT NOT NULL,
    
    -- 実行者情報
    executor_user_id TEXT NOT NULL,
    executor_username TEXT NOT NULL,
    executor_role TEXT NOT NULL CHECK(executor_role IN ('ai-engineer', 'pm', 'em', 'admin')),
    
    -- タスク完了情報
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed')),
    priority INTEGER NOT NULL DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
    completion_time_ms INTEGER,
    
    -- メタデータ
    tag_ids TEXT,  -- JSON Array: ["urgent", "mvp"]
    category TEXT CHECK(category IN ('infra', 'feature', 'design', 'test')),
    phase TEXT CHECK(phase IN ('design', 'implementation', 'test', 'review')),
    
    -- イベント配信状態
    event_status TEXT NOT NULL DEFAULT 'triggered' CHECK(event_status IN ('triggered', 'dispatched', 'acked', 'failed')),
    
    -- タイムスタンプ
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triggered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_webhook_attempt_at DATETIME,
    
    -- インデックス用フィールド
    UNIQUE(task_id, triggered_at),
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE INDEX idx_task_completion_events_task_id ON task_completion_events(task_id);
CREATE INDEX idx_task_completion_events_workflow_id ON task_completion_events(workflow_id);
CREATE INDEX idx_task_completion_events_team_name ON task_completion_events(team_name);
CREATE INDEX idx_task_completion_events_created_at ON task_completion_events(created_at);
CREATE INDEX idx_task_completion_events_event_status ON task_completion_events(event_status);
```

### 4.2 webhook_subscriptions テーブル

**目的:** Webhook 登録情報の管理

```sql
CREATE TABLE webhook_subscriptions (
    -- 主キー
    webhook_id TEXT PRIMARY KEY,  -- UUID: "wh_abc123xyz..."
    
    -- ユーザー情報
    user_id TEXT NOT NULL,
    
    -- Webhook 基本設定
    name TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'task.completed' CHECK(event_type IN ('task.completed')),
    target_url TEXT NOT NULL,
    
    -- 認証情報
    auth_type TEXT NOT NULL CHECK(auth_type IN ('bearer', 'hmac-sha256')),
    secret_key_hash TEXT NOT NULL,  -- ハッシュ化（平文保存禁止）
    
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
    
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX idx_webhook_subscriptions_user_id ON webhook_subscriptions(user_id);
CREATE INDEX idx_webhook_subscriptions_event_type ON webhook_subscriptions(event_type);
CREATE INDEX idx_webhook_subscriptions_is_active ON webhook_subscriptions(is_active);
```

### 4.3 webhook_delivery_logs テーブル

**目的:** Webhook 配信ログ・リトライ制御・監査

```sql
CREATE TABLE webhook_delivery_logs (
    -- 主キー
    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 関連ID
    webhook_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    
    -- 配信情報
    attempt_number INTEGER NOT NULL DEFAULT 1,
    delivery_status TEXT NOT NULL CHECK(delivery_status IN ('pending', 'sent', 'acked', 'failed', 'permanent_failure')),
    
    -- HTTP レスポンス情報
    http_status_code INTEGER,
    response_body TEXT,  -- 失敗時のレスポンス
    
    -- リトライ情報
    next_retry_at DATETIME,
    last_error_message TEXT,
    
    -- タイムスタンプ
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME,
    
    FOREIGN KEY(webhook_id) REFERENCES webhook_subscriptions(webhook_id),
    FOREIGN KEY(event_id) REFERENCES task_completion_events(event_id)
);

CREATE INDEX idx_webhook_delivery_logs_webhook_id ON webhook_delivery_logs(webhook_id);
CREATE INDEX idx_webhook_delivery_logs_event_id ON webhook_delivery_logs(event_id);
CREATE INDEX idx_webhook_delivery_logs_delivery_status ON webhook_delivery_logs(delivery_status);
CREATE INDEX idx_webhook_delivery_logs_next_retry_at ON webhook_delivery_logs(next_retry_at);
```

---

## 5. API スキーマ（OpenAPI 3.0 簡易版）

```yaml
openapi: 3.0.0
info:
  title: Agent Messaging & Notification System API
  version: 1.0.0
  description: MVP Phase 1 - Task Completion Notifications

servers:
  - url: http://localhost:8000/api
    description: Development
  - url: https://thebranch.example.com/api
    description: Production

paths:
  /webhooks/register:
    post:
      summary: Register a new webhook
      operationId: registerWebhook
      tags:
        - Webhooks
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/WebhookRegistrationRequest'
      responses:
        '201':
          description: Webhook created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/WebhookResponse'
        '400':
          description: Invalid request
        '401':
          description: Unauthorized

  /webhooks/{webhook_id}:
    delete:
      summary: Delete a webhook
      operationId: deleteWebhook
      tags:
        - Webhooks
      parameters:
        - name: webhook_id
          in: path
          required: true
          schema:
            type: string
      security:
        - BearerAuth: []
      responses:
        '204':
          description: Webhook deleted
        '404':
          description: Webhook not found

  /webhooks:
    get:
      summary: List webhooks
      operationId: listWebhooks
      tags:
        - Webhooks
      parameters:
        - name: event_type
          in: query
          schema:
            type: string
            enum: [task.completed]
      security:
        - BearerAuth: []
      responses:
        '200':
          description: Webhook list
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/WebhookListResponse'

  /ws:
    get:
      summary: WebSocket endpoint for real-time events
      operationId: connectWebSocket
      tags:
        - WebSocket
      parameters:
        - name: token
          in: query
          schema:
            type: string
          required: true
      responses:
        '101':
          description: Switching Protocols (WebSocket upgrade)

components:
  schemas:
    WebhookRegistrationRequest:
      type: object
      required:
        - name
        - event_type
        - target_url
        - auth_type
        - secret_key
      properties:
        name:
          type: string
          example: orchestrator-completion-notifier
        event_type:
          type: string
          enum: [task.completed]
        target_url:
          type: string
          format: uri
          example: https://external-system.example.com/webhooks/tasks
        auth_type:
          type: string
          enum: [bearer, hmac-sha256]
        secret_key:
          type: string
          example: whsec_abc123xyz...
        is_active:
          type: boolean
          default: true
        retry_policy:
          $ref: '#/components/schemas/RetryPolicy'
        headers:
          type: object
          additionalProperties:
            type: string

    RetryPolicy:
      type: object
      properties:
        max_retries:
          type: integer
          default: 3
        retry_backoff_ms:
          type: integer
          default: 1000
        timeout_ms:
          type: integer
          default: 5000

    WebhookResponse:
      type: object
      properties:
        webhook_id:
          type: string
          example: wh_abc123xyz...
        name:
          type: string
        event_type:
          type: string
        target_url:
          type: string
        is_active:
          type: boolean
        created_at:
          type: string
          format: date-time
        last_triggered_at:
          type: string
          format: date-time
          nullable: true

    WebhookListResponse:
      type: object
      properties:
        webhooks:
          type: array
          items:
            $ref: '#/components/schemas/WebhookResponse'
        total:
          type: integer

    TaskCompletionEvent:
      type: object
      properties:
        type:
          type: string
          enum: [task.completed]
        timestamp:
          type: string
          format: date-time
        task_id:
          type: integer
        task_title:
          type: string
        workflow_id:
          type: string
        team_name:
          type: string
        executor:
          $ref: '#/components/schemas/Executor'
        status:
          type: string
          enum: [completed]
        priority:
          type: integer
          minimum: 1
          maximum: 5
        completion_time_ms:
          type: integer
        metadata:
          $ref: '#/components/schemas/EventMetadata'

    Executor:
      type: object
      properties:
        user_id:
          type: string
        username:
          type: string
        role:
          type: string
          enum: [ai-engineer, pm, em, admin]

    EventMetadata:
      type: object
      properties:
        tag_ids:
          type: array
          items:
            type: string
        category:
          type: string
          enum: [infra, feature, design, test]
        phase:
          type: string
          enum: [design, implementation, test, review]

  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

---

## 6. 実装計画

### フェーズ 1: MVP（タスク完了通知のみ）

**実装順序:**
1. データベースマイグレーション（4.1 - 4.3 スキーマ）
2. WebSocket エンドポイント実装（/ws）
3. Webhook 登録 API（POST /api/webhooks/register）
4. Webhook 削除・一覧 API
5. タスク完了イベント検出ロジック（task.py done 実行時）
6. イベント配信ロジック（WebSocket + Webhook）
7. テスト・E2E 検証

### フェーズ 2: 拡張機能（将来）
- エスカレーション通知
- メッセージフィルター・ルーティング
- リトライロジック（Exponential Backoff）
- メッセージキュー統合

---

## 7. セキュリティ考慮

- **認証:** JWT Bearer Token（既存基盤流用）
- **シークレット管理:** Webhook secret_key は bcrypt または Argon2 ハッシュで保存
- **署名検証:** HMAC-SHA256（ペイロード + タイムスタンプ）
- **HTTPS 必須:** 本番環境での Webhook ターゲット URL は HTTPS のみ
- **レート制限:** Webhook 配信レート制限（10 req/sec per webhook）

---

## 8. 参考リンク

- **既存 WebSocket 基盤:** `/dashboard/app.py` (SocketIO 統合検討)
- **既存認証:** `/dashboard/auth.py`
- **タスク管理:** `~/.claude/skills/task-manager-sqlite/`

---

**Next Step:** Engineer チーム 2 名による実装開始（フェーズ 1 に沿う）
