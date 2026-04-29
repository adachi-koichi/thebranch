# SLA Management API Specification

## 概要

AIエージェントのService Level Agreement (SLA) を管理し、サービス品質を自動監視・保証する API。

---

## エンドポイント一覧

### 1. GET /api/sla/policies
全SLAポリシー一覧を取得

**説明**: システムに登録されているすべてのSLAポリシーを取得する

**リクエスト**:
```http
GET /api/sla/policies HTTP/1.1
Host: localhost:5000
```

**レスポンス** (200 OK):
```json
[
  {
    "id": 1,
    "name": "Standard",
    "response_time_limit_ms": 500,
    "uptime_percentage": 99.5,
    "error_rate_limit": 0.1,
    "enabled": true,
    "created_at": "2026-04-20T10:30:00Z",
    "updated_at": "2026-04-20T10:30:00Z"
  },
  {
    "id": 2,
    "name": "Premium",
    "response_time_limit_ms": 200,
    "uptime_percentage": 99.9,
    "error_rate_limit": 0.05,
    "enabled": true,
    "created_at": "2026-04-20T10:35:00Z",
    "updated_at": "2026-04-20T10:35:00Z"
  }
]
```

**エラーレスポンス**:
```json
{
  "error": "Internal Server Error",
  "status": 500
}
```

---

### 2. POST /api/sla/policies
新規SLAポリシーを作成

**説明**: 新しいSLAポリシーを定義する

**リクエスト**:
```http
POST /api/sla/policies HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "name": "Standard",
  "response_time_limit_ms": 500,
  "uptime_percentage": 99.5,
  "error_rate_limit": 0.1
}
```

**レスポンス** (201 Created):
```json
{
  "id": 1,
  "name": "Standard",
  "response_time_limit_ms": 500,
  "uptime_percentage": 99.5,
  "error_rate_limit": 0.1,
  "enabled": true,
  "created_at": "2026-04-23T17:40:00Z",
  "updated_at": "2026-04-23T17:40:00Z"
}
```

**エラーレスポンス** (400 Bad Request):
```json
{
  "error": "Policy name must be unique",
  "status": 400
}
```

---

### 3. PUT /api/sla/policies/{id}
既存SLAポリシーを更新

**説明**: ポリシーの パラメータを変更する

**リクエスト**:
```http
PUT /api/sla/policies/1 HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "response_time_limit_ms": 450,
  "uptime_percentage": 99.7,
  "error_rate_limit": 0.08
}
```

**レスポンス** (200 OK):
```json
{
  "id": 1,
  "name": "Standard",
  "response_time_limit_ms": 450,
  "uptime_percentage": 99.7,
  "error_rate_limit": 0.08,
  "enabled": true,
  "created_at": "2026-04-20T10:30:00Z",
  "updated_at": "2026-04-23T17:45:00Z"
}
```

**エラーレスポンス** (404 Not Found):
```json
{
  "error": "Policy not found",
  "status": 404
}
```

---

### 4. DELETE /api/sla/policies/{id}
SLAポリシーを削除

**説明**: ポリシーを削除する（関連するメトリクス・違反もカスケード削除）

**リクエスト**:
```http
DELETE /api/sla/policies/1 HTTP/1.1
Host: localhost:5000
```

**レスポンス** (200 OK):
```json
{
  "success": true,
  "message": "Policy deleted successfully"
}
```

**エラーレスポンス** (404 Not Found):
```json
{
  "error": "Policy not found",
  "status": 404
}
```

---

### 5. GET /api/sla/metrics/{policy_id}
特定ポリシーの最新メトリクスを取得

**説明**: 指定されたポリシーIDのメトリクス履歴を取得（直近100件）

**リクエスト**:
```http
GET /api/sla/metrics/1?limit=10 HTTP/1.1
Host: localhost:5000
```

**レスポンス** (200 OK):
```json
[
  {
    "id": 101,
    "policy_id": 1,
    "response_time_ms": 450,
    "uptime_percentage": 99.5,
    "error_rate": 0.08,
    "measured_at": "2026-04-23T17:40:00Z"
  },
  {
    "id": 100,
    "policy_id": 1,
    "response_time_ms": 480,
    "uptime_percentage": 99.4,
    "error_rate": 0.09,
    "measured_at": "2026-04-23T17:35:00Z"
  }
]
```

**エラーレスポンス** (404 Not Found):
```json
{
  "error": "Policy not found",
  "status": 404
}
```

---

## HTTPステータスコード

| コード | 意味 |
|------|------|
| 200 | OK - リクエスト成功 |
| 201 | Created - リソース作成成功 |
| 400 | Bad Request - リクエストが不正 |
| 404 | Not Found - リソースが見つからない |
| 500 | Internal Server Error - サーバーエラー |

---

## レスポンスヘッダー

すべてのレスポンスに以下のヘッダーを含める：

```
Content-Type: application/json
X-Request-ID: <UUID>
X-Response-Time: <milliseconds>
```

---

## リクエスト/レスポンス制約

### リクエストボディ制約

| フィールド | 型 | 制約 |
|-----------|----|----|
| name | string | 1〜255文字、一意 |
| response_time_limit_ms | integer | 1〜10000 |
| uptime_percentage | number | 0〜100 |
| error_rate_limit | number | 0〜1 |

### レスポンス制約

- すべてのタイムスタンプは ISO 8601 形式 (UTC)
- 数値は最大2小数点まで
