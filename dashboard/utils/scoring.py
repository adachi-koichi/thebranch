"""
エージェント評価スコア計算ロジック
"""


def calculate_overall_score(completion_rate: float, quality_score: float) -> float:
    """
    エージェント総合スコアを計算

    計算式: overall_score = (completion_rate × 0.6) + (quality_score × 0.4)

    Args:
        completion_rate (float): 完了率 (0.0-100.0)
        quality_score (float): 品質スコア (1.0-5.0)

    Returns:
        float: 計算済みの総合スコア

    Raises:
        ValueError: 入力値が範囲外の場合
    """
    if not (0.0 <= completion_rate <= 100.0):
        raise ValueError(f"completion_rate must be between 0.0 and 100.0, got {completion_rate}")

    if not (1.0 <= quality_score <= 5.0):
        raise ValueError(f"quality_score must be between 1.0 and 5.0, got {quality_score}")

    # 正規化: completion_rate を 1.0-5.0 スケールに変換
    normalized_completion = (completion_rate / 100.0) * 4.0 + 1.0

    overall_score = (normalized_completion * 0.6) + (quality_score * 0.4)
    return round(overall_score, 2)


def validate_completion_rate(completion_rate: float) -> bool:
    """完了率の妥当性を検証"""
    return 0.0 <= completion_rate <= 100.0


def validate_quality_score(quality_score: float) -> bool:
    """品質スコアの妥当性を検証"""
    return 1.0 <= quality_score <= 5.0
