#  OhCR / DCOE interactive network topology

import json

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from app.datamgmt.case.case_db import get_case
from app.datamgmt.dcoe.dcoe_network_db import (
    export_topology_document,
    get_topology,
    import_assets_to_topology,
    import_topology_document,
    list_assets_for_network,
    list_case_iocs,
    save_topology,
    sync_node_iocs_from_asset,
    topology_to_vis,
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
    topology = get_topology(case)
    assets = list_assets_for_network(caseid)
    assets_by_id = {asset["asset_id"]: asset for asset in assets}
    return {
        "topology": topology,
        "vis": topology_to_vis(topology, assets_by_id),
        "assets": assets,
        "iocs": list_case_iocs(caseid),
    }


@dcoe_network_blueprint.route("/case/dcoe/network", methods=["GET"])
@ac_case_requires(CaseAccessLevel.read_only, CaseAccessLevel.full_access)
def dcoe_network_page(caseid, url_redir):
    if url_redir:
        return redirect(url_for("dcoe_network.dcoe_network_page", cid=caseid, redirect=True))

    case = get_case(caseid)
    form = FlaskForm()
    return render_template("dcoe_network.html", case=case, form=form)


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

    topology = save_topology(case, topology, current_user.user)
    track_activity("updated OhCR/DCOE network topology", caseid=caseid)
    return response_success("Topology saved", data=_network_payload(case, caseid))


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
    payload.pop("csrf_token", None)

    try:
        topology = import_topology_document(payload, current_user.user)
    except ValueError as exc:
        return response_error(str(exc))

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
