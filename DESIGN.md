# cma Design 1.0

This document locks the surface API for cma 1.0. Implementation follows from this specification. Changes to this document follow the Suggestion process pattern (issue, discussion, pull request) once governance is in place; for now the design is finalized by the author.

## Purpose

cma is the executable companion to [Lodestone](https://github.com/Clarethium/lodestone). It runs the compound practice loop on the operator's local machine: capture failures, surface relevant prior context at the moment of action, track decisions and rejected alternatives, detect recurrence, and capture preventions.

This document specifies the seven primitives that compose the cma surface, the relationships between them, and how the surface maps to the vocabulary defined in Lodestone.

## Conceptual basis

Vocabulary lives in two places: prose (the Lodestone glossary) and commands (cma primitives). The two surfaces share the same load-bearing terms.

Capture concepts are first-class. The Lodestone glossary names four distinct capture types — Miss, Decision, Rejection, Prevention — and cma preserves that distinction by giving each a verb. The conceptual difference between recording a failure and recording an eliminated option is load-bearing; collapsing them under a single `cma capture --type=...` would hide the distinction.

Operational concerns are not first-class. Listing rejections, viewing leaks, retiring a learning, previewing a distillation — these are modes of larger operations, expressed as flags rather than separate verbs. Three operational verbs cover them all (surface, distill, stats).

The result is seven primitives total: four capture verbs and three operational verbs.

## The seven primitives

### cma miss

Capture a failure. A specific case where the work fell short of what it intended.

```
cma miss <description>
    [--surface <surface>]
    [--fm <failure-shape>]
    [--files <file>[,<file>...]]
```

**Arguments:**

- `<description>` (required, positional). One-line statement of what failed. Phrased actively: "Treated X as Y without verifying" rather than "X was treated as Y."
- `--surface` (optional). The domain area: `auth`, `db`, `docs`, `ui`, `infra`, `general`, `git`. Auto-detected from file paths when `--files` is provided.
- `--fm` (optional). A failure-mode tag. cma stores the value opaquely; interpretation is the methodology's responsibility. When using a methodology with a canonical catalog (such as [Lodestone](https://github.com/Clarethium/lodestone)), tag with that methodology's canonical names. Auto-classification can be plugged in via the `CMA_FM_CLASSIFIER` env var (see ARCHITECTURE.md).
- `--files` (optional). Files involved in the failure. Comma-separated list.

**Output:** Confirmation with the captured description, surface, fm, and a unique miss ID. If a similar miss exists in the last 90 days, output flags the recurrence and indicates which warning weight has been incremented.

**Surfacing trigger:** Recorded misses surface when the current operator action matches the miss context (surface, file, or keyword overlap).

### cma decision

Capture an architectural or strategic choice. Recorded with rationale and alternatives considered.

```
cma decision <description>
    [--surface <surface>]
    [--applies-when <predicate>]
```

**Arguments:**

- `<description>` (required, positional). Format: "TOPIC: choice (rationale)". The TOPIC is the decision domain; the choice is what was decided; the rationale is the why.
- `--surface` (optional). The domain area where this decision applies.
- `--applies-when` (optional). Predicate for re-surfacing. When the predicate matches the current operator action, the decision is surfaced as relevant. Coarse predicates (surface, file pattern) are sufficient for v1.

**Output:** Confirmation with the captured decision and a unique decision ID.

**Lifecycle:** Active by default. Decisions can be archived when superseded; archive does not delete, the decision remains in the reasoning record.

### cma reject

Capture an eliminated option. The alternatives ruled out, with the reason. Survives session compaction so the elimination is not silently rebuilt.

```
cma reject <description>
    [--surface <surface>]
    [--revisit-when <trigger>]
```

**Arguments:**

- `<description>` (required, positional). Format: "OPTION: reason". The option that was eliminated and why.
- `--surface` (optional). The domain area.
- `--revisit-when` (optional). Trigger that would warrant reconsidering this rejection. For example, "if Python 4 ships" or "if performance becomes critical."

**Output:** Confirmation with the captured rejection and a unique rejection ID.

**Surfacing trigger:** Active rejections surface at session start and when current work matches the rejected option's surface.

### cma prevented

Capture a catch. A moment where a surfaced warning prevented a recurrence. Without prevention captures, compound learning is a claim; with them, it is evidence.

```
cma prevented <description>
    [--miss-id <id>]
    [--warning-id <id>]
```

**Arguments:**

- `<description>` (required, positional). What was almost done versus what was done instead.
- `--miss-id` (optional). The miss ID this prevention links to. If known, this provides traceable evidence that the original miss is no longer recurring.
- `--warning-id` (optional). The warning ID that surfaced and was heeded.

**Output:** Confirmation with the captured prevention. If linked to a miss, the miss's prevention count is incremented and the warning's effectiveness is recorded.

### cma surface

Bring relevant prior captures into view for the current context.

```
cma surface
    [--surface <surface>]
    [--file <file>]
    [--type <miss|decision|rejection|prevention>]
    [--limit <n>]
```

**Arguments:**

All optional. Without arguments, surfaces the most relevant captures for the current working directory and recent activity.

- `--surface` (optional). Filter by domain area.
- `--file` (optional). Filter by specific file. Surfaces captures involving this file.
- `--type` (optional). Filter by capture type.
- `--limit` (optional). Maximum results. Default 10.

**Output:** List of relevant captures ordered by relevance (recency, surface match, file match, keyword overlap). Each entry shows ID, type, description, and a relevance signal.

**Replaces:** the prior `cma context` command, generalized.

### cma distill

Promote a learning, retire a learning, or preview the distillation of accumulated patterns.

```
cma distill <learning>
    [--scope <scope>]
    [--surface <surface>]

cma distill --retire <pattern>
cma distill --review
```

**Modes:**

- **Default mode** — promote a learning from accumulated captures to a permanent core learning that surfaces every session. `<learning>` is the distilled principle.
- **`--retire` mode** — retire a core learning that no longer applies or has been superseded. The learning is moved out of active surfacing but retained in the reasoning record.
- **`--review` mode** — preview the patterns that have accumulated since the last distillation. Outputs a summary of recent captures grouped by surface and failure shape, and lists candidate distillations. Read-only.

**Arguments (default mode):**

- `<learning>` (required, positional). The distilled principle, phrased as a permanent rule.
- `--scope` (optional). Where this learning applies: `project`, `language`, `general`. Default: general.
- `--surface` (optional). The primary domain area for the learning.

**Replaces:** the prior `cma retire` (now `--retire` flag) and `cma review` (now `--review` flag).

### cma stats

Evidence dashboard. Shows the state of compound practice over time.

```
cma stats
    [--rejections]
    [--leaks]
    [--preventions]
    [--recurrence]
```

**Modes:**

- **Default mode** — summary dashboard. Total captures by type, recent activity, most-active surfaces, top failure shapes, prevention rate, recurrence trends.
- **`--rejections` view** — list of active rejections with surfaces, ages, and revisit triggers.
- **`--leaks` view** — failures that occurred despite an active warning. Each leak increments the warning's weight.
- **`--preventions` view** — captured preventions with linked misses. Evidence of the loop closing.
- **`--recurrence` view** — failure shapes ordered by recurrence rate. Identifies preventions that are not working.

**Output:** Tabular text with optional filters. Designed for human reading, not piping.

**Replaces:** the prior `cma rejections` (now `--rejections` view) and `cma leaks` (now `--leaks` view).

## Migration from the working version

| Working version | cma 1.0 |
|-----------------|---------|
| `cma decision "..." [surface]` | `cma decision "..." --surface <s>` |
| `cma reject "..." [surface] [trigger]` | `cma reject "..." --surface <s> --revisit-when <t>` |
| `cma miss "..." [surface] [files] [fm]` | `cma miss "..." --surface <s> --files <f> --fm <fm>` |
| `cma distill "..." [scope] [surface]` | `cma distill "..." --scope <s> --surface <s>` |
| `cma retire <pattern>` | `cma distill --retire <pattern>` |
| `cma review` | `cma distill --review` |
| `cma context <surface> [file] [limit]` | `cma surface --surface <s> --file <f> --limit <n>` |
| `cma prevented "..." [miss-id]` | `cma prevented "..." --miss-id <id>` |
| `cma rejections` | `cma stats --rejections` |
| `cma stats` | `cma stats` |
| `cma leaks` | `cma stats --leaks` |

Eleven verbs collapse to seven. Positional arguments become named flags. The conceptual distinctions between capture types are preserved.

## Out of scope for 1.0

Reference-implementation polish identified in the audit will land as additive features without changing this surface:

- **Texture preservation on misses** (conversation excerpt, intended action, corrected action) — added as additional optional fields on `cma miss`. The basic signature does not change.
- **Counterfactual capture** — same as above.
- **Action-time injection** (PreToolUse hook integration) — not a cma command; an integration with the host environment.
- **Active failure-shape curation** (3-4 active at any time, others archived) — implementation detail of how surfacing prioritizes warnings; surface unchanged.
- **Recurrence detection auto-flagging** — already implicit in `cma miss` output (recurrence is flagged when a similar prior miss exists); becomes more aggressive in a later version.

## Output and storage

cma is a local tool. All captures are stored in the operator's local data directory (default: `~/.cma/`). The captures are private to the operator. The cma toolkit is open source; the operator's data is not.

This separation matches the Lodestone-versus-personal-practice distinction: the methodology is canonical and shared; what an operator captures while running it stays local.

## Implementation status

This design locks the cma 1.0 surface. Implementation work involves porting the existing working version of cma to this surface. Functional behavior is preserved; argument styles and command names are sharpened.

The reference implementation lands in this repository under the Apache-2.0 license as it is ported.
