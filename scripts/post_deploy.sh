#!/usr/bin/env bash
# After `serverless deploy --stage local`: find the LocalStack API id and write ui/config.js.
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1

API_ID=$(aws --endpoint-url=http://localhost:4566 apigateway get-rest-apis \
  --query "items[?name=='local-loan-eligibility-engine'].id | [0]" --output text)

if [[ -z "$API_ID" || "$API_ID" == "None" ]]; then
  echo "Could not find the REST API. Did 'serverless deploy --stage local' succeed?" >&2
  exit 1
fi

BASE="http://localhost:4566/restapis/${API_ID}/local/_user_request_"
echo "window.APP_CONFIG = { API_BASE: '${BASE}' };" > ui/config.js
echo "API base URL: ${BASE}"
echo "Wrote ui/config.js - open http://localhost:8080"
