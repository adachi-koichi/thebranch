import sqlite3
from typing import List, Dict, Optional
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/search", tags=["search"])

THEBRANCH_DB = Path(__file__).parent / "data" / "thebranch.sqlite"


def _safe_search(table: str, query: str, fields: List[str], id_field: str, title_field: str, result_type: str, url_base: str) -> List[Dict]:
    try:
        conn = sqlite3.connect(THEBRANCH_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        conditions = " OR ".join([f"{f} LIKE ?" for f in fields])
        params = [f"%{query}%" for _ in fields]
        cursor.execute(f"SELECT {id_field}, {title_field} FROM {table} WHERE {conditions} LIMIT 10", params)
        results = [{"type": result_type, "id": row[id_field], "title": row[title_field], "description": "", "url": f"{url_base}/{row[id_field]}"} for row in cursor.fetchall()]
        conn.close()
        return results
    except sqlite3.OperationalError:
        return []


def search_departments(query: str) -> List[Dict]:
    return _safe_search("departments", query, ["name", "description"], "id", "name", "department", "/departments")


def search_workflows(query: str) -> List[Dict]:
    return _safe_search("workflow_templates", query, ["name", "description"], "id", "name", "workflow", "/workflows")


def search_teams(query: str) -> List[Dict]:
    return _safe_search("teams", query, ["name"], "id", "name", "team", "/teams")


@router.get("")
async def search(q: str = Query(..., min_length=2), search_type: str = Query("all")) -> Dict:
    if not THEBRANCH_DB.exists():
        raise HTTPException(status_code=500, detail="Database not found")

    results = []

    if search_type in ("all", "department"):
        results.extend(search_departments(q))
    if search_type in ("all", "workflow"):
        results.extend(search_workflows(q))
    if search_type in ("all", "team"):
        results.extend(search_teams(q))

    return {
        "results": results,
        "total": len(results),
        "query": q
    }
