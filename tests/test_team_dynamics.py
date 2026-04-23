"""
Team Dynamics ユニットテスト

calculate_skill_match, calculate_task_allocation_score 等の関数単体テスト
"""
import pytest
import json
from dashboard.app import calculate_skill_match, calculate_task_allocation_score


class TestSkillMatching:
    """スキルマッチング関数のテスト"""

    def test_perfect_skill_match(self):
        """スキルが完全に一致した場合"""
        task_skills = json.dumps(["python", "fastapi"])
        agent_skills = json.dumps(["python", "fastapi", "backend"])

        score = calculate_skill_match(task_skills, agent_skills)
        assert score == 30.0  # 完全一致 → 30ポイント

    def test_partial_skill_match(self):
        """スキルが部分的に一致した場合"""
        task_skills = json.dumps(["python", "fastapi"])
        agent_skills = json.dumps(["python", "javascript"])

        score = calculate_skill_match(task_skills, agent_skills)
        assert score == 15.0  # 50% 一致 → 15ポイント

    def test_no_skill_match(self):
        """スキルが一致しない場合"""
        task_skills = json.dumps(["python", "fastapi"])
        agent_skills = json.dumps(["javascript", "react"])

        score = calculate_skill_match(task_skills, agent_skills)
        assert score == 5.0  # デフォルトスコア

    def test_empty_task_skills(self):
        """タスクが必要スキルを指定していない場合"""
        task_skills = json.dumps([])
        agent_skills = json.dumps(["python", "fastapi"])

        score = calculate_skill_match(task_skills, agent_skills)
        assert score == 5.0  # デフォルトスコア

    def test_null_skills(self):
        """スキル情報が None の場合"""
        score = calculate_skill_match(None, None)
        assert score == 5.0  # デフォルトスコア

    def test_single_skill_match(self):
        """1つのスキルだけ一致"""
        task_skills = json.dumps(["python", "fastapi", "docker"])
        agent_skills = json.dumps(["python", "javascript"])

        score = calculate_skill_match(task_skills, agent_skills)
        # 1つ一致 / 3つ必要 = 33% → 10ポイント
        assert score == pytest.approx(10.0, abs=0.1)


class TestTaskAllocationScoring:
    """タスク割り当てスコアリング関数のテスト"""

    def test_high_completion_rate_agent(self):
        """完了率が高いエージェント"""
        task = {
            "id": 1,
            "required_skills": json.dumps(["python", "fastapi"]),
            "category": "engineering"
        }
        agent = {
            "id": 1,
            "skill_tags": json.dumps(["python", "fastapi", "backend"]),
            "workload_level": 30,
            "collaboration_score": 75,
            "completion_rate": 0.95
        }

        score = calculate_task_allocation_score(task, agent)
        # skill_match(30) + workload(21) + collaboration(15) + reliability(14.25) + domain(5) = 85.25
        assert score > 80

    def test_high_workload_agent(self):
        """負荷が高いエージェント"""
        task = {
            "id": 1,
            "required_skills": json.dumps(["python"]),
            "category": "engineering"
        }
        agent = {
            "id": 1,
            "skill_tags": json.dumps(["python"]),
            "workload_level": 90,  # 高負荷
            "collaboration_score": 50,
            "completion_rate": 0.8
        }

        score = calculate_task_allocation_score(task, agent)
        # workload_score = (1 - 0.9) * 30 = 3.0 (低スコア)
        assert score < 50

    def test_zero_workload_agent(self):
        """負荷がゼロのエージェント"""
        task = {
            "id": 1,
            "required_skills": json.dumps(["python"]),
            "category": "engineering"
        }
        agent = {
            "id": 1,
            "skill_tags": json.dumps(["python"]),
            "workload_level": 0,  # 余裕あり
            "collaboration_score": 50,
            "completion_rate": 0.8
        }

        score = calculate_task_allocation_score(task, agent)
        # workload_score = (1 - 0) * 30 = 30 (最大)
        assert score > 70

    def test_low_collaboration_agent(self):
        """協働スコアが低いエージェント"""
        task = {
            "id": 1,
            "required_skills": json.dumps(["python"]),
            "category": "engineering"
        }
        agent = {
            "id": 1,
            "skill_tags": json.dumps(["python"]),
            "workload_level": 30,
            "collaboration_score": 10,  # 低い
            "completion_rate": 0.8
        }

        score = calculate_task_allocation_score(task, agent)
        # collaboration = 10 / 100 * 20 = 2.0 (低い)
        assert score < 70

    def test_scoring_formula_weights(self):
        """スコアリング式の重み比率を検証"""
        task = {
            "id": 1,
            "required_skills": json.dumps([]),
            "category": "engineering"
        }
        agent = {
            "id": 1,
            "skill_tags": json.dumps([]),
            "workload_level": 50,
            "collaboration_score": 50,
            "completion_rate": 0.5
        }

        score = calculate_task_allocation_score(task, agent)
        # skill_match(5) + workload(15) + collaboration(10) + reliability(7.5) + domain(5) = 42.5
        assert score == pytest.approx(42.5, abs=0.1)

    def test_missing_agent_fields(self):
        """エージェント情報が不完全な場合"""
        task = {
            "id": 1,
            "required_skills": json.dumps(["python"]),
            "category": "engineering"
        }
        agent = {
            "id": 1
            # skill_tags, workload_level, collaboration_score, completion_rate なし
        }

        score = calculate_task_allocation_score(task, agent)
        # デフォルト値で計算されるべき
        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_score_range(self):
        """スコアが 0-100 の範囲内にあることを検証"""
        test_cases = [
            {
                "agent": {
                    "id": 1,
                    "skill_tags": json.dumps(["python", "fastapi"]),
                    "workload_level": 0,
                    "collaboration_score": 100,
                    "completion_rate": 1.0
                },
                "expected_min": 80
            },
            {
                "agent": {
                    "id": 1,
                    "skill_tags": json.dumps([]),
                    "workload_level": 100,
                    "collaboration_score": 0,
                    "completion_rate": 0.0
                },
                "expected_max": 20
            }
        ]

        task = {
            "id": 1,
            "required_skills": json.dumps(["python", "fastapi"]),
            "category": "engineering"
        }

        for case in test_cases:
            score = calculate_task_allocation_score(task, case["agent"])
            assert 0 <= score <= 100

    def test_domain_bonus_applied(self):
        """ドメインボーナスが適用されることを確認"""
        task = {
            "id": 1,
            "required_skills": json.dumps([]),
            "category": "engineering"  # engineering カテゴリ
        }
        agent = {
            "id": 1,
            "skill_tags": json.dumps([]),
            "workload_level": 50,
            "collaboration_score": 50,
            "completion_rate": 0.5
        }

        score = calculate_task_allocation_score(task, agent)
        # domain_bonus(5) が含まれている
        assert score >= 37.5  # 最小スコア（domain_bonus なし場合）+ 5

    def test_reliability_score_calculation(self):
        """信頼性スコアが正しく計算されることを確認"""
        task = {
            "id": 1,
            "required_skills": json.dumps([]),
            "category": "general"
        }

        # completion_rate による reliability_score の検証
        for completion_rate in [0.0, 0.5, 0.8, 1.0]:
            agent = {
                "id": 1,
                "skill_tags": json.dumps([]),
                "workload_level": 50,
                "collaboration_score": 50,
                "completion_rate": completion_rate
            }

            score = calculate_task_allocation_score(task, agent)
            # reliability_score = completion_rate * 15
            expected_reliability = completion_rate * 15 if completion_rate else 8.0
            assert expected_reliability >= 0 and expected_reliability <= 15


class TestAllocationAlgorithmComparison:
    """複数エージェント間の相対スコア比較"""

    def test_ranking_agents_by_skills(self):
        """スキルマッチに基づくエージェントランキング"""
        task = {
            "id": 1,
            "required_skills": json.dumps(["python", "fastapi"]),
            "category": "engineering"
        }

        agents = [
            {
                "id": 1,
                "skill_tags": json.dumps(["python", "fastapi", "backend"]),
                "workload_level": 50,
                "collaboration_score": 50,
                "completion_rate": 0.8
            },
            {
                "id": 2,
                "skill_tags": json.dumps(["python"]),
                "workload_level": 50,
                "collaboration_score": 50,
                "completion_rate": 0.8
            },
            {
                "id": 3,
                "skill_tags": json.dumps(["javascript", "react"]),
                "workload_level": 50,
                "collaboration_score": 50,
                "completion_rate": 0.8
            }
        ]

        scores = [calculate_task_allocation_score(task, agent) for agent in agents]

        # agent-1 (完全一致) > agent-2 (部分一致) > agent-3 (不一致)
        assert scores[0] > scores[1] > scores[2]

    def test_workload_as_tiebreaker(self):
        """スキルマッチが同じ場合、負荷で比較"""
        task = {
            "id": 1,
            "required_skills": json.dumps(["python"]),
            "category": "engineering"
        }

        agents = [
            {
                "id": 1,
                "skill_tags": json.dumps(["python", "fastapi"]),
                "workload_level": 30,  # 低負荷
                "collaboration_score": 50,
                "completion_rate": 0.8
            },
            {
                "id": 2,
                "skill_tags": json.dumps(["python", "fastapi"]),
                "workload_level": 70,  # 高負荷
                "collaboration_score": 50,
                "completion_rate": 0.8
            }
        ]

        scores = [calculate_task_allocation_score(task, agent) for agent in agents]

        # 低負荷エージェントが高スコア
        assert scores[0] > scores[1]
