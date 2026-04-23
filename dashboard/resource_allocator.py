"""
Resource Allocator Module
Handles resource allocation logic and validations for multi-department resource sharing
"""

import sqlite3
from typing import Optional, Dict, List, Tuple
from pathlib import Path


class ResourceAllocator:
    """Manages resource allocation across departments"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def check_availability(self, resource_type: str, required_amount: int) -> bool:
        """Check if resource is available globally"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """SELECT SUM(total_allocated) as total, SUM(current_used) as used,
                          SUM(reserved) as reserved
                   FROM department_resources
                   WHERE resource_type = ?""",
                (resource_type,)
            )
            result = cursor.fetchone()
            conn.close()

            if not result or result["total"] is None:
                return False

            total = result["total"]
            used = result["used"] or 0
            reserved = result["reserved"] or 0
            available = total - used - reserved

            return available >= required_amount
        except Exception as e:
            print(f"Error checking availability: {str(e)}")
            return False

    def allocate_resource(
        self, department_id: int, resource_type: str, amount: int, priority: int = 3
    ) -> bool:
        """Allocate resource to department"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Check current usage
            cursor.execute(
                """SELECT total_allocated, current_used, reserved
                   FROM department_resources
                   WHERE department_id = ? AND resource_type = ?""",
                (department_id, resource_type)
            )
            resource = cursor.fetchone()

            if not resource:
                # Create new resource entry
                cursor.execute(
                    """INSERT INTO department_resources
                       (department_id, resource_type, total_allocated, current_used, reserved)
                       VALUES (?, ?, ?, ?, ?)""",
                    (department_id, resource_type, amount, 0, 0)
                )
            else:
                available = resource[0] - resource[1] - resource[2]
                if available < amount:
                    conn.close()
                    return False

                # Update reserved amount
                cursor.execute(
                    """UPDATE department_resources
                       SET reserved = reserved + ?
                       WHERE department_id = ? AND resource_type = ?""",
                    (amount, department_id, resource_type)
                )

            # Create allocation record
            cursor.execute(
                """INSERT INTO resource_allocations
                   (department_id, resource_type, amount, priority, status, allocated_at)
                   VALUES (?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)""",
                (department_id, resource_type, amount, priority)
            )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error allocating resource: {str(e)}")
            return False

    def deallocate_resource(self, allocation_id: int) -> bool:
        """Release allocated resource"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Get allocation details
            cursor.execute(
                """SELECT department_id, resource_type, amount
                   FROM resource_allocations
                   WHERE id = ?""",
                (allocation_id,)
            )
            allocation = cursor.fetchone()

            if not allocation:
                conn.close()
                return False

            dept_id, resource_type, amount = allocation

            # Update allocation status
            cursor.execute(
                """UPDATE resource_allocations
                   SET status = 'completed'
                   WHERE id = ?""",
                (allocation_id,)
            )

            # Release reserved amount
            cursor.execute(
                """UPDATE department_resources
                   SET reserved = reserved - ?
                   WHERE department_id = ? AND resource_type = ?""",
                (amount, dept_id, resource_type)
            )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deallocating resource: {str(e)}")
            return False

    def get_department_resource_summary(self, department_id: int) -> Dict:
        """Get resource summary for a department"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """SELECT resource_type, total_allocated, current_used, reserved
                   FROM department_resources
                   WHERE department_id = ?
                   ORDER BY resource_type""",
                (department_id,)
            )
            resources = cursor.fetchall()

            # Get active allocations
            cursor.execute(
                """SELECT resource_type, SUM(amount) as total_allocated
                   FROM resource_allocations
                   WHERE department_id = ? AND status = 'active'
                   GROUP BY resource_type""",
                (department_id,)
            )
            allocations = cursor.fetchall()

            summary = {
                "department_id": department_id,
                "resources": [dict(r) for r in resources],
                "allocations": [dict(a) for a in allocations],
                "total_resources": len(resources),
                "utilization_percent": self._calculate_utilization(resources)
            }

            conn.close()
            return summary
        except Exception as e:
            print(f"Error getting resource summary: {str(e)}")
            return {}

    def _calculate_utilization(self, resources: List) -> float:
        """Calculate overall resource utilization percentage"""
        if not resources:
            return 0.0

        total_allocated = sum(r["total_allocated"] or 0 for r in resources)
        total_used = sum(r["current_used"] or 0 for r in resources)

        if total_allocated == 0:
            return 0.0

        return (total_used / total_allocated) * 100

    def get_resource_requests(self, department_id: Optional[int] = None) -> List[Dict]:
        """Get resource requests, optionally filtered by department"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if department_id:
                cursor.execute(
                    """SELECT * FROM resource_requests
                       WHERE department_id = ?
                       ORDER BY created_at DESC""",
                    (department_id,)
                )
            else:
                cursor.execute(
                    """SELECT * FROM resource_requests
                       ORDER BY created_at DESC"""
                )

            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error getting resource requests: {str(e)}")
            return []

    def update_resource_usage(
        self, department_id: int, resource_type: str, used_amount: int
    ) -> bool:
        """Update current resource usage"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """UPDATE department_resources
                   SET current_used = ?
                   WHERE department_id = ? AND resource_type = ?""",
                (used_amount, department_id, resource_type)
            )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating resource usage: {str(e)}")
            return False
