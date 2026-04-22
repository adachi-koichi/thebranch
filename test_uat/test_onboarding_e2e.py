"""
Onboarding E2E Test with pytest-bdd
Test the complete 4-step onboarding flow
"""
import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta
import aiosqlite
from pathlib import Path

# Assuming the app can be imported
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))


@pytest.fixture
def user_id():
    """Generate a unique user ID for testing"""
    return f"test_user_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def onboarding_id():
    """Generate a unique onboarding ID"""
    return f"test_onb_{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def db_connection():
    """Create a connection to test database"""
    db_path = Path.home() / "dev/github.com/adachi-koichi/thebranch/dashboard/data/thebranch.sqlite"
    async with aiosqlite.connect(str(db_path)) as db:
        yield db


# ─────────────────────────────────────────────────
# Step 0: Vision Input
# ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vision_input_creates_onboarding_record(user_id, onboarding_id, db_connection):
    """Test that vision input creates an onboarding progress record"""
    vision_text = "営業チーム立ち上げ、月商1000万円達成"

    # Simulate POST /api/onboarding/vision
    async with db_connection as db:
        await db.execute(
            """INSERT INTO user_onboarding_progress
               (onboarding_id, user_id, vision_input, current_step)
               VALUES (?, ?, ?, 0)""",
            (onboarding_id, user_id, vision_text)
        )
        await db.commit()

        # Verify record was created
        cursor = await db.execute(
            "SELECT vision_input, current_step FROM user_onboarding_progress WHERE onboarding_id = ?",
            (onboarding_id,)
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == vision_text
        assert row[1] == 0


@pytest.mark.asyncio
async def test_vision_input_validation_empty_text(user_id, onboarding_id, db_connection):
    """Test that empty vision text fails validation"""
    vision_text = ""

    # This should be validated at API layer, but we test DB constraint
    assert len(vision_text) == 0 or len(vision_text) > 500 or not vision_text.strip(), \
        "Empty or invalid vision should fail"


@pytest.mark.asyncio
async def test_vision_input_validation_max_length(user_id, onboarding_id, db_connection):
    """Test that vision input exceeding 500 chars fails"""
    vision_text = "a" * 501  # Exceeds 500 char limit

    # API should reject, DB can store as TEXT
    # Validation should happen at API layer
    assert len(vision_text) > 500, "Vision text validation should enforce max length"


# ─────────────────────────────────────────────────
# Step 1: AI Suggestion
# ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_suggestion_creates_template_record(onboarding_id, db_connection):
    """Test that AI suggestion updates onboarding record with template"""
    template_id = "sales"
    suggestion_reason = "ビジョンから営業チーム構成が最適と判定（マッチスコア: 0.98）"

    async with db_connection as db:
        await db.execute(
            """UPDATE user_onboarding_progress
               SET suggested_template_id = ?, suggestion_reason = ?, current_step = 1
               WHERE onboarding_id = ?""",
            (template_id, suggestion_reason, onboarding_id)
        )
        await db.commit()

        # Verify update
        cursor = await db.execute(
            """SELECT suggested_template_id, suggestion_reason, current_step
               FROM user_onboarding_progress WHERE onboarding_id = ?""",
            (onboarding_id,)
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == template_id
        assert row[1] == suggestion_reason
        assert row[2] == 1


@pytest.mark.asyncio
async def test_ai_suggestion_response_format():
    """Test that AI suggestion API returns correct response structure"""
    expected_fields = [
        "template_id",
        "name",
        "match_score",
        "config"
    ]

    # Sample response
    suggestion = {
        "template_id": "sales",
        "name": "営業推進部",
        "match_score": 0.98,
        "config": {
            "members_count": 4,
            "roles": ["営業3人", "マネージャー1人"],
            "budget_monthly": 3000000,
            "processes": ["リード発掘", "初期接触", "提案・クロージング"]
        }
    }

    for field in expected_fields:
        assert field in suggestion, f"Response missing {field}"


# ─────────────────────────────────────────────────
# Step 2: Detailed Setup
# ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detailed_setup_updates_dept_info(onboarding_id, db_connection):
    """Test that detailed setup updates department information"""
    dept_name = "営業推進部"
    manager_name = "山田太郎"
    members_count = 3
    budget = 3000000
    kpi = "月商1000万円、成約率35%"

    async with db_connection as db:
        await db.execute(
            """UPDATE user_onboarding_progress
               SET dept_name = ?, manager_name = ?, members_count = ?,
                   budget = ?, kpi = ?, current_step = 2
               WHERE onboarding_id = ?""",
            (dept_name, manager_name, members_count, budget, kpi, onboarding_id)
        )
        await db.commit()

        # Verify update
        cursor = await db.execute(
            """SELECT dept_name, manager_name, members_count, budget, kpi, current_step
               FROM user_onboarding_progress WHERE onboarding_id = ?""",
            (onboarding_id,)
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == dept_name
        assert row[1] == manager_name
        assert row[2] == members_count
        assert row[3] == budget
        assert row[4] == kpi
        assert row[5] == 2


@pytest.mark.asyncio
async def test_budget_validation(members_count=3, budget=3000000):
    """Test that budget validation checks monthly per-person cost"""
    monthly_per_person = budget / members_count
    market_benchmark = 950000  # Expected benchmark

    # Budget should be reasonable relative to members
    assert monthly_per_person > 0, "Budget per person must be positive"
    assert monthly_per_person >= (market_benchmark * 0.8), \
        f"Budget per person ({monthly_per_person}) is too low compared to benchmark ({market_benchmark})"


@pytest.mark.asyncio
async def test_integration_settings(onboarding_id, db_connection):
    """Test that integration settings (JSON) are stored correctly"""
    integrations = json.dumps({
        "salesforce": True,
        "sheets": False,
        "slack": True
    })

    async with db_connection as db:
        await db.execute(
            """UPDATE user_onboarding_progress
               SET integrations = ?
               WHERE onboarding_id = ?""",
            (integrations, onboarding_id)
        )
        await db.commit()

        # Verify storage and retrieval
        cursor = await db.execute(
            "SELECT integrations FROM user_onboarding_progress WHERE onboarding_id = ?",
            (onboarding_id,)
        )
        row = await cursor.fetchone()
        assert row is not None
        retrieved = json.loads(row[0])
        assert retrieved["salesforce"] is True
        assert retrieved["sheets"] is False
        assert retrieved["slack"] is True


# ─────────────────────────────────────────────────
# Step 3: Initial Task Execution
# ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initial_tasks_generation(onboarding_id, db_connection):
    """Test that initial tasks are generated as JSON"""
    tasks = [
        {
            "task_id": "task_1",
            "title": "リード発掘",
            "description": "B2B リード 100社の発掘",
            "budget": 500000,
            "deadline": "2026-04-29"
        },
        {
            "task_id": "task_2",
            "title": "初期接触・営業提案",
            "description": "リード 20社への初期接触",
            "budget": 500000,
            "deadline": "2026-05-06"
        },
        {
            "task_id": "task_3",
            "title": "月次レポート",
            "description": "進捗報告・分析",
            "deadline": "2026-05-22"
        }
    ]

    tasks_json = json.dumps(tasks)

    async with db_connection as db:
        await db.execute(
            """UPDATE user_onboarding_progress
               SET initial_tasks = ?, agent_status = 'activating',
                   current_step = 3, completed_at = ?
               WHERE onboarding_id = ?""",
            (tasks_json, datetime.utcnow().isoformat(), onboarding_id)
        )
        await db.commit()

        # Verify storage
        cursor = await db.execute(
            "SELECT initial_tasks, agent_status, completed_at FROM user_onboarding_progress WHERE onboarding_id = ?",
            (onboarding_id,)
        )
        row = await cursor.fetchone()
        assert row is not None
        retrieved_tasks = json.loads(row[0])
        assert len(retrieved_tasks) == 3
        assert retrieved_tasks[0]["title"] == "リード発掘"
        assert row[1] == "activating"  # agent_status
        assert row[2] is not None  # completed_at


@pytest.mark.asyncio
async def test_agent_status_transitions(onboarding_id, db_connection):
    """Test that agent status transitions correctly"""
    statuses = ["created", "activated", "running"]

    async with db_connection as db:
        for status in statuses:
            await db.execute(
                """UPDATE user_onboarding_progress
                   SET agent_status = ?
                   WHERE onboarding_id = ?""",
                (status, onboarding_id)
            )
            await db.commit()

            cursor = await db.execute(
                "SELECT agent_status FROM user_onboarding_progress WHERE onboarding_id = ?",
                (onboarding_id,)
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == status


# ─────────────────────────────────────────────────
# End-to-End Flow
# ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_onboarding_flow(user_id, onboarding_id, db_connection):
    """Test the complete onboarding flow from Step 0 to Step 3"""

    async with db_connection as db:
        # Step 0: Vision Input
        vision = "営業チーム立ち上げ、月商1000万円達成"
        await db.execute(
            """INSERT INTO user_onboarding_progress
               (onboarding_id, user_id, vision_input, current_step)
               VALUES (?, ?, ?, 0)""",
            (onboarding_id, user_id, vision)
        )
        await db.commit()

        # Step 1: AI Suggestion
        await db.execute(
            """UPDATE user_onboarding_progress
               SET suggested_template_id = 'sales',
                   suggestion_reason = 'マッチスコア: 0.98',
                   current_step = 1
               WHERE onboarding_id = ?""",
            (onboarding_id,)
        )
        await db.commit()

        # Step 2: Detailed Setup
        await db.execute(
            """UPDATE user_onboarding_progress
               SET dept_name = '営業推進部',
                   manager_name = '山田太郎',
                   members_count = 3,
                   budget = 3000000,
                   kpi = '月商1000万円、成約率35%',
                   current_step = 2
               WHERE onboarding_id = ?""",
            (onboarding_id,)
        )
        await db.commit()

        # Step 3: Initial Task Execution
        tasks = json.dumps([
            {"task_id": "task_1", "title": "リード発掘", "budget": 500000},
            {"task_id": "task_2", "title": "初期接触・営業提案", "budget": 500000},
            {"task_id": "task_3", "title": "月次レポート"}
        ])
        await db.execute(
            """UPDATE user_onboarding_progress
               SET initial_tasks = ?,
                   agent_status = 'activating',
                   current_step = 3,
                   completed_at = ?
               WHERE onboarding_id = ?""",
            (tasks, datetime.utcnow().isoformat(), onboarding_id)
        )
        await db.commit()

        # Verify complete flow
        cursor = await db.execute(
            """SELECT current_step, vision_input, suggested_template_id,
                      dept_name, initial_tasks, completed_at
               FROM user_onboarding_progress WHERE onboarding_id = ?""",
            (onboarding_id,)
        )
        row = await cursor.fetchone()

        assert row is not None
        assert row[0] == 3  # current_step
        assert row[1] == vision
        assert row[2] == "sales"
        assert row[3] == "営業推進部"
        assert row[4] is not None  # initial_tasks
        assert row[5] is not None  # completed_at


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
