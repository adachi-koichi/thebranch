# タスク #2242 実装ガイド - ワークフローテンプレート機能

**期限**: 2026-04-20
**チーム**: 3 Engineer + Design Support

## 実装概要

THEBRANCH の「部署」に割り当て可能なワークフローテンプレートを実装する。
定型業務（月次レポート、採用プロセス、法務確認フロー）をテンプレート化し、AIエージェントが自動実行できるようにする。

---

## DB スキーマ

### workflow_templates テーブル

```sql
CREATE TABLE workflow_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  department_type TEXT NOT NULL,  -- 'accounting', 'legal', 'hr'
  name TEXT NOT NULL,
  description TEXT,
  steps_json TEXT NOT NULL,  -- JSON array: [{order, action, description}, ...]
  status TEXT DEFAULT 'active',  -- 'active', 'archived'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**マイグレーション**: `dashboard/migrations/007_create_workflow_templates_table.sql`

---

## API エンドポイント

### 1. GET /api/workflow-templates
**説明**: テンプレート一覧取得
**Query Params**: 
  - `department_type` (optional): フィルタ (accounting, legal, hr)
  - `status` (optional): ステータス (active, archived)

**Response** (200):
```json
[
  {
    "id": 1,
    "department_type": "accounting",
    "name": "月次帳票生成フロー",
    "description": "毎月の財務レポート生成プロセス",
    "steps": [
      {"order": 1, "action": "collect_invoices", "description": "請求書データ収集"},
      {"order": 2, "action": "generate_ledger", "description": "仕訳帳生成"},
      {"order": 3, "action": "create_report", "description": "財務レポート作成"}
    ],
    "status": "active",
    "created_at": "2026-04-20T17:30:00"
  }
]
```

### 2. POST /api/workflow-templates
**説明**: テンプレート作成
**Request**:
```json
{
  "department_type": "legal",
  "name": "契約書レビューフロー",
  "description": "新規契約書レビュープロセス",
  "steps_json": "[{\"order\": 1, \"action\": \"upload\", \"description\": \"契約書アップロード\"}, ...]"
}
```

**Response** (201):
```json
{
  "id": 2,
  "department_type": "legal",
  "name": "契約書レビューフロー",
  ...
}
```

### 3. POST /api/departments/{id}/workflows
**説明**: 部署にワークフローテンプレートを割り当て
**Request**:
```json
{
  "template_id": 1
}
```

**Response** (200):
```json
{
  "success": true,
  "message": "ワークフローテンプレートを割り当てました",
  "department_id": 5,
  "template_id": 1
}
```

---

## フロントエンド UI

### ページ: `/dashboard/#/workflow-templates`

#### セクション 1: テンプレートライブラリ
- テンプレート一覧（テーブル形式）
- カラム: ID, Department Type, Name, Description, Status, Actions
- フィルタ: By Department Type

#### セクション 2: テンプレート作成フォーム
- Input: Department Type (Dropdown)
- Input: Name, Description
- Input: Steps (JSON Editor または Step Editor UI)
- Button: Create Template

#### セクション 3: 部署への割り当て
- Select Department
- Select Template
- Button: Assign Workflow

---

## プリセットテンプレート（3種類）

### 1. 経理部 - 月次帳票生成フロー
```json
{
  "department_type": "accounting",
  "name": "月次帳票生成フロー",
  "description": "毎月の財務レポート生成プロセス",
  "steps": [
    {"order": 1, "action": "collect_invoices", "description": "請求書データ収集"},
    {"order": 2, "action": "generate_ledger", "description": "仕訳帳生成"},
    {"order": 3, "action": "create_report", "description": "財務レポート作成"}
  ]
}
```

### 2. 法務部 - 契約書レビューフロー
```json
{
  "department_type": "legal",
  "name": "契約書レビューフロー",
  "description": "新規契約書レビュープロセス",
  "steps": [
    {"order": 1, "action": "upload_contract", "description": "契約書アップロード"},
    {"order": 2, "action": "analyze_risk", "description": "リスク分析"},
    {"order": 3, "action": "add_comments", "description": "レビューコメント追加"}
  ]
}
```

### 3. 人事部 - 採用選考フロー
```json
{
  "department_type": "hr",
  "name": "採用選考フロー",
  "description": "採用選考プロセス管理",
  "steps": [
    {"order": 1, "action": "document_review", "description": "書類審査"},
    {"order": 2, "action": "interview_eval", "description": "面接評価"},
    {"order": 3, "action": "decision", "description": "採用決定"}
  ]
}
```

---

## 実装チェックリスト

### バックエンド (Engineer A - pane 1)
- [ ] `dashboard/app.py` に API エンドポイント追加
  - [ ] GET /api/workflow-templates
  - [ ] POST /api/workflow-templates
  - [ ] POST /api/departments/{id}/workflows
- [ ] Pydantic モデル定義 (WorkflowTemplate, WorkflowTemplateCreate)
- [ ] DB クエリ実装

### DB & マイグレーション (Engineer A または pane 0)
- [ ] `dashboard/migrations/007_create_workflow_templates_table.sql` 作成
- [ ] migration 実行確認

### フロントエンド UI (Engineer B - pane 2)
- [ ] `/dashboard/#/workflow-templates` ページ作成
- [ ] テンプレートライブラリ表示
- [ ] テンプレート作成フォーム
- [ ] 部署への割り当てUI

### プリセット登録 (Engineer A または Engineer C)
- [ ] 3 種類のプリセットテンプレートを API または SQL で登録

### テスト & 確認 (All)
- [ ] API テスト（curl / Postman）
- [ ] E2E テスト実装
- [ ] ブラウザ確認: http://localhost:8503
- [ ] プリセットテンプレートが表示されることを確認

---

## 実装順序（推奨）

1. **設計・DB マイグレーション** (pane 0)
   - workflow_templates テーブル定義
   - 007_create_workflow_templates_table.sql 実装
   - migration 実行

2. **バックエンド API 実装** (pane 1 - 並行)
   - エンドポイント実装
   - Pydantic モデル
   - DB クエリ

3. **フロントエンド UI 実装** (pane 2 - 並行)
   - HTML/CSS/JS
   - API 連携

4. **プリセット登録** (pane 0 or 1)
   - 3 種類のテンプレート登録

5. **テスト & 確認** (All)
   - API テスト
   - UI テスト
   - ブラウザ確認

---

## 完了条件

- [ ] `GET /api/workflow-templates` でテンプレート一覧が取得できる
- [ ] `POST /api/workflow-templates` で新規テンプレートが作成できる
- [ ] `POST /api/departments/{id}/workflows` で部署にテンプレートを割り当てられる
- [ ] http://localhost:8503 でUI が表示される
- [ ] プリセットテンプレート 3 種類が登録されている
- [ ] E2E テスト実装済み

---

## 参考

- 既存 API: `dashboard/app.py` lines 3448+（部署 API）
- テスト用コマンド: `curl -X GET http://localhost:8000/api/workflow-templates`
