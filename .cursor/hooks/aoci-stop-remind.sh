#!/usr/bin/env bash
# stop: after a dialogue turn, if session edited files or AOCI drifted, auto-follow up
# so the Agent runs maintain → update_entry (AOCI semantics cannot be written by scripts).
set -euo pipefail

INPUT="$(cat || true)"
REPO_ROOT="$(pwd)"
DIRTY_FILE="$REPO_ROOT/.run/aoci-dirty"

read_meta() {
  python3 -c 'import json,sys
try:
  o=json.loads(sys.argv[1] or "{}")
except Exception:
  o={}
print(o.get("status") or "completed")
print(o.get("loop_count") if o.get("loop_count") is not None else 0)
' "$INPUT" 2>/dev/null || printf 'completed\n0\n'
}

STATUS_LINE="$(read_meta)"
HOOK_STATUS="$(printf '%s\n' "$STATUS_LINE" | sed -n '1p')"
LOOP_COUNT="$(printf '%s\n' "$STATUS_LINE" | sed -n '2p')"

if [[ "$HOOK_STATUS" != "completed" ]]; then
  printf '%s\n' '{}'
  exit 0
fi

if [[ "${LOOP_COUNT:-0}" -ge 2 ]]; then
  printf '%s\n' '{}'
  exit 0
fi

AOCI_BIN="${AOCI_BIN:-}"
if [[ -z "$AOCI_BIN" ]]; then
  if command -v aoci >/dev/null 2>&1; then
    AOCI_BIN="$(command -v aoci)"
  elif [[ -x "$HOME/.local/bin/aoci" ]]; then
    AOCI_BIN="$HOME/.local/bin/aoci"
  fi
fi

SESSION_DIRTY=0
if [[ -f "$DIRTY_FILE" ]] && [[ -s "$DIRTY_FILE" ]]; then
  SESSION_DIRTY=1
fi

ALIGNED=0
DRIFT_SUMMARY=""
if [[ -n "$AOCI_BIN" ]]; then
  RAW="$("$AOCI_BIN" verify --repo "$REPO_ROOT" --json 2>/dev/null || true)"
  if [[ -n "$RAW" ]]; then
    EVAL="$(python3 -c '
import json, sys
raw = sys.stdin.read()
try:
    o = json.loads(raw[raw.find("{"):] if "{" in raw else raw)
except Exception:
    print("0")
    print("")
    raise SystemExit(0)
g = o.get("governance") or {}
aligned = g.get("governance_aligned") is True
drift = g.get("code_drift") or {}
parts = []
for key, label in (("missing","missing"),("stale","stale"),("unbaselined","unbaselined")):
    items = drift.get(key) or []
    if items:
        parts.append(f"{label}={len(items)}")
findings = g.get("findings") or o.get("findings") or []
codes = {f.get("code") for f in findings if isinstance(f, dict)}
if "code_volume_unbaselined" in codes:
    parts.append("volume_baseline_drift")
if not parts and not aligned:
    parts.append("governance_not_aligned")
print("1" if aligned else "0")
print(", ".join(parts))
' <<<"$RAW" 2>/dev/null || printf '0\n')"
    ALIGNED="$(printf '%s\n' "$EVAL" | sed -n '1p')"
    DRIFT_SUMMARY="$(printf '%s\n' "$EVAL" | sed -n '2p')"
  fi
fi

# Clean and quiet when index matches disk and this turn did not leave a dirty mark
# (or dirty mark exists but verify already aligned → clear dirty, no follow-up).
if [[ "$ALIGNED" == "1" ]]; then
  rm -f "$DIRTY_FILE"
  printf '%s\n' '{}'
  exit 0
fi

# Need follow-up when drifted, or session dirty with unknown/unavailable verify
NEED=0
REASON=""
if [[ -n "$DRIFT_SUMMARY" ]]; then
  NEED=1
  REASON="$DRIFT_SUMMARY"
elif [[ "$SESSION_DIRTY" -eq 1 ]]; then
  NEED=1
  REASON="session_file_edits"
fi

if [[ "$NEED" -ne 1 ]]; then
  printf '%s\n' '{}'
  exit 0
fi

MSG="【对话后自动更新 AOCI】检测到未对齐（${REASON}）。请立即执行收尾，不要只回复说明：
1) 调用 MCP aoci_maintain（不要手改 aoci*.txt）
2) 若有 candidates：阅读本批源码后用 aoci_update_entry 整批提交（code_batch_id=code_plan.batch_id）
3) remaining>0 则继续 maintain，直到 remaining=0 且 aligned
4) 再跑 aoci verify / check / index agent guide --agent cursor
详见 doc/AOCI_MAINTAIN.md。"

python3 -c 'import json,sys; print(json.dumps({"followup_message": sys.argv[1]}, ensure_ascii=False))' "$MSG"
exit 0
