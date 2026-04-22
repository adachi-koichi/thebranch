"""Cost tracking and budget management service"""

import logging
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime, timedelta
from calendar import monthrange

from workflow.exceptions import ValidationError

if TYPE_CHECKING:
    from workflow.repositories.cost_repository import CostRepository

logger = logging.getLogger(__name__)


class CostTrackingService:
    """
    APIコスト追跡とコスト集計サービス。

    責務：
    - APIコール記録の追加・クエリ
    - 月次コスト集計
    - 予算アラート生成
    - コスト分析・レポート
    """

    def __init__(self, cost_repo: 'CostRepository') -> None:
        self.cost_repo = cost_repo

    def record_api_call(
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
        """API呼び出しを記録する。返却：api_calls.id"""
        if request_timestamp is None:
            request_timestamp = int(datetime.now().timestamp())

        if not api_provider in ['claude', 'openai', 'other']:
            raise ValidationError(f"Invalid api_provider: {api_provider}")

        call_id = self.cost_repo.add_api_call(
            department_id=department_id,
            agent_id=agent_id,
            api_provider=api_provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cost_usd=cost_usd,
            status=status,
            error_message=error_message,
            request_timestamp=request_timestamp,
        )

        logger.info(
            f"API call recorded: dept_id={department_id}, "
            f"agent_id={agent_id}, provider={api_provider}, cost={cost_usd}"
        )

        return call_id

    def aggregate_monthly_costs(self, department_id: int, year: int, month: int) -> dict:
        """
        指定月のコスト集計を実行する。
        既存レコードがあれば更新、なければ新規作成。
        """
        # 月の始終日を計算
        last_day = monthrange(year, month)[1]
        month_start = int(
            datetime(year, month, 1, 0, 0, 0).timestamp()
        )
        month_end = int(
            datetime(year, month, last_day, 23, 59, 59).timestamp()
        )

        # APIコールを集計
        total_cost = 0.0
        call_count = 0
        failed_count = 0
        model_counts = {}

        for call in self.cost_repo.get_api_calls_by_period(
            department_id, month_start, month_end
        ):
            if call['status'] == 'completed':
                total_cost += call['cost_usd']
                call_count += 1
            elif call['status'] == 'failed':
                failed_count += 1

            model = call.get('model_name', 'unknown')
            model_counts[model] = model_counts.get(model, 0) + 1

        top_model = max(model_counts, key=model_counts.get) if model_counts else None

        # 既存レコードを確認
        existing = self.cost_repo.get_cost_record(department_id, year, month)

        if existing:
            # 更新
            self.cost_repo.update_cost_record(
                department_id=department_id,
                year=year,
                month=month,
                total_cost_usd=total_cost,
                api_call_count=call_count,
                failed_call_count=failed_count,
                top_model=top_model,
            )
        else:
            # 新規作成
            self.cost_repo.add_cost_record(
                department_id=department_id,
                year=year,
                month=month,
                total_cost_usd=total_cost,
                api_call_count=call_count,
                failed_call_count=failed_count,
                top_model=top_model,
            )

        logger.info(
            f"Monthly costs aggregated: dept_id={department_id}, "
            f"year={year}, month={month}, total_cost={total_cost}"
        )

        return {
            'department_id': department_id,
            'year': year,
            'month': month,
            'total_cost_usd': total_cost,
            'api_call_count': call_count,
            'failed_call_count': failed_count,
            'top_model': top_model,
        }

    def check_budget_alerts(
        self, department_id: int, year: int, month: int, budget: Optional[float]
    ) -> List[dict]:
        """予算に対するアラートを生成する"""
        alerts = []

        if not budget or budget <= 0:
            return alerts

        cost_record = self.cost_repo.get_cost_record(department_id, year, month)
        if not cost_record:
            return alerts

        spent = cost_record['total_cost_usd']
        utilization = (spent / budget * 100) if budget > 0 else 0

        # 80% 警告アラート
        if 80 <= utilization < 100:
            alert_id = self.cost_repo.add_cost_alert(
                department_id=department_id,
                alert_type='budget_warning',
                threshold_percent=80,
                current_cost_usd=spent,
                budget_usd=budget,
                message=f"予算の {utilization:.1f}% を消費しています（{spent:.2f} / {budget:.2f} USD）",
                status='unresolved',
            )
            alerts.append({'id': alert_id, 'type': 'budget_warning', 'threshold': 80})
            logger.warning(
                f"Budget warning alert generated: dept_id={department_id}, "
                f"utilization={utilization:.1f}%"
            )

        # 100% 超過アラート
        elif utilization >= 100:
            alert_id = self.cost_repo.add_cost_alert(
                department_id=department_id,
                alert_type='budget_exceeded',
                threshold_percent=100,
                current_cost_usd=spent,
                budget_usd=budget,
                message=f"予算超過：{spent:.2f} / {budget:.2f} USD （超過額：{spent - budget:.2f} USD）",
                status='unresolved',
            )
            alerts.append({'id': alert_id, 'type': 'budget_exceeded', 'threshold': 100})
            logger.error(
                f"Budget exceeded alert generated: dept_id={department_id}, "
                f"exceeded_by={spent - budget:.2f}"
            )

        return alerts

    def get_department_cost_summary(self, department_id: int) -> dict:
        """部署の現在月のコスト概要を取得"""
        now = datetime.now()
        year, month = now.year, now.month

        cost_record = self.cost_repo.get_cost_record(department_id, year, month)
        budget = self.cost_repo.get_monthly_budget(department_id, year, month)

        spent = cost_record['total_cost_usd'] if cost_record else 0.0
        budget_usd = budget['budget_usd'] if budget else 0.0
        remaining = budget_usd - spent if budget_usd > 0 else 0.0
        utilization = (spent / budget_usd * 100) if budget_usd > 0 else 0.0

        return {
            'year': year,
            'month': month,
            'budget': budget_usd,
            'spent': spent,
            'remaining': remaining,
            'utilization_percent': utilization,
            'api_call_count': cost_record['api_call_count'] if cost_record else 0,
        }

    def get_monthly_cost_trend(self, department_id: int, months: int = 12) -> List[dict]:
        """過去N月のコスト推移を取得"""
        trend = []
        now = datetime.now()

        for i in range(months - 1, -1, -1):
            date = now - timedelta(days=30 * i)
            year, month = date.year, date.month

            cost_record = self.cost_repo.get_cost_record(department_id, year, month)
            budget = self.cost_repo.get_monthly_budget(department_id, year, month)

            trend.append({
                'year': year,
                'month': month,
                'cost': cost_record['total_cost_usd'] if cost_record else 0.0,
                'budget': budget['budget_usd'] if budget else 0.0,
                'api_calls': cost_record['api_call_count'] if cost_record else 0,
            })

        return trend

    def get_cost_alerts(
        self, department_id: Optional[int] = None, status: str = 'unresolved'
    ) -> List[dict]:
        """コストアラートを取得"""
        return self.cost_repo.get_cost_alerts(
            department_id=department_id, status=status
        )

    def resolve_alert(self, alert_id: int, resolved_by: str, note: Optional[str] = None) -> None:
        """アラートを解決状態にマーク"""
        self.cost_repo.resolve_cost_alert(
            alert_id=alert_id, resolved_by=resolved_by, resolution_note=note
        )
        logger.info(f"Cost alert resolved: alert_id={alert_id}, resolved_by={resolved_by}")
