#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path


def load_events(event_dir: Path):
    events = []
    for path in sorted(event_dir.glob("*.json")):
        try:
            events.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    events.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return events


def load_snapshot(snapshot_path: Path):
    if not snapshot_path.exists():
        return {"available": False}
    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"available": False}


def latest_event(events, event_type):
    for event in events:
        if event.get("type") == event_type:
            return event
    return None


def latest_event_path(events, event_type, payload_key):
    event = latest_event(events, event_type)
    if not event:
        return "n/a"
    return event.get("payload", {}).get(payload_key, "n/a")


def event_counts(events):
    return Counter(event["type"] for event in events)


def status_counts(events):
    return Counter(event["status"] for event in events)


def iso_now():
    return datetime.utcnow().isoformat() + "Z"


def safe_text(value):
    if value in (None, "", []):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render_bar_rows(counter):
    items = list(counter.items())
    if not items:
        return "<p class=\"muted\">No data yet.</p>"
    max_value = max(value for _, value in items) or 1
    rows = []
    for label, value in sorted(items, key=lambda item: (-item[1], item[0])):
        width = max(8, int((value / max_value) * 100))
        rows.append(
            "<div class=\"bar-row\">"
            f"<div class=\"bar-label\">{escape(str(label))}</div>"
            f"<div class=\"bar-track\"><div class=\"bar-fill\" style=\"width:{width}%\"></div></div>"
            f"<div class=\"bar-value\">{value}</div>"
            "</div>"
        )
    return "".join(rows)


def render_markdown(events, snapshot, output_path: Path):
    counts = event_counts(events)
    statuses = status_counts(events)
    latest_doctor = latest_event(events, "doctor")
    latest_smoke = latest_event(events, "smoke")
    latest_test = latest_event(events, "test")
    latest_release = latest_event(events, "release")
    latest_backup = latest_event(events, "backup")
    latest_export = latest_event(events, "export")
    latest_demo = latest_event(events, "demo")
    latest_demo_seed = latest_event(events, "demo_seed")
    latest_demo_reset = latest_event(events, "demo_reset")
    latest_import = latest_event(events, "import")
    latest_restore = latest_event(events, "restore")

    snapshot_users = snapshot.get("users", {})
    snapshot_programs = snapshot.get("programs", {})
    snapshot_completion = snapshot.get("completion", {})
    snapshot_workouts = snapshot.get("workouts", {})
    snapshot_prs = snapshot.get("prs", {})
    latest_program_data = snapshot_programs.get("latest") or {}
    latest_workout_data = snapshot_workouts.get("latest") or {}
    latest_pr_data = snapshot_prs.get("latest") or {}

    lines = [
        "# Operations Report",
        "",
        f"Generated: {iso_now()}",
        "",
        "## Summary",
        "",
        f"- Total events: {len(events)}",
        f"- Success events: {statuses.get('success', 0)}",
        f"- Fail events: {statuses.get('fail', 0)}",
        f"- Doctor runs: {counts.get('doctor', 0)}",
        f"- Smoke runs: {counts.get('smoke', 0)}",
        f"- Test runs: {counts.get('test', 0)}",
        f"- Backups: {counts.get('backup', 0)}",
        f"- Exports: {counts.get('export', 0)}",
        f"- Releases: {counts.get('release', 0)}",
        "",
        "## Application Snapshot",
        "",
    ]

    if snapshot.get("available"):
        lines.extend([
            f"- Users: {snapshot_users.get('total', 0)} total",
            f"- Coaches: {snapshot_users.get('coaches', 0)}",
            f"- Athletes: {snapshot_users.get('athletes', 0)}",
            f"- Demo users present: {', '.join(snapshot_users.get('demo_users_present', [])) or 'none'}",
            f"- Programs: {snapshot_programs.get('total', 0)}",
            f"- Program completion records: {snapshot_completion.get('records', 0)}",
            f"- Completed exercise entries: {snapshot_completion.get('completed_entries', 0)}",
            f"- Pending exercise entries: {snapshot_completion.get('pending_entries', 0)}",
            f"- Workout logs: {snapshot_workouts.get('total', 0)}",
            f"- PR records: {snapshot_prs.get('total', 0)}",
            "",
            "### Latest App Data",
            "",
            f"- Latest program: {safe_text(latest_program_data.get('name'))}",
            f"- Latest workout athlete: {safe_text(latest_workout_data.get('athlete__username'))}",
            f"- Latest PR lift: {safe_text(latest_pr_data.get('lift_type'))}",
            "",
        ])
    else:
        lines.extend([
            "- Snapshot unavailable",
            "",
        ])

    def append_event_section(title, event, extra_lines):
        if not event:
            return
        lines.extend([
            title,
            "",
            f"- Timestamp: {event['timestamp']}",
            *extra_lines,
            "",
        ])

    if latest_doctor:
        summary = latest_doctor["payload"].get("summary", {})
        append_event_section("## Latest Doctor", latest_doctor, [
            f"- Pass: {summary.get('pass', 0)}",
            f"- Warn: {summary.get('warn', 0)}",
            f"- Fail: {summary.get('fail', 0)}",
        ])

    if latest_smoke:
        payload = latest_smoke["payload"]
        append_event_section("## Latest Smoke", latest_smoke, [
            f"- Program ID: {payload.get('program_id', 'n/a')}",
            f"- Coach Program Count: {payload.get('coach_program_count', 'n/a')}",
            f"- Sinclair Total: {payload.get('sinclair', {}).get('sinclair_total', 'n/a')}",
        ])

    if latest_test:
        append_event_section("## Latest Test", latest_test, [
            f"- Backend checks: {latest_test['payload'].get('backend_checks', 'n/a')}",
            f"- Frontend build: {latest_test['payload'].get('frontend_build', 'n/a')}",
        ])

    if latest_backup:
        payload = latest_backup["payload"]
        append_event_section("## Latest Backup", latest_backup, [
            f"- SQLite: {payload.get('sqlite_backup', 'n/a')}",
            f"- Fixture: {payload.get('fixture_backup', 'n/a')}",
        ])

    if latest_export:
        payload = latest_export["payload"]
        append_event_section("## Latest Export", latest_export, [
            f"- Export file: {payload.get('export_file', 'n/a')}",
        ])

    if latest_release:
        payload = latest_release["payload"]
        append_event_section("## Latest Release", latest_release, [
            f"- Manifest: {payload.get('manifest_file', 'n/a')}",
            f"- Export: {payload.get('export_file', 'n/a')}",
        ])

    if latest_demo or latest_demo_seed or latest_demo_reset:
        lines.extend([
            "## Demo Operations",
            "",
            f"- Rich demo build: {latest_demo['timestamp'] if latest_demo else 'n/a'}",
            f"- Demo seed: {latest_demo_seed['timestamp'] if latest_demo_seed else 'n/a'}",
            f"- Demo reset: {latest_demo_reset['timestamp'] if latest_demo_reset else 'n/a'}",
            "",
        ])

    if latest_import or latest_restore:
        lines.extend([
            "## Data Restore Operations",
            "",
            f"- Latest import: {latest_import['timestamp'] if latest_import else 'n/a'}",
            f"- Latest restore: {latest_restore['timestamp'] if latest_restore else 'n/a'}",
            "",
        ])

    lines.extend([
        "## Recent Events",
        "",
        "| Timestamp | Type | Status | Source |",
        "|---|---|---|---|",
    ])
    for event in events[:25]:
        lines.append(f"| {event['timestamp']} | {event['type']} | {event['status']} | {event['source']} |")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def metric_card(title, rows):
    body = "<ul>" + "".join(
        f"<li><strong>{escape(label)}:</strong> {escape(safe_text(value))}</li>"
        for label, value in rows
    ) + "</ul>"
    return f'<section class="card"><h2>{escape(title)}</h2>{body}</section>'


def render_html(events, snapshot, output_path: Path):
    counts = event_counts(events)
    statuses = status_counts(events)
    latest_doctor = latest_event(events, "doctor")
    latest_smoke = latest_event(events, "smoke")
    latest_test = latest_event(events, "test")
    latest_backup = latest_event(events, "backup")
    latest_export = latest_event(events, "export")
    latest_release = latest_event(events, "release")
    latest_demo = latest_event(events, "demo")

    cards = [
        metric_card("Event Summary", [
            ("Total events", len(events)),
            ("Success", statuses.get("success", 0)),
            ("Fail", statuses.get("fail", 0)),
            ("Doctor", counts.get("doctor", 0)),
            ("Smoke", counts.get("smoke", 0)),
            ("Test", counts.get("test", 0)),
        ])
    ]

    if snapshot.get("available"):
        users = snapshot.get("users", {})
        programs = snapshot.get("programs", {})
        completion = snapshot.get("completion", {})
        workouts = snapshot.get("workouts", {})
        prs = snapshot.get("prs", {})

        cards.extend([
            metric_card("Application Snapshot", [
                ("Users", users.get("total", 0)),
                ("Coaches", users.get("coaches", 0)),
                ("Athletes", users.get("athletes", 0)),
                ("Programs", programs.get("total", 0)),
                ("Completion records", completion.get("records", 0)),
                ("Workout logs", workouts.get("total", 0)),
                ("PR records", prs.get("total", 0)),
            ]),
            metric_card("Demo State", [
                ("Demo users", ", ".join(users.get("demo_users_present", [])) or "none"),
                ("Completed entries", completion.get("completed_entries", 0)),
                ("Pending entries", completion.get("pending_entries", 0)),
                ("Snatch PR rows", prs.get("by_lift", {}).get("snatch", 0)),
                ("Clean & jerk PR rows", prs.get("by_lift", {}).get("clean_jerk", 0)),
                ("Total PR rows", prs.get("by_lift", {}).get("total", 0)),
            ]),
        ])

    if latest_doctor:
        summary = latest_doctor["payload"].get("summary", {})
        cards.append(metric_card("Latest Doctor", [
            ("Timestamp", latest_doctor["timestamp"]),
            ("Pass", summary.get("pass", 0)),
            ("Warn", summary.get("warn", 0)),
            ("Fail", summary.get("fail", 0)),
        ]))

    if latest_smoke:
        payload = latest_smoke["payload"]
        cards.append(metric_card("Latest Smoke", [
            ("Timestamp", latest_smoke["timestamp"]),
            ("Program ID", payload.get("program_id", "n/a")),
            ("Coach program count", payload.get("coach_program_count", "n/a")),
            ("Sinclair total", payload.get("sinclair", {}).get("sinclair_total", "n/a")),
        ]))

    latest_ops_rows = [
        ("Latest test", latest_test["timestamp"] if latest_test else "n/a"),
        ("Latest backup", latest_backup["timestamp"] if latest_backup else "n/a"),
        ("Latest export", latest_export["timestamp"] if latest_export else "n/a"),
        ("Latest release", latest_release["timestamp"] if latest_release else "n/a"),
        ("Latest demo build", latest_demo["timestamp"] if latest_demo else "n/a"),
        ("Latest backup file", latest_event_path(events, "backup", "fixture_backup")),
    ]
    cards.append(metric_card("Operations", latest_ops_rows))

    latest_program = snapshot.get("programs", {}).get("latest") or {}
    latest_workout = snapshot.get("workouts", {}).get("latest") or {}
    latest_pr = snapshot.get("prs", {}).get("latest") or {}
    cards.append(metric_card("Latest App Data", [
        ("Program", latest_program.get("name", "n/a")),
        ("Program athlete", latest_program.get("athlete__username", "n/a")),
        ("Program coach", latest_program.get("coach__username", "n/a")),
        ("Workout athlete", latest_workout.get("athlete__username", "n/a")),
        ("PR athlete", latest_pr.get("athlete__username", "n/a")),
        ("PR lift", latest_pr.get("lift_type", "n/a")),
    ]))

    rows = "".join(
        f"<tr><td>{escape(event['timestamp'])}</td><td>{escape(event['type'])}</td><td>{escape(event['status'])}</td><td>{escape(event['source'])}</td></tr>"
        for event in events[:30]
    )

    latest_warn_count = latest_doctor.get("payload", {}).get("summary", {}).get("warn", 0) if latest_doctor else 0
    latest_fail_count = latest_doctor.get("payload", {}).get("summary", {}).get("fail", 0) if latest_doctor else 0
    tracked_programs = snapshot.get("programs", {}).get("total", 0) if snapshot.get("available") else 0

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>115 Weightlifting Operations Report</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');
    :root {{
      --neon-cyan: #52d8ff;
      --neon-blue: #2aa9ff;
      --neon-ice: #8be9ff;
      --neon-orange: #ff9f1a;
      --neon-amber: #ffc857;
      --neon-violet: #a78bfa;
      --bg: #02040d;
      --bg-deep: #040816;
      --panel: rgba(8, 18, 37, 0.92);
      --panel-strong: rgba(11, 26, 51, 0.98);
      --line: rgba(91, 169, 255, 0.24);
      --line-strong: rgba(82, 216, 255, 0.56);
      --text: #e6f7ff;
      --text-secondary: #c3dcf0;
      --muted: #9fc3d9;
      --accent: var(--neon-cyan);
      --accent-blue: var(--neon-blue);
      --accent-violet: var(--neon-violet);
      --good: #36f0c5;
      --good-soft: rgba(54, 240, 197, 0.14);
      --warn: var(--neon-amber);
      --warn-soft: rgba(255, 200, 87, 0.14);
      --fail: #ff4d6d;
      --fail-soft: rgba(255, 77, 109, 0.16);
      --shadow: 0 22px 52px rgba(2, 8, 18, 0.62);
      --scanlines: repeating-linear-gradient(
        180deg,
        rgba(139, 233, 255, 0.03) 0,
        rgba(139, 233, 255, 0.03) 1px,
        transparent 1px,
        transparent 4px
      );
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "Inter", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 10% 14%, rgba(42, 169, 255, 0.12), transparent 24%),
        radial-gradient(circle at 88% 10%, rgba(82, 216, 255, 0.12), transparent 22%),
        radial-gradient(circle at 80% 84%, rgba(167, 139, 250, 0.08), transparent 18%),
        linear-gradient(180deg, rgba(255, 159, 26, 0.035), transparent 16%),
        linear-gradient(135deg, #02040d 0%, #040816 46%, #02040d 100%);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(82, 216, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(82, 216, 255, 0.024) 1px, transparent 1px);
      background-size: 48px 48px;
      opacity: 0.32;
      mask-image: radial-gradient(circle at center, black 34%, transparent 100%);
    }}
    main {{
      width: min(1240px, calc(100% - 2rem));
      margin: 2rem auto 3rem;
    }}
    .hero {{
      background:
        linear-gradient(145deg, rgba(8, 18, 37, 0.98), rgba(5, 11, 22, 0.9)),
        var(--scanlines);
      color: var(--text);
      border-radius: 24px;
      padding: 1.6rem 1.7rem;
      box-shadow: 0 0 0 1px rgba(82, 216, 255, 0.26), var(--shadow), 0 0 28px rgba(82, 216, 255, 0.16);
      position: relative;
      overflow: hidden;
    }}
    .hero::before {{
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      padding: 1px;
      background:
        linear-gradient(135deg, rgba(82, 216, 255, 0.98), rgba(42, 169, 255, 0.82) 42%, rgba(82, 216, 255, 0.98) 74%, rgba(255, 159, 26, 0.48) 100%);
      -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
      pointer-events: none;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 100% 0%, rgba(167, 139, 250, 0.12), transparent 24%),
        radial-gradient(circle at 0% 0%, rgba(255, 159, 26, 0.12), transparent 22%),
        linear-gradient(180deg, rgba(82, 216, 255, 0.08), transparent 28%),
        var(--scanlines);
      pointer-events: none;
      opacity: 0.9;
    }}
    .hero h1 {{
      margin: 0 0 0.35rem;
      font-size: clamp(1.9rem, 3vw, 3rem);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      font-family: "Exo 2", "Inter", sans-serif;
      font-weight: 700;
      text-shadow: 0 0 12px rgba(82, 216, 255, 0.1);
    }}
    .hero p {{
      margin: 0.2rem 0;
      color: var(--text-secondary, #b9cce2);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 1rem;
      margin: 1.25rem 0;
    }}
    .card {{
      background: var(--panel);
      border-radius: 18px;
      padding: 1.05rem 1.15rem;
      box-shadow: 0 0 0 1px rgba(82, 216, 255, 0.2), var(--shadow), 0 0 18px rgba(82, 216, 255, 0.1);
      backdrop-filter: blur(10px);
      position: relative;
      overflow: hidden;
    }}
    .card::before {{
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      padding: 1px;
      background:
        linear-gradient(135deg, rgba(82, 216, 255, 0.92), rgba(42, 169, 255, 0.72) 44%, rgba(82, 216, 255, 0.92) 76%, rgba(255, 159, 26, 0.34) 100%);
      -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
      pointer-events: none;
    }}
    .card::after {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 100% 0%, rgba(167, 139, 250, 0.1), transparent 24%),
        radial-gradient(circle at 0% 0%, rgba(255, 159, 26, 0.08), transparent 20%),
        linear-gradient(180deg, rgba(82, 216, 255, 0.05), transparent 32%),
        var(--scanlines);
      pointer-events: none;
      opacity: 0.85;
    }}
    .card h2 {{
      margin: 0 0 0.8rem;
      font-size: 0.95rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent);
      font-family: "Exo 2", "Inter", sans-serif;
    }}
    .card ul {{
      margin: 0;
      padding-left: 1rem;
      line-height: 1.6;
    }}
    .card li + li {{
      margin-top: 0.18rem;
    }}
    .muted {{
      color: var(--muted);
    }}
    .charts {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1rem;
      margin: 1rem 0 1.25rem;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 130px 1fr 36px;
      gap: 0.75rem;
      align-items: center;
      margin: 0.55rem 0;
    }}
    .bar-label {{
      font-size: 0.95rem;
      color: var(--muted);
    }}
    .bar-track {{
      height: 14px;
      background: rgba(4, 11, 24, 0.96);
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid rgba(82, 216, 255, 0.12);
    }}
    .bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--accent-blue), var(--accent), var(--neon-orange));
      border-radius: 999px;
      box-shadow: 0 0 18px rgba(82, 216, 255, 0.18);
    }}
    .bar-value {{
      text-align: right;
      font-weight: 700;
    }}
    .status-grid {{
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      margin-top: 0.5rem;
    }}
    .pill {{
      border-radius: 999px;
      padding: 0.52rem 0.82rem;
      font-weight: 600;
      border: 1px solid rgba(91, 169, 255, 0.28);
      background:
        linear-gradient(180deg, rgba(12, 24, 46, 0.96), rgba(6, 14, 28, 0.98)),
        var(--scanlines);
      color: var(--text-secondary, #b9cce2);
      box-shadow: 0 0 0 1px rgba(82, 216, 255, 0.14), 0 0 16px rgba(42, 169, 255, 0.1);
    }}
    .pill.good {{
      background: var(--good-soft);
      color: var(--good);
      border-color: rgba(89, 226, 176, 0.22);
    }}
    .pill.warn {{
      background: var(--warn-soft);
      color: var(--warn);
      border-color: rgba(255, 203, 107, 0.22);
    }}
    .pill.fail {{
      background: var(--fail-soft);
      color: #ffb5c8;
      border-color: rgba(255, 111, 147, 0.22);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border-radius: 18px;
      overflow: hidden;
      box-shadow: 0 0 0 1px rgba(82, 216, 255, 0.18), var(--shadow), 0 0 18px rgba(82, 216, 255, 0.08);
    }}
    th, td {{
      padding: 0.85rem 0.9rem;
      border-bottom: 1px solid rgba(96, 139, 194, 0.14);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--accent);
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      background: rgba(82, 216, 255, 0.06);
      font-family: "Exo 2", "Inter", sans-serif;
    }}
    tbody tr:nth-child(even) {{
      background: rgba(10, 19, 35, 0.56);
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    @media (max-width: 720px) {{
      main {{
        width: min(100% - 1rem, 100%);
      }}
      .bar-row {{
        grid-template-columns: 1fr;
      }}
      .bar-value {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>115 Weightlifting Operations Report</h1>
      <p>Generated {escape(iso_now())}</p>
      <div class="status-grid">
        <span class="pill good">Success events: {statuses.get('success', 0)}</span>
        <span class="pill warn">Warnings in latest doctor: {latest_warn_count}</span>
        <span class="pill {'fail' if latest_fail_count > 0 else 'good'}">Failures in latest doctor: {latest_fail_count}</span>
        <span class="pill good">Programs tracked: {tracked_programs}</span>
      </div>
    </section>
    <section class="grid">
      {''.join(cards)}
    </section>
    <section class="charts">
      <section class="card">
        <h2>Event Type Volume</h2>
        {render_bar_rows(counts)}
      </section>
      <section class="card">
        <h2>Event Status Volume</h2>
        {render_bar_rows(statuses)}
      </section>
    </section>
    <section class="card">
      <h2>Recent Events</h2>
      <table>
        <thead><tr><th>Timestamp</th><th>Type</th><th>Status</th><th>Source</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-dir", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--markdown-out", required=True)
    parser.add_argument("--html-out", required=True)
    args = parser.parse_args()

    event_dir = Path(args.event_dir)
    event_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = Path(args.snapshot)
    markdown_out = Path(args.markdown_out)
    html_out = Path(args.html_out)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    html_out.parent.mkdir(parents=True, exist_ok=True)

    events = load_events(event_dir)
    snapshot = load_snapshot(snapshot_path)
    render_markdown(events, snapshot, markdown_out)
    render_html(events, snapshot, html_out)


if __name__ == "__main__":
    main()
