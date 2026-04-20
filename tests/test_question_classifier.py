#!/usr/bin/env python3
"""
test_question_classifier.py — question_classifier モジュールのユニットテスト
"""

import sys
from pathlib import Path

# スクリプトのディレクトリをPATHに追加
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from question_classifier import classify_question


def test_classify_auto_approve_bug():
    """技術的バグ修正は auto_approve"""
    question = "技術的なバグ修正について承認をお願いします"
    result = classify_question(question, {})
    assert result == "auto_approve"
    print("✓ Auto-approve for bug fix detected")


def test_classify_auto_approve_restart():
    """supervisor再起動は auto_approve"""
    question = "supervisorを再起動してもいいですか？"
    result = classify_question(question, {})
    assert result == "auto_approve"
    print("✓ Auto-approve for supervisor restart detected")


def test_classify_needs_review_architecture():
    """アーキテクチャ選択は needs_review"""
    question = "このアーキテクチャ設計で進めてもいいですか？"
    result = classify_question(question, {})
    assert result == "needs_review"
    print("✓ Needs review for architecture decision detected")


def test_classify_escalate_product():
    """プロダクト方向性は escalate"""
    question = "プロダクト方向性をどう決めるべき？"
    result = classify_question(question, {})
    assert result == "escalate"
    print("✓ Escalate for product direction detected")


def test_classify_escalate_team():
    """チーム設定は escalate"""
    question = "チームメンバーを追加してもいい？"
    result = classify_question(question, {})
    assert result == "escalate"
    print("✓ Escalate for team setting detected")


def test_classify_unknown():
    """分類できない質問は unknown"""
    question = "今日の天気はどう？"
    result = classify_question(question, {})
    assert result == "unknown"
    print("✓ Unknown classification for unrelated question")


if __name__ == "__main__":
    test_classify_auto_approve_bug()
    test_classify_auto_approve_restart()
    test_classify_needs_review_architecture()
    test_classify_escalate_product()
    test_classify_escalate_team()
    test_classify_unknown()
    print("\n✅ All question_classifier tests passed!")
