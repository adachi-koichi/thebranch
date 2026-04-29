# auto_assign_pending.py — タスク自動割り当て設計書

**ドキュメント作成日**: 2026-04-20  
**Tech Lead**: claude-tech-lead（Tech Lead ロール）  
**ステータス**: 設計完了 → Engineer への引き継ぎ予定  

---

## 1. 概要

### 目的
Pending 状態の新規タスク（未割当・初回）を自動検出し、Engineering Manager (EM) に委譲するスクリプトを実装する。

**既存スクリプトとの役割分担**:
- **auto_assign_pending.py** （本設計）: 新規 pending タスク → EM への初回割当
- **auto_reassign.py** （既存）: 停滞中の pending タスク（2時間超）→ EM への再アサイン
- **orchestrate_loop.py** （統合先）: 監視ループに `auto_assign_pending_tasks(limit=5)` を組み込み

### 責務分離
| スクリプト | 担当 | トリガー | 出力 |
|---|---|---|---|
| **auto_assign_pending.py** | 新規割当 | pending かつ assignee が空 | EM セッション起動 + start_pane.py 呼び出し |
| **auto_reassign.py** | 停滞対応 | pending + 2時間超 + assignee が既に em | task.py assign で再通知 |
| **orchestrate_loop.py** | 統合・監視 | 定期スキャン（3分間隔） | 両スクリプト実行の調整 |

---

## 2. API 設計

### 2.1 主要関数仕様

#### `get_pending_tasks(db_path: Path, limit: int = 10) → list[dict]`
**説明**: pending 状態でまだ assignee が割り当てられていないタスクを取得する。

**入力**:
- `db_path` (Path): tasks.sqlite ファイルパス
- `limit` (int): 取得最大件数（デフォルト 10）

**出力** (list[dict]):
```python
[
  {
    "id": 2196,
    "title": "[ai-orchestrator] タスク自動割り当て・監視",
    "category": "infra",
    "priority": 1,
    "dir": "/path/to/project",
    "description": "...",
    "created_at": "2026-04-20T10:00:00Z",
  },
  ...
]
```

**エラーハンドリ**:
- DB ファイルが存在しない → 空リスト `[]` を返す
- DB アクセスエラー → ログ出力 + 空リスト `[]` を返す

---

#### `get_assigned_task_ids(db_path: Path) → set[int]`
**説明**: 既に assignee が割り当てられたタスク ID の集合を取得する（重複排除）。

**入力**:
- `db_path` (Path): tasks.sqlite ファイルパス

**出力** (set[int]):
```python
{2180, 2185, 2190, 2195, 2210}
```

**用途**: `get_unassigned_pending()` で割当済みを除外する際に使用。

**エラーハンドリ**:
- DB エラー → 空セット `set()` を返す

---

#### `get_unassigned_pending(db_path: Path, limit: int = 5) → list[dict]`
**説明**: pending タスク群から割当済みを除いて、割当対象タスクのみを抽出する。

**入力**:
- `db_path` (Path): tasks.sqlite ファイルパス
- `limit` (int): 割当上限数（デフォルト 5）

**出力** (list[dict]):
```python
[
  {"id": 2196, "title": "...", "category": "infra", "dir": "..."},
  {"id": 2197, "title": "...", "category": "frontend", "dir": "..."},
]
```

**内部ロジック**:
1. `get_pending_tasks()` で limit×2 件（バッファ付き）を取得
2. `get_assigned_task_ids()` で既割当を確認
3. 差分（未割当）を limit 件まで抽出

**エラーハンドリ**:
- 内部関数がエラーで空を返した → 空リスト `[]` を返す

---

#### `assign_task_to_em(task_id: int, task_dir: str, task_title: str, start_pane_path: Path) → bool`
**説明**: タスクを EM に委譲するため start_pane.py を実行し、EM セッション・ペインを起動する。

**入力**:
- `task_id` (int): タスク ID（e.g., 2196）
- `task_dir` (str): プロジェクトディレクトリ（e.g., `/Users/.../ai-orchestrator`）
- `task_title` (str): タスク名（ログ・メッセージに使用）
- `start_pane_path` (Path): start_pane.py のパス

**出力** (bool):
- True: start_pane.py の実行成功 + EM セッション起動確認
- False: エラーまたはタイムアウト

**実行コマンド例**:
```bash
python3 start_pane.py \
  --app ai-orchestrator \
  --workflow-id 2196 \
  --team task-2196 \
  --role em \
  --dir /Users/delightone/dev/github.com/adachi-koichi/ai-orchestrator \
  --message "タスク #2196「タスク自動割り当て・監視」を担当してください。"
```

**エラーハンドリ**:
- start_pane.py がファイル存在しない → ログ + False
- プロセス実行タイムアウト（5秒） → ログ + False
- task_dir が存在しない → ログ出力 + False（start_pane.py に委譲してエラーハンドルさせる）
- start_pane.py プロセスエラー（returncode != 0） → ログ + False

**レート制限**:
- 1 タスク割当につき 0.5 秒の待機 → 連続起動による tmux 過負荷を防止

---

#### `mark_task_as_assigned(task_id: int, db_path: Path) → bool`
**説明**: タスクに `assignee = "em"` を記録し、重複割当を防ぐ。

**入力**:
- `task_id` (int): 割当対象のタスク ID
- `db_path` (Path): tasks.sqlite ファイルパス

**出力** (bool):
- True: UPDATE 成功
- False: DB エラー

**SQL 実行例**:
```sql
UPDATE dev_tasks 
SET assignee = 'em', updated_at = datetime('now', 'utc')
WHERE id = 2196 AND status = 'pending'
```

**重要**: 
- `orchestrate_loop.py` の統合時には `auto_assign_pending_tasks()` が内部で自動実行
- 外部から個別呼び出しをする場合は明示的に呼び出す必要がある

**エラーハンドリ**:
- DB 接続失敗 → ログ出力 + False

---

### 2.2 メイン関数

#### `auto_assign_pending_tasks(limit: int = 5, dry_run: bool = False) → dict`
**説明**: pending タスク割当の全体を制御し、結果を集計する。

**入力**:
- `limit` (int): 1サイクルで割り当てるタスク上限数（デフォルト 5）
- `dry_run` (bool): True の場合は start_pane.py を実行しない（ログのみ）

**出力** (dict):
```python
{
  "cycle_id": "2026-04-20T12:30:00+09:00",
  "assigned_count": 3,
  "total_pending": 8,
  "details": [
    {
      "task_id": 2196,
      "title": "[ai-orchestrator] タスク自動割り当て・監視",
      "status": "assigned",  # or "failed"
      "error_message": None,
    },
    {
      "task_id": 2197,
      "title": "...",
      "status": "assigned",
      "error_message": None,
    },
  ],
  "next_check_seconds": 300,
}
```

**実行フロー**:
1. `get_unassigned_pending()` で割当対象 limit 件を抽出
2. 各タスクに対して `assign_task_to_em()` を実行
3. 成功したら `mark_task_as_assigned()` で DB 更新
4. ログ・JSON 出力で結果を記録

**エラーハンドリ**:
- 対象なし → `assigned_count: 0` で正常終了
- 一部失敗 → 成功分は DB 更新、失敗分は `details` に error_message を記録

---

## 3. 既存コンポーネント との統合設計

### 3.1 start_pane.py との連携

start_pane.py が以下を自動実行：
1. セッション名生成（v3形式: `ai-orchestrator_orchestrator_wf{task_id:03d}_task-{task_id}@main`）
2. managers ウィンドウ作成 + em ロール ペイン起動
3. `ccc-engineering-manager` コマンド実行
4. pane_registry.json にペイン情報を記録
5. メッセージをペインに送信

**auto_assign_pending.py の役割**:
- start_pane.py の正しいパスと引数を用意
- プロセス実行 + タイムアウト管理

**連携パラメータ**:
```python
{
  "app": "ai-orchestrator",          # スキル内で固定
  "workflow_id": task_id,             # 各タスク ID
  "team": f"task-{task_id}",          # チーム名（一意性確保）
  "role": "em",                       # 固定
  "dir": task_dir,                    # プロジェクトディレクトリ
  "message": f"タスク #{task_id}「{task_title}」を担当してください。",
}
```

---

### 3.2 pane_registry.json との関係

**目的**: start_pane.py が起動したすべてのペイン（セッション・ウィンドウ・役割）を追跡

**自動登録**: start_pane.py が実行時に自動記録
- 新規ペインの create_at、ccc_cmd、role を保存
- orchestrate_loop.py で pane_registry.json を読み込み、EM の進捗を追跡

**auto_assign_pending.py の確認**:
- 割当直後は start_pane.py が pane_registry.json に記録するため、別途確認不要
- ただし EM セッション起動確認の簡易チェックは可能:
  ```python
  # 例: tmux session-exists で確認
  session = f"ai-orchestrator_orchestrator_wf{task_id:03d}_task-{task_id}@main"
  ```

---

### 3.3 session_naming.py との連携

session_naming.py (SSOT) が提供する機能：
- `make_team_session(service, workflow_id, team_name) → str`
  - 入力: `("ai-orchestrator", 2196, "task-2196")`
  - 出力: `"ai-orchestrator_orchestrator_wf002196_task-2196@main"`

**auto_assign_pending.py での使用方法**:
```python
from session_naming import make_team_session

session_name = make_team_session("ai-orchestrator", task_id, f"task-{task_id}")
# → "ai-orchestrator_orchestrator_wf{task_id:03d}_task-{task_id}@main"
```

**利点**:
- セッション名生成ロジックが一元化 → 変更時の一括対応が容易

---

## 4. リソース制限・無限ループ防止

### 4.1 割当数の制限

**1サイクルごとの上限（limit パラメータ）**:
- デフォルト: 5 タスク/サイクル
- orchestrate_loop.py からの呼び出し時: `limit=5`
- 手動実行時: `--limit 10` で上書き可能

**理由**:
- tmux セッション・ペイン作成の負荷分散
- EM への心理的負荷軽減（一度に 5 つまで）
- ループ内での処理時間短縮（5 タスク × 0.5 秒 = 2.5 秒）

### 4.2 無限ループ防止

**重複割当の防止**:
1. `assignee` フィールドで既割当を追跡
2. `mark_task_as_assigned()` で `assignee = 'em'` をセット
3. `get_unassigned_pending()` で `assignee IS NULL` のみを抽出

**チェック方法**:
```sql
SELECT * FROM dev_tasks 
WHERE status = 'pending' AND (assignee IS NULL OR assignee = '');
```

**db トランザクション**:
- UPDATE 成功 → 確定（重複排除）
- UPDATE 失敗 → ロールバック → 次サイクルで再試行

### 4.3 リソース上限

**tmux セッション・ペイン**:
- orchestrate_loop.py で既に管理される同時セッション制限ルール に従う
- auto_assign_pending.py は「割当指示」のみ → 実際の EM 起動は start_pane.py + orchestrate_loop.py に委譲

**ネットワーク・プロセス**:
- start_pane.py 呼び出しの待機時間: 0.5 秒（レート制限）
- プロセスタイムアウト: 5 秒（hang 検知）

---

## 5. エラーハンドリング戦略

### 5.1 エラー分類と対応

| エラー | 原因 | 対応 |
|---|---|---|
| DB 接続失敗 | sqlite3 コネクション | ログ出力 → スキップ |
| start_pane.py 不存在 | ファイルパス誤り | ログ出力 → スキップ |
| プロセスタイムアウト | tmux 過負荷 | ログ + 次サイクルへ |
| task_dir 不存在 | 設定誤り | start_pane.py へ委譲 |
| assignee UPDATE 失敗 | DB ロック競合 | ログ + 再試行フラグ |

### 5.2 ロギング

**ログレベル**:
- **INFO**: 割当成功、cycle 統計
- **WARNING**: 部分失敗（N/M 成功）
- **ERROR**: 重大エラー（DB 接続失敗、start_pane.py 実行エラー）

**ログ出力先**:
- stdout: orchestrate_loop.py に統合時の可視化
- ファイル: `/tmp/orchestrate_auto_assign.jsonl`（JSONL 形式）

**JSONL スキーマ**:
```json
{
  "timestamp": "2026-04-20T12:30:15+09:00",
  "cycle_id": "2026-04-20T12:30:00+09:00",
  "event": "assigned",
  "task_id": 2196,
  "task_title": "[ai-orchestrator] タスク自動割り当て・監視",
  "status": "success",
  "error_message": null
}
```

---

## 6. orchestrate_loop.py への統合

### 6.1 呼び出し箇所

orchestrate_loop.py のメインループに以下を追加：

```python
# orchestrate_loop.py の main() or loop() 関数内
from auto_assign_pending import auto_assign_pending_tasks

def orchestrate_cycle():
    """統合ループ内で自動割当を実行"""
    
    # 既存処理
    idle_panes = detect_idle_panes()
    check_task_completion()
    auto_close_session()
    
    # ← ここに新規: pending 自動割当
    assign_result = auto_assign_pending_tasks(limit=5, dry_run=False)
    if assign_result["assigned_count"] > 0:
        print(f"[orchestrate] {assign_result['assigned_count']} 件のタスクを EM に割り当てました")
        log_cycle_result(assign_result)
    
    # 続行: その他の処理
    check_long_pending_tasks()
```

### 6.2 呼び出し頻度

- **orchestrate_loop.py の実行間隔**: 3 分（180 秒）
- **auto_assign_pending_tasks() の実行**: 毎サイクル（3 分ごと）
- **割当上限**: 5 タスク/サイクル → 最大 15 タスク/9 分

### 6.3 統合パラメータ

```python
auto_assign_pending_tasks(
    limit=5,        # 1サイクルで割り当てるタスク数（デフォルト）
    dry_run=False   # 本番実行（ログのみモード不使用）
)
```

---

## 7. 危険性検討・ミティゲーション

### 7.1 潜在的な危険性

| 危険性 | シナリオ | ミティゲーション |
|---|---|---|
| **無限割当** | 重複チェック失敗 → 同じタスクを繰り返し割当 | assignee フィールドで状態追跡 |
| **tmux リソース枯渇** | limit を大きく設定 → 過度なセッション生成 | limit デフォルト 5 固定、手動変更不可 |
| **EM 過負荷** | 一度に多数のタスク割当 → EM の判断不能 | limit 5 で心理的負荷を制限 |
| **DB ロック競合** | start_pane.py と assignee UPDATE が競合 | トランザクション・エラーハンドリング実装 |
| **プロセスハング** | start_pane.py が応答不可 → orchestrate_loop 全体停止 | プロセスタイムアウト 5 秒で強制終了 |

### 7.2 監視・アラート

**orchestrate_loop.py での監視**:
- `assigned_count` が 0 のまま 3 サイクル（9 分）続いた → INFO ログ（通常）
- `assigned_count` が割当対象数より少ない → WARNING ログ（一部失敗の可能性）
- エラーが連続発生 → ERROR ログ → report_anomaly.py でタスク化

**手動確認方法**:
```bash
# 割当ログを確認
tail -f /tmp/orchestrate_auto_assign.jsonl

# pending タスクの assignee を確認
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py list --status pending | grep -E "assignee|^  ID"
```

---

## 8. 実装開始前のチェックリスト

Engineer への引き継ぎ前に以下を確認：

- [ ] start_pane.py のパス確認（SSOT: session_naming.py の SERVICE_ALLOWLIST との整合）
- [ ] task.sqlite スキーマ確認（`assignee` フィールドが存在するか）
- [ ] TASKS_DB 環境変数の有無を確認（デフォルト: `~/.claude/skills/task-manager-sqlite/data/tasks.sqlite`）
- [ ] EM ロール用の `ccc-engineering-manager` コマンドが存在するか
- [ ] orchestrate_loop.py への統合ポイント明確化
- [ ] `/tmp/orchestrate_auto_assign.jsonl` 出力パスの権限確認

---

## 9. Engineer への引き継ぎ項目

### 実装範囲

1. **新規スクリプト作成**: `scripts/auto_assign_pending.py`
   - 5つの主要関数 + メイン関数を実装
   - エラーハンドリング完備（try-except）
   - ログ出力・JSON 記録

2. **orchestrate_loop.py への統合**
   - import 追加
   - 呼び出し挿入（メインループ内）
   - ログ出力の統合

3. **テスト実装**
   - ユニットテスト: 各関数の I/O テスト
   - 統合テスト: orchestrate_loop 内での動作確認
   - 手動テスト: `--dry-run` で重複割当検証

### 実装優先度

1. 関数定義（API 仕様の厳密化）
2. DB 操作（get_pending_tasks, mark_task_as_assigned）
3. start_pane.py 連携（assign_task_to_em）
4. メイン関数実装（auto_assign_pending_tasks）
5. orchestrate_loop.py 統合

---

## 10. 参考資料

| ファイル | 用途 |
|---|---|
| `scripts/auto_reassign.py` | 停滞タスク対応の参考（既存パターン） |
| `scripts/orchestrate_loop.py` | 統合先・スケジューリング参考 |
| `~/.claude/skills/task-manager-sqlite/scripts/start_pane.py` | EM セッション起動の参考 |
| `~/.claude/skills/orchestrate/scripts/session_naming.py` | セッション命名規則（SSOT） |
| `~/.claude/skills/task-manager-sqlite/data/tasks.sqlite` | スキーマ参照 |

---

**設計書作成者**: Tech Lead  
**作成日**: 2026-04-20  
**引き継ぎ対象**: Engineer（実装担当）  

---

## 変更履歴

| 版 | 日時 | 変更内容 |
|---|---|---|
| v1 | 2026-04-20 | 初版作成：API 設計・統合方法・危険性検討 |
