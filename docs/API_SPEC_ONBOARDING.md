# オンボーディング API 仕様ドキュメント

## 概要

THEBRANCH オンボーディングの4段階フロー全体をサポートする REST API の完全仕様。

**API ベース URL**: `/api/onboarding`

---

## 実装状況サマリー

| エンドポイント | メソッド | ステータス | 説明 |
|---|---|---|---|
| `/vision` | POST | ✅ 実装済み | ビジョン入力 (Step 0) |
| `/suggest` | POST | ✅ 実装済み | AI 部署提案取得 (Step 1) |
| `/initialize` | POST | ✅ 実装済み | ビジョン → 提案一体処理 |
| `/setup` | POST | ✅ 実装済み | 詳細設定 (Step 2) |
| `/execute` | POST | ✅ 実装済み | 初期タスク実行 (Step 3) |
| `/complete` | POST | ✅ 実装済み | オンボーディング完了確認 |

---

## Phase 1: ビジョン入力

### Endpoint: POST /api/onboarding/vision

**目的**: ユーザーのビジョンを保存し、Step 0 を記録

**認証**: Bearer Token (Authorization ヘッダー)

**Request Body**:
```json
{
  "onboarding_id": "uuid",
  "vision_input": "営業チーム立ち上げ、月商1000万円達成"
}
```

**Validation**:
- `vision_input`: 10-500 文字
- `onboarding_id`: UUID フォーマット

**Response (201 Created)**:
```json
{
  "success": true,
  "onboarding_id": "uuid",
  "current_step": 0,
  "message": "ビジョンを保存しました"
}
```

**Error Responses**:
- `400 Bad Request`: Vision input が無効（短すぎる、長すぎる）
- `401 Unauthorized`: Token が無効
- `500 Internal Server Error`: DB エラー

**DB Operations**:
- `INSERT INTO user_onboarding_progress` with `current_step = 0`

---

## Phase 2: AI 部署提案

### Endpoint: POST /api/onboarding/suggest

**目的**: AI がビジョンを分析し、最適な部署テンプレートを提案

**認証**: Bearer Token

**Request Body**:
```json
{
  "onboarding_id": "uuid",
  "vision_input": "営業チーム立ち上げ、月商1000万円達成"
}
```

**Workflow**:
1. `workflow.services.onboarding.OnboardingService` が vision を分析
2. `template_repo` から全テンプレートを取得
3. AI スコアリングで各テンプレートのマッチスコアを計算
4. スコア順にソート＆返却

**Response (200 OK)**:
```json
{
  "onboarding_id": "uuid",
  "suggestions": [
    {
      "template_id": "sales",
      "name": "営業推進部",
      "match_score": 0.98,
      "config": {
        "members_count": 4,
        "roles": ["営業3人", "マネージャー1人"],
        "budget_monthly": 3000000,
        "processes": ["リード発掘", "初期接触", "提案・クロージング"]
      }
    },
    {
      "template_id": "cs",
      "name": "カスタマーサクセス部",
      "match_score": 0.65,
      "config": { ... }
    }
  ]
}
```

**DB Operations**:
- `UPDATE user_onboarding_progress` set `suggested_template_id`, `suggestion_reason`, `current_step = 1`

---

## Phase 3a: ビジョン → 提案 一体処理（Initialize）

### Endpoint: POST /api/onboarding/initialize

**目的**: ビジョン入力と AI 提案を1ステップで実行（フロント最適化）

**認証**: Bearer Token

**Request Body**:
```json
{
  "vision_input": "営業チーム立ち上げ、月商1000万円達成"
}
```

**Workflow**:
1. `vision_input` バリデーション
2. onboarding_id を自動生成（UUID）
3. DB に `vision_input` を保存
4. AI 分析実行
5. テンプレート提案を返却

**Response (200 OK)**:
```json
{
  "onboarding_id": "uuid",
  "suggestions": [...]
}
```

**DB Operations**:
- `INSERT INTO user_onboarding_progress` with `current_step = 0`
- `UPDATE` to `current_step = 1` after suggestions

---

## Phase 3b: 詳細設定

### Endpoint: POST /api/onboarding/setup

**目的**: 部署の詳細設定を保存し、予算検証を実行

**認証**: Bearer Token

**Request Body**:
```json
{
  "onboarding_id": "uuid",
  "template_id": "sales",
  "dept_name": "営業推進部",
  "manager_name": "山田太郎",
  "members_count": 3,
  "budget": 3000000,
  "kpi": "月商1000万円、成約率35%",
  "integrations": {
    "salesforce": true,
    "sheets": false,
    "slack": true
  }
}
```

**Validation**:
- `dept_name`: 必須、1-100 文字
- `manager_name`: 必須、1-100 文字
- `members_count`: 1-100（整数）
- `budget`: 正の整数
- Budget per person が市場ベンチマーク × 0.8 以上か検証

**Budget Validation Logic**:
```
monthly_per_person = budget / members_count
market_benchmark = 950000（営業推進部の相場）

if monthly_per_person >= market_benchmark * 0.8:
  status = "ok"
else:
  status = "warning"
```

**Response (200 OK)**:
```json
{
  "onboarding_id": "uuid",
  "dept_id": "dept_abc123",
  "config_validated": true,
  "budget_validation": {
    "status": "ok",
    "monthly_per_person": 1000000,
    "market_benchmark": 950000,
    "message": "予算レベルは実行可能です"
  },
  "current_step": 2
}
```

**Error Response (400 Bad Request)**:
```json
{
  "ok": false,
  "error": "dept_name is required"
}
```

**DB Operations**:
- `UPDATE user_onboarding_progress` set `dept_name`, `manager_name`, `members_count`, `budget`, `kpi`, `integrations`, `current_step = 2`

---

## Phase 3c: 初期タスク実行

### Endpoint: POST /api/onboarding/execute

**目的**: AI がテンプレートから初期タスクを自動生成し、エージェント起動

**認証**: Bearer Token

**Request Body**:
```json
{
  "onboarding_id": "uuid"
}
```

**Workflow**:
1. onboarding_progress から dept_id を取得
2. `workflow.services.onboarding.OnboardingService.generate_initial_tasks()` を呼び出し
3. タスク定義（title, description, budget, deadline）を自動生成
4. 生成されたタスク JSON を DB に保存
5. agent_status を "activating" に設定
6. completed_at をセット（Step 3 完了）

**Generated Tasks Example** (営業推進部):
```json
[
  {
    "task_id": "task_1",
    "title": "リード発掘",
    "description": "B2B リード 100社の発掘と初期スクリーニング",
    "budget": 500000,
    "deadline": "2026-04-29",
    "assigned_to": "営業エージェント1"
  },
  {
    "task_id": "task_2",
    "title": "初期接触・営業提案",
    "description": "リード 20社への初期接触と提案資料作成",
    "budget": 500000,
    "deadline": "2026-05-06",
    "assigned_to": "営業エージェント2"
  },
  {
    "task_id": "task_3",
    "title": "月次レポート",
    "description": "部署の進捗報告・分析・改善提案",
    "deadline": "2026-05-22"
  }
]
```

**Response (200 OK)**:
```json
{
  "onboarding_id": "uuid",
  "dept_id": "dept_abc123",
  "tasks_created": [
    {
      "task_id": "task_1",
      "title": "リード発掘",
      "budget": 500000,
      "deadline": "2026-04-29"
    },
    ...
  ],
  "agent_status": "activating",
  "dashboard_url": "/dashboard/dept/dept_abc123",
  "current_step": 3,
  "completed_at": "2026-04-22T19:30:00Z"
}
```

**DB Operations**:
- `UPDATE user_onboarding_progress` set `initial_tasks` (JSON), `agent_status = 'activating'`, `current_step = 3`, `completed_at`

---

## Phase 4: オンボーディング完了確認

### Endpoint: POST /api/onboarding/complete

**目的**: オンボーディングが正常に完了したことを確認し、ダッシュボード遷移情報を返す

**認証**: Bearer Token

**Request Body**:
```json
{
  "onboarding_id": "uuid",
  "dept_id": "dept_abc123"
}
```

**Workflow**:
1. `onboarding_id` の最終状態を確認
2. `current_step == 3` かつ `completed_at` が設定されているか確認
3. ダッシュボード URL を生成
4. onboarding_completed フラグをセット

**Response (201 Created)**:
```json
{
  "ok": true,
  "onboarding_id": "uuid",
  "dept_id": "dept_abc123",
  "dashboard_url": "/dashboard/dept/dept_abc123",
  "message": "オンボーディング完了。ダッシュボードへ遷移します。"
}
```

---

## 共通ヘッダー・エラー仕様

### 認証

すべてのエンドポイントは Bearer Token 認証が必須：

```
Authorization: Bearer <token>
```

Token 検証の流れ：
1. Authorization ヘッダーの有無を確認
2. "Bearer " プレフィックスを検証
3. `auth.verify_token(token)` で user_id を取得
4. user_id が無効なら `401 Unauthorized`

### エラーレスポンス標準形式

```json
{
  "detail": "エラーメッセージ"
}
```

**HTTP Status Codes**:
- `201 Created`: リソース作成成功
- `200 OK`: 成功
- `400 Bad Request`: 入力値エラー
- `401 Unauthorized`: 認証失敗
- `500 Internal Server Error`: サーバーエラー

---

## データベーススキーマ

### テーブル: user_onboarding_progress

```sql
CREATE TABLE user_onboarding_progress (
  onboarding_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  
  -- Step 0: Vision Input
  vision_input TEXT,
  
  -- Step 1: AI Suggestion
  suggested_template_id TEXT,
  suggestion_reason TEXT,
  
  -- Step 2: Detailed Setup
  dept_id TEXT,
  dept_name TEXT,
  manager_name TEXT,
  members_count INTEGER,
  budget INTEGER,
  kpi TEXT,
  integrations TEXT,  -- JSON
  
  -- Step 3: Initial Task Execution
  initial_tasks TEXT,  -- JSON array
  agent_status TEXT,  -- 'created', 'activated', 'running'
  
  -- Metadata
  current_step INTEGER DEFAULT 0,
  completed_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (dept_id) REFERENCES departments(id)
);
```

---

## インテグレーション関連エンドポイント

### Salesforce Integration

`setup` エンドポイント内で `integrations.salesforce` が true の場合：
1. Salesforce API 認証情報を保存
2. 部署情報を Salesforce オブジェクトとして同期
3. TaskId を Salesforce Campaign ID にマッピング

### Slack Integration

タスク実行時に Slack 通知を送信：
```
#sales-channel に「リード発掘タスク開始」の投稿
```

---

## レートリミット・セキュリティ

- **レートリミット**: 1 ユーザーあたり 60 req/min
- **CORS**: オンボーディングドメイン許可
- **HTTPS Only**: 本番環境では HTTPS 必須

---

## トラブルシューティング

### Vision Input バリデーション失敗

```
Error: Vision input must be 10-500 characters
```

**原因**: vision_input が短すぎるか長すぎる
**対応**: 10-500 文字の日本語テキストを入力

### AI Suggestion が空で返ってくる

```
{
  "suggestions": []
}
```

**原因**: テンプレートデータベースが空、またはマッチスコアがすべて 0
**対応**: 
1. `workflow/services/template.py` でテンプレート登録状況を確認
2. AI スコアリングロジックをデバッグ

### Budget Validation Warning

```
{
  "status": "warning",
  "message": "予算がベンチマークを下回っています"
}
```

**対応**: ユーザーに予算増額を提案する（強制ではない）

---

## テストカバレッジ

| エンドポイント | ユニットテスト | 統合テスト | E2E テスト |
|---|---|---|---|
| /vision | ✅ | ✅ | ✅ |
| /suggest | ✅ | ✅ | ✅ |
| /initialize | ✅ | ✅ | ✅ |
| /setup | ✅ | ✅ | ✅ |
| /execute | ✅ | ✅ | ✅ |
| /complete | ✅ | ✅ | ✅ |

---

## 実装チェックリスト

- [x] ビジョン入力エンドポイント (/vision)
- [x] AI 提案取得エンドポイント (/suggest)
- [x] ビジョン + 提案一体エンドポイント (/initialize)
- [x] 詳細設定エンドポイント (/setup) + 予算検証
- [x] 初期タスク実行エンドポイント (/execute)
- [x] 完了確認エンドポイント (/complete)
- [x] 認証（Bearer Token）
- [x] エラーハンドリング
- [x] DB スキーマ
- [x] テスト（BDD + 統合テスト）

---

## 参考リンク

- 設計書: `docs/design/onboarding-flow.md`
- BDD テスト: `features/onboarding_e2e.feature`
- API テスト: `test_uat/test_onboarding_api.py`
- E2E テスト: `test_uat/test_onboarding_e2e.py`
- 実装: `dashboard/app.py` (line 5300-5700)
