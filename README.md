# Tasktally

Daily time tracking on top of [Taskwarrior](https://taskwarrior.org): see how much time you spent on each task, yesterday and today, with totals per tag — from an interactive terminal UI or as a plain text report.

```
 Today — Thursday 05 November    Total: 2h40 (2,7)

    ID        Time   h    Description                 Tags
 ✓  7b2b8fa3  1h30   1,5  Upgrade certifi             +aikido
 ▶  1         0h42   0,7  Fix login bug               +sentry
 ‖  2         0h28   0,5  Review onboarding flow      +product
```

## Features

- **Per-day time**: time is attributed to the day it was spent, so a task started yesterday and finished today shows up in both days with the right amounts.
- **Totals per tag**, in `1h30` and decimal hours (`1,5`) for timesheets.
- **Interactive TUI** to add, start/stop, complete, edit, tag, delete tasks and adjust time.
- **Manual time adjustments** for when you forgot to start the clock.
- Plain Taskwarrior underneath: everything stays usable with the `task` command.

## Requirements

- [Taskwarrior](https://taskwarrior.org) 3.x
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)

## Installation

```sh
brew install task uv
uv tool install git+https://github.com/JeromeM/Tasktally
echo "journal.time=on" >> ~/.taskrc
```

`journal.time=on` makes Taskwarrior record every start/stop as a timestamped annotation, which is what Tasktally uses to compute time.

To update later:

```sh
uv tool upgrade tasktally
```

## Usage

```sh
tally                       # open the interactive view
tally today                 # text report for today
tally yesterday             # text report for yesterday
tally list status:pending   # list tasks matching any Taskwarrior filter
```

A handy shell function for a daily summary:

```sh
today() {
  echo "== YESTERDAY ==";  tally yesterday
  echo "\n== TODAY ==";    tally today
  echo "\n== TO DO ==";    tally list status:pending
}
```

### Interactive view

| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | switch between the day view and the to-do list |
| `a` | add a task — `Fix login bug +sentry +urgent` |
| `s` | start / stop the selected task (starting one stops the running one) |
| `d` | mark as done |
| `o` | reopen a completed task |
| `e` | edit the description |
| `t` | add or remove time — `1h30`, `45min`, `-30min` |
| `g` | edit tags — `+infra -aikido` |
| `x` | delete (with confirmation) |
| `y` | toggle today / yesterday |
| `q` | quit |

### Tracking time

The usual flow with Taskwarrior:

```sh
task add +sentry "Fix login bug"   # create
task 5 start                       # start the clock
task 5 stop                        # pause
task 5 done                        # finish (stops the clock)
```

Forgot to start the clock? Add or remove time with an annotation, on any task, even a completed one:

```sh
task 5 annotate "Tracked 1h30"
task 5 annotate "Tracked -30min"
```

Manual time counts for the day the task was completed (or the day of the annotation if the task is still open).

### Reading the reports

| Mark | Meaning |
|---|---|
| `✓` / ✅ | completed that day |
| `▶` / ▶️ | currently running |
| `‖` / ⏸️ | worked on that day, not finished |
| `~1h20` | estimate: the task was never tracked, so its time is creation → completion |

A task with several tags counts in each of them in the per-tag totals.

## License

MIT
