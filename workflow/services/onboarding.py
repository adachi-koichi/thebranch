import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# 급여 시장 벤치마크 (부서 유형별, 인원수별)
SALARY_BENCHMARKS = {
    "marketing": {"1": 5000, "2-3": 4500, "4-5": 4200, "6+": 4000},
    "sales": {"1": 6000, "2-3": 5500, "4-5": 5000, "6+": 4700},
    "engineering": {"1": 7000, "2-3": 6500, "4-5": 6000, "6+": 5500},
    "finance": {"1": 5500, "2-3": 5000, "4-5": 4700, "6+": 4400},
    "operations": {"1": 4500, "2-3": 4200, "4-5": 4000, "6+": 3800},
    "support": {"1": 4000, "2-3": 3700, "4-5": 3500, "6+": 3300},
}

class OnboardingService:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-opus-4-7"

    def analyze_vision_for_templates(self, vision_input: str) -> List[Dict[str, Any]]:
        """
        Vision 텍스트를 분석하여 적합한 부서 템플릿 제안을 생성합니다.

        Args:
            vision_input: 사용자의 비전 입력 텍스트 (10-500자)

        Returns:
            TemplateSuggestion 형태의 제안 목록 (최소 2개)
        """
        prompt = """あなたは組織設計の専門家です。ユーザーのビジョンを分析し、最適な部署テンプレートを提案してください。

ユーザーのビジョン:
"{vision_input}"

以下の部署テンプレートカタログから、ビジョンに最も合致する2〜3個を選択し、それぞれについて:
1. template_id: 1〜10の整数
2. name: 部署名
3. category: 部署カテゴリ
4. total_roles: 役割数
5. total_processes: プロセス数
6. reason: このテンプレートを選んだ理由（50〜100文字）
7. rank: 適合度ランク（1=最適、2=中位、3=代替）

部署テンプレートカタログ:
- ID 1: マーケティング (Marketing) - 4役割、6プロセス
- ID 2: 営業 (Sales) - 5役割、7プロセス
- ID 3: エンジニアリング (Engineering) - 6役割、8プロセス
- ID 4: 財務 (Finance) - 4役割、5プロセス
- ID 5: オペレーション (Operations) - 5役割、6プロセス
- ID 6: カスタマーサポート (Support) - 4役割、6プロセス
- ID 7: 人事 (HR) - 4役割、5プロセス
- ID 8: 法務 (Legal) - 3役割、4プロセス
- ID 9: プロダクト (Product) - 5役割、6プロセス
- ID 10: データ分析 (Analytics) - 4役割、5プロセス

JSON形式で回答してください:
[
  {{
    "template_id": 1,
    "name": "部署名",
    "category": "カテゴリ",
    "total_roles": 4,
    "total_processes": 6,
    "reason": "選択理由",
    "rank": 1
  }}
]
""".format(vision_input=vision_input)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = message.content[0].text
            # JSON 추출
            try:
                suggestions = json.loads(response_text)
            except json.JSONDecodeError:
                # JSON 블록 추출 시도
                start = response_text.find("[")
                end = response_text.rfind("]") + 1
                if start >= 0 and end > start:
                    suggestions = json.loads(response_text[start:end])
                else:
                    raise ValueError("Valid JSON not found in response")

            # rank별로 정렬
            suggestions.sort(key=lambda x: x.get("rank", 999))
            return suggestions[:3]  # 최대 3개 반환

        except Exception as e:
            logger.error(f"Vision 분석 실패: {str(e)}")
            # 기본 제안 반환
            return self._get_default_suggestions()

    def generate_initial_tasks(
        self,
        dept_name: str,
        kpi: str,
        budget: float,
        members_count: int
    ) -> List[Dict[str, Any]]:
        """
        부서 KPI와 예산을 기반으로 초기 작업을 자동 생성합니다.

        Args:
            dept_name: 부서명
            kpi: 부서의 핵심 성과지표 (예: "월 매출 10% 증가")
            budget: 월 예산 (USD)
            members_count: 팀원 수

        Returns:
            InitialTask 형태의 작업 목록 (3-5개)
        """
        prompt = """あなたは部署目標達成のためのタスク計画専門家です。以下の情報をもとに初期タスクを生成してください。

部署情報:
- 部署名: {dept_name}
- KPI: {kpi}
- 月次予算: ${budget}
- チームメンバー数: {members_count}名

以下の要件を満たす3〜5個の初期タスクを生成してください:
1. task_id: "task_001" 形式
2. title: タスクタイトル（30文字以内）
3. description: タスク説明（50〜100文字）
4. budget: タスク予算（USD、合計が{budget}以下）
5. deadline: 期限（YYYY-MM-DD形式、30日以内）
6. assigned_to: 担当者の役割（日本語）

JSON形式で回答してください:
[
  {{
    "task_id": "task_001",
    "title": "タスクタイトル",
    "description": "タスク説明",
    "budget": 1000.0,
    "deadline": "2026-05-30",
    "assigned_to": "マネージャー"
  }}
]
""".format(dept_name=dept_name, kpi=kpi, budget=budget, members_count=members_count)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = message.content[0].text
            # JSON 추출
            try:
                tasks = json.loads(response_text)
            except json.JSONDecodeError:
                start = response_text.find("[")
                end = response_text.rfind("]") + 1
                if start >= 0 and end > start:
                    tasks = json.loads(response_text[start:end])
                else:
                    raise ValueError("Valid JSON not found in response")

            # 예산 검증 및 조정
            total_budget = sum(t.get("budget", 0) for t in tasks)
            if total_budget > budget:
                scale_factor = budget / total_budget
                for task in tasks:
                    task["budget"] = round(task["budget"] * scale_factor, 2)

            return tasks[:5]  # 최대 5개 반환

        except Exception as e:
            logger.error(f"초기 작업 생성 실패: {str(e)}")
            # 기본 작업 반환
            return self._get_default_tasks(dept_name, budget, members_count)

    def validate_budget(
        self,
        members_count: int,
        budget: float,
        dept_type: str
    ) -> Dict[str, Any]:
        """
        예산이 시장 벤치마크에 대비 적절한지 검증합니다.

        Args:
            members_count: 팀원 수
            budget: 월 예산 (USD)
            dept_type: 부서 유형 (예: "marketing", "engineering")

        Returns:
            BudgetValidation 형태의 검증 결과
        """
        dept_type = dept_type.lower()

        # 급여 벤치마크 조회
        benchmarks = SALARY_BENCHMARKS.get(dept_type, SALARY_BENCHMARKS["operations"])

        # 인원수 범위 결정
        if members_count == 1:
            range_key = "1"
        elif 2 <= members_count <= 3:
            range_key = "2-3"
        elif 4 <= members_count <= 5:
            range_key = "4-5"
        else:
            range_key = "6+"

        market_benchmark = benchmarks.get(range_key, 4000)
        monthly_per_person = budget / members_count if members_count > 0 else 0

        # 상태 결정
        if monthly_per_person >= market_benchmark:
            status = "ok"
            message = f"예산이 적절합니다. 인당 ${monthly_per_person:.0f}/월 (벤치마크: ${market_benchmark}/월)"
        elif monthly_per_person >= market_benchmark * 0.8:
            status = "warning"
            message = f"예산이 약간 낮습니다. 인당 ${monthly_per_person:.0f}/월 (권장: ${market_benchmark}/월)"
        else:
            status = "error"
            message = f"예산이 부족합니다. 인당 ${monthly_per_person:.0f}/월 (최소: ${market_benchmark * 0.8:.0f}/월)"

        return {
            "status": status,
            "monthly_per_person": round(monthly_per_person, 2),
            "market_benchmark": market_benchmark,
            "message": message
        }

    def _get_default_suggestions(self) -> List[Dict[str, Any]]:
        """기본 템플릿 제안을 반환합니다."""
        return [
            {
                "template_id": 1,
                "name": "마케팅",
                "category": "Marketing",
                "total_roles": 4,
                "total_processes": 6,
                "reason": "일반적인 부서 구조로 추천됩니다.",
                "rank": 1
            },
            {
                "template_id": 2,
                "name": "영업",
                "category": "Sales",
                "total_roles": 5,
                "total_processes": 7,
                "reason": "매출 중심 조직에 적합합니다.",
                "rank": 2
            }
        ]

    def _get_default_tasks(
        self,
        dept_name: str,
        budget: float,
        members_count: int
    ) -> List[Dict[str, Any]]:
        """기본 작업 목록을 반환합니다."""
        now = datetime.now()
        deadline_1 = (now + timedelta(days=7)).strftime("%Y-%m-%d")
        deadline_2 = (now + timedelta(days=14)).strftime("%Y-%m-%d")
        deadline_3 = (now + timedelta(days=30)).strftime("%Y-%m-%d")

        task_budget = budget / 3

        return [
            {
                "task_id": "task_001",
                "title": f"{dept_name} 팀 온보딩 완료",
                "description": "팀원들의 시스템 접근권 설정 및 기본 교육",
                "budget": round(task_budget, 2),
                "deadline": deadline_1,
                "assigned_to": "Manager"
            },
            {
                "task_id": "task_002",
                "title": "부서 프로세스 수립",
                "description": "일일/주간/월간 업무 프로세스 정의 및 문서화",
                "budget": round(task_budget, 2),
                "deadline": deadline_2,
                "assigned_to": "Lead"
            },
            {
                "task_id": "task_003",
                "title": "성과 지표(KPI) 수립",
                "description": "부서의 핵심 성과지표를 정의하고 대시보드 구성",
                "budget": round(task_budget, 2),
                "deadline": deadline_3,
                "assigned_to": "Analyst"
            }
        ]


# 싱글톤 인스턴스
_onboarding_service = None

def get_onboarding_service() -> OnboardingService:
    """OnboardingService 싱글톤 인스턴스를 반환합니다."""
    global _onboarding_service
    if _onboarding_service is None:
        _onboarding_service = OnboardingService()
    return _onboarding_service
