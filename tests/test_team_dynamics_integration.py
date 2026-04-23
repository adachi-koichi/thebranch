"""
Team Dynamics 統合テスト

API エンドポイント統合テスト（auto-allocate, dynamics-report 等）
"""
import pytest
import json
import sqlite3
from datetime import datetime, timedelta
from httpx import AsyncClient, Client, ASGITransport
import asyncio


@pytest.mark.asyncio
async def test_auto_allocate_endpoint_basic():
    """auto-allocate エンドポイントの基本動作"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/tasks/1/auto-allocate?team_id=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert "selected_agent_id" in data
        assert "ranking" in data
        assert "algorithm_version" in data
        assert data["algorithm_version"] == "v2_skill_matching"


@pytest.mark.asyncio
async def test_allocation_recommendations_endpoint():
    """allocation-recommendations エンドポイントのテスト"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/teams/1/allocation-recommendations")

        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)


@pytest.mark.asyncio
async def test_allocation_score_in_recommendations():
    """allocation-recommendations の各推奨に allocation_score が含まれる"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/teams/1/allocation-recommendations")

        assert response.status_code == 200
        data = response.json()

        for recommendation in data.get("recommendations", []):
            assert "allocation_score" in recommendation
            assert "factors" in recommendation
            assert "skill_match" in recommendation["factors"]
            assert "workload_score" in recommendation["factors"]
            assert "collaboration" in recommendation["factors"]
            assert "reliability" in recommendation["factors"]


@pytest.mark.asyncio
async def test_generate_dynamics_report_week():
    """週間レポート生成テスト"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/teams/1/dynamics-report/generate?period=week"
        )

        assert response.status_code == 200
        data = response.json()

        assert "report_id" in data
        assert data["status"] == "generated"
        assert data["data"]["period"] == "week"
        assert "period_start" in data["data"]
        assert "period_end" in data["data"]
        assert "summary" in data["data"]
        assert "member_breakdown" in data["data"]


@pytest.mark.asyncio
async def test_generate_dynamics_report_month():
    """月間レポート生成テスト"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/teams/1/dynamics-report/generate?period=month"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["period"] == "month"
        # period_start が30日前であることを確認
        report_start = datetime.fromisoformat(data["data"]["period_start"])
        report_end = datetime.fromisoformat(data["data"]["period_end"])
        delta = report_end.date() - report_start.date()
        assert delta.days >= 29 and delta.days <= 31


@pytest.mark.asyncio
async def test_generate_dynamics_report_day():
    """日次レポート生成テスト"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/teams/1/dynamics-report/generate?period=day"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["period"] == "day"
        # period_start と period_end が同じ日付であることを確認
        assert data["data"]["period_start"] == data["data"]["period_end"]


@pytest.mark.asyncio
async def test_dynamics_report_summary_metrics():
    """レポートサマリーに必要なメトリクスが含まれる"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/teams/1/dynamics-report/generate?period=week"
        )

        assert response.status_code == 200
        data = response.json()
        summary = data["data"]["summary"]

        # 必須メトリクス
        assert "completed_tasks" in summary
        assert "average_completion_rate" in summary
        assert "average_quality_score" in summary
        assert "average_workload" in summary
        assert "workload_balance" in summary
        assert "collaboration_events" in summary
        assert "active_members" in summary

        # 数値の妥当性チェック
        assert isinstance(summary["completed_tasks"], int)
        assert 0 <= summary["average_completion_rate"] <= 1.0
        assert 0 <= summary["average_quality_score"] <= 100
        assert 0 <= summary["average_workload"] <= 100
        assert 0 <= summary["workload_balance"] <= 100


@pytest.mark.asyncio
async def test_dynamics_report_member_breakdown():
    """レポートのメンバー分解が正しい形式"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/teams/1/dynamics-report/generate?period=week"
        )

        assert response.status_code == 200
        data = response.json()
        members = data["data"]["member_breakdown"]

        assert isinstance(members, list)
        for member in members:
            assert "agent_id" in member
            assert "session_id" in member
            assert "workload_level" in member
            assert "completion_rate" in member
            assert "throughput_7d" in member
            assert "quality_score" in member


@pytest.mark.asyncio
async def test_get_dynamics_report():
    """生成したレポートの取得テスト"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # まずレポートを生成
        gen_response = await client.post(
            "/api/teams/1/dynamics-report/generate?period=week"
        )
        report_id = gen_response.json()["report_id"]

        # 生成したレポートを取得
        response = await client.get(
            f"/api/teams/1/dynamics-report?report_id={report_id}"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["report_id"] == report_id
        assert "summary" in data
        assert "member_breakdown" in data
        assert "generated_at" in data


@pytest.mark.asyncio
async def test_get_latest_dynamics_report():
    """最新レポート取得テスト（report_id 指定なし）"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/teams/1/dynamics-report")

        assert response.status_code == 200
        data = response.json()

        # 何らかのレポート情報が返される（空の場合も OK）
        assert "report_id" in data or data["report_id"] is None


@pytest.mark.asyncio
async def test_auto_allocate_skill_differentiation():
    """auto-allocate がスキル差を正しく区別できるか"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/tasks/1/auto-allocate?team_id=1"
        )

        assert response.status_code == 200
        data = response.json()
        ranking = data["ranking"]

        # ランキングが降順であることを確認
        scores = [item["score"] for item in ranking]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_allocation_with_task_category():
    """タスクカテゴリに応じた allocation_score の計算"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/tasks/1/auto-allocate?team_id=1"
        )

        assert response.status_code == 200
        data = response.json()

        # domain_bonus が含まれている
        assert "ranking" in data
        for agent_candidate in data["ranking"]:
            assert "factors" in agent_candidate
            if "domain_bonus" in agent_candidate["factors"]:
                assert agent_candidate["factors"]["domain_bonus"] >= 0


@pytest.mark.asyncio
async def test_performance_summary_endpoint():
    """performance-summary エンドポイント"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/teams/1/performance-summary")

        assert response.status_code == 200
        data = response.json()

        assert "completion_rate" in data
        assert "throughput_7d" in data
        assert "collaboration_score" in data
        assert "active_members" in data


@pytest.mark.asyncio
async def test_member_performance_endpoint():
    """member-performance エンドポイント"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/teams/1/member-performance")

        assert response.status_code == 200
        data = response.json()

        assert "members" in data
        assert isinstance(data["members"], list)


@pytest.mark.asyncio
async def test_collaboration_heatmap_endpoint():
    """collaboration-heatmap エンドポイント"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/teams/1/collaboration-heatmap")

        assert response.status_code == 200
        data = response.json()

        assert "agents" in data
        assert "heatmap" in data
        assert isinstance(data["agents"], list)


@pytest.mark.asyncio
async def test_communication_timeline_endpoint():
    """communication-timeline エンドポイント"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/teams/1/communication-timeline?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_error_handling_nonexistent_team():
    """存在しないチームに対するエラーハンドリング"""
    from dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/teams/99999/dynamics-report/generate?period=week"
        )

        # 404 または 500 エラーを受け取ることを確認（チームが存在しないため）
        assert response.status_code in [404, 500]


@pytest.mark.asyncio
async def test_report_metadata_persistence():
    """レポートメタデータが SQLite に正しく保存される"""
    from dashboard.app import app
    import aiosqlite
    from pathlib import Path

    db_path = Path("/Users/delightone/dev/github.com/adachi-koichi/thebranch/dashboard/data/thebranch.sqlite")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # レポート生成
        response = await client.post(
            "/api/teams/1/dynamics-report/generate?period=week"
        )
        report_id = response.json()["report_id"]

        # DB から直接確認
        async with aiosqlite.connect(str(db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM team_dynamics_snapshot WHERE id = ?",
                (report_id,)
            )
            row = await cursor.fetchone()

            assert row is not None
            assert row["team_id"] == 1
            assert row["metadata"] is not None

            # メタデータが JSON で保存されているか確認
            metadata = json.loads(row["metadata"])
            assert "summary" in metadata
            assert "member_breakdown" in metadata


class TestDynamicsReportDataIntegrity:
    """レポートのデータ整合性テスト"""

    @pytest.mark.asyncio
    async def test_member_count_matches_breakdown(self):
        """summary の active_members と member_breakdown の数が一致"""
        from dashboard.app import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/teams/1/dynamics-report/generate?period=week"
            )

            data = response.json()["data"]
            active_members = data["summary"]["active_members"]
            breakdown_count = len(data["member_breakdown"])

            assert active_members == breakdown_count

    @pytest.mark.asyncio
    async def test_average_metrics_are_reasonable(self):
        """平均値が妥当な範囲内"""
        from dashboard.app import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/teams/1/dynamics-report/generate?period=week"
            )

            data = response.json()["data"]
            summary = data["summary"]
            members = data["member_breakdown"]

            # 完了率の平均値が個別値の平均に近い
            if members:
                individual_avg = sum(m["completion_rate"] for m in members) / len(members)
                assert abs(summary["average_completion_rate"] - individual_avg) < 0.01

            # 品質スコアの平均値が個別値の平均に近い
            if members:
                individual_avg = sum(m["quality_score"] for m in members) / len(members)
                assert abs(summary["average_quality_score"] - individual_avg) < 1.0
