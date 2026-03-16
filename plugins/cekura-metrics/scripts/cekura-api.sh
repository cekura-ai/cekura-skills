#!/bin/bash
# Cekura API helper for metrics operations
# Usage: source this file or call functions directly

# --- Configuration ---
CEKURA_BASE_URL="https://api.cekura.ai"
METRICS_URL="${CEKURA_BASE_URL}/test_framework/v1/metrics"
CALLS_URL="${CEKURA_BASE_URL}/observability/v1/call-logs-external"
AGENTS_URL="${CEKURA_BASE_URL}/test_framework/v1/agents"

# Resolve API key: env var first, then .claude/cekura-metrics.local.md frontmatter
resolve_api_key() {
  if [ -n "$CEKURA_API_KEY" ]; then
    echo "$CEKURA_API_KEY"
    return
  fi
  local settings_file=".claude/cekura-metrics.local.md"
  if [ -f "$settings_file" ]; then
    grep -m1 '^api_key:' "$settings_file" | sed 's/^api_key:\s*//' | tr -d '[:space:]'
    return
  fi
  echo ""
}

# --- Agents ---

get_agent() {
  local api_key
  api_key=$(resolve_api_key)
  local agent_id="$1"
  curl -s -X GET "${AGENTS_URL}/${agent_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

get_agent_description() {
  local api_key
  api_key=$(resolve_api_key)
  local agent_id="$1"
  curl -s -X GET "${AGENTS_URL}/${agent_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('description','') or d.get('agent_description',''))" 2>/dev/null
}

list_agents() {
  local api_key
  api_key=$(resolve_api_key)
  local query_params="$1"
  curl -s -X GET "${AGENTS_URL}/?${query_params}" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

# --- Metrics CRUD ---

create_metric() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"
  curl -s -X POST "${METRICS_URL}/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

get_metric() {
  local api_key
  api_key=$(resolve_api_key)
  local metric_id="$1"
  curl -s -X GET "${METRICS_URL}/${metric_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

list_metrics() {
  local api_key
  api_key=$(resolve_api_key)
  local query_params="$1"  # e.g., "agent=12414" or "project=5"
  curl -s -X GET "${METRICS_URL}/?${query_params}" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

update_metric() {
  local api_key
  api_key=$(resolve_api_key)
  local metric_id="$1"
  local payload="$2"
  curl -s -X PATCH "${METRICS_URL}/${metric_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

delete_metric() {
  local api_key
  api_key=$(resolve_api_key)
  local metric_id="$1"
  curl -s -X DELETE "${METRICS_URL}/${metric_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

# --- Metric Improvement ---

preview_metric() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"
  curl -s -X POST "${METRICS_URL}/preview/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

auto_improve_metric() {
  local api_key
  api_key=$(resolve_api_key)
  local metric_id="$1"
  curl -s -X POST "${METRICS_URL}/${metric_id}/auto-improve/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json"
}

generate_trigger() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"
  curl -s -X POST "${METRICS_URL}/generate_evaluation_trigger/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

run_reviews() {
  local api_key
  api_key=$(resolve_api_key)
  local metric_id="$1"
  curl -s -X POST "${METRICS_URL}/${metric_id}/run-reviews/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json"
}

# --- Call Evaluation ---

evaluate_calls() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"  # JSON with call_ids and metric_ids
  curl -s -X POST "${CALLS_URL}/evaluate_metrics/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

rerun_evaluation() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"
  curl -s -X POST "${CALLS_URL}/rerun_evaluation/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

# --- Feedback ---

mark_metric_vote() {
  local api_key
  api_key=$(resolve_api_key)
  local call_id="$1"
  local payload="$2"  # JSON with metric_id and vote details
  curl -s -X POST "${CALLS_URL}/${call_id}/mark_metric_vote/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

list_calls() {
  local api_key
  api_key=$(resolve_api_key)
  local query_params="$1"  # e.g., "agent=12414&limit=50"
  curl -s -X GET "${CALLS_URL}/?${query_params}" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

get_call() {
  local api_key
  api_key=$(resolve_api_key)
  local call_id="$1"
  curl -s -X GET "${CALLS_URL}/${call_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

get_call_evaluation() {
  local api_key
  api_key=$(resolve_api_key)
  local call_id="$1"
  curl -s -X GET "${CALLS_URL}/${call_id}/evaluation/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}
