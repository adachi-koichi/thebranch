-- 部署管理ベーステーブル
-- 部署CRUD・エージェント管理・グラフ関係管理用

CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,
    description TEXT,
    parent_id   INTEGER REFERENCES departments(id),
    budget      REAL,
    status      TEXT DEFAULT 'active',
    created_by  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    CHECK(status IN ('active', 'inactive', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_departments_status ON departments(status);
CREATE INDEX IF NOT EXISTS idx_departments_parent_id ON departments(parent_id);
CREATE INDEX IF NOT EXISTS idx_departments_created_at ON departments(created_at);

-- 部署とエージェント（中間テーブル）
CREATE TABLE IF NOT EXISTS department_agents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    agent_id      INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    role          TEXT NOT NULL,
    joined_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    left_at       TEXT,
    UNIQUE(department_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_department_agents_department_id
  ON department_agents(department_id);
CREATE INDEX IF NOT EXISTS idx_department_agents_agent_id
  ON department_agents(agent_id);
CREATE INDEX IF NOT EXISTS idx_department_agents_role
  ON department_agents(role);

-- チーム管理
CREATE TABLE IF NOT EXISTS teams (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    slug          TEXT NOT NULL,
    description   TEXT,
    status        TEXT DEFAULT 'active',
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(department_id, slug),
    CHECK(status IN ('active', 'inactive'))
);

CREATE INDEX IF NOT EXISTS idx_teams_department_id ON teams(department_id);
CREATE INDEX IF NOT EXISTS idx_teams_status ON teams(status);

-- チームとエージェント（中間テーブル）
CREATE TABLE IF NOT EXISTS team_x_agents (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id  INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    role     TEXT,
    joined_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(team_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_team_x_agents_team_id ON team_x_agents(team_id);
CREATE INDEX IF NOT EXISTS idx_team_x_agents_agent_id ON team_x_agents(agent_id);

-- 部署間関係
CREATE TABLE IF NOT EXISTS department_relations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_a_id      INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    dept_b_id      INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    relation_type  TEXT NOT NULL,
    description    TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(dept_a_id, dept_b_id, relation_type),
    CHECK(relation_type IN ('parent', 'sibling', 'dependent', 'partner'))
);

CREATE INDEX IF NOT EXISTS idx_department_relations_dept_a ON department_relations(dept_a_id);
CREATE INDEX IF NOT EXISTS idx_department_relations_dept_b ON department_relations(dept_b_id);
