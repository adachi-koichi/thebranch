-- Migration: 023_create_workflow_templates_tables.sql
-- Purpose: Create workflow templates and related tables for design/product workflows
-- Created: 2026-04-23

-- Workflow Templates テーブル
CREATE TABLE IF NOT EXISTS workflow_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'active',  -- active, archived, draft
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_by TEXT DEFAULT 'system'
);

-- Workflow Template Phases テーブル
CREATE TABLE IF NOT EXISTS wf_template_phases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  template_id INTEGER NOT NULL REFERENCES workflow_templates(id) ON DELETE CASCADE,
  phase_key TEXT NOT NULL,
  phase_label TEXT NOT NULL,
  specialist_type TEXT,  -- designer, researcher, engineer, product_manager
  phase_order INTEGER DEFAULT 0,
  is_parallel INTEGER DEFAULT 0,  -- 0=sequential, 1=parallel
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Workflow Template Tasks テーブル
CREATE TABLE IF NOT EXISTS wf_template_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phase_id INTEGER NOT NULL REFERENCES wf_template_phases(id) ON DELETE CASCADE,
  template_id INTEGER NOT NULL REFERENCES workflow_templates(id) ON DELETE CASCADE,
  task_key TEXT NOT NULL,
  task_title TEXT NOT NULL,
  task_description TEXT,
  depends_on_key TEXT,  -- reference to another task_key within same template
  priority INTEGER DEFAULT 1,  -- 1=high, 2=medium, 3=low
  estimated_hours REAL DEFAULT 0.0,
  task_order INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_wf_template_phases_template_id ON wf_template_phases(template_id);
CREATE INDEX IF NOT EXISTS idx_wf_template_phases_phase_key ON wf_template_phases(phase_key);
CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_phase_id ON wf_template_tasks(phase_id);
CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_template_id ON wf_template_tasks(template_id);
CREATE INDEX IF NOT EXISTS idx_wf_template_tasks_task_key ON wf_template_tasks(task_key);
CREATE INDEX IF NOT EXISTS idx_workflow_templates_status ON workflow_templates(status);
