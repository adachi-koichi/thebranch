# BDD業務フロー 実行フロー図

**対象システム**: AI Orchestrator × task-manager-sqlite  
**バージョン**: 1.0  
**作成日**: 2026-04-19

---

## 目次

1. [メインフロー図](#メインフロー図)
2. [エージェント委譲フロー](#エージェント委譲フロー)
3. [自動監視ループ](#自動監視ループ)
4. [ステータス遷移の詳細](#ステータス遷移の詳細)
5. [DAG依存関係の例](#dag依存関係の例)

---

## メインフロー図

### 高水準フロー：ワークフローインスタンス全体

```
Workflow Template (.feature ファイル定義)
        │
        │ [instantiate]
        ↓
Workflow Instance (workflow_id 発行)
status: pending → running → completed
        │
        ├─────────────────────────────────────────────────────────┐
        │                                                           │
        │ Phase 1: Setup (準備)                                    │
        │ status: waiting → running → completed                   │
        │ timeout: 30分                                             │
        │ role: orchestrator                                        │
        │                                                           │
        │   ├─ Task 1.1: リポジトリ初期化                         │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: []                                       │
        │   │   blocks: [1.2]                                       │
        │   │                                                       │
        │   ├─ Task 1.2: 環境設定                                  │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [1.1]                                    │
        │   │   blocks: [1.3]                                       │
        │   │                                                       │
        │   └─ Task 1.3: 依存パッケージ インストール              │
        │       status: pending → in_progress → completed          │
        │       blockedBy: [1.2]                                    │
        │       blocks: [2.1] ← フェーズ間依存                    │
        │                                                           │
        └─────────────────────────────────────────────────────────┘
                            ↓ [Phase 1 completed]
        ┌─────────────────────────────────────────────────────────┐
        │                                                           │
        │ Phase 2: Planning (計画)                                 │
        │ status: waiting → running → completed                   │
        │ timeout: 60分                                             │
        │ role: EM (Engineering Manager)                           │
        │                                                           │
        │   ├─ Task 2.1: 要件定義                                  │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [1.3] ← Phase 1 からの依存             │
        │   │   blocks: [2.2]                                       │
        │   │                                                       │
        │   ├─ Task 2.2: 設計ドキュメント作成                      │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [2.1]                                    │
        │   │   blocks: [2.3]                                       │
        │   │                                                       │
        │   └─ Task 2.3: 実装計画                                  │
        │       status: pending → in_progress → completed          │
        │       blockedBy: [2.2]                                    │
        │       blocks: [3.1, 3.2] ← Phase 3 へ                   │
        │                                                           │
        └─────────────────────────────────────────────────────────┘
                            ↓ [Phase 2 completed]
        ┌─────────────────────────────────────────────────────────┐
        │                                                           │
        │ Phase 3: Implementation (実装) [並行実行]               │
        │ status: waiting → running → completed                   │
        │ timeout: 240分                                            │
        │ role: Engineer × 複数                                    │
        │                                                           │
        │   ├─ Task 3.1: コンポーネント実装                        │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [2.3]                                    │
        │   │   blocks: [3.3, 3.4]                                  │
        │   │   assigned_to: Engineer #1                           │
        │   │                                                       │
        │   ├─ Task 3.2: API 実装                                  │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [2.3]                                    │
        │   │   blocks: [3.3, 3.4]                                  │
        │   │   assigned_to: Engineer #2                           │
        │   │                                                       │
        │   ├─ Task 3.3: 統合テスト準備                            │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [3.1, 3.2]  ← 並行タスク完了を待つ     │
        │   │   blocks: [4.1, 4.2]                                  │
        │   │                                                       │
        │   └─ Task 3.4: 単体テスト実装                            │
        │       status: pending → in_progress → completed          │
        │       blockedBy: [3.1, 3.2]                               │
        │       blocks: [4.3]                                       │
        │                                                           │
        └─────────────────────────────────────────────────────────┘
                            ↓ [Phase 3 completed]
        ┌─────────────────────────────────────────────────────────┐
        │                                                           │
        │ Phase 4: Verification (検証)                             │
        │ status: waiting → running → completed                   │
        │ timeout: 120分                                            │
        │ role: QA / Engineer                                      │
        │                                                           │
        │   ├─ Task 4.1: 統合テスト実行                            │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [3.3]                                    │
        │   │   blocks: [5.2]                                       │
        │   │   assigned_to: QA                                    │
        │   │                                                       │
        │   ├─ Task 4.2: セキュリティテスト                        │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [3.3]                                    │
        │   │   blocks: [5.1]                                       │
        │   │   assigned_to: QA                                    │
        │   │                                                       │
        │   └─ Task 4.3: パフォーマンステスト                      │
        │       status: pending → in_progress → completed          │
        │       blockedBy: [3.4]                                    │
        │       blocks: [5.1]                                       │
        │       assigned_to: Engineer #1                           │
        │                                                           │
        └─────────────────────────────────────────────────────────┘
                            ↓ [Phase 4 completed]
        ┌─────────────────────────────────────────────────────────┐
        │                                                           │
        │ Phase 5: Completion (完了)                               │
        │ status: waiting → running → completed                   │
        │ timeout: 30分                                             │
        │ role: orchestrator                                        │
        │                                                           │
        │   ├─ Task 5.1: ドキュメント最終化                        │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [4.2, 4.3]                               │
        │   │   blocks: [5.3]                                       │
        │   │                                                       │
        │   ├─ Task 5.2: コードレビュー                            │
        │   │   status: pending → in_progress → completed          │
        │   │   blockedBy: [4.1]                                    │
        │   │   blocks: [5.3]                                       │
        │   │                                                       │
        │   └─ Task 5.3: リリース準備                              │
        │       status: pending → in_progress → completed          │
        │       blockedBy: [5.1, 5.2]                               │
        │       blocks: [] ← ワークフロー完了                      │
        │                                                           │
        └─────────────────────────────────────────────────────────┘
                            ↓ [Phase 5 completed]
        
        Workflow Instance status: completed
        completed_at: timestamp
```

### 凡例

| 記号 | 意味 |
|---|---|
| `→` | タスク完了による次ステップへの遷移 |
| `│` | 実行フロー（上から下） |
| `blockedBy: [X]` | タスク X の完了待ち |
| `blocks: [X, Y]` | タスク X, Y をブロック中 |
| `[Phase N completed]` | フェーズ完了時の自動トリガー |

---

## エージェント委譲フロー

### 全体構図：orchestrator → EM → Engineer

```
ai-orchestrator@main セッション
    ├─ window:0 = orchestrator (pane:0.0)
    │   └─ ccc-orchestrator
    │
    └─ window:N = exp-stock team
        ├─ pane:N.0 = EM (team lead)
        │   └─ ccc-engineering-manager
        │
        ├─ pane:N.1 = Engineer #1
        │   └─ ccc-engineer
        │
        └─ pane:N.2 = Engineer #2
            └─ ccc-engineer
```

### 詳細フロー図

```
Step 1: orchestrator が Workflow Instance を開始
┌────────────────────────────────────────────────────┐
│ ai-orchestrator@main:0.0 (orchestrator)            │
│                                                    │
│ /loop 3m /orchestrate                             │
│ ├─ detect_idle_panes.py                           │
│ ├─ check_task_completion.py                       │
│ ├─ advance_wf_instance.py ← [新規] Phase進行管理  │
│ ├─ check_long_pending_tasks.py                    │
│ ├─ check_stale_inprogress_tasks.py                │
│ └─ save_cycle_stats.py                            │
│                                                    │
│ > python3 task.py wf instance start \             │
│     "exp-stock" --params '{"symbol":"AAPL"}'      │
│ [workflow_id: exp-stock-001]                      │
│                                                    │
│ Phase 1: Setup [orchestrator が実行]              │
│ └─ Task 1.1, 1.2, 1.3 [completed]                 │
└────────────────────────────────────────────────────┘
                    ↓
        [Phase 1 completed を検出]
                    ↓
Step 2: orchestrator が EM にタスクを委譲
┌────────────────────────────────────────────────────┐
│ ai-orchestrator@main:0.0 (orchestrator)            │
│                                                    │
│ # 新規チームウィンドウを作成                      │
│ $ tmux new-window -t "ai-orchestrator@main:1" \  │
│     -n "exp-stock-team" -c "$github/..."          │
│                                                    │
│ # EM を起動                                        │
│ $ tmux send-keys -t "ai-orchestrator@main:1:0" \  │
│     "ccc-engineering-manager" Enter                │
│ $ sleep 3                                          │
│                                                    │
│ # Phase 2 タスクを委譲                            │
│ $ tmux send-keys -t "ai-orchestrator@main:1:0" \  │
│     "タスク #2058 を担当してください。\            │
│      Phase 2: Planning - 要件定義・設計" Enter     │
└────────────────────────────────────────────────────┘
                    ↓
Step 3: EM が実装を分析し、Engineer に割り当て
┌────────────────────────────────────────────────────┐
│ ai-orchestrator@main:1.0 (EM)                      │
│                                                    │
│ > task.py list --status pending \                 │
│   --workflow exp-stock-001                         │
│ [Task 2.1, 2.2, 2.3 を表示]                       │
│                                                    │
│ # タスク2.1を確認し、優先度を判定                │
│ > task.py task 2058                               │
│                                                    │
│ # Phase 3 実装タスク（3.1, 3.2）が                │
│ # Task 2.3（実装計画）の完了待ちであることを確認 │
│                                                    │
│ # Engineer ペインを追加                            │
│ $ tmux split-window -t "ai-orchestrator@main:1" \  │
│     -h                                             │
│ $ ENGINEER_PERSONA="Pythonエンジニア。..." \       │
│   tmux send-keys -t "ai-orchestrator@main:1:1" \  │
│     "ccc-engineer" Enter                           │
│ $ sleep 3                                          │
│                                                    │
│ # 最初の実装タスク（Task 3.1）を割り当て          │
│ $ tmux send-keys -t "ai-orchestrator@main:1:1" \  │
│     "タスク #3058 を実装してください。\            │
│      Phase 3: コンポーネント実装" Enter            │
│                                                    │
│ # 2人目の Engineer を追加                          │
│ $ tmux split-window -t "ai-orchestrator@main:1" \  │
│     -h                                             │
│ $ ENGINEER_PERSONA="TypeScriptエンジニア。..." \   │
│   tmux send-keys -t "ai-orchestrator@main:1:2" \  │
│     "ccc-engineer" Enter                           │
│ $ sleep 3                                          │
│                                                    │
│ # Task 3.2 を割り当て（並行実行）                 │
│ $ tmux send-keys -t "ai-orchestrator@main:1:2" \  │
│     "タスク #3059 を実装してください。\            │
│      Phase 3: API 実装" Enter                      │
└────────────────────────────────────────────────────┘
                    ↓
Step 4: Engineer が並行実装
┌────────────────────────────────────────────────────┐
│ ai-orchestrator@main:1.1 (Engineer #1)            │
│ [Task 3.1: コンポーネント実装]                     │
│ Status: in_progress → completed                  │
│ $ task.py update 3058 --status in_progress        │
│ $ # 実装作業 ...                                  │
│ $ task.py done 3058                               │
│                                                    │
│ ai-orchestrator@main:1.2 (Engineer #2)            │
│ [Task 3.2: API 実装]                              │
│ Status: in_progress → completed                  │
│ $ task.py update 3059 --status in_progress        │
│ $ # 実装作業 ...                                  │
│ $ task.py done 3059                               │
└────────────────────────────────────────────────────┘
                    ↓
        [Task 3.1, 3.2 completed を検出]
            [Task 3.3, 3.4 の blockedBy を解除]
                    ↓
Step 5: EM が QA にテストを指示
┌────────────────────────────────────────────────────┐
│ ai-orchestrator@main:1.0 (EM)                      │
│                                                    │
│ # orchestrator の監視ループが Task 3.3, 3.4      │
│ # の blockedBy を自動解除（advance_wf_instance.py）
│                                                    │
│ # EM が QA エージェント起動を判定                 │
│ $ python3 ~/.claude/skills/task-manager-sqlite \  │
│   /scripts/task.py wf phase advance \             │
│   1 4  # Phase 4 (Verification) へ進行            │
│                                                    │
│ # QA ペインを追加（または新規ウィンドウ）         │
│ $ tmux split-window -t "ai-orchestrator@main:1" \ │
│     -h                                             │
│ $ tmux send-keys -t "ai-orchestrator@main:1:3" \ │
│     "ccc-qa" Enter                                 │
│ $ sleep 3                                          │
│                                                    │
│ # テスト指示                                       │
│ $ tmux send-keys -t "ai-orchestrator@main:1:3" \ │
│     "タスク #4058 をテストしてください。\         │
│      Phase 4: 統合テスト実行" Enter               │
└────────────────────────────────────────────────────┘
                    ↓
Step 6: QA がテスト実行
┌────────────────────────────────────────────────────┐
│ ai-orchestrator@main:1.3 (QA)                      │
│ [Task 4.1: 統合テスト実行]                        │
│ Status: in_progress → completed                  │
│ $ task.py update 4058 --status in_progress        │
│ $ # テスト実行 ...                                │
│ $ task.py done 4058                               │
│                                                    │
│ # テスト結果をレポート                             │
│ # 結果: PASS/FAIL を記録                          │
└────────────────────────────────────────────────────┘
                    ↓
Step 7: orchestrator が Phase 5 を開始
┌────────────────────────────────────────────────────┐
│ ai-orchestrator@main:0.0 (orchestrator)            │
│                                                    │
│ # 自動監視ループが Phase 4 完了を検出            │
│ [check_task_completion.py で全テスト Task完了確認]
│                                                    │
│ # Phase 5 へ自動遷移（advance_wf_instance.py）   │
│ Task 5.1, 5.2, 5.3 の blockedBy を解除            │
│                                                    │
│ # orchestrator が Phase 5 (Completion) を処理     │
│ > python3 task.py wf phase advance \              │
│     1 5  # Phase 5 へ                             │
│                                                    │
│ # ドキュメント最終化・コードレビュー・リリース    │
│ $ task.py update 5058 --status in_progress        │
│ $ # 完了作業 ...                                  │
│ $ task.py done 5058                               │
└────────────────────────────────────────────────────┘
                    ↓
        [全 Task completed]
        [Workflow Instance status: completed]
```

---

## 自動監視ループ

### orchestrator の監視周期

```
/loop 3m /orchestrate
│
├─ [周期 1: 0:00～0:03]
│   ├─ Step 1: detect_idle_panes.py
│   │   └─ tmux capture-pane で全ペイン内容取得
│   │      "?" プロンプト検出 → 自動回答
│   │
│   ├─ Step 2: check_task_completion.py
│   │   └─ SQLite で task status を追跡
│   │      in_progress → completed 変化を検出
│   │
│   ├─ Step 3: advance_wf_instance.py ← [新規]
│   │   ├─ Phase N 内の全 Task status を確認
│   │   ├─ 全て completed なら Phase N → completed
│   │   ├─ Phase N+1 の Task.blockedBy を解除
│   │   └─ トリガー: task-manager-sqlite へ通知
│   │
│   ├─ Step 4: check_long_pending_tasks.py
│   │   └─ pending > 60分 → alerts.log に記録
│   │
│   ├─ Step 5: check_stale_inprogress_tasks.py
│   │   └─ in_progress > 120分 → Discord alert
│   │
│   └─ Step 6: save_cycle_stats.py
│       └─ 統計を /tmp/orchestrate_cycle_stats.jsonl に記録
│
├─ [周期 2: 3:00～3:03]
│   ├─ [EM が完了した Task を報告]
│   │ $ task.py done 2058
│   │
│   ├─ [orchestrator が detect_idle_panes で確認]
│   │ tmux capture-pane → "Task completed. Next step?"
│   │
│   ├─ [advance_wf_instance.py で自動判定]
│   │ Phase 2 の Task 2.1, 2.2, 2.3 status 確認
│   │ → 全て completed ⇒ Phase 2 status = completed
│   │ → Phase 3 の Task.blockedBy を自動解除
│   │
│   └─ [EM が次フェーズを認識]
│      Engineer ペインに "Phase 3 が開始可能です" 通知
│
└─ [周期 N: ...]
```

### データフロー図（advance_wf_instance.py）

```
SQLite Database
┌───────────────────────────────────────────────┐
│ workflow_instances (workflow_id=1)            │
│ └─ status: running                            │
│    current_phase_id: 2 (Planning)             │
│                                               │
│ workflow_phases (phase_id=2)                  │
│ └─ status: running                            │
│                                               │
│ dev_tasks (workflow_instance_id=1)            │
│ ├─ Task 2.1: status = completed              │
│ ├─ Task 2.2: status = completed              │
│ └─ Task 2.3: status = completed              │
│ ├─ Task 3.1: status = pending                │
│ │            blockedBy = [2.3]               │
│ ├─ Task 3.2: status = pending                │
│ │            blockedBy = [2.3]               │
│ └─ ...                                        │
└───────────────────────────────────────────────┘
        ↑
        │ [check_task_completion.py]
        │ 「Task 2.1, 2.2, 2.3 が全て completed か？」
        │ YES ⇒ advance_wf_instance.py を実行
        │
┌───────────────────────────────────────────────┐
│ advance_wf_instance.py                        │
│                                               │
│ 1. workflow_phases で phase_id=2 を completed│
│    UPDATE workflow_phases SET                │
│      status = 'completed',                   │
│      completed_at = CURRENT_TIMESTAMP        │
│    WHERE id = <phase_2_id>                   │
│                                               │
│ 2. Phase 3 初期化                            │
│    UPDATE workflow_phases SET                │
│      status = 'running'                      │
│    WHERE id = <phase_3_id>                   │
│                                               │
│ 3. Task 3.1, 3.2 の blockedBy を削除         │
│    DELETE FROM task_dependencies             │
│    WHERE depends_on_id = 2.3                 │
│    AND task_id IN (3.1, 3.2)                 │
│                                               │
│ 4. workflow_instances を更新                │
│    UPDATE workflow_instances SET             │
│      current_phase_id = 3,                   │
│      updated_at = CURRENT_TIMESTAMP          │
│    WHERE id = 1                              │
└───────────────────────────────────────────────┘
        ↓
        │ [トリガー: EM/Engineer に通知]
        │ tmux send-keys -t "exp-stock_orchestrator_wf001_task-1@main:managers.0" \
        │   "Phase 3 が開始可能です。Task 3.1, 3.2 の\
        │    blockedBy が解除されました" Enter
        │
    [次の監視周期へ]
```

---

## ステータス遷移の詳細

### Workflow Instance ステータス遷移

```
┌──────────────────────────────────────────────────────────────────┐
│ pending                                                          │
│ (初期状態)                                                      │
│ status = 'pending'                                              │
│ current_phase_id = NULL                                         │
│                                                                  │
│ [trigger: instantiate]                                          │
│ orchestrator が wf instance start を実行                        │
└──────────────────────────────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────┐
│ running                                                          │
│ Phase 1 実行中                                                  │
│ status = 'running'                                              │
│ current_phase_id = 1                                            │
│ started_at = CURRENT_TIMESTAMP                                  │
│                                                                  │
│ [phase progression loop]                                        │
│ Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5               │
│                                                                  │
│ [エラー: timeout or 失敗]                                       │
│ status → 'failed'                                               │
│ error_message = 「timeout reached」                            │
└──────────────────────────────────────────────────────────────────┘
                    ╱                            ╲
                   ╱                              ╲
                  ╱                                ╲
        [成功パス]                          [失敗パス]
        Phase 5 完了                        再実行・キャンセル
                   ╲                                ╱
                    ╲                              ╱
                     ╲                            ╱
┌──────────────────────────────────────────────────────────────────┐
│ completed ← OR → failed                                          │
│ status = 'completed'      status = 'failed'                    │
│ completed_at = timestamp  error_message = reason               │
│                                                                  │
│ [Workflow Instance の振り返り]                                   │
│ - 実行時間: started_at → completed_at                           │
│ - 完了タスク数                                                   │
│ - エラーの有無                                                   │
│ - Phase 進行状況                                                │
└──────────────────────────────────────────────────────────────────┘
```

### Phase ステータス遷移

```
┌────────────────────────────────────┐
│ waiting (初期状態)                 │
│                                    │
│ [前フェーズ完了 or フェーズ1]     │
│ IF (前フェーズ.status = completed) │
│ THEN Phase.status = running        │
│ ELSE Phase.status = blocked        │
└────────────────────────────────────┘
         ↓
    ┌─────────────────────────┐
    │ blocked                 │
    │ (前フェーズ未完了)      │
    │                         │
    │ [待機]                  │
    │ 前フェーズ完了を待つ    │
    └─────────────────────────┘
         ↑                         ↓
         └─────────────────────────┘
                (復帰)
         
┌────────────────────────────────────┐
│ running                            │
│ started_at = timestamp             │
│                                    │
│ [全 Task completed か？]          │
│ ├─ YES → Phase.status = completed │
│ ├─ NO  → timeout_at に達したか？ │
│ │        ├─ YES → Phase.status = failed
│ │        └─ NO  → 待機継続        │
│ └─ IN_PROGRESS → 待機継続        │
└────────────────────────────────────┘
         ↓
    ┌─────────────────────────┐
    │ completed               │
    │ completed_at = timestamp│
    │                         │
    │ [トリガー]              │
    │ Phase N+1 を running へ │
    └─────────────────────────┘
         
    OR
    
    ┌─────────────────────────┐
    │ failed                  │
    │ error_message = reason  │
    │                         │
    │ [Workflow Instance]     │
    │ status = failed        │
    └─────────────────────────┘
```

### Task ステータス遷移

```
┌─────────────────────────────────────────────────────┐
│ pending (初期状態)                                  │
│ blockedBy = [task IDs...]                          │
│ blocks = [task IDs...]                             │
│                                                     │
│ [blockedBy が全て completed か？]                  │
│ ├─ YES → Task を Engineer に割り当て可能          │
│ └─ NO  → Task.status = blocked (待機中)          │
└─────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────┐
│ in_progress (Engineer が実装中)                     │
│ assigned_to = Engineer ID                           │
│ started_at = timestamp                              │
│                                                     │
│ [実装完了]                                          │
│ Engineer が task.py done <ID> を実行               │
│ → Task.status = completed                         │
│   OR                                                │
│ [テスト失敗・再実装が必要]                          │
│ → Task.status = needs_fix                         │
│   → Task.blockedBy.clear()                        │
│   → Task.blocks.clear()                           │
│   → Task.status = pending (再実装)               │
└─────────────────────────────────────────────────────┘
         ├─ (completed)
         │   ↓
         │ ┌──────────────────────────────┐
         │ │ completed                    │
         │ │ completed_at = timestamp     │
         │ │                              │
         │ │ [トリガー]                   │
         │ │ blocks[] 内の Task の        │
         │ │ blockedBy を自動解除         │
         │ └──────────────────────────────┘
         │
         └─ (needs_fix)
             ↓
         ┌──────────────────────────────┐
         │ pending (再実装)              │
         │ blockedBy = [] (クリア)       │
         │ assigned_to = (同じ Engineer) │
         │ attempted = attempted + 1     │
         │                              │
         │ [再実装ループ]                │
         └──────────────────────────────┘
```

---

## DAG依存関係の例

### 例1: Phase 2 内の直列依存

```
Task 2.1 (要件定義)
  │
  ├─ blockedBy = []
  ├─ blocks = [2.2]
  │
  ↓ [Task 2.1 completed]
  │
Task 2.2 (設計ドキュメント)
  │
  ├─ blockedBy = [2.1]
  ├─ blocks = [2.3]
  │
  ↓ [Task 2.2 completed]
  │
Task 2.3 (実装計画)
  │
  ├─ blockedBy = [2.2]
  ├─ blocks = [3.1, 3.2]
  │
  ↓ [Task 2.3 completed]
  │
Phase 3 へ遷移可能
```

### 例2: Phase 3 内の並行依存

```
Task 2.3 (実装計画) [Phase 2]
  │
  └─ blocks = [3.1, 3.2]
     
     ├─ Task 3.1 (コンポーネント実装)  ←─┐
     │  ├─ blockedBy = [2.3]            │
     │  └─ blocks = [3.3, 3.4]          │ [並行実行]
     │     assigned_to: Engineer #1     │
     │                                   │
     └─ Task 3.2 (API 実装)  ←──────────┤
        ├─ blockedBy = [2.3]            │
        └─ blocks = [3.3, 3.4]          │
           assigned_to: Engineer #2     │

[Task 3.1 completed] AND [Task 3.2 completed]
     ↓
Task 3.3 (統合テスト準備)
├─ blockedBy = [3.1, 3.2]
└─ blocks = [4.1, 4.2]

Task 3.4 (単体テスト実装)
├─ blockedBy = [3.1, 3.2]
└─ blocks = [4.3]
```

### 例3: Phase 間の依存

```
Phase 1: Setup (完了)
├─ Task 1.1: リポジトリ初期化
├─ Task 1.2: 環境設定
└─ Task 1.3: 依存パッケージ インストール
   └─ blocks = [2.1] ← Phase 2 へ

[Phase 1 completed]
     ↓
Phase 2: Planning (開始)
├─ Task 2.1: 要件定義
│  ├─ blockedBy = [1.3] ← Phase 1 からの依存
│  └─ ...
├─ Task 2.2: 設計ドキュメント
└─ Task 2.3: 実装計画
   └─ blocks = [3.1, 3.2] ← Phase 3 へ

[Phase 2 completed]
     ↓
Phase 3: Implementation (開始)
├─ Task 3.1: コンポーネント実装
│  └─ blockedBy = [2.3]
├─ Task 3.2: API 実装
│  └─ blockedBy = [2.3]
└─ ...
```

---

## 参考リンク

- [BDD-Architecture.md](BDD-Architecture.md) - 5層階層設計
- [DATA-MODEL.md](DATA-MODEL.md) - SQLite スキーマ定義
- [THEBRANCH/CLAUDE.md](../CLAUDE.md) - tmux セッション管理ルール
