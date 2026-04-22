from datetime import datetime
from typing import Optional, List
from workflow.repositories.base import BaseRepository


class CostRepository(BaseRepository):
    """Data access for cost tracking"""

    def add_api_call(
        self,
        department_id: int,
        agent_id: Optional[int],
        api_provider: str,
        model_name: Optional[str],
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cost_usd: float = 0.0,
        status: str = "completed",
        error_message: Optional[str] = None,
        request_timestamp: Optional[int] = None,
    ) -> int:
        """Insert API call record, return api_calls.id"""
        now = datetime.now().isoformat()
        if request_timestamp is None:
            request_timestamp = int(datetime.now().timestamp())

        query = '''
            INSERT INTO api_calls
            (department_id, agent_id, api_provider, model_name, input_tokens,
             output_tokens, cache_read_tokens, cache_creation_tokens, cost_usd,
             status, error_message, request_timestamp, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        call_id = self.execute_insert(
            query,
            (
                department_id, agent_id, api_provider, model_name, input_tokens,
                output_tokens, cache_read_tokens, cache_creation_tokens, cost_usd,
                status, error_message, request_timestamp, now, now
            )
        )
        return call_id

    def get_api_calls_by_period(
        self, department_id: int, start_timestamp: int, end_timestamp: int
    ) -> List[dict]:
        """Get API calls for department within timestamp range"""
        query = '''
            SELECT * FROM api_calls
            WHERE department_id = ? AND request_timestamp >= ? AND request_timestamp <= ?
            ORDER BY request_timestamp ASC
        '''
        rows = self.execute_all(query, (department_id, start_timestamp, end_timestamp))
        return [dict(row) for row in rows]

    def add_cost_record(
        self,
        department_id: int,
        year: int,
        month: int,
        total_cost_usd: float,
        api_call_count: int,
        failed_call_count: int = 0,
        top_model: Optional[str] = None,
    ) -> int:
        """Insert cost record, return cost_records.id"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO cost_records
            (department_id, year, month, total_cost_usd, api_call_count,
             failed_call_count, top_model, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        record_id = self.execute_insert(
            query,
            (
                department_id, year, month, total_cost_usd, api_call_count,
                failed_call_count, top_model, now, now
            )
        )
        return record_id

    def get_cost_record(
        self, department_id: int, year: int, month: int
    ) -> Optional[dict]:
        """Get cost record for specific month"""
        query = '''
            SELECT * FROM cost_records
            WHERE department_id = ? AND year = ? AND month = ?
        '''
        row = self.execute_one(query, (department_id, year, month))
        return dict(row) if row else None

    def update_cost_record(
        self,
        department_id: int,
        year: int,
        month: int,
        total_cost_usd: float,
        api_call_count: int,
        failed_call_count: int,
        top_model: Optional[str] = None,
    ) -> None:
        """Update cost record"""
        now = datetime.now().isoformat()
        query = '''
            UPDATE cost_records
            SET total_cost_usd = ?, api_call_count = ?, failed_call_count = ?,
                top_model = ?, updated_at = ?
            WHERE department_id = ? AND year = ? AND month = ?
        '''
        self.execute_update(
            query,
            (
                total_cost_usd, api_call_count, failed_call_count, top_model, now,
                department_id, year, month
            )
        )

    def add_monthly_budget(
        self,
        department_id: int,
        year: int,
        month: int,
        budget_usd: float,
        notes: Optional[str] = None,
    ) -> int:
        """Insert monthly budget, return monthly_budgets.id"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO monthly_budgets
            (department_id, year, month, budget_usd, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        budget_id = self.execute_insert(
            query,
            (department_id, year, month, budget_usd, notes, now, now)
        )
        return budget_id

    def get_monthly_budget(
        self, department_id: int, year: int, month: int
    ) -> Optional[dict]:
        """Get monthly budget for specific month"""
        query = '''
            SELECT * FROM monthly_budgets
            WHERE department_id = ? AND year = ? AND month = ?
        '''
        row = self.execute_one(query, (department_id, year, month))
        return dict(row) if row else None

    def add_cost_alert(
        self,
        department_id: int,
        alert_type: str,
        threshold_percent: Optional[float],
        current_cost_usd: float,
        budget_usd: float,
        message: str,
        status: str = "unresolved",
    ) -> int:
        """Insert cost alert, return cost_alerts.id"""
        now = datetime.now().isoformat()
        query = '''
            INSERT INTO cost_alerts
            (department_id, alert_type, threshold_percent, current_cost_usd,
             budget_usd, message, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        alert_id = self.execute_insert(
            query,
            (
                department_id, alert_type, threshold_percent, current_cost_usd,
                budget_usd, message, status, now, now
            )
        )
        return alert_id

    def get_cost_alerts(
        self, department_id: Optional[int] = None, status: str = "unresolved"
    ) -> List[dict]:
        """Get cost alerts, optionally filtered by department and status"""
        conditions = ['status = ?']
        params = [status]

        if department_id is not None:
            conditions.append('department_id = ?')
            params.append(department_id)

        where_clause = ' WHERE ' + ' AND '.join(conditions)
        query = f'''
            SELECT * FROM cost_alerts
            {where_clause}
            ORDER BY created_at DESC
        '''
        rows = self.execute_all(query, tuple(params))
        return [dict(row) for row in rows]

    def resolve_cost_alert(
        self,
        alert_id: int,
        resolved_by: str,
        resolution_note: Optional[str] = None,
    ) -> None:
        """Mark alert as resolved"""
        now = datetime.now().isoformat()
        query = '''
            UPDATE cost_alerts
            SET status = 'resolved', resolved_at = ?, resolved_by = ?,
                resolution_note = ?, updated_at = ?
            WHERE id = ?
        '''
        self.execute_update(
            query,
            (now, resolved_by, resolution_note, now, alert_id)
        )
