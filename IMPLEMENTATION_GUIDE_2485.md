# タスク #2485 実装ガイド
## AIエージェント評価・スコアリング機能

作成日: 2026-04-26 15:24  
EM: Engineering Manager  
目標: 3時間以内に Phase 1 完成

---

## 📋 バックエンド実装ガイド

### ファイル構成

```
dashboard/
├── app.py                      ← /api/agents/scores ルーター追加
├── blueprints.py               ← 既存（参考用）
├── scores_routes.py            ← 【新規作成】スコアルーター
├── models.py                   ← 【更新】ScoreModel Pydantic スキーマ追加
└── data/
    └── thebranch.sqlite        ← agent_scores テーブル追加
```

### Step 1: models.py に ScoreModel を追加

```python
from pydantic import BaseModel
from typing import Optional

class ScoreModel(BaseModel):
    id: int
    agent_id: str
    agent_name: str
    completion_rate: float
    quality_score: float
    performance_score: float
    overall_score: float
    total_tasks: int
    completed_tasks: int
    last_updated: str
    
    class Config:
        from_attributes = True
```

### Step 2: scores_routes.py を新規作成

```python
from fastapi import APIRouter, Depends, HTTPException
from dashboard.models import ScoreModel
import sqlite3
from pathlib import Path

router = APIRouter(prefix="/api/agents", tags=["agents"])

THEBRANCH_DB = Path(__file__).parent / "data" / "thebranch.sqlite"

@router.get("/scores", response_model=list[ScoreModel])
async def get_agent_scores(authorization: Optional[str] = Header(None)):
    """全エージェントのスコア取得"""
    # 認証チェック（既存の verify_token_with_scope を使用）
    user_id, scopes, token_type = await verify_token_with_scope(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # DB から agent_scores テーブルを取得
    conn = sqlite3.connect(str(THEBRANCH_DB))
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_scores ORDER BY overall_score DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return rows

@router.post("/scores", response_model=ScoreModel)
async def create_agent_score(score_data: ScoreModel, authorization: Optional[str] = Header(None)):
    """エージェントスコアを作成・更新"""
    # 認証チェック
    user_id, scopes, token_type = await verify_token_with_scope(authorization)
    if not user_id or "write" not in scopes:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # DB に INSERT or UPDATE
    conn = sqlite3.connect(str(THEBRANCH_DB))
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO agent_scores (agent_id, agent_name, total_tasks, completed_tasks, quality_score, performance_score, overall_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            agent_name = excluded.agent_name,
            total_tasks = excluded.total_tasks,
            completed_tasks = excluded.completed_tasks,
            quality_score = excluded.quality_score,
            performance_score = excluded.performance_score,
            overall_score = excluded.overall_score,
            last_updated = CURRENT_TIMESTAMP
    """, (
        score_data.agent_id, score_data.agent_name,
        score_data.total_tasks, score_data.completed_tasks,
        score_data.quality_score, score_data.performance_score,
        score_data.overall_score
    ))
    
    conn.commit()
    conn.close()
    
    return score_data
```

### Step 3: app.py にルーター追加

`app.py` の routers include セクションに追加：

```python
from dashboard import scores_routes

# ... existing routers ...
app.include_router(scores_routes.router)  # ← 追加
```

### Step 4: DB Migration

```bash
sqlite3 /Users/delightone/dev/github.com/adachi-koichi/thebranch/dashboard/data/thebranch.sqlite << 'EOF'
CREATE TABLE IF NOT EXISTS agent_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL UNIQUE,
  agent_name TEXT NOT NULL,
  completion_rate REAL DEFAULT 0.0,
  quality_score REAL DEFAULT 0.0,
  performance_score REAL DEFAULT 0.0,
  overall_score REAL DEFAULT 0.0,
  total_tasks INTEGER DEFAULT 0,
  completed_tasks INTEGER DEFAULT 0,
  last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
EOF
```

### Step 5: 動作確認

```bash
# サーバー起動
cd /Users/delightone/dev/github.com/adachi-koichi/thebranch
python3 dashboard/app.py

# テストデータ挿入
curl -X POST http://localhost:5000/api/agents/scores \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "eng-001",
    "agent_name": "Engineer #1",
    "total_tasks": 20,
    "completed_tasks": 17,
    "quality_score": 92.5,
    "performance_score": 88.0,
    "overall_score": 89.2
  }'

# スコア一覧取得
curl http://localhost:5000/api/agents/scores
```

---

## 📋 フロントエンド実装ガイド

### ファイル構成

```
dashboard/
├── index.html       ← 【編集】タブセクション追加
└── js/
    └── scores.js    ← 【新規作成】スコアテーブル・グラフ制御
```

### Step 1: index.html でタブを追加

`index.html` の既存タブ構造を探して（`<nav class="tabs">` など）、新しいタブを追加：

```html
<!-- 既存タブ -->
<nav class="tabs">
  <button class="tab-button active" data-tab="dashboard">ダッシュボード</button>
  <button class="tab-button" data-tab="workflows">ワークフロー</button>
  
  <!-- 【新規追加】 -->
  <button class="tab-button" data-tab="agent-scores">エージェントスコア</button>
</nav>

<!-- タブコンテンツ -->
<div id="dashboard" class="tab-content active"><!-- 既存内容 --></div>
<div id="workflows" class="tab-content"><!-- 既存内容 --></div>

<!-- 【新規追加】 -->
<div id="agent-scores" class="tab-content">
  <div class="scores-container">
    <h2>AIエージェント評価スコア</h2>
    
    <!-- スコアテーブル -->
    <table id="scoresTable" class="scores-table">
      <thead>
        <tr>
          <th>エージェント名</th>
          <th>完了率</th>
          <th>品質スコア</th>
          <th>パフォーマンス</th>
          <th>総合スコア</th>
          <th>更新日時</th>
        </tr>
      </thead>
      <tbody id="scoresTableBody">
        <!-- JavaScript で動的生成 -->
      </tbody>
    </table>
    
    <!-- グラフエリア -->
    <div id="scoresChart" style="margin-top: 40px;"></div>
  </div>
</div>
```

### Step 2: js/scores.js を新規作成

```javascript
// API からスコアデータを取得して表示
async function loadScores() {
  try {
    const response = await fetch('/api/agents/scores');
    const data = await response.json();
    
    if (data.length === 0) {
      document.getElementById('scoresTableBody').innerHTML = 
        '<tr><td colspan="6" style="text-align: center;">データなし</td></tr>';
      return;
    }
    
    // テーブル行を生成
    const tbody = document.getElementById('scoresTableBody');
    tbody.innerHTML = data.map(score => `
      <tr>
        <td>${score.agent_name}</td>
        <td>${(score.completion_rate * 100).toFixed(1)}%</td>
        <td>${score.quality_score.toFixed(1)}</td>
        <td>${score.performance_score.toFixed(1)}</td>
        <td><strong>${score.overall_score.toFixed(1)}</strong></td>
        <td>${new Date(score.last_updated).toLocaleString('ja-JP')}</td>
      </tr>
    `).join('');
    
    // グラフ表示（Chart.js あるいは canvas で実装）
    renderChart(data);
    
  } catch (error) {
    console.error('スコアデータ取得エラー:', error);
    document.getElementById('scoresTableBody').innerHTML = 
      '<tr><td colspan="6" style="color: red;">エラーが発生しました</td></tr>';
  }
}

// グラフ描画（簡易版：Canvas で実装）
function renderChart(data) {
  const chartContainer = document.getElementById('scoresChart');
  
  // Chart.js を使う場合：
  // new Chart(chartContainer, { ... })
  
  // 簡易版（HTML5 Canvas）：
  const canvas = document.createElement('canvas');
  canvas.width = 600;
  canvas.height = 400;
  chartContainer.appendChild(canvas);
  
  // 棒グラフ描画ロジック
  // ...
}

// 30秒ごとに自動更新
setInterval(() => {
  loadScores();
}, 30000);

// 初期ロード
loadScores();
```

### Step 3: index.html に JS を読み込み

`</body>` の前に追加：

```html
<script src="/js/scores.js"></script>
```

### Step 4: CSS スタイル追加（index.html の `<style>` セクション内）

```css
.scores-container {
  padding: 20px;
  background-color: var(--bg-secondary);
  border-radius: 8px;
}

.scores-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 20px;
}

.scores-table thead {
  background-color: var(--bg-tertiary);
}

.scores-table th, .scores-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.scores-table tr:hover {
  background-color: var(--bg-tertiary);
}

.scores-table strong {
  color: var(--accent);
  font-weight: 700;
}
```

### Step 5: 動作確認

1. ブラウザで `http://localhost:5000` を開く
2. 「エージェントスコア」タブをクリック
3. テーブルが表示される
4. 30秒後に自動更新される

---

## 🔗 連携チェックリスト

- [ ] **バックエンド**: DB migration 実行済み
- [ ] **バックエンド**: GET /api/agents/scores エンドポイント実装完了
- [ ] **バックエンド**: POST /api/agents/scores エンドポイント実装完了
- [ ] **バックエンド**: curl でテスト成功
- [ ] **フロント**: 「エージェントスコア」タブ追加完了
- [ ] **フロント**: スコアテーブル表示完了
- [ ] **フロント**: グラフ表示完了（簡易版可）
- [ ] **統合テスト**: ブラウザで動作確認完了
- [ ] **統合テスト**: API と フロント の連携確認完了

---

**EM サポート**: 質問・ブロッカーがあれば managers ペインに送信してください。  
**目標完成時刻**: 2026-04-26 18:30（3時間以内）
