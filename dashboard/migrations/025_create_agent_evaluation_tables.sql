CREATE TABLE IF NOT EXISTS agent_evaluations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL UNIQUE,
  completion_rate REAL NOT NULL,  -- 0.0-100.0
  quality_score REAL NOT NULL,    -- 1.0-5.0
  overall_score REAL NOT NULL,    -- 計算済みスコア
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evaluation_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL,
  completion_rate REAL NOT NULL,
  quality_score REAL NOT NULL,
  overall_score REAL NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(agent_id) REFERENCES agent_evaluations(agent_id)
);

CREATE INDEX idx_evaluation_history_agent_id ON evaluation_history(agent_id);
