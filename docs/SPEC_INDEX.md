# THEBRANCH 仕様書インデックス

AIエージェント・Claudeが仕様書を素早く参照するためのナビゲーションファイル。
「〇〇の設計を確認したい」場合はまずこのファイルを参照し、該当ドキュメントのパスを特定すること。

---

## システム仕様（ルート）

| ファイル | タイトル | 内容 |
|---|---|---|
| `feature_spec.md` | THEBRANCH 機能仕様書 | プラットフォーム全体の機能一覧・要件 |
| `architecture-design.md` | ワークフローテンプレートシステム - システムアーキテクチャ設計 | レイヤー構成・モジュール設計・インターフェース定義 |
| `data-model.md` | ワークフローテンプレートシステム - データモデル設計 | SQLiteスキーマ・テーブル設計 |
| `flow-design.md` | ワークフローテンプレートシステム - 処理フロー設計 | 業務フロー・処理シーケンス |
| `BDD_DESIGN.md` | BDD 業務フロー高水準設計 | BDDアーキテクチャ概要・フロー |
| `business_model_canvas.md` | THEBRANCH ビジネスモデルキャンバス | ビジネスモデル全体像 |
| `personas.md` | THEBRANCH ペルソナドキュメント | ターゲットユーザーペルソナ |
| `validation_report.md` | WF#13 最終ステップ 検証レポート | 実装検証結果 |
| `workflow-template-design.md` | ワークフローテンプレートシステム - Phase 2 技術設計 | Phase 2 技術設計詳細 |
| `WORKFLOW-TEMPLATE-README.md` | ワークフローテンプレート機能 - 要件ドキュメント | テンプレート機能要件 |
| `PROTOTYPE_DESIGN.md` | THEBRANCH プロトタイプ設計 | プロトタイプUI設計 |
| `phase2-summary.md` | Phase 2 技術調査 - 成果物サマリ | Phase 2 成果まとめ |
| `phase4-detailed-interface-design.md` | Phase 4 詳細インターフェース設計 | I/F詳細仕様 |
| `phase5-test-code-design.md` | Phase 5 テストコード設計 | テスト設計・コード仕様 |
| `slack-discord-setup.md` | Slack/Discord 統合セットアップガイド | 外部連携セットアップ手順 |

## API 仕様（api/ / ルート）

| ファイル | タイトル | 内容 |
|---|---|---|
| `api/marketplace-api-spec.md` | マーケットプレイス API 仕様書 v1.0 | マーケットプレイスAPI完全仕様 |
| `api-spec.md` | API 仕様書 - THEBRANCH マーケットプレイス | マーケットプレイスバックエンドAPI |
| `API_SPEC_ONBOARDING.md` | オンボーディング API 仕様ドキュメント | オンボーディングフローAPI |
| `api-spec-departments.md` | 部署管理バックエンド API 仕様書 | 部署CRUD・管理API |
| `api-spec-portfolio.md` | ポートフォリオ管理 API 仕様 | ポートフォリオAPI仕様 |

## 設計書（design/）

### UX・フロント設計

| ファイル | タイトル | 内容 |
|---|---|---|
| `design/onboarding-flow.md` | オンボーディングフロー設計 | ユーザーオンボーディングUXフロー |
| `design/user-journey.md` | THEBRANCH ユーザージャーニーマップ | ユーザー体験の全体フロー |
| `design/ux-vision-phase1.md` | THEBRANCH UX ビジョン & ユーザージャーニーマップ | UXビジョン・Phase1設計 |
| `design/ux-system.md` | THEBRANCH UX デザインシステム | UXデザインシステム定義 |
| `design/INFORMATION_ARCHITECTURE.md` | THEBRANCH プラットフォーム 情報アーキテクチャ設計 | IA・ナビゲーション設計 |
| `design/WIREFRAMES_DESIGN.md` | THEBRANCH プラットフォーム ワイヤーフレーム設計 | 画面ワイヤーフレーム |
| `design/AI-DEPARTMENT-SETTINGS-WIREFRAME.md` | AI 部署設定UI ワイヤーフレーム | 部署設定画面ワイヤーフレーム |
| `design/ORGANIZATION-DASHBOARD.md` | 組織ダッシュボード設計 | ダッシュボード画面設計 |
| `design/EXISTING_UI_AUDIT.md` | THEBRANCH 既存ダッシュボード UI監査 | 現行UI監査結果 |

### マーケットプレイス設計

| ファイル | タイトル | 内容 |
|---|---|---|
| `design/marketplace_api_design.md` | AIエージェント マーケットプレイス API 設計 | マーケットプレイスAPI設計 |
| `design/marketplace_db_schema.md` | AIエージェント マーケットプレイス DB スキーマ設計 | マーケットプレイスDB設計 |
| `design/marketplace_frontend_design.md` | AIエージェント マーケットプレイス フロントエンド設計 | マーケットプレイスUI設計 |
| `design/marketplace-ux.md` | Phase 4 部署マーケットプレイス UX 設計 | マーケットプレイスUX |
| `design/marketplace-ux-review.md` | marketplace-ux.md 品質レビュー & ユーザージャーニー検証 | UXレビュー結果 |

### システム・アーキテクチャ設計

| ファイル | タイトル | 内容 |
|---|---|---|
| `design/THEBRANCH_DETAILED_DESIGN.md` | THEBRANCH プラットフォーム詳細設計ドキュメント | プラットフォーム全体詳細設計 |
| `design/DATA-MODEL.md` | BDD業務フロー データモデル設計書 | SQLite + KuzuDB スキーマ設計 |
| `design/BDD-Architecture.md` | BDD業務フロー アーキテクチャ設計書 | BDDアーキテクチャ詳細 |
| `design/FLOW-DIAGRAM.md` | BDD業務フロー 実行フロー図 | フロー図・シーケンス図 |
| `design/MULTITENANCY-ARCHITECTURE.md` | マルチテナント対応 アーキテクチャ設計書 | マルチテナント設計 |
| `design/auth_multitenancy_design.md` | 認証・マルチテナント・セッション管理 設計書 | 認証・セッション設計 |
| `design/AGENT_TASK_DELEGATION_API.md` | エージェント間タスク委譲API - DBスキーマ・API I/F設計書 | エージェント委譲API設計 |
| `design/WORKFLOW-TEMPLATE-DESIGN.md` | ワークフローテンプレート - API・UI 設計書 | テンプレートAPI・UI設計 |
| `design/WORKFLOW-TEMPLATE-MODEL.md` | ワークフローテンプレート - データモデル設計 | テンプレートデータモデル |
| `design/wave28_workflow_autogen_api_design.md` | 自然言語→DAG変換 API・スキーマ設計書 | 自然言語からDAG自動生成API |
| `design/AUTO_ASSIGN_PENDING_DESIGN.md` | auto_assign_pending.py — タスク自動割り当て設計書 | タスク自動割り当てロジック設計 |
| `design/department-templates-schema.md` | 部署テンプレートライブラリ - スキーマ・業務フロー設計 | 部署テンプレートDB設計 |
| `design/accounting_department_design.md` | 経理部AIエージェント基盤設計 | 経理部エージェント設計 |

### SLA・セキュリティ設計

| ファイル | タイトル | 内容 |
|---|---|---|
| `design/sla-api-specification.md` | SLA Management API Specification | SLA管理API完全仕様 |
| `design/sla-metrics-specification.md` | SLA Metrics Calculation Specification | SLAメトリクス計算仕様 |
| `design/sla-design-review.md` | SLA Management Design Review | SLA設計レビュー結果 |
| `design/security-enhancement-v1.md` | セキュリティ強化・ゼロトラスト実装 v1 設計書 | セキュリティ強化設計 |
| `design/slack-discord-integration.md` | Slack/Discord 統合設計ドキュメント | Slack/Discord連携設計 |

### デザインシステム

| ファイル | タイトル | 内容 |
|---|---|---|
| `design/DESIGN_SYSTEM.md` | THEBRANCH プラットフォーム デザインシステム基礎 | デザインシステム基盤 |
| `design/DESIGN_SYSTEM_SETUP_SUMMARY.md` | THEBRANCH デザインシステム構築準備 - 完了レポート | デザインシステム構築完了レポート |
| `design/COLOR_PALETTE_SPEC.md` | THEBRANCH カラーパレット仕様書 | カラーパレット定義 |
| `design/TYPOGRAPHY_GUIDELINE.md` | THEBRANCH タイポグラフィガイドライン | フォント・タイポグラフィ規定 |
| `design/FIGMA_SETUP_GUIDE.md` | THEBRANCH Figma デザインシステムセットアップガイド | Figmaセットアップ手順 |

### プロダクト・ペルソナ分析

| ファイル | タイトル | 内容 |
|---|---|---|
| `design/PERSONA_ANALYSIS_DEEP_DIVE.md` | THEBRANCH ペルソナ分析：課題・ユースケース深掘り版 | ペルソナ詳細分析 |
| `design/PERSONA_FEATURE_REQUIREMENTS.md` | THEBRANCH ペルソナ機能要件仕様書 | ペルソナ別機能要件 |
| `design/user_segment_value_matrix.md` | ユーザーセグメント × ビジネス価値マトリクス | セグメント×価値マトリクス |
| `design/VISION_FEATURE_MAPPING.md` | THEBRANCH UX ビジョン → 機能要件マッピング | ビジョンから機能へのマッピング |
| `design/IMPLEMENTATION_ROADMAP_2428.md` | THEBRANCH 実装ロードマップ | 実装フェーズ・ロードマップ |
| `design/market_analysis.md` | THEBRANCH 市場・ビジネス分析 | 市場分析・競合分析 |
| `design/TASK_SPECIFICATIONS.md` | タスク詳細仕様書 | タスク管理詳細仕様 |

### テスト・BDD設計

| ファイル | タイトル | 内容 |
|---|---|---|
| `design/TEST-PLAN.md` | BDD業務フロー テスト計画書 | BDDテスト計画・方針 |
| `design/business-flow-template.md` | THEBRANCH ビジネスフローテンプレート v1 | ビジネスフローテンプレート定義 |
| `design/design-sprint-template.md` | デザインスプリント業務フロー テンプレート仕様書 | デザインスプリントテンプレート |
| `design/product-design-workflow.md` | Product Design Workflow - 統合ガイド | 設計ワークフロー統合ガイド |

## プロダクト仕様（product/）

| ファイル | タイトル | 内容 |
|---|---|---|
| `product/vision.md` | THEBRANCH プロダクトビジョン | プロダクトビジョン・方向性 |
| `product/spec.md` | THEBRANCH 機能仕様書 | プロダクト機能仕様 |
| `product/feature_spec.md` | THEBRANCH 機能仕様化・UIプロトタイプ実装ガイド | 機能仕様→実装ガイド |
| `product/prototype.md` | THEBRANCH プロトタイプ設計 | プロトタイプ設計書 |
| `product/user_research.md` | THEBRANCHユーザー課題研究 | ユーザー課題リサーチ結果 |

## テスト（test_reports/）

| ファイル | タイトル | 内容 |
|---|---|---|
| `test_reports/bdd_poc_test_2_report_20260419.md` | BDD PoC テスト #2: 統合受け入れテスト（4段階）レポート | BDD統合テスト結果 |

---

## クイックリファレンス：何を調べるか → どこを見るか

| 知りたいこと | 参照先 |
|---|---|
| API エンドポイント一覧 | `api/marketplace-api-spec.md`, `api-spec.md`, `API_SPEC_ONBOARDING.md` |
| DBスキーマ・テーブル設計 | `data-model.md`, `design/DATA-MODEL.md`, `design/marketplace_db_schema.md` |
| 画面設計・UI仕様 | `design/WIREFRAMES_DESIGN.md`, `design/ORGANIZATION-DASHBOARD.md` |
| オンボーディングフロー | `design/onboarding-flow.md`, `API_SPEC_ONBOARDING.md` |
| マルチテナント・認証 | `design/MULTITENANCY-ARCHITECTURE.md`, `design/auth_multitenancy_design.md` |
| SLA管理 | `design/sla-api-specification.md`, `design/sla-metrics-specification.md` |
| エージェント設計 | `design/AGENT_TASK_DELEGATION_API.md`, `design/accounting_department_design.md` |
| セキュリティ | `design/security-enhancement-v1.md` |
| ワークフローテンプレート | `design/WORKFLOW-TEMPLATE-DESIGN.md`, `design/WORKFLOW-TEMPLATE-MODEL.md` |
| プロダクトビジョン | `product/vision.md`, `business_model_canvas.md` |
| テスト計画 | `design/TEST-PLAN.md`, `test_reports/` |
| デザインシステム | `design/DESIGN_SYSTEM.md`, `design/COLOR_PALETTE_SPEC.md` |
