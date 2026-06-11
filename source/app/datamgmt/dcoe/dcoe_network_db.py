#  OhCR / DCOE network topology persistence

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.datamgmt.case.case_assets_db import get_assets
from app.models import Cases

TOPOLOGY_KEY = "dcoe_network_topology"

ZONE_COLORS = {
    "perimeter": "#ff7f7f",
    "dmz": "#ffd700",
    "internal": "#97C2FC",
    "server": "#7be141",
    "endpoint": "#cdaaff",
    "cloud": "#87ceeb",
    "unknown": "#cccccc",
}


def empty_topology() -> dict:
    return {
        "version": 1,
        "updated_at": None,
        "updated_by": None,
        "nodes": [],
        "edges": [],
    }


def get_topology(case: Cases) -> dict:
    attrs = case.custom_attributes or {}
    topology = attrs.get(TOPOLOGY_KEY)
    if not isinstance(topology, dict):
        return empty_topology()
    topology.setdefault("nodes", [])
    topology.setdefault("edges", [])
    return topology


def save_topology(case: Cases, topology: dict, user_login: str) -> dict:
    attrs = dict(case.custom_attributes or {})
    topology["version"] = 1
    topology["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    topology["updated_by"] = user_login
    attrs[TOPOLOGY_KEY] = topology
    case.custom_attributes = attrs
    flag_modified(case, "custom_attributes")
    db.session.commit()
    return topology


def list_assets_for_network(caseid: int) -> list[dict]:
    assets = get_assets(caseid)
    return [
        {
            "asset_id": row.asset_id,
            "asset_uuid": str(row.asset_uuid),
            "asset_name": row.asset_name,
            "asset_ip": row.asset_ip,
            "asset_type": row.asset_type,
            "asset_tags": row.asset_tags,
            "analysis_status": row.analysis_status,
            "asset_compromise_status_id": row.asset_compromise_status_id,
        }
        for row in assets
    ]


def _guess_zone(asset_type: str, asset_tags: str) -> str:
    text = f"{asset_type or ''} {asset_tags or ''}".lower()
    if any(k in text for k in ("firewall", "fw", "perimeter", "router")):
        return "perimeter"
    if "dmz" in text:
        return "dmz"
    if any(k in text for k in ("server", "dc", "domain")):
        return "server"
    if any(k in text for k in ("workstation", "endpoint", "laptop", "desktop")):
        return "endpoint"
    if "cloud" in text:
        return "cloud"
    return "internal"


def import_assets_to_topology(topology: dict, assets: list[dict], user_login: str) -> dict:
    existing_asset_ids = {
        node.get("asset_id")
        for node in topology.get("nodes", [])
        if node.get("asset_id") is not None
    }

    nodes = list(topology.get("nodes", []))
    base_x = 80 + (len(nodes) % 6) * 40
    base_y = 80 + (len(nodes) // 6) * 90

    for index, asset in enumerate(assets):
        if asset["asset_id"] in existing_asset_ids:
            continue

        zone = _guess_zone(asset.get("asset_type"), asset.get("asset_tags"))
        nodes.append({
            "id": f"asset-{asset['asset_id']}",
            "label": asset["asset_name"] or asset["asset_ip"] or f"Asset {asset['asset_id']}",
            "group": zone,
            "color": ZONE_COLORS.get(zone, ZONE_COLORS["unknown"]),
            "asset_id": asset["asset_id"],
            "asset_uuid": asset["asset_uuid"],
            "asset_ip": asset.get("asset_ip"),
            "asset_type": asset.get("asset_type"),
            "x": base_x + (index % 4) * 160,
            "y": base_y + (index // 4) * 100,
            "comments": [],
        })

    topology["nodes"] = nodes
    topology["updated_by"] = user_login
    return topology


def topology_to_vis(topology: dict) -> dict:
    nodes = []
    for entry in topology.get("nodes", []):
        nodes.append({
            "id": entry["id"],
            "label": entry.get("label", entry["id"]),
            "x": entry.get("x"),
            "y": entry.get("y"),
            "fixed": {"x": True, "y": True} if entry.get("x") is not None else False,
            "color": entry.get("color", ZONE_COLORS["unknown"]),
            "group": entry.get("group", "unknown"),
            "asset_id": entry.get("asset_id"),
            "title": _node_tooltip(entry),
        })

    edges = []
    for entry in topology.get("edges", []):
        edges.append({
            "id": entry["id"],
            "from": entry["from"],
            "to": entry["to"],
            "label": entry.get("label", ""),
            "arrows": "to",
        })

    return {"nodes": nodes, "edges": edges}


def _node_tooltip(entry: dict) -> str:
    parts = [
        entry.get("label", ""),
        f"Zone: {entry.get('group', 'unknown')}",
    ]
    if entry.get("asset_ip"):
        parts.append(f"IP: {entry['asset_ip']}")
    if entry.get("asset_id"):
        parts.append(f"Asset ID: {entry['asset_id']}")
    comment_count = len(entry.get("comments", []))
    if comment_count:
        parts.append(f"Comments: {comment_count}")
    return "\n".join(parts)


def new_node_id() -> str:
    return f"node-{uuid.uuid4().hex[:8]}"


def new_edge_id() -> str:
    return f"edge-{uuid.uuid4().hex[:8]}"
