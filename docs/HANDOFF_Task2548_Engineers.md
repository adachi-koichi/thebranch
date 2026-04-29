# Task #2548 実装ハンドオフドキュメント

**From**: Tech Lead  
**To**: Engineer Team（billing チーム）  
**Date**: 2026-04-30 07:30 JST  
**Task**: サブスクリプション・課金管理システム MVP Phase 1 実装  
**Deadline**: 2026-05-02 18:00 JST（48 時間）

---

## 概要

Tech Lead による技術設計が完了しました。本ドキュメントは、Engineers が設計仕様に基づいて実装を開始するためのハンドオフガイドです。

---

## 📋 設計仕様書

**ファイル**: `docs/subscription_system_design.md`

設計仕様には以下が含まれます：
- ✅ DB スキーマ定義（migration SQL 含む）
- ✅ API エンドポイント仕様（リクエスト/レスポンス形式）
- ✅ Pydantic モデル定義（コピペ可能な Python コード）
- ✅ ビジネスロジック・エラーハンドリング
- ✅ テスト戦略（ユニット・統合・BDD）
- ✅ 実装チェックリスト

**必読項目**:
1. 「2. データベース設計」（DB スキーマ）
2. 「3. API 仕様」（エンドポイント定義）
3. 「5. 実装ガイドライン」（ファイル構成・ビジネスロジック）
4. 「6. テスト戦略」（テスト項目一覧）

---

## 🎯 実装スコープ（MVP Phase 1）

### ✅ 実装する機能

| 機能 | 詳細 | 担当 |
|------|------|------|
| **DB スキーマ** | subscriptions, subscription_plans テーブル作成 | Engineer #1 |
| **API - プラン一覧** | GET /api/subscriptions/plans | Engineer #1 |
| **API - 現在のサブスク** | GET /api/subscriptions/current | Engineer #1 |
| **API - プラン切り替え** | PATCH /api/subscriptions/plan | Engineer #1 |
| **Pydantic モデル** | SubscriptionPlan, SubscriptionResponse 等 | Engineer #1 |
| **Repository レイヤー** | DB アクセス層実装 | Engineer #2 |
| **Service レイヤー** | ビジネスロジック層実装 | Engineer #2 |
| **API ルーター** | routes/subscriptions.py 実装 | Engineer #1 |
| **UI - プラン比較** | templates/pages/subscriptions.html 実装 | Engineer #3 |
| **ユニットテスト** | pytest による単体テスト実装 | Engineer #2 |
| **統合テスト** | API 結合テスト実装 | Engineer #2 |
| **BDD テスト** | features/subscription.feature 実装・実行 | Engineer #3 |
| **E2E 動作確認** | ブラウザでの動作確認 | Engineer #3 |

### ❌ スコープ外（Phase 2 以降）

- Stripe webhook 連携
- 従量課金・プロビジョニング上限
- 監査ログ
- 複数通貨対応

---

## 📂 ファイル構成

実装時に以下のファイルを作成・修正：

```
dashboard/
├── models.py                           ← Pydantic モデル追加
├── routes/
│   └── subscriptions.py                ← 新規作成
├── repositories/
│   └── subscription.py                 ← 新規作成
├── services/
│   └── subscription.py                 ← 新規作成
├── migrations/
│   └── 026_create_subscriptions_tables.sql  ← 新規作成
├── templates/
│   └── pages/
│       └── subscriptions.html          ← 新規作成
└── app.py                              ← routes 登録（1行追加）

tests/
└── test_subscriptions_api.py           ← 新規作成

features/
└── subscription.feature                ← 新規作成
```

---

## 🔧 実装順序（推奨）

### Phase 1: DB・モデル（Engineer #1, #2）
1. Migration SQL 実行（026_create_subscriptions_tables.sql）
2. Pydantic モデル定義（dashboard/models.py に追加）
3. 初回ユーザーへの Free プラン自動割り当て処理を設計

### Phase 2: Repository・Service（Engineer #2）
1. subscription.py（Repository層）実装 - DB CRUD 操作
2. subscription.py（Service層）実装 - ビジネスロジック
3. エラーハンドリング・バリデーション実装

### Phase 3: API ルーター（Engineer #1）
1. routes/subscriptions.py 実装 - 3 つのエンドポイント
2. app.py に `app.include_router(subscriptions_router)` を追加
3. 認証（Bearer token）チェック

### Phase 4: UI（Engineer #3）
1. templates/pages/subscriptions.html 実装
2. プラン比較カード UI（Chart.js で可視化）
3. プラン切り替えボタン＆フォーム

### Phase 5: テスト（Engineer #2, #3）
1. ユニットテスト実装（test_subscriptions_api.py）
2. BDD テスト実装（features/subscription.feature）
3. 全テスト通過確認
4. E2E 動作確認（ブラウザテスト）

---

## 🧪 テスト実行コマンド

```bash
# ユニットテスト実行
pytest tests/test_subscriptions_api.py -v

# BDD テスト実行
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py wf instance node-done <TASK_ID> testing

# 全テスト実行
pytest

# カバレッジ確認
pytest --cov=dashboard.routes.subscriptions tests/test_subscriptions_api.py
```

---

## ✅ 実装完了の確認事項

実装が完了したら、以下をすべて確認してください：

- [ ] DB マイグレーション実行済み（subscriptions テーブル作成確認）
- [ ] Pydantic モデル定義完成（import エラーなし）
- [ ] Repository レイヤー実装＆テスト通過
- [ ] Service レイヤー実装＆テスト通過
- [ ] API ルーター実装＆エンドポイント疎通確認（curl/Postman）
- [ ] ユニットテスト全テスト通過（pytest）
- [ ] BDD テスト全テスト通過（Gherkin）
- [ ] UI 実装・ブラウザ確認（プラン比較画面の表示）
- [ ] E2E 動作確認
  - [ ] Free → Pro 切り替え
  - [ ] Pro → Free 切り替え
  - [ ] エラーハンドリング確認（無効なプラン等）
- [ ] セキュリティレビュー実施
  - [ ] 認証チェック（未認証時は 401 エラー）
  - [ ] 入力検証（無効なプラン ID チェック）
  - [ ] SQL インジェクション対策（Pydantic + ORM 使用で OK）
- [ ] コードレビュー＆マージ

---

## 🚨 重要な実装ポイント

### 1. DB スキーマの UNIQUE 制約

```sql
user_id TEXT NOT NULL UNIQUE  -- 1ユーザーにつき1サブスク
```

**重要**: ユーザーが複数のサブスクリプションレコードを持たないよう UNIQUE 制約を必ず設定。

### 2. 期間計算

プラン切り替え時、新しい `current_period_end` を計算：

```python
from datetime import datetime, timedelta
current_period_start = datetime.utcnow()
current_period_end = current_period_start + timedelta(days=30)
```

### 3. 初回ユーザーのプラン設定

ユーザー登録時に自動的に Free プラン を割り当てるロジックが必要。以下のどこかに実装：

- auth.py の登録処理後
- または dashboard/app.py のミドルウェア

例：
```python
subscription = Subscription(
    id=generate_uuid(),
    user_id=user.id,
    plan='free',
    status='active',
    current_period_start=datetime.utcnow(),
    current_period_end=datetime.utcnow() + timedelta(days=30),
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow()
)
```

### 4. エラーハンドリング

以下のエラーは適切に HTTP ステータスコードで返却：

| エラー | Status | メッセージ例 |
|------|--------|-------------|
| 無効なプラン | 400 | `Invalid plan: 'vip'. Valid plans: free, pro, enterprise` |
| 同じプラン変更 | 400 | `User is already on pro plan` |
| サブスク未登録 | 404 | `Subscription not found for user` |
| 認証失敗 | 401 | `Not authenticated` |

### 5. テストの DB 分離

テスト実行時は本番 DB と分離。pytest.ini で fixture を設定：

```python
@pytest.fixture
def test_db():
    # テスト用 DB 作成
    # テスト後にクリーンアップ
    yield db
```

---

## 📞 質問・ブロッカー対応

実装中に以下のことが発生した場合は**即座に**報告してください：

1. **設計仕様の不明点** → Tech Lead に質問
2. **DB スキーマの変更が必要** → Tech Lead に相談
3. **API 仕様の変更が必要** → Tech Lead に相談
4. **実装時間が予測を超える見込み** → PM に報告（スコープ削減の検討）

---

## 📊 進捗トラッキング

タスク管理システムで進捗を記録してください：

```bash
# 実装開始時
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py update 2548 --status in_progress

# 各フェーズ完了時
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py comment add 2548 "Phase X: ✅ 完了"

# 実装完了時
python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py done 2548
```

---

## 🎉 完了後

実装が完了したら：

1. **main ブランチへマージ**
2. **リリースノート更新** - MVP Phase 1 の実装完了を記載
3. **Phase 2 タスク作成** - Stripe 連携等

---

## 📚 参考資料

- [設計仕様書](subscription_system_design.md)
- [既存 API パターン](../dashboard/routes/manage_routes.py)（実装の参考）
- [既存 DB パターン](../dashboard/migrations/024_create_accounting_tables.sql)（SQL の参考）
- [既存テストパターン](../tests/)（テストの参考）

---

## 👨‍💻 技術スタック確認

- **フレームワーク**: FastAPI（非同期対応）
- **ORM**: sqlite3 / aiosqlite
- **モデル**: Pydantic（BaseModel）
- **テスト**: pytest + BDD（Gherkin）
- **UI**: HTML/CSS + Chart.js

---

**ハンドオフ完了日**: 2026-04-30 07:30 JST  
**Tech Lead**: adachi-koichi  
**Status**: 🟢 Ready for Implementation

