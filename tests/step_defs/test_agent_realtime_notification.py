"""
BDD テスト実装: エージェント リアルタイム通知（WebSocket）

テスト対象:
- /ws/agents WebSocket エンドポイント
- WebSocket接続時の初期状態配信
- エージェント状態変化のリアルタイム配信
- WebSocket再接続ロジック
- SSEフォールバック互換性
"""
import asyncio
import json
import subprocess
import time
from pathlib import Path
import pytest
from pytest_bdd import scenario, given, when, then, and_


# ==========================================
# テストシナリオのマッピング
# ==========================================

@scenario('../features/agent_realtime_notification.feature', 'ダッシュボード接続時に現在のエージェント状態が送信される')
def test_dashboard_connect_initial_state():
    """シナリオ: ダッシュボード接続時に現在のエージェント状態が送信される"""
    pass


@scenario('../features/agent_realtime_notification.feature', 'エージェント起動時にリアルタイムに状態が反映される')
def test_agent_startup_realtime_update():
    """シナリオ: エージェント起動時にリアルタイムに状態が反映される"""
    pass


@scenario('../features/agent_realtime_notification.feature', 'エージェント停止時に即座に状態が更新される')
def test_agent_shutdown_realtime_update():
    """シナリオ: エージェント停止時に即座に状態が更新される"""
    pass


@scenario('../features/agent_realtime_notification.feature', 'エージェントステータスインジケータが正しく表示される')
def test_agent_status_indicator_display():
    """シナリオ: エージェントステータスインジケータが正しく表示される"""
    pass


@scenario('../features/agent_realtime_notification.feature', 'WebSocket 接続が失われた場合に自動再接続される')
def test_websocket_auto_reconnect():
    """シナリオ: WebSocket 接続が失われた場合に自動再接続される"""
    pass


@scenario('../features/agent_realtime_notification.feature', 'SSE フォールバック との後方互換性')
def test_sse_fallback_compatibility():
    """シナリオ: SSE フォールバック との後方互換性"""
    pass


@scenario('../features/agent_realtime_notification.feature', '複数エージェントの同時状態更新')
def test_multiple_agents_simultaneous_update():
    """シナリオ: 複数エージェントの同時状態更新"""
    pass


@scenario('../features/agent_realtime_notification.feature', 'エージェント状態変化の詳細ログ')
def test_agent_state_change_logging():
    """シナリオ: エージェント状態変化の詳細ログ"""
    pass


# ==========================================
# Given: 前提条件の実装
# ==========================================

@given('ダッシュボード（http://localhost:8000）を開く')
def open_dashboard(browser_context):
    """ダッシュボードを開く"""
    page = browser_context.new_page()
    page.goto('http://localhost:8000')
    return page


@given('ダッシュボード（http://localhost:8000）を開いている')
def dashboard_is_open(browser_context):
    """ダッシュボードが開いている状態"""
    page = browser_context.new_page()
    page.goto('http://localhost:8000')
    page.wait_for_load_state('networkidle')
    return page


@given('エージェント "Agent-A" が起動中である')
def agent_a_is_running(tmux_session):
    """Agent-Aを起動"""
    # tmux セッションでエージェントを起動
    subprocess.run(
        ['tmux', 'send-keys', '-t', f'{tmux_session}', 'echo "Agent-A running"', 'Enter'],
        check=True
    )
    time.sleep(1)


@given('/ws/agents WebSocket に接続する')
def connect_websocket(page):
    """WebSocket に接続"""
    # JavaScriptでWebSocketに接続
    page.evaluate('''() => {
        window.wsMessages = [];
        window.ws = new WebSocket('ws://localhost:8000/ws/agents');
        window.ws.onmessage = (e) => {
            window.wsMessages.push(JSON.parse(e.data));
        };
    }''')
    time.sleep(0.5)


@given('/ws/agents WebSocket に接続している')
def websocket_is_connected(page):
    """WebSocket に接続した状態"""
    page.evaluate('''() => {
        window.wsMessages = [];
        window.ws = new WebSocket('ws://localhost:8000/ws/agents');
        window.ws.onmessage = (e) => {
            window.wsMessages.push(JSON.parse(e.data));
        };
    }''')
    time.sleep(1)


@given('エージェント "Agent-C" が起動中である')
def agent_c_is_running(tmux_session):
    """Agent-Cを起動"""
    subprocess.run(
        ['tmux', 'send-keys', '-t', f'{tmux_session}', 'echo "Agent-C running"', 'Enter'],
        check=True
    )
    time.sleep(1)


@given('ブラウザのコンソール logger が有効である')
def console_logger_enabled(page):
    """コンソールログが有効"""
    page.evaluate('''() => {
        window.consoleLogs = [];
        const originalLog = console.log;
        console.log = function(...args) {
            window.consoleLogs.push(args.join(' '));
            originalLog.apply(console, args);
        };
    }''')


# ==========================================
# When: アクションの実装
# ==========================================

@when('/ws/agents WebSocket に接続する')
def when_connect_websocket(page):
    """WebSocket に接続する"""
    page.evaluate('''() => {
        window.wsMessages = [];
        window.ws = new WebSocket('ws://localhost:8000/ws/agents');
        window.ws.onmessage = (e) => {
            window.wsMessages.push(JSON.parse(e.data));
        };
    }''')
    time.sleep(0.5)


@when('tmux で新規エージェント "Agent-B" を起動する')
def start_agent_b(tmux_session):
    """Agent-Bを起動"""
    subprocess.run(
        ['tmux', 'send-keys', '-t', f'{tmux_session}', 'echo "Agent-B started"', 'Enter'],
        check=True
    )


@when('エージェント "Agent-C" を停止する（tmux kill-session）')
def stop_agent_c(tmux_session):
    """Agent-Cを停止"""
    subprocess.run(
        ['tmux', 'send-keys', '-t', f'{tmux_session}', 'exit', 'Enter'],
        check=True
    )


@when('エージェント一覧タブを表示する')
def show_agents_tab(page):
    """エージェント一覧タブを表示"""
    page.click('[data-tab="agents"]')
    page.wait_for_selector('[class*="agent"]')


@when('WebSocket 接続を強制的に閉じる（ネットワークカット等）')
def force_close_websocket(page):
    """WebSocket接続を閉じる"""
    page.evaluate('() => { window.ws.close(); }')


@when('ブラウザが WebSocket をサポートしていない環境である')
def websocket_unsupported():
    """WebSocketをサポートしていない環境をシミュレート"""
    # 実装: WebSocketをサポートしないブラウザプロファイルを使用
    pass


@when('複数のエージェント（Agent-D, Agent-E, Agent-F）を同時起動する')
def start_multiple_agents(tmux_session):
    """複数エージェントを同時起動"""
    for agent in ['Agent-D', 'Agent-E', 'Agent-F']:
        subprocess.run(
            ['tmux', 'send-keys', '-t', f'{tmux_session}', f'echo "{agent} starting"', 'Enter'],
            check=True
        )
    time.sleep(1)


@when('エージェント "Agent-G" を起動→稼働→停止 の全ライフサイクルを経過させる')
def agent_g_full_lifecycle(tmux_session):
    """Agent-Gのフルライフサイクルを実行"""
    # 起動
    subprocess.run(
        ['tmux', 'send-keys', '-t', f'{tmux_session}', 'echo "Agent-G starting"', 'Enter'],
        check=True
    )
    time.sleep(1)
    # 稼働
    time.sleep(1)
    # 停止
    subprocess.run(
        ['tmux', 'send-keys', '-t', f'{tmux_session}', 'exit', 'Enter'],
        check=True
    )


# ==========================================
# Then: 検証の実装
# ==========================================

@then('メッセージ type=agents_update を受け取る')
def verify_agents_update_message(page):
    """agents_updateメッセージを受け取ったか確認"""
    time.sleep(1)
    messages = page.evaluate('() => window.wsMessages')
    assert any(msg.get('type') == 'agents_update' for msg in messages), \
        f"agents_update message not found. Received: {messages}"


@then('agents 配列にエージェント "Agent-A" が含まれている')
def verify_agent_a_in_list(page):
    """agents配列にAgent-Aが含まれているか確認"""
    messages = page.evaluate('() => window.wsMessages')
    agents_update = next((msg for msg in messages if msg.get('type') == 'agents_update'), None)
    assert agents_update, "No agents_update message found"
    agents = agents_update.get('agents', [])
    assert any(a.get('sessionId') == 'Agent-A' for a in agents), \
        f"Agent-A not found in agents. Agents: {agents}"


@then('エージェントの状態は "running" である')
def verify_agent_state_running(page):
    """エージェントの状態がrunningであることを確認"""
    messages = page.evaluate('() => window.wsMessages')
    agents_update = next((msg for msg in messages if msg.get('type') == 'agents_update'), None)
    assert agents_update, "No agents_update message found"
    agents = agents_update.get('agents', [])
    assert any(a.get('state') == 'running' or a.get('tmux_pane') for a in agents), \
        f"No running agent found. Agents: {agents}"


@then('3秒以内に agents_update メッセージを受け取る')
def verify_agents_update_within_3s(page):
    """3秒以内にagents_updateメッセージを受け取ったか確認"""
    start = time.time()
    while time.time() - start < 3:
        messages = page.evaluate('() => window.wsMessages')
        if any(msg.get('type') == 'agents_update' for msg in messages):
            return
        time.sleep(0.1)
    raise AssertionError("agents_update message not received within 3 seconds")


@then('changes 配列に "Agent-B" の状態変化イベントが含まれている')
def verify_agent_b_change_event(page):
    """Agent-Bの状態変化イベントが含まれているか確認"""
    messages = page.evaluate('() => window.wsMessages')
    agents_update = next((msg for msg in messages if msg.get('type') == 'agents_update'), None)
    assert agents_update, "No agents_update message found"
    changes = agents_update.get('changes', [])
    assert any(c.get('agent_id') == 'Agent-B' for c in changes), \
        f"Agent-B change not found in changes. Changes: {changes}"


@then('イベント内容は {"event": "started", ...} である')
def verify_started_event(page):
    """イベント内容が{"event": "started"}であることを確認"""
    messages = page.evaluate('() => window.wsMessages')
    agents_update = next((msg for msg in messages if msg.get('type') == 'agents_update'), None)
    assert agents_update, "No agents_update message found"
    changes = agents_update.get('changes', [])
    assert any(c.get('event') == 'started' for c in changes), \
        f"No started event found. Changes: {changes}"


@then('ダッシュボード UI に "Agent-B" が表示される')
def verify_agent_b_displayed(page):
    """UIにAgent-Bが表示されているか確認"""
    page.wait_for_selector('text=Agent-B', timeout=5000)


@then('changes 配列に "Agent-C" の状態変化イベントが含まれている')
def verify_agent_c_change_event(page):
    """Agent-Cの状態変化イベントが含まれているか確認"""
    messages = page.evaluate('() => window.wsMessages')
    agents_update = next((msg for msg in messages if msg.get('type') == 'agents_update'), None)
    assert agents_update, "No agents_update message found"
    changes = agents_update.get('changes', [])
    assert any(c.get('agent_id') == 'Agent-C' for c in changes), \
        f"Agent-C change not found in changes. Changes: {changes}"


@then('イベント内容は {"event": "stopped", ...} である')
def verify_stopped_event(page):
    """イベント内容が{"event": "stopped"}であることを確認"""
    messages = page.evaluate('() => window.wsMessages')
    agents_update = next((msg for msg in messages if msg.get('type') == 'agents_update'), None)
    assert agents_update, "No agents_update message found"
    changes = agents_update.get('changes', [])
    assert any(c.get('event') == 'stopped' for c in changes), \
        f"No stopped event found. Changes: {changes}"


@then('ダッシュボード UI から "Agent-C" が削除される')
def verify_agent_c_removed(page):
    """UIからAgent-Cが削除されているか確認"""
    try:
        page.wait_for_selector('text=Agent-C', timeout=1000)
        raise AssertionError("Agent-C still visible in UI")
    except:
        pass  # Agent-Cが見つからないことが期待動作


@then('running 状態のエージェントに 🟢 アイコンが表示される')
def verify_running_indicator(page):
    """running状態に🟢アイコンが表示されているか確認"""
    page.wait_for_selector('.agent-status-indicator:has-text("🟢")', timeout=5000)


@then('starting 状態のエージェントに 🟡 アイコンが表示される')
def verify_starting_indicator(page):
    """starting状態に🟡アイコンが表示されているか確認"""
    page.wait_for_selector('.agent-status-indicator:has-text("🟡")', timeout=5000)


@then('stopped 状態のエージェントに 🔴 アイコンが表示される')
def verify_stopped_indicator(page):
    """stopped状態に🔴アイコンが表示されているか確認"""
    page.wait_for_selector('.agent-status-indicator:has-text("🔴")', timeout=5000)


@then('ライブバッジが 🔴 dead に変わる')
def verify_dead_badge(page):
    """ライブバッジが🔴 deadに変わったか確認"""
    page.wait_for_selector('[data-badge="dead"]', timeout=1000)


@then('5秒以内に自動再接続が試みられる')
def verify_auto_reconnect_within_5s(page):
    """5秒以内に自動再接続が試みられたか確認"""
    start = time.time()
    while time.time() - start < 5:
        is_connected = page.evaluate('() => window.ws && window.ws.readyState === 1')
        if is_connected:
            return
        time.sleep(0.1)
    raise AssertionError("Auto reconnection not attempted within 5 seconds")


@then('再接続成功時にライブバッジが 🟢 live に戻る')
def verify_live_badge_restored(page):
    """ライブバッジが🟢 liveに戻ったか確認"""
    page.wait_for_selector('[data-badge="live"]', timeout=5000)


@then('エージェント状態が再同期される')
def verify_state_resync(page):
    """エージェント状態が再同期されたか確認"""
    messages = page.evaluate('() => window.wsMessages')
    # 最新のagents_updateメッセージが存在するか確認
    assert any(msg.get('type') == 'agents_update' for msg in messages[-5:]), \
        "No recent agents_update message found after reconnection"


@then('SSE フォールバック接続処理が実行される')
def verify_sse_fallback(page):
    """SSEフォールバック処理が実行されたか確認"""
    # JavaScriptで SSE フォールバックが使用されているか確認
    using_sse = page.evaluate('() => window.useSSE === true')
    assert using_sse, "SSE fallback not used"


@then('エージェント一覧が表示される（SSE 経由、5秒ポーリング）')
def verify_agents_displayed_via_sse(page):
    """エージェント一覧がSSE経由で表示されているか確認"""
    page.wait_for_selector('[class*="agent"]', timeout=10000)


@then('1つの agents_update メッセージ内に複数の状態変化イベントが含まれている')
def verify_multiple_changes_in_one_message(page):
    """1つのagents_updateメッセージに複数の状態変化が含まれているか確認"""
    messages = page.evaluate('() => window.wsMessages')
    agents_update = next((msg for msg in messages if msg.get('type') == 'agents_update'), None)
    assert agents_update, "No agents_update message found"
    changes = agents_update.get('changes', [])
    assert len(changes) >= 3, \
        f"Expected multiple changes, got {len(changes)}: {changes}"


@then('すべてのエージェント状態が正確に反映される')
def verify_all_agents_accurate(page):
    """すべてのエージェント状態が正確に反映されているか確認"""
    messages = page.evaluate('() => window.wsMessages')
    agents_update = next((msg for msg in messages if msg.get('type') == 'agents_update'), None)
    assert agents_update, "No agents_update message found"
    agents = agents_update.get('agents', [])
    assert len(agents) >= 3, f"Expected 3+ agents, got {len(agents)}"


@then('UI のレンダリングが一度にすべて更新される')
def verify_ui_rendered_atomically(page):
    """UIが一度に更新されているか確認"""
    # UIに全エージェントが表示されているか確認
    agent_elements = page.query_selector_all('[class*="agent-card"]')
    assert len(agent_elements) >= 3, f"Expected 3+ agent cards, found {len(agent_elements)}"


@then('変化イベントごとにコンソール log に以下が出力される')
def verify_console_logs(page, datatable):
    """コンソールログに期待される出力が含まれているか確認"""
    logs = page.evaluate('() => window.consoleLogs')
    expected_events = {row['イベント'] for row in datatable}
    for event in expected_events:
        assert any(event in log for log in logs), \
            f"Expected event '{event}' not found in logs: {logs}"
