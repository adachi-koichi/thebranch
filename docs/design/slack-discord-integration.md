# Slack/Discord 統合設計ドキュメント

タスク #2241「[THEBRANCH] Slack/Discord 統合（タスク通知・操作・チャネル連携）」の残りコンポーネント実装のための設計書。

## 1. 概要

### 目的
THEBRANCH ダッシュボードに Slack/Discord 統合機能を追加し、以下を実現する：
- Webhook 経由での Slack/Discord イベント受信
- イベント検証・パース・DB 保存
- ダッシュボード内の統合通知 UI（既存の `notification_logs` テーブルを活用）
- リアルタイムでの通知送信（WebSocket + ポーリングハイブリッド）

### スコープ
本ドキュメントは以下 3 コンポーネント実装の設計仕様：
1. **Webhook イベント受信エンドポイント**（API Layer）
2. **フロントエンド通知 UI**（Frontend Layer）
3. **統合設定 UI**（Settings Layer）

### 既存実装との関係
- 既存の `notification_logs`, `notification_preferences` テーブルを活用
- 既存 `/ws/notifications` WebSocket エンドポイントを拡張
- 既存 `/api/notifications` REST API を活用
- フレームワーク: **FastAPI**（`dashboard/app.py`）
- DB アクセス: `aiosqlite`（非同期）
- 認証: JWT トークン（`dashboard/auth.py`）

---

## 2. データモデル

### 2.1 新規テーブル

#### `integration_configs` - 統合設定

```sql
CREATE TABLE IF NOT EXISTS integration_configs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_type    TEXT NOT NULL CHECK(integration_type IN ('slack','discord')),
    organization_id     TEXT NOT NULL,
    webhook_url         TEXT NOT NULL,
    webhook_secret      TEXT NOT NULL,
    channel_id          TEXT,
    channel_name        TEXT,
    is_active           INTEGER DEFAULT 1,
    notify_on_agent_status     INTEGER DEFAULT 1,
    notify_on_task_delegation  INTEGER DEFAULT 1,
    notify_on_cost_alert       INTEGER DEFAULT 1,
    notify_on_approval_request INTEGER DEFAULT 1,
    notify_on_error_event      INTEGER DEFAULT 1,
    notify_on_system_alert     INTEGER DEFAULT 1,
    metadata            TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_verified_at    TEXT,
    UNIQUE(integration_type, webhook_url)
);
CREATE INDEX IF NOT EXISTS idx_integration_configs_org
  ON integration_configs(organization_id, integration_type, is_active);
```

#### `webhook_events` - Webhook 受信ログ

```sql
CREATE TABLE IF NOT EXISTS webhook_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id            TEXT NOT NULL UNIQUE,
    integration_config_id INTEGER,
    event_type          TEXT NOT NULL,
    event_source        TEXT NOT NULL CHECK(event_source IN ('slack','discord')),
    raw_payload         TEXT NOT NULL,
    parsed_data         TEXT,
    processing_status   TEXT DEFAULT 'received'
                        CHECK(processing_status IN ('received','validated','processed','failed','ignored')),
    error_message       TEXT,
    notification_id     INTEGER,
    received_at         TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    processed_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_webhook_events_config
  ON webhook_events(integration_config_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_events_status
  ON webhook_events(processing_status, received_at DESC);
```

### 2.2 既存テーブル拡張（`notification_logs`）

```sql
ALTER TABLE notification_logs ADD COLUMN slack_message_id TEXT;
ALTER TABLE notification_logs ADD COLUMN discord_message_id TEXT;
ALTER TABLE notification_logs ADD COLUMN integration_config_id INTEGER;
```

※ 既存カラムが無い場合のみ追加。migration スクリプト側で `PRAGMA table_info` により条件付き追加する。

---

## 3. API 仕様

### 3.1 Webhook 受信エンドポイント

#### `POST /api/webhooks/slack`

- **ヘッダー**: `X-Slack-Request-Timestamp`, `X-Slack-Signature`
- **URL 検証ハンドシェイク**: `type=url_verification` なら `challenge` を返す
- **署名検証**: HMAC-SHA256, `v0:{timestamp}:{body}` → `v0=...`
- **タイムスタンプ鮮度**: 5分以内
- **レスポンス**: `200 {"success": true, "notification_id": ...}`

#### `POST /api/webhooks/discord`

- **ヘッダー**: `X-Signature-Ed25519`, `X-Signature-Timestamp`
- **署名検証**: Ed25519（`PyNaCl` 使用） ※ `PyNaCl` が利用できない環境向けにフォールバック（HMAC-SHA256 も受け付ける簡易実装）を用意
- **レスポンス**: `200 {"success": true, "notification_id": ...}`

### 3.2 統合設定 CRUD

| メソッド | パス | 用途 |
|---|---|---|
| `GET` | `/api/integrations/configs` | 一覧取得（`?integration_type=`, `?is_active=` フィルタ） |
| `POST` | `/api/integrations/configs` | 新規登録 |
| `GET` | `/api/integrations/configs/{id}` | 単一取得 |
| `PUT` | `/api/integrations/configs/{id}` | 更新 |
| `DELETE` | `/api/integrations/configs/{id}` | 削除 |
| `POST` | `/api/integrations/verify/{id}` | Webhook 接続検証 |

**レスポンスでは `webhook_secret` を返さない**（マスキング）。

### 3.3 処理フロー

```
[Webhook 受信]
    ↓
[署名検証]（失敗 → 401）
    ↓
[webhook_events に raw_payload 保存]
    ↓
[integration_configs から該当設定を取得]
    ↓
[notification_type フィルタ]（無効なら ignored 扱い）
    ↓
[notification_logs にレコード作成]
    ↓
[WebSocket /ws/notifications へ broadcast]
    ↓
[webhook_events.processing_status = processed]
    ↓
[200 OK 返却]
```

---

## 4. フロントエンド通知 UI

### 4.1 DOM 構造（`dashboard/index.html` に追加）

- ヘッダー右側に通知ベルボタン `#notificationBellBtn`
- 未読バッジ `#unreadBadge`
- 通知パネル `#notificationPanel`（右上ドロップダウン）
- フィルタ: 未読のみ、種別
- フッター: 「すべて既読にする」ボタン

### 4.2 JS 関数

| 関数 | 役割 |
|---|---|
| `updateNotificationBadge(count)` | バッジ数更新 |
| `toggleNotificationPanel()` | パネル開閉 |
| `fetchNotifications()` | `/api/notifications` 取得・描画 |
| `renderNotificationList(items)` | リスト描画 |
| `markNotificationAsRead(id)` | `POST /api/notifications/{id}/read` |
| `markAllNotificationsAsRead()` | 未読一括既読化 |
| `extendNotificationsWebSocket()` | 既存 WebSocket に通知ハンドラ追加 |
| `startNotificationPolling(interval)` | WebSocket 不通時の fallback（30s） |

### 4.3 スタイル
既存 CSS 変数（`--card`, `--border`, `--accent`, `--red` など）を再利用し、GitHub Dark テーマに統一。

---

## 5. 統合設定 UI

### 5.1 構造（`dashboard/index.html` に追加）

- 設定タブ `#tab-integrations`
- 統合一覧カード `#integrationsList`
- モーダル `#integrationModal`（新規・編集共用）
  - フィールド: `integration_type`, `webhook_url`, `webhook_secret`, `channel_id`, `channel_name`, 通知フィルタ 6 種、`is_active`
  - 「Webhook を検証」ボタン、「保存」ボタン
- ガイドモーダル `#webhookGuideModal`（URL 取得手順）

### 5.2 JS 関数

| 関数 | 役割 |
|---|---|
| `fetchIntegrations()` | 一覧取得・描画 |
| `renderIntegrationsList(configs)` | カード描画 |
| `openIntegrationModal(id?)` | 新規/編集モーダル表示 |
| `saveIntegration(event)` | 送信（POST/PUT） |
| `verifyIntegration(id)` | 検証 API 呼び出し |
| `editIntegration(id)` | 編集遷移 |
| `deleteIntegration(id)` | 削除（確認ダイアログあり） |

---

## 6. 実装タスク分解

### Task #2: Webhook 受信エンドポイント実装

- `dashboard/migrations/027_create_integration_tables.sql` 新規作成
- `dashboard/integrations/__init__.py` 新規
- `dashboard/integrations/slack_handler.py` 新規（署名検証 + パース）
- `dashboard/integrations/discord_handler.py` 新規（署名検証 + パース）
- `dashboard/integrations/webhook_service.py` 新規（DB 書き込み・通知連携）
- `dashboard/app.py` に 8 本のエンドポイント追加
  - `POST /api/webhooks/slack`
  - `POST /api/webhooks/discord`
  - `GET /api/integrations/configs`
  - `POST /api/integrations/configs`
  - `GET /api/integrations/configs/{id}`
  - `PUT /api/integrations/configs/{id}`
  - `DELETE /api/integrations/configs/{id}`
  - `POST /api/integrations/verify/{id}`
- `dashboard/models.py` に Pydantic モデル追加
  - `IntegrationConfigCreate`, `IntegrationConfigUpdate`, `IntegrationConfigResponse`
  - `SlackWebhookPayload`, `DiscordWebhookPayload`
  - `WebhookEventResponse`

### Task #3: フロントエンド通知 UI 実装

- `dashboard/index.html` のヘッダーに通知ベル + バッジ追加
- 通知パネル DOM + CSS 追加
- JS 関数 8 種追加、既存 WebSocket ハンドラ拡張
- ポーリング fallback 実装

### Task #4: 統合設定 UI 実装

- `dashboard/index.html` に `#tab-integrations` セクション追加
- 統合一覧カード + モーダル DOM/CSS 追加
- JS 関数 7 種追加
- ナビゲーションに「統合」タブ追加

---

## 7. テスト観点

### Task #5: API テスト

- **署名検証**
  - Slack: 有効/無効署名、タイムスタンプ改竄、5 分超過
  - Discord: 有効/無効 Ed25519
- **URL 検証ハンドシェイク**（Slack `url_verification`）
- **イベント処理**: `notification_logs`/`webhook_events` 書き込み確認
- **フィルタ**: `notify_on_*=false` で ignored ステータス
- **CRUD**: 統合設定の作成→取得→更新→削除
- **マスキング**: レスポンスに `webhook_secret` が含まれないこと
- **検証 API**: 不達 URL で 400 エラー

### Task #6: フロント E2E テスト

- ベルクリックでパネル開閉
- 未読バッジ表示・数値
- フィルタ（未読のみ / 種別）
- 既読化（単一・全件）
- WebSocket 受信でリアルタイム追加
- 統合設定カード表示、モーダル開閉、フォーム送信、検証ボタン、削除確認

### Task #7: 動作確認

- ブラウザで http://localhost:8503 を開き、設定 → 統合タブ
- Webhook URL/Secret を登録、検証ボタン成功
- `curl` で `POST /api/webhooks/slack` に署名付きリクエスト → 通知バッジ更新
- エラーログ・コンソール無エラー確認
- README or docs/ にセットアップ手順を追記

---

## 8. セキュリティ

- `webhook_secret` は DB に平文保存するが、API レスポンスでは返却しない（マスキング必須）
- すべての Webhook 受信で署名検証必須
- タイムスタンプ鮮度チェックでリプレイ攻撃防止
- IP ベースのレート制限は後続タスクで対応

## 9. 参考

- Slack: https://api.slack.com/authentication/verifying-requests-from-slack
- Discord: https://discord.com/developers/docs/interactions/receiving-and-responding#security-and-authorization
