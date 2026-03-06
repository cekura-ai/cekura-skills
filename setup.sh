#!/bin/bash
# Install Cekura plugins from this marketplace
# Usage: ./setup.sh

set -e

echo "Registering Cekura marketplace..."
echo ""
echo "Run these commands inside Claude Code:"
echo ""
echo "  /plugins add marketplace https://github.com/cekura-ai/claude-skills.git"
echo ""
echo "Then install the plugins:"
echo ""
echo "  /plugins install cekura-metrics"
echo "  /plugins install cekura-evals"
echo ""
echo "Or install both at once from your terminal:"
echo ""
echo "  claude /plugins add marketplace https://github.com/cekura-ai/claude-skills.git"
echo ""
echo "Optional: Set up the Cekura MCP server for full API access:"
echo "  claude mcp add cekura-api http://localhost:8000/mcp --transport http --header \"X-CEKURA-API-KEY:\$CEKURA_API_KEY\""
