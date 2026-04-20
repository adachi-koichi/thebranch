#!/usr/bin/env python3
"""
test_question_detector.py — question_detector モジュールのユニットテスト
"""

import sys
from pathlib import Path

# スクリプトのディレクトリをPATHに追加
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from question_detector import detect_question, extract_question_context


def test_detect_question_english_yes_no():
    """英語の Yes/No ダイアログを検出"""
    content = "Some output\nDo you want to proceed? [Y/n] ❯ "
    result = detect_question(content)
    assert result['detected'] == True
    assert 'Do you want' in result['question_text']
    print("✓ English Yes/No question detected")


def test_detect_question_japanese():
    """日本語の質問を検出"""
    content = "実装が完了しました。\n承認してもよろしいですか？ ❯ "
    result = detect_question(content)
    assert result['detected'] == True
    assert 'ですか' in result['question_text']
    print("✓ Japanese question detected")


def test_detect_question_how():
    """How で始まる英語疑問文を検出"""
    content = "現在の状況:\nHow should I approach this problem? ❯ "
    result = detect_question(content)
    assert result['detected'] == True
    assert 'How' in result['question_text']
    print("✓ How question detected")


def test_no_question():
    """質問がない場合は検出しない"""
    content = "Processing...\nDone\n> "
    result = detect_question(content)
    assert result['detected'] == False
    print("✓ No question correctly identified")


def test_extract_question_context():
    """質問コンテキストを抽出"""
    content = "Line 1\nLine 2\nLine 3\nDo you want to continue? [Y/n]"
    context = extract_question_context(content)
    assert context['question_detected'] == True
    assert 'Do you want' in context['question_text']
    assert len(context['context_before']) >= 1
    print("✓ Question context extracted")


if __name__ == "__main__":
    test_detect_question_english_yes_no()
    test_detect_question_japanese()
    test_detect_question_how()
    test_no_question()
    test_extract_question_context()
    print("\n✅ All question_detector tests passed!")
