#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-llama3.2}"
HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Error: 'ollama' is not installed. Download it from https://ollama.com/download"
  exit 1
fi

export OLLAMA_HOST="$HOST"

echo "Starting Ollama on $OLLAMA_HOST"
if ! pgrep -f "ollama serve" >/dev/null 2>&1; then
  nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  sleep 2
fi

echo "Pulling model: $MODEL"
ollama pull "$MODEL"

echo "LLM ready"
echo "Provider: ollama"
echo "Model: $MODEL"
echo "Endpoint: http://$OLLAMA_HOST/api/chat"
