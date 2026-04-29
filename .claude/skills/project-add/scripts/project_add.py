#!/usr/bin/env python3
"""
project_add.py — thebranch プロジェクト管理 CLI

workflow.services.project_service を呼び出す薄いラッパー。
コアロジックは project_service / project_repository に集約。

使用例:
  python3 project_add.py add --json-file project.json
  python3 project_add.py add --json-str '{"name":"X","workflows":[]}'
  python3 project_add.py list
  python3 project_add.py show --id 1
  python3 project_add.py delete --id 1
"""

import argparse
import json
import sys
from pathlib import Path

# thebranch ルートを sys.path に追加
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from workflow.services import project_service


def cmd_add(args):
    if args.json_file:
        src = Path(args.json_file).read_text(encoding="utf-8")
    elif args.json_str:
        src = args.json_str
    else:
        src = sys.stdin.read()

    spec = json.loads(src)
    result = project_service.create_project_from_spec(spec)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_list(args):
    projects = project_service.list_projects(status=args.status)
    if args.json_out:
        print(json.dumps(projects, ensure_ascii=False, indent=2))
    else:
        print(f"{'ID':>4}  {'Status':8}  {'Name'}")
        print("-" * 60)
        for p in projects:
            print(f"{p['id']:>4}  {p['status']:8}  {p['name']}")


def cmd_show(args):
    result = project_service.get_project_detail(args.id)
    if not result:
        print(f"Project #{args.id} not found", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_delete(args):
    result = project_service.delete_project(args.id)
    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="thebranch プロジェクト管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="プロジェクトを追加")
    p_add.add_argument("--json-file", "-f", help="JSON 定義ファイルパス")
    p_add.add_argument("--json-str", "-s", help="JSON 文字列")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="プロジェクト一覧")
    p_list.add_argument("--status", help="フィルタ: active / archived / draft")
    p_list.add_argument("--json", dest="json_out", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="プロジェクト詳細")
    p_show.add_argument("--id", type=int, required=True)
    p_show.set_defaults(func=cmd_show)

    p_del = sub.add_parser("delete", help="プロジェクトを削除")
    p_del.add_argument("--id", type=int, required=True)
    p_del.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
