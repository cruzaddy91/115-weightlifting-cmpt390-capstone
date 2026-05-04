#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-dir", required=True)
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--payload", default="{}")
    parser.add_argument("--payload-stdin", action="store_true")
    args = parser.parse_args()

    event_dir = Path(args.event_dir)
    event_dir.mkdir(parents=True, exist_ok=True)

    raw_payload = args.payload
    if args.payload_stdin:
        raw_payload = sys.stdin.read().strip()

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid payload JSON: {exc}")

    timestamp = datetime.now(timezone.utc)
    event = {
        "id": uuid4().hex,
        "timestamp": timestamp.isoformat(),
        "type": args.event_type,
        "status": args.status,
        "source": args.source,
        "payload": payload,
    }

    filename = f"{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}_{args.event_type}_{event['id'][:8]}.json"
    (event_dir / filename).write_text(json.dumps(event, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
