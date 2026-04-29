# タスク #2516: 全文検索・AIセマンティック検索 設計仕様書

## 1. アーキテクチャ概要

```
クライアント (Browser)
    ↓  GET /api/search?query=...&type=...&date_from=...&date_to=...
FastAPI (search_routes.py)
    ↓
SearchService
    ├─ FTS5 BM25 全文検索 (app.sqlite の search_index テーブル)
    └─ キーワード展開（同義語マップ）
```

外部ライブラリ追加なし。SQLite FTS5 の bm25() 関数を使用。

---

## 2. データベース設計

### 2-1. FTS5 仮想テーブル (app.sqlite に追加)

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    doctype,      -- 'department' | 'task' | 'mission' | 'agent' | 'comment'
    doc_id,       -- 元テーブルの id (TEXT)
    title,        -- タイトル・名前
    content,      -- 説明・本文
    created_at    UNINDEXED,  -- 日付フィルタ用（インデックス対象外）
    tokenize = 'unicode61 remove_diacritics 1'
);

-- FTS5 設定テーブル（最終ビルド日時管理）
CREATE TABLE IF NOT EXISTS search_index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### 2-2. インデックス対象テーブル

| doctype | 元テーブル | title カラム | content カラム |
|---|---|---|---|
| department | departments | name | description |
| task | tasks | title | description |
| mission | missions | name | description |
| agent | agents | role | session_id |
| comment | delegation_comments | comment_type | content |

### 2-3. マイグレーションファイル

`dashboard/migrations/024_search_index.sql`

---

## 3. API エンドポイント設計

### GET /api/search

**リクエストパラメータ:**

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| query | string | ○ | 検索クエリ（1〜200文字） |
| type | string | - | フィルタ: department/task/mission/agent/comment（カンマ区切り複数可） |
| date_from | string | - | ISO8601 日付 (例: 2026-01-01) |
| date_to | string | - | ISO8601 日付 |
| limit | int | - | 最大件数（デフォルト20, 最大100） |
| offset | int | - | ページネーション（デフォルト0） |

**レスポンス (200 OK):**

```json
{
  "results": [
    {
      "type": "department",
      "id": "42",
      "title": "マーケティング部署",
      "snippet": "...SEO・広告運用を担当する<mark>マーケティング</mark>部署...",
      "score": 0.87,
      "created_at": "2026-04-01T10:00:00"
    }
  ],
  "total": 15,
  "query": "マーケティング",
  "expanded_terms": ["マーケ", "marketing", "広告"],
  "took_ms": 12
}
```

**エラーレスポンス:**

```json
// 400: クエリ空・長すぎる
{"detail": "query must be between 1 and 200 characters"}

// 422: パラメータ型エラー（FastAPI 標準）
```

### POST /api/search/rebuild (管理者向け)

FTS インデックスを全再構築する。

```json
// レスポンス
{"ok": true, "indexed": 1247, "took_ms": 234}
```

---

## 4. SearchService 実装仕様

### 4-1. キーワード展開（同義語マップ）

```python
SYNONYM_MAP = {
    "エージェント": ["agent", "AI", "自動化"],
    "部署":         ["department", "チーム", "組織"],
    "タスク":       ["task", "作業", "TODO"],
    "ミッション":   ["mission", "目標", "プロジェクト"],
    "予算":         ["budget", "コスト", "費用"],
    "ワークフロー": ["workflow", "フロー", "プロセス"],
}
```

クエリ中のキーワードにマッチした同義語を OR 検索に追加。

### 4-2. BM25 スコアリング

```sql
SELECT
    doctype, doc_id, title, content, created_at,
    bm25(search_index, 10.0, 5.0) AS score  -- title に高い重み
FROM search_index
WHERE search_index MATCH ?
  AND (? = '' OR doctype IN (...))
  AND (? = '' OR created_at >= ?)
  AND (? = '' OR created_at <= ?)
ORDER BY score
LIMIT ? OFFSET ?
```

※ FTS5 の bm25() は負の値を返す（小さいほど高スコア）。正規化してから返す。

### 4-3. スニペット生成

```sql
snippet(search_index, 3, '<mark>', '</mark>', '...', 20)
```

---

## 5. ファイル構成（変更・追加）

```
dashboard/
├── search_routes.py          ← 新規: /api/search エンドポイント
├── search_service.py         ← 新規: SearchService（同義語展開・BM25）
├── migrations/
│   └── 024_search_index.sql  ← 新規: FTS5テーブル + 初期投入
└── app.py                    ← 変更: search_routes.router を include

dashboard/js/
└── search.js                 ← 新規: 検索UIコンポーネント（Cmd+K）
```

---

## 6. Frontend 実装仕様

### 6-1. 検索UI（Cmd+K ショートカット）

- `Cmd+K`（Mac）/ `Ctrl+K`（Win）でモーダル表示
- `/` キーでもトリガー（ただしフォーカスがテキスト入力中の場合は除く）
- モーダル外クリック or `Escape` で閉じる

### 6-2. インタラクション

1. キー入力 → 300ms debounce → `GET /api/search?query=...`
2. 結果を type 別にグループ化して表示
3. 各結果をクリック → 対象ページへ遷移
4. ローディングスピナー表示（レスポンス待ち中）

### 6-3. タイプ別遷移先

| type | 遷移先 |
|---|---|
| department | `/` (ダッシュボード、部署カード)  |
| task | `/` (タスクセクション) |
| mission | `/workflows` |
| agent | `/` (エージェントセクション) |
| comment | `/` |

### 6-4. UX 要件

- type フィルタはタブ（すべて / 部署 / タスク / ミッション / エージェント）
- snippet の `<mark>` タグは `font-weight: bold; color: var(--accent)` でハイライト
- 結果ゼロ時は「見つかりませんでした」＋検索ヒント表示
- 検索履歴を localStorage に最大5件保持

---

## 7. 実装順序

1. **Backend Engineer**: search_routes.py + search_service.py + migration SQL
2. **Frontend Engineer**: search.js + index.html への統合
3. **動作確認**: curl テスト → ブラウザ確認
