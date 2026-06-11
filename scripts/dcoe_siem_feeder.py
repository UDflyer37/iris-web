#!/usr/bin/env python3
"""
Push detections from SIEM / Security Onion into IRIS Alerts via the dcoe-siem-api service account.

Uses only the Python standard library (urllib) so it can run from any analyst laptop on the LAN
without the IRIS virtualenv.

Examples:
  # Test connectivity
  python3 scripts/dcoe_siem_feeder.py --config dcoe_siem_feeder.json --ping

  # Ingest a batch file (JSON Lines)
  python3 scripts/dcoe_siem_feeder.py --config dcoe_siem_feeder.json --file sample_alerts.jsonl

  # Single alert from CLI
  python3 scripts/dcoe_siem_feeder.py --config dcoe_siem_feeder.json \\
    --title "Suspicious login" --severity high --customer-id 1 \\
    --tags "ohcr,dcoe,siem" --asset "WS-001"

Environment variable overrides:
  IRIS_URL, IRIS_API_KEY, IRIS_CUSTOMER_ID
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IOC_TYPE_ALIASES = {
    "ip": "ip-src",
    "ipv4": "ip-src",
    "ipv6": "ip-src",
    "hash": "sha256",
    "md5": "md5",
    "filename": "filename",
}


def load_config(path: Path | None) -> dict:
    config: dict[str, Any] = {}
    if path and path.exists():
        with path.open(encoding="utf-8") as handle:
            config = json.load(handle)

    if os.environ.get("IRIS_URL"):
        config["iris_url"] = os.environ["IRIS_URL"].rstrip("/")
    if os.environ.get("IRIS_API_KEY"):
        config["iris_api_key"] = os.environ["IRIS_API_KEY"]
    if os.environ.get("IRIS_CUSTOMER_ID"):
        config["default_customer_id"] = int(os.environ["IRIS_CUSTOMER_ID"])

    required = ["iris_url", "iris_api_key"]
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise SystemExit(
            f"Missing config keys: {', '.join(missing)}. "
            "Copy source/app/resources/dcoe/dcoe_siem_feeder.example.json and set iris_api_key."
        )

    config.setdefault("verify_tls", True)
    config.setdefault("default_status", "New")
    config.setdefault("default_severity", "Medium")
    config.setdefault("default_source", "SIEM")
    config.setdefault("default_tags", "ohcr,dcoe,siem")
    config.setdefault("severity_ids", {
        "unspecified": 1, "informational": 2, "low": 3,
        "medium": 4, "high": 5, "critical": 6,
    })
    config.setdefault("status_ids", {
        "unspecified": 1, "new": 2, "assigned": 3, "in progress": 4,
        "pending": 5, "closed": 6, "merged": 7, "escalated": 8,
    })
    config.setdefault("ioc_type_ids", {})
    config.setdefault("asset_type_ids", {})
    return config


def api_request(config: dict, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{config['iris_url']}{path}"
    headers = {
        "X-IRIS-AUTH": config["iris_api_key"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    context = None
    if not config.get("verify_tls", True):
        context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(request, context=context, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"IRIS API error {exc.code} {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot reach IRIS at {url}: {exc}") from exc


def resolve_id(mapping: dict, key: str, label: str) -> int:
    normalized = key.strip().lower()
    if normalized not in mapping:
        raise SystemExit(f"Unknown {label} '{key}'. Known: {', '.join(mapping.keys())}")
    return int(mapping[normalized])


def build_alert_payload(record: dict, config: dict) -> dict:
    severity_key = str(record.get("severity", config["default_severity"])).lower()
    status_key = str(record.get("status", config["default_status"])).lower()

    payload = {
        "alert_title": record["title"],
        "alert_description": record.get("description", ""),
        "alert_source": record.get("source", config["default_source"]),
        "alert_source_ref": record.get("source_ref", ""),
        "alert_source_link": record.get("source_link", ""),
        "alert_tags": record.get("tags", config["default_tags"]),
        "alert_severity_id": resolve_id(config["severity_ids"], severity_key, "severity"),
        "alert_status_id": resolve_id(config["status_ids"], status_key, "status"),
        "alert_customer_id": int(record.get("customer_id", config.get("default_customer_id", 1))),
        "alert_source_event_time": record.get(
            "event_time",
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        ),
    }

    if record.get("source_content"):
        payload["alert_source_content"] = record["source_content"]

    iocs = []
    for ioc in record.get("iocs", []):
        ioc_type = str(ioc.get("type", "ip")).lower()
        ioc_type = IOC_TYPE_ALIASES.get(ioc_type, ioc_type)
        type_id = config["ioc_type_ids"].get(ioc_type)
        if not type_id:
            continue
        iocs.append({
            "ioc_value": ioc["value"],
            "ioc_type_id": int(type_id),
            "ioc_description": ioc.get("description", ""),
        })
    if iocs:
        payload["alert_iocs"] = iocs

    assets = []
    for asset in record.get("assets", []):
        type_name = asset.get("type", "Windows - Computer")
        type_id = config["asset_type_ids"].get(type_name)
        if not type_id:
            continue
        assets.append({
            "asset_name": asset["name"],
            "asset_type_id": int(type_id),
            "asset_description": asset.get("description", ""),
        })
    if assets:
        payload["alert_assets"] = assets

    return payload


def ingest_record(record: dict, config: dict, dry_run: bool) -> dict | None:
    if "title" not in record:
        raise SystemExit("Each alert record requires a 'title' field")

    payload = build_alert_payload(record, config)
    if dry_run:
        print(json.dumps(payload, indent=2))
        return None

    response = api_request(config, "POST", "/alerts/add", payload)
    if response.get("status") != "success":
        raise SystemExit(f"Unexpected IRIS response: {json.dumps(response)}")
    return response.get("data")


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON on line {line_no} of {path}: {exc}") from exc
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Feed SIEM detections into IRIS alerts")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("dcoe_siem_feeder.json"),
        help="Feeder config JSON (copy from dcoe_siem_feeder.example.json)",
    )
    parser.add_argument("--file", type=Path, help="JSON Lines file of alerts")
    parser.add_argument("--ping", action="store_true", help="Test API connectivity")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without submitting")
    parser.add_argument("--title", help="Single alert title")
    parser.add_argument("--description", default="", help="Single alert description")
    parser.add_argument("--severity", help="Single alert severity name")
    parser.add_argument("--source", help="Single alert source")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--customer-id", type=int, help="IRIS customer ID")
    parser.add_argument("--asset", help="Single asset hostname")
    parser.add_argument("--asset-type", default="Windows - Computer", help="Asset type name")
    parser.add_argument("--ioc", help="Single IOC value")
    parser.add_argument("--ioc-type", default="ip", help="IOC type name")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.ping:
        response = api_request(config, "GET", "/api/ping")
        print(json.dumps(response, indent=2))
        return 0

    records: list[dict] = []
    if args.file:
        records.extend(load_jsonl(args.file))
    if args.title:
        record = {
            "title": args.title,
            "description": args.description,
            "severity": args.severity or config["default_severity"],
            "source": args.source or config["default_source"],
            "tags": args.tags or config["default_tags"],
        }
        if args.customer_id:
            record["customer_id"] = args.customer_id
        if args.asset:
            record["assets"] = [{"name": args.asset, "type": args.asset_type}]
        if args.ioc:
            record["iocs"] = [{"value": args.ioc, "type": args.ioc_type}]
        records.append(record)

    if not records:
        parser.error("Provide --file or --title (or use --ping)")

    created = 0
    for record in records:
        result = ingest_record(record, config, args.dry_run)
        if result:
            created += 1
            alert_id = result.get("alert_id", "?")
            print(f"Created alert #{alert_id}: {result.get('alert_title', record['title'])}")

    if not args.dry_run:
        print(f"Done. {created} alert(s) submitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
