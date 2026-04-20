#!/usr/bin/env python3
"""
task_visualizer.py - タスク状態可視化スクリプト

ターミナル上でタスクの状態分布・優先度分布・カテゴリ別集計を
ASCII グラフで表示する。

使い方:
  python3 task_visualizer.py              # サマリー表示
  python3 task_visualizer.py --mode bar   # バーチャート
  python3 task_visualizer.py --mode pie   # 状態分布（ASCII）
  python3 task_visualizer.py --mode list  # 直近タスク一覧
  python3 task_visualizer.py --watch 10  # 10秒ごとに自動更新
"""

import argparse
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ──────────────────────────────────────────────
# DB パス
# ──────────────────────────────────────────────
TASKS_DB = Path.home() / ".claude" / "skills" / "task-manager-sqlite" / "data" / "tasks.sqlite"

# ──────────────────────────────────────────────
# ANSI カラー
# ──────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
GRAY   = "\033[90m"

STATUS_COLOR = {
    "pending":     YELLOW,
    "in_progress": CYAN,
    "reviewing":   BLUE,
    "completed":   GREEN,
    "cancelled":   GRAY,
    "blocked":     RED,
}

PRIORITY_COLOR = {
    1: RED,
    2: YELLOW,
    3: GREEN,
    4: CYAN,
    5: GRAY,
}

PRIORITY_LABEL = {
    1: "緊急",
    2: "高",
    3: "中",
    4: "低",
    5: "最低",
}


def colored(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def bar(value: int, max_value: int, width: int = 30, fill: str = "█", empty: str = "░") -> str:
    if max_value == 0:
        return empty * width
    filled = int(value / max_value * width)
    return fill * filled + empty * (width - filled)


def clear_screen():
    os.system("clear" if os.name != "nt" else "cls")


# ──────────────────────────────────────────────
# DB クエリ
# ──────────────────────────────────────────────

def fetch_tasks(db_path: Path) -> list[dict]:
    if not db_path.exists():
        print(colored(f"DB が見つかりません: {db_path}", RED))
        sys.exit(1)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""
        SELECT id, title, status, priority, category, phase,
               created_at, updated_at, due_date, session_name, project
        FROM dev_tasks
        WHERE status != 'cancelled'
        ORDER BY id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


# ──────────────────────────────────────────────
# 表示モード
# ──────────────────────────────────────────────

def mode_summary(tasks: list[dict]):
    """サマリーダッシュボード"""
    total = len(tasks)
    status_counts = Counter(t["status"] for t in tasks)
    priority_counts: Counter = Counter()
    for t in tasks:
        if t["priority"] is not None:
            try:
                priority_counts[int(t["priority"])] += 1
            except (ValueError, TypeError):
                pass
    category_counts = Counter(t["category"] or "未分類" for t in tasks)

    now = datetime.now()

    # 直近24h完了
    def parse_dt(s: str) -> datetime:
        """ISO形式のdatetime文字列をnaiveなdatetimeに変換"""
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt

    done_24h = sum(
        1 for t in tasks
        if t["status"] == "completed" and t.get("updated_at")
        and (now - parse_dt(t["updated_at"])).total_seconds() < 86400
    )

    # 期限切れ
    overdue = sum(
        1 for t in tasks
        if t.get("due_date") and t["status"] not in ("completed", "cancelled")
        and parse_dt(t["due_date"]) < now
    )

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║        AI Orchestrator タスク可視化ダッシュボード        ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════╝{RESET}")
    print(f"  更新: {GRAY}{now.strftime('%Y-%m-%d %H:%M:%S')}{RESET}  | 総タスク: {BOLD}{total}{RESET}件\n")

    # ── ステータス別 ──
    print(f"{BOLD}■ ステータス分布{RESET}")
    max_s = max(status_counts.values(), default=1)
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        color = STATUS_COLOR.get(status, WHITE)
        pct = count / total * 100 if total else 0
        b = bar(count, max_s, width=25)
        print(f"  {color}{status:<12}{RESET}  {colored(b, color)}  {count:>4} ({pct:.1f}%)")
    print()

    # ── 優先度別 ──
    print(f"{BOLD}■ 優先度分布{RESET}")
    max_p = max(priority_counts.values(), default=1)
    for prio in sorted(priority_counts):
        count = priority_counts[prio]
        color = PRIORITY_COLOR.get(prio, WHITE)
        label = PRIORITY_LABEL.get(prio, str(prio))
        pct = count / total * 100 if total else 0
        b = bar(count, max_p, width=25)
        print(f"  {color}P{prio} {label:<4}{RESET}  {colored(b, color)}  {count:>4} ({pct:.1f}%)")
    print()

    # ── カテゴリ別 TOP10 ──
    print(f"{BOLD}■ カテゴリ別 TOP10{RESET}")
    max_c = max(category_counts.values(), default=1)
    for cat, count in category_counts.most_common(10):
        pct = count / total * 100 if total else 0
        b = bar(count, max_c, width=20)
        print(f"  {BLUE}{cat[:18]:<18}{RESET}  {colored(b, BLUE)}  {count:>4} ({pct:.1f}%)")
    print()

    # ── 指標 ──
    in_prog = status_counts.get("in_progress", 0)
    pending = status_counts.get("pending", 0)
    reviewing = status_counts.get("reviewing", 0)
    print(f"{BOLD}■ クイック指標{RESET}")
    print(f"  {CYAN}進行中{RESET}       : {BOLD}{in_prog}{RESET} 件")
    print(f"  {YELLOW}保留中{RESET}       : {BOLD}{pending}{RESET} 件")
    print(f"  {BLUE}レビュー中{RESET}   : {BOLD}{reviewing}{RESET} 件")
    print(f"  {GREEN}24h完了{RESET}      : {BOLD}{done_24h}{RESET} 件")
    if overdue:
        print(f"  {RED}期限切れ{RESET}     : {BOLD}{overdue}{RESET} 件  {colored('← 要確認!', RED)}")
    print()


def mode_bar(tasks: list[dict]):
    """ステータス×カテゴリ のバーチャート"""
    print(f"\n{BOLD}{CYAN}■ カテゴリ × ステータス バーチャート{RESET}\n")
    cat_status: dict[str, Counter] = defaultdict(Counter)
    for t in tasks:
        cat = t["category"] or "未分類"
        cat_status[cat][t["status"]] += 1

    statuses = ["pending", "in_progress", "reviewing", "completed"]
    header = f"  {'カテゴリ':<18}"
    for s in statuses:
        color = STATUS_COLOR.get(s, WHITE)
        header += f"  {color}{s[:10]:<10}{RESET}"
    print(header)
    print("  " + "─" * 70)

    for cat, counts in sorted(cat_status.items(), key=lambda x: -sum(x[1].values())):
        row = f"  {BLUE}{cat[:18]:<18}{RESET}"
        for s in statuses:
            count = counts[s]
            color = STATUS_COLOR.get(s, WHITE)
            b = bar(count, 10, width=6, fill="▪", empty="·")
            row += f"  {color}{b}{RESET}{count:>3} "
        print(row)
    print()


def mode_pie(tasks: list[dict]):
    """ステータス分布（ASCII パイ風）"""
    print(f"\n{BOLD}{CYAN}■ ステータス分布{RESET}\n")
    total = len(tasks)
    status_counts = Counter(t["status"] for t in tasks)

    print(f"  総タスク数: {BOLD}{total}{RESET} 件\n")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        color = STATUS_COLOR.get(status, WHITE)
        pct = count / total * 100 if total else 0
        segments = int(pct / 2)
        pie_bar = "█" * segments
        print(f"  {color}{status:<12}{RESET}  {color}{pie_bar:<50}{RESET} {count:>4} ({pct:.1f}%)")
    print()


def mode_list(tasks: list[dict], limit: int = 30):
    """直近タスク一覧"""
    print(f"\n{BOLD}{CYAN}■ 直近タスク一覧 (最新 {limit} 件){RESET}\n")
    print(f"  {'ID':>6}  {'ステータス':<14}  {'P':>2}  {'カテゴリ':<15}  タイトル")
    print("  " + "─" * 90)
    now = datetime.now()
    for t in tasks[:limit]:
        status = t["status"]
        color = STATUS_COLOR.get(status, WHITE)
        prio = t["priority"] or 9
        prio_color = PRIORITY_COLOR.get(prio, WHITE)
        cat = (t["category"] or "─")[:15]
        title = t["title"][:48]

        due_marker = ""
        if t.get("due_date") and status not in ("completed", "cancelled"):
            try:
                _s = t["due_date"].replace("Z", "+00:00")
                _d = datetime.fromisoformat(_s)
                due = _d.replace(tzinfo=None) if _d.tzinfo else _d
                diff = (due - now).days
                if diff < 0:
                    due_marker = colored(f" [期限切れ+{-diff}d]", RED)
                elif diff <= 2:
                    due_marker = colored(f" [あと{diff}d]", YELLOW)
            except Exception:
                pass

        print(f"  {GRAY}{t['id']:>6}{RESET}  {color}{status:<14}{RESET}  {prio_color}{prio:>2}{RESET}  {BLUE}{cat:<15}{RESET}  {title}{due_marker}")
    print()


def mode_timeline(tasks: list[dict]):
    """直近7日間のタスク完了タイムライン"""
    print(f"\n{BOLD}{CYAN}■ 直近7日 完了タイムライン{RESET}\n")
    now = datetime.now()
    days: dict[str, int] = {}
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).strftime("%m-%d")
        days[d] = 0

    def _parse_dt(s: str) -> datetime:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    for t in tasks:
        if t["status"] == "completed" and t.get("updated_at"):
            try:
                dt = _parse_dt(t["updated_at"])
                key = dt.strftime("%m-%d")
                if key in days:
                    days[key] += 1
            except Exception:
                pass

    max_v = max(days.values(), default=1)
    for day, count in days.items():
        b = bar(count, max_v, width=30)
        print(f"  {GRAY}{day}{RESET}  {colored(b, GREEN)}  {count}")
    print()


# ──────────────────────────────────────────────
# エントリポイント
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI Orchestrator タスク状態可視化スクリプト"
    )
    parser.add_argument(
        "--mode",
        choices=["summary", "bar", "pie", "list", "timeline", "all"],
        default="all",
        help="表示モード (デフォルト: all)",
    )
    parser.add_argument(
        "--watch",
        type=int,
        default=0,
        metavar="SEC",
        help="N秒ごとに自動更新 (0=無効)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="list モードの表示件数 (デフォルト: 30)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(TASKS_DB),
        help="SQLite DB パス",
    )
    args = parser.parse_args()

    db_path = Path(args.db)

    def render():
        tasks = fetch_tasks(db_path)
        if args.watch:
            clear_screen()

        if args.mode == "all":
            mode_summary(tasks)
            mode_bar(tasks)
            mode_timeline(tasks)
        elif args.mode == "summary":
            mode_summary(tasks)
        elif args.mode == "bar":
            mode_bar(tasks)
        elif args.mode == "pie":
            mode_pie(tasks)
        elif args.mode == "list":
            mode_list(tasks, limit=args.limit)
        elif args.mode == "timeline":
            mode_timeline(tasks)

        if args.watch:
            print(f"{GRAY}  次回更新まで {args.watch} 秒...  Ctrl+C で終了{RESET}\n")

    if args.watch > 0:
        try:
            while True:
                render()
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print(f"\n{GRAY}終了しました。{RESET}\n")
    else:
        render()


if __name__ == "__main__":
    main()
