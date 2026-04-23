-- Migration: 020_add_completion_rate_to_agents.sql
-- Purpose: Add completion_rate field to agents table for reliability scoring
-- Created: 2026-04-23

ALTER TABLE agents ADD COLUMN completion_rate REAL DEFAULT 0.8;
