# 自然言語→DAG変換 API・スキーマ設計書

**タスク ID**: #2757  
**フェーズ**: 設計フェーズ  
**作成日**: 2026-04-24  
**バージョン**: v1.0  
**対象**: Claude API 連携・KuzuDB グラフスキーマ統合

---

## 目次

1. [概要](#概要)
2. [自然言語入力インターフェース](#自然言語入力インターフェース)
3. [内部DAGスキーマ](#内部dagスキーマ)
4. [Claude API 連携仕様](#claude-api-連携仕様)
5. [REST API 設計](#rest-api-設計)
6. [テンプレート参照I/F](#テンプレート参照if)
7. [API仕様](#api仕様)
8. [KuzuDB グラフスキーマ](#kuzudb-グラフスキーマ)
9. [SQLite スキーマ拡張](#sqlite-スキーマ拡張)
10. [エラーハンドリング・バリデーション](#エラーハンドリングバリデーション)
11. [実装例](#実装例)

---

## 概要

### 背景

THEBRANCH ユーザーが **自然言語で業務フロー** を記述すると、システムが自動的に **DAG（有向非環グラフ）** に変換し、実行可能なワークフローを生成する。

**主な流れ:**
```
ユーザー入力（自然言語）
    ↓
Claude API（自然言語解析・DAG生成）
    ↓
構造化 JSON（ノード・エッジ定義）
    ↓
SQLite task_dependencies テーブル（保存）
    ↓
KuzuDB グラフマップ（可視化・解析）
    ↓
ワークフロー実行エンジン
```

### 主な要件

- ✅ 自然言語テキスト → 構造化 JSON DAG への自動変換
- ✅ Claude API による NLP・LLM ベースの推論
- ✅ 循環参照の自動検出・エラー報告
- ✅ ノード属性の推定（期間推定、優先度推定）
- ✅ グラフの妥当性検証（単一開始点・終了点）
- ✅ エラーメッセージの自然言語フィードバック

---

## 自然言語入力インターフェース

### 入力形式・制約

**入力テキストの仕様:**
- **最小長**: 10文字以上
- **最大長**: 10,000文字
- **言語**: 日本語・英語に対応
- **形式**: 自由形式テキスト（段落・箇条書き・表形式）

**推奨入力パターン:**

```
【フロー名】
プロダクトローンチフロー

【概要】
新機能をリリースするための標準的なフロー。
要件定義から本番リリースまでの全プロセス。

【詳細】
1. 要件定義（PM）- 3営業日
2. 設計・アーキテクチャ（Tech Lead）- 5営業日
3. 実装（Engineer）- 10営業日
4. テスト・品質保証（QA）- 5営業日
5. ステージング環境デプロイ（DevOps）- 1営業日
6. 本番リリース（DevOps）- 1営業日
```

**入力テキストの解析ポイント:**
- フェーズ名・タスク名の自動抽出
- 依存関係の推定（「の後に」「前に」「完了後」キーワード）
- 所要時間の推定（数値＋時間単位の抽出）
- 優先度の推定（重要度キーワード）
- ロール/担当者の推定（職種キーワード）

---

## 内部DAGスキーマ

### ノード定義（詳細）

```json
{
  "task_id": "t001",
  "name": "要件定義",
  "type": "task",
  "description": "プロダクト要件・スコープ確定",
  "estimated_duration_minutes": 480,
  "priority": "high",
  "role_hint": "pm",
  
  // 追加属性
  "source_text": "要件定義（PM）- 3営業日",
  "confidence_score": 0.95,
  "extracted_duration_original": "3営業日",
  "extracted_from_line": 5,
  "role_confidence": 0.98,
  "priority_signals": ["重要", "最初"],
  "phase_key": "planning"
}
```

### エッジ定義（詳細）

```json
{
  "from": "t001",
  "to": "t002",
  "type": "depends_on",
  "condition": null,
  
  // 追加属性
  "dependency_reason": "自然言語から推定：『の後に』",
  "inferred_from": "設計・アーキテクチャ（Tech Lead）- 5営業日 は 要件定義（PM）の後に実行",
  "confidence_score": 0.92,
  "parallel_possible": false
}
```

### DAG 構造の正規化

**正規化ルール:**
1. **ノードID の生成**: `t{001, 002, ...}` 形式で連番付与
2. **重複排除**: 同一名のノードを検出・マージ
3. **推移的閉包**: 明示的エッジから暗黙的エッジを検出
4. **レベル割り当て**: トポロジカルソート → layer 属性を付与

**正規化後の構造:**
```json
{
  "nodes": [
    {
      "task_id": "t001",
      "layer": 0,  // グラフレベル
      "level": 1,  // トポロジカルレベル
      "critical": true,  // クリティカルパス上
      ...
    }
  ],
  "edges": [...],
  "metadata": {
    "node_count": 5,
    "edge_count": 6,
    "max_depth": 4,
    "critical_path_duration": 4320,
    "is_normalized": true
  }
}
```

---

## Claude API 連携仕様

### 1. API モデル選択

**推奨モデル**: `claude-opus-4-7`（最高精度）/ `claude-sonnet-4-6`（バランス型）

**特徴:**
- JSON 出力フォーマットの確実性
- 複雑な依存関係の推論能力
- 日本語テキスト処理の堅牢性

### 2. Claude API リクエスト構造

```python
from anthropic import Anthropic

client = Anthropic()

# ユーザー自然言語入力を Claude に送信
prompt = """
以下の業務フロー説明から、実行可能なDAG（有向非環グラフ）を JSON 形式で生成してください。

【ユーザー入力】
{user_input}

【出力仕様】
JSON フォーマット（以下セクション "リクエスト・レスポンス仕様" を参照）で、以下を含む：
- nodes: タスク・ステップ・マイルストーン
- edges: タスク間の依存関係（depends_on）
- validation: 循環参照チェック結果

【制約】
- 循環参照がある場合は error_detected: true を設定
- 各ノードに task_id, name, description, estimated_duration_minutes, priority を指定
- エッジは {from: task_id, to: task_id, type: "depends_on"} 形式

回答は JSON のみ。余計な説明は不要です。
"""

response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    messages=[
        {"role": "user", "content": prompt}
    ]
)

dag_json = response.content[0].text
```

### 3. Prompt Caching 活用

**目的**: 繰り返し利用される スキーマ定義・バリデーションルール をキャッシュ

```python
# キャッシュ可能な System Prompt（共通スキーマ・ルール）
system_prompt = """
あなたは DAG 生成エキスパートです。

【出力スキーマ】
{
  "workflow": {
    "name": "string",
    "description": "string",
    "nodes": [
      {
        "task_id": "string",
        "name": "string",
        "type": "task|step|milestone",
        "description": "string",
        "estimated_duration_minutes": "int",
        "priority": "high|medium|low",
        "role_hint": "string (optional)"
      }
    ],
    "edges": [
      {
        "from": "task_id",
        "to": "task_id",
        "type": "depends_on",
        "condition": "string (optional, 条件付き依存)"
      }
    ],
    "validation": {
      "has_cycle": false,
      "cycle_nodes": [],
      "single_start": true,
      "single_end": true,
      "warnings": []
    }
  }
}

【バリデーションルール】
1. 循環参照チェック: DFS で全ノードを走査
2. 開始点: in_degree = 0 のノードが 1 つ
3. 終了点: out_degree = 0 のノードが 1 つ
4. 孤立ノード: 全ノードが開始点から到達可能か確認
"""

response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    system=[
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"}  # ← 5分間キャッシュ
        }
    ],
    messages=[
        {"role": "user", "content": f"【ユーザー入力】\n{user_input}"}
    ]
)
```

---

## REST API 設計

### API エンドポイント

#### 1. DAG 生成 API

```http
POST /api/v1/workflows/auto-generate
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "organization_id": "string",
  "natural_language_input": "string",
  "options": {
    "auto_estimate_duration": boolean (default: true),
    "enable_caching": boolean (default: true),
    "model": "claude-opus-4-7|claude-sonnet-4-6" (default: "sonnet-4-6")
  }
}
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "generation_id": "autogen-20260424-uuid",
    "workflow": {
      "name": "Product Launch Workflow",
      "description": "自動生成されたDAG: プロダクトローンチ",
      "nodes": [
        {
          "task_id": "t001",
          "name": "要件定義",
          "type": "task",
          "description": "プロダクト要件・スコープ確定",
          "estimated_duration_minutes": 480,
          "priority": "high",
          "role_hint": "pm"
        },
        {
          "task_id": "t002",
          "name": "設計・アーキテクチャ",
          "type": "task",
          "description": "技術設計・DB スキーマ設計",
          "estimated_duration_minutes": 960,
          "priority": "high",
          "role_hint": "tech_lead"
        },
        {
          "task_id": "t003",
          "name": "実装",
          "type": "task",
          "description": "プロダクト実装",
          "estimated_duration_minutes": 2880,
          "priority": "high",
          "role_hint": "engineer"
        },
        {
          "task_id": "m001",
          "name": "Alpha リリース",
          "type": "milestone",
          "description": "内部テスト版リリース",
          "estimated_duration_minutes": 0,
          "priority": "medium",
          "role_hint": "devops"
        }
      ],
      "edges": [
        {
          "from": "t001",
          "to": "t002",
          "type": "depends_on",
          "condition": null
        },
        {
          "from": "t002",
          "to": "t003",
          "type": "depends_on",
          "condition": null
        },
        {
          "from": "t003",
          "to": "m001",
          "type": "depends_on",
          "condition": "all_tests_passed"
        }
      ],
      "validation": {
        "has_cycle": false,
        "cycle_nodes": [],
        "single_start": true,
        "single_end": true,
        "warnings": []
      }
    },
    "metadata": {
      "generated_at": "2026-04-24T10:30:00Z",
      "model_used": "claude-sonnet-4-6",
      "prompt_tokens": 1250,
      "completion_tokens": 2840,
      "cache_hit": false
    }
  }
}
```

**エラーレスポンス** (400 Bad Request):

```json
{
  "success": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "自然言語入力が短すぎます（最小 10 文字）",
    "details": {
      "input_length": 5,
      "minimum_length": 10
    }
  }
}
```

---

## テンプレート参照I/F

### テンプレートベース DAG 生成 API

**目的**: 既存のワークフローテンプレートを参照して、ユーザー入力を該当テンプレートにマッピング。

```http
POST /api/v1/workflows/auto-generate-from-template
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "organization_id": "string",
  "natural_language_input": "string",
  "template_id": "integer (optional)",
  "auto_match_template": boolean (default: true),
  "options": {
    "model": "claude-opus-4-7|claude-sonnet-4-6"
  }
}
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "generation_id": "autogen-20260424-uuid",
    "matched_template": {
      "template_id": 1,
      "name": "Product Launch",
      "match_score": 0.87,
      "match_reason": "自然言語入力の『プロダクトローンチ』がテンプレート名と一致"
    },
    "workflow": {
      "name": "新機能ローンチ2026Q2",
      "nodes": [...],
      "edges": [...]
    },
    "customizations": {
      "added_nodes": ["t004_extra_qa"],
      "modified_nodes": ["t001_duration_extended"],
      "removed_nodes": []
    }
  }
}
```

### テンプレートマッピング戦略

**マッチング方式:**
1. **キーワード照合**: 入力テキストのキーワード ⟷ テンプレート名・説明
2. **セマンティック類似度**: ベクトル埋め込みで意味的相似性を計算
3. **構造的マッピング**: フェーズ数・タスク数・依存関係パターン
4. **信頼度スコア**: 0.0～1.0 の数値で マッチ品質を定量化

---

## API仕様

### エンドポイント一覧

| メソッド | エンドポイント | 説明 | 認証 |
|--------|--------|------|------|
| `POST` | `/api/v1/workflows/auto-generate` | 自然言語 → DAG 変換 | ✅ Bearer |
| `POST` | `/api/v1/workflows/auto-generate-from-template` | テンプレート参照で生成 | ✅ Bearer |
| `POST` | `/api/v1/workflows/validate-dag` | DAG バリデーション | ✅ Bearer |
| `POST` | `/api/v1/workflows/auto-fix-dag` | DAG 自動修正 | ✅ Bearer |
| `GET` | `/api/v1/workflows/autogen-history/{generation_id}` | 生成履歴取得 | ✅ Bearer |
| `PUT` | `/api/v1/workflows/autogen-history/{generation_id}` | 生成結果の承認/却下 | ✅ Bearer |

### 認証・認可

**認証方式**: OAuth 2.0 Bearer Token

```http
Authorization: Bearer {access_token}
```

**スコープ:**
- `workflow:read` — ワークフロー読み取り
- `workflow:write` — ワークフロー作成・更新
- `workflow:autogen` — 自動生成実行

### レート制限

| リソース | 制限 | リセット周期 |
|--------|------|----------|
| `/auto-generate` | 100リクエスト/日 | UTC 00:00 |
| `/validate-dag` | 1000リクエスト/日 | UTC 00:00 |
| 全体 | 10,000トークン/日 | UTC 00:00 |

### キャッシング戦略

**キャッシュ対象:**
- 入力テキスト（256字以上）→ 7日間キャッシュ
- テンプレートマッピング結果 → 30日間キャッシュ
- バリデーション結果 → 1日間キャッシュ

**キャッシュキー生成:**
```python
import hashlib
cache_key = hashlib.sha256(
  f"{user_id}:{organization_id}:{input_hash}".encode()
).hexdigest()
```

---

#### 2. DAG バリデーション API

```http
POST /api/v1/workflows/validate-dag
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "nodes": [...],
  "edges": [...]
}
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "validation_result": {
      "is_valid": false,
      "errors": [
        {
          "type": "CIRCULAR_DEPENDENCY",
          "severity": "error",
          "message": "循環参照を検出: t001 → t002 → t003 → t001",
          "affected_nodes": ["t001", "t002", "t003"],
          "suggestion": "t003 → t001 の依存関係を削除してください"
        }
      ],
      "warnings": [
        {
          "type": "MULTIPLE_START_NODES",
          "severity": "warning",
          "message": "開始ノードが複数存在: t001, t004",
          "affected_nodes": ["t001", "t004"],
          "suggestion": "1つの開始点に統合することを検討してください"
        }
      ],
      "statistics": {
        "total_nodes": 5,
        "total_edges": 6,
        "critical_path_length": 4,
        "critical_path_duration_minutes": 4320
      }
    }
  }
}
```

---

#### 3. 自動修正 API（バージョン 2）

```http
POST /api/v1/workflows/auto-fix-dag
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "nodes": [...],
  "edges": [...],
  "strategy": "remove_latest_edge|merge_nodes|split_workflow"
}
```

---

## リクエスト・レスポンス仕様

### JSON スキーマ定義

#### DAG ノード型定義

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DAG Node",
  "type": "object",
  "properties": {
    "task_id": {
      "type": "string",
      "pattern": "^[a-z0-9]{1,32}$",
      "description": "ノード一意識別子（小文字英数字、最大32文字）"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 200,
      "description": "ノード表示名"
    },
    "type": {
      "type": "string",
      "enum": ["task", "step", "milestone"],
      "description": "ノード型: task=実行可能タスク, step=サブステップ, milestone=マイルストーン"
    },
    "description": {
      "type": "string",
      "maxLength": 1000,
      "description": "詳細説明"
    },
    "estimated_duration_minutes": {
      "type": "integer",
      "minimum": 0,
      "maximum": 525600,
      "description": "推定所要時間（分）"
    },
    "priority": {
      "type": "string",
      "enum": ["high", "medium", "low"],
      "description": "優先度"
    },
    "role_hint": {
      "type": "string",
      "enum": ["pm", "tech_lead", "engineer", "qa", "devops", "orchestrator"],
      "description": "推奨ロール（未確定）"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "分類タグ（オプション）"
    }
  },
  "required": ["task_id", "name", "type", "description", "estimated_duration_minutes", "priority"]
}
```

#### DAG エッジ型定義

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DAG Edge",
  "type": "object",
  "properties": {
    "from": {
      "type": "string",
      "pattern": "^[a-z0-9]{1,32}$",
      "description": "依存元タスク ID"
    },
    "to": {
      "type": "string",
      "pattern": "^[a-z0-9]{1,32}$",
      "description": "依存先タスク ID"
    },
    "type": {
      "type": "string",
      "enum": ["depends_on", "blocks", "triggers"],
      "description": "依存関係型"
    },
    "condition": {
      "type": "string",
      "description": "条件付き依存（e.g., 'all_tests_passed'）"
    }
  },
  "required": ["from", "to", "type"]
}
```

---

## KuzuDB グラフスキーマ

### ノード型定義

```cypher
CREATE NODE TABLE IF NOT EXISTS Task (
  task_id STRING PRIMARY KEY,
  name STRING NOT NULL,
  description STRING,
  type STRING,  -- 'task', 'step', 'milestone'
  estimated_duration_minutes INTEGER,
  priority STRING,  -- 'high', 'medium', 'low'
  role_hint STRING,
  status STRING DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'blocked'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  workflow_instance_id STRING
);

CREATE NODE TABLE IF NOT EXISTS Milestone (
  milestone_id STRING PRIMARY KEY,
  name STRING NOT NULL,
  description STRING,
  status STRING DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE NODE TABLE IF NOT EXISTS Phase (
  phase_id STRING PRIMARY KEY,
  name STRING NOT NULL,
  description STRING,
  sequence INTEGER,
  status STRING DEFAULT 'pending'
);
```

### エッジ型定義

```cypher
CREATE REL TABLE IF NOT EXISTS depends_on (
  FROM Task TO Task,
  condition STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE REL TABLE IF NOT EXISTS blocks (
  FROM Task TO Task,
  reason STRING
);

CREATE REL TABLE IF NOT EXISTS part_of (
  FROM Task TO Phase
);

CREATE REL TABLE IF NOT EXISTS leads_to_milestone (
  FROM Phase TO Milestone
);
```

### クエリ例

#### 循環参照検出

```cypher
-- 循環参照を含むパスを検出
MATCH (t1:Task)-[:depends_on*2..]->(t1:Task)
RETURN t1.task_id AS node_in_cycle;
```

#### クリティカルパス計算

```cypher
-- 最長パスを検出（CPM: Critical Path Method）
MATCH (start:Task {status: 'pending'})
WHERE NOT EXISTS {
  MATCH (other:Task)-[:depends_on]->(start)
}
MATCH path = (start)-[:depends_on*]->(end:Task)
WHERE NOT EXISTS {
  MATCH (end)-[:depends_on]->(:Task)
}
RETURN 
  [node in nodes(path) | node.task_id] AS critical_path,
  REDUCE(sum = 0, node in nodes(path) | sum + node.estimated_duration_minutes) AS total_duration
ORDER BY total_duration DESC
LIMIT 1;
```

#### 依存タスク一覧取得

```cypher
MATCH (parent:Task {task_id: 't001'})-[:depends_on]->(child:Task)
RETURN child.task_id, child.name, child.estimated_duration_minutes
ORDER BY child.priority DESC;
```

---

## SQLite スキーマ拡張

### テーブル: task_dependencies（拡張）

```sql
CREATE TABLE IF NOT EXISTS task_dependencies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  
  -- 基本情報
  predecessor_id INTEGER NOT NULL REFERENCES dev_tasks(id) ON DELETE CASCADE,
  successor_id INTEGER NOT NULL REFERENCES dev_tasks(id) ON DELETE CASCADE,
  
  -- 依存関係型
  dep_type TEXT NOT NULL CHECK(dep_type IN ('depends_on', 'blocks', 'triggers')) DEFAULT 'depends_on',
  
  -- 条件付き実行
  condition TEXT,  -- e.g., 'all_tests_passed', 'manual_approval'
  
  -- メタデータ
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by TEXT,
  
  -- 生成元情報
  generated_from_ai BOOLEAN DEFAULT 0,  -- Claude API 生成の場合 1
  generation_id TEXT,  -- autogen-YYYYMMDD-uuid
  
  UNIQUE(predecessor_id, successor_id),
  FOREIGN KEY (generation_id) REFERENCES autogen_history(generation_id)
);

CREATE INDEX idx_task_dependencies_pred ON task_dependencies(predecessor_id);
CREATE INDEX idx_task_dependencies_succ ON task_dependencies(successor_id);
CREATE INDEX idx_task_dependencies_gen ON task_dependencies(generation_id);
```

### テーブル: autogen_history（新規）

```sql
CREATE TABLE IF NOT EXISTS autogen_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  generation_id TEXT NOT NULL UNIQUE,
  
  -- 生成情報
  organization_id TEXT NOT NULL,
  workflow_instance_id INTEGER REFERENCES workflow_instances(id) ON DELETE SET NULL,
  user_id TEXT NOT NULL,
  
  -- 入力・出力
  natural_language_input TEXT NOT NULL,
  generated_dag_json TEXT NOT NULL,
  
  -- Claude API 情報
  model_used TEXT NOT NULL,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  cache_hit BOOLEAN DEFAULT 0,
  
  -- 検証結果
  is_valid BOOLEAN NOT NULL,
  validation_errors TEXT,  -- JSON array
  
  -- 承認フロー
  status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'modified')),
  approved_by TEXT,
  approved_at TEXT,
  notes TEXT,
  
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_autogen_history_org ON autogen_history(organization_id);
CREATE INDEX idx_autogen_history_instance ON autogen_history(workflow_instance_id);
CREATE INDEX idx_autogen_history_status ON autogen_history(status);
```

---

## エラーハンドリング・バリデーション

### バリデーション層（多層防御）

**レイヤー 1: 入力バリデーション**
```
自然言語入力 → 長さチェック → 文字エンコーディング確認 → 禁止キーワード検出
```

**レイヤー 2: Claude API レスポンスバリデーション**
```
JSON デコード → スキーマ検証 → 必須フィールド確認 → データ型チェック
```

**レイヤー 3: DAG 構造バリデーション**
```
ノード重複チェック → エッジ参照チェック → 循環参照検出 → グラフ接続性チェック
```

**レイヤー 4: ビジネスロジックバリデーション**
```
組織権限チェック → テンプレート互換性確認 → リソース容量チェック
```

### エラーコード一覧

| コード | HTTP | 説明 | 対応 |
|--------|------|------|------|
| `INVALID_INPUT` | 400 | 入力テキストが不正（長さ不足など） | 入力値を確認・再試行 |
| `PARSING_ERROR` | 400 | 自然言語解析失敗 | テキスト形式を改善 |
| `CIRCULAR_DEPENDENCY` | 422 | 循環参照を検出 | DAG 構造を修正 |
| `INVALID_NODES` | 422 | ノード定義が無効 | スキーマに従う |
| `INVALID_EDGES` | 422 | エッジ定義が無効（参照先不在） | エッジを修正 |
| `MULTIPLE_START_NODES` | 422 | 開始ノードが複数 | 構造を統合 |
| `MULTIPLE_END_NODES` | 422 | 終了ノードが複数 | 構造を統合 |
| `ISOLATED_NODES` | 422 | 孤立ノードが存在 | 依存関係を追加 |
| `API_RATE_LIMIT` | 429 | Claude API レート制限 | 後で再試行 |
| `API_ERROR` | 502 | Claude API エラー | 後で再試行 |
| `INTERNAL_ERROR` | 500 | 内部エラー | サポートに連絡 |

### バリデーション関数（Python）

```python
def validate_dag(nodes: list[dict], edges: list[dict]) -> dict:
    """
    DAG 妥当性チェック
    
    Returns:
        {
            "is_valid": bool,
            "errors": list[dict],
            "warnings": list[dict]
        }
    """
    errors = []
    warnings = []
    
    # 1. ノード ID 重複チェック
    node_ids = [n['task_id'] for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append({
            "type": "DUPLICATE_NODE_IDS",
            "message": "ノード ID が重複しています"
        })
    
    # 2. エッジ参照チェック
    node_id_set = set(node_ids)
    for edge in edges:
        if edge['from'] not in node_id_set:
            errors.append({
                "type": "INVALID_EDGES",
                "message": f"参照先ノードが不在: {edge['from']}"
            })
        if edge['to'] not in node_id_set:
            errors.append({
                "type": "INVALID_EDGES",
                "message": f"参照先ノードが不在: {edge['to']}"
            })
    
    if errors:
        return {"is_valid": False, "errors": errors, "warnings": warnings}
    
    # 3. 循環参照チェック（DFS）
    graph = defaultdict(list)
    for edge in edges:
        graph[edge['from']].append(edge['to'])
    
    cycle = find_cycle_dfs(graph)
    if cycle:
        errors.append({
            "type": "CIRCULAR_DEPENDENCY",
            "message": f"循環参照: {' → '.join(cycle)}",
            "affected_nodes": cycle
        })
        return {"is_valid": False, "errors": errors, "warnings": warnings}
    
    # 4. 開始点・終了点チェック
    in_degrees = {nid: 0 for nid in node_ids}
    out_degrees = {nid: 0 for nid in node_ids}
    for edge in edges:
        in_degrees[edge['to']] += 1
        out_degrees[edge['from']] += 1
    
    start_nodes = [nid for nid, deg in in_degrees.items() if deg == 0]
    end_nodes = [nid for nid, deg in out_degrees.items() if deg == 0]
    
    if len(start_nodes) != 1:
        warnings.append({
            "type": "MULTIPLE_START_NODES" if len(start_nodes) > 1 else "NO_START_NODE",
            "message": f"開始ノード数: {len(start_nodes)} (期待値: 1)",
            "affected_nodes": start_nodes
        })
    
    if len(end_nodes) != 1:
        warnings.append({
            "type": "MULTIPLE_END_NODES" if len(end_nodes) > 1 else "NO_END_NODE",
            "message": f"終了ノード数: {len(end_nodes)} (期待値: 1)",
            "affected_nodes": end_nodes
        })
    
    # 5. 孤立ノードチェック
    if start_nodes:
        reachable = _get_reachable_nodes(start_nodes[0], graph)
        isolated = [nid for nid in node_ids if nid not in reachable]
        if isolated:
            warnings.append({
                "type": "ISOLATED_NODES",
                "message": f"孤立ノード: {isolated}",
                "affected_nodes": isolated
            })
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }
```

---

## 実装例

### Python バックエンド（Flask）

```python
from flask import Blueprint, request, jsonify
from anthropic import Anthropic
import json
from datetime import datetime

bp = Blueprint('autogen', __name__, url_prefix='/api/v1/workflows')

@bp.route('/auto-generate', methods=['POST'])
def auto_generate_dag():
    """自然言語 → DAG 変換 API"""
    
    try:
        data = request.get_json()
        user_input = data.get('natural_language_input', '').strip()
        
        # 入力バリデーション
        if not user_input or len(user_input) < 10:
            return jsonify({
                "success": False,
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "入力テキストが短すぎます（最小 10 文字）",
                    "details": {"input_length": len(user_input)}
                }
            }), 400
        
        # Claude API 呼び出し
        client = Anthropic()
        system_prompt = _get_dag_system_prompt()
        
        response = client.messages.create(
            model=data.get('model', 'claude-sonnet-4-6'),
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"【ユーザー入力】\n{user_input}"
                }
            ]
        )
        
        # レスポンス解析
        dag_json = json.loads(response.content[0].text)
        
        # バリデーション
        validation_result = validate_dag(
            dag_json['workflow']['nodes'],
            dag_json['workflow']['edges']
        )
        dag_json['workflow']['validation'] = validation_result
        
        # 生成履歴保存
        generation_id = f"autogen-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        _save_autogen_history(
            generation_id=generation_id,
            organization_id=data.get('organization_id'),
            user_input=user_input,
            generated_dag_json=json.dumps(dag_json),
            model_used=response.model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            is_valid=not validation_result['errors'],
            validation_errors=json.dumps(validation_result['errors'])
        )
        
        return jsonify({
            "success": True,
            "data": {
                "generation_id": generation_id,
                "workflow": dag_json['workflow'],
                "metadata": {
                    "generated_at": datetime.utcnow().isoformat() + 'Z',
                    "model_used": response.model,
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "cache_hit": "cache_read_input_tokens" in response.usage
                }
            }
        }), 200
    
    except json.JSONDecodeError:
        return jsonify({
            "success": False,
            "error": {
                "code": "PARSING_ERROR",
                "message": "Claude API レスポンスが無効な JSON です"
            }
        }), 400
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        }), 500


@bp.route('/validate-dag', methods=['POST'])
def validate_dag_endpoint():
    """DAG バリデーション API"""
    
    data = request.get_json()
    nodes = data.get('nodes', [])
    edges = data.get('edges', [])
    
    validation_result = validate_dag(nodes, edges)
    
    # クリティカルパス計算
    critical_path = _compute_critical_path(nodes, edges)
    
    return jsonify({
        "success": True,
        "data": {
            "validation_result": validation_result,
            "statistics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "critical_path_length": len(critical_path) if critical_path else 0,
                "critical_path_duration_minutes": sum(
                    next((n['estimated_duration_minutes'] for n in nodes if n['task_id'] == t), 0)
                    for t in critical_path or []
                )
            }
        }
    }), 200
```

---

## 実装チェックリスト

- [ ] Claude API リクエスト実装（Anthropic SDK）
- [ ] DAG JSON スキーマ定義（JSON Schema）
- [ ] バリデーション関数（DFS サイクル検出）
- [ ] REST API エンドポイント実装（Flask）
- [ ] SQLite `autogen_history` テーブル実装
- [ ] KuzuDB ノード・エッジ型定義
- [ ] エラーハンドリング実装
- [ ] 単体テスト（pytest）
- [ ] E2E テスト（Gherkin BDD）
- [ ] ドキュメント・API リファレンス整備

---

## 参考資料

- [Claude API - Messages](https://docs.anthropic.com/messages)
- [Prompt Caching - 最適化](https://docs.anthropic.com/cache)
- [KuzuDB - Cypher Query Language](https://kuzudb.com/docs/cypher/)
- [JSON Schema Draft 7](https://json-schema.org/draft-07/)
- [Critical Path Method - CPM](https://en.wikipedia.org/wiki/Critical_path_method)
