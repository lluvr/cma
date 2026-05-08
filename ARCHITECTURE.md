# cma Architecture

This document specifies the architecture of cma's action-time injection layer: how surfaced warnings reach the operator at the moment of action, and how the data produced supports validation that the compound practice loop is closing.

The document is the contract between cma and any integration that connects it to an operator's environment (AI client, shell, IDE, CI). Specific integrations are interchangeable; this architecture is what they implement.

## 1. Purpose and scope

cma is the executable of compound practice, the discipline defined in [Lodestone](https://github.com/Clarethium/lodestone). The compound practice loop (Lodestone Section VIII) has five steps:

1. **Capture** a failure, decision, rejection, or prevention.
2. **Surface** relevant prior captures when context matches a future action.
3. **Catch** the repeat: the surfaced capture changes operator behavior.
4. **Record prevention** linking the catch to the original capture.
5. **Strengthen** the warning's weight from the prevention evidence.

The loop closes only if step 2 (surface) happens reliably at the moment of step 3 (catch). Manual `cma surface` invocation is sufficient in principle but unreliable in practice: operators forget. Action-time injection makes surfacing automatic and reliable.

This document covers the action-time injection layer: the pattern by which surfacing is triggered automatically by an external interception point, the data it produces, and the criteria that distinguish state-of-the-art integrations from bolt-on ones.

The document does not cover the seven primitives themselves (see [DESIGN.md](DESIGN.md)) or the methodology defined in Lodestone.

## 2. The five-stage architecture

The action-time injection layer is decomposed into five stages. Each is independently testable; each can be implemented differently per environment without affecting the others.

```
Interception → Context extraction → Query → Injection → Logging
```

### 2.1 Interception

The first stage observes that an action is about to happen. Different environments expose different interception points:

- **Claude Code**: `PreToolUse` hook fires before each tool call.
- **Shell (zsh, bash with bash-preexec)**: `preexec` function fires before each command.
- **IDE**: editor pre-save or pre-execute hooks.
- **CI**: pre-commit, pre-push, pre-merge hooks.
- **Manual**: explicit wrapper invocation (`cma-pre <command>`).

The interception layer must:

- Fire reliably before the action it observes (not after, not during).
- Provide enough raw data for the next stage to identify what is about to happen.
- Add minimal overhead to the wrapped action.

Interception is the only environment-specific stage; the rest of the pipeline is shared.

### 2.2 Context extraction

The second stage parses raw interception data into a normalized context. A context describes the action in a form the query stage can use.

Standard context fields:

| Field | Description |
|-------|-------------|
| `tool_name` | Which interception channel fired (`Edit`, `Bash`, `git`, `vim`, etc.) |
| `file_path` | Absolute or relative path of the file being acted on, if applicable |
| `command` | Full command line, if applicable |
| `working_directory` | Current working directory at time of action |
| `project_root` | Detected project root (git toplevel, etc.), if available |
| `surface` | Domain area inferred from `file_path` and `command` |

Surface detection is heuristic: lexical matching of path components and command keywords against a configurable rule table. Heuristics will produce false positives and false negatives. State-of-the-art integrations expose the rule table for operator tuning.

### 2.3 Query

The third stage calls `cma surface` with filters derived from the context.

Query strategy (default):

1. If surface is detected, query with `--surface <s>` (broader, more useful).
2. Else if file_path is detected, query with `--file <basename>`.
3. Else skip the query entirely (no actionable filter; would dump all recent captures, which is noise).

Query result limit: a small number (default 3). The point is to surface the most relevant matches, not to dump the archive.

The query is read-only from the operator's perspective. Logging happens as a side effect of `cma surface`, not as additional work for the integration.

For decisions, `cma surface` additionally matches the decision's `applies_when` field against the context keywords. A decision with `applies_when="auth"` surfaces when the context contains "auth" (in surface or file), even if the decision's stored surface is something else. This closes the decision-surfacing loop: decisions surface at the moment their conditions match, not only when explicitly queried by stored surface. `applies_when` matching is decision-specific; misses, rejections, and preventions match only by their surface and file fields.

### 2.4 Injection

The fourth stage delivers surfaced captures to the operator's context. The injection channel is environment-specific:

| Environment | Channel |
|-------------|---------|
| Claude Code | `stdout` becomes additional context passed to the model |
| Shell | `stderr` is visible to the operator before the next prompt |
| IDE | Inline notice in the editor (status bar, popover, comment) |
| CI | Comment on the commit, PR, or pipeline run |
| Manual | `stdout` of the wrapper command |

The injection layer must:

- Be visible to the operator or agent at the moment of decision (not after the action is complete).
- Be distinguishable from normal output (clearly attributed to cma).
- Be silent on no-match (a noisy signal trains the operator to ignore it).
- Not interrupt the action flow when matches do exist (display, then proceed).

### 2.5 Logging

The fifth stage records the surface event in `surface_events.jsonl` for validation analysis.

Logging is performed by `cma surface` itself, not by the integration layer. This centralizes the logging schema and ensures consistency across all integrations.

The surface event schema is documented in Section 4 (Data contracts).

## 3. Reference implementations

The cma repository includes the following reference implementations of this architecture. Each is a complete worked example; integrations targeting other environments may follow the same pattern.

### 3.1 Claude Code PreToolUse hook

`hooks/claude-code-pre-tool-use.sh`

Interception via Claude Code's `PreToolUse` hook event. Reads stdin JSON (current format) or environment variables (legacy fallback). Surfaces captures to stdout, where Claude Code injects them as additional context. Silent for non-relevant tools (`Read`, etc.) and when no captures match.

Status: implemented, tested.

### 3.1a Claude Code SessionStart hook

`hooks/claude-code-session-start.sh`

Interception via Claude Code's `SessionStart` hook event. Surfaces priming context at the start of each session: recurring failure patterns (from `cma stats --recurrence`), active rejections (from `cma stats --rejections`), and optionally behavior pivots (from `cma stats --behavior`). Configurable via `CMA_SESSION_START_SECTIONS` env var.

Together with the PreToolUse hook, the two cover both ends of the architecture: session-priming context at session boundary and per-action surfacing during work.

Status: implemented, tested.

### 3.2 Shell wrapper (in development)

`hooks/cma-pre.sh` plus `hooks/cma-pre`

Interception via zsh's native `preexec` or bash's bash-preexec library. Multi-shell support. Configurable command rules. Stderr injection. Failure-isolated: if cma errors, the wrapped command still runs.

Status: in design.

### 3.3 Manual wrapper

`hooks/cma-pre` standalone invocation (`cma-pre <command>`).

For environments where automatic interception is unavailable or undesirable. Operators wrap substantive commands explicitly. Same pipeline as the shell wrapper, just triggered manually.

Status: in design.

## 4. Data contracts

The architecture produces three data shapes that downstream analysis depends on. These shapes are stable across environments; integrations writing to or reading from them must conform.

### 4.1 Surface event

Written to `$CMA_DIR/surface_events.jsonl` by `cma surface`:

```json
{
  "type": "surface_event",
  "id": "20260505-070100-abc12345",
  "timestamp": "2026-05-05T07:01:00Z",
  "filter_surface": "auth",
  "filter_file": "",
  "filter_type": "",
  "filter_limit": 3,
  "matched": [
    {
      "id": "20260504-...",
      "type": "miss",
      "surface": "auth",
      "fm": "<failure-shape>"
    }
  ]
}
```

`matched` may be empty. Empty events still record that surfacing was attempted.

### 4.2 Miss with texture

Written to `$CMA_DIR/misses.jsonl` by `cma miss`:

```json
{
  "type": "miss",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "description": "...",
  "surface": "auth",
  "fm": "<failure-shape>",
  "files": "src/auth/jwt.ts",
  "intended": "patch only the failing test",
  "corrected": "trace upstream defect, fix at root",
  "excerpt": "operator: ...\nassistant: ..."
}
```

Texture fields (`intended`, `corrected`, `excerpt`) are optional but recommended. They are the data substrate for behavior-layer validation.

### 4.3 Prevention

Written to `$CMA_DIR/preventions.jsonl` by `cma prevented`:

```json
{
  "type": "prevention",
  "id": "20260505-...",
  "timestamp": "2026-05-05T...",
  "description": "almost X, did Y instead after seeing surfaced warning",
  "miss_id": "20260504-...",
  "warning_id": "..."
}
```

Linking via `miss_id` lets validation analysis compute prevention rates per original miss.

## 5. Validation framework

The architecture is designed to produce data supporting three independent layers of evidence about whether the compound practice loop is working.

### 5.1 Process layer

**Question**: Does the loop run at all?

**Metrics**, computable from cma's existing data:

- Capture rate (captures per session, per day, per project).
- Surface event rate (surfacings per session).
- Coverage: fraction of operator actions that produce a surface event.

**Strength**: easy to measure. **Weakness**: a journal that never affects behavior would still produce these metrics. Necessary but not sufficient.

### 5.2 Behavior layer

**Question**: Do surfaced warnings change operator action?

**Metrics**, computable from texture-preserved captures:

- Counterfactual rate: misses with both `intended` and `corrected` set, where the two differ. Direct evidence of mid-course correction.
- Prevention-to-leak ratio: `cma prevented` captures versus leak detections. Higher ratio means warnings are working.
- Decision-shift rate: decisions captured that contradict prior decisions (operator reflection).

**Strength**: structural data; not self-report alone. **Weakness**: requires operators to capture texture (the `--intended`, `--corrected` flags). Coverage depends on capture discipline.

### 5.3 Outcome layer

**Question**: Does the operator's work get measurably better?

**Metrics**, requiring [Touchstone](https://github.com/Clarethium/touchstone) integration:

- Touchstone score trends on the operator's actual outputs over time.
- Score deltas correlated with cma usage intensity (captures per task, surfacings per task).
- Failure-shape distribution shifts (fewer recurrences of named failure shapes).

**Strength**: objective, model-independent measurement. **Weakness**: requires operator's actual work to be amenable to Touchstone evaluation, which depends on output type. Currently aspirational; the bridge between Lodestone, cma, and Touchstone is the project's intellectual spine and is the next major architectural project after this one.

The three layers are independent. A system that passes the Process layer alone is a journal. A system that passes Process + Behavior is a working compound practice loop. A system that passes all three is a methodology with empirical grounding.

## 6. Quality criteria for an integration

A state-of-the-art integration of this architecture meets the following criteria.

### Reliability

- The interception layer fires before the action, on every relevant action.
- Failures in the cma layer do not block the wrapped action.
- The integration is testable in isolation per stage.

### Performance

- End-to-end overhead under 50 ms in the typical case.
- Bounded worst-case overhead (timeout on cma queries, default 5 seconds).
- Empty-result path is fast: no surface match should not slow the action significantly.

### Signal quality

- Surface detection rules are configurable; defaults are tuned for canonical surfaces (auth, payments, db, ui, docs, test, api).
- False-positive surface matches are rare; false-negatives are acceptable (operators can capture without surface and still hit the file filter).
- Empty matches produce silent output (no dialog box, no chatter).

### Composability

- The integration does not require global state in the operator's environment.
- Aliasing commands is not required; preexec or hook mechanisms are preferred where available.
- Multiple integrations can coexist (Claude Code hook + shell wrapper + IDE plugin).

### Validation contribution

- Every surface event is logged.
- Texture preservation flags are exposed when the integration captures.
- Output is distinguishable from normal output (parseable by future analysis tooling).

## 7. Failure modes to avoid

State-of-the-art integrations explicitly handle each of the following.

### Bolt-on integration

Aliasing every command with `cma-wrap` and stopping there. Fails because it does not compose, scales poorly, and produces inconsistent context across commands. The five-stage architecture exists to prevent this.

### Eager logging

Logging every keystroke, file save, or shell command regardless of relevance. Fails because log noise drowns signal. Surface event logging is bounded to actual `cma surface` calls; the architecture does not log raw interception data.

### Silent failure

If cma is missing or errors, the integration does nothing visible. Fails because operators stop trusting the signal. State-of-the-art: the wrapped action still runs cleanly, but the operator gets a notice that cma was unavailable.

### Performance regression

Integration adds noticeable latency. Fails because operators disable the integration. The 50 ms criterion is the practical bar.

### Surface noise

Surface detection is too aggressive; irrelevant captures get surfaced. Fails because operators stop reading the output. State-of-the-art: heuristics are configurable, defaults are tuned, false-positive rate is monitored.

### Stale signal

Surface events accumulate indefinitely; recent events drown in historical noise. Mitigation: a recency-weighted scoring strategy in `cma surface`, or a log rotation policy in `$CMA_DIR`. The current implementation uses simple recency-sort; future versions may add scoring.

### Schema drift

Integrations writing to `surface_events.jsonl` without conforming to the schema in Section 4 break downstream analysis. Mitigation: cma owns the writer (via `cma surface`); integrations call cma rather than writing directly.

## 8. Versioning and evolution

The architecture's contract is: integrations call `cma surface` and respect its output schema (Section 4). Adding new fields to surface events (additive) is backward-compatible. Removing fields requires a major version bump.

The contract is documented in this file and in [DESIGN.md](DESIGN.md). Changes to the contract follow the project's versioning policy (see [CHANGELOG.md](CHANGELOG.md)).

## 9. Methodology integration

cma is methodology-agnostic. The `--fm` field on captures and any methodology-specific tags are opaque strings from cma's perspective. Semantics are owned by the methodology in use.

When operators use cma alongside a methodology that defines a canonical failure-mode catalog (Lodestone is the canonical human-AI collaboration methodology under Clarethium; others may emerge), they tag captures with the methodology's canonical names. Analysis tooling that reads cma data interprets the tags according to the methodology context.

The integration is by convention (shared vocabulary), not by code. cma does not depend on any methodology. Methodologies do not depend on cma. Each evolves independently. cma documentation does not replicate methodology catalogs; methodology documents own their catalogs and their meaning.

### 9.1 Plugin point: classifier

When the `CMA_FM_CLASSIFIER` env var is set, `cma miss` invokes the named command as a shell expression if `--fm` is not provided explicitly. The command receives the description on stdin and is expected to emit the classified failure-mode tag on its first line of stdout.

Failure modes:

- `--fm` provided explicitly: the classifier is not invoked. Operator override is absolute.
- `CMA_FM_CLASSIFIER` not set: no classifier invocation; `fm` stays empty unless `--fm` was provided.
- Classifier command not found, errors, or exits non-zero: `fm` stays empty; the capture proceeds.
- Classifier exceeds 5 second timeout: `fm` stays empty; the capture proceeds.

The plugin point exists so operators can wire methodology-aware classification (a Lodestone-aware classifier, for instance) without coupling cma to any specific methodology. Operators using a different methodology wire a different classifier. Operators not using auto-classification leave the env var unset and tag manually with `--fm`.

The classifier is external to cma: this repository ships no classifier. Methodologies that wish to provide one ship it as a separate companion tool (or document the wiring pattern in their own docs). This preserves the loose coupling.

## 10. References

- [DESIGN.md](DESIGN.md): the seven cma 1.0 primitives.
- [Lodestone Section VIII](https://github.com/Clarethium/lodestone): the compound practice loop (the methodology this architecture serves).
- [Touchstone](https://github.com/Clarethium/touchstone): the measurement infrastructure for the outcome layer of validation.
