#!/bin/bash
# THEBRANCH向けタスクにプロジェクトラベルを自動付与するhook
# トリガー: Claudeセッション終了時 (Stop hook)

DB="/Users/delightone/.claude/skills/task-manager-sqlite/data/tasks.sqlite"

if [ ! -f "$DB" ]; then
  exit 0
fi

UPDATED=$(sqlite3 "$DB" "
UPDATE dev_tasks
SET project = 'THEBRANCH', updated_at = datetime('now')
WHERE (project IS NULL OR project = '')
AND (
  title LIKE '%THEBRANCH%' OR title LIKE '%thebranch%' OR
  session_id LIKE '61159afe-%' OR
  dir LIKE '%thebranch%' OR
  dir LIKE '%adachi-koichi/thebranch%'
);
SELECT changes();
" 2>/dev/null)

if [ "${UPDATED:-0}" -gt 0 ]; then
  echo "[fix_project_labels] THEBRANCH タスク ${UPDATED} 件を自動ラベル付与" >&2
fi
