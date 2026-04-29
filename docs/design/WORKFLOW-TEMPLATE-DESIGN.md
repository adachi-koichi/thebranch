# ワークフローテンプレート - API・UI 設計書

**タスク ID**: #2242  
**フェーズ**: 設計フェーズ  
**作成日**: 2026-04-20  
**バージョン**: v1.0

---

## 1. API 設計（REST）

### 1-1. テンプレート管理 API

#### 1.1.1. テンプレート一覧取得

```http
GET /api/v1/workflow-templates
Content-Type: application/json
Authorization: Bearer {token}

Query Parameters:
  - status: active | draft | deprecated (optional)
  - category: product | bug-fix | feature | devops (optional)
  - organization_id: {id} (optional, multi-tenancy)
  - search: {keyword} (optional, name/description を検索)
  - limit: 50 (default), max: 200
  - offset: 0 (pagination)
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "id": 1,
        "name": "Product Launch",
        "description": "Standard product launch workflow",
        "category": "product",
        "version": 1,
        "status": "active",
        "phase_count": 4,
        "task_count": 12,
        "estimated_hours": 120,
        "created_at": "2026-04-15T10:00:00Z",
        "created_by": "pm-alice"
      },
      {
        "id": 2,
        "name": "Quick Bug Fix",
        "description": "Lightweight bug fix workflow",
        "category": "bug-fix",
        "version": 2,
        "status": "active",
        "phase_count": 3,
        "task_count": 5,
        "estimated_hours": 16,
        "created_at": "2026-04-10T14:30:00Z",
        "created_by": "em-bob"
      }
    ],
    "total": 42,
    "limit": 50,
    "offset": 0
  }
}
```

---

#### 1.1.2. テンプレート詳細取得

```http
GET /api/v1/workflow-templates/{template_id}
Content-Type: application/json
Authorization: Bearer {token}
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Product Launch",
    "description": "Standard product launch workflow",
    "category": "product",
    "version": 1,
    "status": "active",
    "estimated_hours": 120,
    "created_by": "pm-alice",
    "created_at": "2026-04-15T10:00:00Z",
    "updated_at": "2026-04-18T15:20:00Z",
    "phases": [
      {
        "id": 10,
        "phase_key": "planning",
        "phase_order": 1,
        "phase_label": "Planning Phase",
        "description": "Initial planning and scoping",
        "specialist_type": "pm",
        "specialist_count": 1,
        "is_parallel": false,
        "task_count": 3,
        "estimated_hours": 40,
        "tasks": [
          {
            "id": 101,
            "task_key": "define-scope",
            "task_title": "Define Product Scope",
            "task_description": "Work with {specialist_name} to define product scope and requirements",
            "category": "design",
            "priority": 1,
            "estimated_hours": 16,
            "depends_on_key": null,
            "acceptance_criteria": "Scope document signed off by stakeholders"
          },
          {
            "id": 102,
            "task_key": "timeline-estimation",
            "task_title": "Timeline Estimation",
            "category": "design",
            "priority": 1,
            "estimated_hours": 12,
            "depends_on_key": "define-scope"
          },
          {
            "id": 103,
            "task_key": "resource-allocation",
            "task_title": "Resource Allocation",
            "category": "design",
            "priority": 2,
            "estimated_hours": 12,
            "depends_on_key": "timeline-estimation"
          }
        ]
      },
      {
        "id": 11,
        "phase_key": "development",
        "phase_order": 2,
        "phase_label": "Development Phase",
        "specialist_type": "engineer",
        "specialist_count": 3,
        "is_parallel": false,
        "task_count": 5,
        "estimated_hours": 60,
        "tasks": [
          {
            "id": 201,
            "task_key": "architecture-design",
            "task_title": "Architecture Design",
            "category": "design",
            "priority": 1,
            "estimated_hours": 16,
            "depends_on_key": null
          },
          {
            "id": 202,
            "task_key": "backend-implementation",
            "task_title": "Backend Implementation",
            "category": "implement",
            "priority": 1,
            "estimated_hours": 24,
            "depends_on_key": "architecture-design"
          },
          {
            "id": 203,
            "task_key": "frontend-implementation",
            "task_title": "Frontend Implementation",
            "category": "implement",
            "priority": 1,
            "estimated_hours": 16,
            "depends_on_key": "architecture-design"
          },
          {
            "id": 204,
            "task_key": "integration-testing",
            "task_title": "Integration Testing",
            "category": "test",
            "priority": 1,
            "estimated_hours": 8,
            "depends_on_key": null
          },
          {
            "id": 205,
            "task_key": "documentation",
            "task_title": "API Documentation",
            "category": "documentation",
            "priority": 2,
            "estimated_hours": 8,
            "depends_on_key": "backend-implementation"
          }
        ]
      },
      {
        "id": 12,
        "phase_key": "qa",
        "phase_order": 3,
        "phase_label": "QA Phase",
        "specialist_type": "qa",
        "specialist_count": 1,
        "is_parallel": false,
        "task_count": 2,
        "estimated_hours": 16,
        "tasks": [
          {
            "id": 301,
            "task_key": "test-planning",
            "task_title": "QA Test Plan",
            "category": "test",
            "priority": 1,
            "estimated_hours": 8
          },
          {
            "id": 302,
            "task_key": "system-testing",
            "task_title": "System Testing",
            "category": "test",
            "priority": 1,
            "estimated_hours": 8,
            "depends_on_key": "test-planning"
          }
        ]
      },
      {
        "id": 13,
        "phase_key": "deployment",
        "phase_order": 4,
        "phase_label": "Deployment Phase",
        "specialist_type": "devops",
        "specialist_count": 1,
        "is_parallel": false,
        "task_count": 2,
        "estimated_hours": 8,
        "tasks": [
          {
            "id": 401,
            "task_key": "pre-deployment-checklist",
            "task_title": "Pre-Deployment Checklist",
            "category": "devops",
            "priority": 1,
            "estimated_hours": 4
          },
          {
            "id": 402,
            "task_key": "deployment-to-prod",
            "task_title": "Deploy to Production",
            "category": "devops",
            "priority": 1,
            "estimated_hours": 4,
            "depends_on_key": "pre-deployment-checklist"
          }
        ]
      }
    ]
  }
}
```

---

#### 1.1.3. テンプレート作成

```http
POST /api/v1/workflow-templates
Content-Type: application/json
Authorization: Bearer {token}

Request Body:
{
  "name": "Custom Workflow",
  "description": "Custom workflow for internal project",
  "category": "product",
  "owner_id": 5,
  "organization_id": 1,
  "phases": [
    {
      "phase_key": "planning",
      "phase_order": 1,
      "phase_label": "Planning",
      "specialist_type": "pm",
      "specialist_count": 1,
      "is_parallel": false,
      "estimated_hours": 40,
      "tasks": [
        {
          "task_key": "define-scope",
          "task_title": "Define Scope",
          "task_description": "Define project scope",
          "category": "design",
          "priority": 1,
          "estimated_hours": 16,
          "depends_on_key": null
        }
      ]
    },
    {
      "phase_key": "implementation",
      "phase_order": 2,
      "phase_label": "Implementation",
      "specialist_type": "engineer",
      "specialist_count": 2,
      "is_parallel": false,
      "estimated_hours": 80,
      "tasks": [
        {
          "task_key": "develop-feature",
          "task_title": "Develop Feature",
          "category": "implement",
          "priority": 1,
          "estimated_hours": 40
        }
      ]
    }
  ]
}
```

**レスポンス** (201 Created):

```json
{
  "success": true,
  "data": {
    "id": 100,
    "name": "Custom Workflow",
    "description": "Custom workflow for internal project",
    "category": "product",
    "version": 1,
    "status": "draft",
    "created_at": "2026-04-20T10:00:00Z",
    "created_by": "pm-alice",
    "phases": [...]
  }
}
```

---

#### 1.1.4. テンプレート編集

```http
PUT /api/v1/workflow-templates/{template_id}
Content-Type: application/json
Authorization: Bearer {token}

Request Body:
{
  "description": "Updated description",
  "phases": [...]  // フェーズ情報を追加・編集
}
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Product Launch",
    "description": "Updated description",
    ...
  }
}
```

---

#### 1.1.5. テンプレート削除

```http
DELETE /api/v1/workflow-templates/{template_id}
Authorization: Bearer {token}
```

**レスポンス** (204 No Content) または (200 OK):

```json
{
  "success": true,
  "message": "Template deleted successfully"
}
```

**制約**: status が `active` の場合は削除不可（400 Bad Request）

---

### 1-2. ワークフロー インスタンス化 API

#### 1.2.1. インスタンス作成

```http
POST /api/v1/workflow-instances
Content-Type: application/json
Authorization: Bearer {token}

Request Body:
{
  "template_id": 1,
  "name": "Product Launch - Q2 2026",
  "project_id": 50,
  "organization_id": 1,
  "specialist_assignments": {
    "planning": 2,        // phase_key -> specialist_id
    "development": 3,
    "qa": 4,
    "deployment": 5
  },
  "custom_context": {
    "product_name": "New Feature X",
    "target_launch_date": "2026-06-30",
    "budget_hours": 150
  }
}
```

**レスポンス** (201 Created):

```json
{
  "success": true,
  "data": {
    "id": 1000,
    "template_id": 1,
    "name": "Product Launch - Q2 2026",
    "status": "pending",
    "current_phase_key": "planning",
    "created_at": "2026-04-20T10:30:00Z",
    "estimated_hours": 120,
    "phases_info": [
      {
        "phase_key": "planning",
        "phase_label": "Planning Phase",
        "status": "waiting",
        "specialist_slug": "pm-alice",
        "specialist_name": "Alice (PM)",
        "task_ids": [1001, 1002, 1003]
      },
      {
        "phase_key": "development",
        "phase_label": "Development Phase",
        "status": "waiting",
        "specialist_slug": "engineer-bob",
        "specialist_name": "Bob (Engineer)",
        "task_ids": [1004, 1005, 1006, 1007, 1008]
      },
      {
        "phase_key": "qa",
        "phase_label": "QA Phase",
        "status": "waiting",
        "specialist_slug": "qa-carol",
        "specialist_name": "Carol (QA)",
        "task_ids": [1009, 1010]
      },
      {
        "phase_key": "deployment",
        "phase_label": "Deployment Phase",
        "status": "waiting",
        "specialist_slug": "devops-dave",
        "specialist_name": "Dave (DevOps)",
        "task_ids": [1011, 1012]
      }
    ]
  }
}
```

---

#### 1.2.2. インスタンス詳細取得

```http
GET /api/v1/workflow-instances/{instance_id}
Authorization: Bearer {token}
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "id": 1000,
    "template_id": 1,
    "template_name": "Product Launch",
    "name": "Product Launch - Q2 2026",
    "status": "running",
    "current_phase_key": "development",
    "current_phase_label": "Development Phase",
    "start_time": "2026-04-20T10:30:00Z",
    "estimated_hours": 120,
    "estimated_completion": "2026-05-13T10:30:00Z",
    "phases": [
      {
        "phase_key": "planning",
        "phase_label": "Planning Phase",
        "status": "completed",
        "specialist_slug": "pm-alice",
        "specialist_name": "Alice (PM)",
        "started_at": "2026-04-20T10:30:00Z",
        "completed_at": "2026-04-22T14:00:00Z",
        "task_count": 3,
        "completed_task_count": 3,
        "tasks": [
          {
            "id": 1001,
            "title": "Define Product Scope",
            "status": "completed",
            "priority": 1,
            "completed_at": "2026-04-22T10:00:00Z"
          },
          {
            "id": 1002,
            "title": "Timeline Estimation",
            "status": "completed",
            "priority": 1,
            "completed_at": "2026-04-22T12:00:00Z"
          },
          {
            "id": 1003,
            "title": "Resource Allocation",
            "status": "completed",
            "priority": 2,
            "completed_at": "2026-04-22T14:00:00Z"
          }
        ]
      },
      {
        "phase_key": "development",
        "phase_label": "Development Phase",
        "status": "running",
        "specialist_slug": "engineer-bob",
        "specialist_name": "Bob (Engineer)",
        "started_at": "2026-04-22T14:00:00Z",
        "task_count": 5,
        "completed_task_count": 2,
        "tasks": [
          {
            "id": 1004,
            "title": "Architecture Design",
            "status": "completed",
            "priority": 1,
            "completed_at": "2026-04-25T16:00:00Z"
          },
          {
            "id": 1005,
            "title": "Backend Implementation",
            "status": "in_progress",
            "priority": 1,
            "assigned_to": "engineer-bob"
          },
          {
            "id": 1006,
            "title": "Frontend Implementation",
            "status": "blocked",
            "priority": 1,
            "blocked_by": [1004]
          }
        ]
      },
      {
        "phase_key": "qa",
        "phase_label": "QA Phase",
        "status": "waiting",
        "specialist_slug": "qa-carol",
        "task_count": 2,
        "completed_task_count": 0
      },
      {
        "phase_key": "deployment",
        "phase_label": "Deployment Phase",
        "status": "waiting",
        "specialist_slug": "devops-dave",
        "task_count": 2,
        "completed_task_count": 0
      }
    ]
  }
}
```

---

#### 1.2.3. インスタンス内タスク一覧取得

```http
GET /api/v1/workflow-instances/{instance_id}/tasks
Authorization: Bearer {token}

Query Parameters:
  - phase_key: {phase_key} (optional, フェーズでフィルタ)
  - status: pending | in_progress | completed | blocked (optional)
  - assignee: {specialist_slug} (optional)
```

**レスポンス** (200 OK):

```json
{
  "success": true,
  "data": {
    "instance_id": 1000,
    "total_tasks": 12,
    "completed_tasks": 5,
    "in_progress_tasks": 2,
    "blocked_tasks": 0,
    "tasks": [
      {
        "id": 1001,
        "title": "Define Product Scope",
        "phase_key": "planning",
        "phase_label": "Planning Phase",
        "assignee": "pm-alice",
        "status": "completed",
        "priority": 1,
        "category": "design",
        "estimated_hours": 16,
        "actual_hours": 14,
        "completed_at": "2026-04-22T10:00:00Z",
        "depends_on": [],
        "blocking": [1002]
      },
      {
        "id": 1002,
        "title": "Timeline Estimation",
        "phase_key": "planning",
        "phase_label": "Planning Phase",
        "assignee": "pm-alice",
        "status": "completed",
        "priority": 1,
        "category": "design",
        "estimated_hours": 12,
        "actual_hours": 11,
        "completed_at": "2026-04-22T12:00:00Z",
        "depends_on": [1001],
        "blocking": [1003]
      }
    ]
  }
}
```

---

## 2. UI 設計（フロントエンド）

### 2-1. テンプレート一覧画面

**URL**: `/workflows/templates`

```
┌─────────────────────────────────────────────────────────────┐
│                    Workflow Templates                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  [検索: ____________________]  [フィルタ▼]  [新規テンプレート]  │
│                                                               │
│  Status: ☐ Active  ☐ Draft  ☐ Deprecated                    │
│  Category: ☐ Product  ☐ Bug-Fix  ☐ Feature  ☐ DevOps       │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Product Launch (v1.0)          [STATUS: ACTIVE]     │   │
│  │ Standard product launch workflow                     │   │
│  │ Phases: 4 | Tasks: 12 | Est. Hours: 120            │   │
│  │                                                       │   │
│  │ Created: 2026-04-15 by pm-alice                     │   │
│  │ [View Details] [Clone] [Use This Template]          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Quick Bug Fix (v2.1)           [STATUS: ACTIVE]     │   │
│  │ Lightweight bug fix workflow                        │   │
│  │ Phases: 3 | Tasks: 5 | Est. Hours: 16              │   │
│  │                                                       │   │
│  │ Created: 2026-04-10 by em-bob                       │   │
│  │ [View Details] [Clone] [Use This Template]          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  [< Previous] [1] [2] [3] [Next >]                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**操作**:
- [View Details] → テンプレート詳細画面に遷移
- [Clone] → テンプレート複製ダイアログ表示
- [Use This Template] → テンプレート選択画面に遷移（インスタンス化フロー開始）

---

### 2-2. テンプレート詳細画面

**URL**: `/workflows/templates/{template_id}`

```
┌──────────────────────────────────────────────────────────────┐
│ ◀ Back  │  Product Launch (v1.0)         [EDIT] [DELETE]     │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│ Description: Standard product launch workflow                │
│ Category: Product | Status: Active                           │
│ Owner: pm-alice | Created: 2026-04-15                        │
│ Estimated Hours: 120                                         │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│                      PHASE DIAGRAM                            │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │
│  │ Planning     │──→│ Development  │──→│ QA           │      │
│  │ Phase 1      │   │ Phase 2      │   │ Phase 3      │      │
│  │ (PM x1)      │   │ (Eng x3)     │   │ (QA x1)      │      │
│  │ 3 tasks      │   │ 5 tasks      │   │ 2 tasks      │      │
│  │ 40 hours     │   │ 60 hours     │   │ 16 hours     │      │
│  └──────────────┘   └──────────────┘   └──────────────┘      │
│                                              ↓                 │
│                                     ┌──────────────┐           │
│                                     │ Deployment   │           │
│                                     │ Phase 4      │           │
│                                     │ (DevOps x1)  │           │
│                                     │ 2 tasks      │           │
│                                     │ 8 hours      │           │
│                                     └──────────────┘           │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│                      PHASE DETAILS                            │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│ Phase 1: Planning (PM)                                       │
│ ├─ Define Product Scope (design, 16h)                        │
│ ├─ Timeline Estimation (design, 12h)                         │
│ └─ Resource Allocation (design, 12h)                         │
│                                                                │
│ Phase 2: Development (Engineer)                              │
│ ├─ Architecture Design (design, 16h)                         │
│ ├─ Backend Implementation (implement, 24h)                   │
│ ├─ Frontend Implementation (implement, 16h)                  │
│ ├─ Integration Testing (test, 8h)                            │
│ └─ API Documentation (documentation, 8h)                     │
│                                                                │
│ Phase 3: QA (QA)                                             │
│ ├─ QA Test Plan (test, 8h)                                   │
│ └─ System Testing (test, 8h)                                 │
│                                                                │
│ Phase 4: Deployment (DevOps)                                 │
│ ├─ Pre-Deployment Checklist (devops, 4h)                     │
│ └─ Deploy to Production (devops, 4h)                         │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│ [Use This Template] [Print] [Export as JSON]                 │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

---

### 2-3. インスタンス化ウィザード（テンプレート選択 → Specialist 割り当て）

#### Step 1: テンプレート選択

**URL**: `/workflows/create?template_id={template_id}`

```
┌──────────────────────────────────────────────────────┐
│        Create Workflow Instance - Step 1 of 3         │
├──────────────────────────────────────────────────────┤
│                                                       │
│  Selected Template:                                   │
│  ┌─────────────────────────────────────────────┐    │
│  │ Product Launch (v1.0)                       │    │
│  │ Standard product launch workflow            │    │
│  │ Phases: 4 | Tasks: 12 | Est. Hours: 120   │    │
│  └─────────────────────────────────────────────┘    │
│                                                       │
│  Instance Name:                                      │
│  [Product Launch - Q2 2026____________]              │
│                                                       │
│  Project:                                            │
│  [Select Project ▼]                                  │
│                                                       │
│  Custom Context (optional):                          │
│  Product Name:                                       │
│  [Feature X________________]                         │
│                                                       │
│  Target Launch Date:                                 │
│  [2026-06-30________________]                        │
│                                                       │
│  Budget Hours:                                       │
│  [150________________]                               │
│                                                       │
│                      [< Back] [Next >]               │
│                                                       │
└──────────────────────────────────────────────────────┘
```

---

#### Step 2: Specialist 割り当て

**URL**: `/workflows/create?template_id={template_id}&step=2`

```
┌──────────────────────────────────────────────────────┐
│        Create Workflow Instance - Step 2 of 3         │
├──────────────────────────────────────────────────────┤
│                                                       │
│  Assign Specialists to Each Phase:                   │
│                                                       │
│  Phase 1: Planning (PM) [1 specialist required]      │
│  ┌─────────────────────────────────────────────┐    │
│  │ Select PM:                                   │    │
│  │ [alice (PM) ▼]                               │    │
│  │                                               │    │
│  │ ✓ Available: YES | Load: 2/5 projects       │    │
│  └─────────────────────────────────────────────┘    │
│                                                       │
│  Phase 2: Development (Engineer) [3 required]        │
│  ┌─────────────────────────────────────────────┐    │
│  │ Select Engineers:                             │    │
│  │ [☑ bob (Senior)       Load: 3/5 projects]    │    │
│  │ [☑ charlie (Mid-level) Load: 2/5 projects]   │    │
│  │ [☐ diana (Junior)      Load: 1/5 projects]   │    │
│  │ [☐ eve (Senior)        Load: 4/5 projects]   │    │
│  │                                               │    │
│  │ Selected: 2 / 3 required                      │    │
│  └─────────────────────────────────────────────┘    │
│                                                       │
│  Phase 3: QA (QA) [1 specialist required]            │
│  ┌─────────────────────────────────────────────┐    │
│  │ Select QA:                                   │    │
│  │ [carol (QA Lead) ▼]                          │    │
│  │                                               │    │
│  │ ✓ Available: YES | Load: 1/5 projects       │    │
│  └─────────────────────────────────────────────┘    │
│                                                       │
│  Phase 4: Deployment (DevOps) [1 required]           │
│  ┌─────────────────────────────────────────────┐    │
│  │ Select DevOps:                                │    │
│  │ [dave (DevOps Engineer) ▼]                   │    │
│  │                                               │    │
│  │ ✓ Available: YES | Load: 2/5 projects       │    │
│  └─────────────────────────────────────────────┘    │
│                                                       │
│            [< Back] [Validate] [Next >]              │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**バリデーション**:
- すべてのフェーズにスペシャリストが割り当てられているか
- 割り当てられたスペシャリストが利用可能か
- 過度な負荷割り当てがないか

---

#### Step 3: 確認 & インスタンス化実行

**URL**: `/workflows/create?template_id={template_id}&step=3`

```
┌──────────────────────────────────────────────────────┐
│        Create Workflow Instance - Step 3 of 3         │
├──────────────────────────────────────────────────────┤
│                                                       │
│  SUMMARY:                                            │
│                                                       │
│  Instance Name: Product Launch - Q2 2026             │
│  Template: Product Launch (v1.0)                     │
│  Project: Product Team                               │
│                                                       │
│  Assignments:                                        │
│  Phase 1: Planning (PM)             → alice          │
│  Phase 2: Development (Engineer×3)  → bob, charlie   │
│  Phase 3: QA (QA)                   → carol          │
│  Phase 4: Deployment (DevOps)       → dave           │
│                                                       │
│  Phases & Tasks:                                     │
│  Phase 1: 3 tasks (40 hours)                         │
│  Phase 2: 5 tasks (60 hours)                         │
│  Phase 3: 2 tasks (16 hours)                         │
│  Phase 4: 2 tasks (8 hours)                          │
│                                                       │
│  Total Tasks: 12                                     │
│  Estimated Duration: 120 hours (~3 weeks)            │
│                                                       │
│  Custom Context:                                     │
│  - Product Name: Feature X                           │
│  - Launch Date: 2026-06-30                           │
│  - Budget: 150 hours                                 │
│                                                       │
│  ┌─────────────────────────────────────────────┐    │
│  │ ☑ I have reviewed the workflow. Create it.  │    │
│  └─────────────────────────────────────────────┘    │
│                                                       │
│            [< Back] [Create Workflow]                │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**アクション**:
- [Create Workflow] をクリック → インスタンス作成 API 呼び出し
- 成功 → インスタンス詳細画面にリダイレクト

---

### 2-4. インスタンス進行状況画面

**URL**: `/workflows/instances/{instance_id}`

```
┌──────────────────────────────────────────────────────────────┐
│ ◀ Back  │  Product Launch - Q2 2026              [ACTIONS ▼] │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│ Status: RUNNING | Started: 2026-04-20 10:30 | Est. End: 2026-05-13
│ Progress: 42% (5/12 tasks completed)                         │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│                      PHASE PROGRESS                           │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│ ✓ Phase 1: Planning (100% - 3/3 tasks)                       │
│   └─ pm-alice (Completed 2026-04-22)                         │
│      • Define Product Scope (16h actual: 14h) ✓              │
│      • Timeline Estimation (12h actual: 11h) ✓               │
│      • Resource Allocation (12h actual: 12h) ✓               │
│                                                                │
│ ⊙ Phase 2: Development (40% - 2/5 tasks)                     │
│   └─ engineer-bob (In Progress since 2026-04-22)             │
│      • Architecture Design (16h actual: 16h) ✓               │
│      • Backend Implementation (24h) ⊙ IN PROGRESS            │
│      • Frontend Implementation (16h) ⊗ BLOCKED               │
│      • Integration Testing (8h) ◯ PENDING                    │
│      • API Documentation (8h) ◯ PENDING                      │
│                                                                │
│ ◯ Phase 3: QA (0% - 0/2 tasks)                               │
│   └─ qa-carol (Waiting for Phase 2)                          │
│      • QA Test Plan (8h) ◯ PENDING                           │
│      • System Testing (8h) ◯ PENDING                         │
│                                                                │
│ ◯ Phase 4: Deployment (0% - 0/2 tasks)                       │
│   └─ devops-dave (Waiting for Phase 3)                       │
│      • Pre-Deployment Checklist (4h) ◯ PENDING               │
│      • Deploy to Production (4h) ◯ PENDING                   │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│                      TASK DETAILS                             │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│ Filter by Phase: [All ▼]  Filter by Status: [All ▼]         │
│                                                                │
│ ┌─ 1001: Define Product Scope                          ✓ ──┐ │
│ │  Phase: Planning | Assignee: pm-alice               │     │ │
│ │  Est: 16h | Actual: 14h | Completed: 2026-04-22    │     │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌─ 1005: Backend Implementation                        ⊙ ──┐ │
│ │  Phase: Development | Assignee: engineer-bob         │     │ │
│ │  Est: 24h | Progress: 60% | Started: 2026-04-25     │     │ │
│ │  [View Details] [Add Comment]                        │     │ │
│ └───────────────────────────────────────────────────────────┘ │
│                                                                │
│ [< Previous] [Page 1 of 2] [Next >]                          │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. コンポーネント設計

### 3-1. テンプレート選択コンポーネント

```javascript
<TemplateSelector
  onSelectTemplate={(template) => handleSelectTemplate(template)}
  onFilterChange={(filters) => handleFilterChange(filters)}
  filters={{status: 'active', category: 'product'}}
/>
```

### 3-2. Specialist 割り当てコンポーネント

```javascript
<SpecialistAssignment
  phases={phases}
  availableAgents={agents}
  onAssign={(phaseKey, specialistId) => handleAssign(phaseKey, specialistId)}
  onValidate={() => validateAssignments()}
/>
```

### 3-3. フェーズプログレスコンポーネント

```javascript
<PhaseProgress
  phases={instancePhases}
  tasks={tasksWithStatus}
  onPhaseClick={(phaseKey) => showPhaseDetails(phaseKey)}
/>
```

---

## 4. エラーハンドリング & バリデーション

### 4-1. API エラー レスポンス

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Specialist assignment validation failed",
    "details": [
      {
        "phase_key": "development",
        "message": "Phase requires 3 specialists, but only 2 assigned"
      },
      {
        "phase_key": "deployment",
        "message": "Specialist 'dave' is not available (Load: 5/5)"
      }
    ]
  }
}
```

### 4-2. バリデーション ルール

| チェック項目 | エラーメッセージ |
|---|---|
| テンプレート不在 | "Template not found" |
| フェーズ割り当て不足 | "Phase {phase_key} requires {count} specialists" |
| スペシャリスト存在確認 | "Specialist {id} does not exist" |
| 負荷上限超過 | "Specialist {name} load exceeds limit ({current}/{max})" |
| 権限不足 | "You don't have permission to create workflow instance" |

---

## 5. ページ遷移フロー

```
/workflows/templates
    ↓ [View Details]
/workflows/templates/{id}
    ↓ [Use This Template]
/workflows/create?template_id={id}
    ↓ [Step 1: Template Selection]
/workflows/create?template_id={id}&step=2
    ↓ [Step 2: Specialist Assignment]
/workflows/create?template_id={id}&step=3
    ↓ [Step 3: Confirmation]
/workflows/create (POST) → API Call
    ↓
/workflows/instances/{instance_id}
    ↓ [View Task Details / Monitor Progress]
/workflows/instances/{instance_id}/tasks/{task_id}
```

---

## 参考資料

- [データモデル設計](design/WORKFLOW-TEMPLATE-MODEL.md)
- [要件ドキュメント](docs/WORKFLOW-TEMPLATE-README.md)
- [BDD テスト仕様](features/workflow-template.feature)

---

*このドキュメントは タスク #2242 の設計フェーズにおける API・UI 仕様です。*
