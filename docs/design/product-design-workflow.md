# Product Design Workflow - 統合ガイド

**作成日**: 2026-04-26  
**バージョン**: 1.0  
**参照ドキュメント**: design-sprint-template.md / ux-system.md / user-journey.md  

---

## 1. 概要

このドキュメントは、THEBRANCH プラットフォーム上でのプロダクト設計業務フローを統合したガイドです。**ユーザー調査 → UX 設計 → ワイヤーフレーム → プロトタイプ → 設計レビュー → 実装仕様書** の一連の流れを体系化しています。

### 1.1 想定対象

- 新機能の UI/UX 設計
- 既存機能のリデザイン
- ユーザー体験全体の最適化
- MVP レベルの迅速な設計検証

### 1.2 期待効果

| メトリクス | 期待値 |
|---|---|
| 設計期間短縮 | 従来 2週間 → 5日（70%削減） |
| チーム認識齟齬 | 0% （構造化フロー） |
| ユーザーテスト | 週1回以上の検証 |
| 実装品質向上 | 設計検証済みプロトタイプ ベース |

---

## 2. 設計フロー（5ステップ）

```
┌────────────────────────────────────────────────────────────┐
│               Product Design Workflow                       │
│           UX リサーチ → 実装仕様書                           │
└────────────────────────────────────────────────────────────┘

Step 1: ユーザー調査・ペルソナ定義
  ├─ ユーザージャーニーマッピング
  ├─ タッチポイント分析
  └─ Pain Points & Opportunities 抽出
  
Step 2: UX システム設計
  ├─ デザインシステム定義
  ├─ コンポーネント仕様書
  ├─ インタラクションパターン
  └─ アクセシビリティガイドライン
  
Step 3: ワイヤーフレーム・プロトタイプ設計
  ├─ ロー忠度ワイヤーフレーム（Day 1-2）
  ├─ ハイ忠度プロトタイプ（Day 3-4）
  └─ ユーザーテスト環境構築（Day 4）
  
Step 4: 設計レビュー・フィードバック統合
  ├─ ユーザーテスト実施
  ├─ ステークホルダーレビュー
  ├─ フィードバック分類・優先度付け
  └─ 設計修正（2-3 ラウンド）
  
Step 5: 実装仕様書・デザインシステム成果物
  ├─ 詳細仕様書（コンポーネント仕様・状態遷移）
  ├─ Figma Design Tokens
  ├─ 実装ロードマップ
  └─ QA テストケース抽出
```

---

## 3. 各ステップの詳細

### Step 1: ユーザー調査・ペルソナ定義（Day 1）

**目標**: ターゲットユーザーの理解を深め、設計の指針を確定

**活動内容**

| タスク | 説明 | 担当 | 成果物 |
|---|---|---|---|
| ビジョン・スコープ確認 | プロダクトビジョンの統一 | PM / Design Lead | Vision Statement |
| ユーザーリサーチ | ターゲットユーザー分析 | UX Researcher | User Research Report |
| ペルソナ定義 | 代表的なユーザー像作成 | Designer / PM | Persona Sheet (3-5個) |
| ユーザージャーニー | タッチポイント・感情曲線マッピング | UX Researcher | User Journey Map |
| Pain Points 抽出 | 課題・機会の特定 | 全員 | Opportunity Matrix |

**参照**: `user-journey.md` の「ユーザー調査」セクション

**チェックリスト**
- [ ] ペルソナが 3 個以上定義されている
- [ ] 各ペルソナの Goal / Pain Points が明確
- [ ] User Journey に感情スコア（-5～+5）がマッピング済み

---

### Step 2: UX システム設計（Day 2）

**目標**: 設計の一貫性を保つための Design System を確立

**活動内容**

| タスク | 説明 | 担当 | 成果物 |
|---|---|---|---|
| デザインシステム定義 | カラー・タイポグラフィ・スペーシングルール | Designer | Design Tokens |
| コンポーネント設計 | 再利用可能な UI コンポーネント | Designer | Component Library |
| インタラクション定義 | マイクロインタラクション・アニメーション | Designer | Animation Spec |
| アクセシビリティ | WCAG 2.1 AA に準拠したガイドライン | Designer / QA | A11y Checklist |
| ブランド統一性 | THEBRANCH ビジュアルアイデンティティ | Designer | Brand Guidelines |

**参照**: `ux-system.md` の「デザインシステム」セクション

**チェックリスト**
- [ ] Figma Component Library が作成済み
- [ ] Design Tokens (カラー・サイズ・スペーシング) が定義済み
- [ ] WCAG 2.1 AA チェックリストが作成済み

---

### Step 3: ワイヤーフレーム・プロトタイプ設計（Day 3-4）

**目標**: ロー忠度から ハイ忠度へ段階的にプロトタイプを完成させ、ユーザーテスト可能な状態に

**活動内容**

#### 3a. ロー忠度ワイヤーフレーム（Day 2-3）

| タスク | 説明 | 担当 | 成果物 |
|---|---|---|---|
| ページ構造設計 | 主要ページ・モーダル・フロー | Designer | Low-fi Wireframes (Figma) |
| ユーザーフロー定義 | 画面遷移・ユースケースフロー | Designer / PM | User Flow Diagram |
| インタラクション箇所明示 | 動作が必要な箇所のマーク | Designer | Wireframe with Annotations |

#### 3b. ハイ忠度プロトタイプ（Day 3-4）

| タスク | 説明 | 担当 | 成果物 |
|---|---|---|---|
| ビジュアルデザイン | Design Tokens 適用・詳細なスタイリング | Designer | High-fi Prototype (Figma) |
| プロトタイプ制作 | Figma Prototyping / Interaction 設定 | Designer | Interactive Prototype |
| テスト環境構築 | ユーザーテスト用の環境セットアップ | Developer | Test Environment (Dev/Staging) |
| テストシナリオ作成 | ユーザーテストで検証するシナリオ | Designer / PM | Test Scenarios |

**参照**: `design-sprint-template.md` の「フェーズ 3-4」セクション

**チェックリスト**
- [ ] Low-fi wireframes が 5 ページ以上作成済み
- [ ] High-fi prototype に Design Tokens が 90% 以上適用済み
- [ ] Interactive Prototype のフロー テストが完了
- [ ] ユーザーテストシナリオ (3-5 個) が作成済み

---

### Step 4: 設計レビュー・フィードバック統合（Day 5）

**目標**: ユーザーテスト・ステークホルダーレビューから得た フィードバックを設計に統合

**活動内容**

| タスク | 説明 | 担当 | 成果物 |
|---|---|---|---|
| ユーザーテスト実施 | 3-5 人のユーザーと対面/リモートテスト | Designer / PM | Test Recording + Notes |
| フィードバック記録 | ユーザーの反応・コメント・課題の記録 | UX Researcher | Feedback Spreadsheet |
| ステークホルダーレビュー | PM / Tech Lead / 利害関係者から意見収集 | Designer | Review Comments |
| フィードバック分類 | Critical / High / Medium / Low に分類 | Designer / PM | Feedback Triage |
| 設計修正（1-2ラウンド） | フィードバックを設計に反映 | Designer | Revised Prototype |
| 最終確認 | ステークホルダー・チーム全体の最終確認 | 全員 | Approval / Sign-off |

**チェックリスト**
- [ ] ユーザーテスト 3 人以上実施済み
- [ ] フィードバック 10 件以上記録済み
- [ ] Critical フィードバック 100% 対応済み
- [ ] High フィードバック 80% 以上対応済み
- [ ] ステークホルダー Sign-off 取得済み

---

### Step 5: 実装仕様書・設計システム成果物（Day 5 終了後）

**目標**: エンジニア実装チームが開発を開始できる完全な仕様書・ガイドラインを提供

**活動内容**

| タスク | 説明 | 担当 | 成果物 |
|---|---|---|---|
| 詳細仕様書作成 | コンポーネント仕様・状態遷移・バリエーション | Designer | Component Spec Document |
| Figma Design Tokens エクスポート | 開発チーム向けの Design Tokens | Designer | design-tokens.json |
| マークアップガイド | HTML/CSS/React での実装ガイドライン | Designer / Engineer | Markup Guidelines |
| 実装ロードマップ作成 | 優先度別実装順序・見積もり | PM / Engineer | Implementation Roadmap |
| QA テストケース | 画面・インタラクション・アクセシビリティテスト | Designer / QA | QA Test Cases (Gherkin BDD) |
| デザイン資産の最終化 | コンポーネント・パターン・アイコンの完成 | Designer | Design Library (Published) |

**チェックリスト**
- [ ] コンポーネント仕様書が全コンポーネント網羅
- [ ] Design Tokens JSON が生成・エンジニアに共有済み
- [ ] 実装ロードマップが 2 週間分の見積もり付きで作成済み
- [ ] BDD テストケース (Gherkin) が 10 シナリオ以上作成済み
- [ ] Figma Design System が Published 状態で公開済み

---

## 4. タイムライン（5日間）

```
Monday (Day 1)     : ユーザー調査・ペルソナ定義
                     └─ 成果物: Persona Sheet, User Journey Map

Tuesday (Day 2)    : UX System 設計 + ロー忠度ワイヤーフレーム開始
                     └─ 成果物: Design Tokens, Component Library
                     └─ 並列開始: API/DB 設計 (Engineer)

Wednesday (Day 3)  : ハイ忠度プロトタイプ制作
                     └─ 成果物: High-fi Prototype (Interactive)
                     └─ 並列実行: バックエンド実装 (Engineer)

Thursday (Day 4)   : プロトタイプ完成 + ユーザーテスト準備
                     └─ 成果物: Test Scenarios, Test Environment Ready
                     └─ 並列実行: テスト環境構築 (Engineer)

Friday (Day 5)     : ユーザーテスト + 設計レビュー + 実装仕様書作成
                     └─ 成果物: Test Report, Revised Design, Implementation Spec
                     └─ 成果物: Design Tokens, QA Test Cases, Figma Publish

┌──────────────────────────────────────────────┐
│  実装フェーズ開始（チーム並行実装）          │
└──────────────────────────────────────────────┘
```

---

## 5. チェックリスト（全体）

### 設計フェーズ完了条件

- [ ] **ペルソナ定義**: 3 個以上 + Goal/Pain Points 明確
- [ ] **User Journey Map**: 全タッチポイント + 感情スコア明記
- [ ] **Design System**: Figma Component Library + Design Tokens 完成
- [ ] **プロトタイプ**: 全主要ページの High-fi Prototype 完成
- [ ] **ユーザーテスト**: 3 人以上のユーザーテスト実施 + 記録
- [ ] **実装仕様書**: コンポーネント仕様・状態遷移・バリエーション完全記載
- [ ] **QA テストケース**: Gherkin BDD で 10 シナリオ以上作成
- [ ] **Figma 公開**: Design System を Published 状態で全チームに共有

### 品質基準

| 項目 | 基準 |
|---|---|
| **デザイン一貫性** | 同じコンポーネントの外観・動作が 100% 統一 |
| **アクセシビリティ** | WCAG 2.1 AA に 100% 準拠 |
| **ユーザーテスト結果** | Critical フィードバック 100% 対応、High 80% 対応 |
| **実装準備度** | エンジニアが実装仕様書だけで開発開始可能 |
| **チーム認識** | ステークホルダー全員が設計に Sign-off |

---

## 6. 参考資料

### 関連ドキュメント

- **design-sprint-template.md**: 5日間スプリントの詳細タイムライン・役割分担
- **user-journey.md**: ユーザー調査・ジャーニーマップ・タッチポイント分析
- **ux-system.md**: デザインシステム・コンポーネント・アクセシビリティガイドライン

### ツール・リソース

- **Figma**: プロトタイプ制作・Design System 管理
- **THEBRANCH Dashboard**: ワークフロー管理・タスク追跡
- **task-manager-sqlite**: Product Design Sprint テンプレート（Workflow ID: 13）

---

## 7. 例：実施フロー（新機能「AIエージェント評価機能」の場合）

### Day 1: ユーザー調査

```
Morning:
  • ビジョン確認: 「AIエージェントの評価・フィードバックシステム」
  • ペルソナ定義: 
    - PM（機能を設計する立場）
    - Manager（チームのエージェントを評価する立場）
    - Developer（エージェント改善の参考にしたい）

Afternoon:
  • User Journey Map
    PM    : 評価ルール定義 → 実施 → 結果分析 → アクション
    Manager: 部下評価 → フィードバック提供 → 部下のレスポンス確認
    Developer: メトリクス確認 → 改善提案検討 → 反映
```

### Day 2-3: プロトタイプ制作

```
Low-fi Wireframes:
  1. 評価ダッシュボード（一覧・フィルタ）
  2. エージェント詳細（スコア・グラフ・フィードバック）
  3. フィードバック入力フォーム
  4. 評価ルール管理（Admin）

High-fi Prototype:
  • Design Tokens 適用
  • グラフ・チャート実装
  • インタラクティブフロー（ダッシュボード → 詳細 → フィードバック）
```

### Day 4-5: ユーザーテスト・実装仕様書

```
ユーザーテスト（3人）:
  • PM: 「このダッシュボードで評価ルール設定を簡単にできるか？」
  • Manager: 「フィードバック入力は直感的か？」
  • Developer: 「メトリクスの視認性は十分か？」

実装仕様書:
  • Dashboard コンポーネント仕様
  • Score Card コンポーネント仕様
  • Feedback Form バリエーション（テキスト・スター・スケール）
  • 状態遷移（Loading / Data / Empty State）
  • QA テストケース (Gherkin)
```

---

**最終更新**: 2026-04-26  
**作成者**: Tech Lead  
**ステータス**: Published
