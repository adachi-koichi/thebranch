"""
ユニットテスト: オンボーディング AI 分析・タスク生成
workflow.services.onboarding モジュールの単体テスト
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from workflow.services.onboarding import OnboardingService


class TestOnboardingService:
    """OnboardingService のユニットテスト"""

    @pytest.fixture
    def service(self):
        """OnboardingService インスタンスを作成"""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            return OnboardingService()

    def test_analyze_vision_for_templates_returns_list(self, service):
        """vision 分析が提案リストを返すこと"""
        vision = "営業チームを立ち上げたい"

        with patch.object(service.client, "messages") as mock_messages:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = """
            [
                {
                    "template_id": 2,
                    "name": "営業",
                    "category": "Sales",
                    "total_roles": 5,
                    "total_processes": 7,
                    "reason": "営業チームに最適",
                    "rank": 1
                },
                {
                    "template_id": 1,
                    "name": "マーケティング",
                    "category": "Marketing",
                    "total_roles": 4,
                    "total_processes": 6,
                    "reason": "マーケティングに最適",
                    "rank": 2
                }
            ]
            """
            mock_messages.create.return_value = mock_response

            suggestions = service.analyze_vision_for_templates(vision)

            assert isinstance(suggestions, list)
            assert len(suggestions) > 0
            assert suggestions[0]["template_id"] == 2
            assert suggestions[0]["name"] == "営業"

    def test_analyze_vision_handles_edge_cases(self, service):
        """vision の入力エッジケース処理"""
        # 短い入力（サービスは受け入れ、バリデーションは API レイヤーで実施）
        with patch.object(service.client, "messages") as mock_messages:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = '[{"template_id": 1, "name": "Test", "category": "Test", "total_roles": 1, "total_processes": 1, "reason": "Test", "rank": 1}]'
            mock_messages.create.return_value = mock_response

            # サービスは短い入力も処理する
            suggestions = service.analyze_vision_for_templates("短い")
            assert isinstance(suggestions, list)

    def test_generate_initial_tasks_returns_3_to_5_tasks(self, service):
        """初期タスク生成が 3-5 個のタスクを返すこと"""
        with patch.object(service.client, "messages") as mock_messages:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = """
            [
                {
                    "task_id": "task_001",
                    "title": "チーム オンボーディング",
                    "description": "メンバーのシステム設定",
                    "budget": 1000.0,
                    "deadline": "2026-05-15",
                    "assigned_to": "Manager"
                },
                {
                    "task_id": "task_002",
                    "title": "プロセス定義",
                    "description": "業務フロー定義",
                    "budget": 1500.0,
                    "deadline": "2026-05-22",
                    "assigned_to": "Lead"
                },
                {
                    "task_id": "task_003",
                    "title": "KPI 設定",
                    "description": "成果指標の定義",
                    "budget": 500.0,
                    "deadline": "2026-06-01",
                    "assigned_to": "Analyst"
                }
            ]
            """
            mock_messages.create.return_value = mock_response

            tasks = service.generate_initial_tasks(
                dept_name="営業推進部",
                kpi="月商1000万円達成",
                budget=3000.0,
                members_count=3
            )

            assert isinstance(tasks, list)
            assert 3 <= len(tasks) <= 5
            for task in tasks:
                assert "task_id" in task
                assert "title" in task
                assert "budget" in task
                assert "deadline" in task

    def test_generate_initial_tasks_respects_budget_limit(self, service):
        """タスク予算の合計が指定予算を超えないこと"""
        budget = 3000.0

        with patch.object(service.client, "messages") as mock_messages:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = """
            [
                {"task_id": "task_001", "title": "Task 1", "description": "Desc", "budget": 2000.0, "deadline": "2026-05-15", "assigned_to": "Manager"},
                {"task_id": "task_002", "title": "Task 2", "description": "Desc", "budget": 2000.0, "deadline": "2026-05-22", "assigned_to": "Lead"},
                {"task_id": "task_003", "title": "Task 3", "description": "Desc", "budget": 2000.0, "deadline": "2026-06-01", "assigned_to": "Analyst"}
            ]
            """
            mock_messages.create.return_value = mock_response

            tasks = service.generate_initial_tasks(
                dept_name="営業推進部",
                kpi="月商1000万円達成",
                budget=budget,
                members_count=3
            )

            total_budget = sum(t["budget"] for t in tasks)
            assert total_budget <= budget

    def test_validate_budget_ok_status(self, service):
        """予算チェック: OK ステータス"""
        result = service.validate_budget(
            members_count=3,
            budget=16500.0,  # 3人 × $5500
            dept_type="sales"
        )

        assert result["status"] == "ok"
        assert result["monthly_per_person"] == 5500.0
        assert result["market_benchmark"] == 5500

    def test_validate_budget_warning_status(self, service):
        """予算チェック: WARNING ステータス"""
        result = service.validate_budget(
            members_count=3,
            budget=13200.0,  # 3人 × $4400 (80% of benchmark)
            dept_type="sales"
        )

        assert result["status"] == "warning"
        assert result["monthly_per_person"] == 4400.0

    def test_validate_budget_error_status(self, service):
        """予算チェック: ERROR ステータス"""
        result = service.validate_budget(
            members_count=3,
            budget=9900.0,  # 3人 × $3300 (60% of benchmark)
            dept_type="sales"
        )

        assert result["status"] == "error"
        assert result["monthly_per_person"] == 3300.0

    def test_validate_budget_dept_type_benchmarks(self, service):
        """部署タイプ別の給与相場チェック"""
        # マーケティング
        marketing_result = service.validate_budget(
            members_count=2,
            budget=9000.0,  # 2人 × $4500
            dept_type="marketing"
        )
        assert marketing_result["status"] == "ok"
        assert marketing_result["market_benchmark"] == 4500

        # エンジニアリング
        eng_result = service.validate_budget(
            members_count=2,
            budget=13000.0,  # 2人 × $6500
            dept_type="engineering"
        )
        assert eng_result["status"] == "ok"
        assert eng_result["market_benchmark"] == 6500

    def test_validate_budget_members_count_ranges(self, service):
        """メンバー数の範囲別ベンチマーク"""
        # 1人
        result_1 = service.validate_budget(
            members_count=1,
            budget=6000.0,
            dept_type="sales"
        )
        assert result_1["market_benchmark"] == 6000

        # 2-3人
        result_2_3 = service.validate_budget(
            members_count=2,
            budget=11000.0,  # 2人 × $5500
            dept_type="sales"
        )
        assert result_2_3["market_benchmark"] == 5500

        # 4-5人
        result_4_5 = service.validate_budget(
            members_count=4,
            budget=20000.0,  # 4人 × $5000
            dept_type="sales"
        )
        assert result_4_5["market_benchmark"] == 5000

        # 6人以上
        result_6_plus = service.validate_budget(
            members_count=6,
            budget=28200.0,  # 6人 × $4700
            dept_type="sales"
        )
        assert result_6_plus["market_benchmark"] == 4700


class TestOnboardingIntegration:
    """オンボーディング統合テスト"""

    @pytest.fixture
    def service(self):
        """OnboardingService インスタンス"""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            return OnboardingService()

    def test_full_onboarding_flow(self, service):
        """フルオンボーディングフロー"""
        vision = "営業チームを立ち上げ、月商1000万円達成"

        # 1. Vision 分析
        with patch.object(service.client, "messages") as mock_messages:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = """
            [
                {
                    "template_id": 2,
                    "name": "営業",
                    "category": "Sales",
                    "total_roles": 5,
                    "total_processes": 7,
                    "reason": "営業成長に最適",
                    "rank": 1
                }
            ]
            """
            mock_messages.create.return_value = mock_response

            suggestions = service.analyze_vision_for_templates(vision)
            assert len(suggestions) > 0
            selected_template = suggestions[0]

        # 2. 予算検証
        budget_validation = service.validate_budget(
            members_count=3,
            budget=16500.0,
            dept_type="sales"
        )
        assert budget_validation["status"] == "ok"

        # 3. 初期タスク生成
        with patch.object(service.client, "messages") as mock_messages:
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = """
            [
                {
                    "task_id": "task_001",
                    "title": "営業チーム オンボーディング",
                    "description": "メンバー設定",
                    "budget": 5500.0,
                    "deadline": "2026-05-15",
                    "assigned_to": "Manager"
                },
                {
                    "task_id": "task_002",
                    "title": "営業プロセス定義",
                    "description": "営業フロー定義",
                    "budget": 5500.0,
                    "deadline": "2026-05-22",
                    "assigned_to": "Lead"
                },
                {
                    "task_id": "task_003",
                    "title": "KPI ダッシュボード",
                    "description": "成果指標設定",
                    "budget": 5500.0,
                    "deadline": "2026-06-01",
                    "assigned_to": "Analyst"
                }
            ]
            """
            mock_messages.create.return_value = mock_response

            tasks = service.generate_initial_tasks(
                dept_name="営業推進部",
                kpi="月商1000万円達成",
                budget=16500.0,
                members_count=3
            )

        # 検証
        assert len(tasks) == 3
        total_budget = sum(t["budget"] for t in tasks)
        assert total_budget <= 16500.0
