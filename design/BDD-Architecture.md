# BDD業務フロー アーキテクチャ設計書

**対象システム**: AI Orchestrator  
**バージョン**: 1.0  
**作成日**: 2026-04-18  

---

## 1. 概要

AI Orchestrator は、複数の Claude Code インスタンスを監視・指示するマスターコントローラー。
BDD（振る舞い駆動開発）の原則に従い、業務フロー全体を**テンプレート → インスタンス → フェーズ → タスク → 専門家アサイン** という5層階層で設計する。

---

## 2. BDD業務フロー全体図

```
┌─────────────────────────────────────────────────────────────────────┐
│ 業務フロー定義 (Workflow Template)                                  │
│ - Feature: 「業務フロー実行」                                        │
│ - Scenario テンプレート: 「テンプレート作成」「タスク実行」「監視」  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ (インスタンス化)
┌─────────────────────────────────────────────────────────────────────┐
│ ワークフローインスタンス (Workflow Instance)                         │
│ - 開発プロジェクト (exp-stock)、ドキュメント作成等                   │
│ - task-manager-sqlite でID管理                                      │
│ - 親テンプレートへの参照ポインタ                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ (フェーズ分割)
┌─────────────────────────────────────────────────────────────────────┐
│ 実行フェーズ (Execution Phase)                                      │
│ Phase 1: 準備 (Setup) - タスク分析、専門家決定                      │
│ Phase 2: 計画 (Planning) - ロードマップ、デリバリー構成             │
│ Phase 3: 実装 (Implementation) - コード作成、統合                   │
│ Phase 4: 検証 (Verification) - テスト、品質チェック                │
│ Phase 5: 完了 (Completion) - デプロイ、ドキュメント                │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ (タスク分割)
┌─────────────────────────────────────────────────────────────────────┐
│ タスク (Task)                                                       │
│ - 単一責務（例: 設計書作成、テスト実装、PR レビュー）               │
│ - 依存関係グラフ (DAG)                                              │
│ - 優先度・期限・所有者情報                                          │
│ - ステータス: pending → in_progress → completed                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ (アサイン)
┌─────────────────────────────────────────────────────────────────────┐
│ 専門家アサイン (Agent Assignment)                                   │
│ - orchestrator (監視・指示)                                         │
│ - Engineering Manager (EM) (タスク分解・優先化)                    │
│ - Engineer (実装・テスト)                                           │
│ - 各エージェントの人格/権限/スキル (3つの柱)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 層別設計

### 3.1 層1: テンプレート (Workflow Template)

**定義**: BDD Feature として定義された再利用可能な業務フロー。

| 項目 | 内容 |
|---|---|
| **名前** | Workflow Template |
| **格納先** | `.feature` ファイル、`ref/` ドキュメント |
| **キー属性** | Feature 名、Scenario テンプレート、ステップ定義（Gherkin） |
| **責任** | ビジネス要件の可読化、組織的な標準化 |
| **例** | `development-workflow.feature` |

**例**:
```gherkin
Feature: 開発業務フロー
  Scenario: テンプレート作成
    Given テンプレート "開発フロー" が定義されている
    When orchestrator がテンプレートをインスタンス化する
    Then タスク分割が自動実行される
```

---

### 3.2 層2: ワークフローインスタンス (Workflow Instance)

**定義**: 具体的なプロジェクト・タスクを指す、テンプレートの具体化。

| 項目 | 内容 |
|---|---|
| **名前** | Workflow Instance |
| **識別子** | `workflow_id` (task-manager-sqlite) |
| **格納先** | SQLite DB (task-manager-sqlite) |
| **キー属性** | template_id, project, start_date, deadline, owner |
| **責任** | プロジェクト全体のライフサイクル管理 |
| **例** | `workflow_id=1` (exp-stock プロジェクト) |

**データモデル**:
```json
{
  "workflow_id": 1,
  "template_id": "dev-workflow",
  "project": "exp-stock",
  "created_at": "2026-04-18T10:00:00Z",
  "deadline": "2026-04-20T18:00:00Z",
  "status": "in_progress",
  "phases": [1, 2, 3, 4, 5],
  "owner": "orchestrator"
}
```

---

### 3.3 層3: 実行フェーズ (Execution Phase)

**定義**: ワークフローインスタンスの内部構造。5つのフェーズに分割。

| フェーズ | 説明 | 実行者 | 成果物 |
|---|---|---|---|
| **Phase 1: Setup** | 要件分析、専門家決定、セッション準備 | orchestrator | 要件表、セッション構成 |
| **Phase 2: Planning** | スケジュール作成、アーキテクチャ決定 | EM | 設計書、ロードマップ |
| **Phase 3: Implementation** | コード作成、スキル実装 | Engineer | ソースコード、機能 |
| **Phase 4: Verification** | テスト実行、品質チェック | QA / Engineer | テスト報告書、メトリクス |
| **Phase 5: Completion** | デプロイ、ドキュメント、振り返り | orchestrator | リリース文書 |

**フェーズ遷移**:
```
Setup → Planning → Implementation → Verification → Completion
  ↑                                                      ↓
  └──────────────── (失敗時の再実行) ──────────────────┘
```

---

### 3.4 層4: タスク (Task)

**定義**: 単一責務を持つ実行単位。DAG 形式での依存関係。

| 項目 | 内容 |
|---|---|
| **識別子** | `task_id` (task-manager-sqlite) |
| **属性** | title, description, phase, priority, deadline, owner, status |
| **依存関係** | blockedBy[], blocks[] (DAG) |
| **例** | `task_id=2058` (BDD設計書作成) |

**ステータス遷移**:
```
pending → in_progress → completed (or deleted)
```

**例**:
```json
{
  "task_id": 2058,
  "title": "BDD業務フロー高水準設計",
  "phase": 1,
  "workflow_id": 1,
  "blockedBy": [],
  "blocks": [2059, 2060],
  "owner": "engineer",
  "status": "in_progress",
  "deadline": "2026-04-18T14:00:00Z"
}
```

---

### 3.5 層5: 専門家アサイン (Agent Assignment)

**定義**: タスクを実行する Claude エージェント。委譲チェーンに基づく階層構造。

#### 3.5.1 エージェント階層

```
┌──────────────────────────────────────┐
│ orchestrator                         │
│ 役割: 全体監視・指示・品質保証      │
│ セッション: ai-orchestrator@main     │
│ tmux: window 0, pane 0 (固定)        │
└──────────────┬───────────────────────┘
               │ (タスク委譲)
       ┌───────▼──────────┐
       │ Engineering      │
       │ Manager (EM)     │
       │ 役割: 分解・最適化│
       │ セッション: {svc}_orchestrator_wf{N}_{team}@main:managers.X │
       └───────┬──────────┘
               │ (タスク分配)
    ┌──────────┴──────────┐
    │                     │
┌───▼──────┐      ┌──────▼───┐
│ Engineer │      │ QA       │
│ 役割: 実装│      │ 役割: 検証│
│ {svc}_orchestrator_wf{N}_{team}@main:members.X │
└──────────┘      └──────────┘
```

#### 3.5.2 エージェント定義（3つの柱）

| エージェント | 人格 | 権限 | 行動 |
|---|---|---|---|
| **orchestrator** | 監視者、判断者 | Bash, Glob, Grep, Task管理 | /loop 3m, health-monitor |
| **EM** | 分解者、最適化者 | Bash, Read, Task更新 | task-manager-sqlite スキル |
| **Engineer** | 実装者 | Bash, Edit, Write | bdd スキル、commit |
| **QA** | 検証者 | Bash, Monitor | テスト実行、レポート |

---

## 4. tmux セッション管理

### 4.1 セッション命名規則

| ロール | パターン | 例 |
|---|---|---|
| orchestrator | `ai-orchestrator@main` | `ai-orchestrator@main` (固定) |
| チームセッション | `{service}_orchestrator_wf{N}_{team}@main` | `exp-stock_orchestrator_wf2058_task-2058@main` |
| EM | チームセッション `:managers.X` ペイン | `exp-stock_orchestrator_wf2058_task-2058@main:managers.0` |
| Engineer | チームセッション `:members.X` ペイン | `exp-stock_orchestrator_wf2058_task-2058@main:members.0` |

### 4.2 ペイン操作フロー

```
orchestrator (ai-orchestrator@main:0.0)
  │
  ├─→ start_pane.py --app exp-stock --workflow-id 2058 --team task-2058 --role em
  │   (チームセッション: exp-stock_orchestrator_wf2058_task-2058@main 自動作成)
  │
  └─→ --message "タスク #2058 を担当してください"
      (EM にタスク指示)

EM (exp-stock_orchestrator_wf2058_task-2058@main:managers.0)
  │
  ├─→ start_pane.py --app exp-stock --workflow-id 2058 --team task-2058 --role engineer
  │   (members window に Engineer pane 追加)
  │
  └─→ --message "タスク #2058 を実装してください"
      (Engineer にタスク指示)

Engineer (exp-stock_orchestrator_wf2058_task-2058@main:members.0)
  │
  └─→ コード実装 → TaskUpdate → commit
      (実装完了)
```

---

## 5. task-manager-sqlite 統合

### 5.1 タスク管理フロー

```bash
# 1. pending タスク確認
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py list --status pending

# 2. タスク詳細取得
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py task <task_id>

# 3. ステータス更新
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py update <task_id> --status in_progress

# 4. 完了報告
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py done <task_id>
```

### 5.2 DAG 依存関係

```
task_2055 (準備)
  └─→ task_2056 (計画)
        └─→ task_2057 (設計1)
        └─→ task_2058 (設計2) ← 当タスク
              └─→ task_2059 (実装)
                    └─→ task_2060 (テスト)
```

---

## 6. 監視・制御メカニズム

### 6.1 orchestrator の監視ループ

```bash
/loop 3m /orchestrate
```

**各サイクル (3分ごと)**:
1. `tmux ls` で全セッション列挙
2. `tmux capture-pane` でペイン内容取得
3. "?" or プロンプト待機 の検出
4. CLAUDE.md ルール に従い自動回答
5. 必要に応じてユーザーにエスカレーション

### 6.2 品質保証チェックリスト

- [ ] 全タスク完了していない → orchestrator が原因調査
- [ ] セッション ハング (10分以上出力がない) → 再起動提案
- [ ] エラーメッセージ表示 → ユーザーにエスカレーション
- [ ] 期限切れタスク → 優先度引き上げ

---

## 7. データモデル全体図

```
Workflow (ワークフロー管理テーブル)
├── workflow_id (PK)
├── template_id (FK → Workflow Template)
├── project
├── status
└── phases[] (FK → Phase)

Phase (フェーズ管理)
├── phase_id (PK)
├── workflow_id (FK)
├── phase_name (Setup/Planning/Impl/Verify/Complete)
├── start_date
└── tasks[] (FK → Task)

Task (タスク管理)
├── task_id (PK)
├── phase_id (FK)
├── title
├── status (pending/in_progress/completed)
├── blockedBy[] (FK → Task)
├── blocks[] (FK → Task)
├── owner (orchestrator/EM/Engineer/QA)
└── deadline

Agent (エージェント管理)
├── agent_id (PK)
├── agent_type (orchestrator/EM/Engineer/QA)
├── session_name
├── persona
├── tools[] (権限)
└── current_task (FK → Task)
```

---

## 8. 成功基準

| 項目 | 基準 |
|---|---|
| **テンプレート再利用性** | 同じフロー構造で複数プロジェクトに適用可能 |
| **タスク可見性** | task-manager-sqlite 上のすべてのタスクが追跡可能 |
| **エージェント独立性** | ロール間の権限が明確に分離 |
| **監視自動化** | `/loop` のみで 90% 以上の決定が自動実行 |
| **エスカレーション** | ユーザー判断が必要なケース < 5% |

---

## 9. 拡張ポイント

- 新しいフェーズ追加時は Workflow Template のみ変更（互換性維持）
- エージェント追加時は Agent Hierarchy に新行追加
- データモデル拡張時は SQLite スキーマ マイグレーション実施
