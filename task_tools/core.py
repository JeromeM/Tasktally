import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

FMT = "%Y%m%dT%H%M%SZ"
MANUAL = re.compile(r"^Tracked\s+(?P<sign>-)?\s*(?:(?P<h>\d+)h)?\s*(?:(?P<m>\d+)(?:min)?)?\s*$", re.IGNORECASE)
NO_TAG = "(no tag)"


class TaskError(Exception):
    pass


@dataclass
class Row:
    uuid: str
    ident: str
    description: str
    tags: list[str]
    seconds: float
    exact: bool
    state: str
    status: str


@dataclass
class DayReport:
    start: datetime
    rows: list[Row] = field(default_factory=list)
    total: float = 0
    exact: bool = True
    tags: dict[str, tuple[float, bool]] = field(default_factory=dict)


def parse(ts):
    return datetime.strptime(ts, FMT).replace(tzinfo=timezone.utc)


def run_task(*args):
    result = subprocess.run(
        ["task", "rc.verbose=nothing", "rc.confirmation=off", "rc.bulk=0", *args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise TaskError((result.stderr or result.stdout).strip() or "task command failed")
    return result.stdout


def export(*filter_args):
    return json.loads(run_task("rc.json.array=on", *filter_args, "export") or "[]")


def parse_duration(text):
    match = MANUAL.match(f"Tracked {text.strip()}")
    if not match or not (match["h"] or match["m"]):
        return None
    seconds = int(match["h"] or 0) * 3600 + int(match["m"] or 0) * 60
    return -seconds if match["sign"] else seconds


def fmt_hm(seconds):
    sign = "-" if seconds < 0 else ""
    minutes = int(abs(seconds) // 60)
    hours, minutes = divmod(minutes, 60)
    return f"{sign}{hours}h{minutes:02d}" if hours else f"{sign}{minutes}min"


def fmt_decimal(seconds):
    return f"{seconds / 3600:.1f}".replace(".", ",")


def fmt_duration(seconds):
    return f"{fmt_hm(seconds):<5} ({fmt_decimal(seconds)})"


def ident(task):
    return str(task["id"]) if task.get("id") else task["uuid"][:8]


def time_entries(task, now):
    sessions, manual, started = [], [], None
    for ann in sorted(task.get("annotations", []), key=lambda a: a["entry"]):
        desc = ann["description"]
        if desc.startswith("Started task") and started is None:
            started = parse(ann["entry"])
        elif desc.startswith("Stopped task") and started is not None:
            sessions.append((started, parse(ann["entry"])))
            started = None
        elif match := MANUAL.match(desc):
            seconds = int(match["h"] or 0) * 3600 + int(match["m"] or 0) * 60
            if match["sign"]:
                seconds = -seconds
            manual.append((parse(task["end"]) if "end" in task else parse(ann["entry"]), seconds))
    if "start" in task:
        sessions.append((parse(task["start"]), now))
    elif started is not None and "end" in task:
        sessions.append((started, parse(task["end"])))
    return sessions, manual


def total_time(task, now):
    sessions, manual = time_entries(task, now)
    return sum((e - s).total_seconds() for s, e in sessions) + sum(sec for _, sec in manual)


def in_window(moment, window):
    return window[0] <= moment < window[1]


def day_time(task, window, now):
    sessions, manual = time_entries(task, now)
    seconds = sum(max(0, (min(e, window[1]) - max(s, window[0])).total_seconds()) for s, e in sessions)
    seconds += sum(sec for moment, sec in manual if in_window(moment, window))
    ended = "end" in task and in_window(parse(task["end"]), window)
    if sessions or manual or not ended:
        return seconds, True
    return (parse(task["end"]) - parse(task["entry"])).total_seconds(), False


def day_start(days_ago):
    midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=days_ago)


def day_report(days_ago):
    now = datetime.now(timezone.utc)
    start = day_start(days_ago)
    window = (start, start + timedelta(days=1))
    report = DayReport(start=start)
    tasks = export("(", "status:completed", "or", "status:pending", ")")
    for t in sorted(tasks, key=lambda t: t.get("end", t.get("start", t["entry"]))):
        seconds, exact = day_time(t, window, now)
        ended = "end" in t and in_window(parse(t["end"]), window)
        if not seconds and not ended:
            continue
        if ended:
            state = "done"
        elif "start" in t and days_ago == 0:
            state = "active"
        else:
            state = "paused"
        tags = t.get("tags", [])
        report.rows.append(Row(t["uuid"], ident(t), t["description"], tags, seconds, exact, state, t["status"]))
        report.total += seconds
        report.exact &= exact
        for tag in tags or [NO_TAG]:
            tag_seconds, tag_exact = report.tags.get(tag, (0, True))
            report.tags[tag] = (tag_seconds + seconds, tag_exact and exact)
    return report


def task_list(*filter_args):
    now = datetime.now(timezone.utc)
    rows = []
    for t in sorted(export(*filter_args), key=lambda t: t.get("end", t["entry"])):
        state = "active" if "start" in t else t["status"]
        rows.append(Row(t["uuid"], ident(t), t["description"], t.get("tags", []), total_time(t, now), True, state, t["status"]))
    return rows


def add(text):
    words = text.split()
    tags = [w for w in words if w.startswith("+") and len(w) > 1]
    description = " ".join(w for w in words if w not in tags)
    if not description:
        raise TaskError("Description is empty")
    out = run_task("rc.verbose=new-uuid", "add", *tags, "--", description)
    match = re.search(r"[0-9a-f]{8}-[0-9a-f-]{27}", out)
    return match.group(0) if match else None


def start(uuid):
    for active in export("+ACTIVE"):
        if active["uuid"] != uuid:
            run_task(active["uuid"], "stop")
    run_task(uuid, "start")


def stop(uuid):
    run_task(uuid, "stop")


def done(uuid):
    run_task(uuid, "done")


def reopen(uuid):
    run_task(uuid, "modify", "status:pending")


def delete(uuid):
    run_task(uuid, "delete")


def set_description(uuid, description):
    run_task(uuid, "modify", "--", description)


def modify_tags(uuid, text):
    changes = [w for w in text.split() if len(w) > 1 and w[0] in "+-"]
    if not changes:
        raise TaskError("Use +tag to add and -tag to remove")
    run_task(uuid, "modify", *changes)


def adjust_time(uuid, text):
    seconds = parse_duration(text)
    if seconds is None:
        raise TaskError("Use a duration like 1h30, 45min or -30min")
    run_task(uuid, "annotate", "--", f"Tracked {text.strip()}")
    return seconds
