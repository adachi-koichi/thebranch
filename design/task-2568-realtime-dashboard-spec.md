# Task #2568: リアルタイム状態可視化 - 技術設計仕様書

**作成日:** 2026-04-30  
**Tech Lead:** claude (AI)  
**Status:** 設計完了 → 実装開始待ち

---

## 概要

THEBRANCH ダッシュボードに **リアルタイム状態可視化機能** を実装する。  
tmux セッション・ペイン・タスク情報をリアルタイムで監視し、WebSocket で Frontend に配信する。

---

## 1. 既存構造確認

### Backend
- **Framework:** FastAPI + uvicorn
- **Port:** 7002
- **WebSocket:** `from fastapi import WebSocket, WebSocketDisconnect` (インポート済み)
- **認証:** `get_current_user_zero_trust` dependency
- **既存 SSE:** `/api/stream` (5秒ポーリング) → WebSocket に置き換え予定

### Frontend
- **構成:** SPA (index.html)
- **ルート:** `/projects`, `/workflows`, `/workflow-templates`, `/agent-chat`
- **イベントリスナー:** addEventListener 実装済み

---

## 2. 実装方式：WebSocket 採用決定

### 比較表

| 項目 | WebSocket | SSE |
|---|---|---|
| 双方向通信 | ✅ 可能 | ❌ サーバ→クライアント のみ |
| 遅延 | 低（10-50ms） | 中（500ms-1s） |
| 接続管理 | 複雑 | シンプル |
| ブラウザ互換性 | ✅ 広い | ✅ 広い |
| スケーラビリティ | コネクション多数で重い | ポーリング費用高い |

### 決定理由
- ペイン同期：双方向通信が必要
- リアルタイム性：50ms 以下の遅延が望ましい
- スケーラビリティ：将来の複数部署対応

---

## 3. データフロー設計

```
┌─────────────────────────────────────────────────────────────┐
│ Backend: Orchestration Engine (dashboard/app.py)            │
├─────────────────────────────────────────────────────────────┤
│ Startup:                                                    │
│  • asyncio.create_task(tmux_monitor_loop())                 │
│  • asyncio.create_task(task_db_monitor_loop())              │
│                                                             │
│ @app.websocket("/ws/dashboard/{user_id}")                   │
│  • トークン検証                                              │
│  • コネクション管理（connections dict）                      │
│  • クライアント数制限（500 concurrent）                      │
│                                                             │
│ Monitor Loops:                                              │
│  • tmux_monitor_loop(): 1秒ごと状態取得 → broadcast        │
│  • task_db_monitor_loop(): 2秒ごと状態取得 → broadcast      │
└─────────────────────────────────────────────────────────────┘
           ↕ WebSocket フレーム（JSON Lines）
           ↕ Reconnect handling + heartbeat (30s)
┌─────────────────────────────────────────────────────────────┐
│ Frontend: Real-time Dashboard (js/realtime.js)              │
├─────────────────────────────────────────────────────────────┤
│ • WebSocket接続管理（自動再接続）                            │
│ • メッセージ type 別ディスパッチ                             │
│ • DOM update（debounce: 100ms）                             │
│ • エラーハンドリング + graceful degradation                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. API スキーマ定義

### WebSocket エンドポイント

```
URL: ws://localhost:7002/ws/dashboard/{user_id}
認証: Authorization header (Bearer token) or query param
Path: /ws/dashboard/{user_id}?token=<bearer_token>
```

### クライアント → サーバメッセージ

```json
{
  "type": "subscribe|unsubscribe|ping",
  "channel": "tmux_sessions|tasks|agents",
  "filter": {
    "org_id": "org_123"
  }
}
```

### サーバ → クライアントメッセージ

#### Type: `tmux_session_update`
```json
{
  "type": "tmux_session_update",
  "timestamp": "2026-04-30T01:59:00Z",
  "data": {
    "sessions": [
      {
        "name": "thebranch@main",
        "status": "active|inactive",
        "windows": [
          {
            "id": 0,
            "name": "orchestrator",
            "panes": [
              {
                "id": "0.0",
                "active": true,
                "command": "ccc-orchestrator",
                "cwd": "/Users/delightone/dev/github.com/adachi-koichi/ai-orchestrator"
              }
            ]
          },
          {
            "id": 1,
            "name": "exp-stock-team",
            "panes": [
              {
                "id": "1.0",
                "active": true,
                "command": "ccc",
                "cwd": "/Users/delightone/dev/github.com/adachi-koichi/exp-stock"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

#### Type: `task_status`
```json
{
  "type": "task_status",
  "timestamp": "2026-04-30T01:59:00Z",
  "data": {
    "tasks": [
      {
        "id": 2568,
        "title": "【Wave29】AIエージェント部署ダッシュボード - リアルタイム状態可視化",
        "status": "in_progress|pending|completed",
        "assignee": "engineer_id_1",
        "priority": 1,
        "updated_at": "2026-04-30T01:58:00Z"
      }
    ]
  }
}
```

#### Type: `heartbeat`
```json
{
  "type": "heartbeat",
  "timestamp": "2026-04-30T01:59:00Z"
}
```

#### Type: `error`
```json
{
  "type": "error",
  "code": "AUTH_FAILED|CONNECTION_LIMIT|SERVER_ERROR",
  "message": "..."
}
```

---

## 5. Backend 実装設計

### 新規ファイル: `dashboard/realtime.py`

```python
# Connection manager
class ConnectionManager:
    def __init__(self, max_connections=500):
        self.active_connections: List[WebSocket] = []
        self.max_connections = max_connections
    
    async def connect(self, websocket: WebSocket):
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1008, reason="Server at capacity")
            raise RuntimeError("Connection limit exceeded")
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        
        for connection in dead_connections:
            self.disconnect(connection)

# State cache
class StateCache:
    def __init__(self):
        self.tmux_state = {}
        self.tasks_state = {}
        self.last_tmux_hash = None
        self.last_tasks_hash = None
    
    def has_changed(self, new_state, field):
        old_hash = getattr(self, f"last_{field}_hash")
        new_hash = hashlib.md5(json.dumps(new_state, sort_keys=True).encode()).hexdigest()
        setattr(self, f"last_{field}_hash", new_hash)
        return new_hash != old_hash
```

### Monitor Loops

```python
async def tmux_monitor_loop(cm: ConnectionManager, cache: StateCache):
    while True:
        try:
            sessions = await get_tmux_sessions()  # subprocess.run tmux list-sessions
            if cache.has_changed(sessions, "tmux"):
                await cm.broadcast({
                    "type": "tmux_session_update",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "data": {"sessions": sessions}
                })
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"tmux_monitor_loop error: {e}")
            await asyncio.sleep(5)

async def task_db_monitor_loop(cm: ConnectionManager, cache: StateCache):
    while True:
        try:
            tasks = await get_tasks_from_db()
            if cache.has_changed(tasks, "tasks"):
                await cm.broadcast({
                    "type": "task_status",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "data": {"tasks": tasks}
                })
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"task_db_monitor_loop error: {e}")
            await asyncio.sleep(5)

async def heartbeat_loop(cm: ConnectionManager):
    while True:
        await cm.broadcast({
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        await asyncio.sleep(30)
```

### WebSocket エンドポイント

```python
@app.websocket("/ws/dashboard/{user_id}")
async def websocket_dashboard(websocket: WebSocket, user_id: str, 
                               authorization: Optional[str] = Header(None)):
    # 認証
    auth_user_id, scopes, token_type = await verify_token_with_scope(authorization)
    if not auth_user_id or auth_user_id != user_id:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    # コネクション受け入れ
    try:
        await manager.connect(websocket)
    except RuntimeError:
        return
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "subscribe":
                # フィルタ情報を保存（org_id 等）
                pass
            elif msg_type == "unsubscribe":
                pass
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
```

### Startup

```python
@app.on_event("startup")
async def startup():
    asyncio.create_task(tmux_monitor_loop(manager, state_cache))
    asyncio.create_task(task_db_monitor_loop(manager, state_cache))
    asyncio.create_task(heartbeat_loop(manager))
```

---

## 6. Frontend 実装設計

### 新規ファイル: `dashboard/js/realtime.js`

```javascript
class RealtimeDashboard {
  constructor(userId, options = {}) {
    this.userId = userId;
    this.protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    this.host = window.location.host;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // ms
    this.messageHandlers = {};
    this.debounceTimers = {};
    this.debounceDelay = 100; // ms
  }

  connect() {
    const token = this.getToken(); // localStorage or cookie
    const url = `${this.protocol}://${this.host}/ws/dashboard/${this.userId}?token=${token}`;
    
    this.ws = new WebSocket(url);
    this.ws.onopen = () => this.onOpen();
    this.ws.onmessage = (e) => this.onMessage(JSON.parse(e.data));
    this.ws.onerror = (e) => this.onError(e);
    this.ws.onclose = () => this.onClose();
  }

  onOpen() {
    console.log("WebSocket connected");
    this.reconnectAttempts = 0;
    this.subscribe("tmux_sessions");
    this.subscribe("tasks");
  }

  onMessage(msg) {
    const { type, data, timestamp } = msg;
    
    // Debounce UI updates
    if (this.debounceTimers[type]) {
      clearTimeout(this.debounceTimers[type]);
    }
    
    this.debounceTimers[type] = setTimeout(() => {
      switch(type) {
        case 'tmux_session_update':
          this.updateSessionUI(data);
          break;
        case 'task_status':
          this.updateTaskUI(data);
          break;
        case 'heartbeat':
          // No-op
          break;
        case 'error':
          this.handleError(data);
          break;
        default:
          console.warn("Unknown message type:", type);
      }
    }, this.debounceDelay);
  }

  updateSessionUI(data) {
    const { sessions } = data;
    const container = document.getElementById('tmux-sessions');
    if (!container) return;
    
    // Clear existing
    container.innerHTML = '';
    
    // Render sessions
    sessions.forEach(session => {
      const sessionEl = this.createSessionElement(session);
      container.appendChild(sessionEl);
    });
  }

  updateTaskUI(data) {
    const { tasks } = data;
    const container = document.getElementById('tasks-panel');
    if (!container) return;
    
    // Update task list
    const taskList = container.querySelector('.task-list');
    taskList.innerHTML = tasks.map(task => `
      <div class="task-item" data-id="${task.id}">
        <span class="task-title">${task.title}</span>
        <span class="task-status ${task.status}">${task.status}</span>
        <span class="task-assignee">${task.assignee}</span>
      </div>
    `).join('');
  }

  createSessionElement(session) {
    const div = document.createElement('div');
    div.className = 'session-block';
    div.innerHTML = `
      <h3>${session.name}</h3>
      ${session.windows.map(w => `
        <div class="window-block">
          <h4>Window ${w.id}: ${w.name}</h4>
          <ul class="panes-list">
            ${w.panes.map(p => `
              <li class="pane ${p.active ? 'active' : ''}">
                <code>${p.command}</code>
              </li>
            `).join('')}
          </ul>
        </div>
      `).join('')}
    `;
    return div;
  }

  subscribe(channel) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "subscribe",
        channel: channel,
        filter: { org_id: this.getOrgId() }
      }));
    }
  }

  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`);
      setTimeout(() => this.connect(), delay);
    } else {
      console.error("Max reconnect attempts reached");
      this.fallbackToPolling();
    }
  }

  fallbackToPolling() {
    // /api/dashboard/state/{user_id} をポーリング
    console.log("Falling back to HTTP polling...");
  }

  onError(e) {
    console.error("WebSocket error:", e);
  }

  onClose() {
    console.log("WebSocket closed");
    this.reconnect();
  }

  handleError(error) {
    console.error("Server error:", error);
    // UI notification
  }

  getToken() {
    return localStorage.getItem('auth_token') || 
           new URLSearchParams(window.location.search).get('token');
  }

  getOrgId() {
    return localStorage.getItem('org_id') || 'default';
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  const userId = document.body.dataset.userId;
  const dashboard = new RealtimeDashboard(userId);
  dashboard.connect();
  window.realtimeDashboard = dashboard;
});
```

### HTML 統合 (index.html)

```html
<!-- セッション・ペイン表示 -->
<div id="tmux-sessions" class="realtime-panel">
  <h2>Active Sessions</h2>
  <!-- リアルタイム更新される -->
</div>

<!-- タスク表示 -->
<div id="tasks-panel" class="realtime-panel">
  <h2>Task Status</h2>
  <ul class="task-list">
    <!-- リアルタイム更新される -->
  </ul>
</div>

<!-- Script 読み込み -->
<script src="/js/realtime.js"></script>
```

---

## 7. セキュリティ・パフォーマンス

### セキュリティ
- ✅ WebSocket 接続前に Bearer token 検証
- ✅ org_id フィルタ：同一組織の data のみ配信
- ✅ Rate limiting：100 msg/min per connection
- ✅ CORS + origin check
- ✅ XSS 対策：JSON.stringify 使用（HTML エスケープ）

### パフォーマンス
- ✅ ハートビート：30 秒ごと（接続確認）
- ✅ Debounce：100ms（UI 更新スロットリング）
- ✅ 接続上限：500 concurrent WS
- ✅ State cache：hash 比較で変更検知（不要な配信を削減）
- ✅ Memory：LRU cache（直近 100 state snapshot）

### ネットワーク最適化
- ✅ JSON Lines (NDJSON)：1行 = 1メッセージ
- ✅ 差分配信：変更があった部分のみ送信
- ✅ Compression：gzip を検討（nginx reverse proxy）
- ✅ 自動再接続：exponential backoff

---

## 8. 実装タスク分割

### Backend Tasks

| ID | タスク | 所要時間 | 依存 |
|---|--------|--------|------|
| 8.1 | `realtime.py` 作成：ConnectionManager + StateCache | 2h | - |
| 8.2 | tmux_monitor_loop + task_db_monitor_loop 実装 | 3h | 8.1 |
| 8.3 | `/ws/dashboard/{user_id}` エンドポイント実装 | 2h | 8.1, 8.2 |
| 8.4 | 認証統合 + org_id フィルタ | 1.5h | 8.3 |
| 8.5 | テスト：接続、メッセージ配信、エラーハンドリング | 2h | 8.3, 8.4 |

### Frontend Tasks

| ID | タスク | 所要時間 | 依存 |
|---|--------|--------|------|
| 8.6 | `realtime.js` 作成：RealtimeDashboard クラス | 2h | - |
| 8.7 | DOM update handlers：updateSessionUI, updateTaskUI | 2h | 8.6 |
| 8.8 | HTML 統合（index.html に #tmux-sessions, #tasks-panel 追加） | 1h | 8.7 |
| 8.9 | CSS スタイリング（セッション・ペイン表示） | 1.5h | 8.8 |
| 8.10 | テスト：E2E (接続→メッセージ受信→DOM更新) | 2h | 8.9 |

### Total: ~19.5 hours (1 engineer-day)

---

## 9. テスト計画

### Unit Tests (Backend)
```python
# test_realtime.py
async def test_connection_manager_limit():
    # 接続上限テスト
    
async def test_state_cache_hash_change():
    # 状態変更検知テスト
    
async def test_tmux_monitor_parsing():
    # tmux コマンド解析テスト
```

### E2E Tests
```gherkin
Feature: リアルタイムダッシュボード
  Scenario: WebSocket で tmux セッション更新を受信
    Given ユーザーが接続している
    When tmux で新しいペインを作成
    Then 1秒以内に Frontend に更新が配信される
    And DOM に新しいペインが表示される
```

### 負荷テスト
- 500 concurrent WS connections
- 100 msg/sec broadcast rate
- Memory usage < 500MB

---

## 10. デプロイ・ロールアウト

### Phase 1: Alpha (Internal)
- dev ブランチでテスト
- Orchestrator セッション内で動作確認

### Phase 2: Beta
- `feature/task-2568-realtime` ブランチ
- QA 部門でテスト

### Phase 3: Production
- main ブランチにマージ
- Gradual rollout (10% → 50% → 100%)

---

## 参考資料

- WebSocket RFC: https://tools.ietf.org/html/rfc6455
- FastAPI WebSocket: https://fastapi.tiangolo.com/advanced/websockets/
- tmux scripting: https://man7.org/linux/man-pages/man1/tmux.1.html

---

**Next:** Backend Engineer が Task #8.1 から実装開始
