#!/usr/bin/env python3
"""
Design Sprint Template Loader
THEBRANCHのデザインスプリント業務フロー（5日間）テンプレートを
task-manager-sqliteに登録するスクリプト
"""

import sqlite3
import json
from datetime import datetime
import sys

# DBパス
DB_PATH = "/Users/delightone/.claude/skills/task-manager-sqlite/tasks.sqlite"

def connect_db():
    """DB接続"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_template(conn):
    """テンプレートメタデータを登録"""
    cursor = conn.cursor()

    template_data = {
        "name": "Product Design Sprint (5-day)",
        "description": "5日間の構造化デザインスプリント。ビジョン確認～ユーザーテスト完了まで。",
        "version": 1,
        "status": "active",
        "category": "design",
        "estimated_duration_hours": 40,
        "specialist_types": json.dumps(["Design Lead", "Product Designer", "UX Researcher", "Developer"]),
        "icon": "🎨",
        "tags": json.dumps(["design", "sprint", "5-day", "ux", "product"]),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    cursor.execute("""
        INSERT INTO workflow_templates
        (name, description, version, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        template_data["name"],
        template_data["description"],
        template_data["version"],
        template_data["status"],
        template_data["created_at"],
        template_data["updated_at"]
    ))

    conn.commit()
    template_id = cursor.lastrowid
    print(f"✅ Template created: ID={template_id}")
    return template_id

def create_phases(conn, template_id):
    """フェーズを登録"""
    cursor = conn.cursor()

    phases = [
        {
            "phase_key": "monday-vision",
            "phase_order": 1,
            "phase_label": "Day 1: Vision Alignment",
            "specialist_type": "Design Lead",
            "specialist_count": 4,
            "task_count": 6,
            "estimated_hours": 7,
            "is_parallel": 0,
            "description": "ビジョン確認・ペルソナ分析・スコープ定義"
        },
        {
            "phase_key": "tuesday-journey",
            "phase_order": 2,
            "phase_label": "Day 2: Journey & IA",
            "specialist_type": "UX Researcher",
            "specialist_count": 3,
            "task_count": 6,
            "estimated_hours": 7,
            "is_parallel": 1,
            "description": "ユーザージャーニー詳細化・情報アーキテクチャ定義"
        },
        {
            "phase_key": "wednesday-design",
            "phase_order": 3,
            "phase_label": "Day 3: Wireframe & API",
            "specialist_type": "Product Designer",
            "specialist_count": 2,
            "task_count": 8,
            "estimated_hours": 8,
            "is_parallel": 1,
            "description": "ワイヤーフレーム・API設計を並列実行"
        },
        {
            "phase_key": "thursday-prototype",
            "phase_order": 4,
            "phase_label": "Day 4: Prototype Ready",
            "specialist_type": "Product Designer",
            "specialist_count": 2,
            "task_count": 8,
            "estimated_hours": 8,
            "is_parallel": 1,
            "description": "高忠度プロトタイプ完成・テスト準備"
        },
        {
            "phase_key": "friday-test",
            "phase_order": 5,
            "phase_label": "Day 5: User Test & Handover",
            "specialist_type": "UX Researcher",
            "specialist_count": 4,
            "task_count": 6,
            "estimated_hours": 7,
            "is_parallel": 0,
            "description": "ユーザーテスト実施・実装ロードマップ確定"
        }
    ]

    phase_ids = {}
    for phase in phases:
        try:
            cursor.execute("""
                INSERT INTO wf_template_phases
                (template_id, phase_key, phase_order, phase_label, specialist_type,
                 specialist_count, task_count, estimated_hours, is_parallel, description,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template_id,
                phase["phase_key"],
                phase["phase_order"],
                phase["phase_label"],
                phase["specialist_type"],
                phase["specialist_count"],
                phase["task_count"],
                phase["estimated_hours"],
                phase["is_parallel"],
                phase["description"],
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            phase_ids[phase["phase_key"]] = cursor.lastrowid
            print(f"  ✅ Phase: {phase['phase_label']}")
        except Exception as e:
            print(f"  ⚠️  Phase {phase['phase_key']} error: {e}")

    conn.commit()
    return phase_ids

def create_nodes(conn, template_id, phase_ids):
    """ノード（タスク）を登録"""
    cursor = conn.cursor()

    nodes = [
        # Day 1
        {
            "phase_key": "monday-vision",
            "node_key": "day1-vision-confirm",
            "node_type": "task",
            "label": "Vision & Usecase Confirmation",
            "role": "Design Lead",
            "description": "ビジョン・ユースケース確認（09:00-09:30）",
            "estimated_hours": 0.5
        },
        {
            "phase_key": "monday-vision",
            "node_key": "day1-persona-analysis",
            "node_type": "task",
            "label": "Persona Analysis & Feedback",
            "role": "UX Researcher",
            "description": "ペルソナ分析・フィードバック（09:30-10:30）",
            "estimated_hours": 1.0
        },
        {
            "phase_key": "monday-vision",
            "node_key": "day1-scope-definition",
            "node_type": "task",
            "label": "Scope Definition & Constraints",
            "role": "Design Lead",
            "description": "スコープ定義・制約条件確認（10:30-11:30）",
            "estimated_hours": 1.0
        },
        # Day 2
        {
            "phase_key": "tuesday-journey",
            "node_key": "day2-journey-mapping",
            "node_type": "task",
            "label": "User Journey Detailed Mapping",
            "role": "UX Researcher",
            "description": "ユーザージャーニー詳細化（09:00-10:00）",
            "estimated_hours": 1.0
        },
        {
            "phase_key": "tuesday-journey",
            "node_key": "day2-usecase-flow",
            "node_type": "task",
            "label": "Use Case Flow Design",
            "role": "Product Designer",
            "description": "ユースケースフロー設計（10:00-11:30）",
            "estimated_hours": 1.5
        },
        {
            "phase_key": "tuesday-journey",
            "node_key": "day2-ia-definition",
            "node_type": "task",
            "label": "Information Architecture Definition",
            "role": "Product Designer",
            "description": "情報アーキテクチャ定義（13:00-14:30）",
            "estimated_hours": 1.5
        },
        # Day 3
        {
            "phase_key": "wednesday-design",
            "node_key": "day3-wireframe",
            "node_type": "task",
            "label": "Wireframe Design (Figma)",
            "role": "Product Designer",
            "description": "ワイヤーフレーム作成（09:00-10:30）",
            "estimated_hours": 1.5
        },
        {
            "phase_key": "wednesday-design",
            "node_key": "day3-api-design",
            "node_type": "task",
            "label": "API Specification Design",
            "role": "Developer",
            "description": "APIエンドポイント設計（09:00-11:30）",
            "estimated_hours": 2.5
        },
        {
            "phase_key": "wednesday-design",
            "node_key": "day3-sync-design-api",
            "node_type": "gateway_and_join",
            "label": "Design-API Sync Point",
            "role": "Team Lead",
            "description": "デザインとAPI仕様の確認・調整（11:00）",
            "estimated_hours": 0.25
        },
        # Day 4
        {
            "phase_key": "thursday-prototype",
            "node_key": "day4-hifi-design",
            "node_type": "task",
            "label": "High-Fidelity Design Polish",
            "role": "Product Designer",
            "description": "高忠度デザイン完成（09:00-12:00）",
            "estimated_hours": 3.0
        },
        {
            "phase_key": "thursday-prototype",
            "node_key": "day4-frontend-implementation",
            "node_type": "task",
            "label": "Frontend Implementation",
            "role": "Developer",
            "description": "フロントエンド実装（09:00-15:00）",
            "estimated_hours": 6.0
        },
        # Day 5
        {
            "phase_key": "friday-test",
            "node_key": "day5-user-test",
            "node_type": "task",
            "label": "User Testing Execution",
            "role": "UX Researcher",
            "description": "ユーザーテスト実施（09:00-12:00）",
            "estimated_hours": 3.0
        },
        {
            "phase_key": "friday-test",
            "node_key": "day5-feedback-integration",
            "node_type": "task",
            "label": "Feedback Integration & Roadmap",
            "role": "Design Lead",
            "description": "フィードバック統合・実装ロードマップ確定（13:00-17:00）",
            "estimated_hours": 4.0
        },
    ]

    node_ids = {}
    for node in nodes:
        try:
            phase_id = phase_ids.get(node["phase_key"])
            if not phase_id:
                print(f"  ⚠️  Phase ID not found for {node['phase_key']}")
                continue

            cursor.execute("""
                INSERT INTO wf_template_nodes
                (template_id, node_key, node_type, label, role, phase_key, description,
                 estimated_hours, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template_id,
                node["node_key"],
                node["node_type"],
                node["label"],
                node["role"],
                node["phase_key"],
                node["description"],
                node["estimated_hours"],
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            node_ids[node["node_key"]] = cursor.lastrowid
        except Exception as e:
            print(f"  ⚠️  Node {node['node_key']} error: {e}")

    conn.commit()
    print(f"✅ Nodes created: {len(node_ids)}")
    return node_ids

def create_edges(conn, template_id, node_ids):
    """エッジ（遷移ルール）を登録"""
    cursor = conn.cursor()

    edges = [
        ("day1-vision-confirm", "day1-persona-analysis", None),
        ("day1-persona-analysis", "day1-scope-definition", None),
        ("day1-scope-definition", "day2-journey-mapping", None),
        ("day2-journey-mapping", "day2-usecase-flow", None),
        ("day2-usecase-flow", "day2-ia-definition", None),
        ("day2-ia-definition", "day3-wireframe", None),
        ("day2-ia-definition", "day3-api-design", None),
        ("day3-wireframe", "day3-sync-design-api", None),
        ("day3-api-design", "day3-sync-design-api", None),
        ("day3-sync-design-api", "day4-hifi-design", None),
        ("day3-sync-design-api", "day4-frontend-implementation", None),
        ("day4-hifi-design", "day5-user-test", None),
        ("day4-frontend-implementation", "day5-user-test", None),
        ("day5-user-test", "day5-feedback-integration", None),
    ]

    for from_key, to_key, condition in edges:
        try:
            from_id = node_ids.get(from_key)
            to_id = node_ids.get(to_key)
            if not from_id or not to_id:
                print(f"  ⚠️  Node ID not found: {from_key} → {to_key}")
                continue

            cursor.execute("""
                INSERT INTO wf_template_edges
                (template_id, from_node_id, to_node_id, condition, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                template_id,
                from_id,
                to_id,
                condition,
                datetime.now().isoformat()
            ))
        except Exception as e:
            print(f"  ⚠️  Edge {from_key} → {to_key} error: {e}")

    conn.commit()
    print(f"✅ Edges created")

def main():
    """メイン処理"""
    try:
        conn = connect_db()
        print(f"📄 Connecting to: {DB_PATH}")

        # テーブル確認
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = [
            "workflow_templates",
            "wf_template_phases",
            "wf_template_nodes",
            "wf_template_edges"
        ]

        for table in required_tables:
            if table not in tables:
                print(f"❌ Required table not found: {table}")
                return 1

        print(f"✅ All required tables found\n")

        # テンプレート登録
        print("📝 Registering Design Sprint Template...")
        template_id = create_template(conn)

        print(f"\n📋 Creating phases...")
        phase_ids = create_phases(conn, template_id)

        print(f"\n🎯 Creating nodes...")
        node_ids = create_nodes(conn, template_id, phase_ids)

        print(f"\n🔗 Creating edges...")
        create_edges(conn, template_id, node_ids)

        conn.close()
        print(f"\n✅ Design Sprint Template successfully registered!")
        print(f"   Template ID: {template_id}")
        print(f"   Phases: {len(phase_ids)}")
        print(f"   Nodes: {len(node_ids)}")
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
