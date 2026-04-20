#!/usr/bin/env python3
"""
test_auto_responder.py — auto_responder モジュールのユニットテスト
"""

import sys
from pathlib import Path

# スクリプトのディレクトリをPATHに追加
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from auto_responder import generate_response, format_escalation_message


def test_generate_response_auto_approve():
    """auto_approve カテゴリの応答を生成"""
    question = "バグ修正について承認をお願いします"
    response = generate_response(question, "auto_approve", {}, "pane:0.1")
    assert response is not None
    assert "✓" in response
    assert "自動承認" in response
    print(f"✓ Auto-approve response generated: {response[:50]}...")


def test_generate_response_needs_review():
    """needs_review カテゴリの応答を生成"""
    question = "このアーキテクチャで進めていい？"
    response = generate_response(question, "needs_review", {}, "pane:0.1")
    assert response is not None
    assert "レビュー必要" in response
    print(f"✓ Needs-review response generated: {response[:50]}...")


def test_generate_response_escalate():
    """escalate カテゴリの応答は None（ユーザーエスカレーション）"""
    question = "プロダクト方向性をどうする？"
    response = generate_response(question, "escalate", {}, "pane:0.1")
    assert response is None
    print("✓ Escalate response is None (user escalation)")


def test_format_escalation_message():
    """ユーザーへのエスカレーションメッセージをフォーマット"""
    question = "プロダクト方向性について質問"
    context = {
        'context_before': ['line1', 'line2'],
        'context_after': ['line3', 'line4'],
    }
    message = format_escalation_message(question, context, "pane:0.1")
    assert "⚠️" in message
    assert "ユーザー確認が必要" in message
    assert "pane:0.1" in message
    assert question in message
    print(f"✓ Escalation message formatted")


def test_generate_response_empty():
    """空の質問・カテゴリは None を返す"""
    response = generate_response("", "auto_approve", {}, "pane:0.1")
    assert response is None
    print("✓ Empty question returns None")


if __name__ == "__main__":
    test_generate_response_auto_approve()
    test_generate_response_needs_review()
    test_generate_response_escalate()
    test_format_escalation_message()
    test_generate_response_empty()
    print("\n✅ All auto_responder tests passed!")
