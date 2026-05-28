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

        self.chat = tk.Text(self.root, height=20, wrap="word")
        self.chat.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        self.chat.configure(state="disabled")
        self._say("Agent Kal", "Hello James, I'm Agent Kal. Tell me what authorized system you want to test, and I'll choose the Kali tools, run safe checks, and explain what I find.")

        self.prompt = tk.Entry(self.root)
        self.prompt.pack(fill="x", padx=10, pady=(0, 6))
        self.prompt.insert(0, "Help me run a pentest on 127.0.0.1")
        self.prompt.bind("<Return>", lambda _event: self.run())

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=10)

        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=10, pady=8)
        tk.Button(frame, text="Send", command=self.run).pack(side="left")
        tk.Button(frame, text="Preview", command=self.show_preview).pack(side="left", padx=8)
        tk.Button(frame, text="Watch Mode", command=self.show_watch_mode).pack(side="left", padx=8)
        tk.Button(frame, text="Settings", command=self.show_settings).pack(side="left", padx=8)
        tk.Button(frame, text="Quit", command=self.root.destroy).pack(side="right")

        self.preview: tk.Toplevel | None = None
        self.preview_text: tk.Text | None = None
        self.events: list[dict[str, Any]] = []
        self.session = ChatSession()

    def run(self) -> None:
        command = self.prompt.get().strip()
        if not command:
            return
        self._say("You", command)
        self.prompt.delete(0, "end")
        threading.Thread(target=self._run_agent, daemon=True).start()

    def _run_agent(self) -> None:
        try:
            self.status.set("Running scoped AI plan...")
            scope = Scope.model_validate(json.loads(DEFAULT_SCOPE.read_text(encoding="utf-8")))
            self.events = []
            command = self._last_user_message()
            self._say("Agent Kal", self.session.reply(command))
            if not wants_tool_run(command):
                self.status.set("Ready")
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
            report = Orchestrator(scope, on_event=self._append_event, command=command).run()
            self.events = report.get("events", [])
            self._refresh_preview()
            files = write_reports(report)
            report["report_files"] = files
            append_history(report)
            self._say("Agent Kal", f"Finished. I saved the report here: {files['markdown']}")
            self.status.set(f"Done: {files['markdown']}")
        except Exception as exc:
            self.status.set("Error")
            self._say("Agent Kal", f"I need setup before I can run: {exc}")
            messagebox.showerror("Agentic Kali", str(exc))

    def _say(self, speaker: str, message: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{speaker}: {message}\n\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _last_user_message(self) -> str:
        text = self.chat.get("1.0", "end")
        messages = [line.removeprefix("You: ").strip() for line in text.splitlines() if line.startswith("You: ")]
        return messages[-1] if messages else ""

    def _append_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        self.root.after(0, self._refresh_preview)

    def show_preview(self) -> None:
        if self.preview and self.preview.winfo_exists():
            self.preview.lift()
            return

        self.preview = tk.Toplevel(self.root)
        self.preview.title("Agentic Kali Activity")
        self.preview.attributes("-topmost", True)
        self.preview.geometry("680x520+480+40")
        self.preview_text = tk.Text(self.preview, wrap="word")
        self.preview_text.pack(fill="both", expand=True, padx=8, pady=8)
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
                self.preview_text.insert("end", f"[{event['time']}] {event['event']}\n")
                self.preview_text.insert("end", json.dumps(event["data"], indent=2))
                self.preview_text.insert("end", "\n\n")
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
