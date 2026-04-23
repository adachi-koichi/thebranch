# Slack/Discord 統合セットアップガイド

## 概要

THEBRANCH ダッシュボードは Slack および Discord との統合機能を提供し、エージェント状態変更、タスク委譲、コスト警告、承認リクエスト、エラー、システムアラートなどの重要なイベント通知を Slack/Discord チャネルに自動配信できます。

## 事前準備

### Slack App の作成と設定

1. [Slack API ダッシュボード](https://api.slack.com/apps) にアクセス
2. 「Create New App」をクリック
3. 「From scratch」を選択
4. アプリ名（例：`THEBRANCH Notifications`）とワークスペースを指定して作成
5. 左メニューから「Event Subscriptions」を選択
6. 「Enable Events」をオンに設定
7. 「Request URL」に `https://your-domain/api/webhooks/slack` を入力（ドメインは本番環境に合わせて変更）
8. Slack からのチャレンジリクエストに自動応答
9. 「Subscribe to bot events」から必要なイベント（例：`message.channels`, `app_mention`）を追加
10. 「Signing Secret」をコピー（後でダッシュボードに設定）
11. 「OAuth & Permissions」から `chat:write` スコープを追加
12. ワークスペースに Slack App をインストール
13. 「Bot User OAuth Token」をコピー

### Discord App の作成と設定

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. 「New Application」をクリック
3. アプリ名（例：`THEBRANCH Bot`）を入力
4. 「Bot」タブから「Add Bot」をクリック
5. 左メニュー「General Information」から「Public Key」をコピー（署名検証用）
6. 「Interactions Endpoint URL」に `https://your-domain/api/webhooks/discord` を入力
7. URL が検証されたら保存
8. 「OAuth2」 → 「URL Generator」で以下スコープを選択：
   - `bot`
   - `applications.commands`
9. パーミッション：
   - `Send Messages`
   - `Send Messages in Threads`
10. 生成された URL でサーバーに Bot を招待

## ダッシュボード側の設定手順

### 1. ダッシュボードにログイン

ダッシュボードにアクセスして、管理者またはオーナー権限でログインします。

### 2. 統合設定タブを開く

1. ヘッダーメニューから 「設定」（⚙️）をクリック
2. 「統合設定」タブを選択

### 3. 新規統合を追加

1. 「新規追加」ボタンをクリック
2. 統合タイプを選択：
   - **Slack**: Slack ワークスペースへの通知
   - **Discord**: Discord サーバーへの通知

### 4. 設定情報を入力

以下の情報を入力してください：

#### Slack の場合
- **Webhook URL**: `https://hooks.slack.com/services/YOUR/WEBHOOK/URL`（Slack App の「Incoming Webhooks」から取得可能）
- **Signing Secret**: Slack App の Signing Secret
- **チャネル名**（オプション）: `#notifications` など（指定しない場合はデフォルトチャネルに送信）

#### Discord の場合
- **Webhook URL**: Discord チャネルから「Edit Channel」 → 「Webhooks」 → 「Create Webhook」で生成
- **Public Key**: Discord App の Public Key
- **チャネル名**（オプション）: チャネル ID または名前

### 5. 通知種別フィルタを設定

配信対象とする通知種別をチェックボックスで選択：
- エージェント状態変更（Agent Status）
- タスク委譲（Task Delegation）
- コスト警告（Cost Alert）
- 承認リクエスト（Approval Request）
- エラーイベント（Error Event）
- システムアラート（System Alert）

### 6. Webhook 接続を検証

「Webhook を検証」ボタンをクリックして、入力した URL と認証情報が正しいか確認します。

### 7. 設定を保存

「保存」ボタンをクリックして設定を完了します。

## 通知の確認方法

### ヘッダーの通知ベル

1. ダッシュボード上部右側の通知ベル（🔔）アイコンをクリック
2. 未読通知の一覧が表示されます
3. 未読バッジ（赤丸の数字）が未読件数を示します

### 通知パネルの操作

- **単一既読化**: 通知をクリック
- **全件既読化**: 「すべて既読にする」ボタン
- **フィルタ**: 通知種別や未読のみで絞り込み
- **削除**: 不要な通知を削除（確認後に推奨）

## API 仕様（概要）

### Webhook 受信エンドポイント

#### POST /api/webhooks/slack
Slack イベント受信。HMAC-SHA256 署名検証を実施。

```bash
curl -X POST http://localhost:8503/api/webhooks/slack \
  -H "Content-Type: application/json" \
  -H "X-Slack-Request-Timestamp: 1234567890" \
  -H "X-Slack-Signature: v0=..." \
  -d '{"type":"event_callback","event":{...}}'
```

#### POST /api/webhooks/discord
Discord Interaction 受信。Ed25519 署名検証を実施。

```bash
curl -X POST http://localhost:8503/api/webhooks/discord \
  -H "Content-Type: application/json" \
  -H "X-Signature-Ed25519: ..." \
  -H "X-Signature-Timestamp: ..." \
  -d '{"type":1,"challenge":"..."}'
```

### 統合設定 API

#### GET /api/integrations/configs
すべての統合設定を取得

```bash
curl http://localhost:8503/api/integrations/configs
```

#### POST /api/integrations/configs
新規統合設定を作成

```bash
curl -X POST http://localhost:8503/api/integrations/configs \
  -H "Content-Type: application/json" \
  -d '{
    "integration_type": "slack",
    "webhook_url": "https://hooks.slack.com/...",
    "webhook_secret": "your-secret",
    "notify_on_agent_status": true,
    "notify_on_task_delegation": true,
    "notify_on_cost_alert": true,
    "notify_on_approval_request": true,
    "notify_on_error_event": true,
    "notify_on_system_alert": true
  }'
```

#### GET /api/integrations/configs/{id}
特定の統合設定を取得

```bash
curl http://localhost:8503/api/integrations/configs/1
```

#### PUT /api/integrations/configs/{id}
統合設定を更新

```bash
curl -X PUT http://localhost:8503/api/integrations/configs/1 \
  -H "Content-Type: application/json" \
  -d '{"is_active": true, "notify_on_agent_status": false}'
```

#### DELETE /api/integrations/configs/{id}
統合設定を削除

```bash
curl -X DELETE http://localhost:8503/api/integrations/configs/1
```

#### POST /api/integrations/verify/{id}
Webhook URL 接続検証

```bash
curl -X POST http://localhost:8503/api/integrations/verify/1
```

## セキュリティ

### Secret のマスキング

API レスポンスでは `webhook_secret` が常にマスキング（`***REDACTED***`）されて返却されます。Secret の取得後は安全に保管し、決してネットワークで転送しないでください。

### Slack 署名検証

受信したリクエストの署名を以下の手順で検証：

1. タイムスタンプと本文から署名を計算：
   ```
   HMAC-SHA256(signing_secret, timestamp + ":" + body)
   ```
2. リクエストヘッダの `X-Slack-Signature` と比較
3. タイムスタンプが 5 分以内であることを確認

### Discord 署名検証

受信したリクエストの署名を Ed25519 で検証：

1. `X-Signature-Ed25519` ヘッダと `X-Signature-Timestamp` ヘッダを取得
2. タイムスタンプとボディから署名を検証
3. PyNaCl がインストールされていない環境では HMAC-SHA256 にフォールバック

## トラブルシューティング

### 署名検証失敗エラー

**現象**: `Invalid signature` または `Signature verification failed`

**原因と対策**:
1. Slack/Discord App の Signing Secret / Public Key が正しいか確認
2. API 設定で入力した Secret と App の Secret が一致しているか確認
3. ローカル環境の場合、`ngrok` などのトンネリングツール経由で確認

### タイムスタンプ超過エラー

**現象**: `Timestamp too old` または `Request timestamp is too old`

**原因と対策**:
1. サーバーの時刻が正確か確認
2. NTP（Network Time Protocol）同期が有効か確認
   ```bash
   date  # サーバー時刻を確認
   timedatectl status  # Linux の場合
   ```

### 通知が届かない

**チェックリスト**:
1. 統合設定の `is_active` が `true` か確認
2. 通知種別フィルタが正しく設定されているか確認
3. Webhook URL が正しいか、アクセス可能か確認
4. Slack/Discord の権限設定（Bot の権限など）を確認
5. ダッシュボードのログで通知送信エラーを確認

### Webhook URL 検証エラー

**現象**: `Webhook verification failed`

**対策**:
1. URL が正しい `https://` から始まるか確認
2. ファイアウォール / ロードバランサーの設定を確認
3. Slack/Discord への送信トラフィックが許可されているか確認

## 参考リンク

- [Slack API ドキュメント - リクエスト検証](https://api.slack.com/authentication/verifying-requests-from-slack)
- [Slack - Incoming Webhooks](https://api.slack.com/messaging/webhooks)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord 相互作用エンドポイント](https://discord.com/developers/docs/interactions/receiving-and-responding#security-and-authorization)
