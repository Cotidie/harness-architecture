#!/bin/sh
# PreToolUse hook: meter real codegraph_explore invocations into a per-run counter.
# Reads the tool-call event JSON on stdin and increments the counter only for the
# codegraph explore tool. Never blocks (metering only); the orchestrator enforces
# the budget by reading the counter delta around each agent dispatch.
COUNTER_DIR="${CLAUDE_PROJECT_DIR:-.}/.architecture/.budget"
COUNTER="$COUNTER_DIR/query-count"
event="$(cat)"
case "$event" in
  *mcp__codegraph__codegraph_explore*)
    mkdir -p "$COUNTER_DIR"
    n=$(cat "$COUNTER" 2>/dev/null || echo 0)
    echo $((n + 1)) > "$COUNTER"
    ;;
esac
exit 0
