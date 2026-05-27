from __future__ import annotations

import json
import sys
from pathlib import Path

from agentic_kali.core.orchestrator import Orchestrator
from agentic_kali.policy.models import Scope
from agentic_kali.policy.wizard import run_scope_wizard
from agentic_kali.reporting.history import append_history
from agentic_kali.reporting.writer import write_reports
from agentic_kali.setup import run_config_wizard


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "init":
        scope = run_scope_wizard(Path(sys.argv[2]))
        print(json.dumps(scope.model_dump(mode="json"), indent=2))
        return 0

    if len(sys.argv) in (2, 3) and sys.argv[1] == "config":
        path = Path(sys.argv[2]) if len(sys.argv) == 3 else None
        config = run_config_wizard(path) if path else run_config_wizard()
        safe_config = {**config, "AZURE_OPENAI_API_KEY": "***" if config.get("AZURE_OPENAI_API_KEY") else ""}
        print(json.dumps(safe_config, indent=2))
        return 0

    if len(sys.argv) != 2:
        print("Usage: agentic-kali <scope.json>")
        print("       agentic-kali init <scope.json>")
        print("       agentic-kali config [config.json]")
        return 2

    scope_path = Path(sys.argv[1])
    scope = Scope.model_validate(json.loads(scope_path.read_text(encoding="utf-8")))
    result = Orchestrator(scope).run()
    result["report_files"] = write_reports(result)
    append_history(result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
