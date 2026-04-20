"""Unit tests for TemplateService"""

import pytest
from datetime import datetime
from workflow.models import Template, Phase, TaskDef
from workflow.exceptions import ValidationError, TemplateNotFoundError
from workflow.services.template import TemplateService


class TestTemplateServiceCreateTemplate:
    """TemplateService.create_template tests"""

    def test_create_template_valid(self, template_service, template_repo_mock):
        """Create template with valid inputs"""
        expected = Template(
            id=1,
            name="Product Launch",
            description="Standard product launch process",
            status="draft",
            created_by="alice@example.com",
            created_at=datetime.now(),
        )
        template_repo_mock.create_template.return_value = expected

        result = template_service.create_template(
            name="Product Launch",
            description="Standard product launch process",
            created_by="alice@example.com",
        )

        assert result.id == 1
        assert result.name == "Product Launch"
        assert result.status == "draft"
        template_repo_mock.create_template.assert_called_once()

    def test_create_template_empty_name(self, template_service):
        """Create template with empty name raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            template_service.create_template(name="")
        assert "Invalid template name" in str(exc_info.value)

    def test_create_template_name_too_long(self, template_service):
        """Create template with name >255 chars raises ValidationError"""
        with pytest.raises(ValidationError):
            template_service.create_template(name="x" * 256)

    def test_create_template_minimal(self, template_service, template_repo_mock):
        """Create template with only name"""
        expected = Template(id=2, name="Minimal", status="draft")
        template_repo_mock.create_template.return_value = expected

        result = template_service.create_template(name="Minimal")

        assert result.id == 2
        assert result.name == "Minimal"
        template_repo_mock.create_template.assert_called_once()


class TestTemplateServiceAddPhase:
    """TemplateService.add_phase tests"""

    def test_add_phase_valid(self, template_service, template_repo_mock, template_validator_mock):
        """Add phase with valid inputs"""
        template_repo_mock.get_template.return_value = Template(
            id=1, name="Product Launch", status="draft"
        )
        expected_phase = Phase(
            id=1,
            template_id=1,
            phase_key="planning",
            phase_label="Planning",
            specialist_type="pm",
            phase_order=1,
            is_parallel=False,
        )
        template_repo_mock.create_phase.return_value = expected_phase

        result = template_service.add_phase(
            template_id=1,
            phase_key="planning",
            phase_label="Planning",
            specialist_type="pm",
            phase_order=1,
        )

        assert result.id == 1
        assert result.phase_key == "planning"
        template_repo_mock.create_phase.assert_called_once()

    def test_add_phase_template_not_found(self, template_service, template_repo_mock):
        """Add phase to non-existent template raises TemplateNotFoundError"""
        template_repo_mock.get_template.return_value = None

        with pytest.raises(TemplateNotFoundError):
            template_service.add_phase(
                template_id=999,
                phase_key="planning",
                phase_label="Planning",
                specialist_type="pm",
                phase_order=1,
            )

    def test_add_phase_not_draft(self, template_service, template_repo_mock):
        """Add phase to published template raises ValidationError"""
        template_repo_mock.get_template.return_value = Template(
            id=1, name="Product Launch", status="published"
        )

        with pytest.raises(ValidationError) as exc_info:
            template_service.add_phase(
                template_id=1,
                phase_key="planning",
                phase_label="Planning",
                specialist_type="pm",
                phase_order=1,
            )
        assert "Cannot add phase to non-draft" in str(exc_info.value)


class TestTemplateServiceAddTaskToPhase:
    """TemplateService.add_task_to_phase tests"""

    def test_add_task_to_phase_valid(self, template_service, template_repo_mock):
        """Add task to phase with valid inputs"""
        phase = Phase(
            id=1, template_id=1, phase_key="planning", phase_label="Planning",
            specialist_type="pm", phase_order=1
        )
        template_repo_mock.get_phase.return_value = phase

        template = Template(
            id=1, name="Product Launch", status="draft",
            created_by="alice@example.com"
        )
        template_repo_mock.get_template.return_value = template

        expected_task = TaskDef(
            id=1,
            phase_id=1,
            template_id=1,
            task_key="design-arch",
            task_title="Design Architecture",
            task_description="Create architecture",
            priority=1,
        )
        template_repo_mock.create_task_def.return_value = expected_task

        result = template_service.add_task_to_phase(
            phase_id=1,
            task_key="design-arch",
            task_title="Design Architecture",
            task_description="Create architecture",
        )

        assert result.id == 1
        assert result.task_key == "design-arch"
        template_repo_mock.create_task_def.assert_called_once()

    def test_add_task_phase_not_found(self, template_service, template_repo_mock):
        """Add task to non-existent phase raises error"""
        template_repo_mock.get_phase.return_value = None

        with pytest.raises(Exception):
            template_service.add_task_to_phase(
                phase_id=999,
                task_key="task1",
                task_title="Task 1",
            )


class TestTemplateServicePublish:
    """TemplateService.publish_template tests"""

    def test_publish_valid_template(self, template_service, template_repo_mock, template_validator_mock):
        """Publish template with valid content"""
        template = Template(id=1, name="Product Launch", status="draft")
        template_repo_mock.get_template.return_value = template

        result = template_service.publish_template(1)

        assert result.status == "published"
        template_repo_mock.update_template.assert_called_once()
        template_validator_mock.validate_template_complete.assert_called_once()

    def test_publish_already_published(self, template_service, template_repo_mock):
        """Publish already-published template raises ValidationError"""
        template_repo_mock.get_template.return_value = Template(
            id=1, name="Product Launch", status="published"
        )

        with pytest.raises(ValidationError) as exc_info:
            template_service.publish_template(1)
        assert "Cannot publish non-draft" in str(exc_info.value)
