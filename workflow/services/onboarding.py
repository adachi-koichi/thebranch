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
        prompt = f"""당신은 조직 구조 설계 전문가입니다. 사용자의 비전을 분석하여 가장 적합한 부서 템플릿을 제안해주세요.

사용자 비전:
"{vision_input}"

다음 부서 템플릿 중에서 비전과 가장 잘 맞는 2-3개를 선택하고, 각각에 대해:
1. template_id: 1-10 범위의 정수
2. name: 부서명
3. category: 부서 카테고리
4. total_roles: 역할 수
5. total_processes: 프로세스 수
6. reason: 이 템플릿을 선택한 이유 (50-100자)
7. rank: 적합도 순위 (1=가장 적합, 2=중간, 3=대안)

부서 템플릿 카탈로그:
- ID 1: 마케팅 (Marketing) - 4개 역할, 6개 프로세스
- ID 2: 영업 (Sales) - 5개 역할, 7개 프로세스
- ID 3: 엔지니어링 (Engineering) - 6개 역할, 8개 프로세스
- ID 4: 재무 (Finance) - 4개 역할, 5개 프로세스
- ID 5: 운영 (Operations) - 5개 역할, 6개 프로세스
- ID 6: 고객 지원 (Support) - 4개 역할, 6개 프로세스
- ID 7: 인사 (HR) - 4개 역할, 5개 프로세스
- ID 8: 법무 (Legal) - 3개 역할, 4개 프로세스
- ID 9: 제품 (Product) - 5개 역할, 6개 프로세스
- ID 10: 데이터 분석 (Analytics) - 4개 역할, 5개 프로세스

JSON 형식으로 응답하세요:
[
  {
    "template_id": <int>,
    "name": "<string>",
    "category": "<string>",
    "total_roles": <int>,
    "total_processes": <int>,
    "reason": "<string>",
    "rank": <int>
  }
]
"""

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
        prompt = f"""당신은 부서 목표 달성을 위한 작업 계획 전문가입니다. 주어진 정보를 기반으로 초기 작업을 생성해주세요.

부서 정보:
- 부서명: {dept_name}
- KPI: {kpi}
- 월 예산: ${budget}
- 팀원 수: {members_count}명

다음 요구사항을 만족하는 3-5개의 초기 작업을 생성하세요:
1. task_id: "task_001" 형식
2. title: 작업 제목 (30자 이내)
3. description: 작업 설명 (50-100자)
4. budget: 작업 예산 (USD, 전체 예산의 합 ≤ {budget})
5. deadline: 기한 (YYYY-MM-DD 형식, 30일 이내)
6. assigned_to: 담당자 역할

JSON 형식으로 응답하세요:
[
  {{
    "task_id": "<string>",
    "title": "<string>",
    "description": "<string>",
    "budget": <float>,
    "deadline": "<YYYY-MM-DD>",
    "assigned_to": "<string>"
  }}
]
"""

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
