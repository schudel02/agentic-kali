from __future__ import annotations

import json
from html import escape

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from agentic_kali.core.orchestrator import Orchestrator
from agentic_kali.policy.models import Scope
from agentic_kali.reporting.history import append_history, read_history
from agentic_kali.reporting.writer import write_reports


app = FastAPI(title="Agentic Kali")
LAST_REPORT: dict | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    report = _render_report(LAST_REPORT) if LAST_REPORT else "<p>No run yet.</p>"
    history = _render_history(read_history())
    return f"""
    <!doctype html>
    <html>
      <head>
        <title>Agentic Kali</title>
        <style>
          body {{ font-family: system-ui, sans-serif; margin: 0; color: #141414; background: #f6f7f9; }}
          main {{ max-width: 1120px; margin: 0 auto; padding: 2rem; }}
          form, .finding, .summary {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
          input, select, button {{ box-sizing: border-box; width: 100%; margin: .35rem 0 1rem; padding: .65rem; }}
          button {{ cursor: pointer; font-weight: 700; background: #111; color: white; border: 0; border-radius: 6px; }}
          code, pre {{ background: #111; color: #eee; padding: .75rem; overflow: auto; display: block; }}
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }}
          .badge {{ display: inline-block; padding: .2rem .5rem; border-radius: 999px; background: #e9eef5; font-size: .85rem; }}
          table {{ width: 100%; border-collapse: collapse; margin-top: .5rem; }}
          th, td {{ border-bottom: 1px solid #ddd; padding: .45rem; text-align: left; }}
        </style>
      </head>
      <body>
        <main>
          <h1>Agentic Kali</h1>
          <form method="post" action="/run">
            <div class="grid">
              <div>
                <label>Engagement</label>
                <input name="engagement_name" value="local-lab">
              </div>
              <div>
                <label>Targets, comma-separated</label>
                <input name="targets" value="127.0.0.1">
              </div>
            </div>
            <label>Allowed actions</label>
            <input name="allowed_actions" value="ping_check,nmap_top_ports,whatweb,httpx_probe,nuclei_safe">
            <label>Approval mode</label>
            <select name="approval_mode">
              <option value="recon_only">recon_only</option>
              <option value="approval_required">approval_required</option>
              <option value="lab_only">lab_only</option>
            </select>
          <label>Permission confirmation</label>
          <input name="permission" placeholder="Type AUTHORIZED">
          <label>
            <input style="width:auto" type="checkbox" name="public_targets_allowed" value="yes">
            Allow public targets
          </label>
          <button>Run Authorized Recon</button>
          </form>
          <h2>Activity Preview</h2>
          {report}
          <h2>History</h2>
          {history}
        </main>
      </body>
    </html>
    """


@app.post("/run")
def run(
    engagement_name: str = Form(),
    targets: str = Form(),
    allowed_actions: str = Form(),
    approval_mode: str = Form(),
    permission: str = Form(),
    public_targets_allowed: str | None = Form(default=None),
) -> RedirectResponse:
    global LAST_REPORT
    scope = Scope(
        engagement_name=engagement_name,
        targets=[item.strip() for item in targets.split(",") if item.strip()],
        allowed_actions=[item.strip() for item in allowed_actions.split(",") if item.strip()],
        approval_mode=approval_mode,
        intrusive_allowed=False,
        signed_permission=permission == "AUTHORIZED",
        public_targets_allowed=public_targets_allowed == "yes",
    )
    LAST_REPORT = Orchestrator(scope).run()
    LAST_REPORT["report_files"] = write_reports(LAST_REPORT)
    append_history(LAST_REPORT)
    return RedirectResponse("/", status_code=303)


@app.get("/api/report")
def api_report() -> dict:
    return LAST_REPORT or {}


def _render_report(report: dict) -> str:
    files = report.get("report_files", {})
    summary = f"""
    <section class="summary">
      <strong>{escape(report.get("engagement", ""))}</strong>
      <p>Targets: {escape(", ".join(report.get("targets", [])))}</p>
      <p>Files: {escape(files.get("markdown", ""))}</p>
    </section>
    """
    findings = "\n".join(_render_finding(finding) for finding in report.get("findings", []))
    activity = _render_activity(report.get("events", []))
    return summary + activity + "<h2>Findings</h2>" + (findings or "<p>No findings.</p>")


def _render_activity(events: list[dict]) -> str:
    rows = "".join(
        f"<tr><td>{escape(event.get('time', ''))}</td><td>{escape(event.get('event', ''))}</td><td><code>{escape(json.dumps(event.get('data', {}), indent=2))}</code></td></tr>"
        for event in events
    )
    return f"<table><tr><th>Time</th><th>Event</th><th>Data</th></tr>{rows}</table>"


def _render_finding(finding: dict) -> str:
    metadata = finding.get("metadata") or {}
    return f"""
    <article class="finding">
      <h3>{escape(finding.get("title", ""))}</h3>
      <p>
        <span class="badge">{escape(finding.get("severity", ""))}</span>
        <span>{escape(finding.get("target", ""))}</span>
      </p>
      {_render_metadata(metadata)}
      <pre>{escape(finding.get("evidence", ""))}</pre>
    </article>
    """


def _render_metadata(metadata: dict) -> str:
    if metadata.get("open_ports"):
        rows = "".join(
            f"<tr><td>{item['port']}</td><td>{escape(item['protocol'])}</td><td>{escape(item['state'])}</td><td>{escape(item['service'])}</td><td>{escape(item['version'])}</td></tr>"
            for item in metadata["open_ports"]
        )
        return f"<table><tr><th>Port</th><th>Proto</th><th>State</th><th>Service</th><th>Version</th></tr>{rows}</table>"

    if metadata.get("technologies"):
        badges = " ".join(f"<span class='badge'>{escape(item)}</span>" for item in metadata["technologies"])
        return f"<p>{badges}</p>"

    if metadata.get("responses"):
        return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in metadata["responses"]) + "</ul>"

    return ""


def _render_history(history: list[dict]) -> str:
    if not history:
        return "<p>No history.</p>"
    rows = "".join(
        f"<tr><td>{escape(item.get('engagement', ''))}</td><td>{escape(', '.join(item.get('targets', [])))}</td><td>{item.get('findings', 0)}</td><td>{escape(item.get('report_files', {}).get('markdown', ''))}</td></tr>"
        for item in reversed(history[-20:])
    )
    return f"<table><tr><th>Engagement</th><th>Targets</th><th>Findings</th><th>Report</th></tr>{rows}</table>"
