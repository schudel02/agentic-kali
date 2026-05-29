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
from agentic_kali.policy.security_settings import ADMIN_GUARDRAILS, ALL_ACTIONS, ALL_ADMIN_ACTIONS, SAFE_RECON_ACTIONS, UNSAFE_BUILD_TERMS, all_blocked_build_terms, load_admin_guardrails
from agentic_kali.ai.commands import actions_from_command, is_auto_command
from agentic_kali.ai.request import is_autonomous_request
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
from agentic_kali.tools.runner import stop_all_commands


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
        self.preview_mode = tk.StringVar(value="transcript")
        self._build_menus()

        self.title_text = tk.StringVar(value="Agent Kal V.1")
        tk.Label(self.root, textvariable=self.title_text, anchor="w", font=("TkDefaultFont", 11, "bold"), fg="#174ea6").pack(fill="x", padx=10, pady=(8, 0))

        self.body_frame = tk.Frame(self.root)
        self.body_frame.pack(fill="both", expand=True, padx=10, pady=(8, 6))
        chat_frame = tk.Frame(self.body_frame)
        chat_frame.pack(side="left", fill="both", expand=True)
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
        self.chat_menu.add_command(label="Save Transcript", command=self.save_chat_transcript)
        self.admin_mode = False
        self.user_mode = "Regular"
        self.preferred_name = ""
        self.awaiting_name = False
        self.awaiting_beginner_choice = False
        self.awaiting_beginner_target = False
        self.awaiting_beginner_auth = False
        self.beginner_scope_step = ""
        self.beginner_scope: dict[str, str] = {}
        self.speaking = False
        self.say_queue: list[tuple[str, str, str, str, bool]] = []

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
        self.security_button = tk.Button(input_frame, text="Security", command=self.show_security_settings)
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
        frame.pack(fill="x", padx=10, pady=(4, 6))
        tk.Button(frame, text="Stop", width=8, command=self.stop).pack(side="left")
        tk.Button(frame, text="Quit", width=8, command=self.root.destroy).pack(side="right")

        self.preview: tk.Toplevel | None = None
        self.preview_embedded: tk.Frame | None = None
        self.preview_text: tk.Text | None = None
        self.normal_geometry = self.root.geometry()
        self.events: list[dict[str, Any]] = []
        self.session = ChatSession()
        self.stop_requested = False
        self.type_chars_on_page = 0
        self.pending_launch: LaunchRequest | None = None
        self.last_target: str | None = None
        self.lab_servers: list[LabServer] = []
        self.countdown_after: str | None = None
        self.countdown_remaining = 0
        self._last_suggested_target: str | None = None
        self._awaiting_tool_selection: bool = False
        self._tool_selection_target: str | None = None
        self._awaiting_autonomous_goal: bool = False
        self._awaiting_autonomous_target: bool = False
        self._pending_autonomous_goal: str = ""
        self._tool_timer_var: tk.StringVar = tk.StringVar(value="")
        self._tool_timer_after: str | None = None
        self._tool_timer_remaining: int = 0
        self._current_tool_label: tk.StringVar = tk.StringVar(value="")
        # Sub-agent windows: action_name -> (Toplevel, Text, status_var)
        self._subagent_windows: dict[str, tuple] = {}
        self.root.after(300, self._show_mode_dialog)

    def _build_menus(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Chat Session", command=self._new_chat_session)
        file_menu.add_separator()
        file_menu.add_command(label="Save Chat Transcript", command=self.save_chat_transcript)
        file_menu.add_command(label="Open Reports Folder", command=self.open_reports)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Live View", command=self.show_preview)
        view_menu.add_command(label="Watch Mode", command=self.show_watch_mode)
        view_menu.add_separator()
        view_menu.add_radiobutton(label="Preview: Natural Transcript", variable=self.preview_mode, value="transcript", command=self._refresh_preview)
        view_menu.add_radiobutton(label="Preview: Raw Events", variable=self.preview_mode, value="raw", command=self._refresh_preview)
        menubar.add_cascade(label="View", menu=view_menu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Settings", command=self.show_settings)
        settings_menu.add_command(label="Security Settings", command=self.show_security_settings)
        settings_menu.add_command(label="Azure Config Wizard", command=run_config_wizard)
        menubar.add_cascade(label="Options", menu=settings_menu)
        self.root.config(menu=menubar)

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
        self.say_queue.clear()
        self.speaking = False
        self._awaiting_autonomous_goal = False
        self._awaiting_autonomous_target = False
        self._pending_autonomous_goal = ""
        self._awaiting_tool_selection = False
        self._tool_selection_target = None
        self._stop_tool_timer()
        self._close_subagent_windows()
        stop_all_commands()
        self.status.set("Stopped")
        self._set_thinking("")

    def _show_mode_dialog(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Choose Agent Kal Mode")
        window.attributes("-topmost", True)
        window.geometry("420x260+120+120")
        window.grab_set()
        tk.Label(window, text="Choose Mode", font=("TkDefaultFont", 14, "bold")).pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(window, text="Select how much guidance Agent Kal should provide.", wraplength=380).pack(fill="x", padx=16, pady=(0, 12))
        for mode, desc in (
            ("Beginner", "Step-by-step explanations and guided testing."),
            ("Regular", "Balanced help and direct testing flow."),
            ("Professional", "Minimal explanations and faster execution."),
        ):
            tk.Button(window, text=f"{mode} - {desc}", command=lambda value=mode: self._select_mode(window, value)).pack(fill="x", padx=16, pady=4)

    def _select_mode(self, window: tk.Toplevel, mode: str) -> None:
        self.user_mode = mode
        self.mode.set(f"{mode} Mode")
        window.destroy()
        if mode == "Professional":
            self.preferred_name = "Chuck Norris"
            self.awaiting_name = False
            self.title_text.set("Agent Kal V.1")
            self._say("Agent Kal", "Oh yeah? Professional Mode?\nYou don't have to tell me your name. I already know it.", animated=True)
            self.root.after(2800, lambda: self.title_text.set("Agent Kal V.1 — Chuck Norris"))
            self.root.after(2800, lambda: self._say("Agent Kal", self._mode_intro(), animated=True))
        else:
            self.awaiting_name = True
            self.title_text.set(f"{mode} Mode - Agent Kal V.1" if mode == "Beginner" else "Agent Kal V.1")
            self._say("Agent Kal", "What would you prefer I call you?", animated=True)
        self._focus_prompt()

    def _set_admin_ui(self) -> None:
        self.root.after(0, self._enable_admin_ui)

    def _enable_admin_ui(self) -> None:
        prefix = f"{self.user_mode} Mode - " if self.user_mode == "Beginner" else ""
        self.title_text.set(f"[Admin Mode] - {prefix}Agent Kal V.1")
        self.root.title("Agentic Kali - Admin Mode")
        try:
            self.security_button.pack(side="right", padx=(8, 0))
        except tk.TclError:
            pass

    def _run_agent(self) -> None:
        try:
            self._set_thinking("Thinking through your request...")
            scope = self._load_scope_or_none() or Scope(
                engagement_name="local-lab",
                targets=["127.0.0.1"],
                allowed_actions=list(ALL_ACTIONS),
            )
            self.events = []
            command = self._last_user_message()
            if is_admin_phrase(command):
                self.admin_mode = True
                self.session = ChatSession(admin_mode=True)
                self._set_thinking("")
                self._set_admin_ui()
                self._say("Agent Kal", "Admin Approved Mode enabled. All guardrails bypassed for this session.")
                self.status.set("Admin Approved Mode")
                return
            # Handle pending autonomous target (after goal was already selected)
            if self._awaiting_autonomous_target:
                self._awaiting_autonomous_target = False
                self._set_thinking("")
                target = extract_target(command) or command.strip()
                if not target:
                    self._say("Agent Kal", "I need a valid IP address or domain name.")
                    self._awaiting_autonomous_target = True
                    return
                self.last_target = target
                goal = self._pending_autonomous_goal
                self._pending_autonomous_goal = ""
                scope = self._ensure_consent(scope, target)
                if not scope:
                    self._say("Agent Kal", "Auth required.")
                    return
                self._run_scoped_tests(command, scope, target, autonomous=True, goal=goal)
                return

            # Handle pending autonomous goal selection
            if self._awaiting_autonomous_goal:
                self._awaiting_autonomous_goal = False
                self._set_thinking("")
                _goal_map = {
                    "1": "recon", "2": "web audit", "3": "vulnerability scan",
                    "4": "full pentest", "5": "wifi", "6": "active directory",
                    "7": "credentials", "8": "osint", "9": "forensics",
                    "10": "api", "11": "burp",
                }
                goal = _goal_map.get(command.strip().rstrip("."), command.lower().strip())
                target = self.last_target
                if not target:
                    self._pending_autonomous_goal = goal
                    self._awaiting_autonomous_target = True
                    self._say("Agent Kal", f"Goal: {goal}. What target? Give me an IP or domain.")
                    return
                scope = self._ensure_consent(scope, target)
                if not scope:
                    self._say("Agent Kal", "Auth required.")
                    return
                self._run_scoped_tests(command, scope, target, autonomous=True, goal=goal)
                return

            # Handle pending tool selection response
            if self._awaiting_tool_selection and self._tool_selection_target:
                target = self._tool_selection_target
                self._awaiting_tool_selection = False
                self._tool_selection_target = None
                self._set_thinking("")
                scope = self._ensure_consent(scope, target)
                if not scope:
                    self._say("Agent Kal", "Auth required.")
                    return
                autonomous = is_auto_command(command)
                self._run_scoped_tests(command, scope, target, autonomous=autonomous)
                return

            if self._handle_onboarding(command, scope):
                self._set_thinking("")
                return
            consent_scope = self._scope_from_consent(command, scope)
            if consent_scope:
                scope = consent_scope
                self._say("Agent Kal", f"Consent saved for {', '.join(scope.targets)}.")
                if not wants_tool_run(command):
                    self._set_thinking("")
                    self.status.set("Scope saved")
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
            if not target and self._is_intrusive_request(command):
                self._set_thinking("")
                self._say("Agent Kal", "Target?")
                self.status.set("Target required")
                return
            if is_autonomous_request(command) and self.admin_mode:
                self._awaiting_autonomous_goal = True
                self._set_thinking("")
                self._say(
                    "Agent Kal",
                    "Autonomous mode activated. Choose a test type:\n\n"
                    "  1. Recon              — ping, nmap, DNS, subdomain, OSINT\n"
                    "  2. Web Audit          — fingerprint, nuclei, dirb, nikto, ffuf\n"
                    "  3. Vulnerability Scan — nuclei full, nmap vuln scripts, nikto\n"
                    "  4. Full Pentest       — all available tools\n"
                    "  5. WiFi               — aircrack, wifite, kismet, reaver\n"
                    "  6. Active Directory   — bloodhound, crackmapexec, impacket\n"
                    "  7. Credentials        — hydra, john, hashcat, cewl\n"
                    "  8. OSINT              — theHarvester, sherlock, spiderfoot\n"
                    "  9. Forensics          — binwalk, yara, jadx, ghidra\n"
                    " 10. API Testing        — arjun, api probe, nuclei API templates\n"
                    " 11. Burp Suite         — launch Burp + route tools through proxy\n\n"
                    f"Target: {target or self.last_target or '(tell me the target first)'}\n"
                    "Reply with a number or name.",
                )
                self.status.set("Awaiting test type selection")
                return

            if target and self._wants_run(command, target):
                self.last_target = target
                self._set_thinking("")
                scope = self._ensure_consent(scope, target)
                if not scope:
                    self._say("Agent Kal", "Auth required.")
                    self.status.set("Consent required")
                    return
                autonomous = is_auto_command(command)
                self._run_scoped_tests(command, scope, target, autonomous=autonomous)
                return
            if target and not self._wants_run(command, target) and target != self._last_suggested_target:
                self._last_suggested_target = target
                self.last_target = target
                self._awaiting_tool_selection = True
                self._tool_selection_target = target
                self._set_thinking("")
                self._say("Agent Kal", self._build_target_suggestion(target))
                self.status.set(f"Target: {target}")
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
                self._say("Agent Kal", "Auth required.")
                self.status.set("Consent required")
                return
            if target:
                self.last_target = target
            self._run_scoped_tests(command, scope, target)
        except Exception as exc:
            self._exit_run_mode()
            self.status.set("Error")
            self._set_thinking("")
            self._say("Agent Kal", f"I need setup before I can run: {exc}")
            messagebox.showerror("Agentic Kali", str(exc))

    def _run_scoped_tests(self, command: str, scope: Scope, target: str | None, autonomous: bool = False, goal: str = "") -> None:
        if self.admin_mode:
            scope = scope.model_copy(update={
                "allowed_actions": list(dict.fromkeys([*scope.allowed_actions, *ALL_ADMIN_ACTIONS])),
                "intrusive_allowed": True,
                "signed_permission": True,
            })
        actions = actions_from_command(command, scope.allowed_actions)
        if autonomous:
            goal_label = goal or "full assessment"
            self._say("Agent Kal", f"Starting autonomous {goal_label} on {target or 'the target'}. Deploying sub-agents to run tools in parallel. I will read results between rounds and chain the next set of tests. Press Stop at any time.")
        else:
            self._say("Agent Kal", self._short_run_summary(command, actions, target))
        self._note(self._run_description(actions, target or ", ".join(scope.targets)))
        self._gui_event("run.preparing", {"target": target or scope.targets, "actions": actions})
        self._enter_run_mode(actions)
        report = Orchestrator(
            scope,
            on_event=self._append_event,
            command=command,
            should_stop=lambda: self.stop_requested,
            admin_mode=self.admin_mode,
            autonomous=autonomous,
            goal=goal,
        ).run()
        self.events = report.get("events", [])
        self._refresh_preview()
        files = write_reports(report)
        report["report_files"] = files
        append_history(report)
        if self.stop_requested:
            self._say_static("Agent Kal", self._summarize_results(report, files, stopped=True))
            self.status.set("Stopped")
        else:
            self._say_static("Agent Kal", self._summarize_results(report, files))
            self.status.set(f"Done: {files['markdown']}")
        if target:
            self.last_target = target
        self._exit_run_mode()

    def _continued_launch(self, command: str) -> LaunchRequest | None:
        if not self.pending_launch:
            return None
        if command.lower().strip() in {"yes", "y", "do it", "just open", "just open it", "open it"}:
            return self.pending_launch
        return None

    def _handle_onboarding(self, command: str, scope: Scope) -> bool:
        if self.awaiting_name:
            self.preferred_name = command.strip()
            self.awaiting_name = False
            if self.user_mode == "Beginner":
                self.awaiting_beginner_choice = True
            self._say("Agent Kal", self._mode_intro(), animated=True)
            return True
        if self.user_mode != "Beginner":
            return False
        lower = command.lower().strip()
        if self.awaiting_beginner_choice:
            self.awaiting_beginner_choice = False
            if "sim" in lower or "lab" in lower:
                self._say("Agent Kal", "Good choice. Say `create a local test server` and I will start a safe local practice target, then walk you through recon and reporting.", animated=True)
                return True
            self.awaiting_beginner_target = True
            self._say("Agent Kal", self._target_explanation(), animated=True)
            return True
        if self.awaiting_beginner_target:
            target = extract_target(command)
            if not target:
                self._say("Agent Kal", self._target_explanation(), animated=True)
                return True
            self.last_target = target
            self.awaiting_beginner_target = False
            self.beginner_scope = {"target": target}
            self.awaiting_beginner_auth = True
            self._say("Agent Kal", self._authorization_explanation(target), animated=True)
            self._say("Agent Kal", "Type `authorized` in chat when you are ready to continue.", animated=True)
            return True
        if self.awaiting_beginner_auth:
            if lower not in {"authorize", "authorized"}:
                self._say("Agent Kal", "Authorization is required before I ask the next scope question. Type `authorized` if you have permission, or choose another target.", animated=True)
                return True
            self.awaiting_beginner_auth = False
            target = self.beginner_scope.get("target") or self.last_target
            if target:
                updated = self._save_beginner_authorization(scope, target)
                self._say("Agent Kal", f"Authorization saved for {target}.", animated=True)
                scope = updated
            self.beginner_scope_step = "goal"
            self._say("Agent Kal", self._scope_goal_prompt(), animated=True)
            return True
        if self.beginner_scope_step == "goal":
            self.beginner_scope["goal"] = command.strip()
            self.beginner_scope_step = "restrictions"
            self._say("Agent Kal", self._scope_restrictions_prompt(), animated=True)
            return True
        if self.beginner_scope_step == "restrictions":
            self.beginner_scope["restrictions"] = command.strip()
            self.beginner_scope_step = ""
            self._save_beginner_scope_details(scope)
            self._say("Agent Kal", self._scope_ready_message(), animated=True)
            return True
        return False

    def _mode_intro(self) -> str:
        name = self.preferred_name or "there"
        if self.user_mode == "Beginner":
            return (
                f"Hi {name}, my name is Agent Kal. I'm a Whitehat Ethical Penetration Testing Agent.\n\n"
                "I can assist you in running authorized penetration tests. Some things I can do:\n"
                "- Explain targets, scope, and authorization.\n"
                "- Run recon like port checks, web fingerprinting, and HTTP probing.\n"
                "- Run safe vulnerability checks and conservative SQL injection checks when authorized.\n"
                "- Open Kali tools, explain what they do, and write reports.\n"
                "- Create a local practice server for simulated testing.\n\n"
                "Would you like to run a simulated testing environment first, or dive right in to actual testing?"
            )
        if self.user_mode == "Professional":
            return f"Hi {name}. Professional Mode ready. Give me a target and test objective."
        return f"Hi {name}. Regular Mode ready. Tell me the authorized target and what you want to test."

    def _target_explanation(self) -> str:
        return (
            "Okay. What target are you going to test?\n\n"
            "A target is the system you have permission to assess. Examples:\n"
            "- IP address: 192.168.1.25\n"
            "- Localhost: 127.0.0.1\n"
            "- Host/domain: example.com\n"
            "- URL: https://example.com/login\n\n"
            "Send the target, then I will ask for authorization before any tests run."
        )

    def _authorization_explanation(self, target: str) -> str:
        return (
            f"Target saved: {target}.\n\n"
            "Authorization means you confirm you have full permission to test this target. "
            "This should come from ownership, a written agreement, or an approved lab environment.\n\n"
            "To authorize and confirm you have full permission to proceed, type `authorized` in the authorization box. "
            "If you do not have permission, exit that menu and choose another target."
        )

    def _scope_goal_prompt(self) -> str:
        return (
            "Next scope step: testing goal.\n\n"
            "The goal tells me what kind of security question we are answering. Examples:\n"
            "- Find exposed services\n"
            "- Check a website for common issues\n"
            "- Map web technologies\n"
            "- Run a conservative SQL injection check\n\n"
            "What is your testing goal?"
        )

    def _scope_restrictions_prompt(self) -> str:
        return (
            "Next scope step: restrictions.\n\n"
            "Restrictions are rules I should follow during testing. Examples:\n"
            "- No login testing\n"
            "- Do not test subdomains\n"
            "- Only run non-invasive scans\n"
            "- Stop if the site slows down\n\n"
            "What restrictions should I follow? If none, type `none`."
        )

    def _scope_ready_message(self) -> str:
        target = self.beginner_scope.get("target", "the target")
        goal = self.beginner_scope.get("goal", "authorized testing")
        restrictions = self.beginner_scope.get("restrictions", "none")
        return (
            "Scope is ready.\n\n"
            f"- Target: {target}\n"
            f"- Goal: {goal}\n"
            f"- Restrictions: {restrictions}\n\n"
            "You can now say `run quick recon`, `run vulnerability test`, or `explain what test I should run first`."
        )

    def _save_beginner_authorization(self, scope: Scope, target: str) -> Scope:
        updated = scope.model_copy(
            update={
                "targets": list(dict.fromkeys([*scope.targets, target])),
                "allowed_actions": list(dict.fromkeys([*scope.allowed_actions, *ALL_ACTIONS])),
                "approval_mode": ApprovalMode.RECON_ONLY,
                "intrusive_allowed": True,
                "signed_permission": True,
                "public_targets_allowed": True,
            }
        )
        self._write_scope(updated)
        return updated

    def _save_beginner_scope_details(self, scope: Scope) -> Scope:
        target = self.beginner_scope.get("target")
        existing = self._load_scope_or_none() or scope
        updated = existing.model_copy(
            update={
                "targets": list(dict.fromkeys([*existing.targets, target] if target else existing.targets)),
                "testing_goal": self.beginner_scope.get("goal", ""),
                "restrictions": self.beginner_scope.get("restrictions", ""),
            }
        )
        self._write_scope(updated)
        return updated

    def _build_target_suggestion(self, target: str) -> str:
        from agentic_kali.policy.security_settings import ALL_ADMIN_ACTIONS
        scope = self._load_scope_or_none()
        allowed = set(scope.allowed_actions if scope else []) | set(ALL_ADMIN_ACTIONS if self.admin_mode else [])

        tool_info = {
            "ping_check":    "Ping check — confirm target is reachable",
            "nmap_top_ports":"Nmap — port scan and service detection",
            "whatweb":       "WhatWeb — web technology fingerprinting",
            "httpx_probe":   "httpx — HTTP probe, titles, redirects",
            "nuclei_safe":   "Nuclei (safe) — low-risk vulnerability templates",
            "sqlmap_safe":   "sqlmap — conservative SQL injection check",
            "gobuster_dir":  "Gobuster — directory and path discovery [Admin]",
            "ffuf_fuzz":     "ffuf — web path fuzzing [Admin]",
            "nikto_scan":    "Nikto — web server vulnerability scan [Admin]",
            "nuclei_full":   "Nuclei (full) — medium/high severity templates [Admin]",
            "hydra_brute":   "Hydra — authorized credential brute-force [Admin]",
        }

        available = [name for name in tool_info if name in allowed]
        lines = [f"Target: {target}\n\nAvailable tools:"]
        for i, name in enumerate(available, 1):
            lines.append(f"  {i}. {tool_info[name]}")
        lines += [
            "",
            "Reply with:",
            "  • A number or name — run that tool",
            "  • 'run all' — run every available tool",
            "  • 'quick recon' — ping + nmap + whatweb + httpx",
            "  • 'you choose' or 'auto' — let me pick and chain tools autonomously",
        ]
        return "\n".join(lines)

    def _is_intrusive_request(self, command: str) -> bool:
        text = command.lower()
        return any(phrase in text for phrase in ("sql injection", "sqli", "sqlmap", "invasive", "intrusive"))

    def _short_run_summary(self, command: str, actions: list[str], target: str | None) -> str:
        if self._is_intrusive_request(command):
            return f"Running authorized intrusive checks on {target}: {', '.join(actions)}."
        return summarize_request(command, actions, target)

    def _summarize_results(self, report: dict, files: dict[str, str], stopped: bool = False) -> str:
        findings = report.get("findings", [])
        events = report.get("events", [])
        if not findings:
            ran = [e["data"].get("action") for e in events if e.get("event") == "action.started"]
            intro = "Stopped. " if stopped else "Finished. "
            if not ran:
                return (
                    f"{intro}No tools were run. The target may not be in scope or no actions were selected.\n"
                    "Try: 'run quick recon on [target]' or enable Admin Mode and try again.\n\n"
                    f"Report: {files['markdown']}"
                )
            return (
                f"{intro}Tools ran ({', '.join(ran)}) but returned no structured findings. "
                "This can mean the target had no detectable issues, the tool isn't installed, or the target blocked scanning.\n"
                f"Check the raw report for tool output: {files['markdown']}"
            )

        counts: dict[str, int] = {}
        for finding in findings:
            severity = finding.get("severity", "info")
            counts[severity] = counts.get(severity, 0) + 1
        severity_text = ", ".join(f"{level}: {count}" for level, count in sorted(counts.items()))
        top = findings[:5]
        lines = [
            "Stopped with partial results." if stopped else "Finished. Here is what I found:",
            f"Findings by severity: {severity_text}",
            self._severity_plain_english(counts),
        ]
        lines.append("What each result means:")
        for finding in top:
            title = finding.get("title", "Finding")
            target = finding.get("target", "target")
            severity = finding.get("severity", "info")
            metadata = finding.get("metadata", {})
            detail = self._finding_detail(metadata) or "See report evidence for tool output."
            meaning = self._finding_layman_meaning(title, metadata)
            why = self._finding_why_it_matters(title, metadata, severity)
            next_step = self._finding_next_step(title, metadata, severity)
            lines.extend(
                [
                    f"- {title} on {target} ({severity})",
                    f"  Result: {detail}",
                    f"  In plain English: {meaning}",
                    f"  Why it matters: {why}",
                    f"  What to do next: {next_step}",
                ]
            )
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
                services = [f"{item.get('port')} ({item.get('service', 'service')})" for item in ports if item.get("state") == "open"]
                return f"Open network doors found: {', '.join(services or open_ports)}."
        technologies = metadata.get("technologies") if isinstance(metadata, dict) else None
        if technologies:
            return f"The website appears to use: {', '.join(technologies[:8])}."
        responses = metadata.get("responses") if isinstance(metadata, dict) else None
        if responses:
            return f"The web server responded to HTTP checks. Sample: {responses[0][:120]}."
        if isinstance(metadata, dict) and metadata:
            return "Structured metadata was captured for review."
        return ""

    def _severity_plain_english(self, counts: dict[str, int]) -> str:
        if any(counts.get(level, 0) for level in ("high", "critical")):
            return "Plain English: at least one result may need urgent attention before the system is considered safe."
        if counts.get("medium", 0):
            return "Plain English: some items may increase risk and should be reviewed soon."
        if counts.get("low", 0):
            return "Plain English: the test found minor issues or tool warnings worth cleaning up."
        return "Plain English: these are mostly informational results that help map what the target exposes."

    def _finding_layman_meaning(self, title: str, metadata: dict) -> str:
        metadata = metadata if isinstance(metadata, dict) else {}
        lowered = title.lower()
        if "nmap" in lowered or metadata.get("open_ports"):
            return "The target has services listening on the network. Think of each open port as a door: some doors are expected, but every open door should have a clear business reason."
        if "fingerprint" in lowered or metadata.get("technologies"):
            return "The website is revealing what software, frameworks, or server components it uses. This is useful inventory information, and it helps decide which updates or safe checks matter."
        if "http" in lowered or metadata.get("responses"):
            return "The web server answered Agent Kal's request. That means the site is reachable and can be checked further for headers, exposed pages, and basic configuration issues."
        return "Agent Kal gathered evidence about the target. This is not automatically proof of a serious issue; it is information used to decide the next safe test."

    def _finding_why_it_matters(self, title: str, metadata: dict, severity: str) -> str:
        metadata = metadata if isinstance(metadata, dict) else {}
        lowered = title.lower()
        if "nmap" in lowered or metadata.get("open_ports"):
            return "Attackers and defenders both start by listing exposed services. Unknown or outdated services can become entry points."
        if "fingerprint" in lowered or metadata.get("technologies"):
            return "Known software names and versions can be matched against patches and known vulnerabilities."
        if "http" in lowered or metadata.get("responses"):
            return "HTTP responses show what the public web app exposes and whether later web checks are worth running."
        if severity in {"high", "critical"}:
            return "Higher-severity findings can affect confidentiality, integrity, or availability and should be reviewed first."
        return "It adds context to the security picture and helps avoid guessing."

    def _finding_next_step(self, title: str, metadata: dict, severity: str) -> str:
        metadata = metadata if isinstance(metadata, dict) else {}
        lowered = title.lower()
        if "nmap" in lowered or metadata.get("open_ports"):
            return "Confirm each open service is supposed to be exposed, update it, remove anything unnecessary, then run a safe vulnerability check."
        if "fingerprint" in lowered or metadata.get("technologies"):
            return "Check whether the detected technologies are current, remove version leakage where possible, and test only the components in scope."
        if "http" in lowered or metadata.get("responses"):
            return "Review response headers, login pages, exposed directories, and known safe web checks for this host."
        if severity in {"medium", "high", "critical"}:
            return "Validate the finding manually, document impact, then patch or mitigate before retesting."
        return "Keep it in the report and use it to choose the next scoped test."

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
        if not self.admin_mode and not is_safe_build_request(build_request):
            self._say("Agent Kal", "I can build safe authorized-testing helpers, but I cannot create tools for phishing, credential theft, malware, persistence, exfiltration, or destructive activity. Enable Admin Mode to override.")
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
        if "sqlmap_safe" in actions:
            return f"Opening sqlmap in conservative mode for SQL injection checks on {target}."
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
        if self.preview_embedded and self.preview_embedded.winfo_exists():
            self.preview_embedded.destroy()
            self.preview_embedded = None
            self.preview_text = None
            self.root.geometry(self.normal_geometry)
        self.mode.set("Chat Prompt")
        self.root.title("Agentic Kali - Admin Mode" if self.admin_mode else "Agentic Kali")

    _TOOL_ESTIMATES: dict[str, int] = {
        "ping_check": 5,
        "nmap_top_ports": 180, "nmap_full": 600, "nmap_udp": 300, "nmap_vuln": 300,
        "whatweb": 45, "httpx_probe": 45,
        "nuclei_safe": 240, "nuclei_full": 480,
        "nikto_scan": 360, "wpscan": 300,
        "gobuster_dir": 300, "gobuster_dns": 300,
        "ffuf_fuzz": 240, "dirb": 180, "dirsearch": 240, "feroxbuster": 300,
        "sqlmap_safe": 240, "sqlmap_full": 480,
        "hydra_brute": 240, "medusa": 240,
        "john_crack": 120, "hashcat": 120,
        "dnsrecon": 60, "dnsenum": 90, "amass_passive": 120,
        "subfinder": 60, "sublist3r": 90, "theharvester": 90,
        "dmitry": 30, "sherlock": 30,
        "autorecon": 600, "enum4linux": 120,
        "crackmapexec": 60, "netexec": 60,
        "bloodhound": 60,
        "ettercap": 120, "bettercap": 120, "responder": 120,
        "tcpdump": 60, "snort": 60,
        "wifite": 120, "reaver": 300, "aircrack_ng": 120,
        "spiderfoot": 180, "recon_ng": 60,
    }

    def _estimate_seconds(self, actions: list[str]) -> int:
        return max(30, sum(self._TOOL_ESTIMATES.get(a, 60) for a in actions))

    def _tool_estimate(self, action: str) -> int:
        return self._TOOL_ESTIMATES.get(action, 60)

    def _start_tool_timer(self, action: str, target: str) -> None:
        if self._tool_timer_after:
            self.root.after_cancel(self._tool_timer_after)
            self._tool_timer_after = None
        from agentic_kali.tools.catalog import TOOLS as _CAT
        tool = _CAT.get(action)
        cmd = tool.command if tool else action
        summary = (tool.summary if tool else action.replace("_", " "))[:50]
        self._current_tool_label.set(f"▶  {cmd}  —  {summary}")
        self._tool_timer_remaining = self._tool_estimate(action)
        self._active_tool_cmd = cmd
        self._tick_tool_timer()

    def _tick_tool_timer(self) -> None:
        remaining = max(0, self._tool_timer_remaining)
        mins, secs = divmod(remaining, 60)
        time_str = f"~{mins:02d}:{secs:02d}"
        self._tool_timer_var.set(time_str)
        # Also push to status bar so it's visible even if preview panel is gone
        cmd = getattr(self, "_active_tool_cmd", "tool")
        self.status.set(f"Running: {cmd}  —  {time_str} remaining")
        if remaining <= 0:
            self._tool_timer_var.set("finishing…")
            self.status.set(f"Running: {cmd}  —  finishing…")
            self._tool_timer_after = None
            return
        self._tool_timer_remaining -= 1
        self._tool_timer_after = self.root.after(1000, self._tick_tool_timer)

    def _stop_tool_timer(self) -> None:
        if self._tool_timer_after:
            self.root.after_cancel(self._tool_timer_after)
            self._tool_timer_after = None
        self._tool_timer_var.set("✓ done")
        self.root.after(1500, lambda: self._tool_timer_var.set(""))
        self.root.after(1500, lambda: self._current_tool_label.set(""))

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
                "allowed_actions": list(dict.fromkeys([*existing.allowed_actions, *ALL_ACTIONS])),
                "approval_mode": ApprovalMode.RECON_ONLY,
                "intrusive_allowed": True,
                "signed_permission": True,
                "public_targets_allowed": True,
            }
        )
        DEFAULT_SCOPE.parent.mkdir(parents=True, exist_ok=True)
        self._write_scope(scope)
        return scope

    def _ensure_consent(self, scope: Scope, target: str | None) -> Scope | None:
        requested_targets = [target] if target else scope.targets
        needs_consent = not scope.signed_permission or any(item not in scope.targets for item in requested_targets)
        if not needs_consent:
            return scope.model_copy(
                update={
                    "targets": requested_targets or scope.targets,
                    "allowed_actions": list(dict.fromkeys([*scope.allowed_actions, *ALL_ACTIONS])),
                    "intrusive_allowed": True,
                }
            ) if target else scope

        target_text = ", ".join(requested_targets)
        if not self._ask_written_consent(target_text):
            return None
        updated = scope.model_copy(
            update={
                "targets": list(dict.fromkeys([*scope.targets, *requested_targets])),
                "allowed_actions": list(dict.fromkeys([*scope.allowed_actions, *ALL_ACTIONS])),
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

            tk.Label(window, text="Authorization Required", font=("TkDefaultFont", 12, "bold"), wraplength=520).pack(fill="x", padx=16, pady=(16, 8))
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

            tk.Label(window, text="You must have full written authorization to proceed with this test. Type authorized:", anchor="w", wraplength=520).pack(fill="x", padx=16)
            token = tk.Entry(window)
            token.pack(fill="x", padx=16, pady=(4, 12))
            token.focus_set()

            def approve() -> None:
                if token.get().strip().lower() not in {"authorize", "authorized"}:
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

    def _say_static(self, speaker: str, message: str) -> None:
        """Insert message without animation — safe for long results that must not be cut short."""
        self.root.after(0, lambda: self._insert_static(speaker, message))

    def _insert_static(self, speaker: str, message: str) -> None:
        try:
            label_tag = "user_label" if speaker == "You" else "agent_label"
            tag = "user" if speaker == "You" else "agent"
            if self.admin_mode and speaker == "Agent Kal":
                speaker = "Agent Kal (Admin Mode)"
            self.chat.insert("end", f"{speaker}: ", label_tag)
            self._insert_message_text(message + "\n\n", tag)
            self.chat.see("end")
            self._focus_prompt()
        except tk.TclError:
            pass

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
        if self.stop_requested:
            self.speaking = False
            return
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
        name = event.get("event", "")
        data = event.get("data", {})

        if name == "subagents.deployed" and isinstance(data, dict):
            agents = data.get("agents", [])
            count = data.get("count", len(agents))
            agent_names = ", ".join(a.get("action", "") for a in agents)
            self._current_tool_label.set(f"⚡  {count} sub-agents running: {agent_names[:70]}")
            self._open_subagent_windows(agents)

        elif name == "action.started" and isinstance(data, dict):
            action = data.get("action", "")
            target = data.get("target", "")
            self._start_tool_timer(action, target)
            self._subagent_write(action, f"▶ STARTED: {action} on {target}\n", "header")

        elif name == "action.completed" and isinstance(data, dict):
            action = data.get("action", "")
            self._tool_timer_var.set(f"✓ {action} done")
            self._subagent_mark_done(action)

        elif name == "subagent.error" and isinstance(data, dict):
            action = data.get("action", "")
            self._subagent_write(action, f"⚠ ERROR: {data.get('error', 'unknown')}\n", "error")
            self._subagent_mark_done(action, error=True)

        elif name.startswith("tool.") and name != "tool.description":
            # Route tool output to the matching sub-agent window
            action_key = name.removeprefix("tool.")
            if isinstance(data, dict):
                import re as _re
                _ansi = _re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
                stdout = _ansi.sub("", data.get("stdout", "") or "")
                stderr = _ansi.sub("", data.get("stderr", "") or "")
                found = data.get("found", True)
                if not found:
                    self._subagent_write(action_key, "⚠ Tool not installed on this system.\n", "error")
                elif stdout:
                    self._subagent_write(action_key, stdout[:3000] + ("\n…(truncated)\n" if len(stdout) > 3000 else "\n"), "output")
                elif stderr:
                    self._subagent_write(action_key, f"stderr: {stderr[:1000]}\n", "output")
                else:
                    self._subagent_write(action_key, "Tool completed with no output.\n", "output")

        elif name in {"run.completed", "run.stopped"}:
            self._stop_tool_timer()
            self.root.after(8000, self._close_subagent_windows)

    # ── Sub-agent windows ─────────────────────────────────────────────

    def _open_subagent_windows(self, agents: list[dict]) -> None:
        self._close_subagent_windows()
        from agentic_kali.tools.catalog import TOOLS as _CAT

        # Determine grid layout
        count = len(agents)
        cols = min(count, 2)
        win_w, win_h = 520, 360
        gap = 10

        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_w = self.root.winfo_width()
        start_x = root_x + root_w + gap
        start_y = root_y

        for idx, agent_info in enumerate(agents):
            action = agent_info.get("action", "")
            target = agent_info.get("target", "")
            tool = _CAT.get(action)
            cmd = tool.command if tool else action
            purpose = (tool.summary if tool else action.replace("_", " "))[:60]
            agent_num = idx + 1

            col = idx % cols
            row = idx // cols
            x = start_x + col * (win_w + gap)
            y = start_y + row * (win_h + gap)

            win = tk.Toplevel(self.root)
            win.title(f"Agent {agent_num}  —  {cmd}  —  {purpose}")
            win.geometry(f"{win_w}x{win_h}+{x}+{y}")
            win.attributes("-topmost", True)

            # Header bar
            header = tk.Frame(win, bg="#1a1a2e", pady=4)
            header.pack(fill="x")
            tk.Label(
                header,
                text=f"Sub-Agent {agent_num}",
                bg="#1a1a2e", fg="#00d4ff",
                font=("TkDefaultFont", 10, "bold"), padx=8,
            ).pack(side="left")
            status_var = tk.StringVar(value="⏳ running")
            tk.Label(
                header,
                textvariable=status_var,
                bg="#1a1a2e", fg="#ffcc00",
                font=("TkDefaultFont", 10, "bold"), padx=8,
            ).pack(side="right")

            # Tool info bar
            info = tk.Frame(win, bg="#0d1117", pady=3)
            info.pack(fill="x")
            tk.Label(
                info,
                text=f"  🔧 {cmd}  |  {purpose}",
                bg="#0d1117", fg="#c9d1d9",
                font=("Courier", 9), anchor="w",
            ).pack(fill="x")
            tk.Label(
                info,
                text=f"  🎯 Target: {target}",
                bg="#0d1117", fg="#58a6ff",
                font=("Courier", 9), anchor="w",
            ).pack(fill="x")

            # Output text
            text_frame = tk.Frame(win)
            text_frame.pack(fill="both", expand=True)
            txt = tk.Text(
                text_frame,
                bg="#0d1117", fg="#c9d1d9",
                font=("Courier", 9),
                wrap="word", state="disabled",
            )
            txt.tag_configure("header", foreground="#00d4ff", font=("Courier", 9, "bold"))
            txt.tag_configure("output", foreground="#c9d1d9")
            txt.tag_configure("error", foreground="#ff6b6b")
            txt.tag_configure("done", foreground="#3fb950", font=("Courier", 9, "bold"))
            scroll = tk.Scrollbar(text_frame, command=txt.yview)
            txt.configure(yscrollcommand=scroll.set)
            txt.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")

            # Stop button
            tk.Button(
                win, text="⏹ Stop", bg="#c0392b", fg="white",
                font=("TkDefaultFont", 9, "bold"), relief="flat",
                command=self.stop,
            ).pack(fill="x", pady=2, padx=4)

            self._subagent_windows[action] = (win, txt, status_var)

    def _subagent_write(self, action: str, text: str, tag: str = "output") -> None:
        entry = self._subagent_windows.get(action)
        if not entry:
            return
        _, txt, _ = entry
        try:
            txt.configure(state="normal")
            txt.insert("end", text, tag)
            txt.see("end")
            txt.configure(state="disabled")
        except tk.TclError:
            pass

    def _subagent_mark_done(self, action: str, error: bool = False) -> None:
        entry = self._subagent_windows.get(action)
        if not entry:
            return
        win, txt, status_var = entry
        label = "⚠ error" if error else "✓ complete"
        color = "#ff6b6b" if error else "#3fb950"
        try:
            status_var.set(label)
            self._subagent_write(action, f"\n{label.upper()}\n", "done" if not error else "error")
            win.title(win.title().replace("Agent ", f"{'⚠' if error else '✓'} Agent "))
        except tk.TclError:
            pass

    def _close_subagent_windows(self) -> None:
        for action, (win, _, _) in list(self._subagent_windows.items()):
            try:
                win.destroy()
            except tk.TclError:
                pass
        self._subagent_windows.clear()

    def show_preview(self, attached: bool = False) -> None:
        if attached:
            self._show_embedded_preview()
            return
        if self.preview and self.preview.winfo_exists():
            self.preview.lift()
            return

        self.preview = tk.Toplevel(self.root)
        self.preview.title("Agentic Kali Live View")
        self.preview.attributes("-topmost", True)
        self.preview.geometry("680x520+480+40")
        frame = tk.Frame(self.preview)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_preview_panel(frame)

    def _show_embedded_preview(self) -> None:
        if self.preview_embedded and self.preview_embedded.winfo_exists():
            return
        self.normal_geometry = self.root.geometry()
        self.root.geometry("1180x520+40+40")
        self.preview_embedded = tk.Frame(self.body_frame, borderwidth=1, relief="groove")
        self.preview_embedded.pack(side="right", fill="both", expand=True, padx=(8, 0))
        self._build_preview_panel(self.preview_embedded)

    def _build_preview_panel(self, frame: tk.Frame) -> None:
        toolbar = tk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 4))
        tk.Radiobutton(toolbar, text="Transcript", variable=self.preview_mode, value="transcript", command=self._refresh_preview).pack(side="left")
        tk.Radiobutton(toolbar, text="Raw Events", variable=self.preview_mode, value="raw", command=self._refresh_preview).pack(side="left", padx=8)
        tk.Button(toolbar, text="⏹ Stop", bg="#c0392b", fg="white", font=("TkDefaultFont", 9, "bold"),
                  relief="flat", padx=8, command=self.stop).pack(side="right", padx=4)

        # Per-tool status bar
        tool_bar = tk.Frame(frame, bg="#1a1a2e", pady=4)
        tool_bar.pack(fill="x")
        tk.Label(tool_bar, textvariable=self._current_tool_label, bg="#1a1a2e", fg="#00d4ff",
                 font=("Courier", 10, "bold"), anchor="w", padx=8).pack(side="left", fill="x", expand=True)
        tk.Label(tool_bar, textvariable=self._tool_timer_var, bg="#1a1a2e", fg="#ffcc00",
                 font=("Courier", 11, "bold"), anchor="e", padx=8).pack(side="right")

        self.preview_text = tk.Text(frame, wrap="word")
        self.preview_text.tag_configure("transcript_header", lmargin1=42, lmargin2=42, rmargin=42, spacing1=10, font=("TkDefaultFont", 9, "bold"), foreground="#174ea6")
        self.preview_text.tag_configure("transcript_action", lmargin1=72, lmargin2=72, rmargin=72, spacing1=3, spacing3=8, font=("Serif", 11, "italic"))
        self.preview_text.tag_configure("transcript_result", lmargin1=72, lmargin2=72, rmargin=72, spacing1=3, spacing3=8, font=("TkDefaultFont", 10))
        self.preview_text.tag_configure("transcript_skip", elide=True)
        self.preview_text.tag_configure("raw", font=("Courier", 10), lmargin1=4, lmargin2=4, rmargin=4)
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
                self._append_preview_event(event, scroll=False, animated=False)
            self.preview_text.see("end")
        except tk.TclError:
            self.preview = None
            self.preview_text = None

    def _append_preview_event(self, event: dict[str, Any], scroll: bool = True, animated: bool = True) -> None:
        if not self.preview_text:
            return
        try:
            if self.preview_text.get("1.0", "end").strip() == "No activity yet.":
                self.preview_text.delete("1.0", "end")
            segments = self._preview_event_segments(event)
            if not segments:
                return
            for text, tag in segments:
                self.preview_text.insert("end", text, tag)
            if scroll:
                self.preview_text.see("end")
        except tk.TclError:
            self.preview = None
            self.preview_text = None

    def _preview_event_text(self, event: dict[str, Any]) -> tuple[str, str]:
        segments = self._preview_event_segments(event)
        if not segments:
            return "", "transcript_skip"
        return "".join(text for text, _tag in segments), segments[-1][1]

    def _preview_event_segments(self, event: dict[str, Any]) -> list[tuple[str, str]]:
        if self.preview_mode.get() == "raw":
            return [(f"[{event['time']}] {event['event']}\n{json.dumps(event['data'], indent=2)}\n\n", "raw")]
        text = self._natural_event_text(event)
        if not text:
            return []
        kind, label = self._transcript_kind(event)
        return [
            (f"{label}\n", "transcript_header"),
            (self._format_transcript_text(text) + "\n\n", f"transcript_{kind}"),
        ]

    def _transcript_kind(self, event: dict[str, Any]) -> tuple[str, str]:
        name = event.get("event", "")
        if name.startswith("tool.") and name != "tool.description":
            return "result", "RESULT"
        if name in {"run.completed", "gui.launch.completed"}:
            return "result", "RESULT"
        if name == "run.preparing":
            return "action", "PLAN"
        if name == "subagents.deployed":
            return "action", "⚡ SUB-AGENTS"
        if name == "action.completed":
            return "result", "✓ DONE"
        if name == "subagent.error":
            return "result", "⚠ ERROR"
        return "action", "ACTION"

    def _format_transcript_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def _type_preview_segments(self, segments: list[tuple[str, str]], scroll: bool, index: int = 0) -> None:
        if not self.preview_text or index >= len(segments):
            return
        text, tag = segments[index]
        if tag == "transcript_header":
            try:
                self.preview_text.insert("end", text, tag)
                self.root.after(80, lambda: self._type_preview_segments(segments, scroll, index + 1))
            except tk.TclError:
                self.preview = None
                self.preview_text = None
            return
        self._type_preview_lines(text.splitlines(keepends=True), tag, scroll, done=lambda: self._type_preview_segments(segments, scroll, index + 1))

    def _type_preview_lines(self, lines: list[str], tag: str, scroll: bool, index: int = 0, done=None) -> None:
        if not self.preview_text or index >= len(lines):
            if done:
                done()
            return
        try:
            self.preview_text.insert("end", lines[index], tag)
            if scroll:
                self.preview_text.see("end")
            self.root.after(220, lambda: self._type_preview_lines(lines, tag, scroll, index + 1, done))
        except tk.TclError:
            self.preview = None
            self.preview_text = None

    def _natural_event_text(self, event: dict[str, Any]) -> str:
        name = event.get("event", "")
        data = event.get("data", {})
        target = data.get("target", "the target") if isinstance(data, dict) else "the target"
        if name == "subagents.deployed":
            agents = data.get("agents", []) if isinstance(data, dict) else []
            count = data.get("count", len(agents))
            lines = [f"⚡ DEPLOYING {count} SUB-AGENT{'S' if count != 1 else ''} IN PARALLEL:"]
            for i, a in enumerate(agents, 1):
                from agentic_kali.tools.catalog import TOOLS as _CAT
                t = _CAT.get(a.get("action", ""))
                cmd = t.command if t else a.get("action", "")
                lines.append(f"  Sub-agent {i}: {cmd}  →  {a.get('target', '')}")
            return "\n".join(lines)
        if name == "action.completed":
            action = data.get("action", "tool") if isinstance(data, dict) else "tool"
            return f"✓ Sub-agent finished: {action}"
        if name == "subagent.error":
            action = data.get("action", "tool") if isinstance(data, dict) else "tool"
            return f"⚠ Sub-agent error: {action} — {data.get('error', '')}"
        if name == "run.preparing":
            actions = ", ".join(data.get("actions", [])) if isinstance(data, dict) else "selected checks"
            return f"Preparing the test plan for {target}. Agent Kal selected: {actions}."
        if name == "run.started":
            return "Starting the approved test run and recording each action for the report."
        if name == "policy.decision":
            return ""
        if name == "ai.plan.proposed":
            return ""
        if name == "action.started":
            action = data.get("action", "a tool") if isinstance(data, dict) else "a tool"
            from agentic_kali.tools.catalog import TOOLS as _CAT
            tool = _CAT.get(action)
            if tool:
                estimate = self._tool_estimate(action)
                mins, secs = divmod(estimate, 60)
                time_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
                return (
                    f"CALLING TOOL: {tool.command}\n"
                    f"Action: {action}\n"
                    f"Target: {target}\n"
                    f"Summary: {tool.summary}\n"
                    f"Category: {tool.category}  |  Estimated time: {time_str}"
                )
            return self._action_explanation(action, target)
        if name == "tool.description":
            return ""
        if name.startswith("tool."):
            tool = name.removeprefix("tool.").replace("_", " ")
            found = data.get("found", True) if isinstance(data, dict) else True
            status = "finished and returned output" if found else "was not found on this system"
            return f"{tool} {status}. Agent Kal is saving the output so it can explain the result and include it in the report."
        if name == "run.completed":
            count = data.get("findings", 0) if isinstance(data, dict) else 0
            return f"Test run completed. Agent Kal found {count} reportable item(s) and is preparing a plain-English summary."
        if name == "gui.launch.requested":
            tool = data.get("tool", "the requested tool") if isinstance(data, dict) else "the requested tool"
            return f"Opening {tool} because the operator asked Agent Kal to launch it."
        if name == "gui.launch.completed":
            message = data.get("message", "Launch completed.") if isinstance(data, dict) else "Launch completed."
            return message
        return f"{name.replace('.', ' ').title()}: {json.dumps(data, ensure_ascii=True)}"

    def _action_explanation(self, action: str, target: str) -> str:
        explanations = {
            "ping_check": "Checking that the target is reachable and that the workflow is scoped correctly.",
            "nmap_top_ports": "Opening nmap. Nmap checks common network ports, which are like doors into a system, so Agent Kal can see what services are exposed.",
            "whatweb": "Opening WhatWeb. WhatWeb identifies website software and plugins so the operator can understand what technologies may need patching.",
            "httpx_probe": "Opening httpx. httpx checks web responses, page titles, and visible technologies to map what the website exposes.",
            "nuclei_safe": "Opening nuclei with low-risk templates. Nuclei compares the target against known safe checks for common exposures and misconfigurations.",
            "sqlmap_safe": "Opening sqlmap in conservative mode. sqlmap checks whether web inputs appear vulnerable to SQL injection without dumping data.",
        }
        return f"{explanations.get(action, 'Running the selected Kali tool.')} Target: {target}."

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
            "Testing Goal": tk.Entry(window),
            "Restrictions": tk.Entry(window),
        }
        defaults = {
            "Engagement": "local-lab",
            "Targets": "127.0.0.1",
            "Actions": ",".join(SAFE_RECON_ACTIONS),
            "Approval": "recon_only",
            "Permission": "AUTHORIZED",
            "Public Targets": "false",
            "Testing Goal": "",
            "Restrictions": "",
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
                    "Testing Goal": existing.testing_goal,
                    "Restrictions": existing.restrictions,
                }
            )

        for label, entry in fields.items():
            tk.Label(window, text=label, anchor="w").pack(fill="x", padx=10, pady=(8, 0))
            entry.insert(0, defaults[label])
            entry.pack(fill="x", padx=10)

        tk.Button(window, text="Save Scope", command=lambda: self._save_scope(fields)).pack(fill="x", padx=10, pady=12)
        tk.Button(window, text="Azure Config Wizard", command=lambda: run_config_wizard()).pack(fill="x", padx=10)

    def show_security_settings(self) -> None:
        if not self.admin_mode:
            messagebox.showinfo("Agentic Kali", "Enable Admin Mode first.")
            return
        scope = self._load_scope_or_none() or Scope(
            engagement_name="local-lab",
            targets=["127.0.0.1"],
            allowed_actions=list(SAFE_RECON_ACTIONS),
        )
        window = tk.Toplevel(self.root)
        window.title("Agentic Kali Security Settings")
        window.attributes("-topmost", True)
        window.geometry("560x420+500+100")

        tk.Label(window, text="Current Scope Permissions", font=("TkDefaultFont", 12, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(window, text="Edits apply to /etc/agentic-kali/scope.json for the current authorized target.", anchor="w", wraplength=520).pack(fill="x", padx=10)

        actions = tk.Entry(window)
        actions.insert(0, ",".join(scope.allowed_actions))
        targets = tk.Entry(window)
        targets.insert(0, ",".join(scope.targets))
        intrusive = tk.BooleanVar(value=scope.intrusive_allowed)
        public_targets = tk.BooleanVar(value=scope.public_targets_allowed)
        all_terms = all_blocked_build_terms()
        guardrails = tk.Text(window, height=6, wrap="word")
        guardrails.insert("1.0", "\n".join(all_terms))

        tk.Label(window, text="Targets", anchor="w").pack(fill="x", padx=10, pady=(12, 0))
        targets.pack(fill="x", padx=10)
        tk.Label(window, text="Allowed actions", anchor="w").pack(fill="x", padx=10, pady=(12, 0))
        actions.pack(fill="x", padx=10)
        tk.Checkbutton(window, text="Intrusive tests allowed for authorized targets", variable=intrusive).pack(anchor="w", padx=10, pady=(12, 0))
        tk.Checkbutton(window, text="Public targets explicitly authorized", variable=public_targets).pack(anchor="w", padx=10)
        tk.Label(window, text="Blocked build terms — all editable in Admin Mode (one per line)", anchor="w").pack(fill="x", padx=10, pady=(12, 0))
        guardrails.pack(fill="both", expand=True, padx=10)

        tk.Label(window, text=f"Saves to {ADMIN_GUARDRAILS} and overrides all built-in terms.", anchor="w", fg="#555555", wraplength=520).pack(fill="x", padx=10, pady=(4, 0))
        tk.Button(window, text="Save Security Settings", command=lambda: self._save_security_scope(scope, targets, actions, intrusive, public_targets, guardrails)).pack(fill="x", padx=10, pady=14)

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

    def _new_chat_session(self) -> None:
        self.stop()
        self.chat.delete("1.0", "end")
        self.events = []
        self.say_queue.clear()
        self.speaking = False
        self.session = ChatSession()
        self.admin_mode = False
        self.stop_requested = False
        self.last_target = None
        self._last_suggested_target = None
        self._awaiting_tool_selection = False
        self._tool_selection_target = None
        self._awaiting_autonomous_goal = False
        self._awaiting_autonomous_target = False
        self._pending_autonomous_goal = ""
        self._close_subagent_windows()
        self.status.set("")
        self._set_thinking("")
        self.root.title("Agentic Kali")
        self.title_text.set("Agent Kal V.1")
        self.mode.set("Chat Prompt")
        self._say("Agent Kal", "New session started. What would you like to test?")

    def save_chat_transcript(self) -> None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        path = REPORTS_DIR / f"chat-transcript-{stamp}.txt"
        text = self.chat.get("1.0", "end").strip() + "\n"
        path.write_text(text, encoding="utf-8")
        self.status.set(f"Saved transcript: {path}")
        messagebox.showinfo("Agentic Kali", f"Saved chat transcript:\n{path}")
        self._gui_event("gui.transcript.saved", {"path": str(path)})

    def _save_scope(self, fields: dict[str, tk.Entry]) -> None:
        scope = Scope(
            engagement_name=fields["Engagement"].get(),
            targets=[item.strip() for item in fields["Targets"].get().split(",") if item.strip()],
            allowed_actions=[item.strip() for item in fields["Actions"].get().split(",") if item.strip()],
            approval_mode=ApprovalMode(fields["Approval"].get()),
            intrusive_allowed=False,
            signed_permission=fields["Permission"].get() == "AUTHORIZED",
            public_targets_allowed=fields["Public Targets"].get().lower() == "true",
            testing_goal=fields["Testing Goal"].get(),
            restrictions=fields["Restrictions"].get(),
        )
        self._write_scope(scope)
        messagebox.showinfo("Agentic Kali", f"Saved {DEFAULT_SCOPE}")

    def _save_security_scope(
        self,
        existing: Scope,
        targets: tk.Entry,
        actions: tk.Entry,
        intrusive: tk.BooleanVar,
        public_targets: tk.BooleanVar,
        guardrails: tk.Text,
    ) -> None:
        updated = existing.model_copy(
            update={
                "targets": [item.strip() for item in targets.get().split(",") if item.strip()],
                "allowed_actions": [item.strip() for item in actions.get().split(",") if item.strip()],
                "intrusive_allowed": intrusive.get(),
                "public_targets_allowed": public_targets.get(),
                "testing_goal": existing.testing_goal,
                "restrictions": existing.restrictions,
            }
        )
        self._write_scope(updated)
        self._write_admin_guardrails([line.strip() for line in guardrails.get("1.0", "end").splitlines() if line.strip()])
        messagebox.showinfo("Agentic Kali", f"Saved security scope:\n{DEFAULT_SCOPE}")

    def _write_admin_guardrails(self, terms: list[str]) -> None:
        ADMIN_GUARDRAILS.parent.mkdir(parents=True, exist_ok=True)
        ADMIN_GUARDRAILS.write_text(json.dumps({"all_blocked_terms": terms}, indent=2), encoding="utf-8")
        try:
            ADMIN_GUARDRAILS.chmod(0o660)
        except OSError:
            pass

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
