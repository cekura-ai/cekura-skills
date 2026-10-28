"""The generator configuration held fixed across every arm.

Models are the pinned backend's production-first choices: the orchestrator engine is the
head of PHASED_ENGINE_CHAIN and chunk workers the head of PHASED_CHUNK_CHAIN
(app/claude_utils.py at 650297f). The DeepSeek chain is pinned to Fireworks, the only
provider of that chain this experiment holds a key for; production's default order starts
with Wafer. That and the transport instrumentation are the recorded deviations.
"""
ENGINE = "accounts/fireworks/routers/glm-5p3-fast"
DEEPSEEK = "accounts/fireworks/models/deepseek-v4p1-flash"
CHUNKS = "gemini-3.7-flash"
MODELS = {"api.fireworks.ai": (ENGINE, DEEPSEEK), "generativelanguage.googleapis.com": (CHUNKS,)}
ROUTES = {
    "api.fireworks.ai": {"credential_env": "FIREWORKS_API_KEY", "routes": [
        {"path": "/inference/v1/messages", "api": "anthropic", "query": {"beta": ["true"]}},
        {"path": "/inference/v1/chat/completions", "api": "chat"}]},
    "generativelanguage.googleapis.com": {"credential_env": "GEMINI_API_KEY", "routes": [
        {"pattern": r"^/v1beta/models/(?P<model>[A-Za-z0-9._-]+):(?:generateContent|streamGenerateContent)$", "api": "gemini", "query": {"alt": ["sse"]}}]}}
BACKEND_ENV = {"AGENT_SCENARIO_ENGINE_MODEL": ENGINE, "AGENT_SCENARIO_PI_PROVIDER": "google", "AGENT_SCENARIO_PI_MODEL": CHUNKS,
               "AGENT_SCENARIO_PI_THINKING": "low", "AGENT_DIRECT_ANTHROPIC": "0"}
SETTINGS = {"DEEPSEEK_PROVIDER_ORDER": ["fireworks"], "VAPI_TOOL_END_CALL": ["isolated-experiment"],
            "VAPI_TOOL_DTMF": ["isolated-experiment"], "VAPI_TOOL_END_CALL_ONLY_ON_TRANSFER": ["isolated-experiment"]}
MODAL_APP, MODAL_SECRET = "claude-cekura-experiment", "cekura-experiment-generator"
SANDBOX_LIFETIME, TEARDOWN_GRACE = 600, 60


def generator_config(pricing, sandbox_image):
    """``pricing`` = {model: {"rates": {...}, "admission": {...}}, "sandbox_rates": {...}} with sources."""
    endpoints = [dict(ROUTES[host], host=host, models={m: pricing[m] for m in models}) for host, models in MODELS.items()]
    return {"endpoints": endpoints, "passthrough": ["api.modal.com"], "backend_env": dict(BACKEND_ENV), "settings": dict(SETTINGS),
            "sandbox": {"rates": pricing["sandbox_rates"], "max_lifetime_seconds": SANDBOX_LIFETIME, "teardown_grace_seconds": TEARDOWN_GRACE},
            "sandbox_image": sandbox_image, "modal_secret": MODAL_SECRET, "modal_app": MODAL_APP, "queues": "simulation-eval"}


def build_sandbox_image():
    """The pinned modal.Image recipe, built once in the experiment workspace (Python 3.13, as the worker)."""
    import modal
    app = modal.App.lookup(MODAL_APP, create_if_missing=True)
    image = modal.Image.debian_slim(python_version="3.13").apt_install("curl").run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -", "apt-get install -y nodejs",
        "npm install -g @earendil-works/pi-coding-agent@0.84.1").pip_install("claude-agent-sdk>=0.2.130", "anthropic[bedrock]", "boto3")
    with modal.enable_output():
        image.build(app)
    return image.object_id
