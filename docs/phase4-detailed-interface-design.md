# Phase 4: ワークフローテンプレートシステム - 詳細インターフェース設計

**作成日**: 2026-04-18  
**バージョン**: v1.0 (Phase 4 - Detailed Design)  
**参照**: architecture-design.md, flow-design.md, data-model.md

---

## 目次

1. [モジュール分割方針](#1-モジュール分割方針)
2. [Template Module](#2-template-module)
3. [Instance Module](#3-instance-module)
4. [Task-Gen Module](#4-task-gen-module)
5. [Assignment Module](#5-assignment-module)
6. [モジュール間相互作用](#6-モジュール間相互作用)
7. [例外階層](#7-例外階層)

---

## 1. モジュール分割方針

### 1-1. ディレクトリ構造

```
workflow/
├── __init__.py
├── models/                      # Data models
│   ├── __init__.py
│   ├── template.py              # Template, Phase, TaskDef models
│   ├── instance.py              # WorkflowInstance, PhaseInstance models
│   ├── task.py                  # DevTask, TaskDependency models
│   └── specialist.py            # SpecialistAssignment, Agent models
├── services/                    # Business logic
│   ├── __init__.py
│   ├── template.py              # TemplateService
│   ├── instance.py              # WorkflowInstanceService
│   ├── task_gen.py              # TaskGenerationService
│   └── assignment.py            # SpecialistAssignmentService
├── repositories/                # Data access layer
│   ├── __init__.py
│   ├── base.py                  # BaseRepository
│   ├── template.py              # TemplateRepository
│   ├── instance.py              # InstanceRepository
│   ├── task.py                  # TaskRepository
│   ├── specialist.py            # SpecialistRepository
│   └── graph.py                 # GraphRepository (KuzuDB)
├── validation/                  # Validation logic
│   ├── __init__.py
│   ├── template.py              # TemplateValidator
│   ├── instance.py              # InstanceValidator
│   └── assignment.py            # AssignmentValidator
├── exceptions.py                # Custom exceptions
└── cli/                         # CLI interface
    ├── __init__.py
    └── commands.py              # wf template / wf instance commands
```

### 1-2. モジュール責務

| モジュール | 責務 | 参照レイヤー |
|-----------|------|-----------|
| **Template** | テンプレート CRUD、フェーズ・タスク定義管理 | Service, Repository, Validator |
| **Instance** | インスタンス化、ライフサイクル、状態遷移 | Service, Repository, Graph |
| **Task-Gen** | タスク生成、依存関係構築、プレースホルダ置換 | Service, Repository, Graph, Validator |
| **Assignment** | Specialist 割り当て、検証、型チェック | Service, Repository, Validator |

---

## 2. Template Module

### 2-1. データモデル

```python
# workflow/models/template.py

@dataclass
class TaskDef:
    """Task definition within a phase"""
    id: int | None = None
    phase_id: int | None = None
    template_id: int | None = None
    task_key: str                              # Unique within phase
    task_title: str                            # May contain {placeholders}
    task_description: str | None = None        # May contain {placeholders}
    category: str | None = None                # 'design', 'impl', 'test', etc
    depends_on_key: str | None = None          # Intra-phase dependency
    priority: int = 1                          # 1-5
    estimated_hours: float | None = None
    task_order: int = 0                        # Execution order within phase
    created_at: datetime | None = None

@dataclass
class Phase:
    """Phase definition within template"""
    id: int | None = None
    template_id: int | None = None
    phase_key: str                             # 'planning', 'development', etc
    phase_label: str                           # Display name
    specialist_type: str                       # 'pm', 'engineer', 'qa', 'devops'
    phase_order: int                           # Execution order
    is_parallel: bool = False                  # Parallel with previous phase
    task_count: int = 0                        # Denormalized
    tasks: list[TaskDef] | None = None         # Nested tasks
    created_at: datetime | None = None

@dataclass
class Template:
    """Workflow template (immutable after creation)"""
    id: int | None = None
    name: str                                  # 'Product Launch', etc
    description: str | None = None
    status: str = 'draft'                      # 'draft', 'published', 'archived'
    phases: list[Phase] | None = None          # Nested phases
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None              # Email or agent_id
```

### 2-2. TemplateService インターフェース

```python
# workflow/services/template.py

class TemplateService:
    """
    Template lifecycle management
    Responsibilities:
    - Create template
    - Add/update phases
    - Add/update tasks
    - Publish template
    - Query templates
    """
    
    def __init__(
        self,
        template_repo: TemplateRepository,
        validator: TemplateValidator
    ):
        self.template_repo = template_repo
        self.validator = validator
    
    # ===== CREATE =====
    
    def create_template(
        self,
        name: str,
        description: str | None = None,
        created_by: str | None = None
    ) -> Template:
        """
        Create new template in 'draft' status.
        
        Args:
            name: Template name (required, max 255 chars)
            description: Optional description
            created_by: Creator identifier (email or agent_id)
        
        Returns:
            Template object with assigned id
        
        Raises:
            ValidationError: If name is empty or invalid
            DatabaseError: If insertion fails
        
        Example:
            >>> tmpl = svc.create_template(
            ...     name="Product Launch",
            ...     description="Standard product launch process",
            ...     created_by="alice@example.com"
            ... )
            >>> print(tmpl.id)
            1
        """
        # Validate
        if not name or len(name) > 255:
            raise ValidationError(f"Invalid template name: {name}")
        
        # Create in DB
        template = self.template_repo.create_template(
            name=name,
            description=description,
            created_by=created_by,
            status='draft'
        )
        
        return template
    
    # ===== PHASE MANAGEMENT =====
    
    def add_phase(
        self,
        template_id: int,
        phase_key: str,
        phase_label: str,
        specialist_type: str,
        phase_order: int,
        is_parallel: bool = False
    ) -> Phase:
        """
        Add phase to template (must be in 'draft' status).
        
        Args:
            template_id: Parent template id
            phase_key: Unique identifier within template (e.g., 'planning')
            phase_label: Display name (e.g., 'Planning')
            specialist_type: Required agent type (pm, engineer, qa, devops)
            phase_order: Execution order (1-based)
            is_parallel: If True, can run parallel with previous phase
        
        Returns:
            Phase object with assigned id
        
        Raises:
            TemplateNotFoundError: If template_id doesn't exist
            ValidationError: If template is not in 'draft' status
            ValidationError: If phase_key already exists in template
            ValidationError: If phase_order is invalid
            DatabaseError: If insertion fails
        
        Example:
            >>> phase = svc.add_phase(
            ...     template_id=1,
            ...     phase_key='development',
            ...     phase_label='Development',
            ...     specialist_type='engineer',
            ...     phase_order=2
            ... )
        """
        # Get template
        template = self.template_repo.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        # Validate template is draft
        if template.status != 'draft':
            raise ValidationError(
                f"Cannot add phase to non-draft template (status={template.status})"
            )
        
        # Validate inputs
        self.validator.validate_phase(
            template_id=template_id,
            phase_key=phase_key,
            specialist_type=specialist_type,
            phase_order=phase_order
        )
        
        # Create in DB
        phase = self.template_repo.create_phase(
            template_id=template_id,
            phase_key=phase_key,
            phase_label=phase_label,
            specialist_type=specialist_type,
            phase_order=phase_order,
            is_parallel=is_parallel
        )
        
        return phase
    
    # ===== TASK MANAGEMENT =====
    
    def add_task_to_phase(
        self,
        phase_id: int,
        task_key: str,
        task_title: str,
        task_description: str | None = None,
        depends_on_key: str | None = None,
        priority: int = 1,
        estimated_hours: float | None = None,
        task_order: int = 0
    ) -> TaskDef:
        """
        Add task definition to phase.
        
        Args:
            phase_id: Parent phase id
            task_key: Unique identifier within phase (e.g., 'design-arch')
            task_title: Task name (supports {placeholders})
            task_description: Task details (supports {placeholders})
            depends_on_key: Reference to another task_key in same phase (for ordering)
            priority: 1-5 scale
            estimated_hours: Estimated effort
            task_order: Execution order within phase
        
        Returns:
            TaskDef object with assigned id
        
        Raises:
            PhaseNotFoundError: If phase_id doesn't exist
            ValidationError: If phase is not in draft status
            ValidationError: If task_key already exists in phase
            ValidationError: If depends_on_key references non-existent task
            ValidationError: If circular dependency detected
            DatabaseError: If insertion fails
        
        Example:
            >>> task = svc.add_task_to_phase(
            ...     phase_id=2,
            ...     task_key='design-arch',
            ...     task_title='Design {phase_label} Architecture',
            ...     task_description='Create architecture with {specialist_name}',
            ...     priority=1,
            ...     estimated_hours=8
            ... )
        """
        # Get phase
        phase = self.template_repo.get_phase(phase_id)
        if not phase:
            raise PhaseNotFoundError(f"Phase {phase_id} not found")
        
        # Get template (for status check)
        template = self.template_repo.get_template(phase.template_id)
        if template.status != 'draft':
            raise ValidationError(
                f"Cannot add task to non-draft template (status={template.status})"
            )
        
        # Validate inputs
        self.validator.validate_task_def(
            phase_id=phase_id,
            task_key=task_key,
            depends_on_key=depends_on_key
        )
        
        # Create in DB
        task = self.template_repo.create_task_def(
            phase_id=phase_id,
            template_id=phase.template_id,
            task_key=task_key,
            task_title=task_title,
            task_description=task_description,
            depends_on_key=depends_on_key,
            priority=priority,
            estimated_hours=estimated_hours,
            task_order=task_order
        )
        
        return task
    
    # ===== PUBLISH =====
    
    def publish_template(self, template_id: int) -> Template:
        """
        Publish template (transition from 'draft' to 'published').
        No further edits allowed after publishing.
        
        Args:
            template_id: Template to publish
        
        Returns:
            Updated template with status='published'
        
        Raises:
            TemplateNotFoundError: If template_id doesn't exist
            ValidationError: If template is not in 'draft' status
            ValidationError: If template has no phases or tasks
            CircularDependencyError: If circular dependency detected
            DatabaseError: If update fails
        
        Example:
            >>> tmpl = svc.publish_template(1)
            >>> assert tmpl.status == 'published'
        """
        # Get template
        template = self.template_repo.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        if template.status != 'draft':
            raise ValidationError(
                f"Cannot publish non-draft template (current status={template.status})"
            )
        
        # Validate template is complete
        self.validator.validate_template_complete(template_id)
        
        # Update status
        template.status = 'published'
        self.template_repo.update_template(template)
        
        return template
    
    # ===== QUERY =====
    
    def get_template(self, template_id: int) -> Template:
        """
        Get template with all phases and tasks (denormalized).
        
        Returns:
            Template with nested phases and tasks
        
        Raises:
            TemplateNotFoundError
        """
        template = self.template_repo.get_template_with_phases_and_tasks(
            template_id
        )
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        return template
    
    def list_templates(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[Template]:
        """
        List templates with optional filtering.
        
        Args:
            status: Filter by status ('draft', 'published', 'archived')
            limit: Max results
            offset: Pagination offset
        
        Returns:
            List of templates (without nested tasks, for performance)
        """
        return self.template_repo.list_templates(
            status=status,
            limit=limit,
            offset=offset
        )
```

### 2-3. TemplateRepository インターフェース

```python
# workflow/repositories/template.py

class TemplateRepository:
    """Data access for template layer"""
    
    def create_template(
        self,
        name: str,
        description: str | None,
        created_by: str | None,
        status: str
    ) -> Template:
        """Insert new template, return with id assigned"""
        ...
    
    def get_template(self, template_id: int) -> Template | None:
        """Get template (shallow, without phases)"""
        ...
    
    def get_template_with_phases_and_tasks(
        self,
        template_id: int
    ) -> Template | None:
        """Get template with nested phases and tasks"""
        ...
    
    def update_template(self, template: Template) -> None:
        """Update template (mainly status)"""
        ...
    
    def create_phase(
        self,
        template_id: int,
        phase_key: str,
        phase_label: str,
        specialist_type: str,
        phase_order: int,
        is_parallel: bool
    ) -> Phase:
        """Insert phase, return with id assigned"""
        ...
    
    def get_phase(self, phase_id: int) -> Phase | None:
        """Get phase by id"""
        ...
    
    def get_phases(
        self,
        template_id: int
    ) -> list[Phase]:
        """Get all phases for template, sorted by phase_order"""
        ...
    
    def create_task_def(
        self,
        phase_id: int,
        template_id: int,
        task_key: str,
        task_title: str,
        task_description: str | None,
        depends_on_key: str | None,
        priority: int,
        estimated_hours: float | None,
        task_order: int
    ) -> TaskDef:
        """Insert task definition, return with id assigned"""
        ...
    
    def get_task_def(self, task_def_id: int) -> TaskDef | None:
        """Get task definition by id"""
        ...
    
    def get_tasks_for_phase(
        self,
        phase_id: int
    ) -> list[TaskDef]:
        """Get all tasks for phase, sorted by task_order"""
        ...
    
    def list_templates(
        self,
        status: str | None,
        limit: int,
        offset: int
    ) -> list[Template]:
        """List templates with pagination"""
        ...
```

### 2-4. TemplateValidator

```python
# workflow/validation/template.py

class TemplateValidator:
    """Validate template structure and constraints"""
    
    def validate_phase(
        self,
        template_id: int,
        phase_key: str,
        specialist_type: str,
        phase_order: int
    ) -> None:
        """
        Validate phase addition.
        
        Raises:
            ValidationError: If phase_key already exists
            ValidationError: If specialist_type is invalid
            ValidationError: If phase_order conflicts
        """
        ...
    
    def validate_task_def(
        self,
        phase_id: int,
        task_key: str,
        depends_on_key: str | None
    ) -> None:
        """
        Validate task definition.
        
        Raises:
            ValidationError: If task_key already exists
            ValidationError: If depends_on_key references non-existent task
        """
        ...
    
    def validate_template_complete(self, template_id: int) -> None:
        """
        Validate template is ready for publishing.
        
        Raises:
            ValidationError: If no phases or tasks
            ValidationError: If any phase has no tasks
            CircularDependencyError: If circular dependency exists
        """
        ...
```

---

## 3. Instance Module

### 3-1. データモデル

```python
# workflow/models/instance.py

@dataclass
class PhaseInstance:
    """Phase instance within workflow instance"""
    id: int | None = None
    instance_id: int | None = None
    phase_id: int | None = None
    phase_key: str                             # From phase template
    status: str = 'waiting'                    # waiting, ready, running, completed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None

@dataclass
class WorkflowInstance:
    """Instance of a workflow template"""
    id: int | None = None
    template_id: int                           # Reference to template
    name: str                                  # Instance name (e.g., 'Product Launch #1')
    status: str = 'pending'                    # pending, ready, running, completed
    context: dict[str, Any] = None             # Custom context (JSON)
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

### 3-2. WorkflowInstanceService インターフェース

```python
# workflow/services/instance.py

class WorkflowInstanceService:
    """
    Workflow instance lifecycle management.
    Responsibilities:
    - Instantiate template
    - Manage phase execution
    - Track instance status
    """
    
    def __init__(
        self,
        instance_repo: InstanceRepository,
        template_repo: TemplateRepository,
        task_gen_service: TaskGenerationService,
        assignment_svc: SpecialistAssignmentService,
        validator: InstanceValidator
    ):
        self.instance_repo = instance_repo
        self.template_repo = template_repo
        self.task_gen_service = task_gen_service
        self.assignment_svc = assignment_svc
        self.validator = validator
    
    # ===== INSTANTIATE =====
    
    def instantiate_workflow(
        self,
        template_id: int,
        instance_name: str,
        specialist_assignments: dict[str, str | int],
        context: dict[str, Any] | None = None
    ) -> WorkflowInstance:
        """
        Instantiate template to workflow instance (5-step process).
        
        Steps:
        1. Validate template & assignments
        2. Create workflow_instances record
        3. Assign specialists → workflow_instance_specialists
        4. Create phase instances → wf_instance_nodes
        5. Generate tasks → dev_tasks + task_dependencies
        
        Args:
            template_id: Template to instantiate
            instance_name: Display name for instance
            specialist_assignments: {phase_key → email | agent_id}
                Example: {
                    'planning': 'alice@example.com',
                    'development': 'bob@example.com',
                    'testing': 5  # agent_id
                }
            context: Optional custom context (stored as JSON)
        
        Returns:
            Instantiated WorkflowInstance with status='ready'
        
        Raises:
            TemplateNotFoundError: If template_id invalid
            ValidationError: If template is not 'published'
            ValidationError: If assignments incomplete or invalid
            SpecialistNotFoundError: If specialist not found
            SpecialistAssignmentError: If specialist type mismatch
            CircularDependencyError: If detected during task generation
            DatabaseError: If transaction fails (full rollback)
        
        Example:
            >>> instance = svc.instantiate_workflow(
            ...     template_id=1,
            ...     instance_name='Product Launch #1',
            ...     specialist_assignments={
            ...         'planning': 'alice@example.com',
            ...         'development': 'bob@example.com',
            ...         'testing': 'carol@example.com',
            ...         'deployment': 7
            ...     }
            ... )
            >>> assert instance.status == 'ready'
            >>> assert instance.id is not None
        """
        # Step 1: Validate
        template = self.template_repo.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        if template.status != 'published':
            raise ValidationError(
                f"Cannot instantiate non-published template (status={template.status})"
            )
        
        # Validate specialist assignments
        resolved_assignments = self.assignment_svc.validate_and_resolve_assignments(
            template_id=template_id,
            assignments=specialist_assignments
        )
        
        # Step 2: Create instance
        instance = self.instance_repo.create_instance(
            template_id=template_id,
            name=instance_name,
            status='pending',
            context=context or {}
        )
        
        try:
            # Step 3: Assign specialists
            for phase in self.template_repo.get_phases(template_id):
                specialist = resolved_assignments[phase.phase_key]
                self.instance_repo.assign_specialist(
                    instance_id=instance.id,
                    phase_id=phase.id,
                    specialist_id=specialist.id,
                    specialist_slug=specialist.email,
                    specialist_name=specialist.name
                )
            
            # Step 4: Create phase instances
            for phase in self.template_repo.get_phases(template_id):
                self.instance_repo.create_phase_instance(
                    instance_id=instance.id,
                    phase_id=phase.id,
                    phase_key=phase.phase_key,
                    status='waiting'
                )
            
            # Step 5: Generate tasks
            task_count = self.task_gen_service.generate_tasks_for_instance(
                instance_id=instance.id,
                template_id=template_id
            )
            
            # Update status to ready
            instance.status = 'ready'
            self.instance_repo.update_instance(instance)
            
            return instance
            
        except Exception as e:
            # Rollback on error
            self.instance_repo.delete_instance(instance.id)
            raise
    
    # ===== PHASE EXECUTION =====
    
    def advance_phase(self, instance_id: int, phase_key: str) -> PhaseInstance:
        """
        Manually advance phase to 'ready' (if all predecessors completed).
        Usually called implicitly via task completion.
        
        Args:
            instance_id: Workflow instance
            phase_key: Phase to advance
        
        Returns:
            Updated PhaseInstance with status changed
        
        Raises:
            InstanceNotFoundError
            PhaseNotFoundError
            InvalidStateTransitionError: If predecessor phases not completed
        """
        instance = self.instance_repo.get_instance(instance_id)
        if not instance:
            raise InstanceNotFoundError(f"Instance {instance_id} not found")
        
        phase_instance = self.instance_repo.get_phase_instance(
            instance_id, phase_key
        )
        if not phase_instance:
            raise PhaseNotFoundError(f"Phase {phase_key} not found")
        
        # Check all predecessor phases completed
        template = self.template_repo.get_template(instance.template_id)
        phases = self.template_repo.get_phases(instance.template_id)
        
        target_phase = next(p for p in phases if p.phase_key == phase_key)
        predecessor_phases = [p for p in phases if p.phase_order < target_phase.phase_order]
        
        for pred_phase in predecessor_phases:
            pred_instance = self.instance_repo.get_phase_instance(
                instance_id, pred_phase.phase_key
            )
            if pred_instance.status != 'completed':
                raise InvalidStateTransitionError(
                    f"Cannot advance {phase_key}: predecessor {pred_phase.phase_key} not completed"
                )
        
        # Advance to ready
        phase_instance.status = 'ready'
        self.instance_repo.update_phase_instance(phase_instance)
        
        return phase_instance
    
    # ===== QUERY =====
    
    def get_instance(self, instance_id: int) -> WorkflowInstance:
        """Get instance with basic info"""
        instance = self.instance_repo.get_instance(instance_id)
        if not instance:
            raise InstanceNotFoundError(f"Instance {instance_id} not found")
        return instance
    
    def get_instance_status(
        self,
        instance_id: int
    ) -> dict[str, Any]:
        """
        Get detailed status including phases and tasks.
        
        Returns:
            {
                'instance': WorkflowInstance,
                'phases': [PhaseInstance, ...],
                'tasks': [DevTask, ...],
                'progress': {'total': 14, 'completed': 3, 'pct': 21}
            }
        """
        instance = self.get_instance(instance_id)
        phases = self.instance_repo.get_phase_instances(instance_id)
        tasks = self.instance_repo.get_instance_tasks(instance_id)
        
        completed = sum(1 for t in tasks if t.status == 'completed')
        total = len(tasks)
        pct = int(100 * completed / total) if total > 0 else 0
        
        return {
            'instance': instance,
            'phases': phases,
            'tasks': tasks,
            'progress': {
                'total': total,
                'completed': completed,
                'pct': pct
            }
        }
    
    def list_instances(
        self,
        template_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[WorkflowInstance]:
        """List instances with optional filtering"""
        return self.instance_repo.list_instances(
            template_id=template_id,
            status=status,
            limit=limit,
            offset=offset
        )
```

### 3-3. InstanceRepository

```python
# workflow/repositories/instance.py

class InstanceRepository:
    """Data access for instance layer"""
    
    def create_instance(
        self,
        template_id: int,
        name: str,
        status: str,
        context: dict[str, Any]
    ) -> WorkflowInstance:
        """Insert workflow_instances, return with id"""
        ...
    
    def get_instance(self, instance_id: int) -> WorkflowInstance | None:
        """Get instance"""
        ...
    
    def update_instance(self, instance: WorkflowInstance) -> None:
        """Update instance (mainly status)"""
        ...
    
    def delete_instance(self, instance_id: int) -> None:
        """Delete instance and all related data (cascade)"""
        ...
    
    def assign_specialist(
        self,
        instance_id: int,
        phase_id: int,
        specialist_id: int,
        specialist_slug: str,
        specialist_name: str
    ) -> None:
        """Insert workflow_instance_specialists"""
        ...
    
    def create_phase_instance(
        self,
        instance_id: int,
        phase_id: int,
        phase_key: str,
        status: str
    ) -> PhaseInstance:
        """Insert wf_instance_nodes for phase, return with id"""
        ...
    
    def get_phase_instance(
        self,
        instance_id: int,
        phase_key: str
    ) -> PhaseInstance | None:
        """Get phase instance by phase_key"""
        ...
    
    def get_phase_instances(
        self,
        instance_id: int
    ) -> list[PhaseInstance]:
        """Get all phases for instance, sorted by phase_order"""
        ...
    
    def update_phase_instance(self, phase: PhaseInstance) -> None:
        """Update phase instance"""
        ...
    
    def get_instance_tasks(
        self,
        instance_id: int
    ) -> list[DevTask]:
        """Get all tasks for instance"""
        ...
    
    def list_instances(
        self,
        template_id: int | None,
        status: str | None,
        limit: int,
        offset: int
    ) -> list[WorkflowInstance]:
        """List instances with pagination"""
        ...
```

---

## 4. Task-Gen Module

### 4-1. データモデル

```python
# workflow/models/task.py

@dataclass
class TaskDependency:
    """Dependency edge in task DAG"""
    id: int | None = None
    predecessor_id: int                        # dev_tasks.id
    successor_id: int                          # dev_tasks.id
    dep_type: str                              # 'inter_phase' | 'intra_phase'
    created_at: datetime | None = None

@dataclass
class DevTask:
    """Development task (extended)"""
    id: int | None = None
    title: str
    description: str | None = None
    assignee: str                              # specialist_slug (email)
    phase: str                                 # phase_key from template
    workflow_instance_id: int                  # Instance reference
    wf_node_key: str | None = None             # Phase key (for phase grouping)
    status: str = 'blocked'                    # blocked, pending, in_progress, completed
    priority: int = 1
    estimated_hours: float | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    unblocked_at: datetime | None = None
```

### 4-2. TaskGenerationService インターフェース

```python
# workflow/services/task_gen.py

class TaskGenerationService:
    """
    Auto-generate tasks from template.
    Responsibilities:
    - Generate tasks for all phases
    - Apply placeholders
    - Create inter-phase dependencies
    - Create intra-phase dependencies
    - Ensure idempotency
    """
    
    def __init__(
        self,
        task_repo: TaskRepository,
        template_repo: TemplateRepository,
        instance_repo: InstanceRepository,
        graph_repo: GraphRepository,
        validator: TaskGenValidator
    ):
        self.task_repo = task_repo
        self.template_repo = template_repo
        self.instance_repo = instance_repo
        self.graph_repo = graph_repo
        self.validator = validator
    
    # ===== MAIN GENERATION =====
    
    def generate_tasks_for_instance(
        self,
        instance_id: int,
        template_id: int
    ) -> int:
        """
        Generate all tasks for instance from template.
        
        Algorithm:
        1. Check idempotency (no existing tasks)
        2. Get phases sorted by phase_order
        3. For each phase:
           a. Get task definitions
           b. Get assigned specialist
           c. Create tasks with placeholders resolved
           d. Create intra-phase dependencies
        4. Create inter-phase dependencies
        5. Validate dependency DAG (no cycles)
        
        Args:
            instance_id: Target workflow instance
            template_id: Source template
        
        Returns:
            Total number of tasks generated
        
        Raises:
            InstanceNotFoundError
            TemplateNotFoundError
            ValidationError: If tasks already generated
            CircularDependencyError: If DAG validation fails
            DatabaseError: If insertion fails
        
        Example:
            >>> count = svc.generate_tasks_for_instance(
            ...     instance_id=42,
            ...     template_id=1
            ... )
            >>> print(f"Generated {count} tasks")
            Generated 14 tasks
        """
        # Check idempotency
        existing = self.task_repo.count_instance_tasks(instance_id)
        if existing > 0:
            logger.info(f"Tasks already generated for instance {instance_id}")
            return existing
        
        instance = self.instance_repo.get_instance(instance_id)
        if not instance:
            raise InstanceNotFoundError(f"Instance {instance_id} not found")
        
        # Get template
        template = self.template_repo.get_template(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        # Get phases sorted
        phases = self.template_repo.get_phases(template_id)
        
        total_generated = 0
        phase_task_map = {}  # phase_key → [task_id, ...]
        
        try:
            # For each phase
            for phase in phases:
                # Get specialist assigned to this phase
                specialist = self.instance_repo.get_phase_specialist(
                    instance_id, phase.id
                )
                
                # Get task definitions for this phase
                task_defs = self.template_repo.get_tasks_for_phase(phase.id)
                
                # Generate tasks
                phase_tasks = []
                for task_def in task_defs:
                    task = self._create_task_from_def(
                        instance_id=instance_id,
                        phase_key=phase.phase_key,
                        task_def=task_def,
                        specialist=specialist,
                        phase_label=phase.phase_label,
                        workflow_name=instance.name
                    )
                    phase_tasks.append(task)
                    total_generated += 1
                
                phase_task_map[phase.phase_key] = phase_tasks
                
                # Create intra-phase dependencies
                self._create_intra_phase_dependencies(
                    phase=phase,
                    task_defs=task_defs,
                    phase_tasks=phase_tasks
                )
            
            # Create inter-phase dependencies
            self._create_inter_phase_dependencies(
                phases=phases,
                phase_task_map=phase_task_map
            )
            
            # Validate DAG
            self.validator.validate_no_cycles(instance_id)
            
            return total_generated
            
        except Exception as e:
            # Cleanup on error
            self.task_repo.delete_instance_tasks(instance_id)
            raise
    
    # ===== TASK CREATION =====
    
    def _create_task_from_def(
        self,
        instance_id: int,
        phase_key: str,
        task_def: TaskDef,
        specialist: Agent,
        phase_label: str,
        workflow_name: str
    ) -> DevTask:
        """
        Create single task with placeholders resolved.
        
        Placeholders:
        - {phase_label}: Phase display name
        - {phase_key}: Phase key
        - {specialist_name}: Assigned specialist name
        - {specialist_email}: Specialist email
        - {workflow_name}: Instance name
        - {current_date}: ISO format date
        """
        # Resolve placeholders
        context = {
            'phase_label': phase_label,
            'phase_key': phase_key,
            'specialist_name': specialist.name,
            'specialist_email': specialist.email,
            'workflow_name': workflow_name,
            'current_date': datetime.now().isoformat()
        }
        
        resolved_title = self._apply_placeholders(
            task_def.task_title,
            context
        )
        resolved_description = self._apply_placeholders(
            task_def.task_description or '',
            context
        )
        
        # Create task (initial status: blocked)
        task = self.task_repo.create_task(
            title=resolved_title,
            description=resolved_description,
            assignee=specialist.email,
            phase=phase_key,
            workflow_instance_id=instance_id,
            wf_node_key=phase_key,
            status='blocked',  # Blocked until phase is ready
            priority=task_def.priority,
            estimated_hours=task_def.estimated_hours
        )
        
        return task
    
    def _apply_placeholders(
        self,
        template_text: str,
        context: dict[str, str]
    ) -> str:
        """
        Replace {placeholders} in text.
        
        Args:
            template_text: Text with {placeholders}
            context: {placeholder_name → value}
        
        Returns:
            Text with placeholders replaced
        
        Note:
        - Missing placeholders are logged as warning
        - Unresolved placeholders remain in text
        """
        result = template_text
        
        for placeholder, value in context.items():
            result = result.replace(f'{{{placeholder}}}', str(value))
        
        # Warn about unresolved
        import re
        unresolved = re.findall(r'\{[^}]+\}', result)
        if unresolved:
            logger.warning(f"Unresolved placeholders in task: {unresolved}")
        
        return result
    
    # ===== DEPENDENCIES =====
    
    def _create_intra_phase_dependencies(
        self,
        phase: Phase,
        task_defs: list[TaskDef],
        phase_tasks: list[DevTask]
    ) -> None:
        """
        Create task dependencies within same phase.
        
        Algorithm:
        1. For each task with depends_on_key
        2. Find referenced predecessor task_def
        3. Map to corresponding phase_task
        4. Insert dependency edge
        """
        for task_def in task_defs:
            if not task_def.depends_on_key:
                continue
            
            # Find predecessor task_def
            pred_def = next(
                (td for td in task_defs if td.task_key == task_def.depends_on_key),
                None
            )
            
            if not pred_def:
                # Should be caught by validator, but log anyway
                logger.warning(
                    f"Predecessor task not found: "
                    f"phase={phase.phase_key}, depends_on={task_def.depends_on_key}"
                )
                continue
            
            # Find corresponding task objects
            task = next(t for t in phase_tasks if t.description and str(task_def.id) in t.description)
            pred_task = next(t for t in phase_tasks if t.description and str(pred_def.id) in t.description)
            
            # Create dependency
            self.task_repo.create_task_dependency(
                predecessor_id=pred_task.id,
                successor_id=task.id,
                dep_type='intra_phase'
            )
    
    def _create_inter_phase_dependencies(
        self,
        phases: list[Phase],
        phase_task_map: dict[str, list[DevTask]]
    ) -> None:
        """
        Create dependencies between phases.
        
        Rule:
        All tasks in Phase N-1 must complete before Phase N tasks unblock.
        
        Implementation:
        For each task in Phase N, create edge from all Phase N-1 tasks.
        """
        for i, phase in enumerate(phases):
            if i == 0:
                continue  # No predecessor for first phase
            
            prev_phase = phases[i - 1]
            curr_tasks = phase_task_map[phase.phase_key]
            prev_tasks = phase_task_map[prev_phase.phase_key]
            
            # All predecessors → all current tasks
            for curr_task in curr_tasks:
                for prev_task in prev_tasks:
                    self.task_repo.create_task_dependency(
                        predecessor_id=prev_task.id,
                        successor_id=curr_task.id,
                        dep_type='inter_phase'
                    )
```

### 4-3. TaskRepository

```python
# workflow/repositories/task.py

class TaskRepository:
    """Data access for task layer"""
    
    def create_task(
        self,
        title: str,
        description: str | None,
        assignee: str,
        phase: str,
        workflow_instance_id: int,
        wf_node_key: str | None,
        status: str,
        priority: int,
        estimated_hours: float | None
    ) -> DevTask:
        """Insert dev_tasks, return with id"""
        ...
    
    def count_instance_tasks(self, instance_id: int) -> int:
        """Count tasks for instance (for idempotency check)"""
        ...
    
    def delete_instance_tasks(self, instance_id: int) -> None:
        """Delete all tasks for instance (on rollback)"""
        ...
    
    def create_task_dependency(
        self,
        predecessor_id: int,
        successor_id: int,
        dep_type: str
    ) -> TaskDependency:
        """Insert task_dependencies edge"""
        ...
    
    def get_task(self, task_id: int) -> DevTask | None:
        """Get task"""
        ...
    
    def update_task(self, task: DevTask) -> None:
        """Update task status, completed_at, etc"""
        ...
    
    def get_tasks_by_phase(
        self,
        instance_id: int,
        phase_key: str
    ) -> list[DevTask]:
        """Get all tasks in phase"""
        ...
```

---

## 5. Assignment Module

### 5-1. データモデル

```python
# workflow/models/specialist.py

@dataclass
class Agent:
    """Specialist / Agent"""
    id: int | None = None
    name: str                                  # 'Alice Johnson'
    email: str                                 # 'alice@example.com'
    specialist_type: str                       # 'pm', 'engineer', 'qa', 'devops'
    created_at: datetime | None = None

@dataclass
class SpecialistAssignment:
    """Assignment of specialist to phase within instance"""
    id: int | None = None
    instance_id: int
    phase_id: int
    specialist_id: int                         # Agent.id
    specialist_slug: str                       # Agent.email
    specialist_name: str                       # Agent.name
    created_at: datetime | None = None
```

### 5-2. SpecialistAssignmentService インターフェース

```python
# workflow/services/assignment.py

class SpecialistAssignmentService:
    """
    Specialist assignment and validation.
    Responsibilities:
    - Resolve identifiers (email → Agent)
    - Validate type compatibility
    - Prevent type mismatches
    """
    
    def __init__(
        self,
        specialist_repo: SpecialistRepository,
        validator: AssignmentValidator
    ):
        self.specialist_repo = specialist_repo
        self.validator = validator
    
    # ===== ASSIGNMENT VALIDATION =====
    
    def validate_and_resolve_assignments(
        self,
        template_id: int,
        assignments: dict[str, str | int]
    ) -> dict[str, Agent]:
        """
        Validate and resolve specialist assignments.
        
        Input format:
        {
            'phase_key': 'email@example.com' | agent_id,
            ...
        }
        
        Process:
        1. Check all phases have assignment
        2. Resolve each identifier to Agent
        3. Validate type compatibility
        
        Args:
            template_id: Template (for phase list)
            assignments: {phase_key → email | agent_id}
        
        Returns:
            {phase_key → Agent object}
        
        Raises:
            ValidationError: If missing phase or invalid format
            SpecialistNotFoundError: If email/agent_id not found
            SpecialistAssignmentError: If type mismatch
        
        Example:
            >>> resolved = svc.validate_and_resolve_assignments(
            ...     template_id=1,
            ...     assignments={
            ...         'planning': 'alice@example.com',
            ...         'development': 'bob@example.com',
            ...         'testing': 5  # agent_id
            ...     }
            ... )
            >>> resolved['planning'].specialist_type
            'pm'
        """
        # Get phases from template
        phases = self.specialist_repo.get_template_phases(template_id)
        
        # Validate all phases assigned
        self.validator.validate_all_phases_assigned(phases, assignments)
        
        resolved = {}
        
        for phase in phases:
            identifier = assignments[phase.phase_key]
            
            # Resolve identifier
            agent = self._resolve_identifier(identifier)
            
            if not agent:
                raise SpecialistNotFoundError(
                    f"Specialist not found: {identifier}"
                )
            
            # Validate type (warning if mismatch, but allow)
            if agent.specialist_type != phase.specialist_type:
                logger.warning(
                    f"Type mismatch: specialist {agent.email} "
                    f"type={agent.specialist_type} "
                    f"but phase {phase.phase_key} requires {phase.specialist_type}"
                )
            
            resolved[phase.phase_key] = agent
        
        return resolved
    
    def _resolve_identifier(
        self,
        identifier: str | int
    ) -> Agent | None:
        """
        Resolve email or agent_id to Agent.
        
        Args:
            identifier: Email string or integer agent_id
        
        Returns:
            Agent object or None if not found
        """
        if isinstance(identifier, int):
            return self.specialist_repo.get_agent(identifier)
        elif isinstance(identifier, str):
            if '@' in identifier:
                return self.specialist_repo.get_agent_by_email(identifier)
            else:
                # Try as agent name
                return self.specialist_repo.get_agent_by_name(identifier)
        return None
    
    # ===== AGENT MANAGEMENT =====
    
    def create_specialist(
        self,
        name: str,
        email: str,
        specialist_type: str
    ) -> Agent:
        """
        Register new specialist/agent.
        
        Args:
            name: Display name
            email: Email address
            specialist_type: 'pm' | 'engineer' | 'qa' | 'devops'
        
        Returns:
            Agent object with assigned id
        
        Raises:
            ValidationError: If email invalid or duplicate
            ValidationError: If specialist_type invalid
        """
        # Validate
        self.validator.validate_agent(name, email, specialist_type)
        
        # Check email unique
        existing = self.specialist_repo.get_agent_by_email(email)
        if existing:
            raise ValidationError(f"Agent with email {email} already exists")
        
        # Create
        return self.specialist_repo.create_agent(
            name=name,
            email=email,
            specialist_type=specialist_type
        )
    
    def get_available_specialists(
        self,
        specialist_type: str | None = None
    ) -> list[Agent]:
        """
        Get all available specialists.
        
        Args:
            specialist_type: Filter by type
        
        Returns:
            List of Agent objects
        """
        return self.specialist_repo.get_agents(
            specialist_type=specialist_type
        )
```

### 5-3. SpecialistRepository

```python
# workflow/repositories/specialist.py

class SpecialistRepository:
    """Data access for specialist/agent layer"""
    
    def create_agent(
        self,
        name: str,
        email: str,
        specialist_type: str
    ) -> Agent:
        """Insert agents, return with id"""
        ...
    
    def get_agent(self, agent_id: int) -> Agent | None:
        """Get agent by id"""
        ...
    
    def get_agent_by_email(self, email: str) -> Agent | None:
        """Get agent by email"""
        ...
    
    def get_agent_by_name(self, name: str) -> Agent | None:
        """Get agent by name (case-insensitive)"""
        ...
    
    def get_agents(
        self,
        specialist_type: str | None = None
    ) -> list[Agent]:
        """Get all agents, optional type filter"""
        ...
    
    def get_template_phases(self, template_id: int) -> list[Phase]:
        """Get all phases for template (for assignment validation)"""
        ...
```

---

## 6. モジュール間相互作用

### 6-1. 依存関係図

```
User / CLI
  │
  ├──→ TemplateService
  │    ├→ TemplateRepository
  │    ├→ TemplateValidator
  │    └→ GraphRepository (validate cycles)
  │
  ├──→ WorkflowInstanceService ◄─── Main Orchestrator
  │    ├→ InstanceRepository
  │    ├→ TemplateRepository
  │    ├→ TaskGenerationService ◄─── Task auto-gen
  │    │  ├→ TaskRepository
  │    │  ├→ TemplateRepository
  │    │  ├→ InstanceRepository
  │    │  ├→ GraphRepository (validate cycles)
  │    │  └→ TaskGenValidator
  │    │
  │    ├→ SpecialistAssignmentService ◄─── Assignment
  │    │  ├→ SpecialistRepository
  │    │  └→ AssignmentValidator
  │    │
  │    └→ InstanceValidator
  │
  └──→ SpecialistAssignmentService
       ├→ SpecialistRepository
       └→ AssignmentValidator
```

### 6-2. コール順序（Instantiation）

```
1. WorkflowInstanceService.instantiate_workflow(...)
   └─ validates template & assignments
      │
   2. SpecialistAssignmentService.validate_and_resolve_assignments()
      ├─ resolves email/agent_id → Agent
      └─ validates types
   
   3. InstanceRepository.create_instance()
      └─ INSERT workflow_instances
   
   4. InstanceRepository.assign_specialist() × N phases
      └─ INSERT workflow_instance_specialists
   
   5. InstanceRepository.create_phase_instance() × N phases
      └─ INSERT wf_instance_nodes (status='waiting')
   
   6. TaskGenerationService.generate_tasks_for_instance()
      ├─ retrieves phases & tasks from templates
      ├─ applies placeholders
      │  └─ uses specialist info from InstanceRepository.get_phase_specialist()
      ├─ creates dev_tasks (status='blocked')
      │  └─ TaskRepository.create_task()
      ├─ creates intra-phase dependencies
      │  └─ TaskRepository.create_task_dependency() (type='intra_phase')
      ├─ creates inter-phase dependencies
      │  └─ TaskRepository.create_task_dependency() (type='inter_phase')
      └─ validates DAG
         └─ GraphRepository.check_cycles()
   
   7. InstanceRepository.update_instance(status='ready')
      └─ UPDATE workflow_instances
   
   Return: instance (status='ready')
```

---

## 7. 例外階層

### 7-1. 例外定義

```python
# workflow/exceptions.py

class WorkflowException(Exception):
    """Base exception for workflow system"""
    pass

# ===== Template Exceptions =====

class TemplateException(WorkflowException):
    """Template-related errors"""
    pass

class TemplateNotFoundError(TemplateException):
    """Template not found"""
    pass

class ValidationError(TemplateException):
    """Validation failed (template, phase, task, assignment, etc)"""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}

class CircularDependencyError(TemplateException):
    """Circular dependency detected in task graph"""
    def __init__(self, cycle_path: list[int]):
        self.cycle_path = cycle_path
        super().__init__(f"Circular dependency: {' → '.join(map(str, cycle_path))}")

# ===== Instance Exceptions =====

class InstanceException(WorkflowException):
    """Instance-related errors"""
    pass

class InstanceNotFoundError(InstanceException):
    """Workflow instance not found"""
    pass

class InvalidStateTransitionError(InstanceException):
    """Invalid state transition (e.g., running → waiting)"""
    pass

# ===== Assignment Exceptions =====

class AssignmentException(WorkflowException):
    """Assignment-related errors"""
    pass

class SpecialistNotFoundError(AssignmentException):
    """Specialist/agent not found"""
    pass

class SpecialistAssignmentError(AssignmentException):
    """Specialist assignment failed (type mismatch, not available, etc)"""
    pass

# ===== Phase Exceptions =====

class PhaseException(WorkflowException):
    """Phase-related errors"""
    pass

class PhaseNotFoundError(PhaseException):
    """Phase not found"""
    pass

# ===== Database Exceptions =====

class DatabaseError(WorkflowException):
    """Database operation failed (SQLite or KuzuDB)"""
    pass
```

### 7-2. エラー処理戦略

| エラー | 検出場所 | 対応 | ユーザー通知 |
|--------|--------|------|-------------|
| TemplateNotFoundError | Service | fail fast | error message |
| ValidationError | Validator | fail fast + cleanup | detailed message + details |
| CircularDependencyError | GraphRepository | fail + log path | error + cycle path |
| SpecialistNotFoundError | AssignmentService | fail fast | suggest available |
| SpecialistAssignmentError | AssignmentService | fail fast (warning if type) | type mismatch warning |
| DatabaseError | Repository | rollback transaction | error + retry hint |
| InvalidStateTransitionError | Service | fail + log state | error + allowed states |

---

## 8. テスト戦略（Phase 5 へ向けて）

### 8-1. ユニットテスト

```python
# tests/workflow/services/test_template_service.py

def test_create_template_valid():
    """Template creation with valid inputs"""
    ...

def test_create_template_empty_name():
    """Template creation with empty name → ValidationError"""
    ...

def test_add_phase_duplicate_key():
    """Add phase with duplicate phase_key → ValidationError"""
    ...

def test_publish_template_no_phases():
    """Publish template without phases → ValidationError"""
    ...

# tests/workflow/services/test_instance_service.py

def test_instantiate_workflow_valid():
    """Full instantiation flow with valid inputs"""
    ...

def test_instantiate_non_published():
    """Instantiate non-published template → ValidationError"""
    ...

def test_instantiate_missing_specialist():
    """Instantiate with missing specialist → ValidationError"""
    ...

# tests/workflow/services/test_task_gen_service.py

def test_generate_tasks_idempotency():
    """Second generation returns existing count"""
    ...

def test_apply_placeholders():
    """Placeholder substitution works correctly"""
    ...

def test_circular_dependency_detection():
    """Detect circular intra-phase dependency → CircularDependencyError"""
    ...

# tests/workflow/services/test_assignment_service.py

def test_resolve_email():
    """Resolve email identifier → Agent"""
    ...

def test_resolve_agent_id():
    """Resolve agent_id → Agent"""
    ...

def test_missing_phase_assignment():
    """Missing phase assignment → ValidationError"""
    ...
```

### 8-2. 統合テスト

```python
# tests/workflow/integration/test_workflow_e2e.py

def test_full_workflow_instantiation():
    """
    Full E2E: Create template → Publish → Instantiate → Check tasks
    """
    # 1. Create template
    template = svc.create_template("Product Launch")
    
    # 2. Add phases
    phase_planning = svc.add_phase(template.id, ...)
    phase_dev = svc.add_phase(template.id, ...)
    
    # 3. Add tasks
    svc.add_task_to_phase(phase_planning.id, ...)
    svc.add_task_to_phase(phase_dev.id, ...)
    
    # 4. Publish
    template = svc.publish_template(template.id)
    assert template.status == 'published'
    
    # 5. Instantiate
    instance = instance_svc.instantiate_workflow(
        template_id=template.id,
        instance_name="Product Launch #1",
        specialist_assignments={...}
    )
    assert instance.status == 'ready'
    
    # 6. Verify tasks
    status = instance_svc.get_instance_status(instance.id)
    assert status['progress']['total'] == 8  # 3 + 5
    assert status['progress']['completed'] == 0
    
    # 7. Verify dependencies
    # Phase 1 tasks should have inter-phase deps to Phase 0 tasks
```

---

## まとめ

この Phase 4 詳細設計により、以下の実装準備が整いました：

✅ **モジュール責務の明確化** - 各モジュールの入出力と依存関係を定義  
✅ **メソッドシグネチャの統一** - 一貫した入出力形式  
✅ **例外戦略** - 段階的エラー処理と rollback  
✅ **テストガイド** - ユニット・統合・E2E テストの枠組み  

**Phase 5 では、これらのインターフェース定義に基づいて実装コード（Python）を生成します。**

---

## 参考資料

- **アーキテクチャ**: `/docs/architecture-design.md`
- **処理フロー**: `/docs/flow-design.md`
- **データモデル**: `/docs/data-model.md`
- **BDD シナリオ**: `/features/workflow-template.feature`
