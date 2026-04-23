# タスク #2532: オンボーディングフロー・チュートリアルUI実装

## 概要
初回ユーザーが部署をAIで作る体験ガイドを実装。ステップバイステップのウィザード形式で、新規ユーザーをTHEBRANCHへのオンボーディングから最初のAI部署作成まで案内する。

## 実装要件

### 1. オンボーディングウィザードUI（Step 1〜4）
- **Step 1**: ようこそ画面（ビジョン説明・開始ボタン）
- **Step 2**: 組織タイプ選択（スタートアップ/中小企業/個人）
- **Step 3**: 最初の部署選択（経理/法務/人事/開発）
- **Step 4**: AIエージェント起動確認・完了画面

### 2. データベース拡張
- `users` table に `onboarding_completed` boolean フラグを追加
- `onboarding_state` table を新規作成（step progress tracking）
  - user_id, current_step, organization_type, department_choice, created_at, updated_at

### 3. Flask API エンドポイント
- `GET /api/onboarding/status` — 現在のステップを取得
- `POST /api/onboarding/step` — ステップを進める（current_step を更新）
- `POST /api/onboarding/complete` — オンボーディング完了（onboarding_completed = True）
- `POST /api/onboarding/skip` — スキップ（完了フラグを付けてスキップ）

### 4. フロントエンド UI
- Wizard component（HTML/CSS/JS）
  - ステップごとのパネル表示
  - プログレスバー（1/4, 2/4, 3/4, 4/4）
  - Next/Back ボタン
  - Skip ボタン・後で実行ボタン
  - アニメーション・遷移効果

### 5. スキップ・後で実行機能
- スキップボタン：onboarding_completed = True（スキップ状態）で完了扱い
- 後で実行ボタン：current_step を保存して、セッション次回時に再開

## 実装フェーズ

### Phase 1: DB スキーマ拡張（マイグレーション）
- ファイル: `dashboard/migrations/024_extend_onboarding.sql`
- ALTER users ADD onboarding_completed BOOLEAN DEFAULT FALSE
- CREATE TABLE onboarding_state (...)

### Phase 2: Flask API 実装
- ファイル: `dashboard/app.py` に 4つの新規エンドポイントを追加
- 認証・セッション管理を確認
- JSON レスポンスで current_step, organization_type, department_choice を返す

### Phase 3: フロントエンド UI 実装
- ファイル: `dashboard/index.html` に Wizard component を追加
- CSS: `dashboard/styles/onboarding.css`（新規作成）
- JS: `dashboard/js/onboarding.js`（新規作成）
  - Step 1〜4 のパネル管理
  - API 連携（fetch）
  - ローカルストレージ で temporary state を保存

### Phase 4: テスト・動作確認
- Pytest で API エンドポイントをテスト
- curl で動作確認
- ブラウザ（localhost:5000）で UI フロー全体を確認

## 技術スタック

- **フロントエンド**: HTML/CSS/JavaScript
  - SPA (Single Page Application) 風の Wizard UI
  - Fetch API で Flask API と連携
  - LocalStorage で一時状態保存

- **バックエンド**: Python/Flask
  - RESTful API エンドポイント
  - SQLite ORM（SQLAlchemy）

- **データベース**: SQLite
  - onboarding_completed フラグ
  - onboarding_state table でプログレス追跡

## 開発プロセス

### ✅ Step 1: 設計確認（THIS PHASE）
- 本ドキュメントで実装方針を固める
- Pydantic models を models.py に追加

### ➡️ Step 2: DB マイグレーション実装
- migration ファイルを作成
- `python3 dashboard/migrate.py 024` で適用

### ➡️ Step 3: Flask API 実装
- app.py に 4つのエンドポイント追加
- POST/GET ハンドラー実装
- Error handling

### ➡️ Step 4: フロントエンド実装
- HTML パネル構造
- CSS スタイリング（Wizard风格）
- JavaScript ロジック（Step遷移・API呼び出し）

### ➡️ Step 5: 統合テスト・動作確認
- 手動テスト（ブラウザ）
- Pytest で API テスト
- curl で動作確認

### ➡️ Step 6: 本番デプロイ
- `python3 ~/.claude/skills/task-manager-sqlite/scripts/task.py done 2532`

## ファイル一覧

### 新規作成
- `dashboard/migrations/024_extend_onboarding.sql` — DB マイグレーション
- `dashboard/styles/onboarding.css` — Wizard UI スタイル
- `dashboard/js/onboarding.js` — Wizard ロジック

### 修正対象
- `dashboard/app.py` — 4つのエンドポイント追加
- `dashboard/models.py` — Pydantic models 追加（OnboardingStateCreate, OnboardingStateResponse など）
- `dashboard/index.html` — Wizard component HTML 追加

## 実装上の注意点

1. **認証**: `/api/onboarding/*` エンドポイントは認証が必須
2. **アイドル状態**: 長時間放置された場合の graceful な中断処理
3. **複数セッション**: 同じユーザーで複数タブ開かれた場合の state 同期
4. **モバイル対応**: responsive design でモバイル UX も確保

## 完了基準

- [ ] DB マイグレーション実行済み（onboarding_completed, onboarding_state）
- [ ] Flask API 4エンドポイント実装・テスト済み
- [ ] Wizard UI（Step 1〜4）フロントエンド実装済み
- [ ] プログレスバー表示
- [ ] スキップ・後で実行機能動作確認済み
- [ ] ブラウザで全フロー動作確認済み
- [ ] タスク完了コマンド実行済み
