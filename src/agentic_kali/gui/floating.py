from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Any

from agentic_kali.core.orchestrator import Orchestrator
from agentic_kali.core.planner import SAFE_RECON_ACTIONS
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
        self.root.geometry("420x220+40+40")
        self.root.resizable(True, False)

        self.prompt = tk.Text(self.root, height=4)
        self.prompt.pack(fill="x", padx=10, pady=(10, 6))
        self.prompt.insert("1.0", "Run authorized recon")

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=10)

        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=10, pady=8)
        tk.Button(frame, text="Run", command=self.run).pack(side="left")
        tk.Button(frame, text="Preview", command=self.show_preview).pack(side="left", padx=8)
        tk.Button(frame, text="Settings", command=self.show_settings).pack(side="left", padx=8)
        tk.Button(frame, text="Quit", command=self.root.destroy).pack(side="right")

        self.preview: tk.Toplevel | None = None
        self.preview_text: tk.Text | None = None
        self.events: list[dict[str, Any]] = []

    def run(self) -> None:
        threading.Thread(target=self._run_agent, daemon=True).start()

    def _run_agent(self) -> None:
        try:
            self.status.set("Running scoped AI plan...")
            scope = Scope.model_validate(json.loads(DEFAULT_SCOPE.read_text(encoding="utf-8")))
            self.events = []
            command = self.prompt.get("1.0", "end").strip()
            report = Orchestrator(scope, on_event=self._append_event, command=command).run()
            self.events = report.get("events", [])
            self._refresh_preview()
            files = write_reports(report)
            report["report_files"] = files
            append_history(report)
            self.status.set(f"Done: {files['markdown']}")
        except Exception as exc:
            self.status.set("Error")
            messagebox.showerror("Agentic Kali", str(exc))

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
        self.preview_text.delete("1.0", "end")
        if not self.events:
            self.preview_text.insert("end", "No activity yet.\n")
            return
        for event in self.events:
            self.preview_text.insert("end", f"[{event['time']}] {event['event']}\n")
            self.preview_text.insert("end", json.dumps(event["data"], indent=2))
            self.preview_text.insert("end", "\n\n")

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
