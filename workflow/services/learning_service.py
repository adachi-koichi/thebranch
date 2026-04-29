"""AI agent learning patterns and improvement feedback service"""

import logging
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime

if TYPE_CHECKING:
    from workflow.repositories.learning_repository import LearningPatternsRepository

logger = logging.getLogger(__name__)


class LearningService:
    """
    AIエージェント学習パターン・改善フィードバック管理。

    責務：
    - ワークフロー実行パターン記録
    - 学習フィードバック生成
    - 改善提案・最適化提案
    """

    def __init__(self, learning_repo: 'LearningPatternsRepository') -> None:
        self.learning_repo = learning_repo

    def record_workflow_execution(
        self,
        workflow_id: str,
        workflow_name: str,
        input_text: str,
        output_text: str,
        success: bool,
        confidence: float = 1.0,
        error_message: Optional[str] = None,
    ) -> int:
        """Record a workflow execution as a learning pattern"""
        result_status = "success" if success else "failure"
        if error_message:
            result_status = "warning"

        pattern_id = self.learning_repo.add_learning_pattern(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            input_text=input_text,
            output_text=output_text,
            result_status=result_status,
            confidence=confidence,
        )

        logger.info(
            f"Workflow execution recorded: workflow_id={workflow_id}, "
            f"status={result_status}, confidence={confidence}"
        )

        return pattern_id

    def get_workflow_insights(self, workflow_id: str) -> dict:
        """Get insights and statistics for a workflow"""
        stats = self.learning_repo.get_workflow_statistics(workflow_id)

        total = stats.get('total_executions', 0)
        success = stats.get('success_count', 0)
        failures = stats.get('failure_count', 0)

        success_rate = (success / total * 100) if total > 0 else 0
        failure_rate = (failures / total * 100) if total > 0 else 0

        return {
            'workflow_id': workflow_id,
            'total_executions': total,
            'success_count': success,
            'failure_count': failures,
            'success_rate': success_rate,
            'failure_rate': failure_rate,
            'avg_confidence': stats.get('avg_confidence', 0),
            'last_execution': stats.get('last_execution'),
        }

    def generate_improvement_recommendations(
        self, workflow_id: str
    ) -> List[dict]:
        """Generate improvement recommendations based on patterns"""
        recommendations = []

        # Get workflow statistics
        stats = self.learning_repo.get_workflow_statistics(workflow_id)
        total = stats.get('total_executions', 0)

        if total == 0:
            return recommendations

        failures = stats.get('failure_count', 0)
        failure_rate = (failures / total * 100) if total > 0 else 0

        # Recommendation 1: High failure rate
        if failure_rate > 20:
            recommendations.append({
                'id': 'high_failure_rate',
                'category': 'reliability',
                'priority': 'high',
                'title': 'エラー率が高い',
                'description': f'このワークフローのエラー率が {failure_rate:.1f}% です。'
                               f'失敗パターンを分析し、エラーハンドリングを改善することをお勧めします。',
                'action': 'failure_analysis',
            })

        # Recommendation 2: Low confidence
        avg_confidence = stats.get('avg_confidence', 1.0)
        if avg_confidence < 0.7:
            recommendations.append({
                'id': 'low_confidence',
                'category': 'quality',
                'priority': 'medium',
                'title': '信頼度が低い',
                'description': f'このワークフローの平均信頼度が {avg_confidence:.2f} です。'
                               f'出力品質を向上させるため、プロンプトやロジックを見直してください。',
                'action': 'quality_improvement',
            })

        # Recommendation 3: Suggest optimization
        if total > 10:
            recommendations.append({
                'id': 'optimization_opportunity',
                'category': 'optimization',
                'priority': 'medium',
                'title': '最適化の機会',
                'description': f'{total} 回の実行データから、パフォーマンス最適化のパターンを検出しました。'
                               f'キャッシング戦略やプロンプト最適化を検討してください。',
                'action': 'optimize',
            })

        return recommendations

    def get_failure_analysis(self, workflow_id: str, limit: int = 10) -> dict:
        """Analyze failure patterns for a workflow"""
        failures = self.learning_repo.get_patterns_by_workflow(workflow_id)
        failures = [p for p in failures if p.get('result_status') == 'failure'][:limit]

        if not failures:
            return {
                'workflow_id': workflow_id,
                'failure_count': 0,
                'patterns': [],
                'common_issues': [],
            }

        # Extract common patterns from failures
        common_issues = []
        for failure in failures:
            output = failure.get('output', '')
            if 'timeout' in output.lower():
                common_issues.append('timeout')
            elif 'validation' in output.lower():
                common_issues.append('validation_error')
            elif 'permission' in output.lower():
                common_issues.append('permission_denied')
            elif 'rate_limit' in output.lower():
                common_issues.append('rate_limit')

        # Count occurrences
        issue_counts = {}
        for issue in common_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

        return {
            'workflow_id': workflow_id,
            'failure_count': len(failures),
            'patterns': failures,
            'common_issues': sorted(
                issue_counts.items(),
                key=lambda x: x[1],
                reverse=True
            ),
        }

    def get_similar_successful_patterns(
        self, workflow_id: str, limit: int = 5
    ) -> List[dict]:
        """Get successful patterns to use as reference"""
        patterns = self.learning_repo.get_patterns_by_workflow(workflow_id, limit=limit*2)
        successful = [p for p in patterns if p.get('result_status') == 'success']

        return successful[:limit]

    def get_learning_dashboard_data(self) -> dict:
        """Get overall learning dashboard data"""
        overall_stats = self.learning_repo.get_overall_statistics()
        recent_patterns = self.learning_repo.get_recent_patterns(days=7)
        failure_patterns = self.learning_repo.get_failure_patterns(limit=5)

        return {
            'overall_stats': overall_stats,
            'recent_patterns': recent_patterns,
            'recent_failures': failure_patterns,
            'total_unique_workflows': overall_stats.get('unique_workflows', 0),
            'total_patterns': overall_stats.get('total_patterns', 0),
            'avg_success_rate': (
                overall_stats.get('success_count', 0) /
                overall_stats.get('total_patterns', 1) * 100
            ) if overall_stats.get('total_patterns', 0) > 0 else 0,
        }
