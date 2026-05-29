from __future__ import annotations

import shutil
import subprocess
import time
import os
import signal
import threading
from typing import Callable

_ACTIVE_PROCESSES: set[subprocess.Popen] = set()
_PROCESS_LOCK = threading.Lock()


class CommandResult:
    def __init__(self, command: list[str], found: bool, returncode: int | None, stdout: str, stderr: str) -> None:
        self.command = command
        self.found = found
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def as_dict(self) -> dict:
        return {
            "command": self.command,
            "found": self.found,
            "returncode": self.returncode,
            "stdout": self.stdout[-8000:],
            "stderr": self.stderr[-4000:],
        }


def run_command(
    command: list[str],
    timeout: int = 120,
    should_stop: Callable[[], bool] | None = None,
) -> CommandResult:
    if not shutil.which(command[0]):
        return CommandResult(command, False, None, "", f"{command[0]} not installed")

    started = time.monotonic()
    popen_kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True}
    if os.name == "posix":
        popen_kwargs["preexec_fn"] = os.setsid
    elif os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(command, **popen_kwargs)
    with _PROCESS_LOCK:
        _ACTIVE_PROCESSES.add(process)
    try:
        while process.poll() is None:
            if should_stop and should_stop():
                _stop_process(process)
                try:
                    stdout, stderr = process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    _kill_process(process)
                    stdout, stderr = process.communicate()
                return CommandResult(command, True, process.returncode, stdout, stderr or "stopped by operator")
            if time.monotonic() - started > timeout:
                _kill_process(process)
                stdout, stderr = process.communicate()
                return CommandResult(command, True, process.returncode, stdout, stderr or "command timed out")
            time.sleep(0.1)

        stdout, stderr = process.communicate()
        return CommandResult(command, True, process.returncode, stdout, stderr)
    finally:
        with _PROCESS_LOCK:
            _ACTIVE_PROCESSES.discard(process)


def stop_all_commands() -> None:
    with _PROCESS_LOCK:
        processes = list(_ACTIVE_PROCESSES)
    for process in processes:
        if process.poll() is None:
            _stop_process(process)


def _stop_process(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        pass


def _kill_process(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass

