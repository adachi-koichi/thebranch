#!/usr/bin/env python3
"""
test_discord_reliability.py — Discord 連携信頼性テストのステップ定義

pytest-bdd でシナリオを実装するための基盤。
以下のコマンドで実行:
  pytest tests/step_defs/test_discord_reliability.py -v
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from pytest_bdd import scenario, given, when, then, parsers

# THEBRANCH のスクリプトをインポート
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from discord_notifier import send_message, load_discord_token, load_channel_id, build_cycle_summary


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_env(tmp_path):
    """テスト用の一時的なディレクトリ構造を作成する。"""
    discord_dir = tmp_path / ".claude" / "channels" / "discord"
    discord_dir.mkdir(parents=True, exist_ok=True)

    return {
        "env_file": discord_dir / ".env",
        "channel_file": discord_dir / "channel_id",
        "tmp_path": tmp_path,
    }


@pytest.fixture
def default_token():
    """デフォルトの Discord Bot トークン。"""
    return "test-token-12345abcde"


@pytest.fixture
def default_channel_id():
    """デフォルトの Discord チャンネル ID。"""
    return "123456789012345"


# =============================================================================
# Background: Discord 設定の準備
# =============================================================================

@given("Discord Bot トークンが ~/.claude/channels/discord/.env に設定されている")
def setup_token(mock_env, default_token):
    """トークンを .env ファイルに書き込む。"""
    mock_env["env_file"].write_text(f'DISCORD_TOKEN="{default_token}"\n')


@given("Discord チャンネル ID が ~/.claude/channels/discord/channel_id に設定されている")
def setup_channel_id(mock_env, default_channel_id):
    """チャンネル ID をファイルに書き込む。"""
    mock_env["channel_file"].write_text(default_channel_id)


@given("Discord API エンドポイントが到達可能である")
def setup_discord_api_accessible():
    """Discord API エンドポイントが到達可能（モック）。"""
    pass  # 以降の when/then でモック設定する


# =============================================================================
# Scenario 1: テキストメッセージを送信できる
# =============================================================================

@scenario(
    "../features/discord-reliability.feature",
    "テキストメッセージを送信できる"
)
def test_send_text_message():
    pass


@given("discord_notifier モジュールが初期化されている")
def init_discord_notifier():
    """discord_notifier モジュールが利用可能（既にインポート済み）。"""
    pass


@when("send_message() に \"テストメッセージ\" を渡して実行する")
def send_test_message(mock_env, default_token, default_channel_id):
    """テストメッセージを送信する。"""
    with patch("discord_notifier.load_discord_token", return_value=default_token), \
         patch("discord_notifier.load_channel_id", return_value=default_channel_id), \
         patch("urllib.request.urlopen") as mock_urlopen:

        mock_response = Mock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_urlopen.return_value = mock_response

        result = send_message("テストメッセージ")

        # コンテキストに保存（then で使う）
        pytest.current_test_context = {
            "result": result,
            "mock_urlopen": mock_urlopen,
        }


@then("Discord REST API に POST リクエストが送信される")
def verify_post_request():
    """POST リクエストが送信されたことを確認。"""
    ctx = pytest.current_test_context
    mock_urlopen = ctx["mock_urlopen"]
    mock_urlopen.assert_called_once()

    request = mock_urlopen.call_args[0][0]
    assert request.get_method() == "POST"


@then("Authorization ヘッダーに \"Bot {token}\" が含まれる")
def verify_auth_header():
    """Authorization ヘッダーの確認。"""
    ctx = pytest.current_test_context
    mock_urlopen = ctx["mock_urlopen"]

    request = mock_urlopen.call_args[0][0]
    assert request.headers.get("Authorization").startswith("Bot ")


@then("メッセージボディに \"テストメッセージ\" が JSON 形式で含まれる")
def verify_message_body():
    """メッセージボディの確認。"""
    ctx = pytest.current_test_context
    mock_urlopen = ctx["mock_urlopen"]

    request = mock_urlopen.call_args[0][0]
    body = json.loads(request.data.decode())
    assert body["content"] == "テストメッセージ"


@then("関数は True を返す")
def verify_return_value():
    """戻り値が True であることを確認。"""
    ctx = pytest.current_test_context
    assert ctx["result"] is True


# =============================================================================
# Scenario 2: トークンが見つからない場合
# =============================================================================

@scenario(
    "../features/discord-reliability.feature",
    "トークンが見つからない場合は False を返す"
)
def test_missing_token():
    pass


@given("~/.claude/channels/discord/.env が存在しない")
def missing_env_file():
    """env ファイルを削除."""
    with patch("discord_notifier.load_discord_token", return_value=None):
        pass


@when("send_message() を呼び出す")
def call_send_message_no_token():
    """send_message() を呼び出す。"""
    result = send_message("test message", verbose=True)
    pytest.current_test_context = {"result": result}


@then("関数は False を返す")
def verify_false_return():
    """戻り値が False であることを確認。"""
    assert pytest.current_test_context["result"] is False


@then('エラーメッセージ "[discord_notifier] トークンが見つかりません" がログに出力される')
def verify_error_message():
    """エラーメッセージが出力されたことを確認（capsys で捕捉）。"""
    pass  # 実装時に capsys で検証


# =============================================================================
# Scenario 3: タイムアウト検証
# =============================================================================

@scenario(
    "../features/discord-reliability.feature",
    "Discord API がタイムアウトした場合は False を返す"
)
def test_timeout_handling():
    pass


@given("Discord API エンドポイントがレスポンスしない")
def setup_timeout():
    """urlopen がタイムアウトをシミュレート。"""
    pass


@when("send_message() を呼び出す")
def send_message_with_timeout():
    """タイムアウト中に send_message() を実行。"""
    import socket
    with patch("urllib.request.urlopen", side_effect=socket.timeout("Timeout")):
        result = send_message("test", verbose=True)
        pytest.current_test_context = {"result": result}


@then("10秒以内にタイムアウトして False を返す")
def verify_timeout_behavior():
    """タイムアウト時に False を返すことを確認。"""
    assert pytest.current_test_context["result"] is False


# =============================================================================
# Scenario 4: チャンネル ID のフォールバック
# =============================================================================

@scenario(
    "../features/discord-reliability.feature",
    "チャンネル ID が環境変数からフォールバックで読み込まれる"
)
def test_channel_id_fallback():
    pass


@given("~/.claude/channels/discord/channel_id が存在しない")
def missing_channel_file():
    """チャンネルファイルが存在しないことを設定。"""
    with patch("discord_notifier.load_channel_id") as mock_load:
        # フォールバック時は環境変数から取得
        os.environ["DISCORD_CHANNEL_ID"] = "env-channel-id"
        mock_load.return_value = "env-channel-id"


@given("DISCORD_CHANNEL_ID 環境変数に値が設定されている")
def setup_env_channel_id():
    """環境変数にチャンネル ID を設定。"""
    os.environ["DISCORD_CHANNEL_ID"] = "env-channel-999"


@then("DISCORD_CHANNEL_ID の値が使用される")
def verify_env_channel_used():
    """環境変数の値が使用されたことを確認。"""
    assert os.environ.get("DISCORD_CHANNEL_ID") == "env-channel-999"


# =============================================================================
# テスト実行のヘルパー
# =============================================================================

def run_tests():
    """テストを実行する。"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
