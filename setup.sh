#!/bin/bash
# Install Cekura Claude Code plugins
# Usage: ./setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing Cekura Claude Code plugins..."

claude install-plugin "$SCRIPT_DIR/cekura-metrics"
echo "  Installed cekura-metrics"

claude install-plugin "$SCRIPT_DIR/cekura-evals"
echo "  Installed cekura-evals"

echo ""
echo "Done. Both plugins are now available in Claude Code."
echo ""
echo "Optional: Set up the Cekura MCP server for full API access:"
echo "  claude mcp add cekura-api http://localhost:8000/mcp --transport http --header \"X-CEKURA-API-KEY:\$CEKURA_API_KEY\""
