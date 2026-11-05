import sys

from . import core

GREY, BOLD, RESET = "\033[90m", "\033[1m", "\033[0m"
MARKS = {"done": "✅", "active": "▶️", "paused": "⏸️", "pending": "  ", "completed": "  "}


def print_rows(rows):
    id_w = max(len(r[0]) for r in rows)
    for ident, mark, duration, desc in rows:
        visible = len(duration) - (len(GREY) + len(RESET) if duration.startswith(GREY) else 0)
        print(f" {mark} {ident:>{id_w}}  {duration}{' ' * (16 - visible)}{desc}")


def report_day(days_ago):
    report = core.day_report(days_ago)
    if not report.rows:
        print(" Nothing.")
        return
    print_rows([
        (r.ident, MARKS[r.state],
         core.fmt_duration(r.seconds) if r.exact else f"{GREY}~{core.fmt_duration(r.seconds)}{RESET}",
         r.description)
        for r in report.rows
    ])
    print(f"\n {BOLD}Total: {'' if report.exact else '~'}{core.fmt_duration(report.total)}{RESET}\n")
    tag_w = max(len(tag) for tag in report.tags)
    for tag, (seconds, exact) in sorted(report.tags.items(), key=lambda g: -g[1][0]):
        print(f"   {tag:<{tag_w}}  {'' if exact else '~'}{core.fmt_duration(seconds)}")


def report_list(filter_args):
    rows = core.task_list(*filter_args)
    if not rows:
        print(" Nothing.")
        return
    formatted = []
    for r in rows:
        duration = core.fmt_duration(r.seconds) if r.seconds else f"{GREY}-{RESET}"
        tags = " ".join(f"+{tag}" for tag in r.tags)
        desc = f"{r.description}  {GREY}{tags}{RESET}" if tags else r.description
        formatted.append((r.ident, MARKS[r.state], duration, desc))
    print_rows(formatted)


def main():
    args = sys.argv[1:]
    if args[:1] == ["--day"] and len(args) == 2 and args[1] in ("today", "yesterday"):
        report_day(0 if args[1] == "today" else 1)
    else:
        report_list(args)


if __name__ == "__main__":
    main()
