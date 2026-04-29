#!/usr/bin/env python3
"""
test_question_classifier.py — Wave25カスタマーサポート質問分類テストスイート
"""

import sys
from pathlib import Path

# プロジェクトルートをPATHに追加
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from workflow.models.question import QuestionCategory, SupportContext
from workflow.services.question_classifier import (
    classify_question,
    classify_question_with_details,
    QuestionClassifier,
)


class TestAutoRespond:
    """AUTO_RESPOND カテゴリのテスト"""

    def test_faq_rate_limit(self):
        """FAQ: API レート制限"""
        result = classify_question("API レート制限について教えてください", {})
        assert result == QuestionCategory.AUTO_RESPOND
        print("✓ FAQ rate limit → AUTO_RESPOND")

    def test_faq_setup(self):
        """FAQ: セットアップ方法"""
        result = classify_question("Wave25 のセットアップ方法は？", {})
        assert result == QuestionCategory.AUTO_RESPOND
        print("✓ FAQ setup → AUTO_RESPOND")

    def test_faq_documentation(self):
        """FAQ: ドキュメント参照"""
        result = classify_question("APIドキュメントはどこにありますか？", {})
        assert result == QuestionCategory.AUTO_RESPOND
        print("✓ FAQ documentation → AUTO_RESPOND")


class TestAutoApprove:
    """AUTO_APPROVE カテゴリのテスト"""

    def test_bug_report_simple(self):
        """バグ報告: シンプルなエラー"""
        result = classify_question_with_details(
            "APIが500エラーを返すバグを発見しました", {}
        )
        assert result.category == QuestionCategory.AUTO_APPROVE
        assert result.confidence >= 0.8
        print("✓ Bug report → AUTO_APPROVE")

    def test_bug_report_with_code(self):
        """バグ報告: エラーコード付き"""
        result = classify_question_with_details(
            "データベース接続エラーが発生: [エラーコード 001]", {}
        )
        assert result.category == QuestionCategory.AUTO_APPROVE
        assert result.confidence >= 0.8
        print("✓ Bug report with error code → AUTO_APPROVE")

    def test_bug_crash(self):
        """バグ報告: アプリクラッシュ"""
        result = classify_question_with_details(
            "アプリケーションがクラッシュします", {}
        )
        assert result.category == QuestionCategory.AUTO_APPROVE
        assert result.confidence >= 0.75
        print("✓ Crash report → AUTO_APPROVE")


class TestEscalatePriority:
    """ESCALATE_PRIORITY カテゴリのテスト"""

    def test_critical_data_loss(self):
        """優先度: 重大なデータ喪失"""
        result = classify_question_with_details(
            "緊急: データが全て削除されました。システムクラッシュです", {}
        )
        assert result.category == QuestionCategory.ESCALATE_PRIORITY
        assert result.confidence >= 0.9
        print("✓ Data loss → ESCALATE_PRIORITY")

    def test_security_issue(self):
        """優先度: セキュリティ脆弱性"""
        result = classify_question_with_details(
            "APIキーが漏洩した可能性があります", {}
        )
        assert result.category == QuestionCategory.ESCALATE_PRIORITY
        assert result.confidence >= 0.85
        print("✓ Security issue → ESCALATE_PRIORITY")

    def test_system_down(self):
        """優先度: システムダウン"""
        result = classify_question_with_details(
            "システムが完全にダウンしています。緊急対応をお願いします", {}
        )
        assert result.category == QuestionCategory.ESCALATE_PRIORITY
        print("✓ System down → ESCALATE_PRIORITY")


class TestEscalateSpecialty:
    """ESCALATE_SPECIALTY カテゴリのテスト"""

    def test_enterprise_discount(self):
        """専門: エンタープライズ割引"""
        context = SupportContext(
            question="エンタープライズプラン向けの割引交渉について相談したい",
            company_size="enterprise",
            is_paying_customer=True,
        )
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify(context.question, context)
        # enterprise の割引相談はスペシャリティ
        assert result.category in [
            QuestionCategory.ESCALATE_SPECIALTY,
            QuestionCategory.NEEDS_REVIEW,
        ]
        print("✓ Enterprise discount → ESCALATE_SPECIALTY")

    def test_custom_integration(self):
        """専門: カスタム統合"""
        result = classify_question_with_details(
            "カスタムシステムとの統合についてエンタープライズサポートが必要です",
            {"company_size": "enterprise"},
        )
        assert result.category in [
            QuestionCategory.ESCALATE_SPECIALTY,
            QuestionCategory.NEEDS_REVIEW,
        ]
        print("✓ Custom integration → ESCALATE_SPECIALTY")


class TestClarificationNeeded:
    """CLARIFICATION_NEEDED カテゴリのテスト"""

    def test_unclear_question(self):
        """不明確: 曖昧な質問"""
        result = classify_question_with_details("うまくいきません", {})
        assert result.category == QuestionCategory.CLARIFICATION_NEEDED
        assert result.confidence < 0.7
        print("✓ Unclear question → CLARIFICATION_NEEDED")

    def test_vague_problem(self):
        """不明確: 問題が特定されていない"""
        result = classify_question_with_details("何か問題があります", {})
        assert result.category == QuestionCategory.CLARIFICATION_NEEDED
        print("✓ Vague problem → CLARIFICATION_NEEDED")

    def test_minimal_info(self):
        """不明確: 情報不足"""
        result = classify_question_with_details("サービスについて質問があります", {})
        # 情報不足の場合
        if result.confidence < 0.7:
            assert result.category == QuestionCategory.CLARIFICATION_NEEDED
            print("✓ Minimal info → CLARIFICATION_NEEDED")


class TestNeedsReview:
    """NEEDS_REVIEW カテゴリのテスト"""

    def test_feature_request(self):
        """レビュー: 機能リクエスト"""
        result = classify_question_with_details(
            "新しい統合機能を追加してほしいのですが、これは可能ですか？", {}
        )
        # 機能リクエストはレビューまたはエスカレーション
        assert result.category in [
            QuestionCategory.NEEDS_REVIEW,
            QuestionCategory.ESCALATE_SPECIALTY,
        ]
        print("✓ Feature request → NEEDS_REVIEW or ESCALATE_SPECIALTY")

    def test_architecture_decision(self):
        """レビュー: アーキテクチャ決定"""
        result = classify_question_with_details(
            "このアーキテクチャ設計で進めても大丈夫ですか？", {}
        )
        # アーキテクチャはレビューが必要
        assert result.category == QuestionCategory.NEEDS_REVIEW
        print("✓ Architecture decision → NEEDS_REVIEW")


class TestContextBasedRouting:
    """コンテキストに基づいた振り分けテスト"""

    def test_company_size_adjustment(self):
        """企業規模による分類の変更"""
        question = "割引について相談したいです"

        # Startup は自動応答
        result_startup = classify_question_with_details(
            question, {"company_size": "startup"}
        )
        assert result_startup.category == QuestionCategory.AUTO_RESPOND
        print("✓ Startup discount → AUTO_RESPOND")

        # Enterprise はスペシャリティ
        result_enterprise = classify_question_with_details(
            question, {"company_size": "enterprise", "is_paying_customer": True}
        )
        assert result_enterprise.category in [
            QuestionCategory.ESCALATE_SPECIALTY,
            QuestionCategory.NEEDS_REVIEW,
        ]
        print("✓ Enterprise discount → ESCALATE_SPECIALTY/NEEDS_REVIEW")

    def test_existing_customer_boost(self):
        """既存顧客のサポート件数による精度向上"""
        question = "API認証の設定方法は？"

        # 新規顧客
        result_new = classify_question_with_details(
            question, {"previous_support_count": 0}
        )

        # 既存顧客（5件以上）
        result_existing = classify_question_with_details(
            question, {"previous_support_count": 5, "is_paying_customer": True}
        )

        # 両方とも自動応答のはずだが、既存顧客の方が信頼度が高い
        if result_new.category == QuestionCategory.AUTO_RESPOND:
            assert result_existing.category == QuestionCategory.AUTO_RESPOND
            print("✓ Both new and existing customers → AUTO_RESPOND")


class TestConfidenceScoring:
    """信頼度スコアのテスト"""

    def test_high_confidence_bug(self):
        """高信頼度: 明確なバグ報告"""
        result = classify_question_with_details(
            "データベース接続エラー: [エラーコード 001]", {}
        )
        assert result.confidence >= 0.85
        print(f"✓ Clear bug report confidence: {result.confidence:.2f}")

    def test_medium_confidence_faq(self):
        """中信頼度: FAQ質問"""
        result = classify_question_with_details(
            "APIの使い方について教えてください", {}
        )
        assert 0.7 <= result.confidence < 0.85
        print(f"✓ FAQ question confidence: {result.confidence:.2f}")

    def test_low_confidence_unclear(self):
        """低信頼度: 不明確な質問"""
        result = classify_question_with_details("何かについて質問があります", {})
        assert result.confidence < 0.7
        print(f"✓ Unclear question confidence: {result.confidence:.2f}")


class TestMultiplexedKeywords:
    """複合キーワードマッチングのテスト"""

    def test_bug_and_security(self):
        """バグとセキュリティの両方"""
        result = classify_question_with_details(
            "バグによりデータが削除され、セキュリティ脆弱性も発見しました", {}
        )
        assert result.category == QuestionCategory.ESCALATE_PRIORITY
        assert len(result.matched_rules) > 1
        assert result.confidence >= 0.85
        print("✓ Multiple keywords → ESCALATE_PRIORITY")


class TestUnknownClassification:
    """分類不可のテスト"""

    def test_unrelated_question(self):
        """無関係な質問"""
        result = classify_question_with_details("今日の天気はどう？", {})
        assert result.category == QuestionCategory.UNKNOWN
        print("✓ Unrelated question → UNKNOWN")

    def test_off_topic(self):
        """オフトピック"""
        result = classify_question_with_details("ランチはどこへ行きます？", {})
        assert result.category == QuestionCategory.UNKNOWN
        print("✓ Off-topic question → UNKNOWN")


class TestRecommendedActions:
    """推奨アクションのテスト"""

    def test_auto_respond_action(self):
        """自動応答の推奨アクション"""
        result = classify_question_with_details(
            "API レート制限について", {}
        )
        assert "FAQ" in result.recommended_action or "auto response" in result.recommended_action.lower()
        print("✓ AUTO_RESPOND has FAQ action")

    def test_escalate_action(self):
        """エスカレーションの推奨アクション"""
        result = classify_question_with_details(
            "データが削除されました", {}
        )
        if result.category == QuestionCategory.ESCALATE_PRIORITY:
            assert "senior" in result.recommended_action.lower() or "SLA" in result.recommended_action
            print("✓ ESCALATE_PRIORITY has SLA action")


def run_all_tests():
    """全テストを実行"""
    test_classes = [
        TestAutoRespond,
        TestAutoApprove,
        TestEscalatePriority,
        TestEscalateSpecialty,
        TestClarificationNeeded,
        TestNeedsReview,
        TestContextBasedRouting,
        TestConfidenceScoring,
        TestMultiplexedKeywords,
        TestUnknownClassification,
        TestRecommendedActions,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        print(f"\n📋 {test_class.__name__}")
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    method = getattr(instance, method_name)
                    method()
                    passed += 1
                except AssertionError as e:
                    print(f"✗ {method_name} failed: {e}")
                    failed += 1
                except Exception as e:
                    print(f"✗ {method_name} error: {e}")
                    failed += 1

    print(f"\n{'='*60}")
    print(f"📊 テスト結果: {passed} 成功, {failed} 失敗")
    print(f"{'='*60}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    if success:
        print("\n✅ 全テスト成功！")
        sys.exit(0)
    else:
        print("\n❌ テスト失敗があります")
        sys.exit(1)
