#!/usr/bin/env python3
"""
tests/test_idle_detection.py — detect_idle_panes.py のユニットテスト
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from detect_idle_panes import (
    IDLE_PATTERN,
    capture_pane_content,
    detect_idle_panes,
    get_last_nonempty_line,
    is_idle,
    list_all_panes,
)


class TestIdlePattern:
    """IDLE_PATTERN の正規表現テスト"""

    def test_dollar_sign_idle(self):
        assert IDLE_PATTERN.search("user@host:~$")

    def test_dollar_sign_with_space(self):
        assert IDLE_PATTERN.search("user@host:~$ ")

    def test_percent_sign_idle(self):
        assert IDLE_PATTERN.search("zsh%")

    def test_greater_than_idle(self):
        assert IDLE_PATTERN.search(">>  >")

    def test_not_idle_normal_text(self):
        assert not IDLE_PATTERN.search("Running task...")

    def test_not_idle_long_line(self):
        assert not IDLE_PATTERN.search("Processing 100% complete")


class TestIsIdle:
    """is_idle() のテスト"""

    def test_empty_content(self):
        assert not is_idle("")

    def test_none_like_empty(self):
        assert not is_idle("")

    def test_idle_bash_prompt(self):
        content = "some output\nuser@host:/path$ "
        assert is_idle(content)

    def test_idle_zsh_prompt(self):
        content = "some output\nuser@host % "
        assert is_idle(content)

    def test_not_idle_running_command(self):
        content = "Running tests...\nTest 1/10"
        assert not is_idle(content)

    def test_idle_with_blank_trailing_lines(self):
        content = "user@host:~$ \n\n\n"
        assert is_idle(content)

    def test_idle_gt_prompt(self):
        content = "some text\n> "
        assert is_idle(content)

    def test_not_idle_claude_prompt(self):
        content = "Claude is thinking...\nPlease wait"
        assert not is_idle(content)

    def test_multiline_with_idle_at_end(self):
        content = "\n".join([
            "Building project...",
            "Compiling src/main.py",
            "Done.",
            "user@laptop:~/project$ ",
        ])
        assert is_idle(content)


class TestGetLastNonemptyLine:
    """get_last_nonempty_line() のテスト"""

    def test_basic(self):
        content = "line1\nline2\nline3"
        assert get_last_nonempty_line(content) == "line3"

    def test_trailing_blank_lines(self):
        content = "line1\nline2\n\n\n"
        assert get_last_nonempty_line(content) == "line2"

    def test_empty_content(self):
        assert get_last_nonempty_line("") == ""

    def test_all_blank(self):
        assert get_last_nonempty_line("\n\n\n") == ""

    def test_single_line(self):
        content = "user@host:~$ "
        assert get_last_nonempty_line(content) == "user@host:~$ "


class TestListAllPanes:
    """list_all_panes() のテスト"""

    @patch("detect_idle_panes.subprocess.run")
    def test_normal_output(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="%0 my-session 0 0\n%1 other-session 1 2\n",
        )
        panes = list_all_panes()
        assert len(panes) == 2
        assert panes[0]["pane_id"] == "%0"
        assert panes[0]["session_name"] == "my-session"
        assert panes[0]["window_index"] == "0"
        assert panes[0]["pane_index"] == "0"
        assert panes[1]["pane_id"] == "%1"
        assert panes[1]["session_name"] == "other-session"

    @patch("detect_idle_panes.subprocess.run")
    def test_tmux_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        panes = list_all_panes()
        assert panes == []

    @patch("detect_idle_panes.subprocess.run")
    def test_empty_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        panes = list_all_panes()
        assert panes == []

    @patch("detect_idle_panes.subprocess.run")
    def test_session_name_with_slash(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="%5 adachi-koichi/exp-stock@v1 0 0\n",
        )
        panes = list_all_panes()
        assert len(panes) == 1
        assert panes[0]["session_name"] == "adachi-koichi/exp-stock@v1"


class TestCapturePaneContent:
    """capture_pane_content() のテスト"""

    @patch("detect_idle_panes.subprocess.run")
    def test_normal_content(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="line1\nline2\nuser@host:~$ ",
        )
        content = capture_pane_content("%0")
        assert "user@host:~$ " in content

    @patch("detect_idle_panes.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        content = capture_pane_content("%99")
        assert content == ""

    @patch("detect_idle_panes.subprocess.run")
    def test_truncated_to_30_lines(self, mock_run):
        long_content = "\n".join([f"line{i}" for i in range(100)])
        mock_run.return_value = MagicMock(returncode=0, stdout=long_content)
        content = capture_pane_content("%0")
        lines = content.splitlines()
        assert len(lines) <= 30


class TestDetectIdlePanes:
    """detect_idle_panes() の統合テスト"""

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_finds_idle_panes(self, mock_list, mock_capture):
        mock_list.return_value = [
            {"pane_id": "%0", "session_name": "session-a", "window_index": "0", "pane_index": "0"},
            {"pane_id": "%1", "session_name": "session-b", "window_index": "0", "pane_index": "0"},
        ]
        mock_capture.side_effect = [
            "user@host:~$ ",   # idle
            "Running tests...",  # not idle
        ]

        idle = detect_idle_panes()
        assert len(idle) == 1
        assert idle[0]["pane_id"] == "%0"
        assert idle[0]["session_name"] == "session-a"
        assert "last_content" in idle[0]

    @patch("detect_idle_panes.capture_pane_content")
    @patch("detect_idle_panes.list_all_panes")
    def test_no_idle_panes(self, mock_list, mock_capture):
        mock_list.return_value = [
            {"pane_id": "%0", "session_name": "session-a", "window_index": "0", "pane_index": "0"},
        ]
        mock_capture.return_value = "Claude is processing..."

        idle = detect_idle_panes()
        assert idle == []

    @patch("detect_idle_panes.list_all_panes")
    def test_no_panes(self, mock_list):
        mock_list.return_value = []
        idle = detect_idle_panes()
        assert idle == []
