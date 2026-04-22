# 認証・マルチテナント・セッション管理 設計書

**タスク**: #2412  
**対象システム**: THEBRANCH (部署ダッシュボード)  
**版**: 1.0  
**作成日**: 2026-04-20  
**著者**: Tech Lead

---

## 目次

1. [概要](#概要)
2. [DB スキーマ設計](#db-スキーマ設計)
3. [認証フロー](#認証フロー)
4. [テナント分離戦略](#テナント分離戦略)
5. [セッション管理](#セッション管理)
6. [実装チェックリスト](#実装チェックリスト)

---

## 概要

### 目的

単一ユーザー向けプロトタイプから、**複数ユーザーが複数部署を管理できるマルチテナントシステム**へ進化させる。

### 要件

- ✅ ユーザー単位の認証（ログイン・セッション管理）
- ✅ ユーザーIDをテナント識別子として使用
- ✅ 部署ごとのデータ隔離（他のユーザーのデータにアクセス不可）
- ✅ セッション有効期限管理（7日間）
- ✅ パスワード安全性（PBKDF2 + Salt）

### 設計原則

1. **Zero Trust**: すべてのリクエストで現在のユーザーIDを検証
2. **Defense in Depth**: DB層・アプリ層での複数チェック
3. **シンプルさ**: 初期段階では単一ユーザー = 1つのテナント

---

## DB スキーマ設計

### テーブル構成

#### 1. users テーブル

**用途**: ユーザー認証・管理

```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

**カラム説明**

| カラム | 型 | 説明 |
|-------|-----|------|
| `id` | TEXT (PRIMARY KEY) | ユーザー一意識別子（8バイト HEX） |
| `username` | TEXT (UNIQUE) | ログイン用ユーザー名 |
| `email` | TEXT (UNIQUE) | メールアドレス（パスワード再設定用） |
| `password_hash` | TEXT | PBKDF2 ハッシュ化パスワード |
| `created_at` | TIMESTAMP | アカウント作成日時 |
| `updated_at` | TIMESTAMP | 最終更新日時 |

**テナント識別**: `user_id` = テナント識別子

---

#### 2. departments テーブル

**用途**: ユーザーが管理する部署データ（マルチテナント）

```sql
CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, slug)
);

-- インデックス
CREATE INDEX idx_departments_user_id ON departments(user_id);
CREATE INDEX idx_departments_status ON departments(status);
```

**カラム説明**

| カラム | 型 | 説明 |
|-------|-----|------|
| `id` | INTEGER | 部署ID（自動採番） |
| `user_id` | TEXT (FK) | 所有ユーザーID（テナント識別） |
| `name` | TEXT | 部署名 |
| `slug` | TEXT | URL用スラッグ |
| `description` | TEXT | 部署説明 |
| `status` | TEXT | 状態（active/archived） |
| `created_at` | TIMESTAMP | 作成日時 |
| `updated_at` | TIMESTAMP | 更新日時 |

**テナント分離**: `departments` テーブルのすべてのクエリに `WHERE user_id = ?` 条件

---

#### 3. sessions テーブル

**用途**: ユーザーセッション管理（トークンベース）

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    user_id TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- インデックス
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
```

**カラム説明**

| カラム | 型 | 説明 |
|-------|-----|------|
| `id` | TEXT | セッション記録ID |
| `user_id` | TEXT (FK) | ユーザーID |
| `token` | TEXT (UNIQUE) | セッショントークン（URLsafe Base64） |
| `expires_at` | TIMESTAMP | トークン有効期限（発行日 + 7日） |
| `created_at` | TIMESTAMP | セッション作成日時 |

**有効期限**: 7日間（ログイン時に自動計算）

---

### 既存テーブルとの関係

```
users (テナント親)
  ├─ id = テナント識別子
  ├─ departments (user_id FK)
  ├─ sessions (user_id FK)
  ├─ agents (department_id FK → department.user_id)
  ├─ teams (department_id FK → department.user_id)
  └─ missions (agent_id FK → agent.department_id)
```

---

## 認証フロー

### フロー図（テキスト）

```
┌─ サインアップ ─────────────────────────────────────────┐
│ 1. ユーザー入力 (username, email, password)
│ 2. バリデーション (email format, password strength)
│ 3. パスワードハッシング (PBKDF2 + Salt)
│ 4. DB INSERT (users table)
│ 5. レスポンス: user_id
└───────────────────────────────────────────────────────┘
              ↓
┌─ ログイン ───────────────────────────────────────────────┐
│ 1. ユーザー入力 (username, password)
│ 2. SELECT FROM users WHERE username = ?
│ 3. パスワード検証 (verify_password)
│ 4. 認証成功 → token 生成 (secrets.token_urlsafe)
│ 5. INSERT INTO sessions (user_id, token, expires_at)
│ 6. レスポンス: {token, user_id, expires_at}
└───────────────────────────────────────────────────────┘
              ↓
┌─ リクエスト ────────────────────────────────────────────┐
│ 1. リクエストヘッダ: Authorization: Bearer <token>
│ 2. Token 検証 (verify_token in sessions)
│ 3. user_id 抽出
│ 4. テナント検証 (request.state.user_id = extracted user_id)
│ 5. DB クエリ実行 (WHERE user_id = extracted_user_id)
│ 6. レスポンス返却
└───────────────────────────────────────────────────────┘
```

### ステップ別実装

#### ステップ 1: サインアップ

**入力**: `username`, `email`, `password`

```python
async def create_user(username: str, email: str, password: str) -> Tuple[bool, str]:
    # 1. バリデーション
    if not re.match(r"^[a-zA-Z0-9_]{3,20}$", username):
        return False, "Username invalid"
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return False, "Email invalid"
    if len(password) < 8:
        return False, "Password too short"
    
    # 2. パスワードハッシング
    hashed = hash_password(password)
    
    # 3. DB INSERT
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, hashed)
            )
            await db.commit()
            return True, "User created"
    except sqlite3.IntegrityError:
        return False, "User already exists"
```

---

#### ステップ 2: ログイン

**入力**: `username`, `password`  
**出力**: `token`, `user_id`, `expires_at`

```python
async def authenticate_user(username: str, password: str) -> Tuple[Optional[str], Optional[str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. ユーザー取得
        cursor = await db.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,)
        )
        user = await cursor.fetchone()
        
        # 2. パスワード検証
        if not user or not verify_password(password, user[1]):
            return None, None
        
        # 3. トークン生成
        user_id = user[0]
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # 4. セッション登録
        await db.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at)
        )
        await db.commit()
        
        return user_id, token
```

---

#### ステップ 3: トークン検証

**入力**: `token`  
**出力**: `user_id` (有効なら) / `None` (無効なら)

```python
async def verify_token(token: str) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token,)
        )
        result = await cursor.fetchone()
        return result[0] if result else None
```

---

### リクエスト時のテナント検証（ミドルウェア）

```python
from fastapi import Request, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Authorization ヘッダから token 抽出
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing token")
        
        token = auth_header.split(" ")[1]
        
        # 2. token 検証 → user_id 取得
        user_id = await verify_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # 3. request コンテキストに user_id をセット
        request.state.user_id = user_id
        
        # 4. 次のハンドラへ
        response = await call_next(request)
        return response

# FastAPI に登録
app.add_middleware(TenantIsolationMiddleware)
```

---

## テナント分離戦略

### 原則

**すべてのクエリに `WHERE user_id = request.state.user_id` 条件を強制**

### 実装パターン

#### ❌ 危険：テナント分離なし

```python
@app.get("/api/departments")
async def get_departments():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM departments")
        return await cursor.fetchall()
    # → 全ユーザーのデータが見える！
```

---

#### ✅ 推奨：テナント分離あり

```python
@app.get("/api/departments")
async def get_departments(request: Request):
    user_id = request.state.user_id
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM departments WHERE user_id = ?",
            (user_id,)
        )
        return await cursor.fetchall()
    # → 現在のユーザーのみのデータが見える
```

---

### エンドポイント チェックリスト

すべてのエンドポイントに以下を適用：

```python
@app.post("/api/departments")
async def create_department(
    request: Request,
    dept_data: DepartmentCreate
) -> dict:
    user_id = request.state.user_id
    
    # 必ず user_id を強制
    result = await db.execute(
        """
        INSERT INTO departments (user_id, name, slug, description)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, dept_data.name, dept_data.slug, dept_data.description)
    )
    
    return {"id": result.lastrowid, "user_id": user_id}
```

**テナント分離のポイント:**

| 操作 | パターン |
|------|---------|
| **SELECT** | `WHERE user_id = ?` |
| **INSERT** | `user_id = ?` を強制 |
| **UPDATE** | `WHERE user_id = ? AND id = ?` |
| **DELETE** | `WHERE user_id = ? AND id = ?` |

---

## セッション管理

### 有効期限管理

**発行**: ログイン時に自動計算  
**有効期限**: 7日間

```python
expires_at = datetime.utcnow() + timedelta(days=7)
```

### 自動クリーンアップ

期限切れセッションを定期削除

```python
async def cleanup_expired_sessions():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM sessions WHERE expires_at < datetime('now')"
        )
        await db.commit()
```

**実行頻度**: 1日1回（夜間）

### トークンリボケーション

ログアウト時にセッション削除

```python
@app.post("/api/logout")
async def logout(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
            await db.commit()
    
    return {"status": "logged_out"}
```

---

## 実装チェックリスト

### Phase 1: DB スキーマ（Week 1）

- [ ] `users` テーブル作成 (001_create_auth_tables.sql)
- [ ] `sessions` テーブル作成
- [ ] `departments` テーブル作成（user_id FK）
- [ ] インデックス作成（user_id, token, expires_at）
- [ ] マイグレーション実行確認

### Phase 2: 認証 API（Week 1-2）

- [ ] `/api/auth/signup` エンドポイント実装
- [ ] `/api/auth/login` エンドポイント実装
- [ ] `/api/auth/logout` エンドポイント実装
- [ ] パスワードハッシング (PBKDF2)
- [ ] トークン検証ロジック
- [ ] ミドルウェア実装 (TenantIsolationMiddleware)

### Phase 3: テナント分離（Week 2-3）

- [ ] すべての SELECT に `WHERE user_id = ?` 追加
- [ ] すべての INSERT に `user_id` 強制
- [ ] すべての UPDATE に `WHERE user_id = ?` 追加
- [ ] すべての DELETE に `WHERE user_id = ?` 追加
- [ ] エンドポイントのテスト（クロステナント攻撃シナリオ）

### Phase 4: セッション・保守（Week 3-4）

- [ ] セッション有効期限チェック
- [ ] 期限切れセッションの自動削除
- [ ] ログアウト時のトークンリボケーション
- [ ] クッキー設定: HttpOnly / Secure

---

## セキュリティ要件

### 実装時に確認すべき項目

```
□ SQL インジェクション対策
  → すべてのクエリで Parameterized Queries 使用
  
□ テナント漏洩対策
  → 存在しないリソースと権限なしリソースの区別なし（404で統一）
  
□ パスワード安全性
  → PBKDF2 (SHA256, 100,000 iterations) 使用
  → 最小8文字
  
□ トークン漏洩対策
  → HTTPS のみで通信
  → Cookie: HttpOnly / Secure 設定
  
□ セッション固定攻撃対策
  → トークン有効期限: 7日
  → ログアウト時にセッション削除
```

---

## 今後の拡張

### 複数ユーザーによる部署共有

```sql
-- user-department 関連付けテーブル
CREATE TABLE department_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK(role IN ('owner', 'admin', 'member')),
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(department_id, user_id)
);
```

### オーガニゼーション（組織）対応

既存の `MULTITENANCY-ARCHITECTURE.md` を参照して、複数ユーザーの複数部署管理に対応

---

## まとめ

### アーキテクチャ図

```
┌─────────────────────────────────────────────┐
│ Client (Web Browser / API)                  │
└──────────────────┬──────────────────────────┘
                   │ HTTP + Authorization token
                   ↓
┌─────────────────────────────────────────────┐
│ FastAPI Middleware                          │
│ - Token 検証                                │
│ - user_id 抽出                              │
│ - request.state.user_id セット              │
└──────────────────┬──────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────┐
│ API Endpoints                               │
│ - user_id = request.state.user_id           │
│ - WHERE user_id = ? (すべてのクエリ)        │
└──────────────────┬──────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────┐
│ SQLite Database                             │
│ - users (id, username, email, password_hash)│
│ - sessions (user_id, token, expires_at)    │
│ - departments (user_id, name, ...)         │
│ - (その他 テナント対応テーブル)             │
└─────────────────────────────────────────────┘
```

### 実装順序

1. **スキーマ作成**: users, sessions, departments テーブル
2. **認証 API**: signup, login, logout エンドポイント
3. **ミドルウェア**: TenantIsolationMiddleware
4. **エンドポイント**: すべてに テナント分離チェック
5. **テスト**: セキュリティテスト（クロステナント攻撃）

---

**次のステップ**: PHASE 2 実装（認証 API の開発）
