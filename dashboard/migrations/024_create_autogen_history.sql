CREATE TABLE IF NOT EXISTS autogen_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  generation_id TEXT NOT NULL UNIQUE,
  organization_id TEXT NOT NULL,
  workflow_instance_id INTEGER REFERENCES workflow_instances(id) ON DELETE SET NULL,
  user_id TEXT NOT NULL,
  natural_language_input TEXT NOT NULL,
  generated_dag_json TEXT NOT NULL,
  model_used TEXT NOT NULL,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  cache_hit BOOLEAN DEFAULT 0,
  is_valid BOOLEAN NOT NULL,
  validation_errors TEXT,
  status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'modified')),
  approved_by TEXT,
  approved_at TEXT,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_autogen_history_org ON autogen_history(organization_id);
CREATE INDEX IF NOT EXISTS idx_autogen_history_instance ON autogen_history(workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_autogen_history_status ON autogen_history(status);
