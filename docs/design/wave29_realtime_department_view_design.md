# Wave29 リアルタイム部署稼働ビュー 設計書

**タスク**: #2568  
**機能**: AIエージェント部署ダッシュボード - リアルタイム状態可視化（ペイン・セッション・タスク統合ビュー）  
**作成日**: 2026-04-30

---

## 1. 目的と概要

AIエージェント部署の稼働状況をリアルタイムで可視化する統合ビューを実装する。  
tmuxセッション階層（session > window > pane）と、各ペインで動いているエージェントのタスク情報を一画面で把握できるようにする。

**ゴール**:
- 部署全体が「今何をしているか」を3秒以内の遅延で把握できる
- セッション → ウィンドウ → ペインの階層構造を直感的に確認できる
- 各エージェントの担当タスク・進捗・完了率をカード形式で表示する

---

## 2. 現状分析

### 既存の WebSocket エンドポイント

| エンドポイント | 役割 | 更新間隔 |
|---|---|---|
| `/ws` | タスク統計 + ペインサマリー | 3秒 |
| `/ws/panes` | tmuxペイン状態（差分あり） | 3秒 |
| `/ws/tasks` | タスク一覧（差分あり） | 3秒 |
| `/ws/agents` | エージェント状態（差分検出） | 3秒 |
| `/ws/pane/{pane_id}` | 個別ペインログ | 2秒 |

### 既存データ構造（`get_agents_data()`）

```python
{
    "pid": int,
    "sessionId": str,          # Claude セッションID
    "cwd": str,                # 作業ディレクトリ
    "startedAt": str,          # ISO8601
    "kind": str,
    "tmux_pane": str,          # "session@window:w.p" 形式
    "latest_prompt": str,      # 最新ユーザープロンプト（500文字）
    "persona_name": str,       # エージェント名
    "task_title": str,         # 担当タスクタイトル
    "progress": str,           # 最新アシスタントテキスト（20文字）
}
```

### ギャップ分析

| 必要機能 | 現状 | 対応 |
|---|---|---|
| セッション階層ビュー（session>window>pane） | なし（フラット） | 新規: `_build_session_tree()` |
| ペイン状態（busy/approval/idle） | `_list_panes()` に一部あり | 統合して活用 |
| 応答時間（last activity 経過時間） | なし | JSONL mtime から計算 |
| 完了率 | タスク統計はあるが未連携 | `_get_task_stats()` 活用 |
| 統合WebSocketエンドポイント | なし | 新規: `/ws/integrated` |
| フロントエンドUI（統合ビュー） | なし | index.html に新セクション追加 |

---

## 3. バックエンド設計

### 3.1 新規エンドポイント: `GET /api/department-view`

初回ロード用の REST エンドポイント。WebSocket 接続前の初期データ取得に使用。

```
GET /api/department-view
Authorization: Bearer <token>
Response: 200 OK { ...IntegratedPayload }
```

### 3.2 新規 WebSocket: `/ws/integrated`

セッション・ペイン・タスクを統合したデータを3秒ごとに配信。差分がある場合のみ送信。

#### ペイロード構造

```json
{
    "type": "integrated_update",
    "ts": "2026-04-30T12:34:56",
    "summary": {
        "total_sessions": 3,
        "total_panes": 8,
        "active_agents": 6,
        "task_stats": {
            "pending": 12,
            "in_progress": 6,
            "completed": 245
        },
        "completion_rate": 0.938
    },
    "sessions": [
        {
            "name": "ai-orchestrator@main",
            "display_name": "ai-orchestrator",
            "windows": [
                {
                    "index": 0,
                    "name": "orchestrator",
                    "panes": [
                        {
                            "pane_id": "ai-orchestrator@main:0.0",
                            "cwd": "/path/to/dir",
                            "status": "busy",
                            "agent": {
                                "pid": 12345,
                                "session_id": "abc123",
                                "persona_name": "Orchestrator",
                                "task_title": "Wave29 タスク管理",
                                "progress": "タスク一覧を確認中",
                                "last_activity_sec": 42
                            }
                        }
                    ]
                }
            ]
        }
    ]
}
```

#### `last_activity_sec` の計算ロジック

```python
def _get_last_activity_sec(cwd: str) -> int:
    """最新JSONL更新からの経過秒数を返す"""
    latest = _get_latest_jsonl(cwd)
    if not latest:
        return -1
    return int(time.time() - latest.stat().st_mtime)
```

#### セッション階層構築ロジック

```python
def _build_session_tree(panes: list, agents: list) -> list:
    """
    tmux pane フラットリストと agent データを
    session > window > pane の階層構造に変換する
    """
    agent_by_cwd = {a["cwd"]: a for a in agents}
    tree: dict[str, dict] = {}

    for pane in panes:
        pane_id = pane.get("id", "")
        # pane_id 形式: "session@window:W.P" または "session:W.P"
        # parse してツリーに組み込む
        ...

    return list(tree.values())
```

### 3.3 既存 `_list_panes()` の確認と活用

`_list_panes()` が返す形式を確認し、`pane_id` のパース規則を統一する。

```python
# tmux list-panes -a -F の出力形式
# "session_name@window_name:window_index.pane_index cwd"
# 例: "ai-orchestrator@main:0.0 /Users/delightone/dev/..."
```

---

## 4. フロントエンド設計

### 4.1 配置: `index.html` に新セクション追加

既存の `#agent-scores` セクションの直前に `#department-view` セクションを追加。

```html
<!-- ナビゲーションに追加 -->
<li><a href="#department-view">部署稼働ビュー</a></li>
```

### 4.2 レイアウト構成

```
┌─────────────────────────────────────────────────────────┐
│  部署稼働ビュー                        [最終更新: 3秒前] │
├─────────────┬──────────────┬───────────┬───────────────┤
│ セッション3  │ アクティブ6  │ 完了率93% │ 進行中タスク6 │ ← サマリーバー
├─────────────┴──────────────┴───────────┴───────────────┤
│                                                         │
│  [▼] ai-orchestrator@main                              │
│  │   [▼] window:0  orchestrator                       │
│  │   │   ┌──────────────────────────────────────┐    │
│  │   │   │ ● busy  Orchestrator                  │    │
│  │   │   │ Wave29 タスク管理                      │    │
│  │   │   │ "タスク一覧を確認中"   最終活動: 42秒前│    │
│  │   │   └──────────────────────────────────────┘    │
│  │                                                     │
│  [▼] thebranch_orchestrator_wf2568_task-2568@main      │
│  │   [▼] window:managers                              │
│  │   │   ┌──────────────────────┐                     │
│  │   │   │ ● busy  EM Agent     │                     │
│  │   │   │ #2568 設計フェーズ   │                     │
│  │   │   └──────────────────────┘                     │
│  │   [▼] window:members                               │
│  │       ┌──────────────────────┐ ┌──────────────────┐│
│  │       │ ● busy  Engineer A   │ │ ⏸ idle Engineer B││
│  │       │ 設計書作成           │ │ 待機中           ││
│  │       └──────────────────────┘ └──────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### 4.3 エージェントカード仕様

```
ステータスバッジ:
  ● busy     → グリーン (#10B981)
  ⚠ approval → アンバー (#F59E0B)  ← 承認待ち
  ⏸ idle     → グレー  (#6B7280)

カード内容:
  行1: [ステータスバッジ] [persona_name]          [last_activity]
  行2: [task_title] (最大40文字、省略あり)
  行3: [progress テキスト] (最大30文字、薄色)

クリック動作:
  → ペインログモーダル (/ws/pane/{pane_id}) を開く
```

### 4.4 WebSocket 接続コード（概要）

```javascript
const ws = new WebSocket(`ws://${location.host}/ws/integrated`);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'integrated_update') {
        updateSummaryBar(data.summary);
        renderSessionTree(data.sessions);
        updateLastUpdated(data.ts);
    }
};
```

---

## 5. 実装ファイル一覧

| ファイル | 変更内容 | 規模 |
|---|---|---|
| `dashboard/app.py` | `_build_session_tree()`, `_get_last_activity_sec()`, `/api/department-view`, `/ws/integrated` 追加 | +120行 |
| `dashboard/index.html` | `#department-view` セクション追加、ナビリンク追加、CSS + JS | +200行 |

---

## 6. 実装フェーズ

| フェーズ | 内容 | 優先度 |
|---|---|---|
| Phase 1 | バックエンド: `_build_session_tree()` + `/api/department-view` | 高 |
| Phase 2 | バックエンド: `/ws/integrated` WebSocket + 差分配信 | 高 |
| Phase 3 | フロントエンド: セッションツリー UI + エージェントカード | 高 |
| Phase 4 | フロントエンド: ペインログモーダル連携（既存 `/ws/pane/{pane_id}` 活用） | 中 |

---

## 7. 技術上の注意点

1. **tmux pane_id パース**: `_list_panes()` の出力形式を確認してから階層構築する
2. **認証**: `/ws/integrated` は `get_current_user_zero_trust` と同等の認証が必要  
   → 既存 WSエンドポイントに認証がないため、まず既存方式（無認証）に合わせる
3. **パフォーマンス**: `get_agents_data()` は JSONL ファイル読み込みを含む重い処理  
   → キャッシュ（前回結果を5秒保持）を追加して `/ws/integrated` への影響を抑える
4. **応答時間表示**: JSONL mtime ベースのため、エージェントが無活動の場合は「N秒前」ではなく「不明」と表示する

---

## 8. 受け入れ基準

- [ ] `/api/department-view` が session > window > pane の階層JSONを返す
- [ ] `/ws/integrated` が3秒ごとに差分データを配信する
- [ ] フロントエンドにセッションツリービューが表示される
- [ ] 各エージェントカードにステータス（busy/approval/idle）が表示される
- [ ] 各エージェントカードに担当タスク名と最終活動時間が表示される
- [ ] ダッシュボードで動作確認（curl + ブラウザ）が完了している
