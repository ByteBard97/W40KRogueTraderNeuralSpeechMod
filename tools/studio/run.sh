#!/usr/bin/env bash
# Build the web app if needed, then start the Voice Studio API server on :8930.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f web/dist/index.html ]; then
  (cd web && npm install && npm run build)
fi
cd server
exec python3 -m studio_server --port "${STUDIO_PORT:-8930}" "$@"
