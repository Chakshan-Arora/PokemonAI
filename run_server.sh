#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Starting Pokémon LLM Bridge Server on http://127.0.0.1:8008 ..."
if command -v python3 &>/dev/null; then
    python3 server.py
else
    python server.py
fi
