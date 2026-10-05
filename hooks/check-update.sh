#!/usr/bin/env bash
# Nudge users when a newer obol plugin release is published.
# The marketplace on main pins the plugin to a release tag (vX.Y.Z), so
# that tag, not main's plugin.json, is what users can actually update to.
# Third-party marketplaces don't auto-update by default, so without this
# users silently stay on whatever version they first installed.
# Checks at most once a day, never blocks the session, never fails loudly.
# Opt out with OBOL_SKILLS_NO_UPDATE_CHECK=1.

[ -n "$OBOL_SKILLS_NO_UPDATE_CHECK" ] && exit 0

LATEST_URL="https://raw.githubusercontent.com/ObolNetwork/skills/main/.claude-plugin/marketplace.json"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CACHE_DIR="${CLAUDE_PLUGIN_DATA:-${XDG_CACHE_HOME:-$HOME/.cache}/obol-skills}"
STAMP="$CACHE_DIR/last-update-check"

version_of() { sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([0-9][0-9.]*\)".*/\1/p' | head -n1; }

# Succeeds if $1 is a strictly older x.y.z than $2.
older() {
  local IFS=.
  local -a a=($1) b=($2)
  for i in 0 1 2; do
    (( ${a[i]:-0} < ${b[i]:-0} )) && return 0
    (( ${a[i]:-0} > ${b[i]:-0} )) && return 1
  done
  return 1
}

mkdir -p "$CACHE_DIR" 2>/dev/null || exit 0
if [ -f "$STAMP" ] && [ -z "$(find "$STAMP" -mmin +1440 2>/dev/null)" ]; then
  exit 0
fi
touch "$STAMP" 2>/dev/null

installed=$(version_of < "$ROOT/.claude-plugin/plugin.json" 2>/dev/null)
latest=$(curl -fsSL --max-time 3 "$LATEST_URL" 2>/dev/null | sed -n 's/.*"ref"[[:space:]]*:[[:space:]]*"v\([0-9][0-9.]*\)".*/\1/p' | head -n1)
[ -n "$installed" ] && [ -n "$latest" ] || exit 0
older "$installed" "$latest" || exit 0

msg="Obol skills v$latest is available (you have v$installed). Update with: claude plugin marketplace update obol && claude plugin update obol@obol, or enable auto-update in /plugin > Marketplaces > obol."
printf '{"systemMessage":"%s","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s If the user invokes an Obol skill this session, mention once that a newer version is available."}}\n' "$msg" "$msg"
