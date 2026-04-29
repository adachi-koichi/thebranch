# サブスクリプション・課金管理システム設計書

**Task #2548** | **MVP Phase 1: Free/Pro プラン管理** | **納期: 2026-05-02 18:00 JST**

---

## 1. 概要

本ドキュメントは、THEBRANCH プラットフォームのサブスクリプション・課金管理システムの技術設計を定義します。

MVP Phase 1 では以下を実装：
- ✅ Free/Pro プラン表示＆比較 UI（HTML/CSS + Chart.js）
- ✅ プラン切り替え API（PATCH /api/subscriptions/plan）
- ✅ DB スキーマ（subscriptions テーブル）
- ✅ API・UI テスト（ユニット＋結合）

Phase 2 以降（スコープ外）：
- Stripe webhook 連携
- 従量課金（プロビジョニング上限等）
- 監査ログ

---

## 2. データベース設計

### 2.1 subscriptions テーブル

```sql
CREATE TABLE subscriptions (
    id TEXT PRIMARY KEY,                    -- UUID (sub-xxxxx)
    user_id TEXT NOT NULL UNIQUE,           -- FK: users.id（1ユーザー1サブスク）
    plan TEXT NOT NULL,                     -- 'free' | 'pro'
    status TEXT NOT NULL,                   -- 'active' | 'canceled' | 'expired'
    
    -- 課金期間（月次サイクル）
    current_period_start DATETIME NOT NULL, -- 現在の課金期間開始
    current_period_end DATETIME NOT NULL,   -- 現在の課金期間終了
    
    -- キャンセル・有効期限
    canceled_at DATETIME,                   -- キャンセル日時（NULL=アクティブ）
    
    -- タイムスタンプ
    created_at DATETIME NOT NULL,           -- 初回登録日時
    updated_at DATETIME NOT NULL,           -- 最終更新日時
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_plan ON subscriptions(plan);
CREATE INDEX idx_subscriptions_current_period_end ON subscriptions(current_period_end);
```

### 2.2 subscription_plans テーブル（マスタデータ）

```sql
CREATE TABLE subscription_plans (
    id TEXT PRIMARY KEY,                    -- 'free' | 'pro'
    name TEXT NOT NULL,                     -- 'Free' | 'Pro'
    description TEXT,                       -- プラン説明
    price_jpy INTEGER NOT NULL,             -- 月額料金（円）
    
    -- Feature flags
    features JSONB NOT NULL,                -- { "max_agents": 5, "api_calls_per_month": 10000 }
    
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- マスタデータ挿入例
INSERT INTO subscription_plans VALUES
('free', 'Free', 'Free plan for testing', 0, '{"max_agents": 3, "api_calls_per_month": 1000}', datetime('now'), datetime('now')),
('pro', 'Pro', 'Professional plan', 9900, '{"max_agents": 50, "api_calls_per_month": 1000000}', datetime('now'), datetime('now'));
```

### 2.3 migration ファイル

**ファイル**: `dashboard/migrations/026_create_subscriptions_tables.sql`

```sql
-- Migration 026: サブスクリプション・課金管理テーブル作成

CREATE TABLE subscription_plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price_jpy INTEGER NOT NULL DEFAULT 0,
    features TEXT NOT NULL DEFAULT '{}',  -- JSON
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    plan TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    
    current_period_start DATETIME NOT NULL,
    current_period_end DATETIME NOT NULL,
    canceled_at DATETIME,
    
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plan) REFERENCES subscription_plans(id)
);

CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_plan ON subscriptions(plan);
CREATE INDEX idx_subscriptions_current_period_end ON subscriptions(current_period_end);

-- マスタデータ挿入
INSERT INTO subscription_plans (id, name, description, price_jpy, features)
VALUES
    ('free', 'Free', 'Free plan for testing', 0, '{"max_agents": 3, "api_calls_per_month": 1000, "storage_gb": 1, "email_support": false}'),
    ('pro', 'Pro', 'Professional plan', 9900, '{"max_agents": 50, "api_calls_per_month": 1000000, "storage_gb": 100, "email_support": true, "priority_support": false}'),
    ('enterprise', 'Enterprise', 'Enterprise plan', 0, '{"max_agents": 9999, "api_calls_per_month": 9999999, "storage_gb": 10000, "email_support": true, "priority_support": true}');
```

---

## 3. API 仕様

### 3.1 プランマスタ取得

**エンドポイント**: `GET /api/subscriptions/plans`

**説明**: 利用可能なすべてのプラン情報を取得。UI での「プラン比較」表示に使用。

**認証**: なし（公開情報）

**リクエスト**: なし

**レスポンス 200**:
```json
{
  "plans": [
    {
      "id": "free",
      "name": "Free",
      "description": "Free plan for testing",
      "price_jpy": 0,
      "features": {
        "max_agents": 3,
        "api_calls_per_month": 1000,
        "storage_gb": 1,
        "email_support": false
      }
    },
    {
      "id": "pro",
      "name": "Pro",
      "description": "Professional plan",
      "price_jpy": 9900,
      "features": {
        "max_agents": 50,
        "api_calls_per_month": 1000000,
        "storage_gb": 100,
        "email_support": true,
        "priority_support": false
      }
    }
  ]
}
```

---

### 3.2 現在のサブスクリプション取得

**エンドポイント**: `GET /api/subscriptions/current`

**説明**: 認証ユーザーの現在のサブスクリプション情報を取得。

**認証**: Bearer token（セッション）必須

**リクエスト**: なし

**レスポンス 200**:
```json
{
  "id": "sub-550e8400e29b41d4a716446655440000",
  "user_id": "user-550e8400e29b41d4a716446655440001",
  "plan": "free",
  "status": "active",
  "current_period_start": "2026-04-01T00:00:00Z",
  "current_period_end": "2026-05-01T00:00:00Z",
  "canceled_at": null,
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-01T00:00:00Z"
}
```

**エラー 401**: 認証失敗
```json
{
  "detail": "Not authenticated"
}
```

**エラー 404**: サブスクリプション未登録（初回ユーザー）
```json
{
  "detail": "Subscription not found for user"
}
```

---

### 3.3 プラン切り替え

**エンドポイント**: `PATCH /api/subscriptions/plan`

**説明**: ユーザーのプランを変更（Free → Pro / Pro → Free）。即座に反映（Phase 2 で支払い処理を追加）

**認証**: Bearer token（セッション）必須

**リクエスト**:
```json
{
  "plan": "pro"
}
```

**レスポンス 200** (成功):
```json
{
  "id": "sub-550e8400e29b41d4a716446655440000",
  "user_id": "user-550e8400e29b41d4a716446655440001",
  "plan": "pro",
  "status": "active",
  "current_period_start": "2026-04-30T07:14:56Z",
  "current_period_end": "2026-05-30T07:14:56Z",
  "canceled_at": null,
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-30T07:14:56Z"
}
```

**エラー 400** (無効なプラン):
```json
{
  "detail": "Invalid plan: 'vip'. Valid plans: free, pro, enterprise"
}
```

**エラー 400** (プラン変更なし):
```json
{
  "detail": "User is already on pro plan"
}
```

**エラー 401**: 認証失敗
```json
{
  "detail": "Not authenticated"
}
```

---

## 4. Pydantic モデル定義

### 4.1 models.py に追加

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Subscription Management Models (#2548)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SubscriptionPlanFeatures(BaseModel):
    """プランの機能フラグ"""
    max_agents: int
    api_calls_per_month: int
    storage_gb: int
    email_support: bool
    priority_support: bool = False


class SubscriptionPlan(BaseModel):
    """プランマスタ情報"""
    id: str              # 'free', 'pro', 'enterprise'
    name: str            # 'Free', 'Pro', 'Enterprise'
    description: Optional[str] = None
    price_jpy: int       # 月額料金（円）
    features: SubscriptionPlanFeatures


class SubscriptionResponse(BaseModel):
    """サブスクリプション情報"""
    id: str
    user_id: str
    plan: str            # 'free', 'pro', 'enterprise'
    status: str          # 'active', 'canceled', 'expired'
    current_period_start: datetime
    current_period_end: datetime
    canceled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionPlanChangeRequest(BaseModel):
    """プラン変更リクエスト"""
    plan: str  # 'pro', 'free', 'enterprise'


class SubscriptionPlanListResponse(BaseModel):
    """プランリスト レスポンス"""
    plans: List[SubscriptionPlan]
```

---

## 5. 実装ガイドライン

### 5.1 ファイル構成（Engineers 向け）

```
dashboard/
├── models.py               ← Pydantic モデル追加（上記 4.1 参照）
├── routes/
│   └── subscriptions.py    ← 新規作成（API ルーター）
├── repositories/
│   └── subscription.py     ← 新規作成（DB アクセス層）
├── services/
│   └── subscription.py     ← 新規作成（ビジネスロジック層）
├── migrations/
│   └── 026_create_subscriptions_tables.sql  ← 新規作成
└── templates/
    └── pages/
        └── subscriptions.html  ← 新規作成（UI）
```

### 5.2 ビジネスロジック

**プラン切り替え時の処理**:

1. **入力検証** → 無効なプラン（存在しないプラン）は 400 エラー
2. **重複チェック** → 同じプラン への変更は 400 エラー
3. **期間計算** → 新しい `current_period_end` を計算（30 日後）
4. **DB 更新** → subscriptions テーブルを更新
5. **レスポンス** → 更新後のサブスクリプション情報を返却

**初回ユーザー対応**:

- ユーザー登録時に自動的に `Free プラン` で subscriptions レコード作成
- `current_period_start` = 登録日時
- `current_period_end` = 登録日時 + 30 日

### 5.3 エラーハンドリング

| エラー | ステータス | 原因 |
|------|----------|------|
| Invalid plan | 400 | 存在しないプラン ID |
| User is already on this plan | 400 | 同じプランへの変更 |
| Subscription not found | 404 | サブスクリプション未登録 |
| Not authenticated | 401 | 認証トークン無し/無効 |
| Database error | 500 | DB エラー（予期しないエラー） |

---

## 6. テスト戦略

### 6.1 ユニットテスト（pytest）

**テストファイル**: `tests/test_subscriptions_api.py`

```python
# テスト項目例：

# 1. GET /api/subscriptions/plans
def test_get_subscription_plans()
    # → 3つのプラン情報を取得確認

# 2. GET /api/subscriptions/current
def test_get_current_subscription()
    # → ユーザーの現在のサブスク情報を取得

def test_get_current_subscription_not_found()
    # → サブスク未登録時は 404

def test_get_current_subscription_unauthorized()
    # → 認証なしは 401

# 3. PATCH /api/subscriptions/plan
def test_change_plan_free_to_pro()
    # → Free → Pro 変更が成功

def test_change_plan_pro_to_free()
    # → Pro → Free 変更が成功

def test_change_plan_same_plan()
    # → 同じプランへの変更は 400

def test_change_plan_invalid_plan()
    # → 存在しないプランは 400

def test_change_plan_unauthorized()
    # → 認証なしは 401

# 4. Period 計算の正確性
def test_subscription_period_calculation()
    # → current_period_end が現在 + 30 日 か確認
```

### 6.2 統合テスト（BDD）

**テストファイル**: `features/subscription.feature`

```gherkin
Feature: Subscription Management
  Scenario: User views available plans
    When user accesses GET /api/subscriptions/plans
    Then response status is 200
    And response contains 3 plans (free, pro, enterprise)

  Scenario: User views their current subscription
    Given user is authenticated
    When user accesses GET /api/subscriptions/current
    Then response status is 200
    And response contains user's current plan

  Scenario: User upgrades from Free to Pro
    Given user is authenticated with "free" plan
    When user sends PATCH /api/subscriptions/plan with {"plan": "pro"}
    Then response status is 200
    And response contains "pro" plan
    And current_period_end is 30 days from now

  Scenario: User cannot change to same plan
    Given user is authenticated with "pro" plan
    When user sends PATCH /api/subscriptions/plan with {"plan": "pro"}
    Then response status is 400
    And error message contains "already on pro plan"
```

### 6.3 E2E テスト（ブラウザテスト）

UI テストは Phase 1 では簡易版（手動確認）：
- プラン比較画面の表示（HTML/CSS）
- プラン切り替えボタンのクリック
- 切り替え後の UI 更新

Phase 2 で Selenium/Cypress を導入予定。

---

## 7. UI・UX 仕様

### 7.1 プラン比較ページ（スケッチ）

```
┌─────────────────────────────────────────────┐
│  THEBRANCH | Subscription Plans             │
├─────────────────────────────────────────────┤
│                                             │
│  Free         │  Pro         │  Enterprise │
│  ¥0/月        │  ¥9,900/月   │  カスタム   │
│               │              │             │
│  • 3 agents   │  • 50 agents │  • ∞ agents │
│  • 1GB        │  • 100GB     │  • 1TB      │
│  • 1K API     │  • 1M API    │  • ∞ API    │
│  • Email      │  • Email +   │  • Priority │
│    support    │    Priority  │    support  │
│               │              │             │
│  [Current]    │  [Upgrade]   │  [Contact]  │
│               │              │             │
└─────────────────────────────────────────────┘
```

### 7.2 UI 実装技術

- **フレームワーク**: HTML/CSS/JavaScript
- **グラフ**: Chart.js（プラン比較の可視化）
- **スタイル**: Tailwind CSS（既存に合わせる）

---

## 8. 実装チェックリスト（Engineers 向け）

- [ ] Migration ファイル作成・実行
- [ ] Pydantic モデル定義（models.py）
- [ ] Repository レイヤー実装（subscription.py）
- [ ] Service レイヤー実装（subscription.py）
- [ ] API ルーター実装（routes/subscriptions.py）
- [ ] app.py に router 登録（`app.include_router(...)`）
- [ ] ユニットテスト実装＆全テスト通過
- [ ] BDD テスト実装＆実行（features/subscription.feature）
- [ ] UI 実装（templates/pages/subscriptions.html）
- [ ] E2E 動作確認（ブラウザで確認）
- [ ] セキュリティレビュー（認証・入力検証）
- [ ] コードレビュー＆マージ

---

## 9. 納期・マイルストーン

| 日時 | マイルストーン | 担当 |
|------|-------------|------|
| 2026-04-30 | 設計ドキュメント完成 | Tech Lead ✓ |
| 2026-05-01 | DB スキーマ・API 実装 | Engineer |
| 2026-05-01 | テスト実装＆テスト実行 | QA Engineer |
| 2026-05-02 18:00 | MVP 完成・本番デプロイ | Release |

---

## 10. 参考・関連資料

- [THEBRANCH CLAUDE.md](../CLAUDE.md)
- [Task #2548 - Subscription System MVP Phase 1](#)
- 既存 API 実装: `dashboard/routes/manage_routes.py`
- 既存 DB パターン: `dashboard/migrations/024_create_accounting_tables.sql`

---

**設計完了日**: 2026-04-30 07:30 JST  
**Tech Lead**: adachi-koichi  
**Status**: ✅ Ready for Engineer Handoff

