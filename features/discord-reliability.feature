# features/discord-reliability.feature
Feature: Discord 連携の信頼性
  ai-orchestrator として
  Discord とのメッセージ送受信を確実に行いたい
  そのために通常系・エラー系のケースをすべてテストする

  Background:
    Given Discord Bot トークンが ~/.claude/channels/discord/.env に設定されている
    And Discord チャンネル ID が ~/.claude/channels/discord/channel_id に設定されている
    And Discord API エンドポイントが到達可能である

  # 通常系シナリオ
  Scenario: テキストメッセージを送信できる
    Given discord_notifier モジュールが初期化されている
    When send_message() に "テストメッセージ" を渡して実行する
    Then Discord REST API に POST リクエストが送信される
    And Authorization ヘッダーに "Bot {token}" が含まれる
    And メッセージボディに "テストメッセージ" が JSON 形式で含まれる
    And 関数は True を返す

  Scenario: サマリーメッセージを送信できる
    Given タスク DB に以下のデータが存在する
      | status      | count |
      | pending     | 5     |
      | in_progress | 3     |
      | done        | 10    |
    When build_cycle_summary() を呼び出す
    Then 完了タスク数 "10 件" がメッセージに含まれる
    And pending タスク数 "5 件" がメッセージに含まれる
    And メッセージを send_message() で送信できる

  Scenario: 複数メッセージを順序保証で送信できる
    Given 送信待機中のメッセージが3つある
    When メッセージ1から順番に send_message() で送信する
    Then メッセージ1が先に Discord に到達する
    And メッセージ2がその後に到達する
    And メッセージ3が最後に到達する
    And すべてのメッセージが正常に送信される

  # エラー系シナリオ
  Scenario: トークンが見つからない場合は False を返す
    Given ~/.claude/channels/discord/.env が存在しない
    When send_message() を呼び出す
    Then 関数は False を返す
    And エラーメッセージ "[discord_notifier] トークンが見つかりません" がログに出力される

  Scenario: チャンネル ID が見つからない場合は False を返す
    Given ~/.claude/channels/discord/channel_id が存在しない
    And DISCORD_CHANNEL_ID 環境変数も設定されていない
    When send_message() を呼び出す
    Then 関数は False を返す
    And エラーメッセージ "[discord_notifier] チャンネル ID が見つかりません" がログに出力される

  Scenario: Discord API がタイムアウトした場合は False を返す
    Given Discord API エンドポイントがレスポンスしない
    When send_message() を呼び出す
    Then 10秒以内にタイムアウトして False を返す
    And エラーメッセージ "[discord_notifier] 送信失敗:" がログに出力される
    And タイムアウト例外の詳細が記録される

  Scenario: Discord API が 401 Unauthorized を返した場合は False を返す
    Given Discord Bot トークンが無効である
    When send_message() を呼び出す
    Then Discord API は 401 ステータスを返す
    And send_message() は False を返す
    And エラーメッセージにステータスコードが含まれる

  Scenario: Discord API が 403 Forbidden を返した場合は False を返す
    Given チャンネル ID が存在しない
    When send_message() を呼び出す
    Then Discord API は 403 ステータスを返す
    And send_message() は False を返す
    And エラーメッセージにステータスコードが含まれる

  Scenario: ネットワークエラーが発生した場合は False を返す
    Given ネットワークが一時的に遮断されている
    When send_message() を呼び出す
    Then ConnectionError または URLError が発生する
    And send_message() は False を返す
    And エラーメッセージがログに出力される

  # リトライ・復旧系シナリオ
  Scenario: 一時的なエラーから復旧する
    Given Discord API が一度だけタイムアウトする
    When send_message() を1回目に呼び出す
    Then False を返す
    When Discord API が復旧して Normal に返す
    And send_message() を2回目に呼び出す
    Then True を返す

  Scenario: 複数メッセージ送信中の部分失敗
    Given 送信待機中のメッセージが3つある
    And メッセージ2を送信するときだけ Discord API がエラーを返す
    When 3つのメッセージを順番に send_message() で送信する
    Then メッセージ1は True を返す
    And メッセージ2は False を返す
    And メッセージ3は True を返す
    And 送信結果が正確に記録される

  # メッセージ形式・内容の検証
  Scenario: メッセージ内容が正しく JSON エスケープされる
    Given メッセージに特殊文字 "\"、\\、\n" が含まれている
    When send_message() を呼び出す
    Then JSON ボディが正しくエスケープされている
    And Discord API に到達するメッセージが正確である

  Scenario: User-Agent ヘッダーが正しく設定される
    Given send_message() を呼び出す
    When Discord API へのリクエストがキャプチャされる
    Then User-Agent ヘッダーに "DiscordBot (ai-orchestrator, 1.0)" が含まれる
    And Content-Type ヘッダーに "application/json" が含まれる

  # 環境変数フォールバック
  Scenario: チャンネル ID が環境変数からフォールバックで読み込まれる
    Given ~/.claude/channels/discord/channel_id が存在しない
    And DISCORD_CHANNEL_ID 環境変数に値が設定されている
    When send_message() を呼び出す
    Then DISCORD_CHANNEL_ID の値が使用される
    And メッセージが正常に送信される

  Scenario Outline: 異なるチャンネル ID での送信
    Given 異なるチャンネル ID が指定されている: <channel_id>
    When send_message() を呼び出す
    Then Discord REST API の URL に <channel_id> が含まれる
    And メッセージが正常に送信される

    Examples:
      | channel_id       |
      | 123456789        |
      | 987654321        |
      | 111111111111111  |

  # タイムアウト検証
  Scenario: タイムアウトが10秒に設定されている
    Given urllib.request.urlopen のタイムアウトパラメータがモニタリングされている
    When send_message() を呼び出す
    Then timeout=10 が設定されていることを確認できる

  # 同時実行性
  Scenario: 複数スレッドから同時にメッセージを送信できる
    Given 3つの独立したスレッドが起動されている
    When 各スレッドから send_message() を呼び出す
    Then 3つのメッセージがすべて成功する
    And レースコンディションが発生しない
    And 送信順序は保証されない（ただし全て送信される）
