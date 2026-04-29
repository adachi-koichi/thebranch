# BDD業務フロー テスト計画書

**対象プロジェクト**: AI Orchestrator  
**テスト範囲**: ワークフロー管理・フェーズ遷移・タスク実行・エージェント監視  
**テスト期間**: 2026-04-18 ～ 2026-04-20  
**テストレベル**: Unit + Integration + E2E  

---

## 1. テスト目的

ワークフロー管理システム全体が以下の要件を満たすことを検証する：

1. **テンプレート再利用性**: 同じ Feature 定義から複数プロジェクトのワークフローが作成可能
2. **フェーズ遷移の正確性**: タスク DAG 依存関係に従い、フェーズが段階的に遷移
3. **タスク追跡可能性**: task-manager-sqlite での全タスク状態変化が記録・追跡可能
4. **エージェント委譲の自動化**: orchestrator → EM → Engineer のフローが自動実行可能
5. **監視・制御の有効性**: `/loop 3m /orchestrate` で 90% 以上の判断が自動実行

---

## 2. テスト体系

```
┌────────────────────────────────────────┐
│  テスト全体の構成                      │
├────────────────────────────────────────┤
│  Level 1: Unit Tests                   │
│  - 個別関数・モジュール                │
│  - task-manager-sqlite の CRUD操作    │
│  - tmux コマンド実行                   │
├────────────────────────────────────────┤
│  Level 2: Integration Tests            │
│  - テンプレート→インスタンス化        │
│  - フェーズ→タスク生成                │
│  - 依存関係 DAG 実行                  │
├────────────────────────────────────────┤
│  Level 3: E2E Tests                    │
│  - orchestrator→EM→Engineer フロー    │
│  - 監視ループ自動化検証               │
│  - 全シナリオ実行                      │
└────────────────────────────────────────┘
```

---

## 3. テストケース一覧

### 3.1 Level 1: Unit Tests

#### TC-U1: task-manager-sqlite 基本操作

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-U1-1 | タスク作成 | `task.py add --title "test" --phase 1` | task_id が返却される | P0 |
| TC-U1-2 | タスク更新 | `task.py update <id> --status in_progress` | DB に status が反映される | P0 |
| TC-U1-3 | タスク完了 | `task.py done <id>` | ステータス=completed に変更 | P0 |
| TC-U1-4 | タスク依存設定 | `task.py update <id> --add-blocks [<id2>]` | blocks リスト が更新される | P1 |
| TC-U1-5 | タスク一覧取得 | `task.py list --status pending` | pending タスク全件取得 | P0 |

#### TC-U2: tmux セッション管理

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-U2-1 | セッション作成 | `start_pane.py --app THEBRANCH --workflow-id 1 --team test-1 --role engineer --dir "$PWD"` | v3命名規則でセッション作成される | P0 |
| TC-U2-2 | ペイン内容取得 | `tmux capture-pane -t "test:0.0" -p` | 出力内容取得可能 | P0 |
| TC-U2-3 | キー送信 | `tmux send-keys -t "test:0.0" "echo hello" Enter` | コマンド実行される | P0 |
| TC-U2-4 | セッション削除 | `tmux kill-session -t "test"` | セッション削除される | P1 |

#### TC-U3: Gherkin パース

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-U3-1 | Feature 読込 | `.feature` ファイルを読込 | Feature が解析される | P1 |
| TC-U3-2 | Scenario 抽出 | Scenario タイトル抽出 | 全 Scenario が取得可能 | P1 |
| TC-U3-3 | ステップ定義 | Given/When/Then の解析 | 各ステップが分類される | P1 |

---

### 3.2 Level 2: Integration Tests

#### TC-I1: テンプレート → インスタンス化

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-I1-1 | テンプレートロード | CLAUDE.md の workflow テンプレートロード | template が定義される | P0 |
| TC-I1-2 | インスタンス作成 | `template.instantiate(project="exp-stock")` | workflow_id が発行される | P0 |
| TC-I1-3 | フェーズ自動生成 | インスタンス化後フェーズ確認 | 5つの Phase が生成される | P0 |
| TC-I1-4 | 初期タスク生成 | Phase 1 のタスク確認 | Setup フェーズのタスク生成 | P0 |

#### TC-I2: フェーズ → タスク DAG

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-I2-1 | タスク依存関係設定 | task_2057 → task_2058 の依存設定 | blockedBy=[2057] が保存される | P0 |
| TC-I2-2 | DAG トポロジー検証 | 循環依存チェック | 循環参照なしで DAG 構成 | P1 |
| TC-I2-3 | ブロック状態確認 | task_2058 は task_2057 完了まで blocked | task_2058 が pending のまま | P0 |
| TC-I2-4 | アンブロック検出 | task_2057 完了→task_2058 unblock | task_2058 が遷移可能に | P0 |

#### TC-I3: フェーズ遷移

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-I3-1 | Phase 1 完了判定 | 全タスク completed → Phase 1 → Phase 2 | Phase 1 status = completed | P0 |
| TC-I3-2 | フェーズ順序維持 | Setup → Planning → Impl... | フェーズが順序通り遷移 | P0 |
| TC-I3-3 | Phase スキップ不可 | Phase 2 のタスク、Phase 1 未完了で実行不可 | ブロック状態が維持 | P1 |

#### TC-I4: エージェント割り当て

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-I4-1 | タスク → エージェント割り当て | task.update(owner="EM") | owner が更新される | P0 |
| TC-I4-2 | エージェント権限確認 | orchestrator の権限リスト | Task管理、Bash のみ許可 | P1 |
| TC-I4-3 | Engineer 権限確認 | Engineer の権限リスト | Bash, Edit, Write 許可 | P1 |

---

### 3.3 Level 3: E2E Tests

#### TC-E1: orchestrator → EM → Engineer フロー

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-E1-1 | EM セッション作成 | `start_pane.py --app exp-stock --workflow-id 2058 --team task-2058 --role em --dir "$PWD"` | exp-stock_orchestrator_wf2058_task-2058@main セッション作成 | P0 |
| TC-E1-2 | EM 起動確認 | `tmux capture-pane -t "exp-stock_orchestrator_wf2058_task-2058@main:managers.0" -p \| tail -5` | EM がプロンプト待機状態に | P0 |
| TC-E1-3 | EM がエンジニア起動 | `start_pane.py --app exp-stock --workflow-id 2058 --team task-2058 --role engineer --dir "$PWD"` | members.0 に Engineer pane 追加 | P0 |
| TC-E1-4 | Engineer がタスク実行 | Engineer がアーキテクチャ設計書作成 | design/BDD-Architecture.md 出力 | P0 |
| TC-E1-5 | Engineer 完了報告 | `task.py done 2058` | task_2058 status = completed | P0 |
| TC-E1-6 | orchestrator 次タスク検出 | 次のブロック解除タスク検出 | task_2059 が遷移可能に | P0 |

#### TC-E2: 監視ループ自動化

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-E2-1 | /loop 3m 起動 | `/loop 3m /orchestrate` | 3分ごと監視ループ実行 | P0 |
| TC-E2-2 | ペイン content 取得 | 全セッションのペイン取得 | capture-pane 全ペイン取得可能 | P0 |
| TC-E2-3 | "?" 自動検出 | Engineer ペインに "?" 表示 | orchestrator が質問検出 | P1 |
| TC-E2-4 | CLAUDE.md ルール自動適用 | "?" に自動回答 | 回答が送信される | P1 |
| TC-E2-5 | timeout 検知 | Engineer が 10 分応答なし | orchestrator が alert 発行 | P1 |
| TC-E2-6 | エスカレーション | ユーザーに確認が必要 | prompt が出力される | P1 |

#### TC-E3: 複数プロジェクト同時実行

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-E3-1 | exp-stock プロジェクト開始 | workflow_id=1 作成・開始 | 1つ目のプロジェクト進行 | P2 |
| TC-E3-2 | breast_cancer_research 開始 | workflow_id=2 同時作成・開始 | 2つ目のプロジェクト並行実行 | P2 |
| TC-E3-3 | リソース競合なし | 両プロジェクトの タスク並行実行 | ロック・競合なく完了 | P2 |

#### TC-E4: エラーハンドリング

| TC ID | テスト項目 | テスト手順 | 期待結果 | 優先度 |
|---|---|---|---|---|
| TC-E4-1 | タスク実行失敗 | task_2057 が失敗して pending のまま | task_2058 が blocked 継続 | P1 |
| TC-E4-2 | EM が失敗を報告 | report_anomaly.py 実行 | 異常がタスク化される | P1 |
| TC-E4-3 | 再実行指示 | EM が task_2057 再実行指示 | Engineer が修正実装 | P1 |
| TC-E4-4 | リカバリー完了 | task_2057 completed → task_2058 unblock | 正常に次タスク遷移 | P1 |

---

## 4. テスト実行手順

### 4.1 前提条件

```bash
# 1. 環境セットアップ
cd /Users/delightone/dev/github.com/adachi-koichi/ai-orchestrator

# 2. task-manager-sqlite 確認
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py list

# 3. tmux セッション確認
tmux ls

# 4. テンプレート・Gherkin ファイル配置
ls -la design/BDD-Architecture.md design/bdd-workflow.feature
```

### 4.2 Level 1 実行（Unit Tests）

```bash
# Step 1: task-manager-sqlite テスト
python3 -m pytest tests/test_task_manager.py -v

# Step 2: tmux コマンド テスト
python3 -m pytest tests/test_tmux_ops.py -v

# Step 3: Gherkin パース テスト
python3 -m pytest tests/test_gherkin_parser.py -v
```

### 4.3 Level 2 実行（Integration Tests）

```bash
# Step 1: テンプレート化・インスタンス化
python3 -c "
from design.bdd_workflow import WorkflowTemplate
tpl = WorkflowTemplate.from_file('design/bdd-workflow.feature')
instance = tpl.instantiate(project='test-project')
print(f'workflow_id={instance.id}')
"

# Step 2: フェーズ・タスク生成検証
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py list --status pending

# Step 3: DAG 依存関係検証
python3 -m pytest tests/test_task_dag.py -v
```

### 4.4 Level 3 実行（E2E Tests）

```bash
# Step 1: orchestrator → EM → Engineer フロー（start_pane.py を使う）
python3 ~/.claude/skills/task-manager-sqlite/scripts/start_pane.py \
  --app exp-stock \
  --workflow-id 2058 \
  --team task-2058 \
  --role em \
  --dir "$(pwd)" \
  --message "タスク #2058 を実装してください"
# セッション: exp-stock_orchestrator_wf2058_task-2058@main

# Step 2: 監視ループ起動
/loop 3m /orchestrate

# Step 3: ワークフロー完了まで監視
# (全タスク completed になるまで待機)

# Step 4: テスト報告書生成
python3 -m pytest tests/test_e2e_workflow.py -v --tb=short > test-results.log
```

---

## 5. テスト実行スケジュール

| フェーズ | 期間 | 内容 | 実行者 |
|---|---|---|---|
| **Phase 1: Unit** | 2026-04-18 10:00～11:00 | TC-U1～TC-U3 | Engineer |
| **Phase 2: Integration** | 2026-04-18 11:00～12:30 | TC-I1～TC-I4 | EM + Engineer |
| **Phase 3: E2E** | 2026-04-18 13:00～14:30 | TC-E1～TC-E4 | orchestrator + EM + Engineer |
| **Phase 4: 報告** | 2026-04-18 15:00～15:30 | テスト結果報告 | EM |

---

## 6. テスト成功基準

### 6.1 テスト完了条件

| 項目 | 基準 | 判定 |
|---|---|---|
| **Unit テスト合格率** | 95% 以上 | ✓ |
| **Integration テスト合格率** | 90% 以上 | ✓ |
| **E2E テスト合格率** | 85% 以上 | ✓ |
| **全タスク追跡可能** | 100% | ✓ |
| **エージェント自動化率** | 90% 以上 | ✓ |

### 6.2 リスク許容度

| リスク | 許容度 | 対応 |
|---|---|---|
| Unit テスト失敗 | 0% | すぐ修正 |
| Integration テスト失敗 | 10% | 原因分析 → 修正 |
| E2E テスト失敗 | 15% | 環境差分確認 → 修正 |
| 手動介入必要（自動化失敗） | 10% 以下 | ユーザーに通知 |

---

## 7. 欠陥管理

### 7.1 欠陥の分類

| 重大度 | 例 | 対応 |
|---|---|---|
| **Critical** | ワークフロー全体が停止 | 即座に修正・再テスト |
| **High** | フェーズ遷移失敗 | 当日中に修正 |
| **Medium** | エラーメッセージ不明確 | 翌日修正 |
| **Low** | UI 表示崩れ | 後日対応 |

### 7.2 欠陥報告フォーム

```
[タイトル] TC-E1-2: EM プロンプト待機状態に入らない
[TC ID] TC-E1-2
[重大度] High
[手順] ccc-engineering-manager 起動後、プロンプト `>` が出現しない
[結果] timeout で キャプチャが空
[原因] (調査中)
[修正案] EM 起動スクリプトのエラーハンドリング追加
```

---

## 8. テスト環境

### 8.1 環境構成

| コンポーネント | バージョン | 確認方法 |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| tmux | 3.2+ | `tmux -V` |
| task-manager-sqlite | latest | `python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py list` |
| Claude Code | latest | `claude --version` |
| git | 2.40+ | `git --version` |

### 8.2 クリーンアップ手順

**テスト後のセッション削除**:
```bash
# 全テストセッション削除（v3命名規則: {service}_orchestrator_wf{N}_{team}@main）
tmux ls -F "#{session_name}" | grep "_orchestrator_wf" | grep "@main$" | xargs -I{} tmux kill-session -t "{}"

# DB ロールバック (Optional)
# python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py bulk-delete --filter "project=test-project"
```

---

## 9. テスト成果物

### 9.1 出力ファイル

```
test-results/
├── test-report.html          # テスト実行サマリー
├── coverage-report.html      # カバレッジレポート
├── unit-test-log.txt         # Unit テスト詳細ログ
├── integration-test-log.txt  # Integration テスト詳細ログ
├── e2e-test-log.txt          # E2E テスト詳細ログ
└── defects.csv               # 欠陥一覧
```

### 9.2 確認項目チェックリスト

- [ ] Unit テスト全合格
- [ ] Integration テスト全合格
- [ ] E2E テスト全合格
- [ ] ワークフロー完了（全フェーズ completed）
- [ ] 欠陥なし、または許容度内
- [ ] ドキュメント 100% 作成完了
- [ ] 本番環境デプロイ準備完了
