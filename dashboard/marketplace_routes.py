import json
import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, HTTPException, Header, Query, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

DASHBOARD_DIR = Path(__file__).parent
DB_PATH = DASHBOARD_DIR / "data" / "thebranch.sqlite"

# ──────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────

class AgentCategory(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    display_order: int = 0

class AgentDetail(BaseModel):
    id: str
    name: str
    description: str
    detailed_description: Optional[str] = None
    category_id: str
    publisher_id: str
    version: str
    icon_url: Optional[str] = None
    banner_url: Optional[str] = None
    capabilities: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    installation_count: int = 0
    rating: float = 0.0
    review_count: int = 0
    status: str
    visibility: str
    documentation_url: Optional[str] = None
    github_url: Optional[str] = None
    support_url: Optional[str] = None
    created_at: str
    updated_at: str
    published_at: Optional[str] = None

class AgentListItem(BaseModel):
    id: str
    name: str
    description: str
    category_id: str
    icon_url: Optional[str] = None
    installation_count: int = 0
    rating: float = 0.0
    review_count: int = 0
    version: str

class InstallAgentRequest(BaseModel):
    organization_id: Optional[str] = None
    configuration: Optional[dict] = None

class InstallAgentResponse(BaseModel):
    id: str
    agent_id: str
    user_id: str
    status: str
    installed_at: str

class SearchResponse(BaseModel):
    total: int
    page: int
    per_page: int
    items: List[AgentListItem]
    filters: Optional[dict] = None

# ──────────────────────────────────────────────
# Database Helper Functions
# ──────────────────────────────────────────────

async def get_db():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        yield db

def parse_json_field(value: Optional[str], default=None):
    if not value:
        return default or []
    try:
        return json.loads(value)
    except:
        return default or []

# ──────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────

@router.get("/agents", response_model=SearchResponse)
async def list_agents(
    q: Optional[str] = Query(None, description="検索クエリ"),
    category: Optional[str] = Query(None, description="カテゴリID"),
    sort_by: str = Query("installation_count", description="ソート対象: installation_count, rating, created_at, name"),
    sort_order: str = Query("desc", description="ソート順序: asc, desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_db)
) -> SearchResponse:
    """
    エージェント一覧を取得（検索・フィルター・ソート・ページネーション対応）
    """
    # ページング計算
    offset = (page - 1) * per_page

    # クエリの安全性確認
    valid_sort_fields = ["installation_count", "rating", "created_at", "name"]
    if sort_by not in valid_sort_fields:
        sort_by = "installation_count"

    valid_sort_orders = ["asc", "desc"]
    if sort_order not in valid_sort_orders:
        sort_order = "desc"

    # WHERE 句の構築
    where_conditions = [
        "status = 'published'",
        "visibility IN ('public', 'team')"
    ]
    params = []

    if category:
        where_conditions.append("category_id = ?")
        params.append(category)

    where_clause = " AND ".join(where_conditions)

    # 検索クエリが指定されている場合は LIKE 検索を使用
    if q:
        search_term = f"%{q}%"
        where_conditions.append(
            "(name LIKE ? OR description LIKE ? OR detailed_description LIKE ? OR tags LIKE ? OR capabilities LIKE ?)"
        )
        params.extend([search_term, search_term, search_term, search_term, search_term])
        where_clause = " AND ".join(where_conditions)

    # 総数を取得
    count_query = f"SELECT COUNT(*) as cnt FROM marketplace_agents WHERE {where_clause}"
    async with db.execute(count_query, params) as cursor:
        row = await cursor.fetchone()
        total = row[0] if row else 0

    # ページング込みでエージェント一覧を取得
    query = f"""
        SELECT
            id, name, description, category_id, icon_url,
            installation_count, rating, review_count, version
        FROM marketplace_agents
        WHERE {where_clause}
        ORDER BY {sort_by} {sort_order.upper()}
        LIMIT ? OFFSET ?
    """
    params.extend([per_page, offset])

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()

    items = [
        AgentListItem(
            id=row[0],
            name=row[1],
            description=row[2],
            category_id=row[3],
            icon_url=row[4],
            installation_count=row[5],
            rating=row[6],
            review_count=row[7],
            version=row[8]
        )
        for row in rows
    ]

    return SearchResponse(
        total=total,
        page=page,
        per_page=per_page,
        items=items,
        filters={"q": q, "category": category, "sort_by": sort_by, "sort_order": sort_order}
    )

@router.get("/agents/{agent_id}", response_model=AgentDetail)
async def get_agent_detail(
    agent_id: str,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_db)
) -> AgentDetail:
    """
    エージェント詳細情報を取得
    """
    query = """
        SELECT
            id, name, description, detailed_description, category_id, publisher_id,
            version, icon_url, banner_url, capabilities, tags,
            installation_count, rating, review_count, status, visibility,
            documentation_url, github_url, support_url,
            created_at, updated_at, published_at
        FROM marketplace_agents
        WHERE id = ? AND status = 'published'
    """

    async with db.execute(query, [agent_id]) as cursor:
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentDetail(
        id=row[0],
        name=row[1],
        description=row[2],
        detailed_description=row[3],
        category_id=row[4],
        publisher_id=row[5],
        version=row[6],
        icon_url=row[7],
        banner_url=row[8],
        capabilities=parse_json_field(row[9]),
        tags=parse_json_field(row[10]),
        installation_count=row[11],
        rating=row[12],
        review_count=row[13],
        status=row[14],
        visibility=row[15],
        documentation_url=row[16],
        github_url=row[17],
        support_url=row[18],
        created_at=row[19],
        updated_at=row[20],
        published_at=row[21]
    )

@router.post("/agents/{agent_id}/install", response_model=InstallAgentResponse)
async def install_agent(
    agent_id: str,
    request: InstallAgentRequest,
    authorization: Optional[str] = Header(None),
    db: aiosqlite.Connection = Depends(get_db)
) -> InstallAgentResponse:
    """
    エージェントをインストール
    """
    # TODO: ユーザー認証は別途実装（現在はスキップ）
    user_id = "user-001"  # 実装時に認証から取得

    # エージェントの存在確認
    agent_query = "SELECT version FROM marketplace_agents WHERE id = ? AND status = 'published'"
    async with db.execute(agent_query, [agent_id]) as cursor:
        agent_row = await cursor.fetchone()

    if not agent_row:
        raise HTTPException(status_code=404, detail="Agent not found or not published")

    agent_version = agent_row[0]

    # インストール情報を作成
    installation_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # organization_id が未指定の場合は None を保持（ユーザーのみのインストール）
    unique_key = (agent_id, user_id, request.organization_id)

    # 既存のインストール確認（update の場合）
    check_query = """
        SELECT id FROM marketplace_agent_installations
        WHERE agent_id = ? AND user_id = ? AND organization_id IS ?
    """
    async with db.execute(check_query, [agent_id, user_id, request.organization_id]) as cursor:
        existing = await cursor.fetchone()

    if existing:
        # 既に存在する場合は error
        raise HTTPException(status_code=409, detail="Agent already installed")

    # インストール記録を挿入
    insert_query = """
        INSERT INTO marketplace_agent_installations
        (id, agent_id, user_id, organization_id, release_version, installed_at, status, configuration)
        VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
    """

    config_json = json.dumps(request.configuration) if request.configuration else None

    try:
        await db.execute(
            insert_query,
            [
                installation_id,
                agent_id,
                user_id,
                request.organization_id,
                agent_version,
                now,
                config_json
            ]
        )
        await db.commit()
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail="Installation conflict")

    return InstallAgentResponse(
        id=installation_id,
        agent_id=agent_id,
        user_id=user_id,
        status="active",
        installed_at=now
    )

@router.get("/categories", response_model=List[AgentCategory])
async def list_categories(
    db: aiosqlite.Connection = Depends(get_db)
) -> List[AgentCategory]:
    """
    カテゴリ一覧を取得
    """
    query = """
        SELECT id, name, description, display_order
        FROM marketplace_categories
        ORDER BY display_order ASC, name ASC
    """

    async with db.execute(query) as cursor:
        rows = await cursor.fetchall()

    return [
        AgentCategory(
            id=row[0],
            name=row[1],
            description=row[2],
            display_order=row[3]
        )
        for row in rows
    ]
