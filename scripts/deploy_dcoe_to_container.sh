#!/usr/bin/env bash
# Deploy OhCR/DCOE customizations into a running iriswebapp_app container.
# Usage: ./scripts/deploy_dcoe_to_container.sh [container_name]
set -euo pipefail

CONTAINER="${1:-iriswebapp_app}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Deploying DCOE app code to ${CONTAINER}..."
docker cp "${REPO_ROOT}/source/app" "${CONTAINER}:/iriswebapp/"
docker cp "${REPO_ROOT}/source/scripts/dcoe_bootstrap.py" "${CONTAINER}:/iriswebapp/scripts/"
docker cp "${REPO_ROOT}/source/scripts/dcoe_siem_feeder.py" "${CONTAINER}:/iriswebapp/scripts/" 2>/dev/null || true

echo "Installing GraphQL runtime dependencies..."
docker exec "${CONTAINER}" python3 -m pip install -q \
  'graphql-server[flask]==3.0.0b7' 'graphene==3.3' 'graphene-sqlalchemy==3.0.0rc1'

echo "Restarting ${CONTAINER}..."
docker restart "${CONTAINER}"

echo "Done. After restart, run bootstrap if needed:"
echo "  docker exec -e DCOE_BOOTSTRAP_PASSWORD='YourTeamPassword' ${CONTAINER} \\"
echo "    python3 /iriswebapp/scripts/dcoe_bootstrap.py"
echo ""
echo "Then create a NEW mission case from OhCR-DCOE-MISSION-MASTER."
