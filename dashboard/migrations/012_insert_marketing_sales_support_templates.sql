-- マーケティング部・営業部・カスタマーサポート部テンプレート初期データ投入
-- Phase 4: Marketing, Sales, Customer Support Department の初期化

-- ===== マーケティング部テンプレート =====
INSERT INTO departments_templates (name, description, category, status, total_roles, total_processes, created_by)
VALUES (
    'Marketing Department',
    'ブランド構築・コンテンツ・キャンペーン・データ分析を担当する部署',
    'ops',
    'active',
    5,
    3,
    'admin'
) ON CONFLICT DO NOTHING;

-- ===== 営業部テンプレート =====
INSERT INTO departments_templates (name, description, category, status, total_roles, total_processes, created_by)
VALUES (
    'Sales Department',
    '顧客開拓・商談・売上管理を担当する部署',
    'ops',
    'active',
    4,
    3,
    'admin'
) ON CONFLICT DO NOTHING;

-- ===== カスタマーサポート部テンプレート =====
INSERT INTO departments_templates (name, description, category, status, total_roles, total_processes, created_by)
VALUES (
    'Customer Support Department',
    '顧客サービス・問い合わせ対応・FAQ管理を担当する部署',
    'support',
    'active',
    4,
    3,
    'admin'
) ON CONFLICT DO NOTHING;

-- ===== マーケティング部ロール定義 =====
INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'marketing-director', 'マーケティング部長', 1, 'マーケティング戦略の企画・実行、部署全体の統括', '["marketing_strategy", "brand_management", "leadership"]', 1, 1, NULL, datetime('now','localtime')
FROM departments_templates WHERE name = 'Marketing Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'marketing-manager', 'マーケティングマネージャー', 2, 'キャンペーン計画・コンテンツ戦略・チーム管理', '["campaign_management", "content_strategy", "team_management"]', 1, 2, 'marketing-director', datetime('now','localtime')
FROM departments_templates WHERE name = 'Marketing Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'content-specialist', 'コンテンツスペシャリスト', 3, 'ブログ・ホワイトペーパー・資料作成', '["content_creation", "copywriting", "seo"]', 2, 4, 'marketing-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Marketing Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'digital-marketing-specialist', 'デジタルマーケティング担当', 4, 'SNS運用・広告・メールマーケティング', '["social_media", "digital_advertising", "email_marketing"]', 2, 3, 'marketing-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Marketing Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'marketing-analyst', 'マーケティング分析担当', 5, 'キャンペーン分析・ROI測定・改善提案', '["data_analysis", "marketing_analytics", "reporting"]', 1, 2, 'marketing-director', datetime('now','localtime')
FROM departments_templates WHERE name = 'Marketing Department'
ON CONFLICT DO NOTHING;

-- ===== 営業部ロール定義 =====
INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'sales-director', '営業本部長', 1, '営業戦略の企画・実行、部署全体の統括', '["sales_strategy", "business_development", "leadership"]', 1, 1, NULL, datetime('now','localtime')
FROM departments_templates WHERE name = 'Sales Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'sales-manager', '営業マネージャー', 2, '営業チーム管理・商談進捗管理・成約推進', '["team_management", "deal_management", "negotiation"]', 1, 2, 'sales-director', datetime('now','localtime')
FROM departments_templates WHERE name = 'Sales Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'sales-executive', 'セールスエグゼクティブ', 3, '顧客開拓・営業活動・提案書作成', '["prospecting", "client_relations", "consultative_selling"]', 2, 5, 'sales-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Sales Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'sales-support', '営業サポート', 4, '見積書作成・契約管理・顧客データ管理', '["proposal_management", "crm_administration", "customer_support"]', 1, 2, 'sales-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Sales Department'
ON CONFLICT DO NOTHING;

-- ===== カスタマーサポート部ロール定義 =====
INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'support-director', 'サポート部長', 1, 'サポート戦略の企画・実行、部署全体の統括', '["support_strategy", "customer_success", "leadership"]', 1, 1, NULL, datetime('now','localtime')
FROM departments_templates WHERE name = 'Customer Support Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'support-manager', 'サポートマネージャー', 2, 'サポートチーム管理・品質管理・顧客満足度向上', '["team_management", "quality_assurance", "customer_success_management"]', 1, 2, 'support-director', datetime('now','localtime')
FROM departments_templates WHERE name = 'Customer Support Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'support-agent', 'サポートエージェント', 3, '顧客問い合わせ対応・トラブルシューティング', '["customer_service", "problem_solving", "communication"]', 3, 10, 'support-manager', datetime('now','localtime')
FROM departments_templates WHERE name = 'Customer Support Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_roles (template_id, role_key, role_label, role_order, responsibility, required_skills, min_members, max_members, supervisor_role_key, created_at)
SELECT id, 'knowledge-specialist', 'ナレッジ管理担当', 4, 'FAQ作成・マニュアル作成・ナレッジベース管理', '["knowledge_management", "documentation", "training"]', 1, 2, 'support-director', datetime('now','localtime')
FROM departments_templates WHERE name = 'Customer Support Department'
ON CONFLICT DO NOTHING;

-- ===== マーケティング部プロセス定義 =====
INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'content-creation', 'コンテンツ作成・公開', 1, 'ブログ・ホワイトペーパー・資料の企画・作成・公開', 'content-specialist', 16, 'weekly', '[{"name": "Content Calendar", "format": "xlsx", "mandatory": true}, {"name": "Content Draft", "format": "docx", "mandatory": true}, {"name": "SEO Checklist", "format": "pdf", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Marketing Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'social-media-campaign', 'SNS運用・キャンペーン実施', 2, 'ソーシャルメディア投稿・キャンペーン企画・実行・モニタリング', 'digital-marketing-specialist', 20, 'weekly', '[{"name": "Campaign Plan", "format": "xlsx", "mandatory": true}, {"name": "Social Media Schedule", "format": "xlsx", "mandatory": true}, {"name": "Performance Report", "format": "pdf", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Marketing Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'marketing-analytics', 'マーケティング分析・改善', 3, 'キャンペーン分析・ROI測定・施策改善案作成', 'marketing-analyst', 12, 'monthly', '[{"name": "Analytics Report", "format": "xlsx", "mandatory": true}, {"name": "ROI Analysis", "format": "pdf", "mandatory": true}, {"name": "Improvement Plan", "format": "docx", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Marketing Department'
ON CONFLICT DO NOTHING;

-- ===== 営業部プロセス定義 =====
INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'prospecting-outreach', '顧客開拓・営業活動', 1, '新規顧客の開拓・営業ピッチ・提案作成', 'sales-executive', 20, 'weekly', '[{"name": "Prospect List", "format": "xlsx", "mandatory": true}, {"name": "Proposal", "format": "docx", "mandatory": true}, {"name": "Follow-up Log", "format": "xlsx", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Sales Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'deal-management', '商談進捗管理', 2, '商談の進捗追跡・ステージ管理・成約推進', 'sales-manager', 12, 'weekly', '[{"name": "Pipeline Report", "format": "xlsx", "mandatory": true}, {"name": "Deal Summary", "format": "pdf", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Sales Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'sales-reporting', '売上報告・分析', 3, '月次売上報告・受注分析・目標達成状況報告', 'sales-manager', 8, 'monthly', '[{"name": "Sales Report", "format": "xlsx", "mandatory": true}, {"name": "Performance Analysis", "format": "pdf", "mandatory": true}, {"name": "Forecast", "format": "xlsx", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Sales Department'
ON CONFLICT DO NOTHING;

-- ===== カスタマーサポート部プロセス定義 =====
INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'ticket-management', 'チケット対応・問題解決', 1, '顧客問い合わせの受け付け・分類・対応・解決', 'support-agent', 24, 'daily', '[{"name": "Ticket Log", "format": "xlsx", "mandatory": true}, {"name": "Resolution Note", "format": "docx", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Customer Support Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'faq-management', 'FAQ作成・メンテナンス', 2, 'よくある質問の整理・FAQ文書化・更新・公開', 'knowledge-specialist', 12, 'monthly', '[{"name": "FAQ Draft", "format": "docx", "mandatory": true}, {"name": "FAQ Checklist", "format": "xlsx", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Customer Support Department'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_processes (template_id, process_key, process_label, process_order, description, responsible_role_key, estimated_hours, frequency, doc_requirements, created_at, updated_at)
SELECT id, 'escalation-resolution', 'エスカレーション・重大問題対応', 3, '複雑な問題の対応・エスカレーション・解決報告', 'support-manager', 16, 'monthly', '[{"name": "Escalation Log", "format": "xlsx", "mandatory": true}, {"name": "Root Cause Analysis", "format": "pdf", "mandatory": true}, {"name": "Prevention Plan", "format": "docx", "mandatory": true}]', datetime('now','localtime'), datetime('now','localtime')
FROM departments_templates WHERE name = 'Customer Support Department'
ON CONFLICT DO NOTHING;

-- ===== マーケティング部タスク定義（コンテンツ作成プロセス） =====
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'create-blog-post', 'ブログ記事作成', 'SEO対策済みのブログ記事を執筆・編集', 'content-specialist', 'content', 4, 2, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'content-creation'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'create-whitepaper', 'ホワイトペーパー作成', '業界動向・ソリューション紹介のホワイトペーパーを作成', 'content-specialist', 'content', 8, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'content-creation'
ON CONFLICT DO NOTHING;

-- ===== 営業部タスク定義（顧客開拓プロセス） =====
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'prospect-list-update', 'ターゲットリスト更新', 'CRMにターゲット顧客リストを登録・更新', 'sales-executive', 'prospecting', 2, 2, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'prospecting-outreach'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'send-proposal', '提案書送付', 'カスタマイズされた提案書を作成・送付', 'sales-executive', 'prospecting', 3, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'prospecting-outreach'
ON CONFLICT DO NOTHING;

-- ===== カスタマーサポート部タスク定義（チケット管理プロセス） =====
INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'receive-ticket', 'チケット受け付け・分類', '顧客問い合わせをチケット化・優先度・カテゴリを設定', 'support-agent', 'support', 0.5, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'ticket-management'
ON CONFLICT DO NOTHING;

INSERT INTO department_template_tasks (process_id, template_id, task_key, task_title, task_description, assigned_role_key, category, estimated_hours, priority, created_at)
SELECT p.id, p.template_id, 'resolve-ticket', 'チケット対応・解決', 'トラブルシューティング・解決策の提供・確認', 'support-agent', 'support', 2, 1, datetime('now','localtime')
FROM department_template_processes p WHERE p.process_key = 'ticket-management'
ON CONFLICT DO NOTHING;
