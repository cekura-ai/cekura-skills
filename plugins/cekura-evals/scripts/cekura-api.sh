#!/bin/bash
# Cekura API helper for evaluator/scenario operations
# Usage: source this file or call functions directly

# --- Configuration ---
CEKURA_BASE_URL="https://api.cekura.ai"
SCENARIOS_URL="${CEKURA_BASE_URL}/test_framework/v1/scenarios"
PERSONALITIES_URL="${CEKURA_BASE_URL}/test_framework/v1/personalities"
RESULTS_URL="${CEKURA_BASE_URL}/test_framework/v1/results"
RUNS_URL="${CEKURA_BASE_URL}/test_framework/v1/runs"
TEST_PROFILES_URL="${CEKURA_BASE_URL}/test_framework/v1/test-profiles"
CALLS_URL="${CEKURA_BASE_URL}/observability/v1/call-logs-external"

# Resolve API key: env var first, then .claude/cekura-evals.local.md frontmatter
resolve_api_key() {
  if [ -n "$CEKURA_API_KEY" ]; then
    echo "$CEKURA_API_KEY"
    return
  fi
  local settings_file=".claude/cekura-evals.local.md"
  if [ -f "$settings_file" ]; then
    grep -m1 '^api_key:' "$settings_file" | sed 's/^api_key:\s*//' | tr -d '[:space:]'
    return
  fi
  echo ""
}

# --- Evaluator/Scenario CRUD ---

create_scenario() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"
  curl -s -X POST "${SCENARIOS_URL}/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

get_scenario() {
  local api_key
  api_key=$(resolve_api_key)
  local scenario_id="$1"
  curl -s -X GET "${SCENARIOS_URL}/${scenario_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

list_scenarios() {
  local api_key
  api_key=$(resolve_api_key)
  local query_params="$1"  # e.g., "agent=12414" or "project=5&tags=scheduling"
  curl -s -X GET "${SCENARIOS_URL}/?${query_params}" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

update_scenario() {
  local api_key
  api_key=$(resolve_api_key)
  local scenario_id="$1"
  local payload="$2"
  curl -s -X PATCH "${SCENARIOS_URL}/${scenario_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

delete_scenario() {
  local api_key
  api_key=$(resolve_api_key)
  local scenario_id="$1"
  curl -s -X DELETE "${SCENARIOS_URL}/${scenario_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

# --- Generation ---

generate_scenarios() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"
  curl -s -X POST "${SCENARIOS_URL}/generate-bg/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

check_generation_progress() {
  local api_key
  api_key=$(resolve_api_key)
  local progress_id="$1"
  curl -s -X GET "${SCENARIOS_URL}/${progress_id}/progress/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

create_from_transcript() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"
  curl -s -X POST "${SCENARIOS_URL}/from-transcript/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

# --- Execution ---

run_voice() {
  local api_key
  api_key=$(resolve_api_key)
  local scenario_id="$1"
  local payload="${2:-{}}"
  curl -s -X POST "${SCENARIOS_URL}/${scenario_id}/run-voice/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

run_text() {
  local api_key
  api_key=$(resolve_api_key)
  local scenario_id="$1"
  local payload="${2:-{}}"
  curl -s -X POST "${SCENARIOS_URL}/${scenario_id}/run-text/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

run_websocket() {
  local api_key
  api_key=$(resolve_api_key)
  local scenario_id="$1"
  local payload="${2:-{}}"
  curl -s -X POST "${SCENARIOS_URL}/${scenario_id}/run-websocket/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

run_pipecat() {
  local api_key
  api_key=$(resolve_api_key)
  local scenario_id="$1"
  local payload="${2:-{}}"
  curl -s -X POST "${SCENARIOS_URL}/${scenario_id}/run-pipecat/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

# --- Results ---

list_results() {
  local api_key
  api_key=$(resolve_api_key)
  local query_params="$1"
  curl -s -X GET "${RESULTS_URL}/?${query_params}" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

get_result() {
  local api_key
  api_key=$(resolve_api_key)
  local result_id="$1"
  curl -s -X GET "${RESULTS_URL}/${result_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

rerun_result() {
  local api_key
  api_key=$(resolve_api_key)
  local result_id="$1"
  curl -s -X POST "${RESULTS_URL}/${result_id}/rerun/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json"
}

# --- Runs ---

list_runs() {
  local api_key
  api_key=$(resolve_api_key)
  local query_params="$1"
  curl -s -X GET "${RUNS_URL}/?${query_params}" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

end_call() {
  local api_key
  api_key=$(resolve_api_key)
  local run_id="$1"
  curl -s -X POST "${RUNS_URL}/${run_id}/end-call/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json"
}

# --- Personalities ---

list_personalities() {
  local api_key
  api_key=$(resolve_api_key)
  curl -s -X GET "${PERSONALITIES_URL}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

# --- Test Profiles ---

create_test_profile() {
  local api_key
  api_key=$(resolve_api_key)
  local payload="$1"
  curl -s -X POST "${TEST_PROFILES_URL}/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

get_test_profile() {
  local api_key
  api_key=$(resolve_api_key)
  local profile_id="$1"
  curl -s -X GET "${TEST_PROFILES_URL}/${profile_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

list_test_profiles() {
  local api_key
  api_key=$(resolve_api_key)
  local query_params="$1"  # e.g., "agent_id=12345" or "project_id=576"
  curl -s -X GET "${TEST_PROFILES_URL}/?${query_params}" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

update_test_profile() {
  local api_key
  api_key=$(resolve_api_key)
  local profile_id="$1"
  local payload="$2"
  curl -s -X PATCH "${TEST_PROFILES_URL}/${profile_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

delete_test_profile() {
  local api_key
  api_key=$(resolve_api_key)
  local profile_id="$1"
  curl -s -X DELETE "${TEST_PROFILES_URL}/${profile_id}/" \
    -H "X-CEKURA-API-KEY: ${api_key}"
}

# --- Calls (for transcript-based eval creation) ---

list_calls() {
  local api_key
  api_key=$(resolve_api_key)
  local query_params="$1"
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
