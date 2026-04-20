-- 経理部・法務部テンプレート初期データ投入
-- Phase 2: 経理部（Finance Department）と法務部（Legal Department）の初期化

-- 経理部テンプレート
INSERT INTO departments_templates (name, description, category, status, total_roles, total_processes, created_by)
VALUES (
    'Finance Department',
    '財務管理・経理業務を担当する部署',
    'back-office',
    'active',
    4,
    3,
    'admin'
) ON CONFLICT DO NOTHING;

-- 法務部テンプレート
INSERT INTO departments_templates (name, description, category, status, total_roles, total_processes, created_by)
VALUES (
    'Legal Department',
    '法務・コンプライアンス業務を担当する部署',
    'back-office',
    'active',
    4,
    2,
    'admin'
) ON CONFLICT DO NOTHING;

-- ===== 経理部ロール定義 =====
INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'finance-director', '財務部長', 1, '財務戦略の企画・実行、部署全体の統括', '["financial_strategy", "leadership", "budgeting"]', 1, 1, NULL, datetime('now','localtime')
FROM departments_templates WHERE name = 'Finance Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'finance-manager', '財務マネージャー', 2, '月次決算・財務分析・チーム管理', '["accounting", "tax_planning", "financial_analysis"]', 1, 3, 'finance-director', datetime('now','localtime')
FROM departments_templates WHERE name = 'Finance Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'accountant', '経理', 3, '日々の会計業務・仕訳・決算整理', '["journal_entry", "reconciliation", "compliance"]', 2, 5, 'finance-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Finance Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'audit-specialist', '監査担当', 4, '内部監査・リスク評価・コンプライアンス確認', '["audit", "risk_assessment", "compliance_review"]', 1, 2, 'finance-director', datetime('now','localtime')
FROM departments_templates WHERE name = 'Finance Department'
ON CONFLICT DO NOTHING;

-- ===== 法務部ロール定義 =====
INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'general-counsel', '法務部長', 1, '法務戦略の企画・実行、部署全体の統括', '["legal_strategy", "contract_negotiation", "compliance"]', 1, 1, NULL, datetime('now','localtime')
FROM departments_templates WHERE name = 'Legal Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'legal-manager', '法務マネージャー', 2, '契約書レビュー・法的分析・リスク管理', '["contract_review", "legal_analysis", "risk_management"]', 1, 2, 'general-counsel', datetime('now','localtime')
FROM departments_templates WHERE name = 'Legal Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'compliance-officer', 'コンプライアンス担当', 3, '規制対応・監査・方針開発', '["regulatory_compliance", "audit", "policy_development"]', 1, 2, 'general-counsel', datetime('now','localtime')
FROM departments_templates WHERE name = 'Legal Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'legal-specialist', '法務スペシャリスト', 4, '契約書作成・法的リサーチ・文書化', '["contract_drafting", "legal_research", "documentation"]', 1, 3, 'legal-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Legal Department'
ON CONFLICT DO NOTHING;

-- ===== 経理部プロセス定義 =====
INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, created_at, updated_at)
SELECT id, 'daily-cash-management', '日次現金管理', 1, '日々の現金・銀行口座の照合・取引記録', 'accountant', 1, 'daily', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Finance Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'monthly-closing', '月次決算', 2, '月次決算処理・決算整理・承認', 'finance-manager', 16, 'monthly', '[{"name": "Trial Balance", "format": "xlsx", "mandatory": true}, {"name": "General Ledger", "format": "xlsx", "mandatory": true}, {"name": "Monthly Report", "format": "pdf", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Finance Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, created_at, updated_at)
SELECT id, 'quarterly-audit', '四半期監査', 3, '内部監査・決算監査・リスク評価', 'audit-specialist', 24, 'quarterly', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Finance Department'
ON CONFLICT DO NOTHING;

-- ===== 法務部プロセス定義 =====
INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, created_at, updated_at)
SELECT id, 'contract-management', '契約管理', 1, '契約書の受付・レビュー・承認', 'legal-manager', 8, 'ad-hoc', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Legal Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, created_at, updated_at)
SELECT id, 'compliance-audit', 'コンプライアンス監査', 2, 'コンプライアンス確認・改善計画・報告', 'compliance-officer', 20, 'quarterly', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Legal Department'
ON CONFLICT DO NOTHING;

-- ===== 経理部タスク定義（日次現金管理プロセス） =====
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'reconcile-cash-accounts', '現金勘定の照合', '現金出納帳と帳簿の照合', 'accountant', 'validation', 0.5, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'daily-cash-management'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'record-daily-transactions', '日次取引記録', '本日の取引をシステムに記録', 'accountant', 'data-entry', 0.5, 'reconcile-cash-accounts', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'daily-cash-management'
ON CONFLICT DO NOTHING;

-- ===== 経理部タスク定義（月次決算プロセス） =====
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'reconcile-ledger', '元帳照合', '各科目の元帳と補助簿の照合確認', 'accountant', 'validation', 2, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'monthly-closing'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'prepare-trial-balance', '試算表作成', '元帳から試算表を作成', 'accountant', 'analysis', 2, 'reconcile-ledger', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'monthly-closing'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'review-adjustments', '決算整理項目の検討', '月次決算に必要な決算整理項目の検討・実施', 'finance-manager', 'review', 3, 'prepare-trial-balance', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'monthly-closing'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'approve-closing', '月次決算の承認', '月次決算内容の最終確認と承認', 'finance-director', 'approval', 1, 'review-adjustments', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'monthly-closing'
ON CONFLICT DO NOTHING;

-- ===== 経理部タスク定義（四半期監査プロセス） =====
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'audit-planning', '監査計画作成', '監査対象・手続き・リスク評価を含む監査計画の策定', 'audit-specialist', 'analysis', 4, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'quarterly-audit'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'conduct-audit', '監査実施', '計画に基づいた詳細な内部監査の実施', 'audit-specialist', 'validation', 12, 'audit-planning', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'quarterly-audit'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'audit-report', '監査報告書作成', '監査結果の取りまとめと監査報告書の作成', 'audit-specialist', 'analysis', 8, 'conduct-audit', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'quarterly-audit'
ON CONFLICT DO NOTHING;

-- ===== 法務部タスク定義（契約管理プロセス） =====
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'contract-intake', '契約書受付・分類', '提出された契約書の受付と内容分類', 'legal-specialist', 'data-entry', 1, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'contract-management'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'contract-review', '契約書レビュー', 'リスク・条件・法的問題点の詳細レビュー', 'legal-manager', 'review', 4, 'contract-intake', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'contract-management'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'contract-approval', '契約承認', 'レビュー完了後の最終承認', 'general-counsel', 'approval', 2, 'contract-review', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'contract-management'
ON CONFLICT DO NOTHING;

-- ===== 法務部タスク定義（コンプライアンス監査プロセス） =====
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'compliance-check', 'コンプライアンス確認', '法令・規制の遵守状況確認と評価', 'compliance-officer', 'validation', 8, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'compliance-audit'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'remediation-plan', '改善計画作成', '指摘事項への改善計画・対応策の策定', 'compliance-officer', 'analysis', 6, 'compliance-check', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'compliance-audit'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, depends_on_key, priority, created_at)
SELECT p.id, p.template_id, 'executive-report', '経営層報告', '監査結果と改善計画を経営層に報告', 'general-counsel', 'approval', 2, 'remediation-plan', 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'compliance-audit'
ON CONFLICT DO NOTHING;
