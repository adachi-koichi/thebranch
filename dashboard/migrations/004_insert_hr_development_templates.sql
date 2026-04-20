-- 人事部・開発部テンプレート初期データ投入
-- Phase 1: 人事部（HR Department）と開発部（Development Department）の初期化

-- 人事部テンプレート
INSERT INTO departments_templates (name, description, category, status, total_roles, total_processes, created_by)
VALUES (
    'HR Department',
    '人材採用・育成・管理を担当する部署',
    'back-office',
    'active',
    3,
    2,
    'admin'
) ON CONFLICT DO NOTHING;

-- 開発部テンプレート
INSERT INTO departments_templates (name, description, category, status, total_roles, total_processes, created_by)
VALUES (
    'Development Department',
    'プロダクト開発・エンジニアリングを担当する部署',
    'tech',
    'active',
    5,
    2,
    'admin'
) ON CONFLICT DO NOTHING;

-- 人事部ロール定義
INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'hr-director', '人事部長', 1, '人材戦略の企画・実行、部署全体の統括', '["talent_management", "organizational_development", "strategic_planning"]', 1, 1, NULL, datetime('now','localtime')
FROM departments_templates WHERE name = 'HR Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'hr-manager', '人事マネージャー', 2, '採用・人材評価・従業員関係管理', '["recruitment", "employee_relations", "performance_management"]', 1, 2, 'hr-director', datetime('now','localtime')
FROM departments_templates WHERE name = 'HR Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'hr-specialist', '人事スペシャリスト', 3, '給与・福利厚生・記録管理', '["payroll", "benefits_administration", "record_keeping"]', 1, 3, 'hr-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'HR Department'
ON CONFLICT DO NOTHING;

-- 開発部ロール定義
INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'tech-lead', '技術責任者', 1, 'システムアーキテクチャ・技術戦略、開発全体の統括', '["system_architecture", "technical_leadership", "code_review"]', 1, 1, NULL, datetime('now','localtime')
FROM departments_templates WHERE name = 'Development Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'engineering-manager', 'エンジニアリング・マネージャー', 2, 'チーム管理・プロジェクト計画・技術メンタリング', '["team_management", "project_planning", "technical_mentoring"]', 1, 2, 'tech-lead', datetime('now','localtime')
FROM departments_templates WHERE name = 'Development Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'senior-engineer', 'シニアエンジニア', 3, 'フルスタック開発・DB設計・システム最適化', '["full_stack_development", "database_design", "system_optimization"]', 1, 3, 'engineering-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Development Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'engineer', 'エンジニア', 4, 'プログラミング・テスト・バージョン管理', '["programming", "testing", "version_control"]', 2, 8, 'engineering-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Development Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'qa-engineer', 'QAエンジニア', 5, 'テスト自動化・品質保証・バグ報告', '["test_automation", "quality_assurance", "bug_reporting"]', 1, 2, 'tech-lead', datetime('now','localtime')
FROM departments_templates WHERE name = 'Development Department'
ON CONFLICT DO NOTHING;

-- 人事部プロセス定義
INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, created_at)
SELECT id, 'recruitment', '採用プロセス', 1, '採用・面接・内定', 'hr-manager', 40, 'ad-hoc', datetime('now','localtime')
FROM departments_templates WHERE name = 'HR Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, created_at)
SELECT id, 'performance-review', '人事評価', 2, '評価スケジュール・フィードバック・承認', 'hr-manager', 30, 'annual', datetime('now','localtime')
FROM departments_templates WHERE name = 'HR Department'
ON CONFLICT DO NOTHING;

-- 開発部プロセス定義
INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, created_at)
SELECT id, 'feature-development', '機能開発', 1, '設計・実装・コードレビュー・マージ', 'engineering-manager', 80, 'weekly', datetime('now','localtime')
FROM departments_templates WHERE name = 'Development Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, created_at)
SELECT id, 'testing-release', 'テスト・リリース', 2, 'テスト計画・単体テスト・E2Eテスト・リリース承認', 'qa-engineer', 24, 'weekly', datetime('now','localtime')
FROM departments_templates WHERE name = 'Development Department'
ON CONFLICT DO NOTHING;

-- 人事部タスク定義（採用プロセス）
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'job-posting', '求人票作成・掲載', '求人情報を作成し採用サイトに掲載', 'hr-manager', 'data-entry', 2, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'recruitment'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'candidate-screening', '応募者選別', 'レジュメレビュー・適性判定', 'hr-specialist', 'validation', 8, 'job-posting', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'recruitment'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'interview-coordination', '面接調整', '面接スケジュール・面接官の確保', 'hr-specialist', 'data-entry', 4, 'candidate-screening', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'recruitment'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'offer-decision', '内定決定', '最終選考・内定通知', 'hr-manager', 'approval', 2, 'interview-coordination', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'recruitment'
ON CONFLICT DO NOTHING;

-- 人事部タスク定義（人事評価プロセス）
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'review-planning', '評価スケジュール企画', '評価期間・プロセス・スケジュール設定', 'hr-manager', 'analysis', 4, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'performance-review'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'self-assessment-collection', '自己評価回収', '従業員からの自己評価を収集', 'hr-specialist', 'data-entry', 4, 'review-planning', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'performance-review'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'manager-feedback', '管理職フィードバック作成', '部長・マネージャーによる評価・フィードバック作成', 'hr-manager', 'review', 10, 'self-assessment-collection', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'performance-review'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'review-finalization', '評価書確定・承認', '最終評価の確定と経営層への承認', 'hr-director', 'approval', 2, 'manager-feedback', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'performance-review'
ON CONFLICT DO NOTHING;

-- 開発部タスク定義（機能開発プロセス）
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'design-review', '設計レビュー', 'アーキテクチャ・API設計・DBスキーマレビュー', 'senior-engineer', 'review', 4, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'feature-development'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'implementation', '実装', 'フロントエンド・バックエンド実装', 'engineer', 'implement', 40, 'design-review', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'feature-development'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'code-review', 'コードレビュー', 'コード品質・ベストプラクティス確認', 'senior-engineer', 'review', 8, 'implementation', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'feature-development'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'merge-to-main', 'メインブランチへマージ', 'マージ前の最終確認・本番反映', 'tech-lead', 'approval', 2, 'code-review', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'feature-development'
ON CONFLICT DO NOTHING;

-- 開発部タスク定義（テスト・リリースプロセス）
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'test-planning', 'テスト計画作成', 'テスト戦略・テストケース定義', 'qa-engineer', 'analysis', 2, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'testing-release'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'unit-testing', '単体テスト実施', '関数・モジュールの単体テスト', 'engineer', 'validation', 8, 'test-planning', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'testing-release'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'e2e-testing', 'E2Eテスト実施', 'エンドツーエンドテスト・統合テスト', 'qa-engineer', 'validation', 8, 'unit-testing', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'testing-release'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'release-approval', 'リリース承認', '本番環境へのリリース最終承認', 'tech-lead', 'approval', 2, 'e2e-testing', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'testing-release'
ON CONFLICT DO NOTHING;
