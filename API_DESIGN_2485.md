# タスク #2485: API I/F 設計ドキュメント
## AIエージェント評価・スコアリング機能実装

作成日: 2026-04-26  
ステータス: EM 設計レビュー完了

---

## 1. データベーススキーマ

### `agent_scores` テーブル

```sql
CREATE TABLE agent_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL UNIQUE,           -- エージェント一意識別子
  agent_name TEXT NOT NULL,                 -- エージェント名
  completion_rate REAL,                     -- タスク完了率 (0.0-1.0)
  quality_score REAL,                       -- 品質スコア (0-100)
  performance_score REAL,                   -- パフォーマンススコア (0-100)
  overall_score REAL,                       -- 総合スコア (0-100)
  total_tasks INTEGER DEFAULT 0,            -- 担当タスク数合計
  completed_tasks INTEGER DEFAULT 0,        -- 完了タスク数
  last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### スコア計算式

- **完了率 (completion_rate)**: `completed_tasks / total_tasks`
- **品質スコア (quality_score)**: テストパス率 × 100（0-100）
- **パフォーマンススコア (performance_score)**: 平均応答時間スコア（0-100）
- **総合スコア (overall_score)**: `(completion_rate × 40 + quality_score × 30 + performance_score × 30)`

---

## 2. API エンドポイント仕様

### GET `/api/agents/scores`

**説明**: 全エージェントのスコア一覧を取得

**レスポンス**:

```json
{
  "ok": true,
  "data": [
    {
      "id": 1,
      "agent_id": "eng-001",
      "agent_name": "Engineer #1",
      "completion_rate": 0.85,
      "quality_score": 92.5,
      "performance_score": 88.0,
      "overall_score": 89.2,
      "total_tasks": 20,
      "completed_tasks": 17,
      "last_updated": "2026-04-26T15:00:00Z"
    }
  ],
  "error": null
}
```

---

### GET `/api/agents/scores/<agent_id>`

**説明**: 特定エージェントのスコア詳細を取得

**パラメータ**:
- `agent_id` (string, required): エージェントID

**レスポンス**: 単一エージェントのスコアオブジェクト

---

### POST `/api/agents/scores`

**説明**: エージェントスコアを作成・更新

**リクエストボディ**:

```json
{
  "agent_id": "eng-001",
  "agent_name": "Engineer #1",
  "total_tasks": 20,
  "completed_tasks": 17,
  "quality_score": 92.5,
  "performance_score": 88.0
}
```

**レスポンス**:

```json
{
  "ok": true,
  "data": { /* created/updated score object */ },
  "error": null
}
```

---

## 3. フロントエンド実装要件

### UI コンポーネント

1. **「エージェントスコア」タブ** (`dashboard/index.html`)
   - タブを有効化
   - スコアテーブル表示

2. **スコアテーブル**
   - 列: エージェント名 | 完了率 | 品質 | パフォーマンス | 総合スコア
   - ソート可能（列クリックでソート）
   - 行クリックで詳細表示

3. **グラフ表示（オプション）**
   - 総合スコア別の棒グラフ
   - 完了率の円グラフ

### API 呼び出し

```javascript
// スコア一覧取得
fetch('/api/agents/scores')
  .then(r => r.json())
  .then(data => {
    // data.data に scores 配列
    renderScoresTable(data.data);
  });

// 自動更新（30秒ごと）
setInterval(() => {
  fetch('/api/agents/scores').then(/* ... */);
}, 30000);
```

---

## 4. バックエンド実装ロードマップ

### Phase 1: DB Migration & 初期実装
- [ ] `agent_scores` テーブル作成
- [ ] `/api/agents/scores` GET エンドポイント実装
- [ ] `/api/agents/scores` POST エンドポイント実装

### Phase 2: スコアリングロジック
- [ ] 完了率計算関数
- [ ] 品質スコア計算関数
- [ ] パフォーマンススコア計算関数
- [ ] 総合スコア計算関数

### Phase 3: テスト
- [ ] curl でAPIテスト（正常系・異常系）
- [ ] スコア計算ロジックの単体テスト

---

## 5. 連携チェックリスト

### バックエンド ← → フロントエンド

- [ ] API I/F 合意完了
- [ ] JSON スキーマ確認
- [ ] レスポンス形式統一
- [ ] CORS 設定確認
- [ ] キー名の大文字小文字統一

---

## 6. テスト方法

### バックエンド動作確認

```bash
# スコア一覧取得
curl http://localhost:5000/api/agents/scores

# スコア作成
curl -X POST http://localhost:5000/api/agents/scores \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"eng-001","agent_name":"Test","total_tasks":10,"completed_tasks":8}'
```

### フロントエンド動作確認

1. `http://localhost:5000` を開く
2. 「エージェントスコア」タブをクリック
3. テーブル・グラフが表示されることを確認
4. 自動更新（30秒ごと）が動作することを確認

---

**EM 署名**: Engineering Manager  
**承認日**: 2026-04-26
