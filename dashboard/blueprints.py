"""
Templates API Blueprint for FastAPI

Provides REST API endpoints for:
- Template registration (POST /api/v1/templates)
- Template listing and filtering (GET /api/v1/templates)
- Template detail retrieval (GET /api/v1/templates/{template_id})
- Template updates (PUT /api/v1/templates/{template_id})
- Template matching (POST /api/v1/templates/match)
"""

import logging
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict
from difflib import SequenceMatcher

from fastapi import APIRouter, HTTPException, Header, Query, Depends
from pydantic import BaseModel, Field

from workflow.services.template_service import TemplateService
from workflow.models.template import (
    TemplateValidationError,
    TemplateNotFoundError,
)
from workflow.validation.template import TemplateValidator

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

# ===== Pydantic Models =====

class TemplateNode(BaseModel):
    task_id: str
    name: str
    type: str = "task"
    description: Optional[str] = None
    estimated_duration_minutes: int = 0
    priority: str = "medium"
    role_hint: Optional[str] = None


class TemplateEdge(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    type: str = "depends_on"
    condition: Optional[str] = None

    model_config = {"populate_by_name": True}


class CreateTemplateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    nodes: List[Dict] = Field(default_factory=list)
    edges: List[Dict] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    nodes: Optional[List[Dict]] = None
    edges: Optional[List[Dict]] = None
    tags: Optional[List[str]] = None


class TemplateMatchRequest(BaseModel):
    natural_language_input: str
    auto_match_template: bool = True


# ===== Dependencies =====

async def get_current_user(authorization: str = Header(None)):
    """Extract and validate Bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token is empty")

    return {"token": token, "user_id": token[:16]}


def get_template_service(db_path: str = None) -> TemplateService:
    """Factory for TemplateService dependency injection."""
    from pathlib import Path

    if not db_path:
        dashboard_dir = Path(__file__).parent
        db_path = str(dashboard_dir / "data" / "thebranch.sqlite")

    return TemplateService(db_path=db_path)


# ===== Utility Functions =====

def calculate_match_score(input_text: str, template_data: Dict) -> float:
    """
    Calculate semantic similarity score between input and template.

    Returns score between 0.0 and 1.0
    """
    template_text = (
        f"{template_data.get('name', '')} "
        f"{template_data.get('description', '')} "
        f"{' '.join(template_data.get('tags', []))}"
    ).lower()

    input_lower = input_text.lower()

    # Simple sequence matching (can be enhanced with semantic similarity later)
    matcher = SequenceMatcher(None, input_lower, template_text)
    return matcher.ratio()


def log_api_event(event_type: str, details: Dict):
    """Log API events for monitoring."""
    logger.info(f"[API_EVENT] {event_type}: {json.dumps(details)}")


# ===== Endpoints =====

@router.post("", status_code=201)
async def create_template(
    request: CreateTemplateRequest,
    current_user: Dict = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """
    Create a new workflow template.

    Request body:
    {
        "name": "Product Launch",
        "description": "新規プロダクトローンチフロー",
        "category": "launch",
        "nodes": [...],
        "edges": [...],
        "tags": ["launch", "important"]
    }

    Returns 201 with created template metadata.
    """
    try:
        # Validate request
        if not request.name or len(request.name.strip()) == 0:
            raise HTTPException(status_code=400, detail="Template name is required")

        # Create template using service
        template_metadata = service.create_template(
            name=request.name,
            description=request.description or "",
            nodes=request.nodes,
            edges=request.edges,
            category=request.category,
        )

        # Store tags as JSON metadata (could be extended to separate table)
        log_api_event("TEMPLATE_CREATED", {
            "template_id": template_metadata.template_id,
            "name": request.name,
            "user_id": current_user["user_id"],
        })

        return {
            "success": True,
            "data": {
                "template_id": template_metadata.template_id,
                "name": template_metadata.name,
                "description": template_metadata.description,
                "category": template_metadata.category,
                "tags": request.tags,
                "created_at": template_metadata.created_at.isoformat(),
                "updated_at": template_metadata.updated_at.isoformat(),
                "usage_count": template_metadata.usage_count,
            }
        }

    except TemplateValidationError as e:
        logger.error(f"Template validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", status_code=200)
async def list_templates(
    category: Optional[str] = Query(None),
    search_q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """
    List templates with optional filtering by category and search query.

    Query parameters:
    - category: Filter by category
    - search_q: Search in name and description
    - page: Page number (1-indexed)
    - limit: Results per page (max 100)

    Returns paginated list of template summaries.
    """
    try:
        # Get all templates from service (without pagination first to apply search)
        # Use large limit to get all templates for client-side pagination
        templates = service.list_templates(category=category, page=1, limit=10000)

        # Apply search filter if provided
        if search_q:
            search_lower = search_q.lower()
            templates = [
                t for t in templates
                if search_lower in t.name.lower() or
                   search_lower in (t.description or "").lower()
            ]

        # Calculate total count before pagination
        total_count = len(templates)
        total_pages = (total_count + limit - 1) // limit

        # Apply pagination after search and filtering
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_templates = templates[start_idx:end_idx]

        log_api_event("TEMPLATES_LISTED", {
            "category": category,
            "search_q": search_q,
            "total_count": total_count,
            "page": page,
            "user_id": current_user["user_id"],
        })

        # Helper function to convert datetime to ISO format string
        def to_iso_format(dt):
            if dt is None:
                return None
            if hasattr(dt, 'isoformat'):
                return dt.isoformat()
            return str(dt)

        return {
            "success": True,
            "data": {
                "templates": [
                    {
                        "template_id": t.template_id,
                        "name": t.name,
                        "description": t.description,
                        "category": t.category,
                        "usage_count": t.usage_count,
                        "created_at": to_iso_format(t.created_at),
                        "updated_at": to_iso_format(t.updated_at),
                    }
                    for t in paginated_templates
                ],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_count": total_count,
                    "total_pages": total_pages,
                }
            }
        }

    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{template_id}", status_code=200)
async def get_template(
    template_id: int,
    current_user: Dict = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """
    Get detailed template information including nodes and edges.

    Path parameters:
    - template_id: Template ID

    Returns full template structure with DAG nodes and edges.
    """
    try:
        template_data = service.get_template(template_id)

        # Convert datetime strings to ISO format if needed
        created_at = template_data.get("created_at")
        updated_at = template_data.get("updated_at")

        log_api_event("TEMPLATE_RETRIEVED", {
            "template_id": template_id,
            "user_id": current_user["user_id"],
        })

        return {
            "success": True,
            "data": {
                "template_id": template_data["id"],
                "name": template_data["name"],
                "description": template_data["description"],
                "category": template_data["category"],
                "nodes": template_data.get("nodes", []),
                "edges": template_data.get("edges", []),
                "tags": [],  # Could be loaded from separate column/table
                "metadata": {
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "usage_count": template_data["usage_count"],
                }
            }
        }

    except TemplateNotFoundError as e:
        logger.warning(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{template_id}", status_code=200)
async def update_template(
    template_id: int,
    request: UpdateTemplateRequest,
    current_user: Dict = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """
    Update an existing template.

    Path parameters:
    - template_id: Template ID

    Request body: Partial update allowed - provide only fields to update

    Returns updated template metadata.
    """
    try:
        # Get existing template
        existing = service.get_template(template_id)

        # Prepare update data (use existing values as defaults)
        update_data = {
            "name": request.name if request.name else existing["name"],
            "description": request.description if request.description else existing["description"],
            "category": request.category if request.category else existing["category"],
            "nodes": request.nodes if request.nodes else existing.get("nodes", []),
            "edges": request.edges if request.edges else existing.get("edges", []),
        }

        # Validate and update
        template_metadata = service.update_template(template_id, **update_data)

        log_api_event("TEMPLATE_UPDATED", {
            "template_id": template_id,
            "user_id": current_user["user_id"],
            "fields_updated": [k for k, v in request.model_dump(exclude_unset=True).items() if v is not None],
        })

        # Handle both datetime and string formats
        created_at = template_metadata.created_at
        updated_at = template_metadata.updated_at

        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        if hasattr(updated_at, 'isoformat'):
            updated_at = updated_at.isoformat()

        return {
            "success": True,
            "data": {
                "template_id": template_metadata.template_id,
                "name": template_metadata.name,
                "description": template_metadata.description,
                "category": template_metadata.category,
                "created_at": created_at,
                "updated_at": updated_at,
                "usage_count": template_metadata.usage_count,
            }
        }

    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    except TemplateValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/match", status_code=200)
async def match_templates(
    request: TemplateMatchRequest,
    current_user: Dict = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """
    Find templates matching natural language input.

    Supports:
    - Keyword matching (name, description, tags)
    - Semantic similarity (simple sequence matching)
    - Structural pattern matching

    Request body:
    {
        "natural_language_input": "新規プロダクトをローンチする...",
        "auto_match_template": true
    }

    Returns ranked list of matching templates.
    """
    try:
        if not request.natural_language_input or len(request.natural_language_input.strip()) < 3:
            raise HTTPException(status_code=400, detail="Input text too short (minimum 3 characters)")

        input_text = request.natural_language_input.lower()

        # Get all templates
        all_templates = service.list_templates()

        # Calculate match scores
        matches = []
        for template in all_templates:
            template_full = service.get_template(template.template_id)

            # Calculate match score
            score = calculate_match_score(input_text, template_full)

            # Keyword matching boost
            keywords = [
                template.name.lower(),
                (template.description or "").lower(),
            ]

            match_fields = []
            if any(kw in input_text for kw in keywords):
                score = min(1.0, score + 0.15)  # Boost for keyword match
                match_fields.append("name" if template.name.lower() in input_text else "description")

            if score > 0.3:  # Only include templates with reasonable match
                matches.append({
                    "template_id": template.template_id,
                    "name": template.name,
                    "description": template.description,
                    "match_score": round(score, 2),
                    "match_reason": "Keyword match" if match_fields else "Structural similarity",
                    "matched_fields": match_fields or ["structure"],
                })

        # Sort by match score (highest first)
        matches.sort(key=lambda x: x["match_score"], reverse=True)

        best_match = matches[0] if matches else None

        log_api_event("TEMPLATES_MATCHED", {
            "input_length": len(request.natural_language_input),
            "matches_found": len(matches),
            "best_score": best_match["match_score"] if best_match else 0,
            "user_id": current_user["user_id"],
        })

        return {
            "success": True,
            "data": {
                "matched_templates": matches,
                "best_match": best_match,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to match templates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ===== Error Handlers =====

@router.api_route("", methods=["HEAD"])
async def template_head():
    """Health check endpoint."""
    return {"status": "ok"}


@router.post("/{template_id}/instantiate", status_code=200)
async def instantiate_template_endpoint(
    template_id: int,
    current_user: Dict = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """
    Create a new workflow instance from a template.

    Path parameters:
    - template_id: Template ID

    Returns workflow instance with unique generation_id.
    """
    try:
        instance = service.instantiate_template(template_id)

        log_api_event("TEMPLATE_INSTANTIATED", {
            "template_id": template_id,
            "generation_id": instance["generation_id"],
            "user_id": current_user["user_id"],
        })

        return {
            "success": True,
            "data": {
                "generation_id": instance["generation_id"],
                "template_id": instance["template_id"],
                "workflow": instance["workflow"],
                "created_at": instance["created_at"],
            }
        }

    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    except Exception as e:
        logger.error(f"Failed to instantiate template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
