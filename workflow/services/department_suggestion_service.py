"""Department suggestion service using Claude API"""

import json
import logging
import sqlite3
from typing import Optional, List
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

from dashboard import models
from workflow.services.cost_service import CostTrackingService

logger = logging.getLogger(__name__)


class DepartmentSuggestionService:
    """
    Claude API を使用した部署構成提案サービス。
    ビジョン入力を分析し、最適なテンプレート順序を提案する。
    """

    def __init__(
        self,
        db_path: str,
        cost_service: CostTrackingService
    ) -> None:
        self.db_path = db_path
        self.cost_service = cost_service
        if Anthropic is None:
            logger.warning("Anthropic library not available")
            self.anthropic = None
        else:
            try:
                self.anthropic = Anthropic()
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {str(e)}")
                self.anthropic = None

    def suggest_departments(
        self,
        vision_input: str,
        user_context: Optional[dict] = None,
    ) -> List[models.TemplateSuggestion]:
        """
        Claude API で vision_input を分析 → テンプレート提案順序を返す。

        Returns:
            TemplateSuggestion のリスト（推奨順）
        """
        try:
            # Get all templates from database
            templates = self._get_all_templates()
            if not templates:
                logger.warning("No templates found in database")
                return []

            # Prepare template context for Claude
            template_descriptions = self._prepare_template_context(templates)

            # If Anthropic is not configured, return default suggestions
            if self.anthropic is None:
                logger.warning("Claude API not configured, returning default suggestions")
                return [
                    models.TemplateSuggestion(
                        template_id=t['id'],
                        name=t['name'],
                        category=t['category'],
                        total_roles=t.get('total_roles', 0),
                        total_processes=t.get('total_processes', 0),
                        reason="推奨テンプレート（自動選択）",
                        rank=idx + 1
                    )
                    for idx, t in enumerate(templates[:3])
                ]

            try:
                # Call Claude API
                response = self.anthropic.messages.create(
                    model="claude-opus-4-7",
                    max_tokens=1000,
                    system=[
                        {
                            "type": "text",
                            "text": "You are an expert in organizational structure design. "
                                   "Based on the user's vision, recommend the best department templates "
                                   "in order of relevance. Return a JSON array with template rankings."
                        }
                    ],
                    messages=[
                        {
                            "role": "user",
                            "content": f"""
Vision Input: {vision_input}

Available Templates:
{template_descriptions}

Please analyze the vision and recommend the top 3 templates that best fit this organization's needs.
Return a JSON array with this format (ONLY JSON, no other text):
[
  {{
    "template_id": <id>,
    "rank": 1
  }},
  ...
]

Be specific about why each template matches the vision.
"""
                        }
                    ]
                )

                # Record API cost
                self._record_api_cost(response)

                # Parse response and build suggestions
                suggestions = self._parse_suggestions(response, templates)

                return suggestions

            except Exception as api_error:
                # If API call fails, return default suggestions as fallback
                logger.warning(f"Claude API call failed, returning default suggestions: {str(api_error)}")
                return [
                    models.TemplateSuggestion(
                        template_id=t['id'],
                        name=t['name'],
                        category=t['category'],
                        total_roles=t.get('total_roles', 0),
                        total_processes=t.get('total_processes', 0),
                        reason="推奨テンプレート（自動選択）",
                        rank=idx + 1
                    )
                    for idx, t in enumerate(templates[:3])
                ]

        except Exception as e:
            logger.error(f"Error suggesting departments: {str(e)}")
            raise

    def _get_all_templates(self) -> List[dict]:
        """データベースから全テンプレートを取得"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, category, total_roles, total_processes FROM departments_templates WHERE status = 'active'"
            )
            templates = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return templates
        except Exception as e:
            logger.error(f"Error fetching templates: {str(e)}")
            return []

    def _prepare_template_context(self, templates: List[dict]) -> str:
        """テンプレート情報を Claude API 用に整形"""
        context_lines = []
        for template in templates:
            context_lines.append(
                f"ID: {template['id']}, Name: {template['name']}, "
                f"Category: {template['category']}, "
                f"Roles: {template.get('total_roles', 0)}, "
                f"Processes: {template.get('total_processes', 0)}"
            )
        return "\n".join(context_lines)

    def _parse_suggestions(
        self,
        response,
        templates: List[dict]
    ) -> List[models.TemplateSuggestion]:
        """Claude API レスポンスを TemplateSuggestion リストに変換"""
        suggestions = []

        try:
            # Extract JSON from response
            response_text = response.content[0].text

            # Try to parse JSON - look for array
            json_str = response_text
            if "[" in response_text and "]" in response_text:
                start = response_text.index("[")
                end = response_text.rindex("]") + 1
                json_str = response_text[start:end]

            rankings = json.loads(json_str)

            # Create template lookup
            template_lookup = {t['id']: t for t in templates}

            # Build suggestions with reasons
            for rank, item in enumerate(rankings, 1):
                template_id = item.get('template_id')
                if template_id not in template_lookup:
                    continue

                template = template_lookup[template_id]

                suggestion = models.TemplateSuggestion(
                    template_id=template_id,
                    name=template['name'],
                    category=template['category'],
                    total_roles=template.get('total_roles', 0),
                    total_processes=template.get('total_processes', 0),
                    reason=item.get('reason', f"Recommended template {rank}"),
                    rank=rank
                )
                suggestions.append(suggestion)

            return suggestions

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Error parsing Claude suggestions: {str(e)}")
            # Return all templates as fallback if parsing fails
            return [
                models.TemplateSuggestion(
                    template_id=t['id'],
                    name=t['name'],
                    category=t['category'],
                    total_roles=t.get('total_roles', 0),
                    total_processes=t.get('total_processes', 0),
                    reason="Standard template",
                    rank=idx + 1
                )
                for idx, t in enumerate(templates[:3])
            ]

    def _record_api_cost(self, response) -> None:
        """API コストを CostTrackingService で記録"""
        try:
            usage = response.usage

            # Calculate cost (Claude Opus 4.7 pricing)
            # Input: $3 per 1M tokens, Output: $15 per 1M tokens
            input_cost = (usage.input_tokens / 1_000_000) * 3.0
            output_cost = (usage.output_tokens / 1_000_000) * 15.0
            cache_creation_cost = (getattr(usage, 'cache_creation_input_tokens', 0) / 1_000_000) * 3.75
            cache_read_cost = (getattr(usage, 'cache_read_input_tokens', 0) / 1_000_000) * 0.3

            total_cost = input_cost + output_cost + cache_creation_cost + cache_read_cost

            # Record (department_id=None since this is during onboarding)
            self.cost_service.record_api_call(
                department_id=None,
                agent_id=None,
                api_provider='claude',
                model_name='claude-opus-4-7',
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=getattr(usage, 'cache_read_input_tokens', 0),
                cache_creation_tokens=getattr(usage, 'cache_creation_input_tokens', 0),
                cost_usd=total_cost,
                status='completed'
            )
        except Exception as e:
            logger.error(f"Error recording API cost: {str(e)}")
