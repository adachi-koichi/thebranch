# THEBRANCH プラットフォーム詳細設計ドキュメント

**作成日**: 2026-04-19  
**対象タスク**: #2204, #2205, #2206  
**ビジョン**: 翌朝から組織を持てる。部署ごとAIで動かす。ひとりがユニコーンになれる時代へ。

---

## 目次
1. [タスク #2204: オンボーディングフロー設計](#204-オンボーディングフロー設計)
2. [タスク #2205: AI部署設定UI設計](#205-ai部署設定ui設計)
3. [タスク #2206: 組織ダッシュボード設計](#206-組織ダッシュボード設計)
4. [共通データモデル](#共通データモデル)
5. [API仕様](#api仕様)

---

## #2204 オンボーディングフロー設計

### 1. ユースケース

```
[新規ユーザー]
  ↓
[1. ランディング/ウェルカムページ]
  ↓
[2. アカウント作成（メール or OAuth）]
  ↓
[3. プロフィール入力（名前・組織名・業種）]
  ↓
[4. メール認証]
  ↓
[5. AI部署テンプレート選択]
  ↓
[6. 部署メンバー初期設定]
  ↓
[7. ダッシュボード初回表示 + チュートリアル]
  ↓
[完了: AI部署が稼働開始]
```

**目標**: 5分以内にAI部署を稼働させる

### 2. 画面仕様

#### 2.1 ランディング/ウェルカムスクリーン
**URL**: `/`  
**目的**: プロダクトビジョンを伝え、ユーザーをアカウント作成へ導く

**要素**:
- ヒーロー画像/動画（「部署がAIで動く」イメージ）
- キャッチコピー: 「翌朝から組織を持てる」
- サブタイトル: 「採用でも外注でもなく、部署ごとAIで動かす。ひとりがユニコーンになれる時代へ。」
- メリット箇条書き（3-4項目）:
  - 数分で AI チーム編成完了
  - カスタマイズ可能な部署構成
  - リアルタイムタスク管理
- CTA ボタン: 「今すぐ始める」→ サインアップ
- サインイン リンク

**デザイン要件**:
- レスポンシブ（モバイル 100%, タブレット, PC対応）
- ダークモード対応（デフォルト: ライトモード）
- アクセシビリティ WCAG 2.1 AA 準拠

#### 2.2 アカウント作成フロー
**URL**: `/signup`  
**ステップ**: 3段階（ウィザード形式）

**ステップ 1: 認証方法選択**
- メールアドレス入力フィールド
  - バリデーション: RFC 5322 準拠, 既存メール確認
  - エラー表示: インラインで即座に
- OR
- OAuth ボタン:
  - Google ログイン
  - GitHub ログイン
  - Slack ログイン（オプション）

**ステップ 2: パスワード設定 / OAuth 確認**
- メール選択時: パスワード入力（強度チェック）
  - 最小8文字, 大文字・小文字・数字・記号を含む
  - リアルタイム強度表示ゲージ
- OAuth選択時: ユーザー情報自動入力確認画面

**ステップ 3: プロフィール入力**
- フルネーム（必須）
- 組織名（必須）
- 業種（ドロップダウン: IT, 金融, 医療, 流通, 製造, その他）
- 従業員数（推奨）
- 規約確認チェックボックス

**バリデーション**:
- 全フィールド入力後「次へ」ボタン有効化
- フィールド単位でリアルタイムバリデーション
- エラーは赤色で表示、エラーメッセージ 1 行日本語

**進捗表示**: ステップ 1/3, 2/3, 3/3（上部プログレスバー）

#### 2.3 メール認証画面
**URL**: `/verify-email`  
**トリガー**: メール認証メール送信後

**要素**:
- 説明: 「{email} に確認メールを送信しました。リンクをクリックして認証を完了してください」
- 認証コード入力（6桁）または メール内リンククリック
- 有効期限: 24時間
- 再送信リンク（60秒クールダウン）
- サポート連絡先

**バックエンド処理**:
- メール送信（SendGrid）
- 認証コード DB 保存（TTL 24h）
- クリック時の 確認処理

#### 2.4 AI部署テンプレート選択
**URL**: `/setup/department-template`  
**目的**: ユーザーのユースケースに合わせた初期部署構成を提供

**テンプレート選択肢** (カード形式):

| テンプレート | 構成 | 推奨用途 |
|---|---|---|
| **ソフトウェアエンジニアリング部署** | Tech Lead × 1, Engineer × 2, QA × 1 | プロダクト開発・バックエンド開発 |
| **デザイン・UX部署** | Designer × 2, Researcher × 1 | UI/UX設計・デザインシステム |
| **営業・マーケティング部署** | Sales × 2, Marketer × 1 | リード生成・キャンペーン管理 |
| **カスタム構成** | 空白から選択開始 | 自由構成 |

**各カードの要素**:
- テンプレート名
- メンバー構成アイコン表示
- 説明（1行）
- 「このテンプレートを使用」ボタン

**UI インタラクション**:
- ホバー時: カード拡大, 詳細表示
- 選択後: スピンナー表示 → 次ステップへ

#### 2.5 部署メンバー初期設定
**URL**: `/setup/members`  
**前提**: テンプレート選択済み

**要素**:
- テンプレートに基づくメンバー一覧（テーブル形式）
  - 役職 (Engineer, Designer, 等)
  - エージェント名 (デフォルト: "Engineer #1", "Engineer #2", など)
  - 説明フィールド（カスタマイズ可能）
  - 削除ボタン（テンプレート最小数は削除不可）
- メンバー追加ボタン
  - 役職選択ドロップダウン
  - 動的に行追加
- キャンセル / 完了ボタン

**バリデーション**:
- 最小メンバー数: テンプレート定義値以上
- 最大メンバー数: 10人（後で増加可能）
- エージェント名: 1-50文字, 英数・記号

#### 2.6 ダッシュボード初回表示 + チュートリアル
**URL**: `/dashboard`  
**トリガー**: オンボーディング完了後

**画面レイアウト**:
```
┌─────────────────────────────────────────────┐
│ 🎉 Welcome, {ユーザー名}!                    │
│ あなたの AI 部署 "{部署名}" が稼働開始しました │
└─────────────────────────────────────────────┘

┌──────────────────┬──────────────────┐
│ 📊 概要           │ 🚀 次のステップ    │
│ - タスク数: 0     │ 1. メンバー設定   │
│ - 稼働中: 0       │ 2. タスク作成     │
│ - 完了: 0         │ 3. 統合サービス   │
└──────────────────┴──────────────────┘

┌──────────────────────────────┐
│ 📚 チュートリアル（オーバーレイ）  │
│ [1/5] メンバー管理の使い方     │
│ [スキップ] [次へ]             │
└──────────────────────────────┘
```

**チュートリアルステップ** (5ステップ):
1. メンバー管理パネルへのアクセス方法
2. タスク作成方法
3. リアルタイム進捗確認
4. 外部サービス連携（Slack 等）
5. サポート・ドキュメント

**チュートリアル要件**:
- スキップ可能
- 後で再度表示可能（ヘルプメニュー）
- 各ステップ 15-30秒で読める量

### 3. 技術要件

**フロントエンド**:
- Framework: Next.js 14+ (App Router)
- UI: React 18+
- スタイル: Tailwind CSS / Shadcn UI
- フォーム: React Hook Form + Zod (バリデーション)
- 状態管理: Zustand / Redux Toolkit
- 認証: NextAuth.js

**バックエンド**:
- Framework: FastAPI / Python 3.10+
- ORM: SQLAlchemy / Tortoise ORM
- DB: SQLite (開発) / PostgreSQL (本番)
- メール: SendGrid / Resend
- OAuth: python-dotenv, authlib

**セキュリティ**:
- HTTPS のみ
- CSRF トークン検証
- Rate limiting (5 req/min per IP for signup)
- Password hashing: bcrypt (rounds=12)
- JWT トークン (access: 15min, refresh: 7days)

**デプロイ**:
- フロントエンド: Vercel
- バックエンド: Docker + AWS ECS / Heroku

### 4. データ保存・セッション管理

**セッション フロー**:
```
[1. メール送信/認証]
  └→ DB: users テーブル作成 (pending 状態)
       - email, hashed_password, created_at

[2. メール認証完了]
  └→ DB: users テーブル更新 (verified = true)
       - email_verified_at タイムスタンプ

[3. プロフィール入力]
  └→ DB: users テーブル更新
       - full_name, organization_name, industry

[4. テンプレート選択]
  └→ DB: departments テーブル作成
       - department_id, user_id, template_id, created_at

[5. メンバー設定]
  └→ DB: agents テーブル作成 (複数レコード)
       - agent_id, department_id, role, name, description

[6. ログイン]
  └→ JWT トークン発行
       - access_token: 署名付きJWT
       - refresh_token: DB 保存
```

**JWT ペイロード例**:
```json
{
  "sub": "user_id_12345",
  "email": "user@example.com",
  "org": "organization_name",
  "dept_id": "dept_id_67890",
  "iat": 1234567890,
  "exp": 1234569690
}
```

### 5. エラーハンドリング

| シナリオ | 表示メッセージ | ステータスコード |
|---|---|---|
| メールアドレス既に登録済み | このメールアドレスは既に登録されています。ログインしてください。 | 409 Conflict |
| パスワード不足 | パスワードは8文字以上で、大文字・小文字・数字・記号を含む必要があります。 | 400 Bad Request |
| メール認証タイムアウト | 確認コードの有効期限が切れました。再送信してください。 | 401 Unauthorized |
| サーバーエラー | 予期しないエラーが発生しました。サポートに連絡してください。 | 500 Server Error |

---

## #2205 AI部署設定UI設計

### 1. ユースケース

```
[ユーザー]
  ↓
[ダッシュボード → 部署設定ボタン]
  ↓
[設定パネル開表示]
  ├→ [1. メンバー管理]
  ├→ [2. 部署プロファイル]
  ├→ [3. スキル・専門領域]
  └→ [4. 権限・アクセス制御]
  ↓
[変更を保存]
  ↓
[部署設定更新完了]
```

### 2. UI レイアウト

**メインナビゲーション**:
```
┌──────────────────────────────────────────────┐
│ 🏢 {部署名} 設定                              │
├──────────────────────────────────────────────┤
│ ◀ 戻る                                      │
└──────────────────────────────────────────────┘

┌───────────────┬──────────────────────────────┐
│ 📋 タブ        │ 📄 コンテンツ                 │
├───────────────┼──────────────────────────────┤
│ ・メンバー      │ メンバー一覧 (テーブル)      │
│ ・プロファイル  │ ... (アクティブタブ)         │
│ ・スキル        │                             │
│ ・権限          │                             │
└───────────────┴──────────────────────────────┘
```

#### 2.1 メンバー管理タブ

**レイアウト**:
```
┌─────────────────────────────────┐
│ メンバー管理                     │
├─────────────────────────────────┤
│ [+ メンバーを追加]               │
├─────────────────────────────────┤
│ テーブル:
│ ┌──────┬──────┬──────┬──────┐
│ │名前   │役職  │ステータス│アクション│
│ ├──────┼──────┼──────┼──────┤
│ │Eng #1│Engineer│🟢Active│編集 削除 │
│ │Eng #2│Engineer│🟢Active│編集 削除 │
│ │QA #1 │QA    │🔴Idle │編集 削除 │
│ └──────┴──────┴──────┴──────┘
└─────────────────────────────────┘
```

**機能仕様**:

| 機能 | 詳細 |
|---|---|
| **メンバー追加** | モーダル開表示 → 役職選択 → 名前入力 → 説明追加（オプション） |
| **メンバー編集** | インライン編集 or モーダル → 名前・役職・権限変更 |
| **ステータス** | 🟢Active (最近使用), 🟡Idle (7日未使用), 🔴Archived |
| **削除** | 確認ダイアログ表示 → 論理削除（30日間復旧可能） |
| **権限編集** | タスク閲覧, タスク作成, 承認権限（チェックボックス） |

**バリデーション**:
- メンバー名: 1-50文字
- 最小メンバー数: 1（削除不可）
- 最大メンバー数: 20

**モーダル: メンバー追加/編集**
```
┌──────────────────────────────┐
│ ✏️ メンバー編集                │
├──────────────────────────────┤
│ 名前 *                       │
│ [入力フィールド]             │
│                             │
│ 役職 *                       │
│ [ドロップダウン▼]             │
│ - Engineer                 │
│ - Designer                 │
│ - Manager                  │
│ - QA                       │
│                             │
│ 説明                         │
│ [テキストエリア]             │
│                             │
│ 権限設定:                    │
│ ☑ タスク閲覧                 │
│ ☑ タスク作成                 │
│ ☐ 承認権限                   │
│                             │
│ [キャンセル] [保存]          │
└──────────────────────────────┘
```

#### 2.2 部署プロファイルタブ

**フォーム要素**:

| 項目 | タイプ | 必須 | 詳細 |
|---|---|---|---|
| 部署名 | テキスト | ○ | 1-50文字 |
| 説明 | テキストエリア | | 最大 500文字 |
| アイコン | 画像アップロード | | JPG/PNG, 最大 2MB, 500x500px |
| カラーテーマ | カラーピッカー | | デフォルト: ブルー |
| 最大同時タスク数 | 数値 | | 1-100, デフォルト: 10 |
| 平均応答時間(SLA) | ドロップダウン | | 5分, 15分, 30分, 1時間, 等 |

**統合サービス設定**:

```
├─ Slack 連携
│  ├─ 接続 / 解除
│  └─ 通知設定（タスク開始, 完了, エラー）
├─ Discord 連携
│  ├─ 接続 / 解除
│  └─ チャンネル選択
└─ メール通知
   ├─ ON/OFF
   └─ 通知タイミング（毎日/毎週/カスタム）
```

**バリデーション & エラーメッセージ**:
- 部署名が空: 「部署名は必須です」
- アイコンサイズ超過: 「2MB以下のファイルを選択してください」
- 保存成功: トースト通知「部署設定を更新しました」

#### 2.3 スキル・専門領域タブ

**セクション構成**:

```
1. 技術スタック
   └─ タグ入力フィールド
      (言語: Python, JavaScript, Java, 等)
      (フレームワーク: Django, Next.js, Spring, 等)

2. ドメインナレッジ
   └─ テキストエリア or リスト
      (業界: IT, 金融, 医療, 等)
      (プロセス: アジャイル, ウォーターフォール, 等)

3. ドキュメント統合
   └─ ファイルアップロード or URL 指定
      (Confluence, Notion, GitHub Wiki, 等)
      (最大 10 ファイル / リンク)

4. カスタムプロンプト (オプション)
   └─ テキストエリア
      部署メンバーへの追加指示・コンテキスト
```

**UI イメージ**:
```
┌─────────────────────────┐
│ 技術スタック            │
│ [Python] [JavaScript]   │
│ [新規追加▼]             │
│                         │
│ ドメインナレッジ        │
│ ☑ アジャイル開発        │
│ ☑ マイクロサービス      │
│ ☐ クラウドネイティブ    │
│                         │
│ ドキュメント統合        │
│ [📎 ファイルを追加]     │
│                         │
│ カスタムプロンプト      │
│ [━━━━━━━━━━━━━]        │
│ 「この部署は...」       │
│                         │
│ [保存]                  │
└─────────────────────────┘
```

#### 2.4 権限・アクセス制御タブ

**セクション 1: ロール別権限マトリックス**

```
┌────────┬────┬────┬────┬──────┐
│        │見る│作成│編集│削除  │
├────────┼────┼────┼────┼──────┤
│Manager │ ○  │ ○  │ ○  │ ○   │
│Engineer│ ○  │ ○  │ ○  │ ×   │
│Designer│ ○  │ ○  │ ○  │ ×   │
│Viewer │ ○  │ ×  │ ×  │ ×   │
└────────┴────┴────┴────┴──────┘
```

**セクション 2: 承認フロー設定**

```
カスタム承認フロー:
1️⃣ タスク作成 → [Engineer が実行]
2️⃣ 承認申請 → [Manager が確認]
3️⃣ 実行決定 → [Engineer が実装]
4️⃣ 完了報告 → [Manager が確認]

[+ フロー追加]
```

**セクション 3: 監査ログ**

```
ログ一覧（タイムスタンプ降順）:
┌───────────────────────────────┐
│ 2026-04-19 12:30 Engineer #1  │
│ → タスク #123 を完了          │
│                               │
│ 2026-04-19 11:15 Manager      │
│ → メンバー追加: Eng #3        │
│                               │
│ 2026-04-19 10:00 設定         │
│ → 部署名を変更                │
└───────────────────────────────┘

[すべてのログを見る] → ページング
```

### 3. 技術要件

**フロントエンド コンポーネント**:
- Tabs (メンバー/プロファイル/スキル/権限)
- Modal (メンバー追加/編集)
- Table (メンバー一覧)
- Form Controls (テキスト, 数値, ドロップダウン, チェックボックス)
- ColorPicker
- FileUpload
- TagInput
- DateRangePicker (ログ絞り込み)

**バックエンド API**:
- `GET /api/departments/{dept_id}` - 部署情報取得
- `PUT /api/departments/{dept_id}` - 部署情報更新
- `GET /api/departments/{dept_id}/members` - メンバー一覧
- `POST /api/departments/{dept_id}/members` - メンバー追加
- `PUT /api/departments/{dept_id}/members/{member_id}` - メンバー更新
- `DELETE /api/departments/{dept_id}/members/{member_id}` - メンバー削除
- `GET /api/departments/{dept_id}/audit-log` - 監査ログ取得

**データベース**:
- `departments` テーブル (name, description, icon_url, color_theme, max_concurrent_tasks, sla_minutes)
- `agents` テーブル (agent_id, department_id, name, role, description, skills, status)
- `agent_permissions` テーブル (agent_id, can_view_tasks, can_create_tasks, can_edit_tasks, can_delete_tasks, can_approve)
- `audit_logs` テーブル (timestamp, agent_id, action, resource_type, resource_id, details)

### 4. バリデーション・エラーハンドリング

| シナリオ | エラーメッセージ |
|---|---|
| 部署名が空 | 「部署名は必須です」 |
| アイコンファイルが大きすぎる | 「ファイルは 2MB 以下である必要があります」 |
| メンバー数が最大を超える | 「最大 20 メンバーまで追加できます」 |
| 保存中のネットワークエラー | 「保存に失敗しました。もう一度試してください」 |

---

## #2206 組織ダッシュボード設計

### 1. ユースケース

```
[組織リーダー]
  ↓
[ダッシュボードへアクセス]
  ↓
┌─ [1. 概観パネル] - タスク全体数・進捗
├─ [2. リソース利用状況] - アクティブエージェント
├─ [3. タスクボード] - Kanban 形式でステータス可視化
├─ [4. リスク検出] - 滞留・ブロッカー
├─ [5. アナリティクス] - 部署別トレンド
└─ [6. ドリルダウン] - 部署・タスク詳細
  ↓
[意思決定・最適化の実施]
```

### 2. ダッシュボード全体レイアウト

```
┌─────────────────────────────────────────────────────────────┐
│ 🏢 組織ダッシュボード  |  🔔 通知  🔧 設定  👤 プロフィール   │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 📊 Overview パネル                                            │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────┬──────────┬──────────┬──────────┐               │
│ │ 📌 進行中 │ ✅ 完了  │ ⏸️ 保留 │ ❌ 失敗  │               │
│ │ 12 タスク│ 45 タスク│ 3 タスク │ 1 タスク │               │
│ └──────────┴──────────┴──────────┴──────────┘               │
│                                                              │
│ 本週完了: 15 タスク / 目標 20 タスク (75% ✓)                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 🚨 リソース利用状況                                            │
├──────────────────────────────────────────────────────────────┤
│ アクティブエージェント: 8 / 20                                 │
│ [████████░░░░░░░░░░]                                         │
│                                                              │
│ 同時処理数: 18 / 30  (60% 利用)                              │
│ [██████░░░░]                                                 │
│                                                              │
│ リソース枯渇警告: なし ✓                                      │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 📋 Kanban ボード                                             │
├──────────────────────────────────────────────────────────────┤
│  Pending (5) │ In Progress (12) │ Blocked (2) │ Done (45)    │
│ ┌──────────┐ ┌──────────────┐  ┌──────────┐ ┌────────────┐ │
│ │[Task #1] │ │[Task #8]     │  │[Task #2] │ │[Task #10]  │ │
│ │Eng. Task │ │Design Rev    │  │Waiting   │ │Completed   │ │
│ │[P1]      │ │[P2]          │  │[P1]⚠️    │ │[✓]         │ │
│ │Eng #1    │ │Design #2     │  │Eng #1    │ │Design #1   │ │
│ └──────────┘ └──────────────┘  └──────────┘ └────────────┘ │
│ ┌──────────┐ ...                                            │
│ │[Task #3] │                                                │
│ │...       │                                                │
│ └──────────┘                                                │
│                                                              │
│ ドラッグ&ドロップでステータス変更可能                          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 🚨 リスク・ボトルネック                                        │
├──────────────────────────────────────────────────────────────┤
│ ⚠️ 滞留タスク:
│   • Task #12 (42分, In Progress) - Eng #1
│   • Task #15 (38分, Pending) - 割り当て待ち
│
│ 🔴 ブロッカー:
│   • Task #2 (Blocked by #8) - 承認待ち
│   • Task #5 (Blocked by API服) - 外部待ち
│
│ 📈 完了率低下:
│   • Design 部署: 60% (前週 80%)
│
│ [詳細を見る]
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 📊 アナリティクス (本週 & 月間トレンド)                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ 部署別完了数 (縦棒グラフ):                                    │
│  25 ┤                                                        │
│  20 ┤    ██                                                 │
│  15 ┤ ██ ██ ██                                              │
│  10 ┤ ██ ██ ██ ██                                           │
│   5 ┤ ██ ██ ██ ██ ██                                        │
│   0 ┤ ━━ ━━ ━━ ━━ ━━                                        │
│       Eng Des Ops SRE QA                                   │
│                                                              │
│ 平均処理時間トレンド (折れ線グラフ):                          │
│ 45min ─◆─ ◆ ─ ◆                                             │
│ 40min ─┴─◆─┴◆                                              │
│ 35min ───┴───                                              │
│        W1  W2  W3  W4                                       │
│                                                              │
│ エラー率: 2.3% (前月 3.1%) ✓                                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 🔗 ナビゲーション / ドリルダウン                                │
├──────────────────────────────────────────────────────────────┤
│ [部署別詳細] [タスク詳細] [メンバー別成績] [期間選択]         │
└──────────────────────────────────────────────────────────────┘
```

### 3. 各セクションの詳細仕様

#### 3.1 Overview パネル

**カード要素** (4列):

| カード | 表示内容 | インタラクション |
|---|---|---|
| **進行中** | 🔵 In Progress のタスク数 | クリック → Kanban でフィルタ |
| **完了** | ✅ Done のタスク数 | クリック → Done のみ表示 |
| **保留中** | ⏸️ Blocked のタスク数 | クリック → Blocked のみ表示 |
| **失敗** | ❌ Failed のタスク数 | クリック → Failed のみ表示 |

**進捗率インジケータ**:
```
本週目標: 20 タスク
完了: 15 タスク
進度: ████████░░ (75%)
```

**タイムスタンプ**: 「最終更新: 2分前」

#### 3.2 リソース利用状況

**プログレスバー表示**:
```
アクティブエージェント
━━━━━━━━━■■□□□□□□░░░
8 / 20 (40%)

同時処理タスク数
━━━━━━━━━━━━━━□░░░░░
28 / 30 (93% - 注意⚠️)

CPU 使用率
━━━━━━━■░░░░░░░░░░
62% (正常)

メモリ使用率
━━━━━━━━■░░░░░░░░
71% (正常)
```

**警告レベル**:
- 🟢 Green: 0-70%
- 🟡 Yellow: 70-85%
- 🔴 Red: 85-100%

**リソース枯渇警告** (例):
- 赤色バナー: 「⚠️ 同時処理数が 90% に達しました。新規タスク割り当てを控えてください。」

#### 3.3 Kanban ボード

**列構成**: Pending → In Progress → Blocked → Done

**カード情報**:
```
┌─────────────────┐
│ Task #123       │
│ 設計: API仕様   │
│ [P1] ⭐⭐       │
│ Eng #1          │
│ ━━━━━━━━━━━━  │ (進捗 60%)
│ 🕐 12m          │
└─────────────────┘
```

- **タイトル**: タスク番号 + タスク名
- **優先度**: P1 (赤), P2 (黄), P3 (灰色)
- **担当部署**: アイコン or 名前
- **進捗バー**: 0-100%
- **経過時間**: 現在の滞留時間 (赤表示 if > 30min)

**インタラクション**:
- **ドラッグ&ドロップ**: タスクを列間で移動 → ステータス変更
- **ホバー**: タスク詳細のプレビュー表示
- **クリック**: タスク詳細ページへ遷移

**フィルタリング**:
- 部署で絞り込み（マルチセレクト）
- 優先度で絞り込み
- 検索ボックス (タスク名・ID)

#### 3.4 リスク・ボトルネック

**滞留タスク検出**:
```
⚠️ 注意（30-60分）:
  • Task #12 (42分) - Eng #1 - 実装中
  
🔴 緊急（60分+）:
  • Task #15 (95分) - 割り当て待ち - [サポートが必要]
```

**ブロッカー分析**:
```
🔗 Task #2 is blocked by:
   ↓
   Task #8 (PR レビュー待ち - Design #1)

🔗 Task #5 is blocked by:
   ↓
   外部 API (Stripe) - レスポンス待ち
   推定完了: 12:30 (あと 30分)
```

**エラー率・失敗**:
```
失敗したタスク: 1 件 (Task #99)
エラー内容: "API connection timeout"
リトライ状況: 自動リトライ 3 回済み
手動対応: [手動リトライ] [キャンセル]
```

#### 3.5 アナリティクス

**セクション 1: 部署別完了率** (棒グラフ)
```
グラフ: X軸 = 部署名, Y軸 = 完了数 (本週)

Engineering: 45 ✓
Design: 22 ✓
Operations: 18
Sales: 8
```

**セクション 2: 平均処理時間トレンド** (折れ線グラフ)
```
グラフ: X軸 = 週, Y軸 = 時間(分)

W1 (先月): 48分
W2: 42分 ✓ (改善)
W3: 45分
W4 (今週): 38分 ✓ (改善傾向)
```

**セクション 3: メトリクス詳細**
```
タスク完了率:        95.6% ✓
エラー率:            2.1%
平均リードタイム:     2.3日
アクティブ部署数:     5/8
```

**期間選択**: ドロップダウン (過去7日, 過去30日, カスタム範囲)

#### 3.6 ナビゲーション・ドリルダウン

**サブメニュー**:
```
[部署別詳細表示]
  └→ 各部署の詳細ダッシュボード（独立ページ）

[タスク詳細]
  └→ タスク #XXX の詳細ページ

[メンバー別成績]
  └→ 各エージェントの統計・パフォーマンス

[期間選択]
  └→ カレンダーピッカー (from-to date)

[レポートをエクスポート]
  └→ PDF / CSV ダウンロード
```

### 4. 技術要件

**フロントエンド**:
- Chart.js / D3.js (グラフ表示)
- React Beautiful DnD (ドラッグ&ドロップ)
- React Query / SWR (リアルタイム更新)
- WebSocket (push notifications)
- Tailwind CSS + Shadcn UI

**バックエンド API**:
- `GET /api/dashboard/overview` - 概観パネルデータ
- `GET /api/dashboard/resources` - リソース利用状況
- `GET /api/dashboard/tasks` - Kanban ボードデータ
- `GET /api/dashboard/risks` - リスク検出データ
- `GET /api/dashboard/analytics` - アナリティクスデータ
- `POST /api/tasks/{task_id}/status` - タスクステータス更新
- `GET /api/departments/{dept_id}/dashboard` - 部署別ダッシュボード

**データベース最適化**:
- `tasks` テーブルに複合インデックス (status, created_at)
- キャッシュレイヤー (Redis): アナリティクス集計結果 (TTL 5分)
- タイムシリーズデータベース (InfluxDB): メトリクス履歴

**リアルタイム更新**:
- WebSocket サーバー (Socket.IO)
- 以下のイベントをブロードキャスト:
  - Task status changed
  - New task created
  - Resource metrics updated
  - Risk detected

---

## 共通データモデル

### ユーザー・組織モデル

```sql
-- Users テーブル
CREATE TABLE users (
  user_id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  full_name VARCHAR(255) NOT NULL,
  hashed_password VARCHAR(255),
  profile_image_url VARCHAR(2048),
  organization_name VARCHAR(255) NOT NULL,
  industry VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP
);

-- Departments テーブル
CREATE TABLE departments (
  department_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(user_id),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  icon_url VARCHAR(2048),
  color_theme VARCHAR(50),
  max_concurrent_tasks INT DEFAULT 10,
  sla_minutes INT DEFAULT 30,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP
);

-- Agents テーブル
CREATE TABLE agents (
  agent_id UUID PRIMARY KEY,
  department_id UUID NOT NULL REFERENCES departments(department_id),
  name VARCHAR(255) NOT NULL,
  role VARCHAR(50) NOT NULL, -- Engineer, Designer, Manager, etc
  description TEXT,
  status VARCHAR(50) DEFAULT 'active', -- active, idle, archived
  skills TEXT, -- JSON array
  prompt TEXT, -- Custom system prompt
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent Permissions テーブル
CREATE TABLE agent_permissions (
  permission_id UUID PRIMARY KEY,
  agent_id UUID NOT NULL REFERENCES agents(agent_id),
  can_view_tasks BOOLEAN DEFAULT true,
  can_create_tasks BOOLEAN DEFAULT true,
  can_edit_tasks BOOLEAN DEFAULT true,
  can_delete_tasks BOOLEAN DEFAULT false,
  can_approve_tasks BOOLEAN DEFAULT false
);
```

### タスク・ワークフロー モデル

```sql
-- Tasks テーブル
CREATE TABLE tasks (
  task_id UUID PRIMARY KEY,
  department_id UUID NOT NULL REFERENCES departments(department_id),
  title VARCHAR(255) NOT NULL,
  description TEXT,
  priority INT DEFAULT 2, -- 1=P1, 2=P2, 3=P3
  status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, blocked, done, failed
  assigned_agent_id UUID REFERENCES agents(agent_id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  blocked_by_task_id UUID REFERENCES tasks(task_id),
  progress_percentage INT DEFAULT 0,
  error_message TEXT,
  metadata JSON, -- Custom fields
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP
);

-- Task Audit Log テーブル
CREATE TABLE task_audit_logs (
  log_id UUID PRIMARY KEY,
  task_id UUID NOT NULL REFERENCES tasks(task_id),
  agent_id UUID REFERENCES agents(agent_id),
  action VARCHAR(50) NOT NULL, -- created, started, updated, completed, failed
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  details JSON
);
```

---

## API 仕様

### 認証関連

#### POST /api/auth/signup
**リクエスト**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe",
  "organization_name": "My Company",
  "industry": "IT"
}
```

**レスポンス** (201 Created):
```json
{
  "user_id": "uuid-123",
  "email": "user@example.com",
  "message": "確認メールを送信しました"
}
```

#### POST /api/auth/verify-email
**リクエスト**:
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```

**レスポンス** (200 OK):
```json
{
  "access_token": "jwt-token-here",
  "refresh_token": "refresh-jwt-here",
  "user_id": "uuid-123"
}
```

### 部署管理

#### GET /api/departments/{dept_id}
**レスポンス**:
```json
{
  "department_id": "uuid-456",
  "name": "Engineering",
  "description": "...",
  "icon_url": "...",
  "color_theme": "blue",
  "max_concurrent_tasks": 10,
  "sla_minutes": 30,
  "members_count": 5,
  "active_tasks": 3,
  "completed_tasks_today": 7
}
```

#### PUT /api/departments/{dept_id}
**リクエスト**:
```json
{
  "name": "Engineering Team",
  "description": "...",
  "max_concurrent_tasks": 15,
  "sla_minutes": 45
}
```

#### POST /api/departments/{dept_id}/members
**リクエスト**:
```json
{
  "name": "Engineer #1",
  "role": "Engineer",
  "description": "Senior Backend Engineer",
  "skills": ["Python", "FastAPI", "PostgreSQL"]
}
```

### ダッシュボード API

#### GET /api/dashboard/overview
**レスポンス**:
```json
{
  "pending_count": 5,
  "in_progress_count": 12,
  "blocked_count": 2,
  "done_count": 45,
  "weekly_goal": 20,
  "weekly_completed": 15,
  "last_updated": "2026-04-19T12:30:00Z"
}
```

#### GET /api/dashboard/tasks?status=in_progress
**レスポンス**:
```json
{
  "tasks": [
    {
      "task_id": "uuid-789",
      "title": "API Specification",
      "priority": 1,
      "status": "in_progress",
      "assigned_agent": "Engineer #1",
      "progress": 60,
      "elapsed_minutes": 42,
      "blocked_by": null
    },
    ...
  ]
}
```

#### GET /api/dashboard/risks
**レスポンス**:
```json
{
  "long_running_tasks": [
    {
      "task_id": "uuid-999",
      "title": "Task Title",
      "elapsed_minutes": 95,
      "severity": "critical"
    }
  ],
  "blockers": [
    {
      "task_id": "uuid-111",
      "blocked_by_task_id": "uuid-222",
      "reason": "PR review pending"
    }
  ]
}
```

---

## 実装ロードマップ

### Phase 1: MVP (2-3週間)
- ✅ オンボーディングフロー (簡易版)
- ✅ 部署管理パネル (メンバー管理のみ)
- ✅ ダッシュボード (Overview + Kanban)
- ✅ 基本認証 (メール/パスワード)

### Phase 2: 拡張機能 (3-4週間)
- OAuth 統合 (Google, GitHub)
- 外部サービス連携 (Slack, Discord)
- リスク検出・アラート
- アナリティクス・レポート

### Phase 3: 最適化 (2週間)
- パフォーマンス最適化 (キャッシング, インデックス)
- セキュリティ監査
- UX改善・ユーザーテスト
- ドキュメント完成

---

**この詳細設計に基づき、EM チームが実装を開始できます。** 不明点や追加要件があれば、このドキュメントを随時更新してください。
