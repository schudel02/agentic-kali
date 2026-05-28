from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import tkinter as tk
from datetime import UTC, datetime
from pathlib import Path
from tkinter import messagebox
from typing import Any

from agentic_kali.core.orchestrator import Orchestrator
from agentic_kali.core.planner import SAFE_RECON_ACTIONS
from agentic_kali.ai.commands import actions_from_command
from agentic_kali.ai.request import extract_target, summarize_request, wants_tool_run, wants_tool_run_intent
from agentic_kali.ai.chat import ChatSession
from agentic_kali.desktop.watch import WatchMode
from agentic_kali.desktop.apps import LaunchRequest, launch_program, parse_launch_request
from agentic_kali.desktop.browser import parse_browser_request, run_browser_request
from agentic_kali.desktop.builder import build_custom_tool, is_safe_build_request, parse_build_request
from agentic_kali.desktop.lab import LabServer, parse_lab_request, start_lab_server
from agentic_kali.policy.models import Scope
from agentic_kali.policy.models import ApprovalMode
from agentic_kali.policy.admin import is_admin_phrase
from agentic_kali.reporting.history import append_history
from agentic_kali.setup import run_config_wizard
from agentic_kali.reporting.writer import write_reports


DEFAULT_SCOPE = Path("/etc/agentic-kali/scope.json")
REPORTS_DIR = Path("reports")
COMMAND_PREFIXES = ("sudo", "cd", "git", "bash", "python", "python3", "pip", "pip3", "nmap", "curl", "wget", "apt", "systemctl")


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
        self.chat.tag_configure("user_label", justify="right", font=("TkDefaultFont", 10, "bold"))
        self.chat.tag_configure("agent_label", justify="left", font=("TkDefaultFont", 10, "bold"), foreground="#174ea6")
        self.chat.tag_configure("activity_note", justify="left", font=("TkDefaultFont", 9, "italic"), foreground="#555555", lmargin1=18, lmargin2=18, rmargin=80)
        self.chat.tag_configure("code", background="#eeeeee", font=("Courier", 10), lmargin1=18, lmargin2=18, rmargin=18)
        self.chat.tag_configure("code_prefix", background="#eeeeee", foreground="#174ea6", font=("Courier", 10, "bold"))
        self.chat.bind("<Key>", self._chat_keypress)
        self.chat.bind("<Control-c>", self._copy_selection)
        self.chat.bind("<Button-3>", self._show_chat_menu)
        self.chat_menu = tk.Menu(self.root, tearoff=0)
        self.chat_menu.add_command(label="Copy", command=self._copy_selection)
        self.chat_menu.add_command(label="Select All", command=self._select_all_chat)
        self.admin_mode = False
        self.speaking = False
        self.say_queue: list[tuple[str, str, str, str, bool]] = []
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
        self.prompt.bind("<Control-v>", self._paste_prompt)
        self.prompt.bind("<Control-V>", self._paste_prompt)
        self.prompt.bind("<Button-2>", self._paste_prompt)
        self.prompt.bind("<Button-3>", self._show_prompt_menu)
        self.prompt_menu = tk.Menu(self.root, tearoff=0)
        self.prompt_menu.add_command(label="Paste", command=self._paste_prompt)
        self.prompt_menu.add_command(label="Copy", command=self._copy_prompt_selection)
        self.prompt_menu.add_command(label="Select All", command=self._select_all_prompt)
        tk.Button(input_frame, text="Send", command=self.run).pack(side="right", padx=(8, 0))

        self.status = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=10)
        self.mode = tk.StringVar(value="Chat Prompt")
        tk.Label(self.root, textvariable=self.mode, anchor="w", font=("TkDefaultFont", 9, "bold"), fg="#174ea6").pack(fill="x", padx=10)

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
        tk.Button(frame, text="Reports", command=self.open_reports).pack(side="left", padx=8)
        tk.Button(frame, text="Watch Mode", command=self.show_watch_mode).pack(side="left", padx=8)
        tk.Button(frame, text="Settings", command=self.show_settings).pack(side="left", padx=8)
        tk.Button(frame, text="Quit", command=self.root.destroy).pack(side="right")

        self.preview: tk.Toplevel | None = None
        self.preview_text: tk.Text | None = None
        self.events: list[dict[str, Any]] = []
        self.session = ChatSession()
        self.stop_requested = False
        self.type_chars_on_page = 0
        self.pending_launch: LaunchRequest | None = None
        self.last_target: str | None = None
        self.lab_servers: list[LabServer] = []
        self.countdown_after: str | None = None
        self.countdown_remaining = 0
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
            consent_scope = self._scope_from_consent(command, scope)
            if consent_scope:
                scope = consent_scope
                self._say("Agent Kal", f"Consent saved for {', '.join(scope.targets)}. Admin Mode can now run scoped safe actions without extra approval prompts.")
                if not wants_tool_run(command):
                    self._set_thinking("")
                    self.status.set("Scope saved")
                    return
            if is_admin_phrase(command):
                self.admin_mode = True
                self._set_thinking("")
                self._say("Agent Kal", "Admin Approved Mode enabled for this session. I will still stay inside scope and log every action.")
                self.status.set("Admin Approved Mode")
                return
            lab_request = parse_lab_request(command)
            if lab_request:
                self._set_thinking("")
                self._handle_lab_request(scope, lab_request)
                return
            build_request = parse_build_request(command)
            if build_request:
                self._set_thinking("")
                self._handle_build_request(build_request)
                return
            target = extract_target(command) or self.last_target
            if target and self._wants_run(command, target):
                self.last_target = target
                self._set_thinking("")
                scope = self._ensure_consent(scope, target)
                if not scope:
                    self._say("Agent Kal", "I paused the test because written consent was not confirmed.")
                    self.status.set("Consent required")
                    return
                self._run_scoped_tests(command, scope, target)
                return
            launch = parse_launch_request(command) or self._continued_launch(command)
            if launch:
                self._set_thinking("")
                if launch.requires_tools_open and "tools:open" not in scope.allowed_actions:
                    scope = self._ensure_tools_open(scope, launch.command)
                    if not scope:
                        self.status.set("tools:open required")
                        return
                self._gui_event("gui.launch.requested", {"tool": launch.command, "display_name": launch.display_name})
                self._handle_launch(launch)
                return
            browser_request = parse_browser_request(command)
            if browser_request:
                self._set_thinking("")
                self._remember_target(command)
                self._gui_event("gui.browser.requested", {"action": browser_request.action, "value": browser_request.value})
                self._handle_browser(browser_request)
                return
            wants_run = self._wants_run(command, target)
            if not wants_run:
                reply = self.session.reply(command)
                self._set_thinking("")
                self._say("Agent Kal", reply)
                self.status.set("")
                return
            self._set_thinking("")
            if target:
                self.last_target = target
            scope = self._ensure_consent(scope, target)
            if not scope:
                self._say("Agent Kal", "I paused the test because written consent was not confirmed.")
                self.status.set("Consent required")
                return
            self._run_scoped_tests(command, scope, target)
        except Exception as exc:
            self._exit_run_mode()
            self.status.set("Error")
            self._set_thinking("")
            self._say("Agent Kal", f"I need setup before I can run: {exc}")
            messagebox.showerror("Agentic Kali", str(exc))

    def _run_scoped_tests(self, command: str, scope: Scope, target: str | None) -> None:
        actions = actions_from_command(command, scope.allowed_actions)
        self._say("Agent Kal", summarize_request(command, actions, target))
        self._note(self._run_description(actions, target or ", ".join(scope.targets)))
        self._gui_event("run.preparing", {"target": target or scope.targets, "actions": actions})
        self._enter_run_mode(actions)
        report = Orchestrator(
            scope,
            on_event=self._append_event,
            command=command,
            should_stop=lambda: self.stop_requested,
            admin_mode=self.admin_mode,
        ).run()
        self.events = report.get("events", [])
        self._refresh_preview()
        files = write_reports(report)
        report["report_files"] = files
        append_history(report)
        if self.stop_requested:
            self._say("Agent Kal", self._summarize_results(report, files, stopped=True))
            self.status.set("Stopped")
        else:
            self._say("Agent Kal", self._summarize_results(report, files))
            self.status.set(f"Done: {files['markdown']}")
        self._exit_run_mode()

    def _continued_launch(self, command: str) -> LaunchRequest | None:
        if not self.pending_launch:
            return None
        if command.lower().strip() in {"yes", "y", "do it", "just open", "just open it", "open it"}:
            return self.pending_launch
        return None

    def _summarize_results(self, report: dict, files: dict[str, str], stopped: bool = False) -> str:
        findings = report.get("findings", [])
        if not findings:
            intro = "Stopped. " if stopped else "Finished. "
            return (
                f"{intro}I did not find reportable issues in the completed checks.\n"
                "Next steps:\n"
                "- Confirm the target and scope are correct.\n"
                "- Try Web Fingerprint or Safe Vulnerability Check if you only ran quick recon.\n"
                "- Review the report for raw tool output.\n\n"
                f"Report saved here: {files['markdown']}"
            )

        counts: dict[str, int] = {}
        for finding in findings:
            severity = finding.get("severity", "info")
            counts[severity] = counts.get(severity, 0) + 1
        severity_text = ", ".join(f"{level}: {count}" for level, count in sorted(counts.items()))
        top = findings[:3]
        lines = ["Stopped with partial results." if stopped else "Finished. Here is what I found:", f"Findings by severity: {severity_text}"]
        lines.append("Key findings:")
        for finding in top:
            title = finding.get("title", "Finding")
            target = finding.get("target", "target")
            severity = finding.get("severity", "info")
            metadata = finding.get("metadata", {})
            detail = self._finding_detail(metadata) or "See report evidence for tool output."
            lines.append(f"- {title} on {target} ({severity}): {detail}")
        lines.extend(
            [
                "Recommended next steps:",
                "- Prioritize any medium/high findings first.",
                "- Patch or harden exposed services, then rerun the same test.",
                "- If this was recon only, follow with Safe Vulnerability Check inside the same scope.",
                "- For domain mapping, you can next ask for: web fingerprinting, subdomain discovery, content discovery, HTTP probing, or safe vulnerability checks.",
                f"Report saved here: {files['markdown']}",
            ]
        )
        return "\n".join(lines)

    def _finding_detail(self, metadata: dict) -> str:
        ports = metadata.get("open_ports") if isinstance(metadata, dict) else None
        if ports:
            open_ports = [str(item.get("port")) for item in ports if item.get("state") == "open"]
            if open_ports:
                return f"Open ports found: {', '.join(open_ports)}."
        if isinstance(metadata, dict) and metadata:
            return "Structured metadata was captured for review."
        return ""

    def _handle_launch(self, launch: LaunchRequest) -> None:
        self.pending_launch = launch
        if launch.risk == "approval_required":
            if self.admin_mode:
                self._say("Agent Kal", f"Admin Approved Mode: launching {launch.display_name}.")
                if launch.privileged:
                    self._say("Agent Kal", "Kali may ask for your password in a system prompt.")
                ok, output = launch_program(launch.command, launch.args, launch.privileged, launch.terminal)
                self._gui_event("gui.launch.completed", {"tool": launch.command, "ok": ok, "message": output})
                self.pending_launch = None if ok else launch
                self._say("Agent Kal", output)
                self.status.set("" if ok else "Launch failed")
                return
            approved = messagebox.askyesno(
                "Approve Launch",
                f"Open {launch.display_name} ({launch.command})?\n\nThis is marked {launch.risk}."
                + ("\nKali may ask for your password in a system prompt." if launch.privileged else ""),
            )
            if not approved:
                self._say("Agent Kal", "Launch cancelled.")
                self.status.set("")
                return
        ok, output = launch_program(launch.command, launch.args, launch.privileged, launch.terminal)
        self._gui_event("gui.launch.completed", {"tool": launch.command, "ok": ok, "message": output})
        self.pending_launch = None if ok else launch
        self._say("Agent Kal", output)
        self.status.set("" if ok else "Launch failed")

    def _ensure_tools_open(self, scope: Scope, tool: str) -> Scope | None:
        if "tools:open" in scope.allowed_actions:
            return scope
        if not self._ask_tools_open(tool):
            return None
        updated = scope.model_copy(update={"allowed_actions": list(dict.fromkeys([*scope.allowed_actions, "tools:open"]))})
        self._write_scope(updated)
        self._say("Agent Kal", "`tools:open` saved to scope. I will remember this for future Kali tool launches.")
        return updated

    def _ask_tools_open(self, tool: str) -> bool:
        result: dict[str, bool] = {"approved": False}
        done = threading.Event()

        def ask() -> None:
            result["approved"] = messagebox.askyesno(
                "Enable tools:open",
                f"{tool} is outside the built-in launcher list.\n\nEnable tools:open for this scope so Agent Kal can open installed Kali tools when requested?",
            )
            done.set()

        self.root.after(0, ask)
        done.wait()
        return result["approved"]

    def _handle_lab_request(self, scope: Scope, lab_request) -> None:
        try:
            server = start_lab_server(lab_request)
        except Exception as exc:
            self._say("Agent Kal", f"I could not start the local lab server: {exc}")
            self.status.set("Lab start failed")
            return
        self.lab_servers.append(server)
        self.last_target = server.url
        updated = scope.model_copy(
            update={
                "targets": list(dict.fromkeys([*scope.targets, server.url])),
                "allowed_actions": list(dict.fromkeys([*scope.allowed_actions, *SAFE_RECON_ACTIONS])),
                "approval_mode": ApprovalMode.RECON_ONLY,
                "signed_permission": True,
            }
        )
        self._write_scope(updated)
        self._gui_event("lab.started", {"url": server.url, "path": str(server.path)})
        self._say(
            "Agent Kal",
            "Local test server started.\n"
            f"- URL: {server.url}\n"
            f"- Files: {server.path}\n"
            "- Scope was updated automatically because this is a local lab target.\n\n"
            "You can now say `run vulnerability test` or `run quick recon` and I will use this local server.",
        )
        self.status.set(f"Local lab running: {server.url}")

    def _handle_build_request(self, build_request) -> None:
        if not is_safe_build_request(build_request):
            self._say("Agent Kal", "I can build safe authorized-testing helpers, but I cannot create tools for phishing, credential theft, malware, persistence, exfiltration, or destructive activity.")
            self.status.set("Build blocked")
            return
        tool = build_custom_tool(build_request)
        self._gui_event("custom_tool.built", {"name": tool.name, "path": str(tool.path), "command": tool.command})
        self._say(
            "Agent Kal",
            "I built a safe local testing helper.\n"
            f"- Name: {tool.name}\n"
            f"- Folder: {tool.path}\n"
            f"- Run it with:\n```bash\n{tool.command} example.com --dns --http\n```\n"
            "Tell me the authorized target and I can help run it in a terminal.",
        )
        self.status.set(f"Built custom tool: {tool.name}")

    def _handle_browser(self, browser_request) -> None:
        if not self.admin_mode:
            approved = messagebox.askyesno(
                "Approve Browser Control",
                f"Allow Agent Kal to perform browser action: {browser_request.action} {browser_request.value}".strip(),
            )
            if not approved:
                self._say("Agent Kal", "Browser action cancelled.")
                self.status.set("")
                return
        else:
            self._say("Agent Kal", f"Admin Approved Mode: browser action {browser_request.action}.")
        ok, output = run_browser_request(browser_request)
        self._gui_event("gui.browser.completed", {"action": browser_request.action, "ok": ok, "message": output})
        self._say("Agent Kal", output)
        self.status.set("" if ok else "Browser action failed")

    def _remember_target(self, command: str) -> None:
        target = extract_target(command)
        if target:
            self.last_target = target

    def _wants_run(self, command: str, target: str | None) -> bool:
        return wants_tool_run(command) or (target is not None and wants_tool_run_intent(command))

    def _run_description(self, actions: list[str], target: str) -> str:
        if "nmap_top_ports" in actions:
            return f"Opening nmap and running safe service discovery on {target}."
        if "whatweb" in actions:
            return f"Opening WhatWeb and fingerprinting web technologies on {target}."
        if "httpx_probe" in actions:
            return f"Opening httpx and checking web response details on {target}."
        if "nuclei_safe" in actions:
            return f"Opening nuclei and running low-risk checks on {target}."
        return f"Preparing scoped safe checks for {target}."

    def _enter_run_mode(self, actions: list[str]) -> None:
        seconds = self._estimate_seconds(actions)
        self.root.after(0, lambda: self._start_run_mode(seconds))

    def _start_run_mode(self, seconds: int) -> None:
        self.mode.set("Run Test Mode")
        self.root.title("Agentic Kali - Run Test Mode")
        self.show_preview(attached=True)
        self._start_countdown(seconds)

    def _exit_run_mode(self) -> None:
        self.root.after(0, self._stop_run_mode)

    def _stop_run_mode(self) -> None:
        if self.countdown_after:
            self.root.after_cancel(self.countdown_after)
            self.countdown_after = None
        self.mode.set("Chat Prompt")
        self.root.title("Agentic Kali")

    def _estimate_seconds(self, actions: list[str]) -> int:
        estimates = {
            "ping_check": 5,
            "nmap_top_ports": 180,
            "whatweb": 45,
            "httpx_probe": 45,
            "nuclei_safe": 240,
        }
        return max(30, sum(estimates.get(action, 60) for action in actions))

    def _start_countdown(self, seconds: int) -> None:
        self.countdown_remaining = seconds
        self._tick_countdown()

    def _tick_countdown(self) -> None:
        mins, secs = divmod(max(0, self.countdown_remaining), 60)
        self.status.set(f"Running tests... estimated time left {mins:02d}:{secs:02d}")
        if self.countdown_remaining <= 0:
            self.status.set("Running tests... finishing up")
            self.countdown_after = None
            return
        self.countdown_remaining -= 1
        self.countdown_after = self.root.after(1000, self._tick_countdown)

    def _scope_from_consent(self, command: str, existing: Scope) -> Scope | None:
        lower = command.lower()
        if "authorize" not in lower and "authorized" not in lower:
            return None
        target = extract_target(command)
        if not target:
            return None
        targets = list(dict.fromkeys([*existing.targets, target]))
        scope = existing.model_copy(
            update={
                "targets": targets,
                "allowed_actions": list(dict.fromkeys([*existing.allowed_actions, *SAFE_RECON_ACTIONS])),
                "approval_mode": ApprovalMode.RECON_ONLY,
                "intrusive_allowed": True,
                "signed_permission": True,
            }
        )
        DEFAULT_SCOPE.parent.mkdir(parents=True, exist_ok=True)
        self._write_scope(scope)
        return scope

    def _ensure_consent(self, scope: Scope, target: str | None) -> Scope | None:
        requested_targets = [target] if target else scope.targets
        needs_consent = not scope.signed_permission or any(item not in scope.targets for item in requested_targets)
        if not needs_consent:
            return scope.model_copy(update={"targets": requested_targets or scope.targets}) if target else scope

        target_text = ", ".join(requested_targets)
        if not self._ask_written_consent(target_text):
            return None
        updated = scope.model_copy(
            update={
                "targets": list(dict.fromkeys([*scope.targets, *requested_targets])),
                "allowed_actions": list(dict.fromkeys([*scope.allowed_actions, *SAFE_RECON_ACTIONS])),
                "approval_mode": ApprovalMode.RECON_ONLY,
                "intrusive_allowed": True,
                "signed_permission": True,
                "public_targets_allowed": True,
            }
        )
        self._write_scope(updated)
        self._say("Agent Kal", f"Consent confirmed and saved for {target_text}.")
        return updated.model_copy(update={"targets": requested_targets}) if target else updated

    def _ask_written_consent(self, target_text: str) -> bool:
        result: dict[str, bool] = {"approved": False}
        done = threading.Event()

        def ask() -> None:
            window = tk.Toplevel(self.root)
            window.title("Written Consent Required")
            window.attributes("-topmost", True)
            window.geometry("560x360+120+120")
            window.grab_set()

            tk.Label(window, text="Do you have written permission to perform these tests?", font=("TkDefaultFont", 12, "bold"), wraplength=520).pack(fill="x", padx=16, pady=(16, 8))
            tk.Label(window, text=f"Target host/scope: {target_text}", wraplength=520, justify="left").pack(fill="x", padx=16, pady=(0, 10))
            tk.Label(
                window,
                text=(
                    "WARNING: Running tests on unauthorized targets without written consent is illegal.\n\n"
                    "Agent Kal and his developers urge you to only use this software for authorized testing purposes "
                    "or educational purposes only and will not be held responsible for any misuse."
                ),
                font=("TkDefaultFont", 10, "bold"),
                fg="#9a3412",
                wraplength=520,
                justify="left",
            ).pack(fill="x", padx=16, pady=(0, 12))

            tk.Label(window, text="Type AUTHORIZED to proceed with testing:", anchor="w").pack(fill="x", padx=16)
            token = tk.Entry(window)
            token.pack(fill="x", padx=16, pady=(4, 12))
            token.focus_set()

            def approve() -> None:
                if token.get().strip() != "AUTHORIZED":
                    messagebox.showerror("Authorization Required", "must provide auth to proceed", parent=window)
                    token.selection_range(0, "end")
                    token.focus_set()
                    return
                result["approved"] = True
                window.destroy()
                done.set()

            def cancel() -> None:
                result["approved"] = False
                window.destroy()
                done.set()

            buttons = tk.Frame(window)
            buttons.pack(fill="x", padx=16, pady=8)
            tk.Button(buttons, text="Proceed", command=approve).pack(side="left")
            tk.Button(buttons, text="Cancel", command=cancel).pack(side="right")
            token.bind("<Return>", lambda _event: approve())
            window.protocol("WM_DELETE_WINDOW", cancel)

        self.root.after(0, ask)
        done.wait()
        return result["approved"]

    def _set_thinking(self, message: str) -> None:
        self.root.after(0, lambda: self.thinking.set(message))

    def _say(self, speaker: str, message: str, animated: bool = False) -> None:
        self.root.after(0, lambda: self._enqueue_say(speaker, message, animated))

    def _note(self, message: str) -> None:
        self.root.after(0, lambda: self._enqueue_note(message))

    def _enqueue_note(self, message: str) -> None:
        self.say_queue.append(("", message + "\n\n", "activity_note", "activity_note", False))
        if not self.speaking:
            self._drain_say_queue()

    def _enqueue_say(self, speaker: str, message: str, animated: bool = False) -> None:
        if speaker == "Agent Kal":
            animated = True
            if self.admin_mode:
                speaker = "Agent Kal (Admin Mode)"
        tag = "user" if speaker == "You" else "agent"
        label_tag = "user_label" if speaker == "You" else "agent_label"
        self.say_queue.append((speaker, message, tag, label_tag, animated))
        if not self.speaking:
            self._drain_say_queue()

    def _drain_say_queue(self) -> None:
        if not self.say_queue:
            self.speaking = False
            self._focus_prompt()
            return
        self.speaking = True
        speaker, message, tag, label_tag, animated = self.say_queue.pop(0)
        if speaker:
            self.chat.insert("end", f"{speaker}: ", label_tag)
        self.type_chars_on_page = 0
        if animated:
            if "```" in message or self._has_command_lines(message):
                self._insert_message_text(message + "\n\n", tag)
                self._drain_say_queue()
            else:
                self._type_text(message + "\n\n", tag=tag)
            return
        self._insert_message_text(message + "\n\n", tag)
        self.chat.see("end")
        self._drain_say_queue()

    def _type_text(self, text: str, index: int = 0, tag: str = "agent") -> None:
        if index >= len(text):
            self._drain_say_queue()
            return
        chunk = text[index : index + 2]
        self.chat.insert("end", chunk, tag)
        self.chat.see("end")
        delay = 45
        if chunk in ".!?\n":
            delay = 180
        self.root.after(delay, lambda: self._type_text(text, index + len(chunk), tag))

    def _insert_message_text(self, text: str, tag: str) -> None:
        for part in self._split_code_blocks(text):
            if part[0] == "code":
                self._insert_code_block(part[1])
            elif part[0] == "command":
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
            parts.extend(self._split_command_lines(text))
        return parts

    def _split_command_lines(self, text: str) -> list[tuple[str, str]]:
        parts: list[tuple[str, str]] = []
        text_lines: list[str] = []
        command_lines: list[str] = []
        for line in text.splitlines(keepends=True):
            if self._is_command_line(line):
                if text_lines:
                    parts.append(("text", "".join(text_lines)))
                    text_lines = []
                command_lines.append(line.rstrip() + "\n")
            else:
                if command_lines:
                    parts.append(("command", "".join(command_lines)))
                    command_lines = []
                text_lines.append(line)
        if command_lines:
            parts.append(("command", "".join(command_lines)))
        if text_lines:
            parts.append(("text", "".join(text_lines)))
        return parts

    def _has_command_lines(self, text: str) -> bool:
        return any(self._is_command_line(line) for line in text.splitlines())

    def _is_command_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        stripped = stripped.removeprefix("- ").removeprefix("* ")
        stripped = stripped.removeprefix("$ ").removeprefix("# ")
        first = stripped.split(maxsplit=1)[0]
        return first in COMMAND_PREFIXES

    def _insert_code_block(self, code: str) -> None:
        self.chat.insert("end", "\n", "agent")
        for line in code.splitlines(keepends=True):
            self._insert_code_line(line)
        button = tk.Button(self.chat, text="Copy all", command=lambda value=code: self.root.clipboard_clear() or self.root.clipboard_append(value))
        self.chat.window_create("end", window=button)
        self.chat.insert("end", "\n\n", "agent")

    def _insert_code_line(self, line: str) -> None:
        match = re.match(r"^(\s*(?:[-*]\s*)?(?:[$#]\s*)?)(\S+)(.*)$", line)
        if not match:
            self.chat.insert("end", line, "code")
            return
        lead, prefix, rest = match.groups()
        self.chat.insert("end", lead, "code")
        if prefix in COMMAND_PREFIXES:
            self.chat.insert("end", prefix, ("code", "code_prefix"))
        else:
            self.chat.insert("end", prefix, "code")
        self.chat.insert("end", rest, "code")

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

    def _chat_keypress(self, event) -> str | None:
        if event.state & 0x4 and event.keysym.lower() in {"c", "a"}:
            return None
        return "break"

    def _copy_selection(self, event=None) -> str:
        try:
            selected = self.chat.get("sel.first", "sel.last")
        except tk.TclError:
            selected = ""
        if selected:
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        return "break"

    def _select_all_chat(self, event=None) -> str:
        self.chat.tag_add("sel", "1.0", "end")
        return "break"

    def _show_chat_menu(self, event) -> str:
        self.chat_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _paste_prompt(self, event=None) -> str:
        try:
            self.prompt.insert("insert", self.root.clipboard_get())
        except tk.TclError:
            pass
        return "break"

    def _copy_prompt_selection(self, event=None) -> str:
        try:
            selected = self.prompt.selection_get()
        except tk.TclError:
            selected = ""
        if selected:
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        return "break"

    def _select_all_prompt(self, event=None) -> str:
        self.prompt.selection_range(0, "end")
        self.prompt.icursor("end")
        return "break"

    def _show_prompt_menu(self, event) -> str:
        self.prompt_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _last_user_message(self) -> str:
        text = self.chat.get("1.0", "end")
        messages = [line.removeprefix("You: ").strip() for line in text.splitlines() if line.startswith("You: ")]
        return messages[-1] if messages else ""

    def _append_event(self, event: dict[str, Any]) -> None:
        self.root.after(0, lambda: self._record_event(event))

    def _gui_event(self, event: str, data: dict[str, Any]) -> None:
        self._append_event({"time": datetime.now(UTC).isoformat(), "event": event, "data": data})

    def _record_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        self._append_preview_event(event)

    def show_preview(self, attached: bool = False) -> None:
        if self.preview and self.preview.winfo_exists():
            if attached:
                self._attach_preview()
            self.preview.lift()
            return

        self.preview = tk.Toplevel(self.root)
        self.preview.title("Agentic Kali Live View")
        self.preview.attributes("-topmost", True)
        if attached:
            self._attach_preview()
        else:
            self.preview.geometry("680x520+480+40")
        frame = tk.Frame(self.preview)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        self.preview_text = tk.Text(frame, wrap="word")
        preview_scroll = tk.Scrollbar(frame, orient="vertical", command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        self.preview_text.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")
        self._refresh_preview()

    def _attach_preview(self) -> None:
        self.root.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width()
        y = self.root.winfo_y()
        self.preview.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{x}+{y}")

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
            if self.preview_text.get("1.0", "end").strip() == "No activity yet.":
                self.preview_text.delete("1.0", "end")
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

    def open_reports(self) -> None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        opener = shutil.which("xdg-open") or shutil.which("thunar")
        if not opener:
            messagebox.showerror("Reports", f"Reports folder: {REPORTS_DIR.resolve()}")
            return
        subprocess.Popen([opener, str(REPORTS_DIR.resolve())])
        self._gui_event("gui.reports.opened", {"path": str(REPORTS_DIR.resolve())})

    def _save_scope(self, fields: dict[str, tk.Entry]) -> None:
        scope = Scope(
            engagement_name=fields["Engagement"].get(),
            targets=[item.strip() for item in fields["Targets"].get().split(",") if item.strip()],
            allowed_actions=[item.strip() for item in fields["Actions"].get().split(",") if item.strip()],
            approval_mode=ApprovalMode(fields["Approval"].get()),
            intrusive_allowed=False,
            signed_permission=fields["Permission"].get() == "AUTHORIZED",
            public_targets_allowed=fields["Public Targets"].get().lower() == "true",
        )
        self._write_scope(scope)
        messagebox.showinfo("Agentic Kali", f"Saved {DEFAULT_SCOPE}")

    def _write_scope(self, scope: Scope) -> None:
        DEFAULT_SCOPE.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_SCOPE.write_text(json.dumps(scope.model_dump(mode="json"), indent=2), encoding="utf-8")
        try:
            DEFAULT_SCOPE.chmod(0o660)
        except OSError:
            pass

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
