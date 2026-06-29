#!/usr/bin/env bash
# Bring up local dev datastores for LeadPilot (Postgres + Redis), idempotently.
# Safe to run repeatedly. Used by the Claude Code SessionStart hook and locally.
set -uo pipefail

# --- Postgres (system cluster) ---
if command -v pg_ctlcluster >/dev/null 2>&1; then
  if ! pg_isready -q 2>/dev/null; then
    pg_ctlcluster 16 main start >/dev/null 2>&1 || true
    sleep 1
  fi
  # Ensure pgvector + the leadpilot role/db exist (no-op if already present).
  if pg_isready -q 2>/dev/null; then
    su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='leadpilot'\"" 2>/dev/null \
      | grep -q 1 || su postgres -c "psql -c \"CREATE ROLE leadpilot LOGIN PASSWORD 'leadpilot' SUPERUSER\"" >/dev/null 2>&1 || true
    su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='leadpilot'\"" 2>/dev/null \
      | grep -q 1 || su postgres -c "createdb -O leadpilot leadpilot" >/dev/null 2>&1 || true
  fi
fi

# --- Redis ---
if command -v redis-server >/dev/null 2>&1; then
  redis-cli ping >/dev/null 2>&1 || (redis-server --daemonize yes >/dev/null 2>&1 || true)
fi

echo "dev_up: postgres=$(pg_isready -q 2>/dev/null && echo up || echo down) redis=$(redis-cli ping 2>/dev/null || echo down)"
