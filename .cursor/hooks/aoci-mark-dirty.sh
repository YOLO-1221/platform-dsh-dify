#!/usr/bin/env bash
# afterFileEdit: mark session dirty when a managed business file changes.
# Skip AOCI formal volumes / runtime so maintain writes do not re-dirty forever.
set -euo pipefail

INPUT="$(cat || true)"
REPO_ROOT="$(pwd)"
DIRTY_FILE="$REPO_ROOT/.run/aoci-dirty"

PATH_REL="$(python3 -c '
import json, sys, os
raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    o = json.loads(raw or "{}")
except Exception:
    o = {}
fp = o.get("file_path") or o.get("path") or ""
root = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else ".")
abs_fp = os.path.abspath(fp) if fp else ""
if not abs_fp.startswith(root + os.sep) and abs_fp != root:
    print("")
    raise SystemExit(0)
rel = os.path.relpath(abs_fp, root).replace("\\\\", "/")
print(rel)
' "$INPUT" "$REPO_ROOT" 2>/dev/null || true)"

if [[ -z "${PATH_REL:-}" || "$PATH_REL" == "." ]]; then
  exit 0
fi

case "$PATH_REL" in
  aoci.txt|aoci.code.txt|aoci.meta.txt|aoci.database.txt|.aoci/*|.run/*|.git/*)
    exit 0
    ;;
esac

mkdir -p "$REPO_ROOT/.run"
# append unique relative paths for debugging; presence of file is what stop checks
if [[ -f "$DIRTY_FILE" ]] && grep -Fxq -- "$PATH_REL" "$DIRTY_FILE" 2>/dev/null; then
  exit 0
fi
printf '%s\n' "$PATH_REL" >>"$DIRTY_FILE"
exit 0
