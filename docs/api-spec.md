# API 仕様書 - THEBRANCH マーケットプレイス

**バージョン**: v1.0  
**作成日**: 2026-04-23  
**対応フェーズ**: オンボーディングマーケットプレイス実装  

---

## 概要

本ドキュメントは、THEBRANCHマーケットプレイスUIに対応するバックエンドAPI仕様を定義します。ユーザーのビジョン入力からテンプレート提案、カスタマイズ、デプロイまでの一連のフローをサポートします。

---

## 1. テンプレート提案 API

### エンドポイント
```
POST /api/onboarding/suggest
```

### 説明
ユーザーのビジョン入力からマッチするテンプレートを提案する。キーワード抽出 → スコアリング → ランキング処理を実行します。

### リクエスト

```json
{
  "vision_text": "営業チーム立ち上げ、月商1000万円達成",
  "user_context": {
    "industry": "BtoB SaaS",
    "company_size": "startup",
    "experience_level": "beginner"
  },
  "language": "ja"
}
```

**パラメータ説明**:
| 項目 | 型 | 必須 | 説明 |
|---|---|---|---|
| vision_text | string | ✓ | ユーザーが入力したビジョンテキスト（最大500文字） |
| user_context | object | | 追加コンテキスト（業種・会社規模・経験レベル） |
| language | string | | 言語設定（ja / en、デフォルト: ja） |

### レスポンス

```json
{
  "success": true,
  "suggested_templates": [
    {
      "id": "tpl_sales_001",
      "name": "営業推進部",
      "description": "営業組織の構築と成長を支援する部署テンプレート",
      "category": "sales",
      "match_score": 0.92,
      "confidence_level": "HIGH",
      "recommendation_level": "HIGHLY_RECOMMENDED",
      "key_reasons": [
        "ビジョンに含まれる『営業』キーワードとマッチ",
        "『月商1000万円』の目標スケールに最適"
      ],
      "preview": {
        "roles_count": 4,
        "processes_count": 5,
        "estimated_budget_monthly": 3500000
      }
    },
    {
      "id": "tpl_sales_002",
      "name": "営業企画部",
      "description": "営業戦略立案・マーケット分析を担当する部署テンプレート",
      "category": "sales",
      "match_score": 0.65,
      "confidence_level": "MEDIUM",
      "recommendation_level": "ALTERNATIVE",
      "key_reasons": [
        "営業関連テンプレート（代替案）"
      ],
      "preview": {
        "roles_count": 3,
        "processes_count": 4,
        "estimated_budget_monthly": 2800000
      }
    },
    {
      "id": "tpl_product_001",
      "name": "プロダクト開発部",
      "description": "プロダクト開発・改善を推進する部署テンプレート",
      "category": "product",
      "match_score": 0.45,
      "confidence_level": "LOW",
      "recommendation_level": "MAYBE",
      "key_reasons": [
        "スケール目標に関連する可能性"
      ],
      "preview": {
        "roles_count": 5,
        "processes_count": 6,
        "estimated_budget_monthly": 4200000
      }
    }
  ],
  "search_keywords_extracted": ["営業", "チーム", "月商", "達成"],
  "processing_time_ms": 145,
  "suggestion_log_id": "log_20260423_001"
}
```

**レスポンス詳細**:
| 項目 | 型 | 説明 |
|---|---|---|
| success | boolean | リクエスト成功フラグ |
| suggested_templates | array | マッチしたテンプレートの配列（スコア降順） |
| suggestion_log_id | string | このリクエストの一意ID（履歴管理用） |

### エラーレスポンス

```json
{
  "success": false,
  "error_code": "INVALID_REQUEST",
  "error_message": "vision_text は必須パラメータです",
  "status_code": 400
}
```

| エラーコード | HTTP | 説明 |
|---|---|---|
| INVALID_REQUEST | 400 | リクエスト形式エラー |
| EMPTY_VISION | 400 | vision_text が空 |
| TEXT_TOO_LONG | 400 | vision_text が500文字を超過 |
| TEMPLATE_NOT_FOUND | 404 | テンプレートが見つからない |
| INTERNAL_ERROR | 500 | サーバーエラー |

---

## 2. テンプレート詳細取得 API

### エンドポイント
```
GET /templates/{id}
```

### 説明
選択したテンプレートの詳細情報を取得する。ロール構成、プロセス、予算見積、KPI定義などを返します。

### パスパラメータ

| 項目 | 型 | 必須 | 説明 |
|---|---|---|---|
| id | string | ✓ | テンプレート ID（例：tpl_sales_001） |

### クエリパラメータ

```
GET /templates/tpl_sales_001?include_processes=true&include_budget=true&language=ja
```

| 項目 | 型 | 説明 |
|---|---|---|
| include_processes | boolean | プロセス定義を含める（デフォルト: true） |
| include_budget | boolean | 予算見積を含める（デフォルト: true） |
| language | string | 言語設定（ja / en） |

### レスポンス

```json
{
  "success": true,
  "template": {
    "id": "tpl_sales_001",
    "name": "営業推進部",
    "description": "営業組織の構築と成長を支援する部署テンプレート",
    "category": "sales",
    "version": "1.0",
    "created_date": "2026-04-01",
    "last_updated": "2026-04-15",
    "roles": [
      {
        "role_id": "role_sales_001",
        "title": "営業マネージャー",
        "description": "営業チーム全体のマネジメントと目標達成",
        "required_count": 1,
        "salary_range": {
          "min": 4000000,
          "max": 6000000,
          "currency": "JPY",
          "period": "annual"
        },
        "responsibilities": [
          "営業チームのマネジメント",
          "営業目標の設定・管理",
          "顧客関係管理",
          "新規営業戦略の立案"
        ],
        "required_skills": ["営業管理", "対人スキル", "戦略立案"]
      },
      {
        "role_id": "role_sales_002",
        "title": "営業担当",
        "description": "顧客開拓と既存顧客管理",
        "required_count": 3,
        "salary_range": {
          "min": 2500000,
          "max": 4000000,
          "currency": "JPY",
          "period": "annual"
        },
        "responsibilities": [
          "新規顧客開拓",
          "提案・受注",
          "既存顧客管理",
          "営業レポート作成"
        ],
        "required_skills": ["営業スキル", "顧客対応", "商品知識"]
      }
    ],
    "processes": [
      {
        "process_id": "proc_001",
        "name": "営業活動",
        "description": "見込み客の発掘と初期接触",
        "sequence": 1,
        "owner_role": "role_sales_002",
        "estimated_hours_weekly": 20,
        "tools_required": ["CRM", "メール", "電話"],
        "kpi": {
          "name": "新規接触数",
          "target": 50,
          "unit": "件/月",
          "measurement_frequency": "monthly"
        }
      },
      {
        "process_id": "proc_002",
        "name": "提案・ヒアリング",
        "description": "顧客ニーズのヒアリングと提案書作成",
        "sequence": 2,
        "owner_role": "role_sales_001",
        "estimated_hours_weekly": 15,
        "tools_required": ["提案書作成ツール", "顧客情報管理"],
        "kpi": {
          "name": "提案件数",
          "target": 20,
          "unit": "件/月",
          "measurement_frequency": "monthly"
        }
      },
      {
        "process_id": "proc_003",
        "name": "契約・受注",
        "description": "契約交渉と受注管理",
        "sequence": 3,
        "owner_role": "role_sales_001",
        "estimated_hours_weekly": 10,
        "tools_required": ["契約管理", "受注システム"],
        "kpi": {
          "name": "受注件数",
          "target": 5,
          "unit": "件/月",
          "measurement_frequency": "monthly"
        }
      }
    ],
    "budget_estimate": {
      "monthly": {
        "salary": 3250000,
        "tools_and_systems": 200000,
        "training": 100000,
        "other": 50000,
        "total": 3600000
      },
      "yearly": {
        "salary": 39000000,
        "tools_and_systems": 2400000,
        "training": 1200000,
        "other": 600000,
        "total": 43200000
      },
      "currency": "JPY",
      "assumptions": [
        "給与は市場相場ベース（業績手当を除く）",
        "ツール費用は複数ツール統合のライセンス料",
        "トレーニングは新入社員向け研修費用"
      ]
    },
    "kpi_framework": {
      "department_level": {
        "name": "月間売上高",
        "target": 10000000,
        "unit": "JPY",
        "measurement_frequency": "monthly"
      },
      "team_level": [
        {
          "name": "営業ユニット売上",
          "target": 5000000,
          "unit": "JPY"
        }
      ]
    },
    "success_metrics": {
      "revenue_target_monthly": 10000000,
      "customer_acquisition": 5,
      "customer_retention_rate": 0.85,
      "sales_cycle_days": 30
    },
    "implementation_timeline": {
      "setup_phase_weeks": 2,
      "ramp_up_phase_weeks": 4,
      "stable_phase_weeks": 4,
      "total_timeline_weeks": 10
    },
    "dependencies": [
      {
        "type": "TOOL",
        "name": "CRM System",
        "status": "REQUIRED",
        "note": "SalesForce または HubSpot 推奨"
      },
      {
        "type": "TRAINING",
        "name": "営業スキル研修",
        "status": "REQUIRED",
        "duration_hours": 20
      }
    ]
  }
}
```

### エラーレスポンス

```json
{
  "success": false,
  "error_code": "TEMPLATE_NOT_FOUND",
  "error_message": "テンプレート ID 'tpl_invalid' は見つかりません",
  "status_code": 404
}
```

---

## 3. カスタマイズ API

### エンドポイント
```
POST /api/onboarding/customize
```

### 説明
テンプレートをカスタマイズ（部署名、メンバー数、予算調整）する。バリデーション警告を返して、ユーザーの意思決定をサポートします。

### リクエスト

```json
{
  "template_id": "tpl_sales_001",
  "customization": {
    "department_name": "営業推進部 東京",
    "department_code": "SALES_TOKYO",
    "member_count": 3,
    "budget_monthly": 3000000,
    "budget_yearly": 36000000,
    "reporting_manager_id": "user_123",
    "location": "Tokyo",
    "start_date": "2026-05-01",
    "custom_roles": [
      {
        "role_id": "role_sales_001",
        "title": "営業マネージャー",
        "allocated_count": 1,
        "salary_override": 5000000
      },
      {
        "role_id": "role_sales_002",
        "title": "営業担当",
        "allocated_count": 2,
        "salary_override": 3000000
      }
    ]
  }
}
```

**パラメータ説明**:
| 項目 | 型 | 必須 | 説明 |
|---|---|---|---|
| template_id | string | ✓ | カスタマイズするテンプレート ID |
| department_name | string | ✓ | 新しい部署名 |
| department_code | string | | 部署コード（システム内部用） |
| member_count | integer | ✓ | 配置メンバー数 |
| budget_monthly | integer | ✓ | 月額予算 |
| reporting_manager_id | string | | 報告先マネージャー ID |
| start_date | string (YYYY-MM-DD) | | 部署開始日 |

### レスポンス

```json
{
  "success": true,
  "customized_template": {
    "id": "instance_20260423_001",
    "original_template_id": "tpl_sales_001",
    "status": "DRAFT",
    "department": {
      "name": "営業推進部 東京",
      "code": "SALES_TOKYO",
      "member_count": 3,
      "location": "Tokyo",
      "start_date": "2026-05-01"
    },
    "budget": {
      "monthly": 3000000,
      "yearly": 36000000,
      "per_person_monthly": 1000000,
      "per_person_yearly": 12000000,
      "breakdown": {
        "salary": 2500000,
        "tools": 200000,
        "training": 100000,
        "buffer": 200000
      }
    },
    "roles": [
      {
        "title": "営業マネージャー",
        "count": 1,
        "salary_monthly": 500000,
        "status": "CONFIRMED"
      },
      {
        "title": "営業担当",
        "count": 2,
        "salary_monthly": 250000,
        "status": "CONFIRMED"
      }
    ]
  },
  "validation_warnings": [
    {
      "type": "BUDGET_BELOW_MARKET",
      "severity": "WARNING",
      "field": "budget_monthly",
      "message": "市場相場: ¥950万円/人に対して、カスタマイズ予算は¥1,000万円/人です",
      "recommendation": "市場相場並みの予算設定です。採用困難の場合は予算増加を検討してください",
      "impact": "MEDIUM"
    },
    {
      "type": "TEAM_SIZE_SMALL",
      "severity": "INFO",
      "field": "member_count",
      "message": "テンプレート推奨人数（4名）より少ない構成です",
      "recommendation": "マネージャーを中心とした小規模運営になります。業務負荷を確認してください",
      "impact": "LOW"
    }
  ],
  "suggestions": [
    {
      "category": "BUDGET_OPTIMIZATION",
      "text": "月額 3,200,000 円に増額することで、市場相場並みかつ、採用競争力が向上します",
      "estimated_impact": "採用成功率 +15%"
    }
  ],
  "next_steps": [
    {
      "step_number": 1,
      "action": "警告を確認",
      "description": "BUDGET_BELOW_MARKET 警告を確認し、予算調整を検討"
    },
    {
      "step_number": 2,
      "action": "部署設定を確定",
      "description": "/api/onboarding/finalize エンドポイントを呼び出し"
    },
    {
      "step_number": 3,
      "action": "デプロイ",
      "description": "/api/onboarding/deploy エンドポイントで部署を作成"
    }
  ]
}
```

### エラーレスポンス

```json
{
  "success": false,
  "error_code": "VALIDATION_FAILED",
  "error_message": "カスタマイズバリデーションに失敗しました",
  "validation_errors": [
    {
      "field": "member_count",
      "message": "メンバー数は 1 以上 20 以下である必要があります"
    },
    {
      "field": "budget_monthly",
      "message": "月額予算は 500,000 円以上である必要があります"
    }
  ],
  "status_code": 400
}
```

---

## 4. リアルタイム計算 API

### エンドポイント
```
POST /api/onboarding/calculate-impact
```

### 説明
人数・予算変更時のリアルタイム計算。市場相場との比較、警告メッセージを返します。

### リクエスト

```json
{
  "template_id": "tpl_sales_001",
  "member_count": 3,
  "budget_monthly": 3000000,
  "calculation_type": "budget_impact"
}
```

### レスポンス

```json
{
  "success": true,
  "calculation": {
    "input": {
      "member_count": 3,
      "budget_monthly": 3000000
    },
    "output": {
      "per_person_cost_monthly": 1000000,
      "per_person_cost_yearly": 12000000,
      "market_average_monthly": 950000,
      "market_average_yearly": 11400000,
      "comparison": {
        "difference_monthly": 50000,
        "difference_percentage": 5.26,
        "status": "ABOVE_MARKET"
      }
    },
    "warning_level": "LOW",
    "warnings": [
      {
        "type": "ABOVE_MARKET",
        "message": "市場相場より 5.26% 高い予算設定です",
        "severity": "INFO"
      }
    ],
    "recommendations": [
      {
        "type": "BUDGET_ADJUSTMENT",
        "suggested_budget": 2850000,
        "benefit": "市場相場に合致し、採用競争力が平準化します",
        "impact": "LOW"
      }
    ],
    "cost_breakdown": {
      "salary": 2500000,
      "tools_systems": 200000,
      "training": 100000,
      "buffer": 200000,
      "total": 3000000
    }
  }
}
```

---

## 5. デプロイ / 部署作成 API

### エンドポイント
```
POST /api/onboarding/deploy
```

### 説明
カスタマイズ完了後、部署を実際に作成する（最終確認）。

### リクエスト

```json
{
  "instance_id": "instance_20260423_001",
  "confirm_deployment": true,
  "owner_user_id": "user_123"
}
```

### レスポンス

```json
{
  "success": true,
  "deployment": {
    "status": "DEPLOYED",
    "department_id": "dept_20260423_001",
    "department_name": "営業推進部 東京",
    "created_at": "2026-04-23T10:30:00Z",
    "next_actions": [
      {
        "action": "メンバー招待",
        "description": "部署にメンバーを招待する",
        "url": "/departments/dept_20260423_001/invite"
      },
      {
        "action": "エージェント設定",
        "description": "AIエージェント設定を開始する",
        "url": "/departments/dept_20260423_001/agents/setup"
      }
    ]
  }
}
```

---

## データベース スキーマ

### suggestion_log テーブル
```sql
CREATE TABLE suggestion_log (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  vision_text TEXT NOT NULL,
  user_context JSON,
  suggested_templates JSON NOT NULL, -- {template_id, name, score}[]
  selected_template_id TEXT,
  search_keywords_extracted JSON, -- キーワード抽出結果
  processing_time_ms INTEGER,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (selected_template_id) REFERENCES departments_templates(id)
);

CREATE INDEX idx_suggestion_log_user ON suggestion_log(user_id);
CREATE INDEX idx_suggestion_log_created ON suggestion_log(created_at);
```

### template_instance テーブル
```sql
CREATE TABLE template_instance (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  template_id TEXT NOT NULL,
  department_name TEXT NOT NULL,
  department_code TEXT UNIQUE,
  member_count INTEGER NOT NULL,
  budget_monthly INTEGER NOT NULL,
  budget_yearly INTEGER NOT NULL,
  location TEXT,
  start_date DATE,
  customization_data JSON NOT NULL, -- {roles[], processes[], budget_breakdown}
  validation_warnings JSON, -- バリデーション警告の履歴
  status TEXT DEFAULT 'DRAFT', -- DRAFT, CONFIRMED, DEPLOYED, ARCHIVED
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  deployed_at DATETIME,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (template_id) REFERENCES departments_templates(id)
);

CREATE INDEX idx_template_instance_user ON template_instance(user_id);
CREATE INDEX idx_template_instance_status ON template_instance(status);
CREATE INDEX idx_template_instance_created ON template_instance(created_at);
```

### scoring_result テーブル
```sql
CREATE TABLE scoring_result (
  id TEXT PRIMARY KEY,
  suggestion_log_id TEXT NOT NULL,
  template_id TEXT NOT NULL,
  vision_text TEXT NOT NULL,
  extracted_keywords JSON, -- ["営業", "チーム", ...]
  keyword_match_score REAL, -- 0.0-1.0
  category_match_score REAL,
  scale_match_score REAL,
  final_score REAL,
  confidence_level TEXT, -- HIGH, MEDIUM, LOW
  recommendation_level TEXT, -- HIGHLY_RECOMMENDED, ALTERNATIVE, MAYBE
  key_reasons JSON, -- スコア根拠のテキスト
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (suggestion_log_id) REFERENCES suggestion_log(id),
  FOREIGN KEY (template_id) REFERENCES departments_templates(id)
);

CREATE INDEX idx_scoring_result_suggestion ON scoring_result(suggestion_log_id);
CREATE INDEX idx_scoring_result_final_score ON scoring_result(final_score DESC);
```

### template_market_data テーブル
```sql
CREATE TABLE template_market_data (
  id TEXT PRIMARY KEY,
  template_id TEXT NOT NULL,
  metric_type TEXT NOT NULL, -- salary_range, cost_per_person, etc
  value_min INTEGER,
  value_max INTEGER,
  value_avg INTEGER,
  currency TEXT DEFAULT 'JPY',
  data_source TEXT,
  last_updated DATETIME,
  FOREIGN KEY (template_id) REFERENCES departments_templates(id)
);

CREATE INDEX idx_template_market_data_template ON template_market_data(template_id);
```

---

## エラーハンドリング

### 標準エラーレスポンス形式

```json
{
  "success": false,
  "error_code": "ERROR_CODE",
  "error_message": "ユーザーフレンドリーなエラーメッセージ",
  "error_details": {
    "debug_info": "開発者向けの詳細情報"
  },
  "status_code": 400,
  "request_id": "req_20260423_001"
}
```

### エラーコード一覧

| エラーコード | HTTP | 説明 |
|---|---|---|
| INVALID_REQUEST | 400 | リクエスト形式エラー |
| EMPTY_VISION | 400 | vision_text が空 |
| TEXT_TOO_LONG | 400 | テキストが制限を超過 |
| INVALID_TEMPLATE_ID | 400 | テンプレート ID が無効 |
| VALIDATION_FAILED | 400 | バリデーション失敗 |
| BUDGET_OUT_OF_RANGE | 400 | 予算が範囲外 |
| MEMBER_COUNT_INVALID | 400 | メンバー数が無効 |
| UNAUTHORIZED | 401 | 認証失敗 |
| FORBIDDEN | 403 | アクセス権限なし |
| TEMPLATE_NOT_FOUND | 404 | テンプレットが見つからない |
| INSTANCE_NOT_FOUND | 404 | インスタンスが見つからない |
| CONFLICT | 409 | リソース競合（例：department_code 重複） |
| INTERNAL_ERROR | 500 | サーバーエラー |
| UNAVAILABLE | 503 | サービス一時利用不可 |

---

## 実装優先順位

### P1（最優先）
```
1. テンプレート提案 API
   └─ ビジョンテキスト解析 → テンプレートマッチング
   └─ suggestion_log テーブル
   
2. テンプレート詳細取得 API
   └─ テンプレートデータベース照会
   └─ ロール・プロセス・予算情報返却
   
3. DB テーブル定義
   └─ suggestion_log, template_instance, scoring_result
   └─ スキーマ・インデックス作成
```

### P2（次優先）
```
4. カスタマイズ API
   └─ テンプレート → インスタンス変換
   └─ バリデーション・警告生成
   
5. リアルタイム計算 API
   └─ 市場相場計算
   └─ 予算インパクト分析
   
6. デプロイ API
   └─ 最終確認 → 部署作成
```

### P3（拡張機能）
```
7. エラーハンドリング詳細化
   └─ ユーザーメッセージ翻訳
   └─ エラーリトライロジック
   
8. ロギング・監視
   └─ API 呼び出しログ
   └─ パフォーマンスメトリクス
```

---

## 実装チェックリスト

### API 実装
- [ ] テンプレート提案 API（POST /api/onboarding/suggest）
- [ ] テンプレート詳細取得 API（GET /templates/{id}）
- [ ] カスタマイズ API（POST /api/onboarding/customize）
- [ ] リアルタイム計算 API（POST /api/onboarding/calculate-impact）
- [ ] デプロイ API（POST /api/onboarding/deploy）

### DB 実装
- [ ] suggestion_log テーブル作成
- [ ] template_instance テーブル作成
- [ ] scoring_result テーブル作成
- [ ] template_market_data テーブル作成
- [ ] インデックス作成
- [ ] 外部キー制約設定

### テスト
- [ ] ユニットテスト（各エンドポイント）
- [ ] 統合テスト（フロー全体）
- [ ] エラーハンドリングテスト
- [ ] パフォーマンステスト
- [ ] E2E テスト（UI との連携）

### ドキュメント
- [ ] API 仕様書確認
- [ ] エラーメッセージ日本語化
- [ ] 実装例コード作成
- [ ] トラブルシューティングガイド

---

## 関連ドキュメント

- `/docs/marketplace-ux.md` - マーケットプレイス UX 仕様（別ドキュメント）
- `/docs/design/DESIGN_SYSTEM.md` - デザインシステム
- `/dashboard/app.py` - Flask バックエンド実装
- `/workflow/services/` - ビジネスロジック層

---

## 更新履歴

| バージョン | 日付 | 変更内容 |
|---|---|---|
| v1.0 | 2026-04-23 | 初版作成 |
