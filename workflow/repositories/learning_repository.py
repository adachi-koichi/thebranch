from datetime import datetime
from typing import Optional, List
from workflow.repositories.base import BaseRepository


class LearningPatternsRepository(BaseRepository):
    """Data access for AI agent learning patterns and feedback"""

    def add_learning_pattern(
        self,
        workflow_id: str,
        workflow_name: str,
        input_text: str,
        output_text: str,
        result_status: str,
        confidence: float = 1.0,
    ) -> int:
        """Record a learning pattern from workflow execution"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO learning_patterns
            (workflow_id, workflow_name, input, output, result_status, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        pattern_id = self.execute_insert(
            query,
            (workflow_id, workflow_name, input_text, output_text, result_status, confidence, now)
        )
        return pattern_id

    def get_patterns_by_workflow(
        self, workflow_id: str, limit: int = 100
    ) -> List[dict]:
        """Get all patterns for a specific workflow"""
        query = '''
            SELECT * FROM learning_patterns
            WHERE workflow_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        '''
        rows = self.execute_all(query, (workflow_id, limit))
        return [dict(row) for row in rows]

    def get_patterns_by_status(
        self, status: str, limit: int = 100
    ) -> List[dict]:
        """Get patterns by result status (success, failure, warning)"""
        query = '''
            SELECT * FROM learning_patterns
            WHERE result_status = ?
            ORDER BY created_at DESC
            LIMIT ?
        '''
        rows = self.execute_all(query, (status, limit))
        return [dict(row) for row in rows]

    def get_high_confidence_patterns(
        self, min_confidence: float = 0.8, limit: int = 50
    ) -> List[dict]:
        """Get high-confidence patterns for recommendation"""
        query = '''
            SELECT * FROM learning_patterns
            WHERE confidence >= ?
            ORDER BY confidence DESC, created_at DESC
            LIMIT ?
        '''
        rows = self.execute_all(query, (min_confidence, limit))
        return [dict(row) for row in rows]

    def get_workflow_statistics(self, workflow_id: str) -> dict:
        """Get statistics for workflow execution patterns"""
        query = '''
            SELECT
                COUNT(*) as total_executions,
                SUM(CASE WHEN result_status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN result_status = 'failure' THEN 1 ELSE 0 END) as failure_count,
                SUM(CASE WHEN result_status = 'warning' THEN 1 ELSE 0 END) as warning_count,
                AVG(confidence) as avg_confidence,
                MAX(created_at) as last_execution
            FROM learning_patterns
            WHERE workflow_id = ?
        '''
        row = self.execute_one(query, (workflow_id,))
        return dict(row) if row else {}

    def get_overall_statistics(self) -> dict:
        """Get overall statistics across all workflows"""
        query = '''
            SELECT
                COUNT(DISTINCT workflow_id) as unique_workflows,
                COUNT(*) as total_patterns,
                SUM(CASE WHEN result_status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN result_status = 'failure' THEN 1 ELSE 0 END) as failure_count,
                AVG(confidence) as avg_confidence
            FROM learning_patterns
        '''
        row = self.execute_one(query, ())
        return dict(row) if row else {}

    def get_recent_patterns(self, days: int = 7, limit: int = 50) -> List[dict]:
        """Get patterns from the last N days"""
        query = '''
            SELECT * FROM learning_patterns
            WHERE created_at >= datetime('now', '-' || ? || ' days')
            ORDER BY created_at DESC
            LIMIT ?
        '''
        rows = self.execute_all(query, (days, limit))
        return [dict(row) for row in rows]

    def get_failure_patterns(self, limit: int = 50) -> List[dict]:
        """Get failed patterns for analysis and improvement"""
        query = '''
            SELECT * FROM learning_patterns
            WHERE result_status = 'failure'
            ORDER BY created_at DESC
            LIMIT ?
        '''
        rows = self.execute_all(query, (limit,))
        return [dict(row) for row in rows]

    def search_patterns(self, keyword: str, limit: int = 50) -> List[dict]:
        """Search patterns by input or output text"""
        query = '''
            SELECT * FROM learning_patterns
            WHERE input LIKE ? OR output LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        '''
        search_term = f"%{keyword}%"
        rows = self.execute_all(query, (search_term, search_term, limit))
        return [dict(row) for row in rows]
