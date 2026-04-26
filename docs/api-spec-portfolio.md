# ポートフォリオ管理 API 仕様

- バージョン: v1.0
- 作成日: 2026-04-26
- ベースURL: `/api/v1/portfolios`

---

## 概要

ポートフォリオ管理APIは、ユーザーが保有する部門・エージェント・ミッションの集合体（ポートフォリオ）を作成・管理するためのエンドポイント群です。

---

## DBスキーマ

| テーブル | 概要 |
|---|---|
| `portfolios` | ポートフォリオ本体（名称・ステータス・公開設定） |
| `portfolio_departments` | ポートフォリオと部門の紐付け |
| `portfolio_metrics` | KPI・パフォーマンスメトリクス |
| `portfolio_snapshots` | 定期スナップショット保存 |
| `portfolio_tags` | タグ・カテゴリ付け |

マイグレーションファイル: `dashboard/migrations/030_create_portfolio_tables.sql`

---

## エンドポイント一覧

### ポートフォリオ CRUD

#### `POST /api/v1/portfolios`
ポートフォリオを新規作成する。

**リクエスト:**
```json
{
  "name": "事業展開ポートフォリオ 2026",
  "description": "3部門を統合した戦略推進ポートフォリオ",
  "visibility": "org",
  "tags": ["strategic", "2026"]
}
```

**レスポンス `201`:**
```json
{
  "id": "uuid",
  "name": "事業展開ポートフォリオ 2026",
  "org_id": "uuid",
  "owner_user_id": "uuid",
  "status": "active",
  "visibility": "org",
  "tags": ["strategic", "2026"],
  "created_at": "2026-04-26T00:00:00"
}
```

---

#### `GET /api/v1/portfolios`
ポートフォリオ一覧を取得する（自組織スコープ）。

**クエリパラメータ:**
| パラメータ | 型 | 説明 |
|---|---|---|
| `status` | string | `active` / `archived` / `draft` |
| `visibility` | string | `private` / `org` / `public` |
| `tag` | string | タグでフィルタ |
| `page` | int | ページ番号（デフォルト: 1） |
| `per_page` | int | 件数（デフォルト: 20、最大: 100） |

**レスポンス `200`:**
```json
{
  "portfolios": [
    {
      "id": "uuid",
      "name": "事業展開ポートフォリオ 2026",
      "status": "active",
      "department_count": 3,
      "tags": ["strategic"],
      "updated_at": "2026-04-26T00:00:00"
    }
  ],
  "total": 5,
  "page": 1,
  "per_page": 20
}
```

---

#### `GET /api/v1/portfolios/{portfolio_id}`
ポートフォリオの詳細を取得する。

**レスポンス `200`:**
```json
{
  "id": "uuid",
  "name": "事業展開ポートフォリオ 2026",
  "description": "...",
  "org_id": "uuid",
  "owner_user_id": "uuid",
  "status": "active",
  "visibility": "org",
  "departments": [
    {
      "department_id": "uuid",
      "name": "営業推進部",
      "role": "lead"
    }
  ],
  "tags": ["strategic", "2026"],
  "latest_metrics": {
    "total_tasks": 42,
    "completion_rate": 0.85,
    "total_cost": 150000
  },
  "created_at": "2026-04-26T00:00:00",
  "updated_at": "2026-04-26T00:00:00"
}
```

---

#### `PATCH /api/v1/portfolios/{portfolio_id}`
ポートフォリオを更新する（部分更新対応）。

**リクエスト:**
```json
{
  "name": "更新後の名称",
  "status": "archived",
  "visibility": "public"
}
```

**レスポンス `200`:** 更新後の全フィールド

---

#### `DELETE /api/v1/portfolios/{portfolio_id}`
ポートフォリオを削除する（論理削除: status を `archived` に変更）。

**レスポンス `204`:** No Content

---

### 部門の追加・削除

#### `POST /api/v1/portfolios/{portfolio_id}/departments`
部門をポートフォリオに追加する。

**リクエスト:**
```json
{
  "department_id": "uuid",
  "role": "lead"
}
```

**レスポンス `201`:**
```json
{
  "portfolio_id": "uuid",
  "department_id": "uuid",
  "role": "lead",
  "added_at": "2026-04-26T00:00:00"
}
```

**エラー `409`:** 同一部門が既にポートフォリオに追加済み

---

#### `PATCH /api/v1/portfolios/{portfolio_id}/departments/{department_id}`
部門のロールを変更する。

**リクエスト:** `{"role": "observer"}`

**レスポンス `200`:** 更新後のオブジェクト

---

#### `DELETE /api/v1/portfolios/{portfolio_id}/departments/{department_id}`
部門をポートフォリオから外す。

**レスポンス `204`:** No Content

---

### メトリクス

#### `GET /api/v1/portfolios/{portfolio_id}/metrics`
ポートフォリオのメトリクス一覧を取得する。

**クエリパラメータ:**
| パラメータ | 型 | 説明 |
|---|---|---|
| `period` | string | 集計期間（例: `2026-04`） |
| `metric_key` | string | メトリクスキーでフィルタ |

**レスポンス `200`:**
```json
{
  "metrics": [
    {
      "metric_key": "completion_rate",
      "metric_value": 0.85,
      "metric_unit": "ratio",
      "period": "2026-04",
      "recorded_at": "2026-04-26T00:00:00"
    }
  ]
}
```

---

#### `POST /api/v1/portfolios/{portfolio_id}/metrics`
メトリクスを記録する。

**リクエスト:**
```json
{
  "metric_key": "total_cost",
  "metric_value": 150000,
  "metric_unit": "JPY",
  "period": "2026-04"
}
```

**レスポンス `201`:** 作成されたメトリクスオブジェクト

主要メトリクスキー:
- `total_tasks`: 総タスク数
- `completion_rate`: 完了率（0.0〜1.0）
- `total_cost`: 総コスト（JPY）
- `agent_count`: 稼働エージェント数
- `sla_violation_count`: SLA違反件数

---

### スナップショット

#### `POST /api/v1/portfolios/{portfolio_id}/snapshots`
ポートフォリオのスナップショットを保存する。

**リクエスト:**
```json
{
  "snapshot_type": "milestone",
  "label": "Q1完了時点"
}
```

`snapshot_type` の選択肢: `manual` / `scheduled` / `milestone`

**レスポンス `201`:**
```json
{
  "id": 1,
  "portfolio_id": "uuid",
  "snapshot_type": "milestone",
  "label": "Q1完了時点",
  "created_at": "2026-04-26T00:00:00"
}
```

---

#### `GET /api/v1/portfolios/{portfolio_id}/snapshots`
スナップショット一覧を取得する（最新順）。

**レスポンス `200`:** スナップショットの配列

---

### タグ

#### `POST /api/v1/portfolios/{portfolio_id}/tags`
タグを追加する。

**リクエスト:** `{"tag": "strategic"}`

**レスポンス `201`:** `{"portfolio_id": "uuid", "tag": "strategic"}`

---

#### `DELETE /api/v1/portfolios/{portfolio_id}/tags/{tag}`
タグを削除する。

**レスポンス `204`:** No Content

---

## 認証・認可

- 全エンドポイントに Bearer トークン認証が必要
- `portfolios:read` スコープ: GET 系
- `portfolios:write` スコープ: POST / PATCH / DELETE 系
- `org_id` によるスコープ制限（他組織リソースへのアクセスは403）

---

## エラーレスポンス

| コード | 説明 |
|---|---|
| `400` | リクエストパラメータ不正 |
| `401` | 未認証 |
| `403` | 権限不足（他組織のリソースへのアクセス等） |
| `404` | ポートフォリオが存在しない |
| `409` | 重複（同一部門を二重登録等） |
| `500` | サーバーエラー |
