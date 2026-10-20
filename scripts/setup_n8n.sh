#!/usr/bin/env bash
# Imports credentials + workflows into the running n8n container and activates the workflows.
# Prerequisites: `docker compose up -d` is running and n8n/credentials.json exists (copy of credentials.template.json).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f n8n/credentials.json ]]; then
  echo "Create n8n/credentials.json first:  cp n8n/credentials.template.json n8n/credentials.json  (then edit it)" >&2
  exit 1
fi

docker compose exec -T n8n n8n import:credentials --input=/import/credentials.json
for wf in workflow-a-discovery workflow-b-matching workflow-c-notification; do
  docker compose exec -T n8n n8n import:workflow --input=/import/${wf}.json
done

# Activate (flag name differs between n8n versions; if this fails, toggle "Active" in the UI instead).
docker compose exec -T n8n n8n update:workflow --all --active=true || \
  echo "Could not auto-activate. Open http://localhost:5678 and switch each workflow to Active."

docker compose restart n8n
echo "Done. Open http://localhost:5678"
