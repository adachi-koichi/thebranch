"""
question_classifier.py — Wave25 カスタマーサポート質問分類サービス
NLU + Claude API を使用した自然言語理解と分類
"""

import os
import json
import re
from typing import Optional, Dict, List, Tuple
from dataclasses import asdict

try:
    from anthropic import Anthropic, APIError
except ImportError:
    Anthropic = None
    APIError = Exception

from workflow.models.question import (
    QuestionCategory,
    ClassificationResult,
    SupportContext,
)


class ClassificationRules:
    """キーワードベースの分類ルール定義"""

    # バグ報告パターン
    BUG_KEYWORDS = [
        "バグ", "bug", "error", "エラー", "crash", "クラッシュ",
        "data loss", "データ削除", "fail", "失敗", "not working",
        "動かない", "broken", "割れた", "issue", "問題", "glitch",
        "ダウン", "停止", "down"
    ]

    # FAQ候補キーワード
    FAQ_KEYWORDS = [
        "レート制限", "rate limit", "API", "方法", "方法は",
        "設定", "設定方法", "使い方", "使う", "使用方法",
        "料金", "価格", "費用", "cost", "pricing",
        "機能", "feature", "セットアップ", "setup",
        "ドキュメント", "documentation", "マニュアル", "manual",
        "統合", "integration", "接続", "connect"
    ]

    # エスカレーション必要なキーワード
    ESCALATION_KEYWORDS = [
        "セキュリティ", "security", "漏洩", "leak", "vulnerability",
        "脆弱性", "高度な", "複雑", "複雑な", "advanced",
        "カスタマイズ", "customize", "enterprise", "エンタープライズ",
        "sla", "SLA", "保証", "guarantee", "contract",
        "契約", "discount", "割引", "交渉", "negotiate"
    ]

    # 優先度関連キーワード
    PRIORITY_KEYWORDS = {
        "high": ["高優先度", "urgent", "緊急", "すぐに", "すぐ", "immediately", "asap"],
        "critical": ["critical", "致命的", "システムダウン", "システム停止", "ダウン", "停止", "完全に"],
    }

    @classmethod
    def match_keywords(cls, text: str, keywords: List[str]) -> bool:
        """テキストがキーワードリストのいずれかにマッチするか判定"""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)

    @classmethod
    def extract_priority(cls, text: str) -> str:
        """優先度キーワードを抽出"""
        text_lower = text.lower()
        for level, keywords in cls.PRIORITY_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                return level
        return "normal"


class ContextAnalyzer:
    """カスタマーサポート文脈分析"""

    @staticmethod
    def analyze(context: SupportContext, category: QuestionCategory) -> Dict:
        """文脈情報から分析結果を生成"""
        analysis = {
            "company_size_adjustment": 0.0,
            "customer_history_factor": 1.0,
            "urgency": "normal",
        }

        # 企業規模別優先度調整
        if context.company_size == "enterprise":
            analysis["company_size_adjustment"] = 0.1
        elif context.company_size == "mid":
            analysis["company_size_adjustment"] = 0.05

        # 顧客履歴に基づく自動応答可能性調整
        if context.previous_support_count > 5:
            analysis["customer_history_factor"] = 1.1
        elif context.is_paying_customer:
            analysis["customer_history_factor"] = 0.95

        # 緊急度判定
        if context.previous_support_count == 0:
            analysis["urgency"] = "new_customer"
        elif context.is_paying_customer and category in [
            QuestionCategory.ESCALATE_PRIORITY,
            QuestionCategory.ESCALATE_SPECIALTY,
        ]:
            analysis["urgency"] = "high"

        return analysis


class NLUClassifier:
    """自然言語理解を使用した分類器（Claude API連携）"""

    def __init__(self, api_key: Optional[str] = None):
        """初期化"""
        if Anthropic is None:
            raise ImportError("anthropic package is required. Install: pip install anthropic")

        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-opus-4-7"

    def classify_with_nlu(self, question: str) -> Tuple[Dict, float]:
        """
        Claude API を使用してNLU分析を実行
        戻り値: (intent_details, confidence)
        """
        prompt = f"""
カスタマーサポート質問を分析して、以下をJSON形式で返してください。

質問: "{question}"

JSON形式で以下の構造で返してください:
{{
  "intent": "バグ報告|機能説明|価格相談|セキュリティ|カスタマイズ|不明|その他",
  "severity": "critical|high|medium|low",
  "sentiment": "frustrated|neutral|satisfied|angry",
  "entities": {{"product": "...", "feature": "...", "error_type": "..."}},
  "confidence": 0.0-1.0
}}
"""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            # JSONを抽出
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                intent_details = json.loads(json_match.group())
                confidence = float(intent_details.get("confidence", 0.5))
                return intent_details, confidence

            return {"intent": "unknown"}, 0.5

        except APIError as e:
            return {"intent": "api_error", "error": str(e)}, 0.3


class QuestionClassifier:
    """Wave25 カスタマーサポート質問分類メインクラス"""

    def __init__(self, use_claude_api: bool = True, api_key: Optional[str] = None):
        """初期化"""
        self.use_claude_api = use_claude_api
        self.nlu_classifier = None

        if use_claude_api and Anthropic is not None:
            try:
                self.nlu_classifier = NLUClassifier(api_key)
            except (ImportError, ValueError):
                self.nlu_classifier = None

    def classify(
        self, question: str, context: Optional[SupportContext] = None
    ) -> ClassificationResult:
        """
        質問を分類する

        Step 1. キーワードマッチング
        Step 2. NLU意図認識（Claude API）
        Step 3. コンテキスト判定
        Step 4. 確信度評価
        """
        if context is None:
            context = SupportContext(question=question)

        matched_rules = []

        # Step 1: キーワードマッチング
        has_bug = ClassificationRules.match_keywords(question, ClassificationRules.BUG_KEYWORDS)
        has_faq = ClassificationRules.match_keywords(question, ClassificationRules.FAQ_KEYWORDS)
        has_escalation = ClassificationRules.match_keywords(
            question, ClassificationRules.ESCALATION_KEYWORDS
        )
        has_security = any(
            kw in question.lower() for kw in ["セキュリティ", "security", "脆弱性", "漏洩"]
        )

        if has_bug:
            matched_rules.append("bug_keywords")

        if has_faq:
            matched_rules.append("faq_keywords")

        if has_escalation:
            matched_rules.append("escalation_keywords")

        if has_security:
            matched_rules.append("security_keywords")

        # 複合キーワードマッチング：バグ + セキュリティは最高優先度
        if has_bug and has_security:
            return ClassificationResult(
                category=QuestionCategory.ESCALATE_PRIORITY,
                confidence=0.95,
                matched_rules=matched_rules,
                intent_details={"intent": "critical_security_bug", "severity": "critical"},
                recommended_action="Escalate to senior security support with 15min SLA",
            )

        # バグレポートの単独処理
        if has_bug:
            priority = ClassificationRules.extract_priority(question)

            if priority in ["critical", "high"]:
                return ClassificationResult(
                    category=QuestionCategory.ESCALATE_PRIORITY,
                    confidence=0.95,
                    matched_rules=matched_rules,
                    intent_details={"intent": "critical_bug", "priority": priority},
                    recommended_action="Escalate to senior support with 30min SLA",
                )
            else:
                return ClassificationResult(
                    category=QuestionCategory.AUTO_APPROVE,
                    confidence=0.85,
                    matched_rules=matched_rules,
                    intent_details={"intent": "bug_report", "priority": "normal"},
                    recommended_action="Auto-approve and notify customer",
                )

        # Step 2: NLU意図認識
        intent_details = {"intent": "unknown"}
        confidence = 0.5

        if self.nlu_classifier:
            intent_details, confidence = self.nlu_classifier.classify_with_nlu(question)
        else:
            # NLU なしのシンプル分類
            intent_details = self._simple_intent_analysis(question)
            if matched_rules:
                confidence = 0.8 if "bug_keywords" in matched_rules else 0.75
            else:
                confidence = 0.4

        # Step 3: コンテキスト判定
        context_analysis = ContextAnalyzer.analyze(
            context, self._predict_category(matched_rules, intent_details)
        )

        # Step 4: 確信度評価と分類決定
        category = self._route_to_category(
            question, matched_rules, intent_details, context, confidence
        )

        # 信頼度が低い場合は明確化を要求
        if confidence < 0.7 and category == QuestionCategory.UNKNOWN:
            category = QuestionCategory.CLARIFICATION_NEEDED
            confidence = min(confidence + 0.1, 0.7)

        return ClassificationResult(
            category=category,
            confidence=confidence,
            matched_rules=matched_rules,
            intent_details=intent_details,
            recommended_action=self._get_recommended_action(category, confidence),
        )

    def _simple_intent_analysis(self, question: str) -> Dict:
        """NLU なしのシンプルな意図分析"""
        question_lower = question.lower()

        if any(kw in question_lower for kw in ClassificationRules.BUG_KEYWORDS):
            return {"intent": "bug_report"}
        elif any(kw in question_lower for kw in ClassificationRules.FAQ_KEYWORDS):
            return {"intent": "faq_inquiry"}
        elif any(kw in question_lower for kw in ClassificationRules.ESCALATION_KEYWORDS):
            return {"intent": "escalation"}
        else:
            return {"intent": "unknown"}

    def _predict_category(self, matched_rules: List[str], intent_details: Dict) -> QuestionCategory:
        """マッチしたルールと意図から予測カテゴリを判定"""
        if "escalation_keywords" in matched_rules:
            return QuestionCategory.ESCALATE_SPECIALTY
        elif "bug_keywords" in matched_rules:
            return QuestionCategory.AUTO_APPROVE
        elif "faq_keywords" in matched_rules:
            return QuestionCategory.AUTO_RESPOND
        else:
            return QuestionCategory.UNKNOWN

    def _route_to_category(
        self,
        question: str,
        matched_rules: List[str],
        intent_details: Dict,
        context: SupportContext,
        confidence: float,
    ) -> QuestionCategory:
        """複合ロジックで最適なカテゴリに振り分け"""

        # セキュリティ関連はエスカレーション優先度
        if "security" in intent_details.get("intent", "").lower() or any(
            kw in question.lower() for kw in ["セキュリティ", "security", "脆弱性", "漏洩"]
        ):
            return QuestionCategory.ESCALATE_PRIORITY

        # マッチしたルールに基づく振り分け（キーワードマッチを優先）
        if "escalation_keywords" in matched_rules:
            # 企業規模に応じた振り分け
            if context.company_size == "enterprise":
                return QuestionCategory.ESCALATE_SPECIALTY
            else:
                return QuestionCategory.NEEDS_REVIEW

        if "bug_keywords" in matched_rules:
            severity = intent_details.get("severity", "medium")
            if severity in ["critical", "high"]:
                return QuestionCategory.ESCALATE_PRIORITY
            else:
                return QuestionCategory.AUTO_APPROVE

        if "faq_keywords" in matched_rules:
            return QuestionCategory.AUTO_RESPOND

        # キーワードマッチがない場合は信頼度で判定
        if confidence < 0.7:
            return QuestionCategory.CLARIFICATION_NEEDED

        # デフォルト
        return QuestionCategory.UNKNOWN

    def _get_recommended_action(self, category: QuestionCategory, confidence: float) -> str:
        """カテゴリに応じた推奨アクションを生成"""
        actions = {
            QuestionCategory.AUTO_RESPOND: "Provide auto response from FAQ template",
            QuestionCategory.AUTO_APPROVE: "Auto-approve the request and notify customer",
            QuestionCategory.NEEDS_REVIEW: "Route to support team for human review",
            QuestionCategory.CLARIFICATION_NEEDED: "Request clarification from customer",
            QuestionCategory.ESCALATE_PRIORITY: "Escalate to senior support with high SLA",
            QuestionCategory.ESCALATE_SPECIALTY: "Route to specialized team",
            QuestionCategory.ESCALATE_MANAGEMENT: "Escalate to management/PM team",
            QuestionCategory.UNKNOWN: "Unable to classify - escalate to human agent",
        }
        return actions.get(category, "Manual review required")


# グローバルインスタンス
_classifier_instance: Optional[QuestionClassifier] = None


def get_classifier(use_claude_api: bool = True) -> QuestionClassifier:
    """グローバルな分類器インスタンスを取得"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = QuestionClassifier(use_claude_api=use_claude_api)
    return _classifier_instance


def classify_question(
    question: str, context: Optional[Dict] = None
) -> QuestionCategory:
    """
    質問を分類する（シンプルなAPI）

    Args:
        question: 顧客の質問文
        context: コンテキスト情報（dict）

    Returns:
        QuestionCategory
    """
    use_api = bool(os.environ.get("ANTHROPIC_API_KEY"))
    classifier = get_classifier(use_claude_api=use_api)

    # Dict から SupportContext への変換
    support_context = None
    if context:
        support_context = SupportContext(
            question=question,
            customer_id=context.get("customer_id"),
            company_size=context.get("company_size"),
            plan_type=context.get("plan_type"),
            previous_support_count=context.get("previous_support_count", 0),
            is_paying_customer=context.get("is_paying_customer", False),
        )

    result = classifier.classify(question, support_context)
    return result.category


def classify_question_with_details(
    question: str, context: Optional[Dict] = None
) -> ClassificationResult:
    """
    質問を分類して詳細情報も返す

    Args:
        question: 顧客の質問文
        context: コンテキスト情報（dict）

    Returns:
        ClassificationResult
    """
    use_api = bool(os.environ.get("ANTHROPIC_API_KEY"))
    classifier = get_classifier(use_claude_api=use_api)

    support_context = None
    if context:
        support_context = SupportContext(
            question=question,
            customer_id=context.get("customer_id"),
            company_size=context.get("company_size"),
            plan_type=context.get("plan_type"),
            previous_support_count=context.get("previous_support_count", 0),
            is_paying_customer=context.get("is_paying_customer", False),
        )

    return classifier.classify(question, support_context)
