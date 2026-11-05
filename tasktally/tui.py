from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from . import core

STATE_ICONS = {
    "done": Text("✓", style="bold green"),
    "active": Text("▶", style="bold cyan"),
    "paused": Text("‖", style="yellow"),
    "pending": Text(" "),
}


def duration_cells(seconds, exact=True, empty="-"):
    if not seconds and exact:
        return Text(empty, style="dim"), Text("", style="dim")
    style = "" if exact else "dim italic"
    prefix = "" if exact else "~"
    return Text(prefix + core.fmt_hm(seconds), style=style), Text(core.fmt_decimal(seconds), style=style)


def tags_cell(tags):
    return Text(" ".join(f"+{tag}" for tag in tags), style="magenta")


COLUMNS = {
    "day": ("", "ID", "Time", "h", "Description", "Tags"),
    "tags": ("Tag", "Time", "h"),
    "todo": ("", "ID", "Spent", "h", "Description", "Tags"),
}
MAX_WIDTH = {"Tags": 16}


class PromptScreen(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title, placeholder="", value=""):
        super().__init__()
        self.prompt_title, self.placeholder, self.value = title, placeholder, value

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.prompt_title, classes="dialog-title")
            yield Input(value=self.value, placeholder=self.placeholder)
            yield Label("Enter to confirm · Esc to cancel", classes="dialog-hint")

    @on(Input.Submitted)
    def submit(self, event: Input.Submitted):
        self.dismiss(event.value.strip() or None)

    def action_cancel(self):
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape,n", "cancel", "No"), Binding("y", "confirm", "Yes")]

    def __init__(self, message):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.message, classes="dialog-title")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Yes (y)", variant="error", id="yes")
                yield Button("No (n)", id="no")

    @on(Button.Pressed)
    def pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "yes")

    def action_confirm(self):
        self.dismiss(True)

    def action_cancel(self):
        self.dismiss(False)


class TaskApp(App):
    TITLE = "Tasktally"
    CSS = """
    #day-title, .pane-title { padding: 0 1; background: $boost; text-style: bold; color: $accent; }
    #day { height: auto; min-height: 3; max-height: 50%; margin-bottom: 1; }
    #bottom { height: 1fr; border-top: solid $primary; padding-top: 1; }
    #tags-pane { width: 34; }
    #todo-pane { width: 1fr; }
    DataTable { height: 1fr; scrollbar-size-vertical: 1; }
    PromptScreen, ConfirmScreen { align: center middle; }
    .dialog { width: 70; height: auto; padding: 1 2; border: thick $accent; background: $surface; }
    .dialog-title { text-style: bold; margin-bottom: 1; }
    .dialog-hint { color: $text-muted; margin-top: 1; }
    .dialog-buttons { height: auto; align-horizontal: center; }
    .dialog-buttons Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("a", "add", "Add"),
        Binding("s", "toggle_start", "Start/Stop"),
        Binding("d", "done", "Done"),
        Binding("o", "reopen", "Reopen", show=False),
        Binding("e", "edit", "Edit"),
        Binding("t", "time", "± Time"),
        Binding("g", "tags", "Tags"),
        Binding("x", "delete", "Delete"),
        Binding("y", "toggle_day", "Today/Yesterday"),
        Binding("tab", "app.focus_next", "Switch zone"),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.days_ago = 0
        self.last_table = "day"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(id="day-title")
        yield DataTable(id="day", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="bottom"):
            with Vertical(id="tags-pane"):
                yield Static("By tag", classes="pane-title")
                tags = DataTable(id="tags", cursor_type="none")
                tags.can_focus = False
                yield tags
            with Vertical(id="todo-pane"):
                yield Static("To do", classes="pane-title")
                yield DataTable(id="todo", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self):
        self.call_after_refresh(self.reload)
        self.set_interval(20, self.reload)

    def on_resize(self):
        self.set_timer(0.05, self.reload)

    def on_descendant_focus(self, event):
        if event.widget.id in ("day", "todo"):
            self.last_table = event.widget.id

    def selected_uuid(self, table_id=None):
        table = self.query_one(f"#{table_id or self.last_table}", DataTable)
        if not table.row_count:
            return None
        return table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0)).row_key.value

    def fill(self, table_id, rows):
        table = self.query_one(f"#{table_id}", DataTable)
        keep = self.selected_uuid(table_id) if table.columns else None
        headers = COLUMNS[table_id]
        widths = [
            min(MAX_WIDTH.get(label, 999), max([len(label)] + [Text(c).cell_len if isinstance(c, str) else c.cell_len for c in (r[1][i] for r in rows)]))
            for i, label in enumerate(headers)
        ]
        if "Description" in headers:
            flex = headers.index("Description")
            fixed = sum(w for i, w in enumerate(widths) if i != flex)
            widths[flex] = max(20, table.size.width - fixed - 2 * table.cell_padding * len(headers) - 1)
        table.clear(columns=True)
        for label, width in zip(headers, widths):
            table.add_column(label, width=width)
        for key, cells in rows:
            table.add_row(*(Text(c) if isinstance(c, str) else c for c in cells), key=key, height=None)
        if keep:
            try:
                table.move_cursor(row=table.get_row_index(keep))
            except Exception:
                pass

    def reload(self):
        try:
            report = core.day_report(self.days_ago)
            todo = core.task_list("status:pending")
        except core.TaskError as err:
            self.notify(str(err), severity="error")
            return

        label = "Today" if self.days_ago == 0 else "Yesterday"
        total = ("" if report.exact else "~") + core.fmt_duration(report.total)
        self.query_one("#day-title", Static).update(
            f"{label} — {report.start.strftime('%A %d %B')}    Total: {total}    [dim](y to switch)[/dim]"
        )
        self.fill("day", [
            (r.uuid, (STATE_ICONS[r.state], r.ident, *duration_cells(r.seconds, r.exact, "0min"),
                      r.description, tags_cell(r.tags)))
            for r in report.rows
        ])
        self.fill("tags", [
            (tag, (Text(tag, style="magenta"), *duration_cells(seconds, exact)))
            for tag, (seconds, exact) in sorted(report.tags.items(), key=lambda g: -g[1][0])
        ])
        self.fill("todo", [
            (r.uuid, (STATE_ICONS["active" if r.state == "active" else "pending"], r.ident,
                      *duration_cells(r.seconds), r.description, tags_cell(r.tags)))
            for r in todo
        ])
        active = [r for r in todo if r.state == "active"]
        self.sub_title = f"▶ {active[0].description} — {core.fmt_hm(active[0].seconds)}" if active else "Nothing running"

    def do_task(self, func, *args, success=None):
        try:
            result = func(*args)
        except core.TaskError as err:
            self.notify(str(err), severity="error")
            return None
        if success:
            self.notify(success)
        self.reload()
        return result

    def current_task(self):
        uuid = self.selected_uuid()
        if not uuid:
            self.notify("No task selected", severity="warning")
            return None
        return next((t for t in core.export(uuid)), None)

    def action_add(self):
        def created(text):
            if text:
                self.do_task(core.add, text, success="Task added")

        self.push_screen(PromptScreen("New task", "Description +tag1 +tag2"), created)

    def action_toggle_start(self):
        task = self.current_task()
        if not task:
            return
        if task["status"] != "pending":
            self.notify("Task is completed — reopen it with o", severity="warning")
        elif "start" in task:
            self.do_task(core.stop, task["uuid"], success="Stopped")
        else:
            self.do_task(core.start, task["uuid"], success=f"Started: {task['description']}")

    def action_done(self):
        task = self.current_task()
        if task and task["status"] == "pending":
            self.do_task(core.done, task["uuid"], success=f"Done: {task['description']}")

    def action_reopen(self):
        task = self.current_task()
        if task and task["status"] == "completed":
            self.do_task(core.reopen, task["uuid"], success="Reopened")

    def action_edit(self):
        task = self.current_task()
        if not task:
            return

        def edited(text):
            if text and text != task["description"]:
                self.do_task(core.set_description, task["uuid"], text, success="Description updated")

        self.push_screen(PromptScreen("Edit description", value=task["description"]), edited)

    def action_time(self):
        task = self.current_task()
        if not task:
            return

        def adjusted(text):
            if text:
                self.do_task(core.adjust_time, task["uuid"], text, success=f"Time adjusted: {text}")

        self.push_screen(PromptScreen(f"Add or remove time — {task['description']}", "1h30, 45min, -30min"), adjusted)

    def action_tags(self):
        task = self.current_task()
        if not task:
            return
        current = " ".join(f"+{tag}" for tag in task.get("tags", [])) or "none"

        def tagged(text):
            if text:
                self.do_task(core.modify_tags, task["uuid"], text, success="Tags updated")

        self.push_screen(PromptScreen(f"Tags (current: {current})", "+add -remove"), tagged)

    def action_delete(self):
        task = self.current_task()
        if not task:
            return

        def confirmed(ok):
            if ok:
                self.do_task(core.delete, task["uuid"], success="Task deleted")

        self.push_screen(ConfirmScreen(f"Delete “{task['description']}”?"), confirmed)

    def action_toggle_day(self):
        self.days_ago = 1 - self.days_ago
        self.reload()

    def action_refresh(self):
        self.reload()


def main():
    TaskApp().run()


if __name__ == "__main__":
    main()
