from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Any

from agentic_kali.core.orchestrator import Orchestrator
from agentic_kali.core.planner import SAFE_RECON_ACTIONS
from agentic_kali.ai.commands import actions_from_command
from agentic_kali.ai.request import extract_target, summarize_request, wants_tool_run
from agentic_kali.ai.chat import ChatSession
from agentic_kali.desktop.watch import WatchMode
from agentic_kali.desktop.apps import launch_program, parse_launch_request
from agentic_kali.desktop.browser import parse_browser_request, run_browser_request
from agentic_kali.policy.models import Scope
from agentic_kali.reporting.history import append_history
from agentic_kali.setup import run_config_wizard
from agentic_kali.reporting.writer import write_reports


DEFAULT_SCOPE = Path("/etc/agentic-kali/scope.json")


class FloatingPrompt:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Agentic Kali")
        self.root.attributes("-topmost", True)
        self.root.geometry("640x520+40+40")
        self.root.resizable(True, True)

        chat_frame = tk.Frame(self.root)
        chat_frame.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        self.chat = tk.Text(chat_frame, height=20, wrap="word")
        self.chat_scroll = tk.Scrollbar(chat_frame, orient="vertical", command=self.chat.yview)
        self.chat.configure(yscrollcommand=self.chat_scroll.set)
        self.chat.pack(side="left", fill="both", expand=True)
        self.chat_scroll.pack(side="right", fill="y")
        self.chat.tag_configure("user", justify="right", lmargin1=120, lmargin2=120, rmargin=12)
        self.chat.tag_configure("agent", justify="left", lmargin1=8, lmargin2=8, rmargin=80)
        self.chat.tag_configure("code", background="#eeeeee", font=("Courier", 10), lmargin1=18, lmargin2=18, rmargin=18)
        self.chat.bind("<Key>", lambda event: "break")
        self._say(
            "Agent Kal",
            "Hello James, I'm Agent Kal. Tell me what authorized system you want to test, and I'll choose the Kali tools, run safe checks, and explain what I find.",
            animated=True,
        )

        input_frame = tk.Frame(self.root)
        input_frame.pack(fill="x", padx=10, pady=(0, 6))
        self.prompt = tk.Entry(input_frame, relief="groove", borderwidth=2)
        self.prompt.pack(side="left", fill="x", expand=True, ipady=6)
        self.prompt.bind("<Return>", lambda _event: self.run())
        self.prompt.bind("<Button-1>", lambda _event: self.prompt.focus_set())
        tk.Button(input_frame, text="Send", command=self.run).pack(side="right", padx=(8, 0))

        self.status = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=10)

        self.thinking = tk.StringVar(value="")
        self.thinking_label = tk.Label(
            self.root,
            textvariable=self.thinking,
            anchor="w",
            font=("Serif", 10, "italic"),
            fg="#555555",
        )
        self.thinking_label.pack(fill="x", padx=10)

        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=10, pady=8)
        tk.Button(frame, text="Stop", command=self.stop).pack(side="left")
        tk.Button(frame, text="Preview", command=self.show_preview).pack(side="left", padx=8)
        tk.Button(frame, text="Watch Mode", command=self.show_watch_mode).pack(side="left", padx=8)
        tk.Button(frame, text="Settings", command=self.show_settings).pack(side="left", padx=8)
        tk.Button(frame, text="Quit", command=self.root.destroy).pack(side="right")

        self.preview: tk.Toplevel | None = None
        self.preview_text: tk.Text | None = None
        self.events: list[dict[str, Any]] = []
        self.session = ChatSession()
        self.stop_requested = False
        self.type_chars_on_page = 0
        self.root.after(300, self._focus_prompt)

    def run(self) -> None:
        command = self.prompt.get().strip()
        if not command:
            return
        self._say("You", command)
        self.prompt.delete(0, "end")
        self.stop_requested = False
        threading.Thread(target=self._run_agent, daemon=True).start()

    def stop(self) -> None:
        self.stop_requested = True
        self.status.set("Stopping...")
        self._set_thinking("")

    def _run_agent(self) -> None:
        try:
            self._set_thinking("Thinking through your request...")
            scope = Scope.model_validate(json.loads(DEFAULT_SCOPE.read_text(encoding="utf-8")))
            self.events = []
            command = self._last_user_message()
            reply = self.session.reply(command)
            self._set_thinking("")
            self._say("Agent Kal", reply)
            browser_request = parse_browser_request(command)
            if browser_request:
                approved = messagebox.askyesno(
                    "Approve Browser Control",
                    f"Allow Agent Kal to perform browser action: {browser_request.action} {browser_request.value}".strip(),
                )
                if not approved:
                    self._say("Agent Kal", "Browser action cancelled.")
                    self.status.set("")
                    return
                ok, output = run_browser_request(browser_request)
                self._say("Agent Kal", output)
                self.status.set("" if ok else "Browser action failed")
                return
            launch = parse_launch_request(command)
            if launch:
                if launch.risk == "approval_required":
                    approved = messagebox.askyesno(
                        "Approve Launch",
                        f"Open {launch.display_name} ({launch.command})?\n\nThis is marked {launch.risk}.",
                    )
                    if not approved:
                        self._say("Agent Kal", "Launch cancelled.")
                        self.status.set("")
                        return
                ok, output = launch_program(launch.command, launch.args)
                self._say("Agent Kal", output)
                self.status.set("" if ok else "Launch failed")
                return
            if not wants_tool_run(command):
                self.status.set("")
                return
            target = extract_target(command)
            if target and target not in scope.targets:
                self._say(
                    "Agent Kal",
                    f"I found target {target}, but it is not in your authorized scope. Add it in Settings and confirm permission before I run tests.",
                )
                self.status.set("Needs scope update")
                return
            if target:
                scope = scope.model_copy(update={"targets": [target]})
            actions = actions_from_command(command, scope.allowed_actions)
            self._say("Agent Kal", summarize_request(command, actions, target))
            self.status.set("Running tests...")
            report = Orchestrator(
                scope,
                on_event=self._append_event,
                command=command,
                should_stop=lambda: self.stop_requested,
            ).run()
            self.events = report.get("events", [])
            self._refresh_preview()
            files = write_reports(report)
            report["report_files"] = files
            append_history(report)
            if self.stop_requested:
                self._say("Agent Kal", f"Stopped. I saved partial results here: {files['markdown']}")
                self.status.set("Stopped")
            else:
                self._say("Agent Kal", f"Finished. I saved the report here: {files['markdown']}")
                self.status.set(f"Done: {files['markdown']}")
        except Exception as exc:
            self.status.set("Error")
            self._set_thinking("")
            self._say("Agent Kal", f"I need setup before I can run: {exc}")
            messagebox.showerror("Agentic Kali", str(exc))

    def _set_thinking(self, message: str) -> None:
        self.root.after(0, lambda: self.thinking.set(message))

    def _say(self, speaker: str, message: str, animated: bool = False) -> None:
        if speaker == "Agent Kal":
            animated = True
        tag = "user" if speaker == "You" else "agent"
        self.chat.insert("end", f"{speaker}: ", tag)
        self.type_chars_on_page = 0
        if animated:
            if "```" in message:
                self._insert_message_text(message + "\n\n", tag)
                self._focus_prompt()
            else:
                self._type_text(message + "\n\n", tag=tag)
            return
        self._insert_message_text(message + "\n\n", tag)
        self.chat.see("end")

    def _type_text(self, text: str, index: int = 0, tag: str = "agent") -> None:
        if index >= len(text):
            self._focus_prompt()
            return
        chunk = text[index : index + 4]
        self.chat.insert("end", chunk, tag)
        self.type_chars_on_page += len(chunk)
        if self.type_chars_on_page >= self._chat_page_chars():
            self.chat.yview_scroll(1, "pages")
            self.type_chars_on_page = 0
        self.root.after(15, lambda: self._type_text(text, index + len(chunk), tag))

    def _insert_message_text(self, text: str, tag: str) -> None:
        for part in self._split_code_blocks(text):
            if part[0] == "code":
                self._insert_code_block(part[1])
            else:
                self.chat.insert("end", part[1], tag)

    def _split_code_blocks(self, text: str) -> list[tuple[str, str]]:
        parts: list[tuple[str, str]] = []
        while "```" in text:
            before, rest = text.split("```", 1)
            if before:
                parts.append(("text", before))
            if "```" not in rest:
                parts.append(("text", rest))
                return parts
            code, text = rest.split("```", 1)
            lines = code.splitlines()
            if lines and lines[0].strip().isalpha():
                code = "\n".join(lines[1:])
            parts.append(("code", code.strip() + "\n"))
        if text:
            parts.append(("text", text))
        return parts

    def _insert_code_block(self, code: str) -> None:
        self.chat.insert("end", "\n", "agent")
        self.chat.insert("end", code, "code")
        button = tk.Button(self.chat, text="Copy", command=lambda value=code: self.root.clipboard_clear() or self.root.clipboard_append(value))
        self.chat.window_create("end", window=button)
        self.chat.insert("end", "\n\n", "agent")

    def _chat_page_chars(self) -> int:
        try:
            width = max(40, int(self.chat.winfo_width() / 8))
            height = max(8, int(self.chat.winfo_height() / 18))
            return width * height
        except tk.TclError:
            return 900

    def _focus_prompt(self) -> None:
        try:
            self.prompt.configure(state="normal")
            self.prompt.focus_set()
            self.prompt.focus_force()
        except tk.TclError:
            pass

    def _last_user_message(self) -> str:
        text = self.chat.get("1.0", "end")
        messages = [line.removeprefix("You: ").strip() for line in text.splitlines() if line.startswith("You: ")]
        return messages[-1] if messages else ""

    def _append_event(self, event: dict[str, Any]) -> None:
        self.root.after(0, lambda: self._record_event(event))

    def _record_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        self._append_preview_event(event)

    def show_preview(self) -> None:
        if self.preview and self.preview.winfo_exists():
            self.preview.lift()
            return

        self.preview = tk.Toplevel(self.root)
        self.preview.title("Agentic Kali Activity")
        self.preview.attributes("-topmost", True)
        self.preview.geometry("680x520+480+40")
        frame = tk.Frame(self.preview)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        self.preview_text = tk.Text(frame, wrap="word")
        preview_scroll = tk.Scrollbar(frame, orient="vertical", command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        self.preview_text.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not self.preview_text:
            return
        try:
            if self.preview and not self.preview.winfo_exists():
                self.preview = None
                self.preview_text = None
                return
            self.preview_text.delete("1.0", "end")
            if not self.events:
                self.preview_text.insert("end", "No activity yet.\n")
                return
            for event in self.events:
                self._append_preview_event(event, scroll=False)
            self.preview_text.see("end")
        except tk.TclError:
            self.preview = None
            self.preview_text = None

    def _append_preview_event(self, event: dict[str, Any], scroll: bool = True) -> None:
        if not self.preview_text:
            return
        try:
            self.preview_text.insert("end", f"[{event['time']}] {event['event']}\n")
            self.preview_text.insert("end", json.dumps(event["data"], indent=2))
            self.preview_text.insert("end", "\n\n")
            if scroll:
                self.preview_text.see("end")
        except tk.TclError:
            self.preview = None
            self.preview_text = None

    def show_settings(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Agentic Kali Settings")
        window.attributes("-topmost", True)
        window.geometry("520x560+480+80")

        fields = {
            "Engagement": tk.Entry(window),
            "Targets": tk.Entry(window),
            "Actions": tk.Entry(window),
            "Approval": tk.Entry(window),
            "Permission": tk.Entry(window),
            "Public Targets": tk.Entry(window),
        }
        defaults = {
            "Engagement": "local-lab",
            "Targets": "127.0.0.1",
            "Actions": ",".join(SAFE_RECON_ACTIONS),
            "Approval": "recon_only",
            "Permission": "AUTHORIZED",
            "Public Targets": "false",
        }

        existing = self._load_scope_or_none()
        if existing:
            defaults.update(
                {
                    "Engagement": existing.engagement_name,
                    "Targets": ",".join(existing.targets),
                    "Actions": ",".join(existing.allowed_actions),
                    "Approval": existing.approval_mode,
                    "Permission": "AUTHORIZED" if existing.signed_permission else "",
                    "Public Targets": str(existing.public_targets_allowed).lower(),
                }
            )

        for label, entry in fields.items():
            tk.Label(window, text=label, anchor="w").pack(fill="x", padx=10, pady=(8, 0))
            entry.insert(0, defaults[label])
            entry.pack(fill="x", padx=10)

        tk.Button(window, text="Save Scope", command=lambda: self._save_scope(fields)).pack(fill="x", padx=10, pady=12)
        tk.Button(window, text="Azure Config Wizard", command=lambda: run_config_wizard()).pack(fill="x", padx=10)

    def show_watch_mode(self) -> None:
        try:
            scope = self._load_scope_or_none()
            if not scope:
                messagebox.showinfo("Agentic Kali", "Create scope in Settings first.")
                return
            command = self.prompt.get().strip() or self._last_user_message() or "authorized recon"
            watch = WatchMode(scope)
            plan = "\n".join(f"- {step}" for step in watch.dry_plan(command))
            status = "ready" if watch.can_run() else "missing permission or xdotool/wmctrl"
            messagebox.showinfo("Watch Mode", f"Status: {status}\n\nPlan:\n{plan}")
        except Exception as exc:
            messagebox.showerror("Watch Mode", str(exc))

    def _save_scope(self, fields: dict[str, tk.Entry]) -> None:
        scope = Scope(
            engagement_name=fields["Engagement"].get(),
            targets=[item.strip() for item in fields["Targets"].get().split(",") if item.strip()],
            allowed_actions=[item.strip() for item in fields["Actions"].get().split(",") if item.strip()],
            approval_mode=fields["Approval"].get(),
            intrusive_allowed=False,
            signed_permission=fields["Permission"].get() == "AUTHORIZED",
            public_targets_allowed=fields["Public Targets"].get().lower() == "true",
        )
        DEFAULT_SCOPE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_SCOPE.write_text(json.dumps(scope.model_dump(mode="json"), indent=2), encoding="utf-8")
        messagebox.showinfo("Agentic Kali", f"Saved {DEFAULT_SCOPE}")

    def _load_scope_or_none(self) -> Scope | None:
        if not DEFAULT_SCOPE.exists():
            return None
        return Scope.model_validate(json.loads(DEFAULT_SCOPE.read_text(encoding="utf-8")))

    def start(self) -> None:
        self.root.mainloop()


def main() -> None:
    FloatingPrompt().start()


if __name__ == "__main__":
    main()
