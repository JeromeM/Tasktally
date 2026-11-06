import os
import re
import shutil
import sys
import datetime as dt
from importlib import metadata
from pathlib import Path
from typing import Annotated

import typer

from . import core

GREY, BOLD, RESET = "\033[90m", "\033[1m", "\033[0m"
MARKS = {"done": "✅", "active": "▶️", "paused": "⏸️", "pending": "  ", "completed": "  "}


def print_rows(rows):
    id_w = max(len(r[0]) for r in rows)
    for ident, mark, duration, desc in rows:
        visible = len(duration) - (len(GREY) + len(RESET) if duration.startswith(GREY) else 0)
        print(f" {mark} {ident:>{id_w}}  {duration}{' ' * (16 - visible)}{desc}")


def report_day(day):
    report = core.day_report(day)
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


def section(title):
    line = "=" * 42
    print(f"\n{line}\n {title}\n{line}")


def summary():
    today = dt.date.today()
    for label, day in (("📅 YESTERDAY", today - dt.timedelta(days=1)), ("📅 TODAY", today)):
        section(f"{label} — {day.strftime('%A %d %B')}")
        report_day(day)
    section("🟡 TO DO")
    report_list(["status:pending"])
    print()


def setup():
    taskrc = Path(os.environ.get("TASKRC", Path.home() / ".taskrc")).expanduser()
    if not shutil.which("task"):
        print("Taskwarrior is not installed: https://taskwarrior.org/download/")
        sys.exit(1)
    if not taskrc.exists():
        taskrc.write_text(f"data.location={Path.home() / '.task'}\njournal.time=on\n")
        print(f"Created {taskrc} with time tracking enabled")
        return
    content = taskrc.read_text()
    if re.search(r"^journal\.time=on\s*$", content, re.MULTILINE):
        print(f"Time tracking already enabled in {taskrc}")
        return
    if re.search(r"^journal\.time=", content, re.MULTILINE):
        content = re.sub(r"^journal\.time=.*$", "journal.time=on", content, flags=re.MULTILINE)
    else:
        content += ("" if content.endswith("\n") or not content else "\n") + "journal.time=on\n"
    taskrc.write_text(content)
    print(f"Enabled time tracking in {taskrc}")


app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=True,
    rich_markup_mode="rich",
)


def version_callback(value: bool):
    if value:
        print(f"tasktally {metadata.version('tasktally')}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show the version and exit.")
    ] = False,
):
    """Daily time tracking on top of Taskwarrior.

    Run [bold]tally[/bold] without a command to open the interactive view.
    """
    if ctx.invoked_subcommand is None:
        from .tui import main as tui_main

        tui_main()


@app.command()
def today():
    """Print today's report: time per task and per tag."""
    report_day(dt.date.today())


@app.command()
def yesterday():
    """Print yesterday's report: time per task and per tag."""
    report_day(dt.date.today() - dt.timedelta(days=1))


@app.command("day")
def day_command(
    date: Annotated[
        str,
        typer.Argument(
            metavar="DATE",
            show_default=False,
            help="2026-10-28, 28/10, 28/10/2025, today, yesterday, or a weekday such as monday (the last one).",
        ),
    ],
):
    """Print the report of any day."""
    day = core.parse_day(date)
    if day is None:
        raise typer.BadParameter("use YYYY-MM-DD, DD/MM, DD/MM/YYYY, today, yesterday or a weekday", param_hint="DATE")
    print(f" {BOLD}{core.day_title(day)}{RESET}\n")
    report_day(day)


@app.command("summary")
def summary_command():
    """Print yesterday, today and the to-do list."""
    summary()


@app.command(
    "list",
    options_metavar="[FILTER]...",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def list_command(ctx: typer.Context):
    """Print tasks matching a Taskwarrior filter.

    Example: [bold]tally list status:pending +sentry[/bold]
    """
    report_list(ctx.args)


@app.command("setup")
def setup_command():
    """Enable time tracking (journal.time=on) in your Taskwarrior config."""
    setup()


def main():
    app()


if __name__ == "__main__":
    main()
