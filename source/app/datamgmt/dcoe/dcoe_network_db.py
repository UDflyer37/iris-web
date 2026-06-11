#  OhCR / DCOE network topology persistence

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.datamgmt.case.case_assets_db import (
    get_assets,
    get_linked_iocs_finfo_from_asset,
    set_ioc_links,
)
from app.datamgmt.case.case_iocs_db import get_detailed_iocs
from app.models import Cases

TOPOLOGY_KEY = "dcoe_network_topology"
EXPORT_FORMAT = "dcoe-network-topology"

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
        "version": 2,
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
    topology["version"] = 2
    topology["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    topology["updated_by"] = user_login
    attrs[TOPOLOGY_KEY] = topology
    case.custom_attributes = attrs
    flag_modified(case, "custom_attributes")
    db.session.commit()
    return topology


def _serialize_ioc(row) -> dict:
    return {
        "ioc_id": row.ioc_id,
        "ioc_value": row.ioc_value,
        "ioc_type": row.type_name,
        "ioc_tags": row.ioc_tags,
        "ioc_description": row.ioc_description,
    }


def list_case_iocs(caseid: int) -> list[dict]:
    return [
        {
            "ioc_id": row.ioc_id,
            "ioc_value": row.ioc_value,
            "ioc_type": row.ioc_type,
            "ioc_tags": row.ioc_tags,
        }
        for row in get_detailed_iocs(caseid)
    ]


def list_assets_for_network(caseid: int) -> list[dict]:
    assets = get_assets(caseid)
    payload = []
    for row in assets:
        linked_iocs = [_serialize_ioc(ioc) for ioc in get_linked_iocs_finfo_from_asset(row.asset_id)]
        payload.append({
            "asset_id": row.asset_id,
            "asset_uuid": str(row.asset_uuid),
            "asset_name": row.asset_name,
            "asset_ip": row.asset_ip,
            "asset_type": row.asset_type,
            "asset_tags": row.asset_tags,
            "analysis_status": row.analysis_status,
            "asset_compromise_status_id": row.asset_compromise_status_id,
            "linked_iocs": linked_iocs,
        })
    return payload


def _guess_zone(asset_type: str, asset_tags: str) -> str:
    text = f"{asset_type or ''} {asset_tags or ''}".lower()
    if any(keyword in text for keyword in ("firewall", "fw", "perimeter", "router")):
        return "perimeter"
    if "dmz" in text:
        return "dmz"
    if any(keyword in text for keyword in ("server", "dc", "domain")):
        return "server"
    if any(keyword in text for keyword in ("workstation", "endpoint", "laptop", "desktop")):
        return "endpoint"
    if "cloud" in text:
        return "cloud"
    return "internal"


def _default_services(asset: dict) -> list[dict]:
    services = []
    if asset.get("asset_type"):
        services.append({
            "port": "",
            "protocol": "tcp",
            "service": str(asset["asset_type"]).lower(),
            "state": "unknown",
        })
    return services


def asset_to_node(asset: dict, x: float, y: float) -> dict:
    zone = _guess_zone(asset.get("asset_type"), asset.get("asset_tags"))
    return {
        "id": f"asset-{asset['asset_id']}",
        "label": asset["asset_name"] or asset["asset_ip"] or f"Asset {asset['asset_id']}",
        "group": zone,
        "color": ZONE_COLORS.get(zone, ZONE_COLORS["unknown"]),
        "asset_id": asset["asset_id"],
        "asset_uuid": asset["asset_uuid"],
        "asset_ip": asset.get("asset_ip"),
        "asset_type": asset.get("asset_type"),
        "services": _default_services(asset),
        "ioc_ids": [ioc["ioc_id"] for ioc in asset.get("linked_iocs", [])],
        "x": x,
        "y": y,
        "comments": [],
    }


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
        nodes.append(asset_to_node(
            asset,
            base_x + (index % 4) * 180,
            base_y + (index // 4) * 120,
        ))

    topology["nodes"] = nodes
    topology["updated_by"] = user_login
    return topology


def sync_node_iocs_from_asset(node: dict, caseid: int) -> None:
    asset_id = node.get("asset_id")
    if not asset_id:
        return
    ioc_ids = node.get("ioc_ids") or []
    if ioc_ids:
        set_ioc_links(ioc_ids, asset_id)


def _node_display_label(entry: dict, linked_iocs: list[dict] | None = None) -> str:
    lines = [entry.get("label", entry.get("id", ""))]
    if entry.get("asset_ip"):
        lines.append(entry["asset_ip"])
    services = entry.get("services") or []
    open_services = [
        f"{svc.get('port')}/{svc.get('protocol', 'tcp')}"
        for svc in services
        if svc.get("port")
    ]
    if open_services:
        lines.append(", ".join(open_services[:4]))
    elif services:
        lines.append(services[0].get("service", ""))

    ioc_count = len(entry.get("ioc_ids") or [])
    if linked_iocs:
        ioc_count = max(ioc_count, len(linked_iocs))
    if ioc_count:
        lines.append(f"IOCs: {ioc_count}")
    return "\n".join(line for line in lines if line)


def topology_to_vis(topology: dict, assets_by_id: dict | None = None) -> dict:
    assets_by_id = assets_by_id or {}
    nodes = []
    for entry in topology.get("nodes", []):
        linked = []
        asset_id = entry.get("asset_id")
        if asset_id and asset_id in assets_by_id:
            linked = assets_by_id[asset_id].get("linked_iocs", [])
        nodes.append({
            "id": entry["id"],
            "label": _node_display_label(entry, linked),
            "x": entry.get("x"),
            "y": entry.get("y"),
            "fixed": {"x": True, "y": True} if entry.get("x") is not None else False,
            "color": entry.get("color", ZONE_COLORS["unknown"]),
            "group": entry.get("group", "unknown"),
            "asset_id": asset_id,
            "shape": "box",
            "font": {"multi": True, "size": 12},
            "title": _node_tooltip(entry, linked),
        })

    edges = []
    for entry in topology.get("edges", []):
        label_parts = []
        if entry.get("protocol"):
            label_parts.append(str(entry["protocol"]).upper())
        if entry.get("port"):
            label_parts.append(str(entry["port"]))
        if entry.get("label"):
            label_parts.append(entry["label"])
        edges.append({
            "id": entry["id"],
            "from": entry["from"],
            "to": entry["to"],
            "label": " / ".join(label_parts) if label_parts else "",
            "arrows": "to",
            "title": _edge_tooltip(entry),
        })

    return {"nodes": nodes, "edges": edges}


def _node_tooltip(entry: dict, linked_iocs: list[dict] | None = None) -> str:
    parts = [
        entry.get("label", ""),
        f"Zone: {entry.get('group', 'unknown')}",
    ]
    if entry.get("asset_ip"):
        parts.append(f"IP: {entry['asset_ip']}")
    if entry.get("asset_type"):
        parts.append(f"Type: {entry['asset_type']}")
    for service in entry.get("services") or []:
        port = service.get("port") or "?"
        proto = service.get("protocol", "tcp")
        name = service.get("service", "")
        state = service.get("state", "")
        parts.append(f"Service: {port}/{proto} {name} ({state})".strip())
    ioc_ids = entry.get("ioc_ids") or []
    if linked_iocs:
        for ioc in linked_iocs:
            parts.append(f"IOC: {ioc.get('ioc_value')} ({ioc.get('ioc_type', '')})")
    elif ioc_ids:
        parts.append(f"Linked IOC IDs: {', '.join(str(i) for i in ioc_ids)}")
    parts.append(f"Comments: {len(entry.get('comments', []))}")
    return "\n".join(parts)


def _edge_tooltip(entry: dict) -> str:
    parts = []
    if entry.get("label"):
        parts.append(entry["label"])
    if entry.get("protocol"):
        parts.append(f"Protocol: {entry['protocol']}")
    if entry.get("port"):
        parts.append(f"Port: {entry['port']}")
    parts.append(f"Comments: {len(entry.get('comments', []))}")
    return "\n".join(parts) or "Connection"


def export_topology_document(topology: dict, case_name: str) -> dict:
    return {
        "format": EXPORT_FORMAT,
        "version": 2,
        "case_name": case_name,
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "nodes": topology.get("nodes", []),
        "edges": topology.get("edges", []),
    }


def import_topology_document(payload: dict, user_login: str) -> dict:
    if payload.get("format") == EXPORT_FORMAT:
        return {
            "version": 2,
            "updated_at": None,
            "updated_by": user_login,
            "nodes": payload.get("nodes", []),
            "edges": payload.get("edges", []),
        }

    if isinstance(payload.get("nodes"), list) and isinstance(payload.get("edges"), list):
        return {
            "version": 2,
            "updated_at": None,
            "updated_by": user_login,
            "nodes": payload["nodes"],
            "edges": payload["edges"],
        }

    if isinstance(payload.get("assets"), list):
        topology = empty_topology()
        return import_assets_to_topology(topology, payload["assets"], user_login)

    raise ValueError("Unsupported import format. Use dcoe-network-topology JSON export.")


def new_node_id() -> str:
    return f"node-{uuid.uuid4().hex[:8]}"


def new_edge_id() -> str:
    return f"edge-{uuid.uuid4().hex[:8]}"
