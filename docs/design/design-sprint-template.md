# デザインスプリント業務フロー テンプレート仕様書

**テンプレート名**: Product Design Sprint (5-day)  
**作成日**: 2026-04-23  
**バージョン**: 1.0  
**ステータス**: Draft → Review → Published

---

## 1. テンプレート概要

### 1.1 目的

新規プロダクト機能またはプロダクト全体のUX設計を、**5日間の構造化フロー** で高速に検証・実装するための業務フローテンプレート。

### 1.2 期待効果

| 効果 | 期待値 |
|---|---|
| **設計期間の短縮** | 従来 2週間 → 5日（70%削減） |
| **アイデア検証の高速化** | 市場投入までの時間 短縮 |
| **チーム間の意思疎通** | 構造化フロー → 認識齟齬 0% |
| **成果物の品質** | 検証済みプロトタイプ + デザイン資産 |

### 1.3 適用対象

- ✅ 新規機能設計（MVP レベル）
- ✅ 既存機能のリデザイン
- ✅ UI/UX の部分的な改善
- ✅ ユーザー体験フロー全体の再設計

### 1.4 前提条件

- ビジョン / ユースケースが事前定義済み
- 参加者が最低5日間確保可能
- デザインツール（Figma等）へのアクセス可能

---

## 2. フェーズ構成（5段階）

### フェーズ全体フロー図

```
┌────────────────────────────────────────────────────────────────┐
│          Product Design Sprint (5-day)                          │
└────────────────────────────────────────────────────────────────┘

Monday (Day 1)
  └─ ビジョン確認・ペルソナ分析・スコープ定義
     参加者: Design Lead / PM / UX Researcher

Tuesday (Day 2)
  └─ ユーザージャーニー詳細化・情報アーキテクチャ定義
     参加者: UX Researcher / Product Designer / Developer
     並列可能: Wednesday 以降の準備開始

Wednesday (Day 3)
  ├─ ワイヤーフレーム・プロトタイプ設計
  ├─ バックエンド・API設計の並行
  └─ 並列実行: Product Designer と Developer

Thursday (Day 4)
  ├─ 高忠度プロトタイプ完成
  ├─ ユーザーテスト準備
  └─ 並列実行: デザイン仕上げ / テスト環境構築

Friday (Day 5)
  ├─ ユーザーテスト実施
  ├─ フィードバック統合
  ├─ 実装ロードマップ確定
  └─ 最終成果物レビュー

┌──────────────────────────────────────────┐
│    成果物交付＆次フェーズへ              │
└──────────────────────────────────────────┘
```

---

## 3. 各フェーズの詳細

### Phase 1: Monday - ビジョン確認・スコープ定義

**目標**: チーム全体がビジョンに統一、スコープを明確化

**タイムラインと活動**

| 時間 | 活動 | 担当 | 成果物 |
|---|---|---|---|
| 09:00-09:30 | ビジョン・ユースケース確認 | Design Lead / PM | Vision Statement |
| 09:30-10:30 | ペルソナ分析・フィードバック | UX Researcher | Persona Sheet |
| 10:30-11:30 | スコープ定義・制約条件確認 | Design Lead | Scope Document |
| 11:30-12:00 | チーム確認・質問対応 | 全員 | Alignment Check |
| 13:00-14:00 | ユースケース詳細化 | PM / Designer | Use Case Matrix |
| 14:00-15:00 | リスク・課題の抽出 | Design Lead | Risk Register |
| 15:00-16:00 | 最終確認・方針決定 | 全員 | Monday Summary |

**チェックポイント（Go/No-Go判定）**

```
□ ビジョンに対する質問 / 懸念 = 0（全員が理解）
□ スコープが SMART 形式で定義されているか
□ リスク / 課題が特定済みか
□ 全員が同じゴールを向いているか

Go → Tuesday に進む
No-Go → ビジョン再定義の上、Tuesday スタート
```

**入力（前提条件）**
- Product Vision（ビジョンステートメント）
- Target Persona（ターゲットペルソナ1-3人）
- Constraints（技術的・ビジネス的制約条件）

**出力（成果物）**
- Vision Clarification Document
- Persona Sheet（詳細化版）
- Scope Definition（SMART形式）
- Risk & Issue Register

---

### Phase 2: Tuesday - ユーザージャーニー詳細化・IA定義

**目標**: ユーザーフローを可視化、情報構造を定義

**タイムラインと活動**

| 時間 | 活動 | 担当 | 成果物 |
|---|---|---|---|
| 09:00-10:00 | ユーザージャーニー詳細化 | UX Researcher / Designer | Detailed Journey Map |
| 10:00-11:30 | ユースケースフロー設計 | Designer | Use Case Flow Diagram |
| 11:30-12:00 | API / DB 初期設計方針 | Developer | Tech Requirements |
| 13:00-14:30 | 情報アーキテクチャ (IA) 定義 | Designer / Developer | IA Diagram |
| 14:30-15:30 | ナビゲーション構造設計 | Designer | Navigation Map |
| 15:30-16:00 | チーム確認・調整 | 全員 | Tuesday Summary |

**並列実行の準備**

Wednesday から Product Designer と Developer が並列で作業可能にするため、以下を確定：

```
Product Designer 担当
  ├─ ワイヤーフレーム詳細化
  ├─ ビジュアル仕様定義
  └─ UI成分ライブラリ選定

Developer 担当
  ├─ API エンドポイント設計
  ├─ DB スキーマ初期案
  └─ 環境構築・リポジトリ準備
```

**成果物**
- Detailed User Journey Map（ペルソナ別）
- Use Case Flow Diagram（Swimlane形式）
- Information Architecture Document
- API Specification（初期版）
- Database Schema（初期版）

---

### Phase 3: Wednesday - ワイヤーフレーム＆プロトタイプ設計（並列実行）

**目標**: UI設計と技術実装の並列進行開始

**Product Designer 担当**

| 時間 | 活動 | 成果物 |
|---|---|---|
| 09:00-10:30 | ワイヤーフレーム作成 (Figma) | Wireframe Components |
| 10:30-12:00 | UI仕様書作成（色・フォント・スペーシング） | UI Style Guide |
| 13:00-14:30 | ビジュアルデザイン作成 | High-Fidelity Mockups |
| 14:30-16:00 | インタラクション仕様定義 | Interaction Spec |

**Developer 担当**

| 時間 | 活動 | 成果物 |
|---|---|---|
| 09:00-10:00 | 環境構築・リポジトリ準備 | Development Environment |
| 10:00-11:30 | API エンドポイント実装 | REST API Stubs |
| 11:30-12:00 | DB マイグレーション準備 | Migration Scripts |
| 13:00-14:30 | フロントエンド基盤構築 | React/Vue Project Setup |
| 14:30-16:00 | ダミーデータ準備 | Mock Data |

**同期ポイント**
- 11:00 - Designer と Developer で API-UI 仕様確認（15分）
- 15:00 - チーム全体で進捗共有（30分）

**成果物**
- Wireframes（全画面対応）
- High-Fidelity Mockups
- UI Style Guide & Design System
- API Specification（詳細版）
- Database Schema（最終版）
- 開発リポジトリセットアップ

---

### Phase 4: Thursday - 高忠度プロトタイプ完成＆テスト準備

**目標**: ユーザーテスト可能なプロトタイプ完成

**Product Designer 担当**

| 時間 | 活動 | 成果物 |
|---|---|---|
| 09:00-11:00 | デザイン詳細調整 | Polished Design Files |
| 11:00-12:00 | Figma Prototype 作成 | Interactive Prototype |
| 13:00-15:00 | テスト用画面状態定義 | Test Scenario Screens |
| 15:00-16:00 | デザイン最終レビュー | Design Review Report |

**Developer 担当**

| 時間 | 活動 | 成果物 |
|---|---|---|
| 09:00-10:00 | フロントエンド実装（主要画面） | Frontend Implementation |
| 10:00-12:00 | API 実装・統合テスト | API + Frontend Integration |
| 13:00-15:00 | UI 調整・デバッグ | Bug Fix & Polish |
| 15:00-16:00 | テスト環境デプロイ | Test Environment Ready |

**テスト準備タスク**
- テストシナリオ作成（UX Researcher）
- テスト参加者のスケジューリング
- テスト環境アクセス確認
- Figma Prototype のテスト用セットアップ

**成果物**
- 仕上げられたデザインファイル
- インタラクティブプロトタイプ（Figma）
- 実装済みフロントエンド（テスト用）
- API実装（本番環境展開前）
- テストシナリオ・テストプラン

---

### Phase 5: Friday - ユーザーテスト＆実装ロードマップ確定

**目標**: ユーザーフィードバック取得 & 実装予定確定

**午前：ユーザーテスト実施**

| 時間 | 活動 | 参加者 |
|---|---|---|
| 09:00-10:00 | テスト環境最終確認 | UX Researcher / Developer |
| 10:00-12:00 | ユーザーテスト実施 | ペルソナユーザー 3-5人 |
| 13:00-14:00 | テスト結果集計・分析 | UX Researcher / Designer |
| 14:00-15:00 | フィードバック統合計画立案 | 全員 |

**午後：実装ロードマップ確定**

| 時間 | 活動 | 成果物 |
|---|---|---|
| 15:00-16:00 | テストフィードバック統合 | Updated Design Spec |
| 16:00-16:30 | 実装ロードマップ確定 | Implementation Roadmap |
| 16:30-17:00 | 最終レビュー・承認 | Go-to-Implement Sign-off |

**テスト結果への対応**

```
【テスト観点】
- タスク完了率（成功した user flow %)
- エラー率（UI confusion）
- 満足度（SUS スコア）
- 改善提案数

【対応レベル】
Critical（タスク完了率 < 70%）
  → デザイン大幅改訂 → 再テスト（土日対応）
  
Major（タスク完了率 70-85%）
  → 実装前に修正（実装計画に反映）
  
Minor（タスク完了率 > 85%）
  → 実装後の改善（Phase 2で対応）
```

**成果物（最終交付）**
- ユーザーテスト結果報告書
- デザイン最終版（Figma）
- API 実装完了版
- フロントエンド実装（テスト済み）
- 実装ロードマップ（Phase 2 詳細計画）
- 引き継ぎドキュメント（開発チーム向け）

---

## 4. 参加者・役割定義

### 4.1 必須メンバー

| 役割 | 担当 | 時間配分 | 要件 |
|---|---|---|---|
| **Design Lead** | スコープ定義・リスク管理・チーム調整 | 100% (5日間) | UX/デザイン経験 5年以上 |
| **Product Designer** | UI/UX設計・プロトタイプ | 80% (4日間, 木金) | デザイン実装経験 3年以上 |
| **UX Researcher** | ペルソナ分析・ユーザーテスト | 60% (月火、金) | リサーチ経験 2年以上 |
| **Developer** | 技術仕様・API/フロントエンド実装 | 100% (水木金) | フルスタック経験 3年以上 |
| **PM** | ビジョン確認・スコープ管理 | 40% (月、火午前) | プロダクト企画経験 |

### 4.2 オプションメンバー

- **QA**: テスト計画立案（金曜午前）
- **マーケティング**: ローンチ計画確認（金曜午後）

---

## 5. 成果物チェックリスト

### Phase 1 成果物

- [ ] Vision Clarification Document（200-300語）
- [ ] Persona Sheet（ターゲット3名分）
- [ ] Scope Definition（SMART形式）
- [ ] Risk & Issue Register（5-10件）

### Phase 2 成果物

- [ ] Detailed User Journey Map（ペルソナ別×3）
- [ ] Use Case Flow Diagram（Swimlane形式）
- [ ] Information Architecture Document
- [ ] API Specification v1（全エンドポイント定義）
- [ ] Database Schema v1（テーブル定義）

### Phase 3 成果物

- [ ] Wireframes（全画面）
- [ ] High-Fidelity Mockups（主要画面 ≥80%）
- [ ] UI Style Guide
- [ ] API Specification v2（詳細実装仕様）
- [ ] Database Schema v2（最終版）
- [ ] 開発リポジトリ（セットアップ完了）

### Phase 4 成果物

- [ ] Polished Design Files（Figmaプロジェクト）
- [ ] Interactive Prototype（デモ可能）
- [ ] Frontend Implementation（≥80%完成）
- [ ] API Implementation（全エンドポイント実装）
- [ ] Test Scenario Document

### Phase 5 成果物

- [ ] User Test Report（テスト結果・分析）
- [ ] Design Final Edition（テスト結果反映）
- [ ] Implementation Roadmap（Phase 2以降の詳細計画）
- [ ] Handover Document（開発チーム向け）
- [ ] Go-to-Implement Sign-off（承認）

---

## 6. DB登録仕様（task-manager-sqlite）

### 6.1 テンプレートメタデータ

```json
{
  "name": "Product Design Sprint (5-day)",
  "description": "5日間の構造化デザインスプリント。ビジョン確認～ユーザーテスト完了まで。",
  "version": "1.0",
  "status": "active",
  "category": "design",
  "estimated_duration_hours": 40,
  "specialist_types": ["Design Lead", "Product Designer", "UX Researcher", "Developer"],
  "icon": "🎨",
  "tags": ["design", "sprint", "5-day", "ux", "product"]
}
```

### 6.2 フェーズ定義

```json
[
  {
    "phase_key": "monday-vision",
    "phase_order": 1,
    "phase_label": "Day 1: Vision Alignment",
    "specialist_type": "Design Lead",
    "specialist_count": 4,
    "task_count": 6,
    "estimated_hours": 7,
    "is_parallel": false,
    "description": "ビジョン確認・ペルソナ分析・スコープ定義"
  },
  {
    "phase_key": "tuesday-journey",
    "phase_order": 2,
    "phase_label": "Day 2: Journey & IA",
    "specialist_type": "UX Researcher",
    "specialist_count": 3,
    "task_count": 6,
    "estimated_hours": 7,
    "is_parallel": true,
    "description": "ユーザージャーニー詳細化・情報アーキテクチャ定義"
  },
  {
    "phase_key": "wednesday-design",
    "phase_order": 3,
    "phase_label": "Day 3: Wireframe & API",
    "specialist_type": "Product Designer",
    "specialist_count": 2,
    "task_count": 8,
    "estimated_hours": 8,
    "is_parallel": true,
    "description": "ワイヤーフレーム・API設計を並列実行"
  },
  {
    "phase_key": "thursday-prototype",
    "phase_order": 4,
    "phase_label": "Day 4: Prototype Ready",
    "specialist_type": "Product Designer",
    "specialist_count": 2,
    "task_count": 8,
    "estimated_hours": 8,
    "is_parallel": true,
    "description": "高忠度プロトタイプ完成・テスト準備"
  },
  {
    "phase_key": "friday-test",
    "phase_order": 5,
    "phase_label": "Day 5: User Test & Handover",
    "specialist_type": "UX Researcher",
    "specialist_count": 4,
    "task_count": 6,
    "estimated_hours": 7,
    "is_parallel": false,
    "description": "ユーザーテスト実施・実装ロードマップ確定"
  }
]
```

### 6.3 ノード（タスク）定義例

```json
[
  {
    "template_id": "<TEMPLATE_ID>",
    "node_key": "day1-vision-confirm",
    "node_type": "task",
    "label": "Vision & Usecase Confirmation",
    "role": "Design Lead",
    "phase_key": "monday-vision",
    "description": "ビジョン・ユースケース確認（09:00-09:30）",
    "estimated_hours": 0.5
  },
  {
    "template_id": "<TEMPLATE_ID>",
    "node_key": "day2-journey-mapping",
    "node_type": "task",
    "label": "User Journey Detailed Mapping",
    "role": "UX Researcher",
    "phase_key": "tuesday-journey",
    "description": "ユーザージャーニー詳細化（09:00-10:00）",
    "estimated_hours": 1.0
  }
  // ... 他のノード
]
```

### 6.4 エッジ（遷移）定義

```json
[
  {
    "template_id": "<TEMPLATE_ID>",
    "from_node_key": "day1-vision-confirm",
    "to_node_key": "day2-journey-mapping",
    "condition": null,
    "condition_label": "Day 1 完了後、自動遷移",
    "priority": 0
  }
  // ... 他の遷移
]
```

---

## 7. 実装ガイドライン

### テンプレート登録手順

1. **DB接続確認**
   ```bash
   sqlite3 ~/.claude/skills/task-manager-sqlite/tasks.sqlite
   .schema workflow_templates
   ```

2. **テンプレートレコード挿入**
   ```sql
   INSERT INTO workflow_templates (name, description, version, status)
   VALUES ('Product Design Sprint (5-day)', '...', 1, 'active');
   ```

3. **フェーズレコード挿入**
   ```sql
   INSERT INTO wf_template_phases (template_id, phase_key, phase_order, ...)
   VALUES (...);
   ```

4. **ノード・エッジ挿入**
   - 各ノード（タスク）を挿入
   - エッジ（遷移ルール）を定義

5. **テスト実行**
   ```bash
   python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py template apply \
     --template-name "Product Design Sprint (5-day)" \
     --project-name "test-sprint"
   ```

---

## 8. トラブルシューティング

| 問題 | 原因 | 対応 |
|---|---|---|
| 並列実行がうまく回らない | タスク依存関係が不明確 | エッジ定義を確認・修正 |
| テスト結果が悪い（完了率<70%） | UI設計に課題あり | Day 4終了後に緊急修正 |
| 参加者が時間を確保できない | リソース不足 | PM に相談、フェーズ分割を検討 |

---

## 9. 次のステップ

### Phase 2: 実装フェーズ（2-3週間）
- デザイン完全実装
- ユーザーテストに基づく改善
- ローンチ準備

### Phase 3: 運用・最適化（継続的）
- ユーザーフィードバック収集
- デザインシステムへの統合
- 継続的改善

---

## 参考資料

- **Google Design Sprint**: https://www.gv.com/sprint
- **THEBRANCH UX System**: docs/design/ux-system.md
- **User Journey**: docs/design/user-journey.md
- **Information Architecture**: docs/design/INFORMATION_ARCHITECTURE.md

---

**最終更新**: 2026-04-23 21:30  
**メンテナンス責任者**: Product Design Team
