-- Agent Decision Transparency Tables
-- エージェント意思決定の透明化機能

CREATE TABLE agent_decision_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    decision_type TEXT NOT NULL,
    -- decision_type values: 'task_selection', 'priority_reorder', 'resource_allocation', 'delegation', 'approval'

    decision_summary TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    context TEXT,  -- JSON: decision context
    confidence_score REAL DEFAULT 0.8,  -- 0.0-1.0
    input_data TEXT,  -- JSON: input factors
    output_data TEXT,  -- JSON: result of decision
    status TEXT DEFAULT 'logged',
    -- status values: 'logged', 'reviewed', 'acted_upon', 'revised'

    impact_assessment TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    CHECK(decision_type IN ('task_selection', 'priority_reorder', 'resource_allocation', 'delegation', 'approval')),
    CHECK(confidence_score >= 0.0 AND confidence_score <= 1.0),
    CHECK(status IN ('logged', 'reviewed', 'acted_upon', 'revised'))
);

CREATE INDEX idx_agent_decision_logs_agent_id ON agent_decision_logs(agent_id);
CREATE INDEX idx_agent_decision_logs_department_id ON agent_decision_logs(department_id);
CREATE INDEX idx_agent_decision_logs_decision_type ON agent_decision_logs(decision_type);
CREATE INDEX idx_agent_decision_logs_created_at ON agent_decision_logs(created_at DESC);
CREATE INDEX idx_agent_decision_logs_status ON agent_decision_logs(status);

CREATE TABLE agent_decision_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_log_id INTEGER NOT NULL REFERENCES agent_decision_logs(id) ON DELETE CASCADE,
    factor_type TEXT NOT NULL,
    -- factor_type values: 'constraint', 'optimization', 'priority', 'availability', 'dependency', 'cost', 'deadline'

    factor_name TEXT NOT NULL,
    factor_value TEXT,
    weight REAL DEFAULT 1.0,
    -- weight: importance/influence of this factor (0.0-1.0)

    description TEXT,
    order_sequence INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    CHECK(factor_type IN ('constraint', 'optimization', 'priority', 'availability', 'dependency', 'cost', 'deadline')),
    CHECK(weight >= 0.0 AND weight <= 1.0)
);

CREATE INDEX idx_agent_decision_factors_decision_log_id ON agent_decision_factors(decision_log_id);
CREATE INDEX idx_agent_decision_factors_factor_type ON agent_decision_factors(factor_type);

CREATE TABLE agent_action_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    decision_log_id INTEGER REFERENCES agent_decision_logs(id) ON DELETE SET NULL,

    action_type TEXT NOT NULL,
    -- action_type values: 'delegated_task', 'changed_priority', 'allocated_resource', 'made_decision'

    action_detail TEXT NOT NULL,
    result_status TEXT DEFAULT 'pending',
    -- result_status values: 'success', 'failed', 'pending', 'cancelled'

    result_detail TEXT,
    affected_entity_type TEXT,  -- 'task', 'department', 'team', 'agent'
    affected_entity_id TEXT,

    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    CHECK(action_type IN ('delegated_task', 'changed_priority', 'allocated_resource', 'made_decision')),
    CHECK(result_status IN ('success', 'failed', 'pending', 'cancelled'))
);

CREATE INDEX idx_agent_action_audit_agent_id ON agent_action_audit(agent_id);
CREATE INDEX idx_agent_action_audit_decision_log_id ON agent_action_audit(decision_log_id);
CREATE INDEX idx_agent_action_audit_action_type ON agent_action_audit(action_type);
CREATE INDEX idx_agent_action_audit_result_status ON agent_action_audit(result_status);
CREATE INDEX idx_agent_action_audit_created_at ON agent_action_audit(created_at DESC);

CREATE TABLE decision_explanation_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_log_id INTEGER NOT NULL REFERENCES agent_decision_logs(id) ON DELETE CASCADE,

    explanation_summary TEXT NOT NULL,
    explanation_html TEXT,  -- HTML formatted explanation for UI

    generated_by TEXT,  -- 'ai', 'system'
    generation_method TEXT,  -- 'rule_based', 'llm_generated'

    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),

    CHECK(generated_by IN ('ai', 'system')),
    CHECK(generation_method IN ('rule_based', 'llm_generated'))
);

CREATE INDEX idx_decision_explanation_report_decision_log_id
ON decision_explanation_report(decision_log_id);

-- Trigger to update timestamps
CREATE TRIGGER update_agent_decision_logs_timestamp
AFTER UPDATE ON agent_decision_logs
BEGIN
    UPDATE agent_decision_logs SET updated_at = datetime('now','localtime')
    WHERE id = NEW.id;
END;
