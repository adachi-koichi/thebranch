CREATE TABLE IF NOT EXISTS learning_patterns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_id TEXT,
  workflow_name TEXT,
  input TEXT,
  output TEXT,
  result_status TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  confidence REAL
);

CREATE INDEX IF NOT EXISTS idx_learning_patterns_workflow_id ON learning_patterns(workflow_id);
CREATE INDEX IF NOT EXISTS idx_learning_patterns_created_at ON learning_patterns(created_at);
