"""``jv`` — служебная командная строка JARVIS (проверка политики, очередь, отчёт о расходах)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jarviscore import __version__
from jarviscore.claude_runner import spent_today
from jarviscore.planner import Scheduler
from jarviscore.policy import Policy

ROOT = Path(__file__).resolve().parents[2]


def cmd_check(args: argparse.Namespace) -> int:
    policy = Policy.load(ROOT / "config" / "allowlist.toml")
    if args.command:
        v = policy.check_command(args.command)
    elif args.path:
        v = policy.check_path(args.path)
    else:
        v = policy.check_program(args.program)
    print(f"{v.decision.value}: {v.reason or 'ok'}")
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    sched = Scheduler.load(ROOT / "data" / "tasks.json")
    if not sched.tasks:
        print("очередь пуста")
        return 0
    for t in sched.tasks.values():
        dl = t.deadline.strftime("%d.%m %H:%M") if t.deadline else "—"
        print(f"[{t.state.value:13}] p{t.priority} {t.id:14} {t.title}  дедлайн {dl}  ресурсы {','.join(t.resources) or '—'}")
    risks = sched.at_risk()
    if risks:
        print("\nПод угрозой:")
        for t, why in risks:
            print(f"  {t.id}: {why}")
    return 0


def cmd_costs(_: argparse.Namespace) -> int:
    print(f"сегодня: {spent_today(ROOT / 'data' / 'logs' / 'costs.jsonl'):.2f} $ (эквивалент API)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jv", description=f"JARVIS core {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="проверить команду/путь/программу по политике")
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--command")
    g.add_argument("--path")
    g.add_argument("--program")
    c.set_defaults(func=cmd_check)

    t = sub.add_parser("tasks", help="показать очередь задач")
    t.set_defaults(func=cmd_tasks)

    k = sub.add_parser("costs", help="расходы за сегодня")
    k.set_defaults(func=cmd_costs)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
