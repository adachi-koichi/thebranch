Feature: Agent Messaging Webhook System
  Comprehensive QA testing for Task completion event webhooks and Agent Messaging notifications

  Background:
    Given Webhook system is initialized
    And test database is available
    And Bearer token authentication is configured

  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Scenario 1: Webhook Registration
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Scenario: Webhook を正常に登録できる
    Given 有効な Webhook URL が準備されている
    And Bearer token がリクエストヘッダに含まれている
    When POST /api/webhooks/register で以下のペイロードを送信
      """
      {
        "name": "test-webhook",
        "event_type": "task.completed",
        "target_url": "https://webhook.site/test-uuid-001",
        "auth_type": "bearer",
        "secret_key": "test-secret-key-12345",
        "is_active": true,
        "retry_policy": {
          "max_retries": 3,
          "retry_backoff_ms": 1000,
          "timeout_ms": 5000
        }
      }
      """
    Then ステータスコード 201 が返却される
    And response に以下のフィールドが含まれている
      | webhook_id |
      | name |
      | event_type |
      | target_url |
      | is_active |
      | created_at |
    And response.webhook_id は "wh_" プレフィックスを持つ
    And webhook_subscriptions テーブルに新規レコードが挿入されている
    And secret_key_hash は bcrypt でハッシュ化されている


  Scenario: 無効な Webhook URL で登録失敗
    Given 無効な URL フォーマットが提供されている
    And Bearer token がリクエストヘッダに含まれている
    When POST /api/webhooks/register で以下のペイロードを送信
      """
      {
        "name": "invalid-webhook",
        "event_type": "task.completed",
        "target_url": "not-a-valid-url",
        "auth_type": "bearer",
        "secret_key": "test-secret"
      }
      """
    Then ステータスコード 400 が返却される
    And response.detail に "Invalid target URL format" が含まれている


  Scenario: 既存 Webhook 重複登録で失敗
    Given Webhook が既に登録されている
    And 同じ target_url, user_id で別の Webhook 登録を試みる
    When POST /api/webhooks/register で既存 Webhook と同じ target_url を送信
    Then ステータスコード 201 または 409 が返却される
    And 重複チェック ロジック がログに記録されている


  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Scenario 2: Task Completion Event Detection
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Scenario: Task 完了時に Webhook トリガーイベントが発火する
    Given Task が tasks テーブルに存在する
    And Webhook が task.completed イベント で登録されている
    When Task ステータスが "completed" に更新される
    Then task_completion_events テーブルに新規イベントが作成される
    And イベント status は "triggered" で初期化される
    And イベント event_status は "triggered" で設定される
    And created_at, triggered_at がタイムスタンプされている


  Scenario: イベントペイロードに正しいデータが含まれている
    Given Task completion event が生成されている
    When イベント ペイロードを確認する
    Then ペイロードに以下のフィールドが含まれている
      | event_id |
      | task_id |
      | workflow_id |
      | team_name |
      | executor_user_id |
      | executor_username |
      | executor_role |
      | status |
      | priority |
      | completion_time_ms |
      | created_at |
      | triggered_at |
    And executor_role は ('ai-engineer', 'pm', 'em', 'admin') のいずれか
    And priority は 1-5 の範囲内
    And すべてのフィールドが NULL でない（nullable フィールド除外）


  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Scenario 3: Webhook Delivery Success
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Scenario: Webhook エンドポイントに POST リクエストが送信される
    Given task_completion_event が準備されている
    And Webhook subscription が active 状態である
    And webhook_delivery_logs テーブルが空である
    When Webhook delivery process が実行される
    Then Webhook target_url に POST リクエストが送信される
    And リクエスト Headers に Authorization がある
    And リクエスト Body が JSON フォーマット
    And webhook_delivery_logs テーブルに delivery レコードが作成される
    And delivery_status は "pending" で初期化される


  Scenario: Response code 200 で配信成功と判定
    Given Webhook endpoint が 200 OK で応答する Mock が準備されている
    When Webhook POST リクエストが実行される
    Then ステータスコード 200 が受け取られる
    And webhook_subscriptions の trigger_count がインクリメントされる
    And webhook_subscriptions の success_count がインクリメントされる
    And webhook_subscriptions の last_triggered_at が更新される
    And webhook_delivery_logs の delivery_status は "sent" に更新される
    And webhook_delivery_logs の http_status_code は 200 に設定される
    And webhook_delivery_logs の sent_at がタイムスタンプされる
    And task_completion_events の event_status は "dispatched" に更新される


  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Scenario 4: Webhook Delivery Failure & Retry
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Scenario: 配信失敗時 5xx エラーで 3 回までリトライ
    Given Webhook endpoint が以下の順序で応答する
      | Attempt | Status Code | Error Message |
      | 1       | 503         | Service Unavailable |
      | 2       | 502         | Bad Gateway |
      | 3       | 200         | Success (final) |
    When Webhook delivery が実行される
    Then 1 回目の配信が失敗（503）
    And webhook_delivery_logs に attempt_number=1, delivery_status="failed" が記録される
    And next_retry_at が計算され記録される
    And リトライ待機時間が retry_backoff_ms に従う（デフォルト: 1000ms）
    And 2 回目の配信がリトライされる（待機後）
    And 2 回目の配信が失敗（502）
    And webhook_delivery_logs に attempt_number=2, delivery_status="failed" が記録される
    And 3 回目の配信がリトライされる
    And 3 回目の配信が成功（200）
    And webhook_delivery_logs に attempt_number=3, delivery_status="sent" が記録される
    And webhook_subscriptions.success_count がインクリメントされる
    And task_completion_events.event_status は "dispatched" に更新される


  Scenario: 最終的に失敗時は task_webhook_attempts テーブルに記録
    Given Webhook endpoint が常に 5xx エラーで応答する
    And retry_policy.max_retries は 3
    When Webhook delivery が実行され 3 回すべてリトライ失敗
    Then webhook_delivery_logs の最終レコードが delivery_status="permanent_failure"
    And webhook_delivery_logs の last_error_message が設定される
    And webhook_subscriptions.failure_count がインクリメントされる
    And webhook_subscriptions.last_status_code は最終レスポンスコード
    And task_completion_events.event_status は "failed" に更新される
    And アラート・通知 ログが生成されている


  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Scenario 5: WebSocket Real-time Notification
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Scenario: WS /ws/tasks に接続後、Task 更新時にリアルタイム通知を受信
    Given WebSocket server が起動している
    When WebSocket クライアント が WS /ws/tasks に接続
    Then WebSocket 接続が確立される（connection_id が割り当てられる）
    And ConnectionManager に新規接続が登録される
    When Task completion event が発火する
    Then WebSocket クライアント は リアルタイム通知を受信する
    And 通知 JSON が以下のスキーマに従う
      """
      {
        "type": "task_completed",
        "event_id": integer,
        "task_id": integer,
        "status": "completed",
        "timestamp": ISO8601
      }
      """
    And 通知 delivery_latency が 100ms 以下


  Scenario: 複数クライアント接続でブロードキャスト動作確認
    Given WebSocket サーバーが起動している
    And Client A, Client B, Client C が WS /ws/tasks に接続している
    When Task completion event が発火する
    Then すべての接続済みクライアント（A, B, C）が同一の通知を受信する
    And 通知は 15ms 以内に全クライアントに配信される
    When Client A が接続を切断
    Then Client B, C は継続して通知を受信する
    And Client A は通知を受信しない
    And ConnectionManager から Client A の接続が削除される


  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # Additional Edge Cases
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Scenario: 無効な auth_type で登録失敗
    Given auth_type が ('bearer', 'hmac-sha256') に含まれない
    When POST /api/webhooks/register で登録リクエストを送信
    Then ステータスコード 400 が返却される
    And response.detail に "Invalid auth_type" が含まれている


  Scenario: Bearer token 未提供で 401 エラー
    Given Bearer token が提供されていない
    When POST /api/webhooks/register にリクエスト送信
    Then ステータスコード 401 が返却される
    And response.detail に "Missing or invalid bearer token" が含まれている


  Scenario: Webhook を正常に削除できる
    Given Webhook が登録されている
    And webhook_id が存在する
    When DELETE /api/webhooks/{webhook_id} でリクエスト送信
    Then ステータスコード 204 が返却される
    And webhook_subscriptions テーブルから該当レコードが削除される
    And 関連する webhook_delivery_logs も DELETE CASCADE で削除される


  Scenario: 他のユーザーの Webhook は削除不可
    Given Webhook がユーザー A で登録されている
    And ユーザー B の Bearer token でリクエスト
    When DELETE /api/webhooks/{webhook_id} でリクエスト送信
    Then ステータスコード 403 が返却される
    And response.detail に "Not authorized" が含まれている
    And webhook_subscriptions テーブルから削除されない


  Scenario: Webhook 一覧取得で event_type でフィルタリング
    Given 複数の Webhook が登録されている（event_type: 'task.completed'）
    When GET /api/webhooks?event_type=task.completed でリクエスト送信
    Then ステータスコード 200 が返却される
    And response.webhooks は event_type='task.completed' のみ
    And response.total は一致する Webhook 数
