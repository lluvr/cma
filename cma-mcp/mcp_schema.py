"""
MCP tool input schemas and metadata.

This module is the single source of truth for cma-mcp's tool surface.
Each tool entry mirrors a bash cma primitive (see cma's DESIGN.md);
the schema describes the input shape an MCP client passes; the
description teaches the agent both how to invoke the tool and when
to invoke it (operator says X, OR the agent itself recognizes a
capture-worthy moment).

Field-name discipline: snake_case in MCP schema (e.g.,
`applies_when`, `revisit_when`, `miss_id`). cma_subprocess translates
these to bash cma's CLI flag form (`--applies-when`, `--revisit-when`,
`--miss-id`).

Surface labels are open-ended. cma's data substrate stores `surface`
as an opaque string; the canonical examples (`auth`, `db`, `docs`,
`ui`, `infra`, `general`, `git`) are listed in the field description
but operators may pass any short label that fits their work.

`fm` (failure-mode) is opaque per DECISIONS AD-006. cma-mcp does not
bundle a failure-mode catalog. Tool descriptions reference Lodestone
as the canonical methodology that owns the FM-1..10 vocabulary;
operators using a different methodology pass that methodology's tag
through as opaque data.
"""

from __future__ import annotations

from typing import Any


# ── shared schema fragments ─────────────────────────────────────────

_SURFACE_DESCRIPTION = (
    "Surface label (the domain area). Canonical values used by the cma "
    "reference implementation: auth, db, docs, ui, infra, general, git. "
    "Custom values are accepted; cma stores the surface as an opaque "
    "string."
)

_FM_DESCRIPTION = (
    "Failure-mode tag, opaque to cma. When the operator uses a "
    "methodology with a canonical catalog (such as Lodestone's "
    "FM-1..10, see https://github.com/Clarethium/lodestone), pass "
    "that tag here as a string. cma-mcp does not bundle the catalog "
    "itself. If unset, cma falls back to the operator's "
    "CMA_FM_CLASSIFIER plugin (if configured) or stores the miss "
    "with no fm."
)


# ── input size bounds ───────────────────────────────────────────────
#
# Every string field carries an upper bound so an adversarial or
# malfunctioning MCP client cannot push payloads past the OS ARG_MAX
# limit (typically ~2 MiB on Linux x86_64) when cma-mcp shells out to
# bash cma. The bounds below leave headroom for argv overhead and
# multiple fields per call.
#
# MAX_DESCRIPTION   one-line capture summaries. 4 KiB is generous.
# MAX_TEXTURE       multi-line excerpts. 64 KiB covers realistic
#                   conversation excerpts; longer payloads should be
#                   stored externally and referenced by path.
# MAX_SHORT_FIELD   labels, predicates, IDs. 2 KiB.
MAX_DESCRIPTION = 4096
MAX_TEXTURE = 65536
MAX_SHORT_FIELD = 2048


def _surface_field() -> dict:
    return {
        "type": "string",
        "maxLength": MAX_SHORT_FIELD,
        "description": _SURFACE_DESCRIPTION,
    }


def _fm_field() -> dict:
    return {
        "type": "string",
        "maxLength": MAX_SHORT_FIELD,
        "description": _FM_DESCRIPTION,
    }


# ── per-tool definitions ────────────────────────────────────────────

CMA_MISS = {
    "name": "cma_miss",
    "title": "Record a miss",
    "description": (
        "Capture a failure: a specific moment where work fell short of "
        "intent and is likely to recur. Wraps `cma miss`.\n\n"
        "Invoke when (a) the operator says 'record a miss', 'log this', "
        "'this was wrong', or similar, OR (b) you yourself notice a "
        "miss worth surfacing in future similar work.\n\n"
        "Description should preserve enough specifics that the same "
        "failure-shape would be recognizable next time it appears. "
        "Generic captures ('I made a mistake') are useless; specific "
        "captures ('I claimed verified without testing the cross-tenant "
        "write path') fire as warnings later via cma's surface-time "
        "matching.\n\n"
        "Texture preservation: pass `intended` (what was about to "
        "happen), `corrected` (what happened instead), and `excerpt` "
        "(the conversation excerpt) when available. Texture-preserved "
        "misses surface in cma's behavior-layer validation view "
        "(`cma_stats` with view=behavior)."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["description"],
        "properties": {
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": MAX_DESCRIPTION,
                "description": (
                    "What failed, in the operator's own words. Phrase "
                    "actively ('Treated X as Y without verifying') "
                    "rather than passively. Specific enough that the "
                    "same shape of failure would be recognizable next "
                    "time."
                ),
            },
            "surface": _surface_field(),
            "fm": _fm_field(),
            "files": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Comma-separated list of files involved in the "
                    "failure. Used for surface auto-detection at "
                    "surface-time matching."
                ),
            },
            "intended": {
                "type": "string",
                "maxLength": MAX_TEXTURE,
                "description": (
                    "What was about to happen (the counterfactual). "
                    "Texture field; preserves the conditions of the "
                    "failure so cma_stats view=behavior can identify "
                    "behavior pivots."
                ),
            },
            "corrected": {
                "type": "string",
                "maxLength": MAX_TEXTURE,
                "description": (
                    "What happened instead, after correction. Texture "
                    "field; pairs with `intended` to capture the "
                    "behavior pivot."
                ),
            },
            "excerpt": {
                "type": "string",
                "maxLength": MAX_TEXTURE,
                "description": (
                    "Multi-line excerpt of the conversation or session "
                    "that produced the miss. Newlines and quotes are "
                    "preserved through bash cma's JSON encoding."
                ),
            },
        },
    },
}

CMA_DECISION = {
    "name": "cma_decision",
    "title": "Record an architectural or strategic decision",
    "description": (
        "Capture a non-trivial choice the operator wants surfaced in "
        "future similar work. Wraps `cma decision`.\n\n"
        "Format: 'TOPIC: choice (rationale)'. The TOPIC is the decision "
        "domain; the choice is what was decided; the rationale is the "
        "why.\n\n"
        "Invoke when (a) the operator articulates a decision, OR "
        "(b) you yourself are about to commit to or recommend a "
        "non-trivial choice (pattern, architecture, security stance, "
        "configuration philosophy) whose rationale matters more than "
        "its mechanics.\n\n"
        "Read the cma://decisions resource first to avoid duplicating "
        "an existing decision. Implementation tweaks, bug fixes, "
        "polish, refactors are not decisions.\n\n"
        "Pass `applies_when` to set the predicate cma matches against "
        "context keywords at surface time. A decision with "
        "applies_when='auth db' surfaces whenever the current action's "
        "surface or file path contains 'auth' or 'db', closing the "
        "decision-surfacing loop."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["description"],
        "properties": {
            "description": {
                "type": "string",
                "minLength": 15,
                "maxLength": MAX_DESCRIPTION,
                "description": (
                    "TOPIC: choice (rationale). Real-world decisions "
                    "like 'GIT: Commit only' (16 chars) are valid."
                ),
            },
            "surface": _surface_field(),
            "applies_when": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Predicate matched against context keywords at "
                    "surface time. Coarse predicates (surface name, "
                    "file pattern) are sufficient; cma performs "
                    "substring matching."
                ),
            },
        },
    },
}

CMA_REJECT = {
    "name": "cma_reject",
    "title": "Record an explicit rejection",
    "description": (
        "Capture an option considered and ruled out. Survives session "
        "compaction and prevents silently rebuilding what was "
        "deliberately not built. Wraps `cma reject`.\n\n"
        "Format: 'OPTION: reason for elimination'.\n\n"
        "Invoke when (a) the operator states a rejection, OR (b) you "
        "yourself recognize that you have just eliminated an option "
        "whose rationale is non-obvious enough that a future you "
        "(or another model) might rebuild it without context.\n\n"
        "Read the cma://rejections resource first to see what is "
        "already eliminated.\n\n"
        "Pass `revisit_when` to name the trigger that would warrant "
        "reconsidering the rejection ('if performance becomes "
        "critical', 'if Python 4 ships', etc.)."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["description"],
        "properties": {
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": MAX_DESCRIPTION,
                "description": "OPTION: reason for elimination.",
            },
            "surface": _surface_field(),
            "revisit_when": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Trigger that would warrant reconsidering this "
                    "rejection. Surfaces alongside the rejection so "
                    "operators see the reopen condition in context."
                ),
            },
        },
    },
}

CMA_PREVENTED = {
    "name": "cma_prevented",
    "title": "Record a prevention catch",
    "description": (
        "Capture a moment where a surfaced warning actually changed "
        "behavior. The catch is the evidence compound learning works; "
        "without preventions captured, the loop's effect is invisible. "
        "Wraps `cma prevented`.\n\n"
        "Invoke immediately after the catch, while the chain (warning "
        "→ recognition → different choice) is still legible. "
        "Triggered by either (a) operator request, OR (b) your own "
        "recognition that you almost did something a warning had "
        "named, and you stopped.\n\n"
        "Description names what was almost done versus what was done "
        "instead. If the warning came from a specific prior miss, "
        "pass that miss's id as `miss_id` so cma can compute the "
        "miss's prevention rate."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["description"],
        "properties": {
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": MAX_DESCRIPTION,
                "description": (
                    "What was almost done versus what was done "
                    "instead. The chain is most useful when explicit."
                ),
            },
            "miss_id": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "ID of the original miss this prevention links to "
                    "(format: YYYYMMDD-HHMMSS-<8-hex>). Lets cma "
                    "compute the miss's prevention rate."
                ),
            },
            "warning_id": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "ID of the surface event whose warning was heeded. "
                    "Optional; cma uses it to track which warnings "
                    "actually catch repeats."
                ),
            },
        },
    },
}

CMA_DISTILL = {
    "name": "cma_distill",
    "title": "Promote, retire, or review distilled learnings",
    "description": (
        "Operate on cma's core-learnings layer: promote a captured "
        "pattern to permanent surfacing, retire one that no longer "
        "applies, or preview the patterns that have accumulated since "
        "the last distillation. Wraps `cma distill`.\n\n"
        "Three modes:\n"
        "- `default`: promote a learning. Pass `description` (the "
        "  distilled rule), optional `scope` (project / language / "
        "  general; default general) and optional `surface`.\n"
        "- `retire`: mark matching core learnings as retired. Pass "
        "  `pattern` (substring matched against existing learnings).\n"
        "- `review`: read-only preview of patterns that would warrant "
        "  distillation. No other arguments.\n\n"
        "Invoke when the operator articulates a distilled learning, "
        "or when reviewing recurring miss patterns and wanting to "
        "promote one to permanent surfacing."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["mode"],
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["default", "retire", "review"],
                "description": (
                    "Operation mode. `default` promotes; `retire` "
                    "removes from active surfacing; `review` previews."
                ),
            },
            "description": {
                "type": "string",
                "minLength": 8,
                "maxLength": MAX_DESCRIPTION,
                "description": (
                    "Distilled rule (mode=default only). Phrased as a "
                    "permanent rule, not a one-off observation."
                ),
            },
            "pattern": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Substring pattern (mode=retire only). Matches "
                    "against existing core learnings; matches are "
                    "marked retired."
                ),
            },
            "scope": {
                "type": "string",
                "enum": ["project", "language", "general"],
                "description": (
                    "Scope of the learning (mode=default only). "
                    "Defaults to 'general'."
                ),
            },
            "surface": _surface_field(),
        },
    },
}

CMA_SURFACE = {
    "name": "cma_surface",
    "title": "Surface relevant prior captures for the current context",
    "description": (
        "Bring relevant prior captures into view for the current "
        "context: misses with matching surface or file path, decisions "
        "with matching applies_when, active rejections, and core "
        "learnings. Wraps `cma surface`.\n\n"
        "This call has a side effect: cma writes a record to "
        "surface_events.jsonl with the filters used and the matched "
        "captures. The leak-detection view (cma_stats view=leaks) "
        "later joins these events against subsequent misses to flag "
        "failures that occurred despite a relevant warning being "
        "surfaced. Disabling the log defeats leak detection, so cma-mcp "
        "does not expose the --no-log flag.\n\n"
        "Invoke when about to act on a domain (file edit, command "
        "execution, design decision) and the agent wants to inherit "
        "prior context relevant to that action. Without arguments, "
        "surfaces the most relevant captures for the current working "
        "directory."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "surface": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Filter by domain area. Matches captures whose "
                    "stored surface equals this value, or whose "
                    "applies_when predicate (decisions only) "
                    "substring-matches it."
                ),
            },
            "file": {
                "type": "string",
                "maxLength": MAX_SHORT_FIELD,
                "description": (
                    "Filter by file path (or basename). Matches "
                    "captures whose `files` field includes this value."
                ),
            },
            "type": {
                "type": "string",
                "enum": ["miss", "decision", "rejection", "prevention"],
                "description": "Filter by capture type.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum number of results. Default 10.",
            },
        },
    },
}

CMA_STATS = {
    "name": "cma_stats",
    "title": "Compound-practice evidence dashboard",
    "description": (
        "Compute the evidence dashboard for compound practice over "
        "time. Wraps `cma stats`.\n\n"
        "Views:\n"
        "- `default`: summary (totals, recent activity, top surfaces, "
        "  top failure shapes, prevention rate, recurrence trends).\n"
        "- `leaks`: failures that occurred despite an active warning "
        "  having been surfaced. Each leak increments the warning's "
        "  weight. The empirical signal that compound learning is "
        "  working (or not).\n"
        "- `recurrence`: failure shapes ordered by recurrence rate. "
        "  Identifies preventions that are not working.\n"
        "- `preventions`: captured preventions with linked misses. "
        "  Evidence of the loop closing.\n"
        "- `rejections`: active rejections with surfaces, ages, and "
        "  revisit triggers.\n"
        "- `behavior`: behavior pivots from texture-preserved misses "
        "  (those captured with `intended` and `corrected`). Surfaces "
        "  patterns where surfaced warnings consistently changed "
        "  operator behavior.\n\n"
        "Invoke when the operator wants quantitative evidence the "
        "loop is closing, or when the agent is evaluating which "
        "captures matter most for the current work."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "view": {
                "type": "string",
                "enum": [
                    "default",
                    "leaks",
                    "recurrence",
                    "preventions",
                    "rejections",
                    "behavior",
                ],
                "description": (
                    "Which view to compute. Defaults to 'default' "
                    "(summary)."
                ),
            },
        },
    },
}


# Ordered list (the order defines the sequence in tools/list response).
TOOLS: list[dict[str, Any]] = [
    CMA_MISS,
    CMA_DECISION,
    CMA_REJECT,
    CMA_PREVENTED,
    CMA_DISTILL,
    CMA_SURFACE,
    CMA_STATS,
]


# ── resources ─────────────────────────────────────────────────────

RESOURCES: list[dict[str, Any]] = [
    {
        "uri": "cma://decisions",
        "name": "decisions",
        "title": "Active decisions in scope",
        "description": (
            "Architectural and strategic decisions the operator has "
            "captured, filtered to those in scope for the current "
            "project (plus global-scope decisions). Sorted by recency."
        ),
        "mimeType": "application/json",
    },
    {
        "uri": "cma://rejections",
        "name": "rejections",
        "title": "Active rejections",
        "description": (
            "Options the operator has explicitly rejected and the "
            "reason. Filtered to the current project. Sorted by "
            "recency."
        ),
        "mimeType": "application/json",
    },
    {
        "uri": "cma://core",
        "name": "core",
        "title": "Active core learnings",
        "description": (
            "Distilled learnings promoted to permanent surfacing via "
            "cma_distill. Retired learnings are filtered out."
        ),
        "mimeType": "application/json",
    },
    {
        "uri": "cma://stats",
        "name": "stats",
        "title": "Compound-practice statistics summary",
        "description": (
            "Default stats summary. For specific views (leaks, "
            "recurrence, preventions, rejections, behavior), call the "
            "cma_stats tool with the view argument."
        ),
        "mimeType": "application/json",
    },
]


def get_tool(name: str) -> dict[str, Any] | None:
    """Look up a tool definition by name."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_resource(uri: str) -> dict[str, Any] | None:
    """Look up a resource definition by URI."""
    for res in RESOURCES:
        if res["uri"] == uri:
            return res
    return None
