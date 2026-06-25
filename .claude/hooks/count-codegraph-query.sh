#!/bin/sh
# PreToolUse hook: meter real codegraph_explore invocations into a per-run counter.
# Reads the tool-call event JSON on stdin and increments the counter only when the
# event's tool_name field is EXACTLY the codegraph explore tool. Parsing the field
# (not substring-matching the whole event) avoids false positives when some other
# tool's arguments or a file's contents merely mention the tool name.
# Never blocks (metering only); the orchestrator enforces the budget by reading the
# counter delta around each agent dispatch.
COUNTER_DIR="${CLAUDE_PROJECT_DIR:-.}/.architecture/.budget"
COUNTER="$COUNTER_DIR/query-count"
event="$(cat)"
name=$(printf '%s' "$event" | python3 -c 'import sys, json
try:
    print(json.load(sys.stdin).get("tool_name", ""))
except Exception:
    print("")' 2>/dev/null)
if [ "$name" = "mcp__codegraph__codegraph_explore" ]; then
  mkdir -p "$COUNTER_DIR"
  n=$(cat "$COUNTER" 2>/dev/null || echo 0)
  echo $((n + 1)) > "$COUNTER"
fi
exit 0
