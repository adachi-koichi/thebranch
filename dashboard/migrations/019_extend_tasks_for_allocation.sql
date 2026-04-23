-- Migration: 019_extend_tasks_for_allocation.sql
-- Purpose: Add skill requirements and category to tasks for better allocation
-- Created: 2026-04-23

-- tasks テーブル拡張
-- Note: SQLite ALTER TABLE不具合対策 - Python側で既存カラム確認
ALTER TABLE tasks ADD COLUMN required_skills TEXT;  -- JSON array
ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT 'general';  -- engineering, product, design, research
ALTER TABLE tasks ADD COLUMN complexity INTEGER DEFAULT 1;  -- 1-5: 1=easy, 5=very hard
ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 2;  -- 1=critical, 2=normal, 3=low
