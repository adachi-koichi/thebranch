# AIエージェント間メッセージング・通知システム（MVP フェーズ 1）
## 実装サマリー・Engineer チーム委譲指示

**Document Version:** 1.0  
**Date:** 2026-04-30  
**Status:** Ready for Implementation  
**Tech Lead:** Claude Code (Task #2547)  

---

## 実装概要

### MVPスコープ（フェーズ 1）
✅ **設計完了** — 以下 3 つの仕様書・計画ドキュメント完成

1. **インターフェース仕様書** (`agent_messaging_interface_spec.md`)
   - WebSocket イベント仕様（task.completed）
   - Webhook 登録 API（POST /api/webhooks/register）
   - API スキーマ（OpenAPI 3.0）
   - セキュリティ考慮

2. **DB マイグレーション計画** (`agent_messaging_db_migration_plan.md`)
   - task_completion_events テーブル
   - webhook_subscriptions テーブル
   - webhook_delivery_logs テーブル
   - Flask Alembic マイグレーション実装例

3. **実装ロードマップ**（本ドキュメント）
   - 実装順序・優先度
   - Engineer チーム向け分配タスク
   - テスト計画

---

## Engineer チーム構成（2名）

| 順序 | 名前 | 担当 | 期限 |
|---|---|---|---|
| Engineer #1 | - | Backend: WebSocket + Webhook API | 2026-05-07 |
| Engineer #2 | - | Backend: DB + イベント検出ロジック | 2026-05-07 |

### チーム運営ルール
- **日次同期:** 朝 10:00 (15分)
- **実装進捗報告:** Slack または GitHub Issues コメント
- **Design Review:** Tech Lead による設計確認（毎日）

---

## 実装タスク分配

### Engineer #1: WebSocket + Webhook API 実装

#### Task: WebSocket エンドポイント実装 (`/ws`)

**ファイル:** `dashboard/app.py` または `dashboard/websocket.py`（新規）

**実装項目:**
1. Flask / Flask-SocketIO 統合
2. JWT トークン認証（クエリパラメータ・ヘッダ対応）
3. イベント送信ロジック（task.completed イベント）
4. クライアント接続管理
5. ハートビート・キープアライブ

**テスト:**
```python
# test_websocket.py
def test_websocket_task_completed_event():
    """WebSocket task.completed イベント送信"""
    event = {
        "type": "task.completed",
        "timestamp": "2026-04-30T06:57:03Z",
        "task_id": 2547,
        ...
    }
    # WebSocket 経由でイベント送信・受信確認

def test_websocket_authentication():
    """JWT トークン認証"""
    # 無効なトークンでの接続拒否確認
    # 有効なトークンでの接続確認
```

**コード例:**
```python
from flask import request
from flask_socketio import emit, join_room, disconnect

@socketio.on('connect')
def handle_connect():
    token = request.args.get('token')
    if not verify_jwt_token(token):
        disconnect()
        return False
    
    user_id = get_user_id_from_token(token)
    join_room(f"user_{user_id}")
    emit('connected', {'data': 'Connected'})

def notify_task_completed(event: dict):
    """task.completed イベント をすべてのリスナーに送信"""
    emit('task.completed', event, broadcast=True)
```

---

#### Task: Webhook 登録 API 実装

**ファイル:** `dashboard/routes/webhooks.py`（新規）

**実装項目:**
1. `POST /api/webhooks/register` — Webhook 登録
2. `DELETE /api/webhooks/{webhook_id}` — Webhook 削除
3. `GET /api/webhooks` — Webhook 一覧取得
4. シークレット保管（bcrypt ハッシュ化）
5. 入力バリデーション（URL形式、auth_type）

**テスト:**
```python
# test_webhooks_api.py
def test_register_webhook():
    """Webhook 登録"""
    payload = {
        "name": "test-webhook",
        "event_type": "task.completed",
        "target_url": "https://example.com/webhooks",
        "auth_type": "bearer",
        "secret_key": "whsec_test123"
    }
    resp = client.post('/api/webhooks/register', json=payload, 
                       headers={"Authorization": "Bearer <token>"})
    assert resp.status_code == 201
    assert 'webhook_id' in resp.json

def test_webhook_list():
    """Webhook 一覧取得"""
    resp = client.get('/api/webhooks?event_type=task.completed',
                      headers={"Authorization": "Bearer <token>"})
    assert resp.status_code == 200
    assert len(resp.json['webhooks']) >= 0
```

**コード例:**
```python
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')

@webhooks_bp.route('/register', methods=['POST'])
def register_webhook():
    """Webhook 登録"""
    data = request.get_json()
    
    # バリデーション
    required_fields = ['name', 'event_type', 'target_url', 'auth_type', 'secret_key']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # シークレット ハッシュ化
    secret_hash = generate_password_hash(data['secret_key'])
    
    webhook = WebhookSubscription(
        webhook_id=f"wh_{uuid.uuid4().hex[:20]}",
        user_id=get_current_user_id(),
        name=data['name'],
        event_type=data['event_type'],
        target_url=data['target_url'],
        auth_type=data['auth_type'],
        secret_key_hash=secret_hash,
        is_active=data.get('is_active', True)
    )
    db.session.add(webhook)
    db.session.commit()
    
    return jsonify({
        'webhook_id': webhook.webhook_id,
        'name': webhook.name,
        'created_at': webhook.created_at.isoformat()
    }), 201
```

---

### Engineer #2: DB + イベント検出ロジック実装

#### Task: DB マイグレーション実行

**ファイル:** `dashboard/migrations/versions/0XXX_add_agent_messaging_tables.py`

**実装手順:**
1. Alembic マイグレーションスクリプト生成
2. テーブル・インデックス作成
3. FOREIGN KEY 制約設定
4. ロールバック検証

**コマンド:**
```bash
cd /Users/delightone/dev/github.com/adachi-koichi/thebranch/dashboard
flask db migrate -m "Add agent messaging notification tables"
# 生成ファイルを上記仕様に合わせて調整
flask db upgrade
```

**テスト:**
```python
# test_db_migration.py
def test_task_completion_events_table_exists():
    """task_completion_events テーブル存在確認"""
    from dashboard.models import TaskCompletionEvent
    assert TaskCompletionEvent.__tablename__ == 'task_completion_events'

def test_webhook_subscriptions_table_exists():
    """webhook_subscriptions テーブル存在確認"""
    from dashboard.models import WebhookSubscription
    assert WebhookSubscription.__tablename__ == 'webhook_subscriptions'
```

---

#### Task: タスク完了イベント検出ロジック

**ファイル:** `dashboard/events/task_events.py`（新規）

**実装項目:**
1. `task.py done` 実行時のイベント検出フック
2. TaskCompletionEvent レコード作成
3. WebSocket ブロードキャスト
4. Webhook 配信キュー（pending → sent）

**実装例:**
```python
# dashboard/events/task_events.py
from dashboard.models import TaskCompletionEvent, db
from datetime import datetime, timezone

def on_task_completed(task_id: int, executor_user_id: str, completion_time_ms: int = None):
    """タスク完了時の イベント検出・配信処理"""
    
    # タスク情報を task-manager-sqlite から取得
    task = get_task_from_sqlite(task_id)
    
    # event レコード作成
    event = TaskCompletionEvent(
        task_id=task_id,
        workflow_id=task.get('workflow_id', str(task_id)),
        team_name=task.get('team_name', 'general'),
        executor_user_id=executor_user_id,
        executor_username=get_username(executor_user_id),
        executor_role=get_user_role(executor_user_id),
        status='completed',
        priority=task.get('priority', 3),
        completion_time_ms=completion_time_ms,
        tag_ids=json.dumps(task.get('tags', [])),
        category=task.get('category'),
        phase=task.get('phase'),
        event_status='triggered',
        triggered_at=datetime.now(timezone.utc)
    )
    db.session.add(event)
    db.session.commit()
    
    # WebSocket ブロードキャスト
    broadcast_task_completion_event(event)
    
    # Webhook 配信キュー登録
    queue_webhook_delivery(event)

def broadcast_task_completion_event(event: TaskCompletionEvent):
    """WebSocket クライアントにイベント ブロードキャスト"""
    event_payload = {
        "type": "task.completed",
        "timestamp": event.triggered_at.isoformat() + "Z",
        "task_id": event.task_id,
        "task_title": event.task_title,
        "workflow_id": event.workflow_id,
        "team_name": event.team_name,
        "executor": {
            "user_id": event.executor_user_id,
            "username": event.executor_username,
            "role": event.executor_role
        },
        "status": event.status,
        "priority": event.priority,
        "completion_time_ms": event.completion_time_ms,
        "metadata": {
            "tag_ids": json.loads(event.tag_ids or '[]'),
            "category": event.category,
            "phase": event.phase
        }
    }
    # Flask-SocketIO emit
    emit('task.completed', event_payload, broadcast=True)

def queue_webhook_delivery(event: TaskCompletionEvent):
    """Webhook 配信キューに登録"""
    from dashboard.models import WebhookSubscription, WebhookDeliveryLog
    
    # task.completed 購読者を取得
    webhooks = WebhookSubscription.query.filter_by(
        event_type='task.completed',
        is_active=True
    ).all()
    
    # 各 webhook に対して delivery log を作成
    for webhook in webhooks:
        log = WebhookDeliveryLog(
            webhook_id=webhook.webhook_id,
            event_id=event.event_id,
            attempt_number=1,
            delivery_status='pending'
        )
        db.session.add(log)
    
    db.session.commit()
```

---

#### Task: task.py done フック実装

**ファイル:** `~/.claude/skills/task-manager-sqlite/scripts/task.py` または `webhook_dispatcher.py`

**実装内容:**
1. `task.py done <TASK_ID>` 実行時の フック検出
2. `on_task_completed()` 関数呼び出し
3. SQLite task テーブルからメタデータ抽出

**統合方法:**
```python
# task.py done コマンド実行時
def done(task_id: int):
    """Mark task as done"""
    # 既存: task を completed に変更
    # 追加: イベント発火
    
    task = get_task(task_id)
    update_task_status(task_id, 'completed')
    
    # イベント発火 (NEW)
    from dashboard.events.task_events import on_task_completed
    on_task_completed(
        task_id=task_id,
        executor_user_id=get_current_user_id(),
        completion_time_ms=calculate_completion_time(task)
    )
```

---

## テスト計画

### Unit テスト

```bash
# Engineer #1
pytest tests/test_websocket.py -v
pytest tests/test_webhooks_api.py -v

# Engineer #2
pytest tests/test_db_migration.py -v
pytest tests/test_task_events.py -v
```

### E2E テスト

```bash
# 1. task.py done 実行
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py done 2547

# 2. WebSocket で イベント受信確認
# (client.py で WebSocket コネクト → task.completed イベント待機)

# 3. Webhook 配信確認
# (httpbin.org または local mock server で POST 受信確認)
```

---

## デリバリー チェックリスト

### Engineer #1 デリバリー
- [ ] WebSocket エンドポイント実装完了
  - [ ] JWT 認証機能
  - [ ] task.completed イベント送信
  - [ ] クライアント接続管理
- [ ] Webhook 登録 API 実装完了
  - [ ] POST /api/webhooks/register
  - [ ] DELETE /api/webhooks/{webhook_id}
  - [ ] GET /api/webhooks
  - [ ] シークレット ハッシュ化
- [ ] Unit テスト作成・実行
  - [ ] test_websocket.py (≥80% coverage)
  - [ ] test_webhooks_api.py (≥80% coverage)

### Engineer #2 デリバリー
- [ ] DB マイグレーション実行完了
  - [ ] task_completion_events テーブル作成
  - [ ] webhook_subscriptions テーブル作成
  - [ ] webhook_delivery_logs テーブル作成
  - [ ] インデックス作成
- [ ] イベント検出ロジック実装完了
  - [ ] task.py done フック統合
  - [ ] TaskCompletionEvent レコード作成
  - [ ] WebSocket ブロードキャスト
  - [ ] Webhook 配信キュー登録
- [ ] Unit テスト作成・実行
  - [ ] test_db_migration.py (≥90% coverage)
  - [ ] test_task_events.py (≥85% coverage)

### Tech Lead デリバリー（Design Phase 完了）
- [x] インターフェース仕様書 (`agent_messaging_interface_spec.md`)
- [x] DB マイグレーション計画 (`agent_messaging_db_migration_plan.md`)
- [x] 実装サマリー・委譲指示（本ドキュメント）
- [x] タスク #2547 完了

---

## 参照ドキュメント

| ドキュメント | パス | 責任者 |
|---|---|---|
| インターフェース仕様書 | `docs/design/agent_messaging_interface_spec.md` | Tech Lead |
| DB マイグレーション計画 | `docs/design/agent_messaging_db_migration_plan.md` | Tech Lead |
| 既存 API 設計 | `docs/design/AGENT_TASK_DELEGATION_API.md` | - |
| 既存 WebSocket 実装 | `dashboard/app.py` | Engineer |
| 既存認証実装 | `dashboard/auth.py` | Engineer |

---

**Status:** ✅ 設計完了（Design Phase）→ 実装フェーズへ移行

**Next Step:** Engineer チーム 2 名による実装開始（2026-05-01 予定）
