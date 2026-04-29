# AIエージェント マーケットプレイス API 設計

**Document Version**: 1.0  
**Created**: 2026-04-26  
**Related Task**: #2494 Tech Lead: AIエージェントマーケットプレイス設計  
**Related Schema**: `marketplace_db_schema.md`

---

## 1. 概要

THEBRANCH マーケットプレイスの RESTful API 仕様。3つのメインエンドポイントで検索・詳細取得・インストール機能を提供します。

### ベース URL

```
GET /api/marketplace/
POST /api/marketplace/
```

### 認証

全エンドポイント共通：
- **必須**: Bearer Token（Authorization ヘッダー）
- **詳細**: ゼロトラスト原則に基づく認証（#2755）

```
Authorization: Bearer {api_token}
```

---

## 2. エンドポイント設計

### 2.1 エージェント一覧・検索 API

**エンドポイント**: `GET /api/marketplace/agents`

**目的**: マーケットプレイス内のエージェント一覧を取得。検索・フィルター・ソート・ページネーション対応。

#### リクエスト

```http
GET /api/marketplace/agents?search=task&category=hr&sort=rating&order=desc&page=1&limit=20
Authorization: Bearer {token}
```

**クエリパラメータ**:

| パラメータ | 型 | 必須 | 説明 | 例 |
|---|---|---|---|---|
| search | string | ❌ | フリーテキスト検索（FTS5） | `task automation` |
| category | string | ❌ | カテゴリID またはカテゴリ名 | `hr` / `f123e456...` |
| visibility | string | ❌ | 公開範囲フィルター | `public`, `team`, `private` |
| sort | string | ❌ | ソートキー（デフォルト: score） | `score`, `rating`, `installation_count`, `created_at` |
| order | string | ❌ | ソート順（デフォルト: desc） | `asc`, `desc` |
| page | integer | ❌ | ページ番号（デフォルト: 1） | `1`, `2`, `3` |
| limit | integer | ❌ | 1ページあたりの件数（デフォルト: 20, 最大: 100） | `20`, `50` |
| min_rating | number | ❌ | 最小評価スコア（1.0～5.0） | `3.5` |
| status | string | ❌ | ステータスフィルター | `published`, `draft`, `archived` |

#### レスポンス

**成功時** (200 OK):

```json
{
  "success": true,
  "data": {
    "agents": [
      {
        "id": "agent_123e456...",
        "name": "HR Task Automation",
        "description": "自動化された人事タスク管理エージェント",
        "category": {
          "id": "cat_hr_123...",
          "name": "HR"
        },
        "publisher": {
          "id": "user_456...",
          "username": "hr_team"
        },
        "version": "1.2.0",
        "icon_url": "https://...",
        "installation_count": 234,
        "rating": 4.5,
        "review_count": 42,
        "status": "published",
        "visibility": "public",
        "tags": ["automation", "hr", "productivity"],
        "capabilities": ["task_scheduling", "approval_workflow", "reporting"],
        "created_at": "2026-01-15T10:30:00Z",
        "published_at": "2026-01-20T14:00:00Z"
      },
      ...
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total_count": 156,
      "total_pages": 8,
      "has_next": true,
      "has_prev": false
    },
    "filters": {
      "applied": {
        "search": "task",
        "category": "hr",
        "sort": "rating",
        "order": "desc"
      },
      "available_categories": [
        { "id": "cat_hr_123...", "name": "HR", "count": 34 },
        { "id": "cat_fin_456...", "name": "Finance", "count": 28 },
        { "id": "cat_mkt_789...", "name": "Marketing", "count": 42 }
      ]
    }
  },
  "meta": {
    "request_id": "req_xyz789...",
    "timestamp": "2026-04-26T15:49:57Z"
  }
}
```

**エラー時**:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_CATEGORY",
    "message": "指定されたカテゴリが見つかりません",
    "details": {
      "category": "invalid_cat_123"
    }
  },
  "meta": {
    "request_id": "req_xyz789...",
    "timestamp": "2026-04-26T15:49:57Z"
  }
}
```

#### 実装ノート

- **FTS5 検索**: search パラメータは SQLite FTS5 で全文検索実行
- **キャッシング**: 検索結果は 5 分間キャッシュ（Redis 推奨）
- **レート制限**: 1 ユーザーあたり 100 requests/minute
- **権限**: visibility フィルターは認証ユーザーの権限に基づいて自動適用

---

### 2.2 エージェント詳細 API

**エンドポイント**: `GET /api/marketplace/agents/{id}`

**目的**: 指定されたエージェントの詳細情報を取得。

#### リクエスト

```http
GET /api/marketplace/agents/agent_123e456...
Authorization: Bearer {token}
```

**パスパラメータ**:

| パラメータ | 型 | 説明 |
|---|---|---|
| id | string | エージェントID（UUID） |

#### レスポンス

**成功時** (200 OK):

```json
{
  "success": true,
  "data": {
    "agent": {
      "id": "agent_123e456...",
      "name": "HR Task Automation",
      "description": "自動化された人事タスク管理エージェント",
      "detailed_description": "このエージェントは...\n\n## 機能\n- タスク自動割り当て\n- 承認フロー管理\n- レポート生成",
      "category": {
        "id": "cat_hr_123...",
        "name": "HR",
        "description": "人事関連エージェント",
        "icon_url": "https://..."
      },
      "publisher": {
        "id": "user_456...",
        "username": "hr_team",
        "avatar_url": "https://..."
      },
      "version": "1.2.0",
      "icon_url": "https://...",
      "banner_url": "https://...",
      "rating": 4.5,
      "review_count": 42,
      "installation_count": 234,
      "status": "published",
      "visibility": "public",
      "tags": ["automation", "hr", "productivity"],
      "capabilities": [
        {
          "name": "task_scheduling",
          "description": "タスクを自動スケジュール"
        },
        {
          "name": "approval_workflow",
          "description": "承認フロー管理"
        },
        {
          "name": "reporting",
          "description": "自動レポート生成"
        }
      ],
      "features": [
        {
          "id": "feat_001",
          "name": "自動タスク割り当て",
          "description": "AI による最適な割り当て",
          "icon_url": "https://..."
        },
        {
          "id": "feat_002",
          "name": "リアルタイム通知",
          "description": "進捗状況の即時通知",
          "icon_url": "https://..."
        }
      ],
      "requirements": {
        "min_python_version": "3.9",
        "dependencies": ["anthropic>=0.7", "flask>=2.0"],
        "storage_required_mb": 256
      },
      "settings_schema": {
        "type": "object",
        "properties": {
          "notification_channel": {
            "type": "string",
            "description": "通知先チャンネル",
            "enum": ["email", "slack", "teams"]
          },
          "auto_approval_threshold": {
            "type": "number",
            "description": "自動承認の閾値",
            "minimum": 0,
            "maximum": 1
          }
        },
        "required": ["notification_channel"]
      },
      "documentation_url": "https://docs.example.com/agents/hr-automation",
      "github_url": "https://github.com/example/hr-agent",
      "support_url": "https://support.example.com/contact",
      "releases": [
        {
          "version": "1.2.0",
          "release_notes": "Bug fixes and performance improvements",
          "published_at": "2026-04-20T10:00:00Z",
          "status": "active"
        },
        {
          "version": "1.1.0",
          "release_notes": "Initial release",
          "published_at": "2026-03-15T10:00:00Z",
          "status": "active"
        }
      ],
      "recent_reviews": [
        {
          "id": "review_001",
          "user": { "username": "user_abc" },
          "rating": 5,
          "title": "素晴らしいエージェント",
          "comment": "タスク割り当てが本当に効率的です",
          "created_at": "2026-04-20T10:30:00Z",
          "helpful_count": 12
        },
        {
          "id": "review_002",
          "user": { "username": "user_def" },
          "rating": 4,
          "title": "ほぼ完璧",
          "comment": "Slack 連携があるともっと良い",
          "created_at": "2026-04-15T14:20:00Z",
          "helpful_count": 5
        }
      ],
      "current_user_installation": {
        "id": "inst_xyz789...",
        "status": "active",
        "installed_at": "2026-04-10T09:00:00Z",
        "last_used_at": "2026-04-25T16:30:00Z",
        "execution_count": 156,
        "success_count": 152,
        "error_count": 4,
        "avg_execution_time_ms": 342
      }
    }
  },
  "meta": {
    "request_id": "req_xyz789...",
    "timestamp": "2026-04-26T15:49:57Z"
  }
}
```

**エラー時** (404 Not Found):

```json
{
  "success": false,
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "指定されたエージェントが見つかりません"
  },
  "meta": {
    "request_id": "req_xyz789...",
    "timestamp": "2026-04-26T15:49:57Z"
  }
}
```

#### 実装ノート

- **権限チェック**: visibility が private の場合は所有者のみアクセス可能
- **キャッシング**: 詳細情報は 10 分間キャッシュ
- **パフォーマンス**: reviews は最新 3 件のみ返す（pagination サポート可能）

---

### 2.3 エージェント インストール API

**エンドポイント**: `POST /api/marketplace/agents/{id}/install`

**目的**: エージェントをインストール。インストール履歴を記録。

#### リクエスト

```http
POST /api/marketplace/agents/agent_123e456.../install
Authorization: Bearer {token}
Content-Type: application/json

{
  "organization_id": "org_abc123",
  "release_version": "1.2.0",
  "configuration": {
    "notification_channel": "slack",
    "auto_approval_threshold": 0.8
  }
}
```

**リクエストボディ**:

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| organization_id | string | ❌ | インストール先の組織ID（未指定の場合はユーザー個人） |
| release_version | string | ❌ | インストール対象バージョン（デフォルト: 最新） |
| configuration | object | ❌ | エージェント固有の設定（スキーマは agents.settings_schema に従う） |

#### レスポンス

**成功時** (201 Created):

```json
{
  "success": true,
  "data": {
    "installation": {
      "id": "inst_xyz789...",
      "agent_id": "agent_123e456...",
      "user_id": "user_456...",
      "organization_id": "org_abc123",
      "release_version": "1.2.0",
      "status": "active",
      "installed_at": "2026-04-26T15:49:57Z",
      "configuration": {
        "notification_channel": "slack",
        "auto_approval_threshold": 0.8
      },
      "next_steps": [
        "ダッシュボードでエージェントの実行を開始",
        "設定ページでカスタマイズ",
        "ドキュメントで詳細を確認"
      ]
    }
  },
  "meta": {
    "request_id": "req_xyz789...",
    "timestamp": "2026-04-26T15:49:57Z"
  }
}
```

**エラー時** (400 Bad Request - 既にインストール済み):

```json
{
  "success": false,
  "error": {
    "code": "ALREADY_INSTALLED",
    "message": "このエージェントは既にインストール済みです",
    "details": {
      "existing_installation_id": "inst_xyz789...",
      "installed_at": "2026-04-10T09:00:00Z"
    }
  },
  "meta": {
    "request_id": "req_xyz789...",
    "timestamp": "2026-04-26T15:49:57Z"
  }
}
```

**エラー時** (422 Unprocessable Entity - 設定スキーマ検証失敗):

```json
{
  "success": false,
  "error": {
    "code": "INVALID_CONFIGURATION",
    "message": "提供された設定がスキーマ検証に失敗しました",
    "details": {
      "validation_errors": [
        {
          "path": "notification_channel",
          "message": "必須フィールドです"
        }
      ]
    }
  },
  "meta": {
    "request_id": "req_xyz789...",
    "timestamp": "2026-04-26T15:49:57Z"
  }
}
```

#### 実装ノート

- **べき等性**: 同じ設定でのインストール再実行は ALREADY_INSTALLED エラーを返す
- **スキーマ検証**: configuration は agents.settings_schema に基づいて検証
- **統計更新**: installation_count を +1 し、キャッシュを無効化
- **通知**: インストール完了後、ユーザーに通知を送信（推奨）

---

## 3. エラーハンドリング

### 3.1 標準エラーコード

| コード | HTTPステータス | 説明 |
|---|---|---|
| INVALID_REQUEST | 400 | リクエスト形式が不正 |
| UNAUTHORIZED | 401 | 認証トークンが無効または期限切れ |
| FORBIDDEN | 403 | リソースへのアクセス権限がない |
| AGENT_NOT_FOUND | 404 | エージェントが見つからない |
| ALREADY_INSTALLED | 400 | エージェント既にインストール済み |
| INVALID_CONFIGURATION | 422 | 設定スキーマ検証失敗 |
| INVALID_CATEGORY | 400 | カテゴリが見つからない |
| RATE_LIMIT_EXCEEDED | 429 | レート制限超過 |
| INTERNAL_ERROR | 500 | サーバー内部エラー |

---

## 4. レート制限

- **リクエスト制限**: 1 ユーザーあたり 100 requests/minute
- **検索ボックス最適化**: クライアント側で debounce（300ms）を実装推奨
- **ヘッダー情報**:
  ```
  X-RateLimit-Limit: 100
  X-RateLimit-Remaining: 87
  X-RateLimit-Reset: 1682002197
  ```

---

## 5. キャッシング戦略

| リソース | TTL | キャッシュ戦略 |
|---|---|---|
| GET /agents（一覧） | 5 分 | 検索パラメータキーでキャッシュ |
| GET /agents/{id}（詳細） | 10 分 | エージェント ID でキャッシュ |
| categories（カテゴリ） | 1 時間 | 静的キャッシュ |

**無効化タイミング**:
- エージェント情報更新時
- インストール時（installation_count +1）
- レビュー追加時

---

## 6. 実装参考

### 既存実装パターン

**参照ファイル**: `dashboard/scores_routes.py`

```python
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/api/marketplace')

@marketplace_bp.route('/agents', methods=['GET'])
def list_agents():
    """エージェント一覧・検索"""
    # scores_routes.py のパターンを参照
    pass

@marketplace_bp.route('/agents/<agent_id>', methods=['GET'])
def get_agent_detail(agent_id):
    """エージェント詳細"""
    pass

@marketplace_bp.route('/agents/<agent_id>/install', methods=['POST'])
def install_agent(agent_id):
    """エージェント インストール"""
    pass
```

---

## 7. 次フェーズ

**フロントエンド設計**: `marketplace_frontend_design.md`
- マーケットプレイス一覧ページ
- エージェント詳細ページ
- インストール確認ダイアログ
