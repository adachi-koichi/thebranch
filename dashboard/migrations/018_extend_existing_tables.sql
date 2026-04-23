-- Migration: 018_extend_existing_tables.sql
-- Purpose: Extend existing tables with team dynamics columns
-- Created: 2026-04-23

-- agents テーブル拡張
-- Note: SQLite ALTER TABLE不具合対策 - IF NOT EXISTSを削除
-- 既存カラムが存在する場合はスキップされます（Python側で確認）
ALTER TABLE agents ADD COLUMN workload_level INTEGER DEFAULT 0;
ALTER TABLE agents ADD COLUMN skill_tags TEXT;  -- JSON array
ALTER TABLE agents ADD COLUMN collaboration_score REAL DEFAULT 50;
ALTER TABLE agents ADD COLUMN last_activity_at TEXT;

-- teams テーブル拡張
ALTER TABLE teams ADD COLUMN optimization_enabled BOOLEAN DEFAULT 1;
ALTER TABLE teams ADD COLUMN performance_tier TEXT DEFAULT 'silver';  -- bronze/silver/gold
ALTER TABLE teams ADD COLUMN sla_target_completion_rate REAL DEFAULT 0.90;

-- task_delegations テーブル拡張
ALTER TABLE task_delegations ADD COLUMN allocation_algorithm_used TEXT;
ALTER TABLE task_delegations ADD COLUMN allocation_score REAL;
ALTER TABLE task_delegations ADD COLUMN reallocation_reason TEXT;
