"""
Seed script for department templates (Legal Department & Finance Department).

Inserts initial template data into:
- departments_templates
- department_template_roles
- department_template_processes
- department_template_tasks
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Legal Department Template Definition
LEGAL_DEPARTMENT_TEMPLATE = {
    "name": "Legal Department",
    "category": "back-office",
    "description": "法務・コンプライアンス業務を担当する部署",
    "created_by": "system",
    "roles": [
        {
            "role_key": "general-counsel",
            "role_label": "法務部長",
            "role_order": 1,
            "min_members": 1,
            "max_members": 1,
            "responsibility": "法務部門全体の統括、法律戦略の企画・実行",
            "required_skills": json.dumps(["legal_strategy", "contract_negotiation", "compliance"]),
        },
        {
            "role_key": "legal-manager",
            "role_label": "法務マネージャー",
            "role_order": 2,
            "supervisor_role_key": "general-counsel",
            "min_members": 1,
            "max_members": 2,
            "responsibility": "契約審査・リスク管理の実行",
            "required_skills": json.dumps(["contract_review", "legal_analysis", "risk_management"]),
        },
        {
            "role_key": "compliance-officer",
            "role_label": "コンプライアンス担当",
            "role_order": 2,
            "supervisor_role_key": "general-counsel",
            "min_members": 1,
            "max_members": 2,
            "responsibility": "規制対応・ポリシー開発・監査",
            "required_skills": json.dumps(["regulatory_compliance", "audit", "policy_development"]),
        },
        {
            "role_key": "legal-specialist",
            "role_label": "法務スペシャリスト",
            "role_order": 3,
            "supervisor_role_key": "legal-manager",
            "min_members": 1,
            "max_members": 3,
            "responsibility": "契約作成・法務調査・文書作成",
            "required_skills": json.dumps(["contract_drafting", "legal_research", "documentation"]),
        },
    ],
    "processes": [
        {
            "process_key": "contract-management",
            "process_label": "契約管理",
            "process_order": 1,
            "responsible_role_key": "legal-manager",
            "frequency": "ad-hoc",
            "estimated_hours": 8,
            "description": "契約書の受付・審査・承認フロー",
            "doc_requirements": json.dumps([
                {"name": "Contract Review Report", "format": "pdf", "mandatory": True},
                {"name": "Risk Assessment", "format": "docx", "mandatory": True},
            ]),
            "tasks": [
                {
                    "task_key": "contract-intake",
                    "task_title": "契約書受付・分類",
                    "task_description": "新規契約書の受け付けと分類",
                    "assigned_role_key": "legal-specialist",
                    "category": "data-entry",
                    "estimated_hours": 1,
                    "priority": 2,
                },
                {
                    "task_key": "contract-review",
                    "task_title": "契約書レビュー",
                    "task_description": "契約内容の法的審査",
                    "assigned_role_key": "legal-manager",
                    "category": "review",
                    "estimated_hours": 4,
                    "depends_on_key": "contract-intake",
                    "priority": 1,
                },
                {
                    "task_key": "contract-approval",
                    "task_title": "契約承認",
                    "task_description": "法務部長による最終承認",
                    "assigned_role_key": "general-counsel",
                    "category": "approval",
                    "estimated_hours": 2,
                    "depends_on_key": "contract-review",
                    "priority": 1,
                },
            ],
        },
        {
            "process_key": "compliance-audit",
            "process_label": "コンプライアンス監査",
            "process_order": 2,
            "responsible_role_key": "compliance-officer",
            "frequency": "quarterly",
            "estimated_hours": 20,
            "description": "四半期ごとのコンプライアンス監査",
            "tasks": [
                {
                    "task_key": "compliance-check",
                    "task_title": "コンプライアンス確認",
                    "task_description": "各部門のコンプライアンス状況確認",
                    "assigned_role_key": "compliance-officer",
                    "category": "validation",
                    "estimated_hours": 8,
                    "priority": 1,
                },
                {
                    "task_key": "remediation-plan",
                    "task_title": "改善計画作成",
                    "task_description": "発見された問題への改善計画",
                    "assigned_role_key": "compliance-officer",
                    "category": "analysis",
                    "estimated_hours": 6,
                    "depends_on_key": "compliance-check",
                    "priority": 1,
                },
                {
                    "task_key": "executive-report",
                    "task_title": "経営層報告",
                    "task_description": "監査結果の経営層への報告",
                    "assigned_role_key": "general-counsel",
                    "category": "approval",
                    "estimated_hours": 2,
                    "depends_on_key": "remediation-plan",
                    "priority": 1,
                },
            ],
        },
    ],
}

# Finance Department Template Definition
FINANCE_DEPARTMENT_TEMPLATE = {
    "name": "Finance Department",
    "category": "back-office",
    "description": "財務管理・経理業務を担当する部署",
    "created_by": "system",
    "roles": [
        {
            "role_key": "finance-director",
            "role_label": "財務部長",
            "role_order": 1,
            "min_members": 1,
            "max_members": 1,
            "responsibility": "財務戦略の企画・実行、部署全体の統括",
            "required_skills": json.dumps(["financial_strategy", "budget_management", "reporting"]),
        },
        {
            "role_key": "finance-manager",
            "role_label": "財務マネージャー",
            "role_order": 2,
            "supervisor_role_key": "finance-director",
            "min_members": 1,
            "max_members": 3,
            "responsibility": "月次決算・財務分析",
            "required_skills": json.dumps(["accounting", "tax_planning", "financial_analysis"]),
        },
        {
            "role_key": "accountant",
            "role_label": "経理",
            "role_order": 3,
            "supervisor_role_key": "finance-manager",
            "min_members": 2,
            "max_members": 5,
            "responsibility": "日次経理処理・帳簿管理",
            "required_skills": json.dumps(["journal_entry", "reconciliation", "compliance"]),
        },
        {
            "role_key": "audit-specialist",
            "role_label": "監査担当",
            "role_order": 2,
            "supervisor_role_key": "finance-director",
            "min_members": 1,
            "max_members": 2,
            "responsibility": "四半期監査の実施",
            "required_skills": json.dumps(["audit", "risk_assessment", "compliance_review"]),
        },
    ],
    "processes": [
        {
            "process_key": "daily-cash-management",
            "process_label": "日次現金管理",
            "process_order": 1,
            "responsible_role_key": "accountant",
            "frequency": "daily",
            "estimated_hours": 1,
            "description": "日次現金の照合と記録",
            "tasks": [
                {
                    "task_key": "reconcile-cash-accounts",
                    "task_title": "現金勘定の照合",
                    "task_description": "銀行口座と帳簿の照合",
                    "assigned_role_key": "accountant",
                    "category": "validation",
                    "estimated_hours": 0.5,
                    "priority": 1,
                },
                {
                    "task_key": "record-daily-transactions",
                    "task_title": "日次取引記録",
                    "task_description": "日次の取引を帳簿に記録",
                    "assigned_role_key": "accountant",
                    "category": "data-entry",
                    "estimated_hours": 0.5,
                    "depends_on_key": "reconcile-cash-accounts",
                    "priority": 1,
                },
            ],
        },
        {
            "process_key": "monthly-closing",
            "process_label": "月次決算",
            "process_order": 2,
            "responsible_role_key": "finance-manager",
            "frequency": "monthly",
            "estimated_hours": 16,
            "description": "月次決算書の作成と承認",
            "doc_requirements": json.dumps([
                {"name": "Trial Balance", "format": "xlsx", "mandatory": True},
                {"name": "General Ledger", "format": "xlsx", "mandatory": True},
                {"name": "Monthly Report", "format": "pdf", "mandatory": True},
            ]),
            "tasks": [
                {
                    "task_key": "reconcile-ledger",
                    "task_title": "元帳照合",
                    "task_description": "各勘定の照合作業",
                    "assigned_role_key": "accountant",
                    "category": "validation",
                    "estimated_hours": 2,
                    "priority": 1,
                },
                {
                    "task_key": "prepare-trial-balance",
                    "task_title": "試算表作成",
                    "task_description": "月次試算表の作成",
                    "assigned_role_key": "accountant",
                    "category": "analysis",
                    "estimated_hours": 2,
                    "depends_on_key": "reconcile-ledger",
                    "priority": 1,
                },
                {
                    "task_key": "review-adjustments",
                    "task_title": "決算整理項目の検討",
                    "task_description": "月末調整事項の検討",
                    "assigned_role_key": "finance-manager",
                    "category": "review",
                    "estimated_hours": 3,
                    "depends_on_key": "prepare-trial-balance",
                    "priority": 1,
                },
                {
                    "task_key": "approve-closing",
                    "task_title": "月次決算の承認",
                    "task_description": "決算書の最終承認",
                    "assigned_role_key": "finance-director",
                    "category": "approval",
                    "estimated_hours": 1,
                    "depends_on_key": "review-adjustments",
                    "priority": 1,
                },
            ],
        },
        {
            "process_key": "quarterly-audit",
            "process_label": "四半期監査",
            "process_order": 3,
            "responsible_role_key": "audit-specialist",
            "frequency": "quarterly",
            "estimated_hours": 24,
            "description": "四半期財務監査",
            "tasks": [
                {
                    "task_key": "audit-planning",
                    "task_title": "監査計画作成",
                    "task_description": "監査スコープの決定",
                    "assigned_role_key": "audit-specialist",
                    "category": "analysis",
                    "estimated_hours": 4,
                    "priority": 1,
                },
                {
                    "task_key": "conduct-audit",
                    "task_title": "監査実施",
                    "task_description": "監査テスト実施",
                    "assigned_role_key": "audit-specialist",
                    "category": "validation",
                    "estimated_hours": 12,
                    "depends_on_key": "audit-planning",
                    "priority": 1,
                },
                {
                    "task_key": "audit-report",
                    "task_title": "監査報告書作成",
                    "task_description": "監査結果報告書作成",
                    "assigned_role_key": "audit-specialist",
                    "category": "analysis",
                    "estimated_hours": 8,
                    "depends_on_key": "conduct-audit",
                    "priority": 1,
                },
            ],
        },
    ],
}


def insert_department_template(conn: sqlite3.Connection, template_data: dict) -> int:
    """Insert department template and return template ID."""
    cursor = conn.cursor()

    # Check if template already exists
    cursor.execute(
        "SELECT id FROM departments_templates WHERE name = ?",
        (template_data["name"],),
    )
    existing = cursor.fetchone()
    if existing:
        print(f"  Template '{template_data['name']}' already exists (ID: {existing[0]})")
        return existing[0]

    # Insert template
    cursor.execute(
        """
        INSERT INTO departments_templates
        (name, description, category, version, status, created_by, created_at, updated_at)
        VALUES (?, ?, ?, 1, 'active', ?, datetime('now','localtime'), datetime('now','localtime'))
        """,
        (
            template_data["name"],
            template_data["description"],
            template_data["category"],
            template_data["created_by"],
        ),
    )
    template_id = cursor.lastrowid
    print(f"  Inserted template: {template_data['name']} (ID: {template_id})")

    # Insert roles
    for role in template_data["roles"]:
        cursor.execute(
            """
            INSERT INTO department_template_roles
            (template_id, role_key, role_label, role_order, responsibility, required_skills,
             min_members, max_members, supervisor_role_key, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            """,
            (
                template_id,
                role["role_key"],
                role["role_label"],
                role["role_order"],
                role["responsibility"],
                role["required_skills"],
                role["min_members"],
                role["max_members"],
                role.get("supervisor_role_key"),
            ),
        )
        print(f"    Inserted role: {role['role_label']}")

    # Insert processes and tasks
    for process in template_data["processes"]:
        cursor.execute(
            """
            INSERT INTO department_template_processes
            (template_id, process_key, process_label, process_order, description,
             responsible_role_key, estimated_hours, frequency, doc_requirements,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), datetime('now','localtime'))
            """,
            (
                template_id,
                process["process_key"],
                process["process_label"],
                process["process_order"],
                process["description"],
                process["responsible_role_key"],
                process["estimated_hours"],
                process["frequency"],
                process.get("doc_requirements"),
            ),
        )
        process_id = cursor.lastrowid
        print(f"    Inserted process: {process['process_label']}")

        # Insert tasks
        for task in process["tasks"]:
            cursor.execute(
                """
                INSERT INTO department_template_tasks
                (process_id, template_id, task_key, task_title, task_description,
                 assigned_role_key, category, estimated_hours, depends_on_key, priority,
                 created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                """,
                (
                    process_id,
                    template_id,
                    task["task_key"],
                    task["task_title"],
                    task["task_description"],
                    task["assigned_role_key"],
                    task["category"],
                    task["estimated_hours"],
                    task.get("depends_on_key"),
                    task.get("priority", 3),
                ),
            )
            print(f"      Inserted task: {task['task_title']}")

    conn.commit()
    return template_id


def seed_department_templates(db_path: str) -> None:
    """Seed department template tables with initial data."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        print("[SEED] Inserting Legal Department template...")
        insert_department_template(conn, LEGAL_DEPARTMENT_TEMPLATE)

        print("\n[SEED] Inserting Finance Department template...")
        insert_department_template(conn, FINANCE_DEPARTMENT_TEMPLATE)

        print("\n[SEED] Department templates seeded successfully!")

    except Exception as e:
        print(f"[SEED] Error: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    db_path = str(Path(__file__).parent.parent / "dashboard" / "instance" / "tasks.sqlite")
    print(f"[SEED] Using database: {db_path}\n")
    seed_department_templates(db_path)
