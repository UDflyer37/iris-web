#  OhCR / DCOE network topology persistence

from __future__ import annotations

import datetime
import uuid

from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.datamgmt.case.case_assets_db import (
    create_asset,
    get_asset,
    get_asset_type_id,
    get_assets,
    get_assets_types,
    get_linked_iocs_finfo_from_asset,
    get_unspecified_analysis_status_id,
    set_ioc_links,
    update_asset,
)
from app.schema.marshables import CaseAssetsSchema
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

ZONE_LABELS = {
    "perimeter": "Perimeter",
    "dmz": "DMZ",
    "internal": "Internal",
    "server": "Server",
    "endpoint": "Endpoint",
    "cloud": "Cloud",
    "unknown": "Unknown",
}

MOE_COVERAGE_TARGET = 95

COMPROMISE_LABELS = {
    0: "To be determined",
    1: "Compromised",
    2: "Not compromised",
    3: "Unknown",
}

CRITICALITY_LEVELS = ["low", "medium", "high", "critical"]

TRAFFIC_TYPES = ["allowed", "monitored", "blocked", "unknown"]

SERVICE_PRESETS = [
    {"label": "HTTPS (443)", "port": "443", "protocol": "tcp", "service": "https", "state": "open"},
    {"label": "HTTP (80)", "port": "80", "protocol": "tcp", "service": "http", "state": "open"},
    {"label": "RDP (3389)", "port": "3389", "protocol": "tcp", "service": "rdp", "state": "open"},
    {"label": "SMB (445)", "port": "445", "protocol": "tcp", "service": "smb", "state": "open"},
    {"label": "SSH (22)", "port": "22", "protocol": "tcp", "service": "ssh", "state": "open"},
    {"label": "DNS (53)", "port": "53", "protocol": "udp", "service": "dns", "state": "open"},
    {"label": "LDAP (389)", "port": "389", "protocol": "tcp", "service": "ldap", "state": "open"},
    {"label": "Kerberos (88)", "port": "88", "protocol": "tcp", "service": "kerberos", "state": "open"},
    {"label": "SMTP (25)", "port": "25", "protocol": "tcp", "service": "smtp", "state": "open"},
]


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
        compromise_id = row.asset_compromise_status_id
        payload.append({
            "asset_id": row.asset_id,
            "asset_uuid": str(row.asset_uuid),
            "asset_name": row.asset_name,
            "asset_ip": row.asset_ip,
            "asset_type": row.asset_type,
            "asset_tags": row.asset_tags,
            "analysis_status": row.analysis_status,
            "asset_compromise_status_id": compromise_id,
            "compromise_label": COMPROMISE_LABELS.get(compromise_id, "Unknown"),
            "suggested_zone": guess_zone(row.asset_type, row.asset_tags),
            "ioc_count": len(linked_iocs),
            "linked_iocs": linked_iocs,
        })
    return payload


def guess_zone(asset_type: str, asset_tags: str) -> str:
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


def _empty_node_metadata() -> dict:
    return {
        "hostname": "",
        "role": "",
        "criticality": "medium",
        "notes": "",
    }


def asset_to_node(asset: dict, x: float, y: float) -> dict:
    zone = guess_zone(asset.get("asset_type"), asset.get("asset_tags"))
    label = asset["asset_name"] or asset["asset_ip"] or f"Asset {asset['asset_id']}"
    return {
        "id": f"asset-{asset['asset_id']}",
        "label": label,
        "group": zone,
        "color": ZONE_COLORS.get(zone, ZONE_COLORS["unknown"]),
        "asset_id": asset["asset_id"],
        "asset_uuid": asset["asset_uuid"],
        "asset_ip": asset.get("asset_ip"),
        "asset_type": asset.get("asset_type"),
        "component_type": None,
        "services": _default_services(asset),
        "ioc_ids": [ioc["ioc_id"] for ioc in asset.get("linked_iocs", [])],
        "x": x,
        "y": y,
        "comments": [],
        **_empty_node_metadata(),
        "hostname": asset.get("asset_ip") or "",
        "role": asset.get("asset_type") or "",
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
    set_ioc_links(ioc_ids, asset_id)


def _node_display_label(entry: dict, linked_iocs: list[dict] | None = None) -> str:
    lines = [entry.get("label", entry.get("id", ""))]
    if entry.get("role"):
        lines.append(entry["role"])
    if entry.get("hostname") and entry.get("hostname") != entry.get("asset_ip"):
        lines.append(entry["hostname"])
    if entry.get("asset_ip"):
        lines.append(entry["asset_ip"])
    if entry.get("criticality") in ("high", "critical"):
        lines.append(f"⚠ {entry['criticality'].upper()}")
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
        shape = "box"
        if entry.get("component_type") in ("firewall", "router"):
            shape = "diamond"
        elif entry.get("component_type") in ("cloud_service",):
            shape = "ellipse"

        border_color = "#546e7a"
        border_width = 2
        if asset_id and asset_id in assets_by_id:
            asset_row = assets_by_id[asset_id]
            compromise_id = asset_row.get("asset_compromise_status_id")
            if compromise_id == 1:
                border_color = "#c62828"
                border_width = 3
            elif compromise_id == 2:
                border_color = "#2e7d32"
                border_width = 3
            analysis = (asset_row.get("analysis_status") or "").lower()
            if analysis and "progress" in analysis:
                border_color = "#ef6c00"
        elif entry.get("asset_id"):
            border_color = "#1b5e20"

        node_vis = {
            "id": entry["id"],
            "label": _node_display_label(entry, linked),
            "x": entry.get("x"),
            "y": entry.get("y"),
            "color": {
                "background": entry.get("color", ZONE_COLORS["unknown"]),
                "border": border_color,
                "highlight": {"background": entry.get("color", ZONE_COLORS["unknown"]), "border": "#111"},
            },
            "group": entry.get("group", "unknown"),
            "asset_id": asset_id,
            "shape": shape,
            "font": {"multi": True, "size": 12},
            "title": _node_tooltip(entry, linked),
            "borderWidth": border_width,
            "compromise_status_id": (
                assets_by_id[asset_id].get("asset_compromise_status_id") if asset_id and asset_id in assets_by_id else None
            ),
        }
        if entry.get("x") is not None and entry.get("y") is not None:
            node_vis["fixed"] = False
        nodes.append(node_vis)

    edges = []
    for entry in topology.get("edges", []):
        label_parts = []
        if entry.get("protocol"):
            label_parts.append(str(entry["protocol"]).upper())
        if entry.get("port"):
            label_parts.append(str(entry["port"]))
        if entry.get("label"):
            label_parts.append(entry["label"])
        if entry.get("traffic_type") and entry.get("traffic_type") != "unknown":
            label_parts.append(entry["traffic_type"])
        traffic = entry.get("traffic_type") or "allowed"
        edge_color = "#c62828" if traffic == "blocked" else "#ef6c00" if traffic == "monitored" else "#5c6bc0"
        edges.append({
            "id": entry["id"],
            "from": entry["from"],
            "to": entry["to"],
            "label": " / ".join(label_parts) if label_parts else "",
            "arrows": "to",
            "title": _edge_tooltip(entry),
            "color": {"color": edge_color, "highlight": edge_color},
            "dashes": traffic == "blocked",
        })

    return {"nodes": nodes, "edges": edges}


def _node_tooltip(entry: dict, linked_iocs: list[dict] | None = None) -> str:
    parts = [
        entry.get("label", ""),
        f"Zone: {ZONE_LABELS.get(entry.get('group', 'unknown'), entry.get('group', 'unknown'))}",
    ]
    if entry.get("component_type"):
        preset = COMPONENT_PRESETS.get(entry["component_type"], {})
        parts.append(f"Component: {preset.get('label', entry['component_type'])}")
    if entry.get("role"):
        parts.append(f"Role: {entry['role']}")
    if entry.get("hostname"):
        parts.append(f"Hostname: {entry['hostname']}")
    if entry.get("criticality"):
        parts.append(f"Criticality: {entry['criticality']}")
    if entry.get("notes"):
        parts.append(f"Notes: {entry['notes'][:120]}")
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
    if entry.get("traffic_type"):
        parts.append(f"Traffic: {entry['traffic_type']}")
    if entry.get("protocol"):
        parts.append(f"Protocol: {entry['protocol']}")
    if entry.get("port"):
        parts.append(f"Port: {entry['port']}")
    if entry.get("bandwidth"):
        parts.append(f"Bandwidth: {entry['bandwidth']}")
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


def compute_network_coverage(caseid: int, topology: dict, assets: list[dict]) -> dict:
    placed_asset_ids = {
        node.get("asset_id")
        for node in topology.get("nodes", [])
        if node.get("asset_id") is not None
    }
    total = len(assets)
    mapped = len(placed_asset_ids)
    unmapped = [asset for asset in assets if asset["asset_id"] not in placed_asset_ids]
    pct = round((mapped / total) * 100, 1) if total else 0.0
    nodes_total = len(topology.get("nodes", []))
    diagram_only = max(0, nodes_total - mapped)
    zones: dict[str, int] = {}
    for node in topology.get("nodes", []):
        zone = node.get("group") or "unknown"
        zones[zone] = zones.get(zone, 0) + 1

    return {
        "total_assets": total,
        "mapped_assets": mapped,
        "unmapped_assets": len(unmapped),
        "coverage_pct": pct,
        "moe_target_pct": MOE_COVERAGE_TARGET,
        "moe_met": pct >= MOE_COVERAGE_TARGET,
        "nodes_total": nodes_total,
        "diagram_only_nodes": diagram_only,
        "edges_total": len(topology.get("edges", [])),
        "zones": zones,
        "updated_at": topology.get("updated_at"),
        "updated_by": topology.get("updated_by"),
        "unmapped_list": [
            {
                "asset_id": asset["asset_id"],
                "asset_name": asset.get("asset_name") or f"Asset {asset['asset_id']}",
                "asset_ip": asset.get("asset_ip") or "",
                "asset_type": asset.get("asset_type") or "",
                "suggested_zone": guess_zone(asset.get("asset_type"), asset.get("asset_tags")),
            }
            for asset in unmapped[:40]
        ],
    }


def build_network_map_report_prefill(case, caseid: int, user_login: str) -> dict:
    topology = get_topology(case)
    assets = list_assets_for_network(caseid)
    coverage = compute_network_coverage(caseid, topology, assets)
    network_url = f"/case/dcoe/network?cid={caseid}"

    gaps = ", ".join(
        entry["asset_name"] for entry in coverage["unmapped_list"][:12]
    )
    if coverage["unmapped_assets"] > 12:
        gaps = f"{gaps} (+{coverage['unmapped_assets'] - 12} more)"
    if not gaps:
        gaps = "None — all case assets are on the diagram"

    physical_status = "Not started"
    logical_status = "Not started"
    overlay_status = "Not started"
    if coverage["nodes_total"] > 0:
        logical_status = "In progress"
        physical_status = "In progress"
    if coverage["edges_total"] > 0:
        overlay_status = "In progress"
    if coverage["moe_met"]:
        physical_status = "Complete"
        logical_status = "Complete"
        overlay_status = "Complete" if coverage["edges_total"] else "In progress"

    verified = "No"
    if coverage["moe_met"]:
        verified = "Yes"
    elif coverage["coverage_pct"] >= 50:
        verified = "Partial"

    return {
        "assets_mapped": f"{coverage['mapped_assets']} / {coverage['total_assets']}",
        "last_updated_by": coverage.get("updated_by") or user_login,
        "physical_status": physical_status,
        "physical_evidence": network_url,
        "logical_status": logical_status,
        "logical_evidence": network_url,
        "overlay_status": overlay_status,
        "netad_verified": verified,
        "coverage_pct": f"{coverage['coverage_pct']}%",
        "gaps": gaps,
    }


def merge_topology_documents(existing: dict, incoming: dict, user_login: str) -> dict:
    merged = {
        "version": 2,
        "updated_at": None,
        "updated_by": user_login,
        "nodes": list(existing.get("nodes", [])),
        "edges": list(existing.get("edges", [])),
    }
    node_ids = {node["id"] for node in merged["nodes"]}
    for node in incoming.get("nodes", []):
        if node.get("id") not in node_ids:
            merged["nodes"].append(node)
            node_ids.add(node["id"])
    edge_ids = {edge["id"] for edge in merged["edges"]}
    for edge in incoming.get("edges", []):
        if edge.get("id") not in edge_ids:
            merged["edges"].append(edge)
            edge_ids.add(edge["id"])
    return merged


def create_or_refresh_network_map_report(case, user_login: str) -> dict:
    from app.datamgmt.dcoe.dcoe_report_db import (
        create_report_draft,
        list_report_drafts,
        resolve_template_by_key,
        update_report_draft,
    )

    report = resolve_template_by_key("network_map_status")
    if not report:
        raise ValueError("Network Map Status report template not found. Run dcoe bootstrap.")

    prefill = build_network_map_report_prefill(case, case.case_id, user_login)
    existing = next(
        (
            draft
            for draft in list_report_drafts(case)
            if draft.get("report_template_key") == "network_map_status"
        ),
        None,
    )

    if existing:
        form_data = dict(existing.get("form_data") or {})
        form_data.update(prefill)
        draft = update_report_draft(
            case,
            existing["id"],
            form_data=form_data,
            user_login=user_login,
        )
        created = False
    else:
        draft = create_report_draft(
            case,
            report_template_id=report.id,
            task_id=None,
            user_login=user_login,
        )
        form_data = dict(draft.get("form_data") or {})
        form_data.update(prefill)
        draft = update_report_draft(
            case,
            draft["id"],
            form_data=form_data,
            user_login=user_login,
        )
        created = True

    workspace_url = f"/case/dcoe/reports?cid={case.case_id}&draft_id={draft['id']}"
    return {
        "draft": draft,
        "created": created,
        "workspace_url": workspace_url,
        "prefill": prefill,
    }


def network_page_payload(case, caseid: int, *, user_login: str, user_name: str) -> dict:
    topology = get_topology(case)
    assets = list_assets_for_network(caseid)
    assets_by_id = {asset["asset_id"]: asset for asset in assets}
    coverage = compute_network_coverage(caseid, topology, assets)

    return {
        "topology": topology,
        "vis": topology_to_vis(topology, assets_by_id),
        "assets": assets,
        "iocs": list_case_iocs(caseid),
        "asset_types": list_asset_types_for_network(),
        "components": list_component_presets(),
        "component_categories": list_component_categories(),
        "service_presets": SERVICE_PRESETS,
        "criticality_levels": CRITICALITY_LEVELS,
        "traffic_types": TRAFFIC_TYPES,
        "coverage": coverage,
        "zone_legend": [
            {"id": zone, "label": ZONE_LABELS.get(zone, zone.title()), "color": color}
            for zone, color in ZONE_COLORS.items()
            if zone != "unknown"
        ],
        "current_user": {
            "login": user_login,
            "name": user_name,
        },
        "guess_zone_fn": "client",
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


COMPONENT_PRESETS = {
    "firewall": {
        "label": "Firewall",
        "group": "perimeter",
        "category": "Perimeter",
        "icon": "fa-shield-halved",
        "description": "Edge firewall controlling north-south traffic",
        "asset_type_hint": "firewall",
        "default_services": [{"port": "443", "protocol": "tcp", "service": "https", "state": "filtered"}],
    },
    "router": {
        "label": "Router",
        "group": "perimeter",
        "category": "Perimeter",
        "icon": "fa-route",
        "description": "Core or edge router",
        "asset_type_hint": "router",
        "default_services": [],
    },
    "vpn_gateway": {
        "label": "VPN Gateway",
        "group": "perimeter",
        "category": "Perimeter",
        "icon": "fa-lock",
        "description": "Remote access VPN concentrator",
        "asset_type_hint": "router",
        "default_services": [{"port": "443", "protocol": "udp", "service": "ipsec", "state": "open"}],
    },
    "load_balancer": {
        "label": "Load Balancer",
        "group": "dmz",
        "category": "Perimeter",
        "icon": "fa-scale-balanced",
        "description": "DMZ load balancer or reverse proxy front-end",
        "asset_type_hint": "server",
        "default_services": [{"port": "443", "protocol": "tcp", "service": "https", "state": "open"}],
    },
    "switch": {
        "label": "Switch",
        "group": "internal",
        "category": "Internal",
        "icon": "fa-network-wired",
        "description": "Layer-2/Layer-3 switch",
        "asset_type_hint": "switch",
        "default_services": [],
    },
    "dns_server": {
        "label": "DNS Server",
        "group": "server",
        "category": "Server",
        "icon": "fa-globe",
        "description": "Internal or external DNS resolver",
        "asset_type_hint": "server",
        "default_services": [{"port": "53", "protocol": "udp", "service": "dns", "state": "open"}],
    },
    "server": {
        "label": "Server",
        "group": "server",
        "category": "Server",
        "icon": "fa-server",
        "description": "Generic application or file server",
        "asset_type_hint": "server",
        "default_services": [],
    },
    "domain_controller": {
        "label": "Domain Controller",
        "group": "server",
        "category": "Server",
        "icon": "fa-sitemap",
        "description": "Active Directory domain controller",
        "asset_type_hint": "server",
        "default_services": [
            {"port": "88", "protocol": "tcp", "service": "kerberos", "state": "open"},
            {"port": "389", "protocol": "tcp", "service": "ldap", "state": "open"},
        ],
        "default_role": "Domain Controller",
        "default_criticality": "critical",
    },
    "workstation": {
        "label": "Workstation",
        "group": "endpoint",
        "category": "Endpoint",
        "icon": "fa-desktop",
        "description": "User endpoint or analyst workstation",
        "asset_type_hint": "windows",
        "default_services": [],
    },
    "cloud_service": {
        "label": "Cloud Service",
        "group": "cloud",
        "category": "Cloud",
        "icon": "fa-cloud",
        "description": "SaaS or IaaS service boundary",
        "asset_type_hint": "cloud",
        "default_services": [{"port": "443", "protocol": "tcp", "service": "https", "state": "open"}],
    },
    "generic": {
        "label": "Network Component",
        "group": "unknown",
        "category": "Other",
        "icon": "fa-circle-nodes",
        "description": "Unclassified diagram placeholder",
        "asset_type_hint": "account",
        "default_services": [],
    },
}


def list_component_presets() -> list[dict]:
    rows = []
    for key, preset in COMPONENT_PRESETS.items():
        rows.append({
            "key": key,
            **preset,
            "zone_label": ZONE_LABELS.get(preset["group"], preset["group"].title()),
        })
    category_order = ["Perimeter", "Internal", "Server", "Endpoint", "Cloud", "Other"]
    rows.sort(key=lambda row: (category_order.index(row["category"]), row["label"]))
    return rows


def list_component_categories() -> list[str]:
    seen = []
    for preset in COMPONENT_PRESETS.values():
        cat = preset.get("category", "Other")
        if cat not in seen:
            seen.append(cat)
    return seen


def list_asset_types_for_network() -> list[dict]:
    return [{"id": asset_id, "name": asset_name} for asset_id, asset_name in get_assets_types()]


def default_asset_type_id(hint: str | None = None) -> int | None:
    if hint:
        match = get_asset_type_id(hint.lower())
        if match:
            return match.asset_id
    types = get_assets_types()
    return types[0][0] if types else None


def generic_component_node(
    component_key: str,
    x: float,
    y: float,
    label: str | None = None,
) -> dict:
    preset = COMPONENT_PRESETS.get(component_key, COMPONENT_PRESETS["generic"])
    node_label = label or preset["label"]
    zone = preset["group"]
    services = [dict(entry) for entry in preset.get("default_services", [])]
    meta = _empty_node_metadata()
    meta["role"] = preset.get("default_role") or preset["label"]
    meta["criticality"] = preset.get("default_criticality") or "medium"
    return {
        "id": new_node_id(),
        "label": node_label,
        "group": zone,
        "color": ZONE_COLORS.get(zone, ZONE_COLORS["unknown"]),
        "component_type": component_key,
        "asset_id": None,
        "asset_uuid": None,
        "asset_ip": "",
        "asset_type": preset.get("asset_type_hint"),
        "services": services,
        "ioc_ids": [],
        "x": x,
        "y": y,
        "comments": [],
        **meta,
    }


def _serialize_asset_for_network(asset) -> dict:
    from app.models import AssetsType

    linked_iocs = [_serialize_ioc(ioc) for ioc in get_linked_iocs_finfo_from_asset(asset.asset_id)]
    asset_type_name = None
    if asset.asset_type_id:
        asset_type = AssetsType.query.filter(AssetsType.asset_id == asset.asset_type_id).first()
        asset_type_name = asset_type.asset_name if asset_type else None
    return {
        "asset_id": asset.asset_id,
        "asset_uuid": str(asset.asset_uuid),
        "asset_name": asset.asset_name,
        "asset_ip": asset.asset_ip,
        "asset_type": asset_type_name,
        "asset_tags": asset.asset_tags,
        "analysis_status": None,
        "asset_compromise_status_id": asset.asset_compromise_status_id,
        "linked_iocs": linked_iocs,
    }


def create_asset_and_node(
    caseid: int,
    user_id: int,
    *,
    asset_name: str,
    asset_type_id: int,
    asset_ip: str = "",
    asset_description: str = "",
    asset_tags: str = "",
    zone: str = "internal",
    x: float | None = None,
    y: float | None = None,
    node_id: str | None = None,
    ioc_ids: list[int] | None = None,
) -> tuple[dict, dict]:
    """Create a case asset and place (or update) it on the topology diagram."""
    request_data = {
        "asset_name": asset_name,
        "asset_type_id": asset_type_id,
        "asset_ip": asset_ip or "",
        "asset_description": asset_description or "",
        "asset_tags": asset_tags or "",
        "analysis_status_id": get_unspecified_analysis_status_id(),
    }
    schema = CaseAssetsSchema()
    schema.is_unique_for_cid(caseid, request_data)
    asset = schema.load(request_data)
    asset = create_asset(asset=asset, caseid=caseid, user_id=user_id)

    if ioc_ids:
        set_ioc_links(ioc_ids, asset.asset_id)

    asset_payload = _serialize_asset_for_network(asset)
    topology = None

    if node_id:
        topology = get_topology(Cases.query.filter(Cases.case_id == caseid).first())
        node = next((entry for entry in topology.get("nodes", []) if entry["id"] == node_id), None)
        if node:
            node["label"] = asset_name
            node["asset_id"] = asset.asset_id
            node["asset_uuid"] = str(asset.asset_uuid)
            node["asset_ip"] = asset_ip
            node["asset_type"] = asset_payload["asset_type"]
            node["group"] = zone
            node["color"] = ZONE_COLORS.get(zone, ZONE_COLORS["unknown"])
            if x is not None:
                node["x"] = x
            if y is not None:
                node["y"] = y
            if ioc_ids:
                node["ioc_ids"] = list(ioc_ids)
            return asset_payload, node

    node = asset_to_node(
        asset_payload,
        x if x is not None else 120,
        y if y is not None else 120,
    )
    node["group"] = zone
    node["color"] = ZONE_COLORS.get(zone, ZONE_COLORS["unknown"])
    if ioc_ids:
        node["ioc_ids"] = list(ioc_ids)
    return asset_payload, node


def promote_node_to_asset(
    case: Cases,
    node: dict,
    user_id: int,
    *,
    asset_name: str | None = None,
    asset_type_id: int | None = None,
) -> dict:
    if node.get("asset_id"):
        raise ValueError("Node is already linked to an asset")

    component_key = node.get("component_type") or "generic"
    preset = COMPONENT_PRESETS.get(component_key, COMPONENT_PRESETS["generic"])
    resolved_name = asset_name or node.get("label") or preset["label"]
    resolved_type_id = asset_type_id or default_asset_type_id(preset.get("asset_type_hint"))
    if not resolved_type_id:
        raise ValueError("No asset types configured in IRIS")

    asset_payload, updated_node = create_asset_and_node(
        case.case_id,
        user_id,
        asset_name=resolved_name,
        asset_type_id=resolved_type_id,
        asset_ip=node.get("asset_ip") or "",
        zone=node.get("group") or "internal",
        x=node.get("x"),
        y=node.get("y"),
        node_id=node["id"],
        ioc_ids=node.get("ioc_ids"),
    )
    return {"asset": asset_payload, "node": updated_node}


def sync_asset_fields_from_node(node: dict, caseid: int) -> bool:
    asset_id = node.get("asset_id")
    if not asset_id:
        return False

    asset = get_asset(asset_id, caseid)
    if not asset:
        return False

    update_asset(
        asset_name=node.get("label") or asset.asset_name,
        asset_description=asset.asset_description,
        asset_ip=node.get("asset_ip") or asset.asset_ip,
        asset_info=asset.asset_info,
        asset_domain=asset.asset_domain,
        asset_compromise_status_id=asset.asset_compromise_status_id,
        asset_type=asset.asset_type_id,
        asset_id=asset_id,
        caseid=caseid,
        analysis_status=asset.analysis_status_id,
        asset_tags=asset.asset_tags,
    )
    return True
