# 設計仕様書 #2784: 部署エージェント設定・デプロイUI実装

**タイトル**: 部署エージェント設定・デプロイUI実装（部署タイプ選択・AIエージェント起動制御）  
**期限**: 2026-04-26 15分以内  
**ステータス**: Tech Lead 設計完了  
**次フェーズ**: Engineer 実装フェーズ

---

## 1. 全体構成

```
部署設定フロー
├─ 部署タイプ選択 UI
│  ├─ department_type: 'sales', 'engineering', 'marketing'
│  └─ 部署別テンプレート表示
├─ エージェント起動制御 UI
│  ├─ Start/Stop ボタン
│  ├─ ステータス表示（running, stopped, failed）
│  └─ ログビューア
└─ APIエンドポイント群
   ├─ POST /api/departments/deploy
   ├─ POST /api/agents/start
   ├─ POST /api/agents/stop
   └─ GET /api/departments/<id>/agent-status
```

---

## 2. データベーススキーマ

### Migration 034: 部署タイプ・デプロイ設定テーブル

```sql
-- 部署タイプマスタ
CREATE TABLE IF NOT EXISTS department_types (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type_key      TEXT NOT NULL UNIQUE,
    type_label    TEXT NOT NULL,
    description   TEXT,
    icon_url      TEXT,
    default_roles TEXT,  -- JSON: ["manager", "engineer", "analyst"]
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 初期データ
INSERT INTO department_types (type_key, type_label, description, default_roles, is_active) VALUES
('sales', '営業部', '営業・顧客獲得部門', '["sales_manager", "sales_rep", "customer_success"]', 1),
('engineering', 'エンジニアリング部', '開発・技術部門', '["engineering_lead", "backend_engineer", "frontend_engineer"]', 1),
('marketing', 'マーケティング部', 'マーケティング・ブランド部門', '["marketing_director", "campaign_manager", "content_creator"]', 1);

-- エージェントデプロイ設定
CREATE TABLE IF NOT EXISTS agent_deploy_configs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id         INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    department_type_id    INTEGER NOT NULL REFERENCES department_types(id),
    agent_name            TEXT NOT NULL,
    agent_role            TEXT NOT NULL,
    deploy_status         TEXT DEFAULT 'pending',
    config_json           TEXT,  -- {"model": "claude-sonnet-4-6", "temperature": 0.7, ...}
    deployed_at           TEXT,
    stopped_at            TEXT,
    error_log             TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    CHECK(deploy_status IN ('pending', 'deploying', 'running', 'stopping', 'stopped', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_agent_deploy_dept_id ON agent_deploy_configs(department_id);
CREATE INDEX IF NOT EXISTS idx_agent_deploy_status ON agent_deploy_configs(deploy_status);
```

---

## 3. API エンドポイント仕様

### 3.1 部署タイプ一覧取得

```
GET /api/departments/types
```

**レスポンス:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "type_key": "sales",
      "type_label": "営業部",
      "description": "営業・顧客獲得部門",
      "icon_url": "/icons/sales.svg",
      "default_roles": ["sales_manager", "sales_rep"],
      "is_active": 1
    },
    {
      "id": 2,
      "type_key": "engineering",
      "type_label": "エンジニアリング部",
      "description": "開発・技術部門",
      "icon_url": "/icons/engineering.svg",
      "default_roles": ["engineering_lead", "backend_engineer"],
      "is_active": 1
    }
  ]
}
```

### 3.2 部署作成（タイプ選択）

```
POST /api/departments/deploy
```

**リクエスト:**
```json
{
  "department_name": "東京営業チーム",
  "department_type_id": 1,
  "manager_name": "田中太郎",
  "monthly_budget": 500000,
  "team_size": 5
}
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "department_id": 42,
    "department_name": "東京営業チーム",
    "department_type": "sales",
    "message": "部署を作成しました。エージェント起動に進んでください。"
  }
}
```

### 3.3 エージェント起動

```
POST /api/agents/start
```

**リクエスト:**
```json
{
  "department_id": 42,
  "agent_role": "sales_manager",
  "agent_name": "Aiko-Sales-Manager",
  "config": {
    "model": "claude-sonnet-4-6",
    "temperature": 0.7,
    "max_tokens": 4096
  }
}
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "agent_id": 123,
    "agent_name": "Aiko-Sales-Manager",
    "deploy_config_id": 456,
    "status": "deploying",
    "session_id": "sales_orchestrator_wf001_tokyo-sales@main",
    "message": "エージェント起動を開始しました。"
  }
}
```

### 3.4 エージェント停止

```
POST /api/agents/stop
```

**リクエスト:**
```json
{
  "agent_id": 123
}
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "agent_id": 123,
    "status": "stopped",
    "stopped_at": "2026-04-26T15:30:00+09:00",
    "message": "エージェントを停止しました。"
  }
}
```

### 3.5 エージェント状態確認

```
GET /api/departments/<id>/agent-status
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "department_id": 42,
    "agents": [
      {
        "agent_id": 123,
        "agent_name": "Aiko-Sales-Manager",
        "agent_role": "sales_manager",
        "status": "running",
        "deployed_at": "2026-04-26T15:20:00+09:00",
        "session_id": "sales_orchestrator_wf001_tokyo-sales@main"
      }
    ],
    "summary": {
      "total_agents": 1,
      "running_agents": 1,
      "stopped_agents": 0,
      "failed_agents": 0
    }
  }
}
```

---

## 4. UI コンポーネント構成図

### 4.1 ページ構成（HTML + JS）

```
dashboard/index.html
├─ Navigation
│  └─ "部署設定" / "エージェント管理" タブ
├─ Main Content
│  ├─ Section 1: 部署タイプ選択
│  │  ├─ Card Grid (3 列)
│  │  │  ├─ Card: 営業部 (Sales)
│  │  │  ├─ Card: エンジニアリング部 (Engineering)
│  │  │  └─ Card: マーケティング部 (Marketing)
│  │  └─ 各カード: アイコン + 説明 + 「選択」ボタン
│  ├─ Section 2: 部署情報入力
│  │  ├─ 部署名 (text input)
│  │  ├─ マネージャー名 (text input)
│  │  ├─ 月次予算 (number input)
│  │  ├─ チームサイズ (number input)
│  │  └─ 「作成」ボタン
│  └─ Section 3: エージェント起動制御
│     ├─ エージェント一覧テーブル
│     │  ├─ エージェント名
│     │  ├─ ロール
│     │  ├─ ステータス表示（ヒートマップ色）
│     │  ├─ Start/Stop ボタン
│     │  └─ 詳細ログボタン
│     └─ ログビューア（折りたたみ可能）
└─ Footer: 操作ガイド
```

### 4.2 コンポーネント詳細

#### 部署タイプセレクターカード

```html
<div class="department-type-card" data-type="sales">
  <img src="/icons/sales.svg" alt="Sales" class="card-icon">
  <h3>営業部</h3>
  <p>営業・顧客獲得部門</p>
  <button class="btn-select">選択</button>
</div>
```

#### エージェント制御パネル

```html
<div class="agent-control-panel" data-agent-id="123">
  <div class="agent-info">
    <span class="agent-name">Aiko-Sales-Manager</span>
    <span class="agent-role">sales_manager</span>
  </div>
  <div class="agent-status-badge" data-status="running">
    ● Running
  </div>
  <button class="btn-stop" data-action="stop">停止</button>
  <button class="btn-logs" data-action="logs">ログ</button>
  <div class="agent-logs" style="display:none;">
    <pre id="logs-output"></pre>
  </div>
</div>
```

#### ステータス表示（カラーマップ）

| ステータス | 色      | アイコン |
|-----------|--------|---------|
| running   | 🟢 緑  | ●       |
| deploying | 🟡 黄  | ⟳       |
| stopped   | ⚫ 灰  | ◆       |
| failed    | 🔴 赤  | ✕       |

---

## 5. JavaScript 実装モジュール

### 5.1 モジュール構成（js/departmentDeploy.js）

```javascript
// 部署タイプ選択管理
class DepartmentTypeSelector {
  constructor() { }
  fetchTypes() { }
  selectType(typeId) { }
  renderCards(types) { }
}

// 部署デプロイ管理
class DepartmentDeployer {
  constructor() { }
  createDepartment(data) { }
  validateInput(data) { }
  submitForm(data) { }
}

// エージェント制御管理
class AgentController {
  constructor() { }
  startAgent(departmentId, agentRole, config) { }
  stopAgent(agentId) { }
  checkStatus(departmentId) { }
  pollStatus(departmentId, interval = 3000) { }
  renderAgentList(agents) { }
  displayLogs(agentId, logs) { }
}

// ステータスビジュアライザー
class StatusVisualizer {
  constructor() { }
  getStatusColor(status) { }
  getStatusIcon(status) { }
  renderStatusBadge(status) { }
  animateDeploying(element) { }
}
```

---

## 6. Pydantic モデル（models.py 追加分）

```python
class DepartmentTypeResponse(BaseModel):
    id: int
    type_key: str
    type_label: str
    description: Optional[str]
    icon_url: Optional[str]
    default_roles: List[str]
    is_active: int

class DepartmentDeployRequest(BaseModel):
    department_name: str
    department_type_id: int
    manager_name: str
    monthly_budget: int
    team_size: int

class DepartmentDeployResponse(BaseModel):
    department_id: int
    department_name: str
    department_type: str
    message: str

class AgentStartRequest(BaseModel):
    department_id: int
    agent_role: str
    agent_name: str
    config: Optional[dict] = None

class AgentStartResponse(BaseModel):
    agent_id: int
    agent_name: str
    deploy_config_id: int
    status: str
    session_id: str
    message: str

class AgentStopRequest(BaseModel):
    agent_id: int

class AgentStatusResponse(BaseModel):
    agent_id: int
    agent_name: str
    agent_role: str
    status: str
    deployed_at: Optional[str]
    session_id: Optional[str]

class DepartmentAgentStatusResponse(BaseModel):
    department_id: int
    agents: List[AgentStatusResponse]
    summary: dict
```

---

## 7. Flask ルート設計（dashboard/app.py）

```python
# 部署タイプ一覧
@app.route('/api/departments/types', methods=['GET'])
def get_department_types():
    # SELECT * FROM department_types WHERE is_active = 1
    pass

# 部署作成
@app.route('/api/departments/deploy', methods=['POST'])
def deploy_department():
    # INSERT INTO departments, agent_deploy_configs
    # trigger: エージェント起動コマンド生成
    pass

# エージェント起動
@app.route('/api/agents/start', methods=['POST'])
def start_agent():
    # INSERT INTO agents, agent_deploy_configs
    # trigger: tmux セッション起動 + status polling
    pass

# エージェント停止
@app.route('/api/agents/stop', methods=['POST'])
def stop_agent():
    # UPDATE agents SET status = 'stopped'
    # trigger: tmux kill-session / kill-pane
    pass

# エージェント状態確認
@app.route('/api/departments/<int:dept_id>/agent-status', methods=['GET'])
def get_agent_status(dept_id):
    # SELECT * FROM agents WHERE department_id = dept_id
    pass
```

---

## 8. 実装順序（Engineer 向け）

### Phase 1: DB + Models
1. Migration 034 作成（department_types, agent_deploy_configs）
2. Pydantic モデル追加（models.py）
3. DB初期化スクリプト

### Phase 2: Backend API
1. department_types エンドポイント
2. departments/deploy エンドポイント
3. agents/start, agents/stop エンドポイント
4. departments/<id>/agent-status エンドポイント

### Phase 3: Frontend UI
1. index.html レイアウト追加
2. departmentDeploy.js 実装
3. rbac.js との統合
4. スタイル調整（CSS）

### Phase 4: 統合テスト
1. E2E テスト（部署作成 → エージェント起動）
2. エラーハンドリング
3. ログ・ステータス表示

---

## 9. 依存関係・制約

### 既存との整合性
- agents テーブル（006_create_agents_table.sql）との統合
- departments テーブルとの FK 参照
- RBAC（031_rbac_default_roles.sql）との権限確認

### セキュリティ
- 認証: REQUIRED（Bearer token）
- 認可: RBAC チェック（manager, owner 以上）
- バリデーション: 部署タイプID・エージェント設定の検証

### パフォーマンス
- agent_deploy_configs のインデックス（department_id, deploy_status）
- ポーリング間隔: 3秒（調整可能）
- キャッシュ: department_types（1時間有効）

---

## 10. 成果物チェックリスト

- [x] データベーススキーマ（migration SQL）
- [x] API I/F 仕様（エンドポイント・リクエスト・レスポンス）
- [x] UI コンポーネント構成図
- [x] JavaScript モジュール設計
- [x] Pydantic モデル定義
- [x] Flask ルート設計
- [x] 実装順序・依存関係

---

**Tech Lead**: Claude  
**作成日時**: 2026-04-26 15:50 JST  
**設計完了**: YES ✓

→ **次: Engineer による実装フェーズ開始**
