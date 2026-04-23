"""
Resource Allocation API Routes
Implements FastAPI endpoints for resource allocation management
"""

import sqlite3
import aiosqlite
import logging
from typing import Optional
from pathlib import Path
from fastapi import HTTPException

from . import models

logger = logging.getLogger(__name__)


class ResourceRoutes:
    """Resource allocation route handlers"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def get_resources(self, department_id: Optional[int] = None):
        """Get all resources or resources for a specific department"""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                db.row_factory = sqlite3.Row

                if department_id:
                    cursor = await db.execute(
                        """SELECT id, department_id, resource_type, total_allocated,
                                  current_used, reserved, unit, created_at, updated_at
                           FROM department_resources
                           WHERE department_id = ?
                           ORDER BY resource_type""",
                        (department_id,)
                    )
                else:
                    cursor = await db.execute(
                        """SELECT id, department_id, resource_type, total_allocated,
                                  current_used, reserved, unit, created_at, updated_at
                           FROM department_resources
                           ORDER BY department_id, resource_type"""
                    )

                rows = await cursor.fetchall()
                resources = [dict(row) for row in rows]

                return {
                    "success": True,
                    "count": len(resources),
                    "resources": resources
                }
        except Exception as e:
            logger.error(f"Failed to get resources: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def request_resource(self, request: models.ResourceAllocationRequest):
        """Request resource allocation"""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                db.row_factory = sqlite3.Row

                # Verify department exists
                cursor = await db.execute(
                    "SELECT id FROM departments WHERE id = ?",
                    (request.department_id,)
                )
                dept = await cursor.fetchone()
                if not dept:
                    raise HTTPException(status_code=404, detail="Department not found")

                # Create resource request
                cursor = await db.execute(
                    """INSERT INTO resource_requests
                       (department_id, resource_type, required_amount, reason, status)
                       VALUES (?, ?, ?, ?, 'pending')""",
                    (request.department_id, request.resource_type, request.required_amount, request.reason)
                )
                await db.commit()
                request_id = cursor.lastrowid

                return {
                    "success": True,
                    "resource_request_id": request_id,
                    "status": "pending",
                    "message": "Resource request created"
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create resource request: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def allocate_resource(
        self, request_id: int, approval: models.ResourceAllocationApprovalRequest
    ):
        """Approve and allocate resources"""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                db.row_factory = sqlite3.Row

                # Get resource request
                cursor = await db.execute(
                    """SELECT * FROM resource_requests WHERE id = ?""",
                    (request_id,)
                )
                req = await cursor.fetchone()
                if not req:
                    raise HTTPException(status_code=404, detail="Resource request not found")

                dept_id = req["department_id"]
                resource_type = req["resource_type"]
                approved_amount = approval.approved_amount

                # Check if department has enough resources available
                cursor = await db.execute(
                    """SELECT total_allocated, current_used, reserved
                       FROM department_resources
                       WHERE department_id = ? AND resource_type = ?""",
                    (dept_id, resource_type)
                )
                resource = await cursor.fetchone()

                if not resource:
                    # Create new resource entry if doesn't exist
                    cursor = await db.execute(
                        """INSERT INTO department_resources
                           (department_id, resource_type, total_allocated, current_used, reserved)
                           VALUES (?, ?, ?, ?, ?)""",
                        (dept_id, resource_type, approved_amount, 0, 0)
                    )
                    await db.commit()
                else:
                    available = resource["total_allocated"] - resource["current_used"] - resource["reserved"]
                    if available < approved_amount:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Insufficient resources. Available: {available}, Requested: {approved_amount}"
                        )

                # Update resource request status
                cursor = await db.execute(
                    """UPDATE resource_requests
                       SET status = 'approved', approved_amount = ?, approval_reason = ?,
                           approved_by = ?, approved_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (approved_amount, approval.approval_reason, approval.approved_by or "system", request_id)
                )
                await db.commit()

                # Create resource allocation
                cursor = await db.execute(
                    """INSERT INTO resource_allocations
                       (department_id, resource_type, amount, status, allocated_at)
                       VALUES (?, ?, ?, 'active', CURRENT_TIMESTAMP)""",
                    (dept_id, resource_type, approved_amount)
                )
                await db.commit()
                allocation_id = cursor.lastrowid

                # Update reserved amount
                cursor = await db.execute(
                    """UPDATE department_resources
                       SET reserved = reserved + ?
                       WHERE department_id = ? AND resource_type = ?""",
                    (approved_amount, dept_id, resource_type)
                )
                await db.commit()

                return {
                    "success": True,
                    "allocation_id": allocation_id,
                    "status": "active",
                    "approved_amount": approved_amount,
                    "message": "Resource allocated successfully"
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to allocate resource: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_resource_status(self, request_id: int):
        """Get resource allocation status"""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                db.row_factory = sqlite3.Row

                # Get resource request
                cursor = await db.execute(
                    """SELECT * FROM resource_requests WHERE id = ?""",
                    (request_id,)
                )
                req = await cursor.fetchone()
                if not req:
                    raise HTTPException(status_code=404, detail="Resource request not found")

                # Get related allocations
                cursor = await db.execute(
                    """SELECT * FROM resource_allocations
                       WHERE department_id = ? AND resource_type = ? AND status = 'active'""",
                    (req["department_id"], req["resource_type"])
                )
                allocations = await cursor.fetchall()

                # Get current resource usage
                cursor = await db.execute(
                    """SELECT * FROM department_resources
                       WHERE department_id = ? AND resource_type = ?""",
                    (req["department_id"], req["resource_type"])
                )
                resource = await cursor.fetchone()

                return {
                    "success": True,
                    "request_id": request_id,
                    "request_status": req["status"],
                    "request_details": {
                        "department_id": req["department_id"],
                        "resource_type": req["resource_type"],
                        "required_amount": req["required_amount"],
                        "approved_amount": req["approved_amount"],
                        "reason": req["reason"],
                        "requested_at": req["requested_at"],
                        "approved_at": req["approved_at"]
                    },
                    "allocations": [dict(a) for a in allocations] if allocations else [],
                    "resource_summary": dict(resource) if resource else None
                }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get resource status: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
