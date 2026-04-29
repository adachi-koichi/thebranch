-- Task #2516: 全文検索・AIセマンティック検索
-- FTS5 仮想テーブルの作成と初期データ投入

-- FTS5 仮想テーブル
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    doctype,
    doc_id,
    title,
    content,
    created_at UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 1'
);

CREATE TABLE IF NOT EXISTS search_index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 初期データ投入（5テーブル）
INSERT OR IGNORE INTO search_index(doctype, doc_id, title, content, created_at)
SELECT 'department', CAST(id AS TEXT), name, COALESCE(description,''), created_at FROM departments;

INSERT OR IGNORE INTO search_index(doctype, doc_id, title, content, created_at)
SELECT 'task', CAST(id AS TEXT), title, COALESCE(description,''), created_at FROM tasks;

INSERT OR IGNORE INTO search_index(doctype, doc_id, title, content, created_at)
SELECT 'mission', CAST(id AS TEXT), name, COALESCE(description,''), created_at FROM missions;

INSERT OR IGNORE INTO search_index(doctype, doc_id, title, content, created_at)
SELECT 'agent', CAST(id AS TEXT), role, COALESCE(session_id,''), created_at FROM agents;

INSERT OR IGNORE INTO search_index(doctype, doc_id, title, content, created_at)
SELECT 'comment', CAST(id AS TEXT), COALESCE(comment_type,'note'), content, created_at FROM delegation_comments;

INSERT OR REPLACE INTO search_index_meta(key, value) VALUES('last_rebuild', datetime('now','localtime'));
