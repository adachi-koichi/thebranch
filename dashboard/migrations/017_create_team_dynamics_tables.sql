-- Migration: 017_create_team_dynamics_tables.sql
-- Purpose: Create tables for team dynamics optimization feature
-- Created: 2026-04-23

-- 1. team_dynamics_snapshot: 日単位チーム状態スナップショット
CREATE TABLE IF NOT EXISTS team_dynamics_snapshot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id INTEGER NOT NULL,
  snapshot_date TEXT,
  member_count INTEGER,
  completed_tasks_today INTEGER,
  avg_completion_rate REAL,
  avg_throughput_7d REAL,
  collaboration_score REAL,
  metadata TEXT,  -- JSON
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(team_id) REFERENCES teams(id)
);

-- 2. team_performance_metrics: メンバー個別パフォーマンス指標
CREATE TABLE IF NOT EXISTS team_performance_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id INTEGER NOT NULL,
  agent_id INTEGER NOT NULL,
  metric_date TEXT,
  completion_rate REAL,
  throughput_tasks_7d REAL,
  quality_score REAL,      -- 0-100
  workload_score REAL,     -- 0-100
  responsiveness_score REAL, -- 0-100
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(team_id) REFERENCES teams(id),
  FOREIGN KEY(agent_id) REFERENCES agents(id)
);

-- 3. agent_skills_inventory: エージェントのスキル・能力マトリックス
CREATE TABLE IF NOT EXISTS agent_skills_inventory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL,
  skill_key TEXT,
  proficiency_level INTEGER,  -- 1-5
  last_used_at TEXT,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  metadata TEXT,  -- JSON
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(agent_id) REFERENCES agents(id)
);

-- 4. team_collaboration_events: 自動推出コラボレーションイベント
CREATE TABLE IF NOT EXISTS team_collaboration_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id INTEGER NOT NULL,
  event_type TEXT,  -- communication, knowledge_share, help_request, blocker_resolution
  participant_ids TEXT,  -- JSON array
  source_delegation_id INTEGER,
  event_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
  metadata TEXT,  -- JSON
  FOREIGN KEY(team_id) REFERENCES teams(id)
);

-- 5. task_allocation_history: タスク割り当て最適化履歴
CREATE TABLE IF NOT EXISTS task_allocation_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  allocated_agent_id INTEGER NOT NULL,
  algorithm_version TEXT,
  ranking_score REAL,
  candidate_scores TEXT,  -- JSON: {agent_id: score, ...}
  allocation_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(allocated_agent_id) REFERENCES agents(id)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_team_dynamics_team_date
  ON team_dynamics_snapshot(team_id, snapshot_date);

CREATE INDEX IF NOT EXISTS idx_team_perf_team_agent
  ON team_performance_metrics(team_id, agent_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_team_collab_events_team
  ON team_collaboration_events(team_id, event_timestamp);

CREATE INDEX IF NOT EXISTS idx_task_alloc_history_task
  ON task_allocation_history(task_id, allocation_timestamp);
