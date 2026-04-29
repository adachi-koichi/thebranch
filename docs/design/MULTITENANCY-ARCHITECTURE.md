# マルチテナント対応 アーキテクチャ設計書

**対象システム**: THEBRANCH (ai-orchestrator)  
**版**: 1.0  
**作成日**: 2026-04-20  
**著者**: Tech Lead

---

## 目次

1. [概要](#概要)
2. [DB分離戦略](#db分離戦略)
3. [認証・認可設計](#認証認可設計)
4. [データアクセス制御](#データアクセス制御)
5. [推奨実装パターン](#推奨実装パターン)
6. [移行戦略](#移行戦略)

---

## 概要

### マルチテナント化の背景

THEBRANCH は単一組織向けのプロトタイプから、複数の顧客組織を支援するプロダクトへの転換を目指す。

**主要要件:**
- **データ隔離**: 複数組織のデータを同一 DB インスタンスで安全に分離
- **スケーラビリティ**: テナント数増加に対応し、リソース効率化
- **監査・コンプライアンス**: 組織ごとの監査ログ・アクセス制御
- **運用コスト**: 専用 DB の維持コストを最小化しながらセキュリティを確保

### 設計原則

1. **Zero Trust**: テナント情報は常にリクエスト・トークンから確認し、暗黙的に信用しない
2. **Defense in Depth**: DB 層・アプリ層・API 層での多層的データ隔離
3. **監査可能性**: すべてのテナント境界を越えるアクセスをログ記録
4. **段階的導入**: 既存システムの後方互換性を保ちながら段階的に導入

---

## DB分離戦略

### 候補アプローチ比較

| 戦略 | 共有スキーマ | 専用スキーマ | 専用DB |
|-----|----------|----------|-------|
| **実装複雑度** | 低 | 中 | 高 |
| **データ隔離** | アプリ層 | DB層 + アプリ層 | DB層（強固） |
| **スケーラビリティ** | 中（WHERE フィルタ） | 中～高（スキーマ分離） | 高（水平分散） |
| **運用コスト** | 低（1つの DB） | 中（スキーマ管理） | 高（複数 DB インスタンス） |
| **パフォーマンス** | 低（全テーブルをスキャン） | 中（スキーマ分離） | 高（専用リソース） |
| **トランザクション** | 制限なし | 制限なし | クロステナント禁止 |
| **セキュリティ** | 低（アプリバグで漏洩可能） | 中（SQL注入時は隔離） | 高（DB レベルで強制） |

---

## 推奨戦略: 共有スキーマ + テナント ID カラム

### 理由

**初期段階（テナント数: 1～50）での採用を推奨** する。

**メリット:**
- **運用コスト最小**: 単一 SQLite ファイル管理
- **実装がシンプル**: 既存スキーマに `tenant_id` カラムを追加するのみ
- **開発速度**: マルチテナント機能の段階的追加が容易
- **後方互換性**: 既存テーブル・クエリへの影響最小

**デメリット:**
- アプリケーション層での厳密なテナント隔離が必須
- SQL インジェクション・バグが直結して漏洩リスク
- テナント間のリソース競合（大型テナントが小型を圧迫）

**適用条件:**
- テナント数 50 以下の段階
- 信頼性重視より開発速度を優先する初期フェーズ
- 専用 DB への段階的移行を前提

---

### 実装詳細: 共有スキーマアプローチ

#### 1. スキーマ設計

すべてのテーブルに `tenant_id` と `organization_id` カラムを追加する。

**基本テーブル（既存から拡張）:**

```sql
-- 1. organizations テーブル（新規）
CREATE TABLE organizations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  org_id TEXT NOT NULL UNIQUE,           -- 外部識別子（API で使用）
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,             -- URL subdomain 等に使用
  tier TEXT CHECK(tier IN ('free', 'pro', 'enterprise')) DEFAULT 'free',
  status TEXT CHECK(status IN ('active', 'suspended', 'deleted')) DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by TEXT,
  billing_email TEXT,
  metadata TEXT                          -- JSON: カスタム設定
);

CREATE UNIQUE INDEX idx_organizations_org_id ON organizations(org_id);
CREATE UNIQUE INDEX idx_organizations_slug ON organizations(slug);

-- 2. users テーブル（新規またはテナント対応に拡張）
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  org_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  email TEXT NOT NULL,
  password_hash TEXT,
  role TEXT CHECK(role IN ('owner', 'admin', 'member', 'viewer')) DEFAULT 'member',
  status TEXT CHECK(status IN ('active', 'inactive', 'invited', 'deleted')) DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TEXT,
  FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE,
  UNIQUE(org_id, email)
);

CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);

-- 3. 既存テーブル（workflow_instances の例）
ALTER TABLE workflow_instances ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE workflow_instances ADD FOREIGN KEY (org_id) REFERENCES organizations(org_id);

-- tenant_id と org_id の関連付け
CREATE INDEX idx_workflow_instances_org_id ON workflow_instances(org_id);
CREATE UNIQUE INDEX idx_workflow_instances_org_workflow_id ON workflow_instances(org_id, workflow_id);

-- 4. 監査ログテーブル（新規）
CREATE TABLE audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  org_id TEXT NOT NULL,
  user_id TEXT,
  action TEXT NOT NULL,                  -- 'create', 'update', 'delete', 'export'
  resource_type TEXT,                    -- 'task', 'workflow', 'user'
  resource_id INTEGER,
  old_value TEXT,                        -- JSON: 変更前の値
  new_value TEXT,                        -- JSON: 変更後の値
  ip_address TEXT,
  timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE
);

CREATE INDEX idx_audit_logs_org_id ON audit_logs(org_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
```

#### 2. テーブル拡張パターン（他のテーブル）

既存の `workflow_templates`, `dev_tasks`, `agent_assignments` にも適用:

```sql
-- 各テーブル共通のパターン
ALTER TABLE workflow_templates ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE dev_tasks ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE agent_assignments ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default';

-- コンポジットキー制約（テーブルごとに UNIQUE を再定義）
CREATE UNIQUE INDEX idx_workflow_templates_org_name 
  ON workflow_templates(org_id, name);

CREATE UNIQUE INDEX idx_dev_tasks_org_id 
  ON dev_tasks(org_id, id);
```

---

## 認証・認可設計

### 1. テナント識別方法（複合戦略）

#### 方法 1: JWT クレーム（推奨・1次）

```json
{
  "sub": "user-123",
  "org_id": "org-exp-stock",
  "email": "user@example.com",
  "role": "owner",
  "iat": 1713600000,
  "exp": 1713603600
}
```

**メリット:**
- ステートレス（DB クエリ不要）
- サーバー再起動時も有効
- マイクロサービス対応

**実装:**
```python
# JWT デコード・検証
import jwt
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        org_id = payload.get("org_id")
        if not org_id:
            raise ValueError("org_id not found in token")
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

#### 方法 2: HTTP ヘッダー（2次・フォールバック）

リクエストに `X-Org-ID` ヘッダーを含める。JWT に org_id がない場合に使用。

```http
GET /api/tasks HTTP/1.1
X-Org-ID: org-exp-stock
Authorization: Bearer <token>
```

**実装:**
```python
@app.get("/api/tasks")
def list_tasks(
    request: Request,
    org_id_header: str = Header(None, alias="X-Org-ID")
) -> list:
    # JWT から org_id を優先取得
    org_id = request.state.org_id or org_id_header
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id required")
    
    # DB クエリ時に常に org_id でフィルタ
    tasks = db.execute(
        "SELECT * FROM dev_tasks WHERE org_id = ? AND status != 'deleted'",
        (org_id,)
    )
    return tasks
```

#### 方法 3: URL Subdomain（UI 専用・3次）

```
https://exp-stock.thebranch.example.com/dashboard
```

UI のリクエスト時のみ、subdomain から org_id を抽出。

**実装:**
```python
from fastapi import Request

def extract_org_id_from_subdomain(request: Request) -> str:
    host = request.headers.get("Host", "")
    parts = host.split(".")
    if len(parts) > 1 and parts[0] not in ("www", "api", "staging"):
        return parts[0]  # subdomain が org_id
    return None
```

### 2. ユーザーとテナント・組織の関連付けモデル

```
Organization (組織)
  ├─ User 1 (role: owner)
  ├─ User 2 (role: admin)
  └─ User 3 (role: member)

関連付けは users テーブルの org_id FK で管理。
1 ユーザーが複数組織に属することも可能（将来対応）。
```

**現在の実装：1 User ← → 1 Organization**

- JWT の `org_id` はユーザーの所属組織を示す
- ユーザーが複数組織に属する場合は、ログイン時に選択組織を指定

---

### 3. 組織ロール・権限管理

#### ロールモデル（4段階）

| ロール | 説明 | 権限 |
|-------|------|------|
| **owner** | 組織の所有者 | すべて（組織削除も含む） |
| **admin** | 組織管理者 | ユーザー管理・設定変更 |
| **member** | メンバー | プロジェクト・タスク作成・編集 |
| **viewer** | 閲覧者 | 読み取り専用 |

#### 権限マトリックス

```
                    owner  admin  member  viewer
├─ User管理          ✓      ✓      -       -
├─ 組織設定          ✓      ✓      -       -
├─ Project作成       ✓      ✓      ✓       -
├─ Task作成          ✓      ✓      ✓       -
├─ Task編集(自分)    ✓      ✓      ✓       -
├─ Task編集(他人)    ✓      ✓      -       -
├─ 削除              ✓      -      -       -
└─ 読み取り          ✓      ✓      ✓       ✓
```

#### 実装：権限チェック関数

```python
def check_permission(
    org_id: str,
    user_id: str,
    action: str,
    resource_type: str = None
) -> bool:
    """
    権限判定ロジック
    
    Args:
        org_id: 組織 ID
        user_id: ユーザー ID
        action: 'create', 'read', 'update', 'delete'
        resource_type: 'task', 'workflow', 'user', 'organization'
    
    Returns:
        権限あり → True、なし → False
    """
    # 1. ユーザーの役割を取得
    user = db.execute(
        "SELECT role FROM users WHERE org_id = ? AND user_id = ?",
        (org_id, user_id)
    ).fetchone()
    
    if not user:
        return False
    
    role = user["role"]
    
    # 2. 権限マトリックスで判定
    permissions = {
        "owner": ["create", "read", "update", "delete"],
        "admin": ["create", "read", "update"],
        "member": ["create", "read", "update"],
        "viewer": ["read"]
    }
    
    return action in permissions.get(role, [])


# API エンドポイントでの使用例
@app.delete("/api/tasks/{task_id}")
def delete_task(
    task_id: int,
    request: Request
) -> dict:
    org_id = request.state.org_id
    user_id = request.state.user_id
    
    # 権限チェック
    if not check_permission(org_id, user_id, "delete", "task"):
        raise HTTPException(status_code=403, detail="No permission")
    
    # タスク削除
    db.execute(
        "UPDATE dev_tasks SET status = 'deleted' WHERE id = ? AND org_id = ?",
        (task_id, org_id)
    )
    return {"status": "deleted"}
```

---

## データアクセス制御

### 1. Row-Level Security (RLS) vs アプリケーション層隔離

#### 戦略選択: アプリケーション層（推奨）

**理由:**
- SQLite には RLS 機能がない
- Python アプリ層での実装が標準的
- パフォーマンス・柔軟性に優れる

#### 実装パターン

**原則: すべての SELECT / UPDATE / DELETE に `WHERE org_id = ?` 条件を付与**

```python
# ❌ 危険：org_id フィルタなし
def get_tasks():
    return db.execute("SELECT * FROM dev_tasks").fetchall()

# ✅ 推奨：org_id フィルタあり
def get_tasks(org_id: str):
    return db.execute(
        "SELECT * FROM dev_tasks WHERE org_id = ? AND status != 'deleted'",
        (org_id,)
    ).fetchall()
```

---

### 2. API 層でのテナント隔離チェック

#### ミドルウェア実装（FastAPI の例）

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. トークン検証
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing token")
        
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            org_id = payload.get("org_id")
            user_id = payload.get("sub")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # 2. org_id をリクエストのコンテキストに設定
        request.state.org_id = org_id
        request.state.user_id = user_id
        
        # 3. 次のハンドラに渡す
        response = await call_next(request)
        return response

# app に登録
app.add_middleware(TenantIsolationMiddleware)
```

#### エンドポイント実装パターン

```python
from fastapi import Request

@app.get("/api/tasks")
def list_tasks(
    request: Request,
    status: str = None
) -> list:
    org_id = request.state.org_id
    user_id = request.state.user_id
    
    # 権限チェック
    if not check_permission(org_id, user_id, "read", "task"):
        raise HTTPException(status_code=403, detail="No permission")
    
    # org_id でフィルタしたクエリ
    query = "SELECT * FROM dev_tasks WHERE org_id = ? AND status != 'deleted'"
    params = [org_id]
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    tasks = db.execute(query, params).fetchall()
    
    # 監査ログ記録
    log_audit(org_id, user_id, "read_tasks", "task", len(tasks))
    
    return tasks


@app.post("/api/tasks")
def create_task(
    request: Request,
    task_data: dict
) -> dict:
    org_id = request.state.org_id
    user_id = request.state.user_id
    
    # 権限チェック
    if not check_permission(org_id, user_id, "create", "task"):
        raise HTTPException(status_code=403, detail="No permission")
    
    # 作成（org_id 強制）
    result = db.execute(
        """
        INSERT INTO dev_tasks (org_id, title, description, status, created_by)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (org_id, task_data["title"], task_data.get("description"), user_id)
    )
    
    # 監査ログ記録
    log_audit(org_id, user_id, "create_task", "task", result.lastrowid)
    
    return {"id": result.lastrowid, "status": "created"}
```

---

### 3. リソースアクセスの実装パターン

#### タスク取得時の多層チェック

```python
def get_task_with_isolation(
    task_id: int,
    org_id: str,
    user_id: str
) -> dict:
    """
    マルチテナント対応のタスク取得
    
    チェックフロー:
    1. org_id でフィルタ
    2. task が存在するかチェック
    3. ユーザーの権限チェック
    """
    # ステップ 1: org_id フィルタ
    task = db.execute(
        "SELECT * FROM dev_tasks WHERE id = ? AND org_id = ?",
        (task_id, org_id)
    ).fetchone()
    
    if not task:
        # ステップ 2: 存在しない（または別 org）
        raise HTTPException(status_code=404, detail="Task not found")
    
    # ステップ 3: 権限チェック
    if not check_permission(org_id, user_id, "read", "task"):
        # 権限がない場合も 404 で返す（URL enumeration 防止）
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task
```

---

### 4. 監査・ロギング設計

#### 監査ログの記録

```python
def log_audit(
    org_id: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: int,
    old_value: dict = None,
    new_value: dict = None,
    ip_address: str = None
):
    """
    テナント境界を越えるアクセスをログ記録
    """
    import json
    from datetime import datetime
    
    db.execute(
        """
        INSERT INTO audit_logs 
        (org_id, user_id, action, resource_type, resource_id, old_value, new_value, ip_address, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            org_id,
            user_id,
            action,
            resource_type,
            resource_id,
            json.dumps(old_value) if old_value else None,
            json.dumps(new_value) if new_value else None,
            ip_address,
            datetime.utcnow().isoformat()
        )
    )
    db.commit()


# FastAPI でリモート IP を取得
def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

# ミドルウェアで IP をリクエストに追加
request.state.client_ip = get_client_ip(request)
```

#### 監査ログクエリ例

```python
def get_audit_logs(
    org_id: str,
    start_date: str = None,
    end_date: str = None,
    user_id: str = None
) -> list:
    """
    監査ログの検索（組織内のみ）
    """
    query = "SELECT * FROM audit_logs WHERE org_id = ?"
    params = [org_id]
    
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)
    
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    
    query += " ORDER BY timestamp DESC LIMIT 1000"
    
    return db.execute(query, params).fetchall()
```

---

## 推奨実装パターン

### マルチテナント対応チェックリスト（実装順）

#### フェーズ 1: スキーマ拡張（Week 1）
- [ ] `organizations` テーブル作成
- [ ] `users` テーブル作成
- [ ] `audit_logs` テーブル作成
- [ ] 既存テーブルに `org_id` カラム追加
- [ ] インデックス作成

#### フェーズ 2: 認証・認可（Week 2）
- [ ] JWT トークンに `org_id` 追加
- [ ] TenantIsolationMiddleware 実装
- [ ] `check_permission()` 実装
- [ ] ロールベースアクセス制御（RBAC）

#### フェーズ 3: API 隔離（Week 3）
- [ ] すべてのエンドポイントに `org_id` フィルタ追加
- [ ] 権限チェックを API 層に統合
- [ ] テスト（クロステナント攻撃シナリオ）

#### フェーズ 4: 監査・ロギング（Week 4）
- [ ] 監査ログシステム実装
- [ ] ダッシュボード UI で監査ログ表示
- [ ] 定期的な監査ログ確認手順

---

### セキュリティベストプラクティス

#### チェック項目

```
□ SQL インジェクション対策
  → すべてのクエリで parameterized queries 使用
  
□ 認可漏れ対策
  → すべての エンドポイントで `check_permission()` 呼び出し
  
□ クロステナント攻撃対策
  → 存在しないリソースと権限なしリソースの区別なし
  → ステータス 404 で統一（URL enumeration 防止）
  
□ 監査ログ改ざん対策
  → 監査ログは append-only
  → ユーザーは削除・編集不可
  
□ トークン漏洩対策
  → JWT は HTTPS のみ
  → Cookie 設定: HttpOnly / Secure
```

---

## 移行戦略

### フェーズ別実装（既存システムとの互換性維持）

#### Phase 1: 単一テナント（現在）
- org_id = "default" で全データを扱う
- 既存 API は変更なし

#### Phase 2: マルチテナント準備
- スキーマ拡張（org_id カラム追加）
- 既存データを org_id = "default" で移行
- 新規 API は org_id フィルタ対応

#### Phase 3: 段階的テナント導入
- 新規顧客を org_id を指定して作成
- 既存顧客は org_id = "default" で運用継続
- 混在運用（2～3 ヶ月）

#### Phase 4: 全 API マルチテナント対応
- すべてのエンドポイントで org_id チェック
- 既存顧客の明示的な migration 実施

---

## 実装例：タスク作成エンドポイント（フル実装）

```python
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
import jwt

app = FastAPI()

SECRET_KEY = "your-secret-key"

class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[int] = 1

@app.post("/api/tasks")
def create_task(
    request: Request,
    task_data: TaskCreateRequest
) -> dict:
    """
    タスク作成エンドポイント（マルチテナント対応）
    
    フロー:
    1. トークン検証（org_id 取得）
    2. 権限チェック
    3. 入力検証
    4. DB 插入（org_id 強制）
    5. 監査ログ記録
    6. レスポンス返却
    """
    # 1. org_id・user_id をリクエストから取得（ミドルウェアで設定済み）
    org_id = request.state.org_id
    user_id = request.state.user_id
    client_ip = request.client.host if request.client else "unknown"
    
    # 2. 権限チェック
    if not check_permission(org_id, user_id, "create", "task"):
        raise HTTPException(status_code=403, detail="No permission to create tasks")
    
    # 3. 入力検証
    if not task_data.title or len(task_data.title) < 3:
        raise HTTPException(status_code=400, detail="Invalid task title")
    
    # 4. DB 插入（org_id は絶対に強制）
    try:
        result = db.execute(
            """
            INSERT INTO dev_tasks 
            (org_id, title, description, priority, status, created_by, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?, datetime('now'))
            """,
            (org_id, task_data.title, task_data.description, task_data.priority, user_id)
        )
        db.commit()
        task_id = result.lastrowid
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create task")
    
    # 5. 監査ログ記録
    log_audit(
        org_id=org_id,
        user_id=user_id,
        action="create_task",
        resource_type="task",
        resource_id=task_id,
        new_value=task_data.dict(),
        ip_address=client_ip
    )
    
    # 6. レスポンス返却
    return {
        "id": task_id,
        "status": "created",
        "org_id": org_id,
        "title": task_data.title
    }
```

---

## まとめ

### 推奨アーキテクチャ

| レイヤ | 戦略 | 実装 |
|-------|------|------|
| **DB** | 共有スキーマ + org_id | SQLite 単一ファイル |
| **認証** | JWT + org_id クレーム | FastAPI ミドルウェア |
| **認可** | RBAC（4ロール） | check_permission() 関数 |
| **隔離** | アプリケーション層（org_id フィルタ） | 全エンドポイント対応 |
| **監査** | 専用ログテーブル | audit_logs 記録 |

### 段階的導入

1. **Week 1-2**: スキーマ + 認証・認可 (Phases 1-2)
2. **Week 3-4**: API 隔離 + 監査ログ (Phase 3)
3. **Week 5+**: 本番テナント運用 (Phase 4)

この戦略により、**セキュリティと運用コストのバランス**を取りながら、段階的にマルチテナント化を進めることができます。
