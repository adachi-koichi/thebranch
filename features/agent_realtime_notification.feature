Feature: エージェント リアルタイム通知（WebSocket）

  Scenario: ダッシュボード接続時に現在のエージェント状態が送信される
    Given ダッシュボード（http://localhost:8000）を開く
    And エージェント "Agent-A" が起動中である
    When /ws/agents WebSocket に接続する
    Then メッセージ type=agents_update を受け取る
    And agents 配列にエージェント "Agent-A" が含まれている
    And エージェントの状態は "running" である

  Scenario: エージェント起動時にリアルタイムに状態が反映される
    Given ダッシュボード（http://localhost:8000）を開いている
    And /ws/agents WebSocket に接続している
    When tmux で新規エージェント "Agent-B" を起動する
    Then 3秒以内に agents_update メッセージを受け取る
    And changes 配列に "Agent-B" の状態変化イベントが含まれている
    And イベント内容は {"event": "started", ...} である
    And ダッシュボード UI に "Agent-B" が表示される

  Scenario: エージェント停止時に即座に状態が更新される
    Given ダッシュボード（http://localhost:8000）を開いている
    And /ws/agents WebSocket に接続している
    And エージェント "Agent-C" が起動中である
    When エージェント "Agent-C" を停止する（tmux kill-session）
    Then 3秒以内に agents_update メッセージを受け取る
    And changes 配列に "Agent-C" の状態変化イベントが含まれている
    And イベント内容は {"event": "stopped", ...} である
    And ダッシュボード UI から "Agent-C" が削除される

  Scenario: エージェントステータスインジケータが正しく表示される
    Given ダッシュボード（http://localhost:8000）を開く
    When エージェント一覧タブを表示する
    Then running 状態のエージェントに 🟢 アイコンが表示される
    And starting 状態のエージェントに 🟡 アイコンが表示される
    And stopped 状態のエージェントに 🔴 アイコンが表示される

  Scenario: WebSocket 接続が失われた場合に自動再接続される
    Given ダッシュボード（http://localhost:8000）を開いている
    And /ws/agents WebSocket に接続している
    When WebSocket 接続を強制的に閉じる（ネットワークカット等）
    Then ライブバッジが 🔴 dead に変わる
    And 5秒以内に自動再接続が試みられる
    And 再接続成功時にライブバッジが 🟢 live に戻る
    And エージェント状態が再同期される

  Scenario: SSE フォールバック との後方互換性
    Given ダッシュボード（http://localhost:8000）を開く
    When ブラウザが WebSocket をサポートしていない環境である
    Then SSE フォールバック接続処理が実行される
    And エージェント一覧が表示される（SSE 経由、5秒ポーリング）

  Scenario: 複数エージェントの同時状態更新
    Given ダッシュボード（http://localhost:8000）を開いている
    And /ws/agents WebSocket に接続している
    When 複数のエージェント（Agent-D, Agent-E, Agent-F）を同時起動する
    Then 1つの agents_update メッセージ内に複数の状態変化イベントが含まれている
    And すべてのエージェント状態が正確に反映される
    And UI のレンダリングが一度にすべて更新される

  Scenario: エージェント状態変化の詳細ログ
    Given ダッシュボード（http://localhost:8000）を開いている
    And /ws/agents WebSocket に接続している
    And ブラウザのコンソール logger が有効である
    When エージェント "Agent-G" を起動→稼働→停止 の全ライフサイクルを経過させる
    Then 変化イベントごとにコンソール log に以下が出力される
      | イベント | タイムスタンプ | agent_id | state     |
      | started  | 2026-04-20T... | Agent-G  | starting  |
      | pane_change | 2026-04-20T... | Agent-G  | running   |
      | stopped  | 2026-04-20T... | Agent-G  | stopped   |
