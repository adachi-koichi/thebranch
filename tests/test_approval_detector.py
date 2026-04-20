#!/usr/bin/env python3
"""
tests/test_approval_detector.py — approval_detector.py のユニットテスト
"""

import sys
from pathlib import Path

import pytest

# scripts/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from approval_detector import APPROVAL_PATTERNS, detect_approval_needed


class TestApprovalPatterns:
    """APPROVAL_PATTERNS リストの基本確認"""

    def test_patterns_not_empty(self):
        assert len(APPROVAL_PATTERNS) > 0

    def test_patterns_are_strings(self):
        for p in APPROVAL_PATTERNS:
            assert isinstance(p, str)


class TestDetectApprovalNeeded:
    """detect_approval_needed() のユニットテスト"""

    # ── 検知できるケース ──────────────────────────────────────────────────────

    def test_yes_no_bracket_upper(self):
        result = detect_approval_needed("Continue? [Y/n]")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_yes_no_bracket_lower(self):
        result = detect_approval_needed("Proceed with installation? [y/N]")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_yes_no_parentheses_lower(self):
        result = detect_approval_needed("Are you sure? (yes/no)")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "yes"

    def test_yes_no_parentheses_upper(self):
        result = detect_approval_needed("Confirm deletion (Y/N):")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "Y"

    def test_enter_your_choice(self):
        result = detect_approval_needed("Enter your choice: ")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "1"

    def test_select_option(self):
        result = detect_approval_needed("Select option: 1) skip  2) retry")
        assert result["needs_approval"] is True

    def test_numbered_selection(self):
        result = detect_approval_needed("[1] Install  [2] Skip  [3] Cancel")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "1"

    def test_do_you_want_to_proceed(self):
        result = detect_approval_needed("Do you want to proceed with this action?")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_allow_this_action(self):
        result = detect_approval_needed("Allow this action? (y/n)")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_approve_question(self):
        result = detect_approval_needed("Approve changes?")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_continue_yn(self):
        result = detect_approval_needed("Continue? (y/n)")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_overwrite_question(self):
        result = detect_approval_needed("Overwrite existing file?")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_delete_question(self):
        result = detect_approval_needed("Delete all records?")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_replace_question(self):
        result = detect_approval_needed("Replace current config?")
        assert result["needs_approval"] is True
        assert result["suggested_response"] == "y"

    def test_multiline_with_approval(self):
        pane_text = "\n".join([
            "Running test suite...",
            "Found existing config.",
            "Overwrite existing file?",
            "",
        ])
        result = detect_approval_needed(pane_text)
        assert result["needs_approval"] is True

    # ── 検知しないケース ─────────────────────────────────────────────────────

    def test_empty_string(self):
        result = detect_approval_needed("")
        assert result["needs_approval"] is False
        assert result["pattern_matched"] is None

    def test_normal_output(self):
        result = detect_approval_needed("Building project... done.")
        assert result["needs_approval"] is False

    def test_shell_prompt(self):
        result = detect_approval_needed("user@host:~/project$ ")
        assert result["needs_approval"] is False

    def test_progress_output(self):
        result = detect_approval_needed("Downloading 100%... complete")
        assert result["needs_approval"] is False

    def test_log_line(self):
        result = detect_approval_needed("[INFO] Task completed successfully")
        assert result["needs_approval"] is False

    # ── 戻り値の構造確認 ─────────────────────────────────────────────────────

    def test_return_keys_when_detected(self):
        result = detect_approval_needed("[Y/n]")
        assert "needs_approval" in result
        assert "pattern_matched" in result
        assert "suggested_response" in result

    def test_return_keys_when_not_detected(self):
        result = detect_approval_needed("no approval here")
        assert "needs_approval" in result
        assert "pattern_matched" in result
        assert "suggested_response" in result

    def test_pattern_matched_is_string_when_detected(self):
        result = detect_approval_needed("[Y/n]")
        assert isinstance(result["pattern_matched"], str)

    def test_pattern_matched_is_none_when_not_detected(self):
        result = detect_approval_needed("no approval here")
        assert result["pattern_matched"] is None

    def test_case_insensitive_overwrite(self):
        result = detect_approval_needed("OVERWRITE FILE?")
        assert result["needs_approval"] is True

    def test_case_insensitive_delete(self):
        result = detect_approval_needed("delete this item?")
        assert result["needs_approval"] is True
