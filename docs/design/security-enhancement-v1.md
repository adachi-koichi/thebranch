# セキュリティ強化・ゼロトラスト実装 v1 設計書

**タスク #2525 / #2751**  
**最終更新:** 2026-04-24  
**ステータス:** 実装準備中

---

## 概要

THEBRANCHのセキュリティを強化し、エンタープライズレベルの信頼性を実現する包括的なセキュリティ実装。

- **APIトークン管理**: パーソナルアクセストークン、スコープ制限、有効期限
- **セッション管理強化**: 非アクティブタイムアウト、同時セッション制限、強制ログアウト
- **2FA（二要素認証）**: TOTP（Google Authenticator）、バックアップコード
- **ゼロトラスト原則**: 全API認証・認可検証、最小権限

---

## 1. DB スキーマ設計

### 1.1 API Token テーブル

```sql
CREATE TABLE api_tokens (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  scope TEXT NOT NULL,  -- 'read', 'write', 'admin' のカンマ区切り
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_used_at DATETIME,
  expires_at DATETIME,
  is_revoked INTEGER DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_api_tokens_user_id ON api_tokens(user_id);
CREATE INDEX idx_api_tokens_token ON api_tokens(token);
```

### 1.2 Session テーブル拡張

```sql
ALTER TABLE sessions ADD COLUMN last_activity_at DATETIME;
ALTER TABLE sessions ADD COLUMN ip_address TEXT;
ALTER TABLE sessions ADD COLUMN user_agent TEXT;
ALTER TABLE sessions ADD COLUMN is_forced_logout INTEGER DEFAULT 0;

CREATE INDEX idx_sessions_last_activity ON sessions(last_activity_at);
```

### 1.3 2FA テーブル

```sql
CREATE TABLE totp_secrets (
  id TEXT PRIMARY KEY,
  user_id TEXT UNIQUE NOT NULL,
  secret TEXT NOT NULL,
  backup_codes TEXT NOT NULL,  -- JSON形式
  is_enabled INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  enabled_at DATETIME,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_totp_secrets_user_id ON totp_secrets(user_id);
```

---

## 2. API 設計

### 2.1 APIトークン管理エンドポイント

#### POST /api/tokens
パーソナルアクセストークンを発行。

```json
Request:
{
  "name": "GitHub Integration",
  "scope": ["read", "write"],
  "expires_in_days": 90
}

Response:
{
  "id": "pat_xxx",
  "token": "thebranch_xxx",
  "scope": ["read", "write"],
  "created_at": "2026-04-24T02:17:01Z",
  "expires_at": "2026-07-23T02:17:01Z"
}
```

#### GET /api/tokens
ユーザーが保有するトークン一覧を取得。

```json
Response:
[
  {
    "id": "pat_xxx",
    "name": "GitHub Integration",
    "scope": ["read", "write"],
    "created_at": "2026-04-24T02:17:01Z",
    "last_used_at": "2026-04-24T02:00:00Z",
    "expires_at": "2026-07-23T02:17:01Z"
  }
]
```

#### DELETE /api/tokens/{token_id}
トークンを取り消し。

```json
Response:
{
  "message": "Token revoked successfully"
}
```

### 2.2 セッション管理エンドポイント

#### GET /api/sessions
アクティブなセッション一覧を取得。

```json
Response:
[
  {
    "id": "sess_xxx",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "created_at": "2026-04-24T01:00:00Z",
    "last_activity_at": "2026-04-24T02:15:00Z",
    "expires_at": "2026-05-01T01:00:00Z"
  }
]
```

#### POST /api/sessions/{session_id}/force-logout
セッションを強制ログアウト。

```json
Response:
{
  "message": "Session terminated"
}
```

### 2.3 2FA エンドポイント

#### POST /api/2fa/enable
TOTP 2FA を有効化（初回設定）。

```json
Request:
{
  "user_id": "user_xxx"
}

Response:
{
  "secret": "JBSWY3DPEBLW64TMMQ======",
  "qr_code": "data:image/png;base64,..."
  "backup_codes": ["code1", "code2", ...]
}
```

#### POST /api/2fa/verify
TOTP トークンを検証。

```json
Request:
{
  "totp_code": "123456"
}

Response:
{
  "verified": true
}
```

#### DELETE /api/2fa/disable
TOTP 2FA を無効化。

```json
Request:
{
  "password": "user_password"  // 確認のためパスワード要求
}

Response:
{
  "message": "2FA disabled"
}
```

---

## 3. 実装方針

### 3.1 auth.py 追加関数

```python
# API Token Management
async def create_api_token(user_id: str, name: str, scope: list, expires_in_days: int = 90) -> dict
async def revoke_api_token(token_id: str) -> Tuple[bool, str]
async def verify_api_token(token: str) -> Tuple[Optional[str], Optional[list]]  # (user_id, scope)
async def list_api_tokens(user_id: str) -> list

# Session Management
async def session_timeout(timeout_minutes: int = 30) -> Tuple[int, list]  # (cleaned_count, expired_session_ids)
async def enforce_max_sessions(user_id: str, max_sessions: int = 3) -> list  # (revoked_session_ids)
async def list_active_sessions(user_id: str) -> list
async def force_logout_session(session_id: str) -> Tuple[bool, str]

# 2FA Management
async def enable_2fa(user_id: str) -> Tuple[str, str, list]  # (secret, qr_code_base64, backup_codes)
async def verify_2fa_token(user_id: str, totp_code: str) -> Tuple[bool, str]
async def disable_2fa(user_id: str, password: str) -> Tuple[bool, str]
```

### 3.2 app.py ゼロトラスト実装

#### @require_auth デコレータ

```python
from functools import wraps

def require_auth(required_scope: Optional[list] = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, authorization: Optional[str] = Header(None), **kwargs):
            if not authorization:
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            user_id, scopes = await verify_api_token(authorization)
            if not user_id:
                raise HTTPException(status_code=403, detail="Invalid token")
            
            if required_scope and not any(s in scopes for s in required_scope):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await func(*args, user_id=user_id, **kwargs)
        return wrapper
    return decorator
```

#### リソースベース アクセス制御

```python
def can_access_resource(user_id: str, resource_id: str, resource_type: str, action: str) -> bool:
    # リソース所有者確認 → owner のみ access
    # グループメンバー確認 → group の場合 member が access
    # 権限確認 → role ベース
    pass
```

### 3.3 セッション タイムアウト実装

- 非アクティブ 30分 → 自動ログアウト
- 同時セッション数制限: 1ユーザーあたり最大 3個
- last_activity_at を API リクエスト毎に更新

---

## 4. ミグレーション計画

### 4.1 マイグレーションファイル

```
dashboard/migrations/
├── 024_create_api_tokens_table.sql
├── 025_extend_sessions_table.sql
├── 026_create_totp_secrets_table.sql
└── 027_zero_trust_indexes.sql
```

### 4.2 既存データ対応

- 既存セッション: is_forced_logout = 0 (デフォルト)
- API トークン: 既存 API キー を api_tokens に マイグレート（optional）

---

## 5. セキュリティレビューチェックリスト

- [ ] トークン保存: DB で暗号化 (ハッシュ化) 保存
- [ ] パスワード: PBKDF2-SHA256 + salt （既存）
- [ ] TOTP: pyotp ライブラリ（RFC 6238）
- [ ] バックアップコード: 1回限りの使用
- [ ] レート制限: ブルートフォース対策（attempt counter）
- [ ] HTTPS強制: 本番環境
- [ ] CORS: Authorization ヘッダ許可
- [ ] ログ: セキュリティイベント（login, logout, token revoke）

---

## 6. テスト戦略

### 6.1 単体テスト

- Token 発行・検証
- Session タイムアウト
- TOTP 生成・検証
- Scope ベース アクセス制御

### 6.2 統合テスト

- APIトークン → API呼び出し
- 同時セッション制限
- 2FA 有効化・無効化フロー

### 6.3 E2E テスト

- ブラウザで TOTP QR コード スキャン
- セッション タイムアウト 確認
- 強制ログアウト 動作

---

## 7. 実装タスク分割

| Task ID | タイトル | 依存 | 担当 |
|---------|---------|------|------|
| 2751 | 設計・API仕様 | - | Tech Lead |
| 2752 | APIトークン実装 | 2751 | Engineer #1 |
| 2753 | セッション管理実装 | 2751 | Engineer #2 |
| 2754 | 2FA 実装 | 2751 | Engineer #3 |
| 2755 | ゼロトラスト実装 | 2752 | Engineer #1 |
| 2756 | テスト・検証 | 2752+ | QA |

---

## 8. スケジュール（目安）

- **設計**: 1日 (2026-04-24)
- **実装**: 3日 (2026-04-25～27)
- **テスト・レビュー**: 1日 (2026-04-28)
- **本番デプロイ**: 2026-04-29

---

## 参考資料

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- Google Authenticator (TOTP): RFC 6238
- JWT Best Practices: https://tools.ietf.org/html/rfc7519

