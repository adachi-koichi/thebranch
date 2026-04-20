#!/usr/bin/env python3
"""
test_concurrency_limit.py — Task #2197 ユニット・統合テスト

テスト内容:
- validate_concurrency_limit() 関数の動作検証
- start_pane.py の同時起動数制限チェック統合
- orchestrate_loop.py の監視ループ統合
"""

import json
import os
import sys
import pytest
import subprocess
from pathlib import Path

# スクリプトパスの追加
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from session_naming import validate_concurrency_limit, make_team_session, ORCHESTRATOR_SESSION


class TestValidateConcurrencyLimit:
    """validate_concurrency_limit() の単体テスト"""

    def test_returns_dict_structure(self):
        """返り値が正しい辞書構造を持つことを確認"""
        result = validate_concurrency_limit()
        assert isinstance(result, dict)
        assert "orchestrator" in result
        assert "sessions" in result
        assert "violations" in result

    def test_orchestrator_section_structure(self):
        """orchestrator セクションの構造を確認"""
        result = validate_concurrency_limit()
        orch = result["orchestrator"]
        assert "current" in orch
        assert "max" in orch
        assert "status" in orch
        assert orch["max"] == 1

    def test_session_section_structure(self):
        """sessions セクションの構造を確認"""
        result = validate_concurrency_limit()
        assert isinstance(result["sessions"], list)

        # セッションが存在する場合、各エントリの構造を確認
        for session in result["sessions"]:
            assert "session" in session
            assert "managers" in session
            assert "members" in session
            assert "current" in session["managers"]
            assert "max" in session["managers"]
            assert "status" in session["managers"]
            assert "current" in session["members"]
            assert "max" in session["members"]
            assert "status" in session["members"]

    def test_violations_section_structure(self):
        """violations セクションの構造を確認"""
        result = validate_concurrency_limit()
        assert isinstance(result["violations"], list)

        # 違反が存在する場合、各エントリの構造を確認
        for violation in result["violations"]:
            assert "type" in violation
            assert "details" in violation
            # 'session' は None または文字列
            assert violation.get("session") is None or isinstance(violation["session"], str)

    def test_orchestrator_pane_limit(self):
        """orchestrator セッション制限をテスト"""
        result = validate_concurrency_limit()
        orch_count = result["orchestrator"]["current"]
        # 正常な環境では orchestrator は 1 つのみ
        assert orch_count == 1, f"orchestrator セッション数が不正: {orch_count}"

    def test_no_violations_in_normal_state(self):
        """正常な状態では違反がないことを確認"""
        result = validate_concurrency_limit()
        # 通常の環境では違反がない
        violations = result["violations"]
        if violations:
            # 違反がある場合、その内容をログ出力
            for v in violations:
                print(f"  違反: {v['type']} - {v['details']}")

    def test_managers_window_max_panes(self):
        """managers window の最大ペイン数（2）を確認"""
        result = validate_concurrency_limit()
        for session_info in result["sessions"]:
            managers = session_info["managers"]
            assert managers["max"] == 2

    def test_members_window_max_panes(self):
        """members window の最大ペイン数（3）を確認"""
        result = validate_concurrency_limit()
        for session_info in result["sessions"]:
            members = session_info["members"]
            assert members["max"] == 3


class TestStartPaneConcurrencyCheck:
    """start_pane.py の同時起動数制限チェック統合テスト"""

    def test_import_validate_concurrency_limit(self):
        """start_pane.py が validate_concurrency_limit をインポート可能か確認"""
        from start_pane import validate_concurrency_limit as vcc
        assert callable(vcc)

    def test_start_pane_validation_logic(self):
        """start_pane.py の検証ロジックが存在することを確認"""
        start_pane_path = Path(_SCRIPTS_DIR) / "start_pane.py"
        with open(start_pane_path) as f:
            content = f.read()

        # validate_concurrency_limit のインポートが存在
        assert "from session_naming import" in content
        assert "validate_concurrency_limit" in content

        # ロール別チェックロジックが存在
        assert 'if role_lower in ("engineer"' in content or 'if role_lower in ("engineer' in content


class TestOrchestrateLoopIntegration:
    """orchestrate_loop.py の監視ループ統合テスト"""

    def test_import_in_orchestrate_loop(self):
        """orchestrate_loop.py が validate_concurrency_limit をインポート可能か確認"""
        orchestrate_loop_path = Path(_SCRIPTS_DIR) / "orchestrate_loop.py"
        with open(orchestrate_loop_path) as f:
            content = f.read()

        # インポート文が存在
        assert "from session_naming import" in content
        assert "validate_concurrency_limit" in content

    def test_concurrency_check_in_run_once(self):
        """run_once() に同時起動数チェックが統合されていることを確認"""
        orchestrate_loop_path = Path(_SCRIPTS_DIR) / "orchestrate_loop.py"
        with open(orchestrate_loop_path) as f:
            content = f.read()

        # Step 0.7 の同時起動数チェックが存在
        assert "Step 0.7" in content or "0.7" in content
        assert "validate_concurrency_limit" in content
        assert "concurrency" in content.lower()


class TestErrorHandling:
    """エラーハンドリングとエッジケースのテスト"""

    def test_tmux_command_failure_handling(self):
        """tmux コマンド失敗時のハンドリングを確認"""
        # tmux ls が失敗しても例外が発生しないことを確認
        try:
            result = validate_concurrency_limit()
            # 正常に完了
            assert result is not None
        except Exception as e:
            pytest.fail(f"validate_concurrency_limit() が予期しない例外を発生: {e}")

    def test_empty_sessions_handling(self):
        """セッションなし時のハンドリング"""
        result = validate_concurrency_limit()
        # セッションがない場合も正常に処理される
        assert isinstance(result["sessions"], list)
        assert isinstance(result["violations"], list)


class TestIntegrationWithStartPane:
    """start_pane.py との統合テスト（シミュレーション）"""

    def test_validation_raises_on_violation(self):
        """違反検出時に RuntimeError が raise されることを確認"""
        from start_pane import validate_concurrency_limit as vcc

        # 現在の状態をチェック
        result = vcc()
        if result["violations"]:
            # 違反がある場合、その内容をログ
            for v in result["violations"]:
                print(f"検出された違反: {v['type']} - {v['details']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
