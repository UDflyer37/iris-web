#  OhCR / DCOE interactive network topology

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.datamgmt.dcoe.dcoe_network_db import (
    create_asset_and_node,
    create_or_refresh_network_map_report,
    export_topology_document,
    generic_component_node,
    get_topology,
    import_assets_to_topology,
    import_topology_document,
    list_assets_for_network,
    merge_topology_documents,
    network_page_payload,
    promote_node_to_asset,
    save_topology,
    sync_asset_fields_from_node,
    sync_node_iocs_from_asset,
)
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.util import ac_api_case_requires, ac_case_requires, response_error, response_success

dcoe_network_blueprint = Blueprint(
    "dcoe_network",
    __name__,
    template_folder="templates",
)


def _network_payload(case, caseid: int) -> dict:
    return network_page_payload(
        case,
        caseid,
        user_login=current_user.user if current_user.is_authenticated else "",
        user_name=current_user.name if current_user.is_authenticated else "",
    )


@dcoe_network_blueprint.route("/case/dcoe/network", methods=["GET"])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_network_page(caseid, url_redir):
    if url_redir:
        return redirect(url_for("dcoe_network.dcoe_network_page", cid=caseid, redirect=True))

    case = get_case(caseid)
    form = FlaskForm()
    from app.datamgmt.dcoe.dcoe_ops_db import get_dcoe_ops_context

    dcoe_ops = get_dcoe_ops_context(case, current_user)
    return render_template("dcoe_network.html", case=case, form=form, dcoe_ops=dcoe_ops, page="dcoe_network")


@dcoe_network_blueprint.route("/case/dcoe/network/data", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_network_data(caseid):
    case = get_case(caseid)
    return response_success("", data=_network_payload(case, caseid))


@dcoe_network_blueprint.route("/case/dcoe/network/data", methods=["PUT"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_save(caseid):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    topology = payload.get("topology")
    if not isinstance(topology, dict):
        return response_error("Invalid topology payload")

    for node in topology.get("nodes", []):
        sync_node_iocs_from_asset(node, caseid)
        if payload.get("sync_assets"):
            sync_asset_fields_from_node(node, caseid)

    topology = save_topology(case, topology, current_user.user)
    track_activity("updated OhCR/DCOE network topology", caseid=caseid)
    return response_success("Topology saved", data=_network_payload(case, caseid))


@dcoe_network_blueprint.route("/case/dcoe/network/report-draft", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_report_draft(caseid):
    case = get_case(caseid)
    try:
        result = create_or_refresh_network_map_report(case, current_user.user)
    except ValueError as exc:
        return response_error(str(exc))

    track_activity("updated Network Map Status report from topology", caseid=caseid)
    return response_success(
        "Network Map Status report updated from live topology",
        data=result,
    )


@dcoe_network_blueprint.route("/case/dcoe/network/components", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_add_component(caseid):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    component_key = payload.get("component_key") or "generic"
    try:
        x = float(payload.get("x", 120))
        y = float(payload.get("y", 120))
    except (TypeError, ValueError):
        return response_error("Invalid coordinates")

    topology = get_topology(case)
    node = generic_component_node(
        component_key=component_key,
        x=x,
        y=y,
        label=payload.get("label"),
    )
    topology.setdefault("nodes", []).append(node)
    topology = save_topology(case, topology, current_user.user)
    track_activity(f"added network component '{node['label']}'", caseid=caseid)
    return response_success("Component added", data=_network_payload(case, caseid))


@dcoe_network_blueprint.route("/case/dcoe/network/assets", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_create_asset(caseid):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}

    asset_name = (payload.get("asset_name") or "").strip()
    if not asset_name:
        return response_error("Asset name is required")

    asset_type_id = payload.get("asset_type_id")
    if not asset_type_id:
        return response_error("Asset type is required")

    try:
        asset_payload, node = create_asset_and_node(
            caseid,
            current_user.id,
            asset_name=asset_name,
            asset_type_id=int(asset_type_id),
            asset_ip=(payload.get("asset_ip") or "").strip(),
            asset_description=(payload.get("asset_description") or "").strip(),
            asset_tags=(payload.get("asset_tags") or "").strip(),
            zone=payload.get("zone") or "internal",
            x=float(payload.get("x", 120)),
            y=float(payload.get("y", 120)),
            node_id=payload.get("node_id"),
            ioc_ids=payload.get("ioc_ids"),
        )
    except Exception as exc:
        return response_error(str(exc))

    topology = get_topology(case)
    if payload.get("node_id"):
        for index, entry in enumerate(topology.get("nodes", [])):
            if entry["id"] == payload["node_id"]:
                topology["nodes"][index] = node
                break
    else:
        topology.setdefault("nodes", []).append(node)

    topology = save_topology(case, topology, current_user.user)
    track_activity(f"created asset '{asset_name}' from network topology", caseid=caseid)
    return response_success(
        "Asset created",
        data={
            **_network_payload(case, caseid),
            "created_asset": asset_payload,
            "created_node": node,
        },
    )


@dcoe_network_blueprint.route("/case/dcoe/network/nodes/<node_id>/promote", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_promote_node(caseid, node_id):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    topology = get_topology(case)
    node = next((entry for entry in topology.get("nodes", []) if entry["id"] == node_id), None)
    if not node:
        return response_error("Node not found")

    try:
        result = promote_node_to_asset(
            case,
            node,
            current_user.id,
            asset_name=payload.get("asset_name"),
            asset_type_id=payload.get("asset_type_id"),
        )
    except ValueError as exc:
        return response_error(str(exc))
    except Exception as exc:
        return response_error(str(exc))

    for index, entry in enumerate(topology.get("nodes", [])):
        if entry["id"] == node_id:
            topology["nodes"][index] = result["node"]
            break

    topology = save_topology(case, topology, current_user.user)
    track_activity(f"promoted topology node to asset '{result['asset']['asset_name']}'", caseid=caseid)
    return response_success("Node promoted to asset", data=_network_payload(case, caseid))


@dcoe_network_blueprint.route("/case/dcoe/network/import-assets", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_import_assets(caseid):
    case = get_case(caseid)
    payload = request.get_json(silent=True) or {}
    asset_ids = payload.get("asset_ids")

    assets = list_assets_for_network(caseid)
    if asset_ids:
        wanted = {int(asset_id) for asset_id in asset_ids}
        assets = [asset for asset in assets if asset["asset_id"] in wanted]

    topology = get_topology(case)
    topology = import_assets_to_topology(topology, assets, current_user.user)
    topology = save_topology(case, topology, current_user.user)
    track_activity("imported assets into OhCR/DCOE network topology", caseid=caseid)
    return response_success("Assets imported", data=_network_payload(case, caseid))


@dcoe_network_blueprint.route("/case/dcoe/network/import", methods=["POST"])
@ac_api_case_requires(CaseAccessLevel.full_access)
def dcoe_network_import_file(caseid):
    case = get_case(caseid)
    payload = dict(request.get_json(silent=True) or {})
    merge = bool(payload.pop("merge", False))
    payload.pop("csrf_token", None)

    try:
        incoming = import_topology_document(payload, current_user.user)
    except ValueError as exc:
        return response_error(str(exc))

    if merge:
        existing = get_topology(case)
        topology = merge_topology_documents(existing, incoming, current_user.user)
    else:
        topology = incoming

    topology = save_topology(case, topology, current_user.user)
    track_activity("imported OhCR/DCOE network topology file", caseid=caseid)
    return response_success("Topology imported", data=_network_payload(case, caseid))


@dcoe_network_blueprint.route("/case/dcoe/network/export", methods=["GET"])
@ac_api_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_network_export(caseid):
    case = get_case(caseid)
    topology = get_topology(case)
    return response_success(
        "",
        data=export_topology_document(topology, case.name),
    )
