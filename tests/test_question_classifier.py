"""
test_question_classifier.py — Wave25 質問分類ロジックテスト
7カテゴリ分類の動作確認
"""

import pytest
from workflow.models.question import (
    QuestionCategory,
    ClassificationResult,
    SupportContext,
)
from workflow.services.question_classifier import (
    QuestionClassifier,
    ClassificationRules,
    ContextAnalyzer,
    classify_question,
    classify_question_with_details,
)


class TestClassificationRules:
    """キーワードマッチングルールのテスト"""

    def test_bug_keywords_match(self):
        """バグキーワードのマッチング"""
        assert ClassificationRules.match_keywords(
            "アプリがクラッシュします", ClassificationRules.BUG_KEYWORDS
        )
        assert ClassificationRules.match_keywords(
            "I got an error 500", ClassificationRules.BUG_KEYWORDS
        )
        assert not ClassificationRules.match_keywords(
            "機能の使い方を教えてください", ClassificationRules.BUG_KEYWORDS
        )

    def test_faq_keywords_match(self):
        """FAQ候補キーワードのマッチング"""
        assert ClassificationRules.match_keywords(
            "レート制限とは何ですか？", ClassificationRules.FAQ_KEYWORDS
        )
        assert ClassificationRules.match_keywords(
            "How do I set up the API?", ClassificationRules.FAQ_KEYWORDS
        )
        assert not ClassificationRules.match_keywords(
            "セキュリティ脆弱性の報告", ClassificationRules.FAQ_KEYWORDS
        )

    def test_escalation_keywords_match(self):
        """エスカレーション必要なキーワードのマッチング"""
        assert ClassificationRules.match_keywords(
            "セキュリティ脆弱性を発見しました", ClassificationRules.ESCALATION_KEYWORDS
        )
        assert ClassificationRules.match_keywords(
            "Enterprise SLA の交渉", ClassificationRules.ESCALATION_KEYWORDS
        )

    def test_priority_extraction(self):
        """優先度キーワード抽出"""
        assert ClassificationRules.extract_priority("これは緊急です") == "high"
        assert ClassificationRules.extract_priority("critical bug found") == "critical"
        assert ClassificationRules.extract_priority("普通の質問です") == "normal"


class TestContextAnalyzer:
    """文脈分析のテスト"""

    def test_enterprise_company_adjustment(self):
        """企業規模別優先度調整"""
        context = SupportContext(
            question="テスト", company_size="enterprise", is_paying_customer=True
        )
        analysis = ContextAnalyzer.analyze(context, QuestionCategory.AUTO_APPROVE)
        assert analysis["company_size_adjustment"] == 0.1

    def test_customer_history_factor(self):
        """顧客履歴に基づく自動応答可能性調整"""
        context = SupportContext(
            question="テスト", previous_support_count=6, is_paying_customer=True
        )
        analysis = ContextAnalyzer.analyze(context, QuestionCategory.AUTO_RESPOND)
        assert analysis["customer_history_factor"] == 1.1


class TestQuestionClassifier:
    """メイン分類器のテスト"""

    def test_critical_security_bug_classification(self):
        """セキュリティバグ（最高優先度）"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify(
            "セキュリティ脆弱性: パスワード保存時のバグが見つかった"
        )
        assert result.category == QuestionCategory.ESCALATE_PRIORITY
        assert result.confidence >= 0.95

    def test_bug_report_critical_classification(self):
        """高優先度バグレポート"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify("critical: システムがダウンしています")
        assert result.category == QuestionCategory.ESCALATE_PRIORITY
        assert "bug_keywords" in result.matched_rules

    def test_bug_report_normal_classification(self):
        """通常優先度バグレポート"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify("ボタンをクリックしてもエラーが出ます")
        assert result.category == QuestionCategory.AUTO_APPROVE
        assert result.confidence >= 0.85

    def test_faq_classification(self):
        """FAQ候補の分類"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify("APIの使い方を教えてください")
        assert result.category == QuestionCategory.AUTO_RESPOND

    def test_escalation_enterprise_classification(self):
        """エンタープライズ顧客のエスカレーション"""
        classifier = QuestionClassifier(use_claude_api=False)
        context = SupportContext(
            question="Enterprise SLA の契約内容について",
            company_size="enterprise",
        )
        result = classifier.classify(
            "Enterprise SLA の契約内容について変更したい", context
        )
        assert result.category in [
            QuestionCategory.ESCALATE_SPECIALTY,
            QuestionCategory.NEEDS_REVIEW,
        ]

    def test_clarification_needed_low_confidence(self):
        """信頼度が低い場合は明確化を要求"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify("何かあります")  # 曖昧な質問
        # 信頼度が低い場合は明確化を要求または不明
        assert result.category in [
            QuestionCategory.CLARIFICATION_NEEDED,
            QuestionCategory.UNKNOWN,
        ]

    def test_context_analysis_integration(self):
        """文脈統合テスト"""
        classifier = QuestionClassifier(use_claude_api=False)
        context = SupportContext(
            question="バグ報告",
            customer_id=123,
            company_size="enterprise",
            is_paying_customer=True,
            previous_support_count=10,
        )
        result = classifier.classify("データが削除されてしまいました", context)
        assert isinstance(result, ClassificationResult)
        assert result.confidence > 0


class TestPublicAPIs:
    """公開API（シンプルインターフェース）のテスト"""

    def test_classify_question_simple_api(self):
        """classify_question シンプルAPI"""
        category = classify_question("バグが発生しました")
        assert isinstance(category, QuestionCategory)

    def test_classify_question_with_context(self):
        """classify_question with context"""
        context = {
            "customer_id": 123,
            "company_size": "enterprise",
            "is_paying_customer": True,
        }
        category = classify_question("API の設定方法を教えてください", context)
        assert isinstance(category, QuestionCategory)

    def test_classify_question_with_details(self):
        """classify_question_with_details 詳細API"""
        result = classify_question_with_details("セキュリティ問題を報告します")
        assert isinstance(result, ClassificationResult)
        assert result.confidence >= 0.0
        assert result.category in list(QuestionCategory)


class TestRecommendedActions:
    """推奨アクションのテスト"""

    def test_auto_respond_action(self):
        """AUTO_RESPOND のアクション"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify("API の使用方法は？")
        assert "FAQ" in result.recommended_action

    def test_escalate_priority_action(self):
        """ESCALATE_PRIORITY のアクション"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify("critical: システム停止")
        assert "escalate" in result.recommended_action.lower()

    def test_needs_review_action(self):
        """NEEDS_REVIEW のアクション"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify(
            "複雑なカスタマイズについて相談したいです"
        )
        # needs_review または他のカテゴリ
        assert result.recommended_action is not None


class TestConfidenceThreshold:
    """信頼度閾値のテスト"""

    def test_is_confident_above_threshold(self):
        """is_confident: 閾値以上"""
        result = ClassificationResult(
            category=QuestionCategory.AUTO_RESPOND,
            confidence=0.85,
            matched_rules=["faq_keywords"],
            intent_details={"intent": "faq"},
            recommended_action="Provide FAQ response",
        )
        assert result.is_confident(0.7)

    def test_is_confident_below_threshold(self):
        """is_confident: 閾値以下"""
        result = ClassificationResult(
            category=QuestionCategory.CLARIFICATION_NEEDED,
            confidence=0.5,
            matched_rules=[],
            intent_details={"intent": "unknown"},
            recommended_action="Request clarification",
        )
        assert not result.is_confident(0.7)


class TestMultipleRuleMatches:
    """複数ルールマッチのテスト"""

    def test_bug_and_escalation_keywords(self):
        """バグ + エスカレーションキーワード"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify(
            "セキュリティバグ: パスワードが平文で保存されています"
        )
        assert result.category == QuestionCategory.ESCALATE_PRIORITY
        assert "bug_keywords" in result.matched_rules
        assert "escalation_keywords" in result.matched_rules

    def test_escalation_only_keywords(self):
        """エスカレーションキーワードのみ"""
        classifier = QuestionClassifier(use_claude_api=False)
        result = classifier.classify(
            "Enterprise プランの高度なカスタマイズについて"
        )
        assert result.category in [
            QuestionCategory.ESCALATE_SPECIALTY,
            QuestionCategory.NEEDS_REVIEW,
        ]
