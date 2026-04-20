"""E2E tests for departments API - TC-1 to TC-8."""

import pytest
from fastapi.testclient import TestClient


class TestDepartmentsE2E:
    """Departments API E2E test suite."""

    def test_tc1_create_department_success(self, client: TestClient):
        """TC-1: 部署テンプレート作成（正常系）."""
        payload = {
            "name": "開発部",
            "slug": "development",
            "description": "ソフトウェア開発を担当する部署",
            "budget": 5000000.0,
        }

        response = client.post("/api/departments", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["name"] == "開発部"
        assert data["slug"] == "development"
        assert data["description"] == "ソフトウェア開発を担当する部署"
        assert data["budget"] == 5000000.0
        assert data["status"] == "active"
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        assert "agent_count" in data
        assert "team_count" in data

    def test_tc2_list_departments_success(self, client: TestClient):
        """TC-2: 部署リスト取得（正常系）."""
        # Create some departments first
        client.post(
            "/api/departments",
            json={
                "name": "営業部",
                "slug": "sales",
                "description": "営業活動",
                "budget": 3000000.0,
            },
        )
        client.post(
            "/api/departments",
            json={
                "name": "企画部",
                "slug": "planning",
                "description": "企画・戦略",
                "budget": 2000000.0,
            },
        )

        response = client.get("/api/departments?status=active&limit=20")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 2
        assert data["pagination"]["limit"] == 20
        assert data["pagination"]["page"] == 1

        # Check created departments are in the list
        dept_names = [d["name"] for d in data["data"]]
        assert "営業部" in dept_names
        assert "企画部" in dept_names

    def test_tc3_get_department_detail_success(self, client: TestClient):
        """TC-3: 部署詳細取得（正常系）."""
        # Create a department
        create_response = client.post(
            "/api/departments",
            json={
                "name": "人事部",
                "slug": "hr",
                "description": "人材管理",
                "budget": 1500000.0,
            },
        )
        dept_id = create_response.json()["id"]

        response = client.get(f"/api/departments/{dept_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dept_id
        assert data["name"] == "人事部"
        assert data["slug"] == "hr"
        assert data["status"] == "active"
        assert "agent_count" in data
        assert "team_count" in data
        assert isinstance(data["agent_count"], int)
        assert isinstance(data["team_count"], int)

    def test_tc4_create_department_duplicate_name_error(self, client: TestClient):
        """TC-4: 重複名エラー（異常系）."""
        payload1 = {
            "name": "一意の部署名",
            "slug": "unique-slug-1",
            "description": "説明",
            "budget": 1000000.0,
        }
        payload2 = {
            "name": "一意の部署名",
            "slug": "unique-slug-2",
            "description": "別のスラッグ",
            "budget": 2000000.0,
        }

        # Create first department
        response1 = client.post("/api/departments", json=payload1)
        assert response1.status_code == 201

        # Try to create with same name but different slug
        response2 = client.post("/api/departments", json=payload2)

        assert response2.status_code == 400
        data = response2.json()
        assert "detail" in data
        assert data["detail"]["error"] == "DEPT_NAME_DUPLICATE"
        assert "部署名が既に存在します" in data["detail"]["message"]

    def test_tc5_create_department_duplicate_slug_error(self, client: TestClient):
        """TC-5: スラッグ重複エラー（異常系）."""
        payload1 = {
            "name": "部署A",
            "slug": "duplicate-slug",
            "description": "説明1",
            "budget": 1000000.0,
        }
        payload2 = {
            "name": "部署B",
            "slug": "duplicate-slug",
            "description": "説明2",
            "budget": 2000000.0,
        }

        # Create first department
        response1 = client.post("/api/departments", json=payload1)
        assert response1.status_code == 201

        # Try to create with same slug
        response2 = client.post("/api/departments", json=payload2)

        assert response2.status_code == 400
        data = response2.json()
        assert "detail" in data
        assert data["detail"]["error"] == "DEPT_SLUG_DUPLICATE"
        assert "スラッグが既に存在します" in data["detail"]["message"]

    def test_tc6_filter_by_status(self, client: TestClient):
        """TC-6: status フィルター."""
        # Create active department
        active_dept = client.post(
            "/api/departments",
            json={
                "name": "アクティブ部",
                "slug": "active-dept",
                "status": "active",
                "budget": 1000000.0,
            },
        ).json()

        # Get active departments
        response = client.get("/api/departments?status=active")

        assert response.status_code == 200
        data = response.json()
        dept_names = [d["name"] for d in data["data"]]
        assert "アクティブ部" in dept_names

        # All returned departments should have status='active'
        for dept in data["data"]:
            assert dept["status"] == "active"

    def test_tc7_filter_by_parent_id(self, client: TestClient):
        """TC-7: parent_id フィルター."""
        # Create parent department
        parent_response = client.post(
            "/api/departments",
            json={
                "name": "親部署",
                "slug": "parent-dept",
                "budget": 5000000.0,
            },
        )
        parent_id = parent_response.json()["id"]

        # Create child departments
        child1_response = client.post(
            "/api/departments",
            json={
                "name": "子部署1",
                "slug": "child-dept-1",
                "parent_id": parent_id,
                "budget": 2000000.0,
            },
        )
        child1_id = child1_response.json()["id"]

        child2_response = client.post(
            "/api/departments",
            json={
                "name": "子部署2",
                "slug": "child-dept-2",
                "parent_id": parent_id,
                "budget": 2000000.0,
            },
        )
        child2_id = child2_response.json()["id"]

        # Filter by parent_id
        response = client.get(f"/api/departments?parent_id={parent_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) >= 2

        child_ids = [d["id"] for d in data["data"]]
        assert child1_id in child_ids
        assert child2_id in child_ids

        # All returned departments should have parent_id set to parent_id
        for dept in data["data"]:
            assert dept["parent_id"] == parent_id

    def test_tc8_pagination(self, client: TestClient):
        """TC-8: ページネーション."""
        # Create 25 departments
        dept_slugs = []
        for i in range(25):
            response = client.post(
                "/api/departments",
                json={
                    "name": f"部署{i:02d}",
                    "slug": f"dept-{i:02d}",
                    "budget": 1000000.0,
                },
            )
            dept_slugs.append(response.json()["slug"])

        # Get first page (default limit=20)
        response1 = client.get("/api/departments?page=1&limit=20")
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["data"]) == 20
        assert data1["pagination"]["page"] == 1
        assert data1["pagination"]["limit"] == 20
        assert data1["pagination"]["total"] >= 25

        # Get second page
        response2 = client.get("/api/departments?page=2&limit=20")
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["data"]) >= 5

        # Check that pages don't overlap
        page1_ids = [d["id"] for d in data1["data"]]
        page2_ids = [d["id"] for d in data2["data"]]
        assert len(set(page1_ids) & set(page2_ids)) == 0

        # Get with smaller limit
        response3 = client.get("/api/departments?page=1&limit=10")
        assert response3.status_code == 200
        data3 = response3.json()
        assert len(data3["data"]) == 10
        assert data3["pagination"]["pages"] >= 3

    def test_get_nonexistent_department(self, client: TestClient):
        """テスト：存在しない部署を取得."""
        response = client.get("/api/departments/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_create_department_with_parent(self, client: TestClient):
        """テスト：親部署を指定して作成."""
        # Create parent
        parent_response = client.post(
            "/api/departments",
            json={
                "name": "親部署",
                "slug": "parent",
                "budget": 5000000.0,
            },
        )
        parent_id = parent_response.json()["id"]

        # Create child
        child_response = client.post(
            "/api/departments",
            json={
                "name": "子部署",
                "slug": "child",
                "parent_id": parent_id,
                "budget": 2000000.0,
            },
        )

        assert child_response.status_code == 201
        child_data = child_response.json()
        assert child_data["parent_id"] == parent_id

        # Verify parent relation
        detail_response = client.get(f"/api/departments/{child_data['id']}")
        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        assert detail_data["parent_id"] == parent_id
