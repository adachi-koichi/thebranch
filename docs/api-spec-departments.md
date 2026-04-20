# 部署管理バックエンド API 仕様書

**作成日**: 2026-04-20  
**バージョン**: v1.0  
**Tech Lead**: 初期設計フェーズ  
**対応**: architecture-design.md, data-model.md に基づく

---

## 目次

1. [概要](#概要)
2. [REST API エンドポイント](#rest-api-エンドポイント)
3. [データモデル](#データモデル)
4. [リクエスト・レスポンス形式](#リクエストレスポンス形式)
5. [HTTP ステータスコード](#http-ステータスコード)
6. [エラーハンドリング](#エラーハンドリング)
7. [KuzuDB グラフスキーマ](#kuzudb-グラフスキーマ)

---

## 概要

THEBRANCH の部署管理システムは、組織内の部署を CRUD で管理し、部署とエージェント・チームの関係性をグラフDBで追跡するシステムです。

### 主要機能
- **部署 CRUD**: 部署の作成・読取・更新・削除
- **エージェント管理**: 部署に属するエージェントの管理
- **グラフ関係管理**: KuzuDB で部署間・部署とエージェント間の関係を追跡
- **永続化**: SQLite で部署・エージェント・チーム情報を管理

---

## REST API エンドポイント

### 1. 部署管理 API

| メソッド | エンドポイント | 説明 | 認可 |
|---------|---|------|------|
| **POST** | `/api/departments` | 新規部署を作成 | orchestrator, pm |
| **GET** | `/api/departments` | 部署一覧を取得 | all |
| **GET** | `/api/departments/{id}` | 部署詳細を取得 | all |
| **PUT** | `/api/departments/{id}` | 部署を更新 | orchestrator, pm |
| **DELETE** | `/api/departments/{id}` | 部署を削除 | orchestrator |

### 2. 部署内エージェント管理 API

| メソッド | エンドポイント | 説明 | 認可 |
|---------|---|------|------|
| **POST** | `/api/departments/{id}/agents` | エージェントを部署に追加 | orchestrator, pm |
| **GET** | `/api/departments/{id}/agents` | 部署内エージェント一覧 | all |
| **DELETE** | `/api/departments/{id}/agents/{agent_id}` | エージェントを部署から削除 | orchestrator, pm |

### 3. 部署間関係管理 API

| メソッド | エンドポイント | 説明 | 認可 |
|---------|---|------|------|
| **POST** | `/api/departments/{id}/relations` | 部署間関係を作成 | orchestrator, pm |
| **GET** | `/api/departments/{id}/relations` | 部署の関連部署を取得 | all |
| **DELETE** | `/api/departments/{id}/relations/{related_dept_id}` | 部署間関係を削除 | orchestrator |

### 4. チーム管理 API

| メソッド | エンドポイント | 説明 | 認可 |
|---------|---|------|------|
| **POST** | `/api/departments/{id}/teams` | チームを作成 | orchestrator, pm |
| **GET** | `/api/departments/{id}/teams` | 部署内チーム一覧 | all |
| **GET** | `/api/departments/{id}/teams/{team_id}` | チーム詳細を取得 | all |
| **PUT** | `/api/departments/{id}/teams/{team_id}` | チームを更新 | orchestrator, pm |
| **DELETE** | `/api/departments/{id}/teams/{team_id}` | チームを削除 | orchestrator |

---

## データモデル

### ER 図（SQLite スキーマ）

```
┌──────────────────────────────────────────────────────────────────┐
│                     部署・チーム管理層                              │
│                                                                  │
│  ┌──────────────────┐                  ┌──────────────────────┐ │
│  │    departments   │                  │ department_agents   │ │
│  │                  │                  │  （中間テーブル）      │ │
│  │ id (PK)          │◄────1:N─────────►│ department_id (FK)  │ │
│  │ name             │                  │ agent_id (FK)       │ │
│  │ slug             │                  │ role                │ │
│  │ description      │                  │ joined_at           │ │
│  │ parent_id (FK)   │                  └──────────────────────┘ │
│  │ budget           │                          ▲                 │
│  │ status           │                          │                 │
│  │ created_at       │                          │ (agents.id)     │
│  └──────┬───────────┘                          │                 │
│         │                    ┌─────────────────┴──────────┐      │
│         │                    │                            │      │
│         │ 1:N                ▼                            │      │
│         │            ┌──────────────────────────────┐    │      │
│         │            │         teams                │    │      │
│         │            │                              │    │      │
│         │            │ id (PK)                      │    │      │
│         │            │ department_id (FK)           │◄───┘      │
│         │            │ name                         │            │
│         │            │ description                  │            │
│         │            │ status (active/inactive)    │            │
│         │            │ created_at                   │            │
│         │            └──────┬───────────────────────┘            │
│         │                   │                                    │
│         │                   │ 1:N                                │
│         │                   ▼                                    │
│         │         ┌────────────────────────┐                    │
│         │         │   team_x_agents       │                    │
│         │         │  （中間テーブル）       │                    │
│         │         │ team_id (FK)           │                    │
│         │         │ agent_id (FK)          │                    │
│         │         └────────────────────────┘                    │
│         │                                                        │
│  ┌──────▼───────────────────┐                                  │
│  │ department_relations     │                                  │
│  │                          │                                  │
│  │ id (PK)                  │                                  │
│  │ dept_a_id (FK)           │                                  │
│  │ dept_b_id (FK)           │                                  │
│  │ relation_type (parent... │                                  │
│  │ created_at               │                                  │
│  └──────────────────────────┘                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     エージェント・ペルソナ層                        │
│                                                                  │
│  ┌──────────────────────────┐                                  │
│  │       agents             │                                  │
│  │                          │                                  │
│  │ id (PK)                  │                                  │
│  │ slug (unique)            │                                  │
│  │ name                      │                                  │
│  │ role_type (em/engineer...) │                               │
│  │ specialty                 │                                  │
│  │ status (active/inactive)  │                                  │
│  │ created_at                │                                  │
│  └──────────────────────────┘                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### テーブル仕様

#### `departments` - 部署マスタ

```sql
CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,              -- 部署名（例: "Data Team"）
    slug        TEXT NOT NULL UNIQUE,              -- URL用スラッグ（例: "data-team"）
    description TEXT,                             -- 部署説明
    parent_id   INTEGER REFERENCES departments(id), -- 親部署 ID (NULL = トップレベル)
    budget      REAL,                             -- 予算（単位: 万円）
    status      TEXT DEFAULT 'active',            -- active / inactive / archived
    created_by  TEXT,                             -- 作成者ユーザー名
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_departments_status ON departments(status);
CREATE INDEX IF NOT EXISTS idx_departments_parent_id ON departments(parent_id);
CREATE INDEX IF NOT EXISTS idx_departments_created_at ON departments(created_at);
```

**カラム説明**:
- `slug`: REST API で使用（例: `/api/departments/data-team`）
- `parent_id`: 組織の階層構造を表現（例: "Data Team" の親は "Engineering"）
- `budget`: 部署の運営予算
- `status`: ライフサイクル管理（active=稼働中, inactive=休止, archived=廃止）

#### `department_agents` - 部署とエージェント（中間テーブル）

```sql
CREATE TABLE IF NOT EXISTS department_agents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    agent_id      INTEGER NOT NULL REFERENCES agents(id),
    role          TEXT NOT NULL,                  -- 部署内での役割（lead, member, consultant）
    joined_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    left_at       TEXT,                           -- 部署を離れた時刻
    UNIQUE(department_id, agent_id)               -- 1 agent は1 dept に1回だけ属する
);

CREATE INDEX IF NOT EXISTS idx_department_agents_department_id 
  ON department_agents(department_id);
CREATE INDEX IF NOT EXISTS idx_department_agents_agent_id 
  ON department_agents(agent_id);
CREATE INDEX IF NOT EXISTS idx_department_agents_role 
  ON department_agents(role);
```

**カラム説明**:
- `role`: 部署内での職務（lead=リード, member=メンバー, consultant=相談役）
- `left_at`: エージェントが部署を離れた時刻（NULL = 現在も属している）

#### `teams` - チーム管理

```sql
CREATE TABLE IF NOT EXISTS teams (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    name          TEXT NOT NULL,                  -- チーム名（例: "Backend Team"）
    slug          TEXT NOT NULL,                  -- URL用スラッグ
    description   TEXT,                           -- チーム説明
    status        TEXT DEFAULT 'active',          -- active / inactive
    created_by    TEXT,                           -- 作成者
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(department_id, slug)                   -- 部署内で slug は一意
);

CREATE INDEX IF NOT EXISTS idx_teams_department_id ON teams(department_id);
CREATE INDEX IF NOT EXISTS idx_teams_status ON teams(status);
```

#### `team_x_agents` - チームとエージェント（中間テーブル）

```sql
CREATE TABLE IF NOT EXISTS team_x_agents (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id  INTEGER NOT NULL REFERENCES teams(id),
    agent_id INTEGER NOT NULL REFERENCES agents(id),
    role     TEXT,                                -- チーム内の役割
    joined_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(team_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_team_x_agents_team_id ON team_x_agents(team_id);
CREATE INDEX IF NOT EXISTS idx_team_x_agents_agent_id ON team_x_agents(agent_id);
```

#### `department_relations` - 部署間関係

```sql
CREATE TABLE IF NOT EXISTS department_relations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_a_id        INTEGER NOT NULL REFERENCES departments(id),
    dept_b_id        INTEGER NOT NULL REFERENCES departments(id),
    relation_type    TEXT NOT NULL,               -- parent / sibling / dependent / partner
    description      TEXT,                        -- 関係説明
    created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(dept_a_id, dept_b_id, relation_type)  -- 同じ関係は1度だけ
);

CREATE INDEX IF NOT EXISTS idx_department_relations_dept_a ON department_relations(dept_a_id);
CREATE INDEX IF NOT EXISTS idx_department_relations_dept_b ON department_relations(dept_b_id);
```

---

## リクエスト・レスポンス形式

### 1. 部署作成（POST /api/departments）

**リクエスト**:
```json
{
  "name": "Data Team",
  "slug": "data-team",
  "description": "データ分析・ML部門",
  "parent_id": 1,
  "budget": 500
}
```

**レスポンス (201 Created)**:
```json
{
  "id": 2,
  "name": "Data Team",
  "slug": "data-team",
  "description": "データ分析・ML部門",
  "parent_id": 1,
  "budget": 500,
  "status": "active",
  "created_at": "2026-04-20T13:19:01+09:00",
  "updated_at": "2026-04-20T13:19:01+09:00",
  "_links": {
    "self": "/api/departments/2",
    "agents": "/api/departments/2/agents",
    "teams": "/api/departments/2/teams",
    "relations": "/api/departments/2/relations"
  }
}
```

### 2. 部署一覧取得（GET /api/departments）

**クエリパラメータ**:
```
GET /api/departments?status=active&parent_id=1&page=1&limit=20
```

**レスポンス (200 OK)**:
```json
{
  "data": [
    {
      "id": 2,
      "name": "Data Team",
      "slug": "data-team",
      "description": "データ分析・ML部門",
      "parent_id": 1,
      "status": "active",
      "budget": 500,
      "agent_count": 5,
      "team_count": 2,
      "created_at": "2026-04-20T13:19:01+09:00"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1,
    "pages": 1
  }
}
```

### 3. 部署詳細取得（GET /api/departments/{id}）

**レスポンス (200 OK)**:
```json
{
  "id": 2,
  "name": "Data Team",
  "slug": "data-team",
  "description": "データ分析・ML部門",
  "parent_id": 1,
  "parent": {
    "id": 1,
    "name": "Engineering",
    "slug": "engineering"
  },
  "budget": 500,
  "status": "active",
  "agent_count": 5,
  "team_count": 2,
  "created_at": "2026-04-20T13:19:01+09:00",
  "updated_at": "2026-04-20T13:19:01+09:00",
  "_links": {
    "self": "/api/departments/2",
    "agents": "/api/departments/2/agents",
    "teams": "/api/departments/2/teams",
    "relations": "/api/departments/2/relations"
  }
}
```

### 4. 部署更新（PUT /api/departments/{id}）

**リクエスト**:
```json
{
  "name": "Data & Analytics Team",
  "description": "データ分析・ML・BI部門",
  "budget": 600,
  "status": "active"
}
```

**レスポンス (200 OK)**:
```json
{
  "id": 2,
  "name": "Data & Analytics Team",
  "slug": "data-team",
  "description": "データ分析・ML・BI部門",
  "budget": 600,
  "status": "active",
  "updated_at": "2026-04-20T14:30:00+09:00"
}
```

### 5. 部署削除（DELETE /api/departments/{id}）

**レスポンス (204 No Content)**:
```
(空のボディ)
```

**レスポンス (400 Bad Request)** - 子部署が存在する場合:
```json
{
  "error": "DEPT_HAS_CHILDREN",
  "message": "子部署が存在するため削除できません",
  "child_departments": [
    {"id": 3, "name": "Backend Sub-team", "slug": "backend-sub"}
  ]
}
```

### 6. エージェント追加（POST /api/departments/{id}/agents）

**リクエスト**:
```json
{
  "agent_id": 5,
  "role": "member"
}
```

**レスポンス (201 Created)**:
```json
{
  "department_id": 2,
  "agent_id": 5,
  "agent": {
    "id": 5,
    "slug": "engineer-bob",
    "name": "Bob",
    "role_type": "engineer",
    "specialty": "backend"
  },
  "role": "member",
  "joined_at": "2026-04-20T13:19:01+09:00"
}
```

### 7. 部署内エージェント一覧（GET /api/departments/{id}/agents）

**レスポンス (200 OK)**:
```json
{
  "data": [
    {
      "agent_id": 5,
      "agent": {
        "id": 5,
        "slug": "engineer-bob",
        "name": "Bob",
        "role_type": "engineer",
        "specialty": "backend"
      },
      "role": "member",
      "joined_at": "2026-04-20T13:19:01+09:00"
    }
  ],
  "total": 1
}
```

### 8. チーム作成（POST /api/departments/{id}/teams）

**リクエスト**:
```json
{
  "name": "Backend Team",
  "slug": "backend-team",
  "description": "バックエンド開発チーム",
  "status": "active"
}
```

**レスポンス (201 Created)**:
```json
{
  "id": 10,
  "department_id": 2,
  "name": "Backend Team",
  "slug": "backend-team",
  "description": "バックエンド開発チーム",
  "status": "active",
  "created_at": "2026-04-20T13:19:01+09:00",
  "_links": {
    "self": "/api/departments/2/teams/10",
    "agents": "/api/departments/2/teams/10/agents"
  }
}
```

---

## HTTP ステータスコード

| コード | 説明 | 例 |
|-------|------|-----|
| **200** | OK | GET 成功、PUT 成功 |
| **201** | Created | POST 成功（リソース作成） |
| **204** | No Content | DELETE 成功 |
| **400** | Bad Request | バリデーションエラー、スキーマ不整合 |
| **401** | Unauthorized | 認証失敗 |
| **403** | Forbidden | 認可失敗 |
| **404** | Not Found | リソースが見つからない |
| **409** | Conflict | 重複（例: slug 重複、親部署が見つからない） |
| **500** | Internal Server Error | DB エラー、予期しないエラー |

---

## エラーハンドリング

### エラーレスポンス形式

```json
{
  "error": "ERROR_CODE",
  "message": "人間が読める説明",
  "details": {
    "field": "name",
    "value": "Data Team",
    "reason": "既に存在します"
  },
  "timestamp": "2026-04-20T13:19:01+09:00",
  "request_id": "req-abc123def456"
}
```

### 主要エラーコード

| コード | HTTP | 説明 |
|-------|------|------|
| `DEPT_NOT_FOUND` | 404 | 部署が見つからない |
| `AGENT_NOT_FOUND` | 404 | エージェントが見つからない |
| `DEPT_SLUG_DUPLICATE` | 409 | 部署 slug が重複している |
| `INVALID_PARENT_ID` | 400 | 親部署が見つからない |
| `DEPT_HAS_CHILDREN` | 400 | 子部署が存在するため削除不可 |
| `DEPT_HAS_AGENTS` | 400 | 配置されたエージェントが存在するため削除不可 |
| `CIRCULAR_DEPENDENCY` | 400 | 親部署指定で循環構造が発生 |
| `VALIDATION_ERROR` | 400 | 入力値検証エラー |
| `UNAUTHORIZED` | 401 | 認証なし |
| `FORBIDDEN` | 403 | 認可なし |
| `INTERNAL_ERROR` | 500 | サーバーエラー |

---

## KuzuDB グラフスキーマ

### ノード定義

```cypher
-- 部署ノード
CREATE NODE TABLE IF NOT EXISTS Department (
    id INT64 PRIMARY KEY,
    name STRING,
    slug STRING UNIQUE,
    status STRING,
    created_at TIMESTAMP
);

-- エージェントノード
CREATE NODE TABLE IF NOT EXISTS Agent (
    id INT64 PRIMARY KEY,
    slug STRING UNIQUE,
    name STRING,
    role_type STRING,
    status STRING
);

-- チームノード
CREATE NODE TABLE IF NOT EXISTS Team (
    id INT64 PRIMARY KEY,
    name STRING,
    slug STRING,
    department_id INT64,
    status STRING
);
```

### リレーション定義

```cypher
-- 部署内エージェント関係
CREATE REL TABLE IF NOT EXISTS HAS_AGENT (FROM Department TO Agent) {
    role STRING,
    joined_at TIMESTAMP
};

-- チーム内エージェント関係
CREATE REL TABLE IF NOT EXISTS TEAM_HAS_AGENT (FROM Team TO Agent) {
    role STRING,
    joined_at TIMESTAMP
};

-- 部署間親子関係
CREATE REL TABLE IF NOT EXISTS HAS_CHILD_DEPT (FROM Department TO Department) {
    relation_type STRING,
    created_at TIMESTAMP
};

-- 部署間関係（汎用）
CREATE REL TABLE IF NOT EXISTS RELATED_TO (FROM Department TO Department) {
    relation_type STRING,
    description STRING,
    created_at TIMESTAMP
};

-- 部署所属チーム関係
CREATE REL TABLE IF NOT EXISTS HAS_TEAM (FROM Department TO Team) {
    created_at TIMESTAMP
};
```

### クエリ例

```cypher
-- 部署 A に属するすべてのエージェントを取得
MATCH (d:Department {id: 2})-[rel:HAS_AGENT]->(a:Agent)
RETURN d.name, a.name, rel.role;

-- 部署 A の全子孫部署を取得（再帰）
MATCH (d:Department {id: 2})-[:HAS_CHILD_DEPT*]->(child:Department)
RETURN child.name, child.slug;

-- エージェント X の全部署を取得
MATCH (a:Agent {id: 5})<-[rel:HAS_AGENT]-(d:Department)
RETURN d.name, rel.role;

-- 部署間の最短パスを取得
MATCH path = SHORTEST(d1:Department {id: 1})-[*]-(d2:Department {id: 5})
RETURN path;
```

---

## 実装チェックリスト

### Backend Engineer

- [ ] SQLite スキーマ作成・マイグレーション
- [ ] REST API エンドポイント実装（Flask/FastAPI）
- [ ] リクエスト検証・バリデーション
- [ ] エラーハンドリング・ロギング
- [ ] 認可チェック（orchestrator, pm のみ編集可）

### Data Engineer

- [ ] KuzuDB スキーマ初期化
- [ ] SQLite → KuzuDB 同期ロジック
- [ ] グラフクエリ実装（リレーション検索）
- [ ] 循環依存検出（親部署指定時）

### QA Engineer

- [ ] API テストスイート（pytest）
- [ ] エッジケーステスト（削除制約、循環など）
- [ ] パフォーマンステスト（グラフ検索）
- [ ] E2E テスト（UI→API→DB）

---

**次ステップ**: Backend Engineer と Data Engineer による詳細設計・実装確認

