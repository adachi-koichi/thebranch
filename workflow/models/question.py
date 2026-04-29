"""
question.py — カスタマーサポート質問分類モデル
Wave25 Phase 1 実装
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


class QuestionCategory(Enum):
    """サポート質問の分類カテゴリ（7つ）"""

    # Tier 1: 自動応答可能
    AUTO_RESPOND = "auto_respond"              # FAQ回答可能
    AUTO_APPROVE = "auto_approve"              # バグ修正・管理操作

    # Tier 2: レビュー必要
    NEEDS_REVIEW = "needs_review"              # アーキテクチャ・設計判定
    CLARIFICATION_NEEDED = "clarification"     # 質問の明確化必要

    # Tier 3: エスカレーション
    ESCALATE_PRIORITY = "escalate_priority"    # 高優先度エスカレーション
    ESCALATE_SPECIALTY = "escalate_specialty"  # 専門チームへ振分
    ESCALATE_MANAGEMENT = "escalate_mgmt"      # 経営層エスカレーション

    # その他
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """質問分類の結果"""
    category: QuestionCategory
    confidence: float                   # 0.0 - 1.0
    matched_rules: List[str]           # マッチしたルール一覧
    intent_details: Dict[str, Any]     # 意図分析の詳細
    recommended_action: str             # 推奨アクション

    def is_confident(self, threshold: float = 0.7) -> bool:
        """信頼度が閾値以上かを判定"""
        return self.confidence >= threshold


@dataclass
class SupportContext:
    """カスタマーサポートの文脈情報"""
    question: str
    customer_id: Optional[int] = None
    company_size: Optional[str] = None          # startup/smb/mid/enterprise
    plan_type: Optional[str] = None             # free/pro/enterprise
    previous_support_count: int = 0
    is_paying_customer: bool = False
    support_history: Optional[List[Dict]] = None
    language: str = "ja"
