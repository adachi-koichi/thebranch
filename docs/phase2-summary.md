# Phase 2 技術調査 - 成果物サマリ

**完了日**: 2026-04-18  
**Tech Lead**: AI Orchestrator  
**ステータス**: Phase 2 完了 → Phase 3 準備完了

---

## 調査成果

### 1. ワークフローテンプレートスキーマ設計 ✅

#### 既存インフラの活用
- task-manager-sqlite v2 の既存テーブル（workflow_templates, wf_template_nodes, wf_template_edges）を基盤として活用
- KuzuDB グラフDB がすでに統合されており、依存関係の循環検出・高速クエリが可能

#### 新規テーブル設計（Phase ベース）
1. **`wf_template_phases`** - フェーズレベルのメタデータ
   - phase_order で実行順序を制御
   - specialist_type でロール要件を定義
   - is_parallel で前フェーズとの並列性を制御

2. **`wf_template_tasks`** - タスク定義テンプレート
   - task_key で一意性を確保
   - depends_on_key で同一フェーズ内の依存関係を定義
   - プレースホルダ対応で動的タスク生成をサポート

3. **`workflow_instance_specialists`** - Specialist アサイン管理
   - インスタンスごとに異なる specialist 組合せをサポート
   - phase_key → specialist_id のマッピングを保持

#### スキーマの利点
- **シンプル**: 既存テーブルの拡張により、複雑性を最小化
- **汎用性**: Phase ベースにより、多様なワークフローパターンに対応
- **トレーサビリティ**: 全アサインメント・マッピングを記録

### 2. インスタンス化メカニズム設計 ✅

#### インスタンス化の流れ（5 段階）

```
1. テンプレート + Specialist Assignment
   ↓
2. workflow_instances レコード作成
   ↓
3. workflow_instance_specialists に specialist マッピング記録
   ↓
4. wf_instance_nodes（Phase インスタンス）を生成
   ↓
5. dev_tasks を自動生成・依存関係を設定
```

#### Specialist 割り当て戦略
- **方式選択**: ユーザー指定（方式 3）を採用
  - 理由: テンプレートは汎用的だが、実際の specialist は都度決定が必要
  - メリット: インスタンスごとに異なる specialist 組合せをテスト・レビュー可能

#### Phase 順序制御メカニズム
- **遷移ルール**: waiting → ready → running → completed
- **前フェーズ完了待ち**: task_dependencies + unblock_successors 既存機構を活用
- **実装シンプル**: 既存の タスク依存関係管理（KuzuDB）を再利用

#### 実装のメリット
- 既存の task-manager-sqlite インフラ（SQLite + KuzuDB）との統合がシンプル
- unblock_successors() 既存ロジックを活用し、phase_order に基づく自動アンブロック

### 3. 自動タスク生成設計 ✅

#### タスク生成アルゴリズム
1. フェーズを phase_order でソート
2. 各フェーズごとに task_defs（wf_template_tasks）から読み込み
3. specialist 情報を workflow_instance_specialists から取得
4. dev_tasks にレコード作成（status='pending', assignee=specialist_slug）
5. task_dependencies に依存関係を記録

#### 順序依存性の実装

**レベル 1: フェーズレベル**
```
Phase N のすべてのタスク completed
   ↓
task_dependencies の unblock_successors 呼び出し
   ↓
Phase N+1 のタスク: blocked → pending に自動遷移
```

**レベル 2: フェーズ内タスク**
```
depends_on_key で同一フェーズ内の先行タスクを定義
   ↓
task_dependencies に挿入
   ↓
先行タスク完了時に自動アンブロック
```

#### 冪等性の保証
- インスタンス化時に既にタスクが生成されているか確認
- 重複生成を防止し、トレーサビリティを向上

#### 生成タスク数の計算
```
Total Tasks = Σ(phase.task_count) for all phases
Dependency Edges = Σ(フェーズ間依存) + Σ(フェーズ内依存)
```

---

## 実装に必要な確認項目

### データベース・スキーマ

- [x] 既存テーブルの構造確認（workflow_templates, wf_template_nodes, wf_template_edges）
- [x] 新規テーブル設計（wf_template_phases, wf_template_tasks, workflow_instance_specialists）
- [ ] マイグレーション SQL の実装と検証
- [ ] データベースインデックスの最適化

### インスタンス化メカニズム

- [ ] instantiate_workflow() 関数の実装
- [ ] specialist_assignments パラメータの UI/API 仕様
- [ ] エラーハンドリング（specialist 不在、前フェーズ未完了等）
- [ ] トランザクション管理（原子性の確保）

### 自動タスク生成

- [ ] generate_tasks_for_workflow_instance() 関数の実装
- [ ] task_defs → dev_tasks のマッピング（ID 管理）
- [ ] depends_on_key の解決ロジック
- [ ] プレースホルダ置換エンジン（{specialist_name}, {phase_label} 等）

### テスト戦略

- [ ] ユニットテスト（各関数の単体テスト）
- [ ] 統合テスト（テンプレート→インスタンス→タスク生成の全フロー）
- [ ] E2E テスト（BDD シナリオに基づいて）
- [ ] パフォーマンステスト（大規模ワークフローの生成時間）

---

## Phase 3 へ向けたロードマップ

### Phase 3: 実装 & ステップ定義

#### マイルストーン 3-1: スキーマ実装（1-2 日）
- マイグレーション SQL の作成・実行
- 新規テーブルの検証

#### マイルストーン 3-2: インスタンス化機能実装（2-3 日）
- instantiate_workflow() 関数の実装
- specialist assignment の入力・検証ロジック
- エラーハンドリング

#### マイルストーン 3-3: タスク自動生成実装（2-3 日）
- generate_tasks_for_workflow_instance() 関数
- depends_on_key の依存関係解決
- タスク生成ロジックの検証

#### マイルストーン 3-4: BDD テスト実装（1-2 日）
- workflow-template.feature のステップ定義
- Gherkin シナリオから実装への自動トレーサビリティ

#### マイルストーン 3-5: 統合テスト & E2E（1-2 日）
- エンドツーエンドフロー検証
- パフォーマンステスト
- エッジケースの検証

---

## 技術的なリスク & 対策

| リスク | 影響 | 対策 |
|---|---|---|
| **既存テーブルとの互換性** | マイグレーション失敗 | マイグレーション SQL を念入りにテスト。ロールバック計画を準備 |
| **複雑な依存関係ロジック** | バグの温床 | ユニットテスト・グラフDB による循環検出を活用 |
| **specialist 割り当て漏れ** | タスク孤立 | インスタンス化時に全 phase に specialist が割り当てられているか確認 |
| **プレースホルダ置換エラー** | 動的タスク生成失敗 | テンプレート検証時にプレースホルダ一覧を確認 |
| **大規模タスク生成の性能** | DB ロック・タイムアウト | バッチ挿入・トランザクション最適化を検討 |

---

## 参考資料

- **スキーマ詳細**: `/docs/workflow-template-design.md` (Section 1)
- **インスタンス化詳細**: `/docs/workflow-template-design.md` (Section 2)
- **タスク生成詳細**: `/docs/workflow-template-design.md` (Section 3)
- **BDD シナリオ**: `/features/workflow-template.feature`

---

## 次ステップ

1. **ユーザーレビュー**: 設計内容に対するフィードバック・承認
2. **スキーマ検証**: 既存 DB でのマイグレーションテスト
3. **実装開始**: Phase 3 - マイルストーン 3-1 から順序実行

---

*Phase 2 完了。Phase 3 では、このドキュメントに基づいて実装を進めます。*
