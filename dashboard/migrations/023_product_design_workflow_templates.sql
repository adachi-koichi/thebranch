-- Migration: 023_product_design_workflow_templates.sql
-- Purpose: Create product design workflow templates for Design Sprint, UX Research, and Prototype Auto-generation
-- Created: 2026-04-23

-- Template 1: Design Sprint (5-day process)
INSERT INTO workflow_templates (name, description, status, created_at, updated_at, created_by)
VALUES (
  'デザインスプリント',
  '5日間で問題定義からテスト・改善までを実施するプロセス。チームが迅速にアイデアを形にし、ユーザーフィードバックを得るための集中的な方法論。',
  'active',
  datetime('now','localtime'),
  datetime('now','localtime'),
  'system'
);

-- Get template 1 ID
WITH template_1 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'デザインスプリント' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_phases (template_id, phase_key, phase_label, specialist_type, phase_order, is_parallel, created_at)
SELECT id, 'day1_problem_definition', 'Day1: 問題定義', 'designer', 1, 0, datetime('now','localtime') FROM template_1
UNION ALL
SELECT id, 'day2_brainstorm', 'Day2: アイデア発散', 'designer', 2, 0, datetime('now','localtime') FROM template_1
UNION ALL
SELECT id, 'day3_prototype', 'Day3: プロトタイプ', 'designer', 3, 0, datetime('now','localtime') FROM template_1
UNION ALL
SELECT id, 'day4_user_test', 'Day4: ユーザーテスト', 'designer', 4, 0, datetime('now','localtime') FROM template_1
UNION ALL
SELECT id, 'day5_refinement', 'Day5: 改善・ラップアップ', 'designer', 5, 0, datetime('now','localtime') FROM template_1;

-- Day1 Phase: 問題定義
WITH day1_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'day1_problem_definition' ORDER BY created_at DESC LIMIT 1
),
template_1 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'デザインスプリント' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM day1_phase),
  (SELECT id FROM template_1),
  'define_challenge',
  'デザインチャレンジ明確化',
  'ユーザーが直面している問題・デザイン課題を明確に定義する。',
  NULL,
  1,
  2.0,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM day1_phase),
  (SELECT id FROM template_1),
  'stakeholder_interview',
  'ステークホルダーインタビュー',
  'チームメンバー・顧客からの意見を収集し、問題の多角的理解を得る。',
  'define_challenge',
  1,
  1.5,
  2,
  datetime('now','localtime');

-- Day2 Phase: アイデア発散
WITH day2_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'day2_brainstorm' ORDER BY created_at DESC LIMIT 1
),
template_1 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'デザインスプリント' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM day2_phase),
  (SELECT id FROM template_1),
  'brainstorming_session',
  'ブレインストーミング',
  'チーム全体でアイデア出しを実施。量を重視し、評価は後で行う。',
  NULL,
  1,
  2.0,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM day2_phase),
  (SELECT id FROM template_1),
  'sketch_ideation',
  'スケッチ・イデーション',
  'アイデアをビジュアルスケッチで表現する。粗くても構わない。',
  'brainstorming_session',
  1,
  1.5,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM day2_phase),
  (SELECT id FROM template_1),
  'idea_review',
  'アイデア投票・選定',
  'スケッチを共有し、チームで最有望なアイデアを選定する。',
  'sketch_ideation',
  1,
  1.0,
  3,
  datetime('now','localtime');

-- Day3 Phase: プロトタイプ
WITH day3_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'day3_prototype' ORDER BY created_at DESC LIMIT 1
),
template_1 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'デザインスプリント' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM day3_phase),
  (SELECT id FROM template_1),
  'create_prototype',
  '簡易プロトタイプ作成',
  'Figma・Sketch・HTML等で簡易的なプロトタイプを作成。完成度は不要。',
  NULL,
  1,
  3.0,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM day3_phase),
  (SELECT id FROM template_1),
  'prototype_review',
  'プロトタイプレビュー',
  'チーム内でプロトタイプを確認し、微調整を実施。',
  'create_prototype',
  1,
  1.0,
  2,
  datetime('now','localtime');

-- Day4 Phase: ユーザーテスト
WITH day4_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'day4_user_test' ORDER BY created_at DESC LIMIT 1
),
template_1 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'デザインスプリント' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM day4_phase),
  (SELECT id FROM template_1),
  'recruit_users',
  'ユーザーリクルート',
  'テストに参加するユーザーを5〜8人募集する。',
  NULL,
  1,
  1.5,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM day4_phase),
  (SELECT id FROM template_1),
  'conduct_test',
  'ユーザーテスト実施',
  'プロトタイプをユーザーに見せ、操作・反応を観察してフィードバックを収集。',
  'recruit_users',
  1,
  2.5,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM day4_phase),
  (SELECT id FROM template_1),
  'feedback_analysis',
  'フィードバック分析',
  'ユーザーの反応・コメントを分析し、改善点を洗い出す。',
  'conduct_test',
  1,
  1.0,
  3,
  datetime('now','localtime');

-- Day5 Phase: 改善・ラップアップ
WITH day5_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'day5_refinement' ORDER BY created_at DESC LIMIT 1
),
template_1 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'デザインスプリント' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM day5_phase),
  (SELECT id FROM template_1),
  'refine_design',
  'デザイン改善',
  'ユーザーテストの洞察をもとに、プロトタイプを改善する。',
  NULL,
  1,
  2.0,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM day5_phase),
  (SELECT id FROM template_1),
  'scalability_review',
  'スケーラビリティ検討',
  '改善されたデザインが本番環境でどう動作するか、技術的な実現性を検討。',
  'refine_design',
  1,
  1.5,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM day5_phase),
  (SELECT id FROM template_1),
  'plan_next_steps',
  'ネクストステップ計画',
  '検証内容をまとめ、開発フェーズへの移行計画を策定。',
  'scalability_review',
  1,
  1.0,
  3,
  datetime('now','localtime');

-- Template 2: UX Research Flow
INSERT INTO workflow_templates (name, description, status, created_at, updated_at, created_by)
VALUES (
  'UXリサーチフロー',
  'ユーザーの行動・ニーズ・課題を深掘りするためのリサーチプロセス。ペルソナ・ジャーニーマップ・インサイト抽出で、データに基づいたデザイン戦略を構築。',
  'active',
  datetime('now','localtime'),
  datetime('now','localtime'),
  'system'
);

-- Get template 2 ID and create phases
WITH template_2 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'UXリサーチフロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_phases (template_id, phase_key, phase_label, specialist_type, phase_order, is_parallel, created_at)
SELECT id, 'persona_research', 'ペルソナ調査', 'researcher', 1, 0, datetime('now','localtime') FROM template_2
UNION ALL
SELECT id, 'journey_mapping', 'ジャーニーマップ作成', 'designer', 2, 0, datetime('now','localtime') FROM template_2
UNION ALL
SELECT id, 'insight_extraction', 'インサイト抽出', 'researcher', 3, 0, datetime('now','localtime') FROM template_2;

-- Persona Research Phase
WITH persona_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'persona_research' ORDER BY created_at DESC LIMIT 1
),
template_2 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'UXリサーチフロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM persona_phase),
  (SELECT id FROM template_2),
  'define_research_scope',
  'リサーチスコープ定義',
  'リサーチの対象ユーザー層・目的・質問項目を定義。',
  NULL,
  1,
  1.5,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM persona_phase),
  (SELECT id FROM template_2),
  'conduct_interviews',
  'ユーザーインタビュー',
  'ターゲットユーザーへの1対1インタビューを実施。10人以上の対象者からデータ収集。',
  'define_research_scope',
  1,
  3.0,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM persona_phase),
  (SELECT id FROM template_2),
  'create_personas',
  'ペルソナ作成',
  'インタビューデータをもとに、代表的なペルソナ（ユーザープロフィール）を3〜5個作成。',
  'conduct_interviews',
  1,
  2.0,
  3,
  datetime('now','localtime');

-- Journey Mapping Phase
WITH journey_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'journey_mapping' ORDER BY created_at DESC LIMIT 1
),
template_2 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'UXリサーチフロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM journey_phase),
  (SELECT id FROM template_2),
  'identify_touchpoints',
  'タッチポイント特定',
  'ユーザーがサービスと接点を持つすべてのポイント（認知・購入・サポート等）を洗い出す。',
  NULL,
  1,
  1.5,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM journey_phase),
  (SELECT id FROM template_2),
  'map_user_journey',
  'ジャーニーマップ作成',
  'ペルソナ別にタッチポイント・感情・課題をビジュアル化したジャーニーマップを作成。',
  'identify_touchpoints',
  1,
  2.5,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM journey_phase),
  (SELECT id FROM template_2),
  'identify_pain_points',
  'ペインポイント特定',
  'ジャーニーマップ上で、ユーザーが最も不満・困難を感じるポイントを指摘。',
  'map_user_journey',
  1,
  1.0,
  3,
  datetime('now','localtime');

-- Insight Extraction Phase
WITH insight_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'insight_extraction' ORDER BY created_at DESC LIMIT 1
),
template_2 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'UXリサーチフロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM insight_phase),
  (SELECT id FROM template_2),
  'synthesize_data',
  'データ統合・分析',
  'インタビュー・ジャーニーマップデータを統合し、共通パターン・傾向を分析。',
  NULL,
  1,
  2.0,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM insight_phase),
  (SELECT id FROM template_2),
  'extract_insights',
  'インサイト抽出',
  'ユーザー行動の背後にある深い洞察・ニーズ・課題を導出。',
  'synthesize_data',
  1,
  1.5,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM insight_phase),
  (SELECT id FROM template_2),
  'document_findings',
  'リサーチレポート作成',
  'ペルソナ・ジャーニーマップ・インサイトをまとめた リサーチレポートを作成・共有。',
  'extract_insights',
  1,
  1.5,
  3,
  datetime('now','localtime');

-- Template 3: Prototype Auto-generation Flow
INSERT INTO workflow_templates (name, description, status, created_at, updated_at, created_by)
VALUES (
  'プロトタイプ自動生成フロー',
  'AIを活用した快速プロトタイピングフロー。ワイヤーフレーム→モックアップ自動生成→インタラクション定義→ステークホルダーレビューの4段階で、数時間で高品質プロトタイプを実現。',
  'active',
  datetime('now','localtime'),
  datetime('now','localtime'),
  'system'
);

-- Get template 3 ID and create phases
WITH template_3 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'プロトタイプ自動生成フロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_phases (template_id, phase_key, phase_label, specialist_type, phase_order, is_parallel, created_at)
SELECT id, 'wireframe_design', 'ワイヤーフレーム設計', 'designer', 1, 0, datetime('now','localtime') FROM template_3
UNION ALL
SELECT id, 'mockup_generation', 'モックアップ自動生成', 'designer', 2, 0, datetime('now','localtime') FROM template_3
UNION ALL
SELECT id, 'interaction_definition', 'インタラクション定義', 'designer', 3, 0, datetime('now','localtime') FROM template_3
UNION ALL
SELECT id, 'stakeholder_review', 'ステークホルダーレビュー', 'designer', 4, 0, datetime('now','localtime') FROM template_3;

-- Wireframe Design Phase
WITH wireframe_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'wireframe_design' ORDER BY created_at DESC LIMIT 1
),
template_3 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'プロトタイプ自動生成フロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM wireframe_phase),
  (SELECT id FROM template_3),
  'define_layout',
  'レイアウト定義',
  'ページのセクション・配置・コンテンツ構造を定義。グリッドシステムに基づいて設計。',
  NULL,
  1,
  1.5,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM wireframe_phase),
  (SELECT id FROM template_3),
  'create_wireframes',
  'ワイヤーフレーム作成',
  'Figma等で全ページのワイヤーフレームを作成。色・テキスト詳細は不要。',
  'define_layout',
  1,
  2.0,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM wireframe_phase),
  (SELECT id FROM template_3),
  'wireframe_review',
  'ワイヤーフレームレビュー',
  'UX・情報設計の観点からワイヤーフレームをレビュー・微調整。',
  'create_wireframes',
  1,
  1.0,
  3,
  datetime('now','localtime');

-- Mockup Generation Phase
WITH mockup_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'mockup_generation' ORDER BY created_at DESC LIMIT 1
),
template_3 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'プロトタイプ自動生成フロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM mockup_phase),
  (SELECT id FROM template_3),
  'ai_mockup_generation',
  'AI モックアップ自動生成',
  'AI（Claude Vision等）を使用してワイヤーフレームから自動的にモックアップを生成。',
  NULL,
  1,
  1.0,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM mockup_phase),
  (SELECT id FROM template_3),
  'refine_visuals',
  'ビジュアル調整',
  '自動生成されたモックアップの色・タイポグラフィ・スタイルを手動調整。',
  'ai_mockup_generation',
  1,
  1.5,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM mockup_phase),
  (SELECT id FROM template_3),
  'mockup_review',
  'モックアップレビュー',
  'デザイン品質・ブランド整合性をレビュー。',
  'refine_visuals',
  1,
  0.75,
  3,
  datetime('now','localtime');

-- Interaction Definition Phase
WITH interaction_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'interaction_definition' ORDER BY created_at DESC LIMIT 1
),
template_3 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'プロトタイプ自動生成フロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM interaction_phase),
  (SELECT id FROM template_3),
  'define_user_flows',
  'ユーザーフロー定義',
  'ボタン・フォーム・ナビゲーション等のインタラクションフローを定義。',
  NULL,
  1,
  1.5,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM interaction_phase),
  (SELECT id FROM template_3),
  'create_prototypes',
  'プロトタイプ作成',
  'Figma Prototype・Framer等を使用して、実際に操作できるインタラクティブプロトタイプを作成。',
  'define_user_flows',
  1,
  2.0,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM interaction_phase),
  (SELECT id FROM template_3),
  'usability_check',
  '操作性確認',
  '自分たちでプロトタイプを操作し、ユーザーフローの違和感がないか確認。',
  'create_prototypes',
  1,
  1.0,
  3,
  datetime('now','localtime');

-- Stakeholder Review Phase
WITH review_phase AS (
  SELECT id FROM wf_template_phases
  WHERE phase_key = 'stakeholder_review' ORDER BY created_at DESC LIMIT 1
),
template_3 AS (
  SELECT id FROM workflow_templates
  WHERE name = 'プロトタイプ自動生成フロー' ORDER BY created_at DESC LIMIT 1
)
INSERT INTO wf_template_tasks (phase_id, template_id, task_key, task_title, task_description, depends_on_key, priority, estimated_hours, task_order, created_at)
SELECT
  (SELECT id FROM review_phase),
  (SELECT id FROM template_3),
  'prepare_demo',
  'デモ準備',
  'ステークホルダー向けのプレゼンテーション・デモの台本を作成。',
  NULL,
  1,
  1.0,
  1,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM review_phase),
  (SELECT id FROM template_3),
  'conduct_review',
  'ステークホルダーレビュー',
  'プロトタイプをステークホルダー（顧客・経営陣等）に提示し、フィードバックを収集。',
  'prepare_demo',
  1,
  1.5,
  2,
  datetime('now','localtime')
UNION ALL
SELECT
  (SELECT id FROM review_phase),
  (SELECT id FROM template_3),
  'consolidate_feedback',
  'フィードバック統約',
  '複数のステークホルダーからのフィードバックを整理し、優先度を付与。',
  'conduct_review',
  1,
  1.0,
  3,
  datetime('now','localtime');

-- Create indexes for new templates
CREATE INDEX IF NOT EXISTS idx_workflow_templates_status_created_at
  ON workflow_templates(status, created_at DESC);
