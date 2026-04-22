# マーケットプレイス API 仕様書 v1.0

**対応タスク**: #2440-TL (テクニカルレビュー・API 仕様確認)  
**作成日**: 2026-04-22  
**ステータス**: 実装前設計段階  
**Tech Lead**: (アサイン待ち)

---

## 目次

1. [概要](#1-概要)
2. [API エンドポイント仕様](#2-apiエンドポイント仕様)
3. [Template Suggestion ロジック](#3-template-suggestion-ロジック)
4. [DB スキーマ拡張](#4-dbスキーマ拡張)
5. [エラーハンドリング](#5-エラーハンドリング)
6. [パフォーマンス・セキュリティ](#6-パフォーマンスセキュリティ)

---

## 1. 概要

### 1-1. マーケットプレイスの役割

THEBRANCH マーケットプレイスは、ユーザーのビジョン（組織目的・要件）を入力として、最適なテンプレートを提案し、カスタマイズできるシステムです。

**機能フロー**:
```
[ユーザー入力: vision_text]
         ↓
[Template Suggestion Engine]
  ├─ 自然言語処理（vision の解析）
  ├─ スコア計算（category, skills, processes マッチ度）
  └─ recommendation_level 判定
         ↓
[テンプレート一覧 + スコア + 理由]
         ↓
[ユーザーが選択 + カスタマイズ]
         ↓
[department_instance 作成]
```

### 1-2. API 層の責務

| エンドポイント | 入力 | 出力 | DB操作 |
|---|---|---|---|
| **POST /suggest-templates** | vision_text | templates[], scores[], reasons[] | SELECT (読み取り) + INSERT (suggestion_log) |
| **POST /customize-template** | template_id, custom_config | department_instance, setup_status | INSERT + UPDATE（複数テーブル） |
| **GET /templates** | category?, status? | templates[], stats[] | SELECT (キャッシュ優先) |

---

## 2. API エンドポイント仕様

### 2-1. Template Suggestion API

#### エンドポイント

```
POST /api/marketplace/suggest-templates
```

#### リクエスト

**Headers**:
```
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>
```

**Body**:
```json
{
  "vision_text": "営業チームを2週間で立ち上げて、初月50万円の売上を目指す。20代の意欲的なメンバーで構成したい。",
  "optional_context": {
    "industry": "SaaS",
    "company_stage": "seed|growth|scale",
    "team_size_estimate": 5,
    "budget_range": {
      "min": 500000,
      "max": 2000000
    },
    "required_capabilities": ["sales", "customer-success"],
    "timeline_days": 14
  }
}
```

**バリデーション**:
- `vision_text`: required, 20-500 chars, non-empty
- `optional_context.team_size_estimate`: range 1-100
- `optional_context.budget_range.min < max`

#### レスポンス

**Status**: 200 OK

```json
{
  "request_id": "req_2026_04_22_001",
  "vision_analysis": {
    "detected_categories": ["sales", "customer-success"],
    "detected_skills": ["relationship-building", "negotiation", "customer-onboarding"],
    "timeline_urgency": "high",
    "budget_constraint": "medium"
  },
  "suggested_templates": [
    {
      "rank": 1,
      "template": {
        "id": 3,
        "name": "Sales Department",
        "category": "sales",
        "description": "営業部による新規顧客獲得・ライフサイクル管理",
        "version": 2,
        "status": "active"
      },
      "match_score": 0.92,
      "recommendation_level": "highly_recommended",
      "score_breakdown": {
        "category_match": 0.95,
        "skills_fit": 0.90,
        "process_alignment": 0.92,
        "team_size_compatibility": 0.88,
        "timeline_feasibility": 0.95
      },
      "match_reasons": [
        "ビジョンに含まれる『営業』『2週間立ち上げ』に100%マッチ",
        "チームサイズ 3-8名の要件に適合（5名推奨）",
        "初月売上目標に最適化されたプロセス設計済み",
        "過去のテンプレート利用者で同一条件の成功率 87%"
      ],
      "quick_stats": {
        "typical_team_size": "5-7名",
        "typical_monthly_cost": 1400000,
        "setup_time_hours": 4,
        "typical_onboarding_days": 7,
        "success_rate_percent": 87
      },
      "roles_overview": [
        { "role_key": "sales-director", "role_label": "営業部長", "min_members": 1 },
        { "role_key": "account-executive", "role_label": "営業（新規営業）", "min_members": 2 },
        { "role_key": "customer-success-manager", "role_label": "CS", "min_members": 1 }
      ],
      "key_processes": [
        { "process_key": "lead-generation", "process_label": "リード発掘", "frequency": "daily" },
        { "process_key": "deal-closure", "process_label": "成約", "frequency": "weekly" },
        { "process_key": "customer-onboarding", "process_label": "顧客導入", "frequency": "weekly" }
      ]
    },
    {
      "rank": 2,
      "template": {
        "id": 4,
        "name": "Sales + Marketing Combined",
        "category": "sales",
        "description": "営業 + マーケティング連携部門",
        "version": 1
      },
      "match_score": 0.78,
      "recommendation_level": "recommended",
      "score_breakdown": { "category_match": 0.85, "skills_fit": 0.72, "..." },
      "match_reasons": [
        "営業 + マーケティング連携で、より体系的なリード生成が可能",
        "スケール段階に適している（将来的には分離可能）"
      ]
    }
  ],
  "alternative_templates": [
    {
      "rank": 3,
      "template_id": 5,
      "name": "Custom Sales",
      "match_score": 0.65,
      "recommendation_level": "alternative",
      "reason": "高度なカスタマイズが必要な場合の選択肢"
    }
  ],
  "suggestion_metadata": {
    "processing_time_ms": 245,
    "model_version": "suggestion-v2.1",
    "confidence_level": "high",
    "suggestion_id": "sug_001_2026_04_22"
  }
}
```

**エラーレスポンス** (400 Bad Request):
```json
{
  "error": {
    "code": "INVALID_VISION_TEXT",
    "message": "vision_text is required and must be 20-500 characters",
    "details": {
      "field": "vision_text",
      "received_length": 15,
      "min_length": 20
    }
  }
}
```

---

### 2-2. Template Customization API

#### エンドポイント

```
POST /api/marketplace/customize-template
```

#### リクエスト

**Body**:
```json
{
  "template_id": 3,
  "suggestion_id": "sug_001_2026_04_22",
  "custom_config": {
    "instance_name": "東京営業部 A チーム",
    "location": "Tokyo",
    "organization_id": "org_2026_001",
    "manager_agent_id": 5,
    "team_composition": {
      "actual_team_size": 5,
      "roles": [
        {
          "base_role_key": "sales-director",
          "custom_label": "営業部長",
          "assigned_count": 1
        },
        {
          "base_role_key": "account-executive",
          "custom_label": "新規営業",
          "assigned_count": 3
        },
        {
          "base_role_key": "customer-success-manager",
          "custom_label": "カスタマーサクセス",
          "assigned_count": 1
        }
      ]
    },
    "process_customizations": [
      {
        "process_key": "lead-generation",
        "enabled": true,
        "custom_frequency": "daily",
        "custom_description": "LinkedIn + cold calling を組み合わせた営業開拓"
      },
      {
        "process_key": "deal-closure",
        "enabled": true,
        "custom_frequency": "weekly"
      },
      {
        "process_key": "customer-onboarding",
        "enabled": true,
        "custom_frequency": "on-demand"
      }
    ],
    "budget_allocation": {
      "total_monthly_budget": 1500000,
      "salary_percent": 0.7,
      "tools_percent": 0.2,
      "training_percent": 0.1
    },
    "kpi_targets": {
      "monthly_revenue": 500000,
      "deal_closure_rate": 0.2,
      "customer_satisfaction": 4.5
    },
    "custom_context": {
      "department_code": "SALES-01",
      "cost_center": "CC-2001",
      "reporting_currency": "JPY",
      "fiscal_year": 2026
    }
  }
}
```

**バリデーション ロジック**:

1. **template_id 存在確認**
   ```sql
   SELECT id FROM departments_templates WHERE id = ? AND status = 'active'
   ```

2. **team_composition 検証**
   ```
   - 各 role の assigned_count が min_members ~ max_members の範囲内か
   - テンプレートで定義されていないロール割り当てはエラー
   ```

3. **process_customizations 検証**
   ```
   - 指定された process_key がテンプレートに存在するか
   - custom_frequency が enum('daily', 'weekly', 'monthly', 'quarterly', 'annual', 'ad-hoc')に属しているか
   ```

4. **budget_allocation 検証**
   ```
   - salary_percent + tools_percent + training_percent ≤ 1.0
   - total_monthly_budget > 0
   - 計算額がロール数の salary 最小値に対応しているか（警告）
   ```

#### レスポンス

**Status**: 201 Created

```json
{
  "customized_instance": {
    "id": 42,
    "template_id": 3,
    "name": "東京営業部 A チーム",
    "status": "planning",
    "location": "Tokyo",
    "manager_agent_id": 5,
    "created_at": "2026-04-22T10:30:45Z",
    "context": {
      "department_code": "SALES-01",
      "cost_center": "CC-2001",
      "budget_allocated": 1500000,
      "fiscal_year": 2026,
      "reporting_currency": "JPY"
    },
    "team_setup": {
      "target_team_size": 5,
      "roles_configured": [
        {
          "role_key": "sales-director",
          "role_label": "営業部長",
          "assigned": 0,
          "required": 1,
          "status": "pending_assignment"
        },
        {
          "role_key": "account-executive",
          "assigned": 0,
          "required": 3,
          "status": "pending_assignment"
        }
      ],
      "members_assigned": 0
    },
    "process_setup": {
      "total_processes": 3,
      "enabled_processes": 3,
      "configured": 3,
      "processes": [
        {
          "process_key": "lead-generation",
          "process_label": "リード発掘",
          "enabled": true,
          "frequency": "daily",
          "tasks": 5,
          "estimated_hours": 40
        }
      ]
    },
    "setup_progress": {
      "overall_percent": 65,
      "steps": [
        { "step": "template_selected", "completed": true },
        { "step": "config_customized", "completed": true },
        { "step": "roles_assigned", "completed": false },
        { "step": "processes_activated", "completed": false },
        { "step": "approved_to_launch", "completed": false }
      ]
    },
    "next_actions": [
      "メンバーを割り当て（5/5 人）",
      "プロセス順序を確認",
      "承認して運用開始"
    ],
    "estimated_launch_date": "2026-04-24T00:00:00Z"
  },
  "suggestion_log_entry": {
    "suggestion_id": "sug_001_2026_04_22",
    "instance_id": 42,
    "action": "customized",
    "customization_timestamp": "2026-04-22T10:30:45Z"
  }
}
```

**エラーレスポンス** (400 Bad Request):
```json
{
  "error": {
    "code": "ROLE_ASSIGNMENT_MISMATCH",
    "message": "Role assignment violates template constraints",
    "details": {
      "role_key": "account-executive",
      "assigned_count": 5,
      "min_required": 2,
      "max_allowed": 3,
      "violation": "max_members exceeded"
    }
  }
}
```

---

### 2-3. Template List API（既存の改善版）

#### エンドポイント

```
GET /api/marketplace/templates
```

**パラメータ**:
```
?category=sales&status=active&sort=-avg_satisfaction&limit=10&offset=0
```

#### レスポンス

```json
{
  "templates": [
    {
      "id": 3,
      "name": "Sales Department",
      "category": "sales",
      "description": "営業部による新規顧客獲得・ライフサイクル管理",
      "status": "active",
      "version": 2,
      "stats": {
        "instance_count": 15,
        "total_roles": 4,
        "total_processes": 5,
        "avg_satisfaction_score": 4.6,
        "success_rate_percent": 87,
        "avg_setup_time_hours": 4.2
      },
      "preview": {
        "roles": ["sales-director", "account-executive", "customer-success-manager"],
        "key_processes": ["lead-generation", "deal-closure", "customer-onboarding"]
      }
    }
  ],
  "pagination": {
    "total": 12,
    "page": 1,
    "limit": 10
  },
  "cached": {
    "from_cache": true,
    "cache_ttl_seconds": 3600,
    "cache_key": "templates:active:sort=-score"
  }
}
```

---

## 3. Template Suggestion ロジック

### 3-1. Vision Text 分析パイプライン

```
[vision_text 入力]
    ↓
[1. Tokenization & 形態素解析]
  - 日本語: janome または MeCab
  - 英語: nltk
    ↓
[2. Category Detection]
  - キーワード抽出（sales, marketing, cs, ops 等）
  - 複数カテゴリ検出対応
    ↓
[3. Skills Extraction]
  - Vision から要求スキルを抽出
  - 例: "営業" → relationship-building, negotiation
    ↓
[4. Temporal Analysis]
  - Timeline Urgency スコア（days, weeks）
  - Budget Constraint レベル
    ↓
[5. Template Matching & Scoring]
  - 各テンプレートに対してスコア計算
  - recommendation_level 判定
```

### 3-2. スコア計算式

```
match_score = 
  w1 * category_match_score +
  w2 * skills_fit_score +
  w3 * process_alignment_score +
  w4 * team_size_compatibility_score +
  w5 * timeline_feasibility_score

where:
  w1 = 0.25 (category の重要度最高)
  w2 = 0.25 (skills の重要度最高)
  w3 = 0.20 (process alignment)
  w4 = 0.15 (team size)
  w5 = 0.15 (timeline)
  Σwi = 1.0
```

#### 3-2-1. category_match_score

```
- detected_category が template.category と完全一致: 1.0
- 部分一致（e.g., "営業" と "sales + marketing"): 0.8
- 無関連: 0.0
```

#### 3-2-2. skills_fit_score

```
template_required_skills = [skill1, skill2, ...]
detected_skills = [detected1, detected2, ...]

fit_score = |intersection| / |union|  # Jaccard similarity

例:
  required_skills = [relationship-building, negotiation, closing]
  detected = [sales, relationship-building, closing]
  → fit_score = 2/4 = 0.5
```

#### 3-2-3. process_alignment_score

```
- テンプレートの process_key が vision に言及されているか
- 例: "月次決算" を目指すなら "monthly-closing" process マッチ
- frequency マッチ（daily など）も考慮
```

#### 3-2-4. team_size_compatibility_score

```
estimated_team_size = optional_context.team_size_estimate

template_roles の min_members の合計 ≤ estimated_team_size ≤ max_members の合計:
  → 1.0

範囲外（±20%以内）: 0.7
範囲外（±50%以内）: 0.4
範囲外（50%以上）: 0.0
```

#### 3-2-5. timeline_feasibility_score

```
timeline_days = optional_context.timeline_days

テンプレートの typical_setup_hours に基づいて:

setup_days = typical_setup_hours / 8  # 1日8時間作業

timeline_days ≥ setup_days * 1.5:  1.0  (十分な余裕)
timeline_days ≥ setup_days:        0.8  (最小限の余裕)
timeline_days < setup_days:        0.3  (タイト)
```

### 3-3. recommendation_level の判定

```python
if match_score >= 0.85:
    recommendation_level = "highly_recommended"
elif match_score >= 0.70:
    recommendation_level = "recommended"
elif match_score >= 0.50:
    recommendation_level = "alternative"
else:
    recommendation_level = "not_recommended"
```

---

## 4. DB スキーマ拡張

### 4-1. template_suggestions テーブル

```sql
CREATE TABLE IF NOT EXISTS template_suggestions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    suggestion_id           TEXT NOT NULL UNIQUE,  -- 例: sug_001_2026_04_22
    user_id                 TEXT NOT NULL,
    vision_text             TEXT NOT NULL,
    vision_analysis         TEXT,                  -- JSON (detected_categories, detected_skills, ...)
    
    -- スコア化結果
    matched_template_ids    TEXT,                  -- JSON [1, 3, 5]
    suggestion_scores       TEXT,                  -- JSON [{id: 1, score: 0.92}, ...]
    recommendation_levels   TEXT,                  -- JSON [{id: 1, level: "highly_recommended"}, ...]
    
    -- メタデータ
    processing_time_ms      INTEGER,
    model_version           TEXT,                  -- 例: "suggestion-v2.1"
    confidence_level        TEXT,                  -- 'high', 'medium', 'low'
    
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_template_suggestions_user_timestamp
  ON template_suggestions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_template_suggestions_id
  ON template_suggestions(suggestion_id);
```

### 4-2. suggestion_customization_log テーブル

```sql
CREATE TABLE IF NOT EXISTS suggestion_customization_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    suggestion_id           TEXT NOT NULL,         -- FK to template_suggestions
    instance_id             INTEGER NOT NULL,      -- FK to department_instances
    customization_config    TEXT NOT NULL,         -- JSON (full custom_config)
    action                  TEXT NOT NULL,         -- 'selected', 'customized', 'finalized'
    status                  TEXT DEFAULT 'pending', -- 'pending', 'completed', 'cancelled'
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    
    FOREIGN KEY (suggestion_id) REFERENCES template_suggestions(suggestion_id),
    FOREIGN KEY (instance_id) REFERENCES department_instances(id) ON DELETE CASCADE,
    UNIQUE(suggestion_id, instance_id)
);

CREATE INDEX IF NOT EXISTS idx_customization_log_instance_id
  ON suggestion_customization_log(instance_id);
```

### 4-3. スキーマ整合性ルール

```sql
-- Department Instance への suggestion_id 紐付け
ALTER TABLE department_instances 
ADD COLUMN suggestion_id TEXT REFERENCES template_suggestions(suggestion_id);

-- Suggestion から Instance への逆参照インデックス
CREATE INDEX IF NOT EXISTS idx_instances_suggestion_id
  ON department_instances(suggestion_id);
```

---

## 5. エラーハンドリング

### 5-1. エラー分類

| エラーコード | HTTP Status | 説明 |
|---|---|---|
| `INVALID_VISION_TEXT` | 400 | vision_text がバリデーション失敗 |
| `TEMPLATE_NOT_FOUND` | 404 | 指定 template_id が存在しない |
| `ROLE_ASSIGNMENT_MISMATCH` | 400 | ロール割り当てが制約違反 |
| `BUDGET_ALLOCATION_INVALID` | 400 | 予算配分がバリデーション失敗 |
| `SUGGESTION_EXPIRED` | 410 | suggestion_id の有効期限切れ（24h） |
| `INTERNAL_SUGGESTION_ERROR` | 500 | Vision 分析エラー |
| `UNAUTHORIZED` | 401 | 認証失敗 |
| `RATE_LIMIT_EXCEEDED` | 429 | API レート制限超過 |

### 5-2. エラーレスポンス形式

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "request_id": "req_xxx",
    "timestamp": "2026-04-22T10:30:45Z",
    "details": {
      "field": "optional_field_name",
      "constraint": "constraint_description",
      "received": "actual_value",
      "expected": "expected_value"
    }
  }
}
```

---

## 6. パフォーマンス・セキュリティ

### 6-1. キャッシング戦略

```
1. Template Stats キャッシュ (Redis / in-memory)
   - Key: "templates:stats:{template_id}"
   - TTL: 1時間
   - 無効化トリガー: department_instance 作成/削除

2. Vision Analysis キャッシュ (Redis)
   - Key: "vision:analysis:{hash(vision_text)}"
   - TTL: 5分（同一ビジョンへの重複分析回避）
   - 容量: 最大100エントリ

3. Template List キャッシュ (Redis)
   - Key: "templates:list:{category}:{status}:{sort_order}"
   - TTL: 1時間
   - 無効化トリガー: テンプレート作成/更新
```

### 6-2. レート制限

```
POST /suggest-templates:
  - 認証済みユーザー: 100 req/hour
  - 非認証（デモ）: 5 req/hour
  - Burst: 10 req/minute

POST /customize-template:
  - 認証済み: 50 req/hour
  - Burst: 5 req/minute
```

### 6-3. セキュリティ

```
1. Input Validation
   - vision_text: SQLi, XSS 対策（HTML escape）
   - custom_config: JSON スキーマ検証
   - parameter whitelist（sort, category 等）

2. Authorization
   - API Key + JWT ベース認証
   - ユーザーは自身の suggestion_log のみアクセス可能
   - Admin のみ全テンプレート編集可能

3. Audit Logging
   - 全 suggestion, customization を記録
   - タイムスタンプ + user_id + IP 記録
   - 監査目的で90日保持
```

### 6-4. パフォーマンス目標

```
SLA:
- POST /suggest-templates:      < 500ms (p99)
- POST /customize-template:     < 200ms (p99)
- GET /templates:               < 100ms (p99、キャッシュ利用時)

Throughput:
- suggest-templates:             200 req/sec 対応
- customize-template:            100 req/sec 対応
- templates list:                500 req/sec 対応
```

---

## 実装チェックリスト

### フェーズ 1: DB スキーマ（優先度: 最高）
- [ ] `template_suggestions` テーブル作成
- [ ] `suggestion_customization_log` テーブル作成
- [ ] インデックス最適化
- [ ] マイグレーション検証（冪等性）

### フェーズ 2: Suggestion Engine（優先度: 高）
- [ ] Vision Text 分析パイプライン実装
  - [ ] Tokenization + 形態素解析
  - [ ] Category Detection ロジック
  - [ ] Skills Extraction ロジック
  - [ ] Temporal Analysis ロジック
- [ ] スコア計算式実装＆検証
- [ ] recommendation_level 判定ロジック

### フェーズ 3: API 実装（優先度: 高）
- [ ] POST /suggest-templates エンドポイント
- [ ] POST /customize-template エンドポイント
- [ ] GET /templates エンドポイント（改善版）
- [ ] Input validation + error handling
- [ ] Authentication & Authorization

### フェーズ 4: キャッシング・最適化（優先度: 中）
- [ ] Redis キャッシングレイヤー実装
- [ ] キャッシュ無効化ロジック
- [ ] レート制限実装
- [ ] パフォーマンステスト（負荷テスト）

### フェーズ 5: テスト・ドキュメント（優先度: 中）
- [ ] ユニットテスト（スコア計算ロジック）
- [ ] API 統合テスト
- [ ] E2E テスト（vision → suggestion → customization → instance 作成）
- [ ] パフォーマンステスト（1000テンプレート規模）
- [ ] OpenAPI / Swagger 仕様書

---

## 参考資料

- **既存スキーマ**: `docs/design/department-templates-schema.md`
- **ワークフロー設計**: `docs/workflow-template-design.md`
- **ペルソナ要件**: `docs/design/PERSONA_FEATURE_REQUIREMENTS.md`
- **UIプロトタイプ**: `dashboard/prototype-onboarding-wizard.html`

---

**次の承認者**: Tech Lead (レビュー・承認)  
**実装開始日**: (Tech Lead 承認後)  
**目標完了日**: 2026-05-15

