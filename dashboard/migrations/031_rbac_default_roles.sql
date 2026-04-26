-- RBAC: 既存ユーザーにデフォルト 'member' ロールを付与 (Task #2493)
-- user_roles テーブルは 001_create_auth_tables.sql で作成済み

INSERT OR IGNORE INTO user_roles (id, user_id, role, created_at)
SELECT
    lower(hex(randomblob(8))),
    id,
    'member',
    CURRENT_TIMESTAMP
FROM users
WHERE id NOT IN (SELECT DISTINCT user_id FROM user_roles);
