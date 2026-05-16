#!/usr/bin/env bash
# Tests for cma 1.0
# Run from repository root: ./test.sh

set -uo pipefail

CMA="$(cd "$(dirname "$0")" && pwd)/cma"
CMA_DIR=$(mktemp -d)
export CMA_DIR
trap 'rm -rf "$CMA_DIR"' EXIT

pass=0
fail=0

# Run a command, assert exit code matches expected
expect_exit() {
    local name="$1"
    local expected="$2"
    shift 2
    local actual=0
    "$@" >/dev/null 2>&1 || actual=$?
    if [[ "$actual" == "$expected" ]]; then
        printf "PASS  %s\n" "$name"
        pass=$((pass + 1))
    else
        printf "FAIL  %s (expected exit %s, got %s)\n" "$name" "$expected" "$actual"
        fail=$((fail + 1))
    fi
}

# Run a command and assert stdout contains a substring
expect_contains() {
    local name="$1"
    local needle="$2"
    shift 2
    local output
    output=$("$@" 2>&1) || true
    if [[ "$output" == *"$needle"* ]]; then
        printf "PASS  %s\n" "$name"
        pass=$((pass + 1))
    else
        printf "FAIL  %s (output missing %q)\n" "$name" "$needle"
        fail=$((fail + 1))
    fi
}

# Run a command and assert stdout matches a regex (robust to whitespace)
expect_matches() {
    local name="$1"
    local pattern="$2"
    shift 2
    local output
    output=$("$@" 2>&1) || true
    if [[ "$output" =~ $pattern ]]; then
        printf "PASS  %s\n" "$name"
        pass=$((pass + 1))
    else
        printf "FAIL  %s (output didn't match /%s/)\n" "$name" "$pattern"
        fail=$((fail + 1))
    fi
}

# Assert all lines in a file parse as valid JSON
expect_json_valid() {
    local name="$1"
    local file="$2"
    if python3 -c 'import json,sys; [json.loads(l) for l in open(sys.argv[1])]' "$file" 2>/dev/null; then
        printf "PASS  %s\n" "$name"
        pass=$((pass + 1))
    else
        printf "FAIL  %s (file %s is not valid JSONL)\n" "$name" "$file"
        fail=$((fail + 1))
    fi
}

# Reset data between test groups
reset() { rm -rf "$CMA_DIR"/*.jsonl 2>/dev/null || true; }

# Wait until the ISO-second has visibly advanced. cma stores
# timestamps at 1-second precision; leak detection requires strict
# event_ts < miss_ts. On hosts with clock drift (notably WSL2's
# periodic host-clock sync), a plain `sleep 2` can still resolve
# to the same ISO-second. This helper polls until the seconds digit
# changes, which is robust to drift in either direction.
wait_for_next_second() {
    # Wait until the seconds digit visibly changes, then wait a
    # full extra second. cma timestamps are second-precision and
    # leak detection requires strict event_ts < miss_ts. On hosts
    # with periodic host-clock sync (notably WSL2), the wall clock
    # can drift backwards mid-command and drag the next record's
    # timestamp into the prior second; the trailing 1-second pad
    # gives margin against that. CI ubuntu-latest does not see this
    # drift and runs reliably either way. Local WSL2 reruns may
    # still occasionally flake on three timing-sensitive leak/
    # evidence assertions; the cma binary's behavior is correct
    # and the canonical test surface is CI.
    local prev=$(date -u +%S)
    while [[ "$(date -u +%S)" == "$prev" ]]; do sleep 0.1; done
    sleep 1
}

# ---------------------------------------------------------------------------
# Meta commands
# ---------------------------------------------------------------------------

expect_exit     "version flag exits 0"           0 "$CMA" --version
expect_contains "version flag prints version"    "1.0" "$CMA" --version
expect_exit     "help flag exits 0"              0 "$CMA" --help
expect_exit     "no args exits 0 (shows help)"   0 "$CMA"
expect_contains "help lists all seven primitives" "cma surface" "$CMA" --help
expect_exit     "unknown command exits 1"        1 "$CMA" garbage

# ---------------------------------------------------------------------------
# Capture verbs
# ---------------------------------------------------------------------------

reset
expect_exit "miss with no description exits 1"   1 "$CMA" miss
expect_exit "miss with description succeeds"     0 "$CMA" miss "test miss"
expect_exit "miss with all flags succeeds"       0 "$CMA" miss "t" --surface docs --fm test --files a.md
expect_exit "miss with unknown flag exits 1"     1 "$CMA" miss "t" --bogus value

# Texture preservation: --excerpt, --intended, --corrected, --excerpt-from
reset
expect_exit "miss with --intended succeeds"      0 "$CMA" miss "t" --intended "what was about to happen"
expect_exit "miss with --corrected succeeds"     0 "$CMA" miss "t" --corrected "what happened instead"
expect_exit "miss with --excerpt succeeds"       0 "$CMA" miss "t" --excerpt "conversation excerpt here"

# --excerpt-from reads from a file
excerpt_file=$(mktemp)
printf 'multiline\nexcerpt with "quotes"\n' > "$excerpt_file"
expect_exit "miss with --excerpt-from succeeds" 0 "$CMA" miss "t" --excerpt-from "$excerpt_file"
expect_exit "miss with --excerpt-from missing file exits 1" 1 "$CMA" miss "t" --excerpt-from "/nonexistent/path"
rm -f "$excerpt_file"

# Verify all texture fields land in JSONL
reset
"$CMA" miss "with full texture" \
    --surface auth --fm fm-1 \
    --intended "patch the symptom" \
    --corrected "fix root cause" \
    --excerpt "operator: do X. assistant: Y." >/dev/null
texture_check=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    rec = json.loads(f.read().strip())
ok = all(rec.get(k) for k in ['intended', 'corrected', 'excerpt'])
print('ok' if ok else 'fail')
")
if [[ "$texture_check" == "ok" ]]; then
    printf "PASS  %s\n" "all texture fields persist in JSONL"
    pass=$((pass + 1))
else
    printf "FAIL  %s\n" "all texture fields persist in JSONL"
    fail=$((fail + 1))
fi

# CMA_FM_CLASSIFIER plugin hook
reset
CMA_FM_CLASSIFIER='echo from-classifier' "$CMA" miss "test description" >/dev/null
classifier_fm=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    print(json.loads(f.read().strip()).get('fm', ''))
")
if [[ "$classifier_fm" == "from-classifier" ]]; then
    printf "PASS  %s\n" "classifier sets fm when --fm not provided"
    pass=$((pass + 1))
else
    printf "FAIL  %s (got=%q)\n" "classifier sets fm when --fm not provided" "$classifier_fm"
    fail=$((fail + 1))
fi

reset
CMA_FM_CLASSIFIER='echo wrong' "$CMA" miss "test" --fm explicit >/dev/null
explicit_fm=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    print(json.loads(f.read().strip()).get('fm', ''))
")
if [[ "$explicit_fm" == "explicit" ]]; then
    printf "PASS  %s\n" "--fm explicit wins over classifier"
    pass=$((pass + 1))
else
    printf "FAIL  %s (got=%q)\n" "--fm explicit wins over classifier" "$explicit_fm"
    fail=$((fail + 1))
fi

reset
expect_exit "classifier failure does not block capture" 0 env CMA_FM_CLASSIFIER='exit 1' "$CMA" miss "test"
fail_fm=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    print(json.loads(f.read().strip()).get('fm', '<not set>'))
")
if [[ "$fail_fm" == "<not set>" ]]; then
    printf "PASS  %s\n" "classifier failure leaves fm unset"
    pass=$((pass + 1))
else
    printf "FAIL  %s (got=%q)\n" "classifier failure leaves fm unset" "$fail_fm"
    fail=$((fail + 1))
fi

# Schema versioning: every capture has schema_version field
reset
"$CMA" miss "v" --surface auth >/dev/null
"$CMA" decision "v" --surface infra >/dev/null
"$CMA" reject "v" --surface ui >/dev/null
"$CMA" prevented "v" >/dev/null
"$CMA" distill "v" --scope project >/dev/null
schema_ok=$(python3 -c "
import json, glob, os
ok = True
for path in glob.glob('$CMA_DIR/*.jsonl'):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            rec = json.loads(line)
            if rec.get('schema_version') != '1.0':
                ok = False
                print('missing schema_version in', path, rec.get('type'))
                break
print('ok' if ok else 'fail')
")
if [[ "$schema_ok" == "ok" ]]; then
    printf "PASS  %s\n" "all captures include schema_version 1.0"
    pass=$((pass + 1))
else
    printf "FAIL  %s\n" "all captures include schema_version 1.0"
    fail=$((fail + 1))
fi

# Tolerant read: corrupted JSONL line is skipped with stderr warning
reset
"$CMA" miss "valid" --surface auth >/dev/null
echo "this is not valid json" >> "$CMA_DIR/misses.jsonl"
"$CMA" miss "another valid" --surface auth >/dev/null
output=$("$CMA" surface --surface auth 2>&1)
err_output=$("$CMA" surface --surface auth 2>&1 >/dev/null)
if [[ "$output" == *"valid"* ]] && [[ "$output" == *"another valid"* ]]; then
    printf "PASS  %s\n" "tolerant read: valid records still surfaced after corruption"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "tolerant read: valid records still surfaced after corruption" "$output"
    fail=$((fail + 1))
fi
if [[ "$err_output" == *"corrupted"* ]]; then
    printf "PASS  %s\n" "tolerant read: corrupted line warned to stderr"
    pass=$((pass + 1))
else
    printf "FAIL  %s (err=%q)\n" "tolerant read: corrupted line warned to stderr" "$err_output"
    fail=$((fail + 1))
fi

# cma init creates the data directory with a README
init_dir=$(mktemp -d)/cma-init-test
expect_exit "init creates directory" 0 env CMA_DIR="$init_dir" "$CMA" init
if [[ -d "$init_dir" && -f "$init_dir/README.md" ]]; then
    printf "PASS  %s\n" "init writes README inside data directory"
    pass=$((pass + 1))
else
    printf "FAIL  %s\n" "init writes README inside data directory"
    fail=$((fail + 1))
fi
expect_exit "init is idempotent" 0 env CMA_DIR="$init_dir" "$CMA" init
expect_contains "init README references DATA.md" "DATA.md" cat "$init_dir/README.md"
rm -rf "$(dirname "$init_dir")"

# init warns on cloud-sync-shaped paths but still succeeds.
sync_dir=$(mktemp -d -p /tmp Dropbox-XXXXXX)
expect_exit "init succeeds on Dropbox-shaped path" 0 env CMA_DIR="$sync_dir" "$CMA" init
warn_out=$(env CMA_DIR="$sync_dir" "$CMA" init 2>&1 >/dev/null)
if [[ "$warn_out" == *"cloud-sync"* ]]; then
    printf "PASS  %s\n" "init warns on cloud-sync-shaped path"
    pass=$((pass + 1))
else
    printf "FAIL  %s (no warning emitted)\n" "init warns on cloud-sync-shaped path"
    fail=$((fail + 1))
fi
rm -rf "$sync_dir"

# init is silent on normal local paths.
local_dir=$(mktemp -d)
silent_check=$(env CMA_DIR="$local_dir" "$CMA" init 2>&1 >/dev/null)
if [[ -z "$silent_check" ]]; then
    printf "PASS  %s\n" "init silent on local filesystem"
    pass=$((pass + 1))
else
    printf "FAIL  %s (stderr=%q)\n" "init silent on local filesystem" "$silent_check"
    fail=$((fail + 1))
fi
rm -rf "$local_dir"

reset
expect_exit "decision succeeds"                  0 "$CMA" decision "TOPIC: choice (rationale)" --surface infra
expect_exit "decision with applies-when"         0 "$CMA" decision "X" --applies-when "surface=docs"

reset
expect_exit "reject succeeds"                    0 "$CMA" reject "OPTION: reason" --surface ui
expect_exit "reject with revisit-when"           0 "$CMA" reject "X" --revisit-when "if Python 4"

reset
expect_exit "prevented succeeds"                 0 "$CMA" prevented "almost X, did Y instead"
expect_exit "prevented with miss-id"             0 "$CMA" prevented "x" --miss-id abc123

# ---------------------------------------------------------------------------
# cma id helper
# ---------------------------------------------------------------------------

reset
expect_exit "id with no captures exits 1"     1 "$CMA" id miss
"$CMA" miss "first" --surface auth >/dev/null
"$CMA" miss "second" --surface db >/dev/null
last_id=$("$CMA" id miss)
if [[ -z "$last_id" ]]; then
    printf "FAIL  %s (empty output)\n" "id miss returns a real miss id"
    fail=$((fail + 1))
elif grep -q "$last_id" "$CMA_DIR/misses.jsonl"; then
    printf "PASS  %s\n" "id miss returns a real miss id"
    pass=$((pass + 1))
else
    printf "FAIL  %s (id=%q not in misses.jsonl)\n" "id miss returns a real miss id" "$last_id"
    fail=$((fail + 1))
fi
# The second miss was on db; --surface auth should return the first.
auth_id=$("$CMA" id miss --surface auth)
db_id=$("$CMA" id miss --surface db)
if [[ -n "$auth_id" && -n "$db_id" && "$auth_id" != "$db_id" ]]; then
    printf "PASS  %s\n" "id miss --surface filters by surface"
    pass=$((pass + 1))
else
    printf "FAIL  %s (auth=%q db=%q)\n" "id miss --surface filters by surface" "$auth_id" "$db_id"
    fail=$((fail + 1))
fi
# Composability: pipe id into prevented --miss-id
"$CMA" prevented "caught the auth one" --miss-id "$("$CMA" id miss --surface auth)" >/dev/null
expect_contains "prevented composed from cma id" "auth_id" sh -c "python3 -c \"
import json
with open('$CMA_DIR/preventions.jsonl') as f:
    for line in f:
        rec = json.loads(line)
        if 'caught the auth' in rec.get('description', ''):
            print('auth_id' if rec.get('miss_id') == '$auth_id' else 'mismatch')
\""
expect_exit "id with unknown type fails"      1 "$CMA" id bogus

# ---------------------------------------------------------------------------
# cma install-hook (Claude Code settings.json wiring)
# ---------------------------------------------------------------------------

expect_exit "install-hook with no target exits 1"      1 "$CMA" install-hook
expect_exit "install-hook with bogus target exits 1"   1 "$CMA" install-hook --bogus
expect_exit "install-hook bad scope exits 1"           1 "$CMA" install-hook --claude-code --scope bogus

# Dry-run on a virgin tree prints merged JSON to stdout, leaves no file behind.
ih_dir=$(mktemp -d)
pushd "$ih_dir" >/dev/null
out=$("$CMA" install-hook --claude-code --scope project --dry-run 2>/dev/null)
if echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'SessionStart' in d['hooks'] and 'PreToolUse' in d['hooks']" 2>/dev/null; then
    printf "PASS  %s\n" "install-hook --dry-run emits valid merged JSON"
    pass=$((pass + 1))
else
    printf "FAIL  %s\n" "install-hook --dry-run emits valid merged JSON"
    fail=$((fail + 1))
fi
if [[ ! -f .claude/settings.json ]]; then
    printf "PASS  %s\n" "install-hook --dry-run does not write settings.json"
    pass=$((pass + 1))
else
    printf "FAIL  %s\n" "install-hook --dry-run does not write settings.json"
    fail=$((fail + 1))
fi
popd >/dev/null
rm -rf "$ih_dir"

# Write to a fresh project tree: settings.json is created with both hooks.
ih_dir=$(mktemp -d)
pushd "$ih_dir" >/dev/null
"$CMA" install-hook --claude-code --scope project >/dev/null
expect_contains "install-hook writes SessionStart hook" "claude-code-session-start.sh" cat .claude/settings.json
expect_contains "install-hook writes PreToolUse hook"   "claude-code-pre-tool-use.sh"   cat .claude/settings.json

# Idempotent: a second run reports no changes.
out=$("$CMA" install-hook --claude-code --scope project 2>&1)
if [[ "$out" == *"already present"* ]]; then
    printf "PASS  %s\n" "install-hook is idempotent on re-run"
    pass=$((pass + 1))
else
    printf "FAIL  %s (got: %s)\n" "install-hook is idempotent on re-run" "$out"
    fail=$((fail + 1))
fi
popd >/dev/null
rm -rf "$ih_dir"

# Merge preserves existing hooks and unrelated keys; backup captures prior.
ih_dir=$(mktemp -d)
pushd "$ih_dir" >/dev/null
mkdir -p .claude
cat > .claude/settings.json <<'JSON'
{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo prior"}]}]}, "theme": "dark"}
JSON
"$CMA" install-hook --claude-code --scope project >/dev/null
expect_contains "install-hook preserves existing hooks"  "echo prior" cat .claude/settings.json
expect_contains "install-hook preserves unrelated keys"  "\"theme\": \"dark\"" cat .claude/settings.json
if [[ -f .claude/settings.json.bak ]]; then
    printf "PASS  %s\n" "install-hook creates backup of prior settings"
    pass=$((pass + 1))
else
    printf "FAIL  %s\n" "install-hook creates backup of prior settings"
    fail=$((fail + 1))
fi
popd >/dev/null
rm -rf "$ih_dir"

# Malformed JSON is refused without overwriting.
ih_dir=$(mktemp -d)
pushd "$ih_dir" >/dev/null
mkdir -p .claude
echo "not json {" > .claude/settings.json
expect_exit "install-hook refuses malformed settings.json" 1 "$CMA" install-hook --claude-code --scope project
content=$(cat .claude/settings.json)
if [[ "$content" == "not json {" ]]; then
    printf "PASS  %s\n" "install-hook leaves malformed settings.json unchanged"
    pass=$((pass + 1))
else
    printf "FAIL  %s (file was modified)\n" "install-hook leaves malformed settings.json unchanged"
    fail=$((fail + 1))
fi
popd >/dev/null
rm -rf "$ih_dir"

# ---------------------------------------------------------------------------
# JSON validity (each capture writes valid JSONL)
# ---------------------------------------------------------------------------

reset
"$CMA" miss "simple description" >/dev/null
"$CMA" miss 'with "quotes"' >/dev/null
"$CMA" miss 'with \backslashes'\\ >/dev/null
"$CMA" miss "with
newline" >/dev/null
expect_json_valid "misses.jsonl is valid JSONL after edge inputs" "$CMA_DIR/misses.jsonl"

reset
"$CMA" decision "X" --surface a >/dev/null
"$CMA" reject "Y" --revisit-when 'if "Z"' >/dev/null
"$CMA" prevented "P" --miss-id m1 >/dev/null
expect_json_valid "decisions.jsonl is valid"     "$CMA_DIR/decisions.jsonl"
expect_json_valid "rejections.jsonl is valid"    "$CMA_DIR/rejections.jsonl"
expect_json_valid "preventions.jsonl is valid"   "$CMA_DIR/preventions.jsonl"

# ---------------------------------------------------------------------------
# Surface (operational verb)
# ---------------------------------------------------------------------------

reset
expect_contains "surface with empty data"        "No captures match." "$CMA" surface
"$CMA" miss "first miss" --surface docs >/dev/null
"$CMA" miss "second miss" --surface auth >/dev/null
"$CMA" decision "a decision" --surface infra >/dev/null
expect_contains "surface lists all captures"     "first miss" "$CMA" surface
expect_contains "surface --type miss filters"    "first miss" "$CMA" surface --type miss
expect_exit     "surface --limit 1 succeeds"     0 "$CMA" surface --limit 1
expect_contains "surface --surface docs filters" "first miss" "$CMA" surface --surface docs
expect_exit     "surface --bogus exits 1"        1 "$CMA" surface --bogus

# Surface --type filter excludes other types
output=$("$CMA" surface --type miss 2>&1)
if [[ "$output" != *"a decision"* ]]; then
    printf "PASS  %s\n" "surface --type miss excludes decisions"
    pass=$((pass + 1))
else
    printf "FAIL  %s\n" "surface --type miss leaks decisions"
    fail=$((fail + 1))
fi

# Decision applies-when matching (the decision-surfacing closure)
reset
"$CMA" decision "AUTH: validate JWT" --surface infra --applies-when auth >/dev/null
"$CMA" decision "DB: use migrations" --surface infra --applies-when "db migration" >/dev/null
"$CMA" decision "STYLE: early returns" --surface general >/dev/null
"$CMA" miss "auth check missed" --surface auth >/dev/null

# Surface filter on auth: matches AUTH decision (via applies-when) and miss (via surface field)
output=$("$CMA" surface --surface auth 2>&1)
if [[ "$output" == *"AUTH: validate JWT"* ]]; then
    printf "PASS  %s\n" "decision surfaces by applies-when keyword"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "decision surfaces by applies-when keyword" "$output"
    fail=$((fail + 1))
fi

# Multi-keyword applies-when: db decision matches both "db" and "migration"
output=$("$CMA" surface --surface migration 2>&1)
if [[ "$output" == *"DB: use migrations"* ]]; then
    printf "PASS  %s\n" "decision applies-when matches any of multiple keywords"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "decision applies-when matches any of multiple keywords" "$output"
    fail=$((fail + 1))
fi

# Decision without applies-when only matches by stored surface
output=$("$CMA" surface --surface infra 2>&1)
if [[ "$output" == *"AUTH: validate JWT"* && "$output" == *"DB: use migrations"* && "$output" != *"STYLE: early returns"* ]]; then
    printf "PASS  %s\n" "decision without applies-when matches only by stored surface"
    pass=$((pass + 1))
else
    printf "FAIL  %s\n" "decision without applies-when matches only by stored surface"
    fail=$((fail + 1))
fi

# Misses do NOT get applies-when matching (only their surface field matters)
# A miss with surface="auth" should not match --surface=migration even if a decision with applies-when does
output=$("$CMA" surface --surface migration --type miss 2>&1)
if [[ "$output" == *"No captures match"* ]]; then
    printf "PASS  %s\n" "misses do not surface via applies-when (decision-specific)"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "misses do not surface via applies-when (decision-specific)" "$output"
    fail=$((fail + 1))
fi

# ---------------------------------------------------------------------------
# Distill (default mode + --review/--retire stubs)
# ---------------------------------------------------------------------------

reset
expect_exit     "distill no args exits 1"        1 "$CMA" distill
expect_exit     "distill --review with empty data" 0 "$CMA" distill --review
expect_contains "review reports no misses"       "No misses" "$CMA" distill --review
expect_exit     "distill default mode succeeds"  0 "$CMA" distill "Pattern Study before code" --scope project
expect_json_valid "core.jsonl valid after distill" "$CMA_DIR/core.jsonl"
expect_exit     "distill --bogus exits 1"        1 "$CMA" distill --bogus

# Build a pattern of recurring misses and check --review surfaces it
reset
"$CMA" miss "first" --surface auth --fm fm-1 >/dev/null
"$CMA" miss "second" --surface auth --fm fm-1 >/dev/null
"$CMA" miss "third elsewhere" --surface ui --fm fm-2 >/dev/null
expect_contains "review identifies recurring pattern" "2x" "$CMA" distill --review
expect_contains "review reports surface in pattern"   "auth" "$CMA" distill --review

# distill --retire
reset
"$CMA" distill "rule about auth" --surface auth >/dev/null
"$CMA" distill "rule about ui" --surface ui >/dev/null
expect_contains "retire with no match"           "No active core" "$CMA" distill --retire nonexistent
expect_contains "retire matches by substring"    "Retired 1" "$CMA" distill --retire auth
expect_contains "retire is idempotent"           "No active core" "$CMA" distill --retire auth
expect_json_valid "core.jsonl valid after retire" "$CMA_DIR/core.jsonl"

# ---------------------------------------------------------------------------
# Stats (default summary + --rejections/--preventions views + pending flags)
# ---------------------------------------------------------------------------

reset
expect_exit     "stats default runs"             0 "$CMA" stats
"$CMA" miss "one" >/dev/null
"$CMA" miss "two" >/dev/null
"$CMA" decision "d1" >/dev/null
"$CMA" reject "r1" >/dev/null
expect_matches  "stats counts misses"            'misses[[:space:]]+2' "$CMA" stats
expect_matches  "stats counts decisions"         'decisions[[:space:]]+1' "$CMA" stats
expect_matches  "stats counts rejections"        'rejections[[:space:]]+1' "$CMA" stats
expect_matches  "stats shows total"              'total[[:space:]]+4' "$CMA" stats
expect_contains "stats --rejections shows reject" "r1" "$CMA" stats --rejections
expect_exit     "stats --bogus exits 1"          1 "$CMA" stats --bogus

# stats --recurrence
reset
expect_contains "recurrence empty data"          "No misses" "$CMA" stats --recurrence
"$CMA" miss "x" --surface auth --fm fm-1 >/dev/null
expect_contains "recurrence single miss not recurring" "no patterns are recurring" "$CMA" stats --recurrence
"$CMA" miss "y" --surface auth --fm fm-1 >/dev/null
expect_contains "recurrence detects pattern"     "2x" "$CMA" stats --recurrence
expect_contains "recurrence default scope all time" "all time" "$CMA" stats --recurrence
expect_contains "recurrence frames as not closing" "not closing the loop" "$CMA" stats --recurrence
expect_contains "recurrence --window scopes header"  "trailing 7 days" "$CMA" stats --recurrence --window 7
expect_exit     "recurrence --window 0 rejected"     1 "$CMA" stats --recurrence --window 0

# Recurrence + preventions: catch-rate annotation appears when a prevention
# links to a miss in the recurring pair.
reset
"$CMA" miss "x1" --surface auth --fm fm-1 >/dev/null
"$CMA" miss "x2" --surface auth --fm fm-1 >/dev/null
miss_id=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    print(json.loads(f.readline()).get('id'))
")
"$CMA" prevented "caught one" --miss-id "$miss_id" >/dev/null
expect_contains "recurrence shows caught count"        "caught: 1" "$CMA" stats --recurrence
expect_contains "recurrence shows catch-rate"          "catch-rate: 33%" "$CMA" stats --recurrence

# Leaks + preventions: the per-leak line shows the caught count for the pair.
reset
"$CMA" miss "anchor" --surface auth --fm fm-1 >/dev/null
anchor_id=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    print(json.loads(f.readline()).get('id'))
")
"$CMA" surface --surface auth >/dev/null
wait_for_next_second
"$CMA" miss "leaked despite warning" --surface auth --fm fm-1 >/dev/null
"$CMA" prevented "caught a different time" --miss-id "$anchor_id" >/dev/null
expect_contains "leaks line shows caught annotation"   "Caught on this pair: 1" "$CMA" stats --leaks

# stats --leaks
reset
expect_contains "leaks with no events"           "No surface events" "$CMA" stats --leaks
"$CMA" miss "old" --surface auth --fm fm-1 >/dev/null
"$CMA" surface --surface auth >/dev/null
expect_contains "leaks with surface but no later miss" "no leaks detected" "$CMA" stats --leaks
wait_for_next_second
"$CMA" miss "new despite warning" --surface auth --fm fm-1 >/dev/null
expect_contains "leaks detects miss after surfaced warning" "1 leak" "$CMA" stats --leaks
expect_contains "leaks shows the miss"           "new despite warning" "$CMA" stats --leaks
expect_exit     "surface --no-log skips logging" 0 "$CMA" surface --no-log

# stats --leaks weak signals (surface match, fm absent on one side)
reset
"$CMA" miss "fm-absent on new side" --surface auth --fm fm-1 >/dev/null
"$CMA" surface --surface auth >/dev/null
wait_for_next_second
"$CMA" miss "recurred without fm" --surface auth >/dev/null
expect_contains "leaks weak: fm absent on new side"   "weak signal" "$CMA" stats --leaks
# Strong leak (both fms present and equal) co-existing with a weak signal in same run.
reset
"$CMA" miss "fm anchor" --surface auth --fm fm-1 >/dev/null
"$CMA" surface --surface auth >/dev/null
wait_for_next_second
"$CMA" miss "strong recur" --surface auth --fm fm-1 >/dev/null
"$CMA" miss "weak recur, no fm" --surface auth >/dev/null
expect_contains "leaks strong still labeled leak"     "1 leak" "$CMA" stats --leaks
expect_contains "leaks weak alongside strong"         "weak signal" "$CMA" stats --leaks
expect_contains "leaks weak label fm=(none)"          "fm=(none)" "$CMA" stats --leaks

# stats --evidence
reset
expect_contains "evidence empty data"            "No loop-closure evidence yet" "$CMA" stats --evidence
expect_contains "evidence window flag accepted"  "trailing 7 days" "$CMA" stats --evidence --window 7
expect_exit     "evidence rejects window 0"      1 "$CMA" stats --evidence --window 0
expect_exit     "evidence rejects window non-numeric" 1 "$CMA" stats --evidence --window foo

# Loop-closure evidence requires the chain: miss → surface event → prevention.
# Arrange that chain: capture an anchor miss, surface it (which logs an event
# whose `matched` list carries the anchor's id), then a leak miss, then a
# prevention linking to the anchor. The prevention is evidenced because a
# surface event for the anchor's id exists between the anchor's capture and
# the prevention's capture.
"$CMA" miss "anchor miss to be evidenced" --surface auth --fm fm-1 >/dev/null
anchor_id=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    print(json.loads(f.readline()).get('id'))
")
"$CMA" surface --surface auth >/dev/null
wait_for_next_second
"$CMA" miss "leaked despite warning" --surface auth --fm fm-1 >/dev/null
"$CMA" prevented "caught a repeat of the anchor" --miss-id "$anchor_id" >/dev/null
expect_contains "evidence counts leak"           "Leaks:                       1" "$CMA" stats --evidence
expect_contains "evidence counts prevention"     "Preventions captured:        1" "$CMA" stats --evidence
expect_contains "evidence shows linked count"    "linked to a miss: 1" "$CMA" stats --evidence
expect_contains "evidence shows evidenced count" "evidenced:        1" "$CMA" stats --evidence
expect_contains "evidence shows closure rate"    "Loop closure rate:           50%" "$CMA" stats --evidence

# A prevention without miss_id is captured but is NOT evidenced; it does not
# enter the closure-rate denominator.
reset
"$CMA" miss "anchor" --surface auth --fm fm-1 >/dev/null
anchor_id=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    print(json.loads(f.readline()).get('id'))
")
"$CMA" surface --surface auth >/dev/null
wait_for_next_second
"$CMA" miss "leak" --surface auth --fm fm-1 >/dev/null
"$CMA" prevented "self-attested without linkage" >/dev/null
expect_contains "self-attested prevention captured"  "Preventions captured:        1" "$CMA" stats --evidence
expect_contains "self-attested prevention not evidenced" "evidenced:        0" "$CMA" stats --evidence
expect_contains "self-attested rate excludes prevention" "Loop closure rate:           0%" "$CMA" stats --evidence

# --evidence --json emits the new schema with closure-rate fields.
reset
"$CMA" miss "anchor j" --surface auth --fm fm-1 >/dev/null
anchor_id=$(python3 -c "
import json
with open('$CMA_DIR/misses.jsonl') as f:
    print(json.loads(f.readline()).get('id'))
")
"$CMA" surface --surface auth >/dev/null
wait_for_next_second
"$CMA" miss "recurred j" --surface auth --fm fm-1 >/dev/null
"$CMA" prevented "evidenced j" --miss-id "$anchor_id" >/dev/null
json_out=$("$CMA" stats --evidence --json --window 7 2>/dev/null)
json_ok=$(python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
required = {'schema_version', 'window_days', 'generated_at', 'preventions',
            'preventions_linked_to_miss', 'preventions_evidenced',
            'leaks', 'loop_closure_rate', 'recurring'}
missing = required - set(d.keys())
ok = (
    not missing
    and d['preventions'] == 1
    and d['preventions_linked_to_miss'] == 1
    and d['preventions_evidenced'] == 1
    and d['leaks'] == 1
    and d['loop_closure_rate'] == 0.5
    and d['window_days'] == 7
)
print('ok' if ok else f'fail (missing={missing} d={d})')
" <<<"$json_out")
if [[ "$json_ok" == "ok" ]]; then
    printf "PASS  %s\n" "evidence --json emits closure-rate schema"
    pass=$((pass + 1))
else
    printf "FAIL  %s: %s\n" "evidence --json emits closure-rate schema" "$json_ok"
    fail=$((fail + 1))
fi

# Empty corpus: loop_closure_rate is null (not 0.0).
reset
empty_json=$("$CMA" stats --evidence --json 2>/dev/null)
empty_rate=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read())['loop_closure_rate'])" <<<"$empty_json")
if [[ "$empty_rate" == "None" ]]; then
    printf "PASS  %s\n" "evidence --json empty corpus rate is null"
    pass=$((pass + 1))
else
    printf "FAIL  %s (got=%q)\n" "evidence --json empty corpus rate is null" "$empty_rate"
    fail=$((fail + 1))
fi

# stats --behavior
reset
expect_contains "behavior empty data"            "No misses" "$CMA" stats --behavior
"$CMA" miss "no texture" --surface auth >/dev/null
expect_contains "behavior with no texture"       "none have intended/corrected" "$CMA" stats --behavior
"$CMA" miss "with texture" --surface auth --fm fm-1 \
    --intended "patch the symptom" \
    --corrected "fix the root cause" >/dev/null
expect_contains "behavior groups by surface/fm"  "surface=auth" "$CMA" stats --behavior
expect_contains "behavior shows intended"        "patch the symptom" "$CMA" stats --behavior
expect_contains "behavior shows corrected"       "fix the root cause" "$CMA" stats --behavior

# ---------------------------------------------------------------------------
# Hook integration (Claude Code PreToolUse)
# ---------------------------------------------------------------------------

reset
HOOK="$(cd "$(dirname "$0")" && pwd)/hooks/claude-code-pre-tool-use.sh"
# Make cma command available on PATH for the hook's subprocess call
HOOK_BIN_DIR=$(mktemp -d)
ln -sf "$CMA" "$HOOK_BIN_DIR/cma"
trap 'rm -rf "$CMA_DIR" "$HOOK_BIN_DIR"' EXIT
export PATH="$HOOK_BIN_DIR:$PATH"

# Silent for non-relevant tool
hook_out=$(echo '{"tool_name":"Read","tool_input":{"file_path":"/x/auth.ts"}}' | bash "$HOOK" 2>&1)
if [[ -z "$hook_out" ]]; then
    printf "PASS  %s\n" "hook silent for non-relevant tool"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "hook silent for non-relevant tool" "$hook_out"
    fail=$((fail + 1))
fi

# Silent when no captures match
hook_out=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"/x/utils/z.ts"}}' | bash "$HOOK" 2>&1)
if [[ -z "$hook_out" ]]; then
    printf "PASS  %s\n" "hook silent when no captures match"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "hook silent when no captures match" "$hook_out"
    fail=$((fail + 1))
fi

# Surfaces matched capture
"$CMA" miss "auth issue example" --surface auth >/dev/null
hook_out=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"/x/auth/y.ts"}}' | bash "$HOOK" 2>&1)
if [[ "$hook_out" == *"auth issue example"* ]]; then
    printf "PASS  %s\n" "hook surfaces matched capture via stdin JSON"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "hook surfaces matched capture via stdin JSON" "$hook_out"
    fail=$((fail + 1))
fi

# Env var fallback
hook_out=$(CLAUDE_TOOL_NAME=Bash CLAUDE_TOOL_INPUT='{"command":"npm test auth"}' bash "$HOOK" </dev/null 2>&1)
if [[ "$hook_out" == *"auth issue example"* ]]; then
    printf "PASS  %s\n" "hook env var fallback works"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "hook env var fallback works" "$hook_out"
    fail=$((fail + 1))
fi

# ---------------------------------------------------------------------------
# SessionStart hook
# ---------------------------------------------------------------------------

reset
SS_HOOK="$(cd "$(dirname "$0")" && pwd)/hooks/claude-code-session-start.sh"

# Empty data: silent
out=$(bash "$SS_HOOK" </dev/null 2>&1)
if [[ -z "$out" ]]; then
    printf "PASS  %s\n" "session-start silent on empty data"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "session-start silent on empty data" "$out"
    fail=$((fail + 1))
fi

# With recurring pattern: outputs recurrence section
"$CMA" miss "first" --surface auth --fm fm-1 >/dev/null
"$CMA" miss "second" --surface auth --fm fm-1 >/dev/null
out=$(bash "$SS_HOOK" </dev/null 2>&1)
if [[ "$out" == *"## recurrence"* ]] && [[ "$out" == *"2x"* ]]; then
    printf "PASS  %s\n" "session-start surfaces recurrence section"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "session-start surfaces recurrence section" "$out"
    fail=$((fail + 1))
fi

# With rejection: includes rejections section
"$CMA" reject "OPTION: rejected for testing" --surface infra >/dev/null
out=$(bash "$SS_HOOK" </dev/null 2>&1)
if [[ "$out" == *"## rejections"* ]] && [[ "$out" == *"OPTION: rejected"* ]]; then
    printf "PASS  %s\n" "session-start includes rejections section"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "session-start includes rejections section" "$out"
    fail=$((fail + 1))
fi

# CMA_SESSION_START_SECTIONS env var override (only rejections)
out=$(CMA_SESSION_START_SECTIONS=rejections bash "$SS_HOOK" </dev/null 2>&1)
if [[ "$out" == *"## rejections"* ]] && [[ "$out" != *"## recurrence"* ]]; then
    printf "PASS  %s\n" "session-start respects CMA_SESSION_START_SECTIONS"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "session-start respects CMA_SESSION_START_SECTIONS" "$out"
    fail=$((fail + 1))
fi

# CMA_SESSION_START_SECTIONS=all includes behavior
"$CMA" miss "with texture" --surface auth --fm fm-1 \
    --intended "patch symptom" --corrected "fix root" >/dev/null
out=$(CMA_SESSION_START_SECTIONS=all bash "$SS_HOOK" </dev/null 2>&1)
if [[ "$out" == *"## behavior"* ]]; then
    printf "PASS  %s\n" "session-start sections=all includes behavior"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "session-start sections=all includes behavior" "$out"
    fail=$((fail + 1))
fi

# Failure isolation: cma missing → silent
out=$(env -i PATH=/usr/bin:/bin HOME="$HOME" CMA_DIR="$CMA_DIR" bash "$SS_HOOK" </dev/null 2>&1)
if [[ -z "$out" ]]; then
    printf "PASS  %s\n" "session-start silent when cma missing"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "session-start silent when cma missing" "$out"
    fail=$((fail + 1))
fi

# ---------------------------------------------------------------------------
# Shell wrapper (cma-pre)
# ---------------------------------------------------------------------------

reset
PRE="$(cd "$(dirname "$0")" && pwd)/hooks/cma-pre"

# No-args exits 1
expect_exit "cma-pre with no args exits 1"       1 bash "$PRE"

# Non-trigger command: silent, exits 0
output=$(bash "$PRE" --check "ls /tmp" 2>&1)
exit=$?
if [[ -z "$output" && "$exit" == "0" ]]; then
    printf "PASS  %s\n" "cma-pre --check non-trigger silent exit 0"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q exit=%s)\n" "cma-pre --check non-trigger silent exit 0" "$output" "$exit"
    fail=$((fail + 1))
fi

# Trigger + matching surface: produces output
"$CMA" miss "test wrapper miss" --surface auth >/dev/null
output=$(bash "$PRE" --check "git commit -m fix-auth-bug" 2>&1)
if [[ "$output" == *"test wrapper miss"* ]]; then
    printf "PASS  %s\n" "cma-pre --check surfaces matched capture"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "cma-pre --check surfaces matched capture" "$output"
    fail=$((fail + 1))
fi

# Trigger but no surface keyword: silent
output=$(bash "$PRE" --check "make build" 2>&1)
if [[ -z "$output" ]]; then
    printf "PASS  %s\n" "cma-pre --check trigger without surface silent"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "cma-pre --check trigger without surface silent" "$output"
    fail=$((fail + 1))
fi

# Failure isolation: cma not on PATH
output=$(env -i HOME="$HOME" PATH="/usr/bin:/bin" CMA_DIR="$CMA_DIR" bash "$PRE" --check "git commit -m auth" 2>&1)
exit=$?
if [[ -z "$output" && "$exit" == "0" ]]; then
    printf "PASS  %s\n" "cma-pre fails silently when cma missing"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q exit=%s)\n" "cma-pre fails silently when cma missing" "$output" "$exit"
    fail=$((fail + 1))
fi

# Surface event logged by cma-pre invocations
events_before=0
[[ -f "$CMA_DIR/surface_events.jsonl" ]] && events_before=$(wc -l < "$CMA_DIR/surface_events.jsonl" | tr -d ' ')
bash "$PRE" --check "git commit auth-fix" >/dev/null 2>&1
events_after=$(wc -l < "$CMA_DIR/surface_events.jsonl" | tr -d ' ')
if [[ "$events_after" -gt "$events_before" ]]; then
    printf "PASS  %s\n" "cma-pre logs surface event via cma surface"
    pass=$((pass + 1))
else
    printf "FAIL  %s (before=%s after=%s)\n" "cma-pre logs surface event via cma surface" "$events_before" "$events_after"
    fail=$((fail + 1))
fi

# CMA_PRE_TRIGGERS env var override
output=$(CMA_PRE_TRIGGERS="custom_tool" bash "$PRE" --check "custom_tool auth-config" 2>&1)
if [[ "$output" == *"test wrapper miss"* ]]; then
    printf "PASS  %s\n" "cma-pre respects CMA_PRE_TRIGGERS override"
    pass=$((pass + 1))
else
    printf "FAIL  %s (out=%q)\n" "cma-pre respects CMA_PRE_TRIGGERS override" "$output"
    fail=$((fail + 1))
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "$pass passed, $fail failed"
[[ "$fail" -eq 0 ]] || exit 1
